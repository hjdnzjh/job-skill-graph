"""Emerging job discovery: identify and define new job roles from raw titles.

Uses LLM to classify unknown job titles as emerging roles, variations of
known roles, or generic/non-tech positions, then generates structured
definitions for emerging roles.
"""

import json
import logging
import re
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

from openai import OpenAI

from kg.skill_extractor import TITLE_TO_SKILLS

logger = logging.getLogger(__name__)

# Known canonical job titles from the skill extractor
CANONICAL_TITLES = list(TITLE_TO_SKILLS.keys())

# Cleanup patterns
_CLEANUP_PATTERNS = [
    (re.compile(r'^招聘'), ''),
    (re.compile(r'\([^)]*\)'), ''),
    (re.compile(r'（[^）]*）'), ''),
    (re.compile(r'[（(]\s*[Jj]\d+\s*[)）]'), ''),
    (re.compile(r'--.*$'), ''),
    (re.compile(r'[-—].*(Base|L\d|上海|北京|深圳|杭州|广州|成都).*$'), ''),
    (re.compile(r'[，,]\s*(Base|L\d).*$'), ''),
    (re.compile(r'^\s+|\s+$'), ''),
]

DISCOVERY_SYSTEM_PROMPT = """你是一个新兴岗位分析专家。你的任务是对给定的岗位标题进行分类，并为新兴岗位生成结构化定义。

## 分类标准

对于每个标题，归入以下三类之一：

1. **variation_of_known** — 已知岗位的变体。已知岗位包括：
   Java开发工程师, Python开发工程师, 前端开发工程师, 数据分析师, 产品经理,
   C++开发工程师, 算法工程师, 测试工程师, 运维工程师, 网络安全工程师,
   嵌入式开发工程师, UI设计师, Go开发工程师, PHP开发工程师, 架构师,
   人工智能工程师, 大数据开发工程师, 区块链开发工程师, 游戏开发工程师,
   全栈开发工程师, 安卓开发工程师

   变体示例："招聘Java后端开发" → Java开发工程师
            "Web前端" → 前端开发工程师
            "Golang开发" → Go开发工程师

2. **emerging** — 新兴岗位，不在上述已知岗位列表中，且代表一个明确的技术或业务角色。
   示例：数据科学家, 机器学习工程师, 安全架构师, AIGC产品经理, 量化交易员

3. **generic** — 通用/非技术岗位，如：客服、文员、销售、会计、前台等

## 输出格式

返回纯 JSON 数组，每个元素对应一个输入标题：
[
  {
    "original_title": "招聘数据科学家",
    "normalized_title": "数据科学家",
    "category": "emerging",
    "known_match": null,
    "responsibilities": "1. 负责数据建模和特征工程...\\n2. 设计AB实验方案...\\n3. 构建数据管道...",
    "required_skills": ["Python", "SQL", "机器学习"],
    "preferred_skills": ["Spark", "深度学习", "大数据平台"],
    "industries": ["互联网/IT", "金融", "电商"],
    "confidence": 0.9
  }
]

对于 variation_of_known，填写 known_match 为匹配的已知岗位名，responsibilities 等字段可以为空。
对于 generic，normalized_title 保持原标题。
必须返回合法 JSON，不要有其他文字。"""


class EmergingJobDetector:
    """Discover emerging job roles from raw recruitment titles."""

    def __init__(self, settings):
        self.settings = settings
        self._neo4j = None
        self._llm_client = None

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
    # Title cleaning
    # ------------------------------------------------------------------

    @staticmethod
    def clean_title(raw: str) -> str:
        """Remove recruiter prefixes, location suffixes, and parentheticals."""
        result = raw.strip()
        for pat, repl in _CLEANUP_PATTERNS:
            result = pat.sub(repl, result)
        return result.strip() or raw.strip()

    # ------------------------------------------------------------------
    # Scanning
    # ------------------------------------------------------------------

    def scan_titles(self) -> dict:
        """Fetch all titles from Neo4j and classify them.

        Returns dict with keys: canonical, variation, unknown, stats.
        """
        rows = self.neo4j.run_query(
            "MATCH (j:Job)-[:HAS_TITLE]->(t:JobTitle) "
            "RETURN t.name AS title, count(j) AS cnt "
            "ORDER BY cnt DESC"
        )

        canonical = []
        variation = []
        unknown = []

        for r in rows:
            raw = r["title"]
            cnt = r["cnt"]
            cleaned = self.clean_title(raw)

            # Exact match against canonical
            if cleaned in CANONICAL_TITLES:
                canonical.append({"raw": raw, "cleaned": cleaned, "cnt": cnt,
                                  "match_type": "exact"})
                continue

            # Fuzzy match
            best_match, best_score = self._fuzzy_match(cleaned, CANONICAL_TITLES)
            if best_score >= 0.70:
                variation.append({"raw": raw, "cleaned": cleaned, "cnt": cnt,
                                  "match_type": "fuzzy",
                                  "matched_to": best_match,
                                  "similarity": round(best_score, 2)})
                continue

            unknown.append({"raw": raw, "cleaned": cleaned, "cnt": cnt})

        stats = {
            "total_titles": len(rows),
            "canonical": len(canonical),
            "variation": len(variation),
            "unknown": len(unknown),
            "total_jobs_in_unknown": sum(u["cnt"] for u in unknown),
        }

        logger.info(f"Title scan: {stats}")
        return {
            "canonical": canonical,
            "variation": variation,
            "unknown": unknown,
            "stats": stats,
        }

    @staticmethod
    def _fuzzy_match(target: str, candidates: list) -> tuple:
        """Return (best_candidate, best_score) using SequenceMatcher."""
        best = ("", 0.0)
        for c in candidates:
            score = SequenceMatcher(None, target, c).ratio()
            if score > best[1]:
                best = (c, score)
        return best

    # ------------------------------------------------------------------
    # LLM Analysis
    # ------------------------------------------------------------------

    def analyze_batch(self, titles: list, batch_size: int = 20) -> list:
        """Use LLM to classify and define a batch of unknown job titles.

        Args:
            titles: List of {"raw": str, "cleaned": str, "cnt": int} dicts.
            batch_size: Number of titles per LLM call.

        Returns:
            List of analyzed job dicts with definitions for emerging roles.
        """
        results = []
        for i in range(0, len(titles), batch_size):
            batch = titles[i:i + batch_size]
            raw_titles = [t["cleaned"] for t in batch]

            messages = [
                {"role": "system", "content": DISCOVERY_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(raw_titles, ensure_ascii=False)},
            ]

            logger.info(f"Analyzing batch {i//batch_size + 1}, {len(batch)} titles")

            response = self.llm.chat.completions.create(
                model=self.settings.llm_model,
                messages=messages,
                temperature=0.1,
            )

            content = response.choices[0].message.content.strip()
            content = re.sub(r'^```(?:json)?\s*\n?', '', content)
            content = re.sub(r'\n?```\s*$', '', content)

            try:
                parsed = json.loads(content)
                # Merge back original metadata
                for j, item in enumerate(parsed):
                    if j < len(batch):
                        item["original_title"] = batch[j]["raw"]
                        item["job_count"] = batch[j]["cnt"]
                results.extend(parsed)
            except json.JSONDecodeError as exc:
                logger.error(f"Failed to parse LLM response: {exc}")
                logger.debug(f"Raw response: {content[:500]}")

        # Sort emerging first, then by confidence
        cat_order = {"emerging": 0, "variation_of_known": 1, "generic": 2}
        results.sort(key=lambda x: (cat_order.get(x.get("category", "generic"), 9),))
        return results

    # ------------------------------------------------------------------
    # Neo4j storage
    # ------------------------------------------------------------------

    def save_emerging_jobs(self, jobs: list):
        """Save emerging job definitions to Neo4j.

        Creates EmergingJob nodes and links to Skill/Industry nodes.
        """
        emerging = [j for j in jobs if j.get("category") == "emerging"]

        if not emerging:
            logger.info("No emerging jobs to save")
            return

        # Ensure constraints
        self.neo4j.init_db()

        for job in emerging:
            title = job.get("normalized_title", "")
            if not title:
                continue

            props = {
                "name": title,
                "original_title": job.get("original_title", ""),
                "responsibilities": job.get("responsibilities", ""),
                "confidence": job.get("confidence", 0.0),
                "job_count": job.get("job_count", 0),
            }

            # Create EmergingJob node
            query = """
            MERGE (e:EmergingJob {name: $name})
            SET e += $props
            """
            self.neo4j.run_query(query, {
                "name": title,
                "props": props,
            })

            # Link required skills
            for skill_name in job.get("required_skills", []):
                self.neo4j.run_query(
                    "MATCH (e:EmergingJob {name: $job_name}) "
                    "MERGE (s:Skill {name: $skill_name}) "
                    "MERGE (e)-[:REQUIRES]->(s)",
                    {"job_name": title, "skill_name": skill_name}
                )

            # Link preferred skills
            for skill_name in job.get("preferred_skills", []):
                self.neo4j.run_query(
                    "MATCH (e:EmergingJob {name: $job_name}) "
                    "MERGE (s:Skill {name: $skill_name}) "
                    "MERGE (e)-[:PREFERS]->(s)",
                    {"job_name": title, "skill_name": skill_name}
                )

            # Link industries
            for ind_name in job.get("industries", []):
                self.neo4j.run_query(
                    "MATCH (e:EmergingJob {name: $job_name}) "
                    "MERGE (i:Industry {name: $ind_name}) "
                    "MERGE (e)-[:BELONGS_TO]->(i)",
                    {"job_name": title, "ind_name": ind_name}
                )

        logger.info(f"Saved {len(emerging)} emerging jobs to Neo4j")

    def list_emerging(self) -> list:
        """List saved emerging jobs from Neo4j."""
        rows = self.neo4j.run_query(
            "MATCH (e:EmergingJob) "
            "RETURN e.name AS name, e.confidence AS confidence, "
            "e.job_count AS job_count, e.responsibilities AS responsibilities "
            "ORDER BY e.confidence DESC"
        )
        return rows
