"""RAG engine: retrieval-augmented generation for job-skill QA.

Uses TF-IDF + cosine similarity for retrieval (no external model downloads needed),
Neo4j for structured graph context, and DeepSeek LLM for answer generation.

Hybrid: vector search (TF-IDF) + graph context (Neo4j) → LLM answer.
Includes hallucination detection via graph fact-checking.
"""

import json
import logging
import os
import pickle
import re
from typing import Any, Dict, List, Optional

import numpy as np
from openai import OpenAI

logger = logging.getLogger(__name__)

INDEX_PATH = "data/rag_index.pkl"

# Hallucination detection patterns
_HALLUCINATION_PATTERNS = [
    (re.compile(r'(?:不需要|无需|没有).*?(?:技能|要求|经验)'), "可能遗漏关键技能"),
    (re.compile(r'(?:月薪|薪资).*?(\d{5,6})'), "薪资数字需核实"),
]

# Common skill names for graph context extraction
_KNOWN_SKILLS = [
    'Python', 'Java', 'MySQL', 'Linux', 'Git', 'Redis', 'Docker',
    'Kafka', 'Spring Boot', 'Django', 'C++', 'Go', 'JavaScript', 'React',
    'Vue', 'Spark', 'Flink', 'Hadoop', 'AI', '机器学习', '深度学习',
    'NLP', 'Kubernetes', 'MongoDB', 'PostgreSQL', 'TypeScript',
    '微服务', '分布式', 'MyBatis', 'Hive', 'HBase', 'Elasticsearch',
    'HTML5', 'CSS3', 'Node.js', 'Webpack', 'TensorFlow', 'PyTorch',
    'Scikit-learn', 'FastAPI', 'Flask', 'Spring Cloud', 'Android',
    'iOS', 'Unity', '小程序', 'RAG', 'LLM',
]


class RAGEngine:
    """Retrieval-Augmented Generation for job-skill knowledge QA."""

    def __init__(self, settings):
        self.settings = settings
        self._neo4j = None
        self._llm_client = None
        self._vectorizer = None
        self._doc_vectors = None  # TF-IDF document matrix
        self._docs = []
        self._doc_ids = []
        self._doc_metas = []

    @property
    def neo4j(self):
        if self._neo4j is None:
            from kg.neo4j_client import Neo4jClient
            self._neo4j = Neo4jClient(self.settings)
        return self._neo4j

    @property
    def llm(self):
        if self._llm_client is None:
            self._llm_client = OpenAI(
                api_key=self.settings.llm_api_key,
                base_url=self.settings.llm_base_url,
            )
        return self._llm_client

    def close(self):
        if self._neo4j:
            self._neo4j.close()

    # ------------------------------------------------------------------
    # Indexing (TF-IDF)
    # ------------------------------------------------------------------

    def build_index(self, force: bool = False):
        """Collect all job-related knowledge from Neo4j and build TF-IDF index."""
        if not force and os.path.exists(INDEX_PATH):
            self._load_index()
            logger.info(f"Loaded cached index: {len(self._docs)} docs")
            return len(self._docs)

        docs = []
        ids_ = []
        metas = []

        # 1. Skill documents
        skill_rows = self.neo4j.run_query(
            "MATCH (:Job)-[:REQUIRES]->(s:Skill) "
            "RETURN s.name AS name, s.category AS category, count(*) AS demand "
            "ORDER BY demand DESC"
        )
        for r in skill_rows:
            text = (f"技能名称: {r['name']}。"
                    f"类别: {r.get('category', '未分类')}。"
                    f"需求量: {r['demand']} 个岗位要求此技能。")
            docs.append(text)
            ids_.append(f"skill_{r['name']}")
            metas.append({"type": "skill", "name": r["name"]})

        # 2. Job title documents
        title_rows = self.neo4j.run_query(
            "MATCH (t:JobTitle) WHERE exists((:Job)-[:HAS_TITLE]->(t)) "
            "RETURN t.name AS name, count { (j:Job)-[:HAS_TITLE]->(t) } AS cnt "
            "ORDER BY cnt DESC"
        )
        for r in title_rows:
            skill_info = self.neo4j.run_query(
                "MATCH (j:Job)-[:HAS_TITLE]->(t:JobTitle {name: $title}), "
                "(j)-[:REQUIRES]->(s:Skill) "
                "RETURN s.name AS skill, count(*) AS n ORDER BY n DESC LIMIT 10",
                {"title": r["name"]},
            )
            top_skills = [s["skill"] for s in skill_info]

            salary_rows = self.neo4j.run_query(
                "MATCH (j:Job)-[:HAS_TITLE]->(t:JobTitle {name: $title}) "
                "RETURN avg(j.salary_min) AS avg_min, avg(j.salary_max) AS avg_max",
                {"title": r["name"]},
            )
            sal = salary_rows[0] if salary_rows else {}

            text = (f"岗位名称: {r['name']}。"
                    f"招聘数量: {r['cnt']} 个。"
                    f"核心技能: {', '.join(top_skills)}。")
            if sal.get("avg_min") and sal.get("avg_max"):
                text += f"平均薪资范围: {int(sal['avg_min'])}-{int(sal['avg_max'])} 元/月。"
            docs.append(text)
            ids_.append(f"title_{r['name']}")
            metas.append({"type": "job_title", "name": r["name"]})

        # 3. City info
        city_rows = self.neo4j.run_query(
            "MATCH (j:Job)-[:LOCATED_IN]->(c:City) "
            "RETURN c.name AS city, count(j) AS cnt, "
            "avg(j.salary_min) AS avg_min, avg(j.salary_max) AS avg_max "
            "ORDER BY cnt DESC LIMIT 20"
        )
        for r in city_rows:
            text = (f"城市: {r['city']}。岗位数量: {r['cnt']}。"
                    f"平均薪资: {int(r.get('avg_min', 0) or 0)}-{int(r.get('avg_max', 0) or 0)} 元/月。")
            docs.append(text)
            ids_.append(f"city_{r['city']}")
            metas.append({"type": "city", "name": r["city"]})

        # 4. Industry info
        ind_rows = self.neo4j.run_query(
            "MATCH (j:Job)-[:BELONGS_TO]->(i:Industry) "
            "RETURN i.name AS industry, count(j) AS cnt ORDER BY cnt DESC LIMIT 20"
        )
        for r in ind_rows:
            top_skills = self.neo4j.run_query(
                "MATCH (j:Job)-[:BELONGS_TO]->(i:Industry {name: $ind}), "
                "(j)-[:REQUIRES]->(s:Skill) "
                "RETURN s.name AS skill, count(*) AS n ORDER BY n DESC LIMIT 8",
                {"ind": r["industry"]},
            )
            skills_str = ", ".join(s["skill"] for s in top_skills)
            text = (f"行业: {r['industry']}。岗位数量: {r['cnt']}。热门技能: {skills_str}。")
            docs.append(text)
            ids_.append(f"industry_{r['industry']}")
            metas.append({"type": "industry", "name": r["industry"]})

        # 5. Emerging jobs
        emerging = self.neo4j.run_query(
            "MATCH (e:EmergingJob) RETURN e.name AS name, "
            "e.responsibilities AS resp"
        )
        for r in emerging:
            text = f"新兴岗位: {r['name']}。职责: {r.get('resp', '暂无')}"
            docs.append(text)
            ids_.append(f"emerging_{r['name']}")
            metas.append({"type": "emerging_job", "name": r["name"]})

        if not docs:
            logger.warning("No documents to index")
            return 0

        # Build TF-IDF vectors
        from sklearn.feature_extraction.text import TfidfVectorizer
        self._vectorizer = TfidfVectorizer(
            max_features=2000,
            ngram_range=(1, 3),
            analyzer='char_wb',  # Character-level works better for Chinese
        )
        self._doc_vectors = self._vectorizer.fit_transform(docs)
        self._docs = docs
        self._doc_ids = ids_
        self._doc_metas = metas

        self._save_index()
        logger.info(f"Indexed {len(docs)} documents (TF-IDF, {len(self._vectorizer.get_feature_names_out())} features)")
        return len(docs)

    def _save_index(self):
        os.makedirs(os.path.dirname(INDEX_PATH), exist_ok=True)
        with open(INDEX_PATH, "wb") as f:
            pickle.dump({
                "vectorizer": self._vectorizer,
                "doc_vectors": self._doc_vectors,
                "docs": self._docs,
                "doc_ids": self._doc_ids,
                "doc_metas": self._doc_metas,
            }, f)

    def _load_index(self):
        with open(INDEX_PATH, "rb") as f:
            data = pickle.load(f)
        self._vectorizer = data["vectorizer"]
        self._doc_vectors = data["doc_vectors"]
        self._docs = data["docs"]
        self._doc_ids = data["doc_ids"]
        self._doc_metas = data["doc_metas"]

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def query(self, question: str, top_k: int = 5) -> dict:
        """Answer a question with RAG: TF-IDF retrieve + graph context + LLM generate.

        Returns:
            dict: {question, answer, retrieved_docs, graph_context, warnings}
        """
        # Ensure index is loaded
        if self._vectorizer is None:
            if os.path.exists(INDEX_PATH):
                self._load_index()
            else:
                self.build_index()

        # Step 1: TF-IDF retrieval
        q_vec = self._vectorizer.transform([question])
        from sklearn.metrics.pairwise import cosine_similarity
        scores = cosine_similarity(q_vec, self._doc_vectors).flatten()
        top_indices = np.argsort(scores)[::-1][:top_k]

        retrieved_docs = [self._docs[i] for i in top_indices if scores[i] > 0.01]

        # Step 2: Structured graph context
        graph_context = self._get_graph_context(question)

        # Step 3: Build augmented prompt and generate
        context_text = "\n".join(f"- {doc}" for doc in retrieved_docs)
        graph_text = "\n".join(f"- {ctx}" for ctx in graph_context)

        messages = [
            {"role": "system", "content": RAG_SYSTEM_PROMPT},
            {"role": "user", "content": (
                f"## 问题\n{question}\n\n"
                f"## 检索到的相关知识\n{context_text or '（未检索到相关文档）'}\n\n"
                f"## 图谱结构化数据\n{graph_text or '（未找到图谱数据）'}\n\n"
                f"请基于以上知识回答问题。如果信息不足，请诚实说明。"
            )},
        ]

        response = self.llm.chat.completions.create(
            model=self.settings.llm_model,
            messages=messages,
            temperature=0.1,
        )
        answer = response.choices[0].message.content.strip()

        # Step 4: Hallucination check (rules + graph verification)
        basic_warnings = self._check_hallucination(answer, retrieved_docs, graph_context)
        from kg.hallucination_checker import HallucinationChecker
        hc = HallucinationChecker(self.settings)
        verification = hc.verify(answer)
        warnings = basic_warnings + [
            {"type": "fact_verification", "message": w.get("correction", w.get("claim", ""))}
            for w in verification.get("warnings", [])
        ]

        return {
            "question": question,
            "answer": answer,
            "retrieved_docs": retrieved_docs,
            "graph_context": graph_context,
            "warnings": warnings,
            "hallucination_score": verification.get("overall_score", 1.0),
            "verified_claims": verification.get("verified_claims", 0),
            "total_claims": verification.get("total_claims", 0),
        }

    def _get_graph_context(self, question: str) -> list:
        """Extract structured context from Neo4j based on question keywords."""
        ctx = []

        # Skill mentions
        found_skills = [s for s in _KNOWN_SKILLS if s.lower() in question.lower()]
        if found_skills:
            skill_rows = self.neo4j.run_query(
                "MATCH (:Job)-[:REQUIRES]->(s:Skill) WHERE s.name IN $skills "
                "RETURN s.name AS skill, s.category AS category, count(*) AS demand",
                {"skills": found_skills},
            )
            for r in skill_rows:
                ctx.append(f"[图谱] {r['skill']}（{r['category']}）: {r['demand']} 个岗位需求")

        # City mentions
        import difflib
        city_rows_all = self.neo4j.run_query(
            "MATCH (c:City) RETURN c.name AS name"
        )
        city_names = [c["name"] for c in city_rows_all]
        for city in city_names:
            if city in question:
                rows = self.neo4j.run_query(
                    "MATCH (j:Job)-[:LOCATED_IN]->(c:City {name: $city}) "
                    "RETURN count(j) AS cnt, "
                    "avg(j.salary_min) AS avg_min, avg(j.salary_max) AS avg_max",
                    {"city": city},
                )
                for r in rows:
                    ctx.append(f"[图谱] {city}: {r['cnt']} 岗位, "
                              f"均薪 {int(r.get('avg_min',0) or 0)}-{int(r.get('avg_max',0) or 0)}/月")
                break

        # Salary keywords
        if any(w in question for w in ("薪资", "工资", "薪酬", "待遇", "月薪", "年薪")):
            sal_rows = self.neo4j.run_query(
                "MATCH (j:Job) WHERE j.salary_min IS NOT NULL "
                "RETURN avg(j.salary_min) AS avg_min, avg(j.salary_max) AS avg_max, "
                "min(j.salary_min) AS gmin, max(j.salary_max) AS gmax"
            )
            for r in sal_rows:
                ctx.append(f"[图谱] 整体薪资: 均 {int(r['avg_min'])}-{int(r['avg_max'])}/月, "
                          f"范围 {int(r['gmin'])}-{int(r['gmax'])}")

        # Job title mentions
        title_rows_all = self.neo4j.run_query(
            "MATCH (t:JobTitle) WHERE exists((:Job)-[:HAS_TITLE]->(t)) "
            "RETURN t.name AS name"
        )
        for t in title_rows_all:
            if t["name"] in question:
                skill_rows = self.neo4j.run_query(
                    "MATCH (j:Job)-[:HAS_TITLE]->(t:JobTitle {name: $title}), "
                    "(j)-[:REQUIRES]->(s:Skill) "
                    "RETURN s.name AS skill, count(*) AS n ORDER BY n DESC LIMIT 8",
                    {"title": t["name"]},
                )
                if skill_rows:
                    skills = [f"{s['skill']}({s['n']})" for s in skill_rows]
                    ctx.append(f"[图谱] {t['name']} 核心技能: {', '.join(skills)}")
                break

        return ctx[:8]  # Limit context length

    def _check_hallucination(self, answer: str, retrieved_docs: list,
                              graph_context: list) -> list:
        """Detect potential hallucinations."""
        warnings = []
        for pattern, msg in _HALLUCINATION_PATTERNS:
            if pattern.search(answer):
                warnings.append({"type": "pattern_match", "message": msg})

        all_context = " ".join(retrieved_docs + graph_context)
        # Extract potential English skill names
        skills_in_answer = re.findall(
            r'[A-Z][a-zA-Z+#.0-9]*(?:\s?[A-Z][a-zA-Z+#.0-9]*)?', answer
        )
        for skill in skills_in_answer[:8]:
            if len(skill) > 2 and skill.lower() not in all_context.lower():
                # Check if it's a common English word vs a skill name
                if skill in _KNOWN_SKILLS:
                    warnings.append({
                        "type": "unverified_entity",
                        "message": f"'{skill}' 未在检索结果中找到支撑数据",
                    })

        return warnings


RAG_SYSTEM_PROMPT = """你是一个岗位-能力知识图谱智能助手。基于检索到的知识回答用户问题。

## 规则
1. 优先使用检索知识回答，引用具体数据
2. 信息不足时明确说明"根据现有数据..."
3. 不编造技能名称、薪资数字或公司名
4. 回答简洁结构化，使用中文
5. 薪资问题需注明数据来源于招聘数据"""
