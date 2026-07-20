"""Semantic Scholar academic paper collector — requests-based API client.

Target API: api.semanticscholar.org/graph/v1/paper/search
Free tier — no API key required (rate limited to ~100 requests/5 min).

Returns JSON with paper metadata: title, abstract, authors, year,
external IDs (ArXiv, DOI), and URL.
"""

import logging
import re
from typing import Optional

import requests

from collector.base import BaseCollector

logger = logging.getLogger(__name__)

# Skill keywords for extraction from title + abstract
# Same set as arxiv.py — mirrors kg/skill_extractor.py SKILL_KEYWORDS
SKILL_KEYWORDS: list[tuple] = [
    # Programming languages
    (r"\bPython\b", "Python"), (r"\bJava\b", "Java"), (r"\bGo\b", "Go"),
    (r"\bC\+\+\b", "C++"), (r"\bRust\b", "Rust"), (r"\bScala\b", "Scala"),
    (r"\bKotlin\b", "Kotlin"), (r"\bTypeScript\b", "TypeScript"),
    (r"\bJavaScript\b", "JavaScript"), (r"\bSwift\b", "Swift"),
    # Frontend
    (r"\bReact\b", "React"), (r"\bVue\b", "Vue"), (r"\bAngular\b", "Angular"),
    # Backend frameworks
    (r"\bSpring\s*Boot\b", "Spring Boot"), (r"\bDjango\b", "Django"),
    (r"\bFlask\b", "Flask"), (r"\bFastAPI\b", "FastAPI"),
    (r"\bGraphQL\b", "GraphQL"), (r"\bgRPC\b", "gRPC"),
    # Databases
    (r"\bMySQL\b", "MySQL"), (r"\bPostgreSQL\b", "PostgreSQL"),
    (r"\bMongoDB\b", "MongoDB"), (r"\bRedis\b", "Redis"),
    (r"\bElasticsearch\b", "Elasticsearch"),
    # AI / ML
    (r"\bTensorFlow\b", "TensorFlow"), (r"\bPyTorch\b", "PyTorch"),
    (r"\bKeras\b", "Keras"), (r"\bScikit-learn\b", "Scikit-learn"),
    (r"\bTransformer\b", "Transformer"), (r"\bBERT\b", "BERT"),
    (r"\bGPT\b", "GPT"), (r"\bNLP\b", "NLP"),
    (r"\bOpenCV\b", "OpenCV"), (r"\bLLM\b", "LLM"),
    (r"\bRAG\b", "RAG"), (r"\bXGBoost\b", "XGBoost"),
    (r"\bLightGBM\b", "LightGBM"), (r"\bLangChain\b", "LangChain"),
    (r"\bCUDA\b", "CUDA"), (r"\bYOLO\b", "YOLO"),
    (r"\b机器学习\b", "机器学习"), (r"\b深度学习\b", "深度学习"),
    (r"\b计算机视觉\b", "计算机视觉"), (r"\b数据挖掘\b", "数据挖掘"),
    (r"\b推荐系统\b", "推荐系统"), (r"\b强化学习\b", "强化学习"),
    (r"\b多模态\b", "多模态"), (r"\b向量数据库\b", "向量数据库"),
    (r"\b特征工程\b", "特征工程"),
    # DevOps / Cloud
    (r"\bDocker\b", "Docker"), (r"\bKubernetes\b|K8s\b", "Kubernetes"),
    (r"\bAWS\b", "AWS"), (r"\bAzure\b", "Azure"), (r"\bGCP\b", "Google Cloud"),
    (r"\bJenkins\b", "Jenkins"), (r"\bCI/CD\b", "CI/CD"),
    (r"\bNginx\b", "Nginx"), (r"\bTerraform\b", "Terraform"),
    (r"\bPrometheus\b", "Prometheus"), (r"\bGrafana\b", "Grafana"),
    (r"\bDevOps\b", "DevOps"),
    # Big data
    (r"\bSpark\b", "Spark"), (r"\bFlink\b", "Flink"),
    (r"\bHadoop\b", "Hadoop"), (r"\bHive\b", "Hive"),
    (r"\bKafka\b", "Kafka"), (r"\bRabbitMQ\b", "RabbitMQ"),
    # General
    (r"\bLinux\b", "Linux"), (r"\bGit\b", "Git"),
    (r"\b微服务\b", "微服务"), (r"\b分布式\b", "分布式"),
    (r"\b高并发\b", "高并发"), (r"\b系统设计\b", "系统设计"),
    (r"\b网络安全\b", "网络安全"), (r"\b渗透测试\b", "渗透测试"),
    (r"\b区块链\b", "区块链"), (r"\b物联网\b", "物联网"),
    (r"\b云计算\b", "云计算"), (r"\b量化交易\b", "量化交易"),
    (r"\b语音识别\b", "语音识别"), (r"\b语音合成\b", "语音合成"),
    (r"\b数据分析\b", "数据分析"), (r"\b数据仓库\b", "数据仓库"),
    (r"\b搜索引擎\b", "搜索引擎"), (r"\b向量检索\b", "向量检索"),
    (r"\b单元测试\b", "单元测试"), (r"\b自动化测试\b", "自动化测试"),
    (r"\bPandas\b", "Pandas"), (r"\bNumPy\b", "NumPy"),
    (r"\bMatplotlib\b", "Matplotlib"),
]


class SemanticScholarCollector(BaseCollector):
    """Collect academic papers from Semantic Scholar (api.semanticscholar.org)."""

    platform = "semantic_scholar"

    API_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
    PAGE_SIZE = 20

    # Requested fields per paper
    FIELDS = (
        "title,abstract,authors,year,externalIds,url,"
        "publicationTypes,journal,fieldsOfStudy,citationCount"
    )

    def search(self, keyword: str, city: str = "", page: int = 1) -> list[dict]:
        """Fetch a single page of papers from the Semantic Scholar API.

        Args:
            keyword: Search keyword (e.g. "machine learning")
            city: Ignored (academic papers not location-based)
            page: Page index (1-based), maps to API offset parameter

        Returns:
            List of raw paper dicts. Returns empty list on any error.
        """
        offset = (page - 1) * self.PAGE_SIZE

        params = {
            "query": keyword,
            "limit": self.PAGE_SIZE,
            "offset": offset,
            "fields": self.FIELDS,
        }

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json",
        }

        try:
            resp = requests.get(
                self.API_URL, params=params, headers=headers, timeout=30
            )

            if resp.status_code == 429:
                # Rate limited — Semantic Scholar free tier allows ~100 req/5 min
                logger.warning(
                    "[semantic_scholar] Rate limited (HTTP 429). "
                    "Wait before retrying."
                )
                return []

            resp.raise_for_status()
            data = resp.json()

            papers = data.get("data", [])
            if not papers:
                logger.info(
                    "[semantic_scholar] No results for keyword='%s' page=%d",
                    keyword, page,
                )
                return []

            results = []
            for paper in papers:
                raw = self._parse_paper(paper)
                if raw:
                    results.append(raw)

            return results

        except requests.RequestException as e:
            logger.error("[semantic_scholar] Request failed: %s", e)
            return []
        except (ValueError, KeyError, TypeError) as e:
            logger.error("[semantic_scholar] JSON parse / data error: %s", e)
            return []

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _parse_paper(self, paper: dict) -> Optional[dict]:
        """Parse a single paper dict from the API response into a raw dict."""
        try:
            title = paper.get("title", "") or ""
            abstract = paper.get("abstract", "") or ""

            # Authors: list of {authorId, name}
            authors_raw = paper.get("authors", []) or []
            authors = []
            first_author_name = ""
            for a in authors_raw:
                name = a.get("name", "")
                if name:
                    authors.append(name)
                    if not first_author_name:
                        first_author_name = name

            # External IDs (ArXiv, DOI, etc.)
            external_ids = paper.get("externalIds", {}) or {}
            arxiv_id = external_ids.get("ArXiv", "") or ""

            # Paper URL
            paper_url = paper.get("url", "") or ""
            if not paper_url and arxiv_id:
                paper_url = f"https://arxiv.org/abs/{arxiv_id}"

            # Source ID
            paper_id = paper.get("paperId", "") or ""

            # Year
            year = paper.get("year")
            if year:
                # Approximate publish date as Jan 1 of that year
                published = f"{year}-01-01"
            else:
                published = ""

            # Fields of study → industry-like category
            fields_of_study = paper.get("fieldsOfStudy", []) or []
            journal_info = paper.get("journal", {}) or {}

            # Determine a simple industry/category string
            industry = self._infer_industry(fields_of_study, journal_info)

            return {
                "title": title,
                "abstract": abstract,
                "published": published,
                "paper_id": paper_id,
                "paper_url": paper_url,
                "arxiv_id": arxiv_id,
                "authors": authors,
                "first_author_name": first_author_name,
                "year": year,
                "fields_of_study": fields_of_study,
                "journal": journal_info,
                "industry": industry,
            }

        except Exception as e:
            logger.warning("[semantic_scholar] Failed to parse paper: %s", e)
            return None

    @staticmethod
    def _infer_industry(fields_of_study: list, journal: dict) -> str:
        """Infer a simple industry label from fields of study and journal."""
        # Combine all field strings for matching
        field_text = " ".join(fields_of_study).lower()
        journal_name = (journal.get("name", "") or "").lower()

        if any(kw in field_text for kw in [
            "computer science", "artificial intelligence", "machine learning",
            "natural language", "computer vision", "deep learning",
            "software engineering", "data science",
        ]):
            return "计算机科学"
        elif any(kw in field_text for kw in [
            "statistics", "mathematics",
        ]):
            return "统计学"
        elif any(kw in field_text for kw in [
            "physics", "engineering", "electrical",
        ]):
            return "工程技术"
        elif any(kw in field_text for kw in [
            "biology", "medicine", "chemistry",
        ]):
            return "生物医学"
        elif any(kw in field_text for kw in [
            "economics", "business",
        ]):
            return "经济管理"
        return "学术研究"

    def normalize(self, raw: dict) -> dict:
        """Map a raw Semantic Scholar paper dict to the unified job schema.

        Field mapping:
            title    → job_title
            abstract → job_description
            first_author_name → company
            published → publish_date
            paper_url → source_url
            paper_id  → source_job_id
            industry  → industry
        """
        title = raw.get("title", "")
        abstract = raw.get("abstract", "")

        # Extract skills from title + abstract
        skills = self._extract_skills(title + " " + abstract)

        return {
            "source_platform": raw.get("source_platform", self.platform),
            "source_job_id": str(raw.get("paper_id", "")),
            "source_url": raw.get("paper_url", ""),
            "title": title,
            "company": raw.get("first_author_name", ""),
            "city": "",
            "salary_min": None,
            "salary_max": None,
            "description": abstract,
            "education": "",
            "experience": "",
            "industry": raw.get("industry", ""),
            "skills": skills,
            "publish_date": raw.get("published", "") or None,
        }

    # ------------------------------------------------------------------
    # Skill extraction
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_skills(text: str) -> list[str]:
        """Extract technology keywords from text using regex."""
        if not text:
            return []
        found = []
        seen = set()
        for pattern, skill_name in SKILL_KEYWORDS:
            if skill_name in seen:
                continue
            try:
                if re.search(pattern, text, re.IGNORECASE):
                    found.append(skill_name)
                    seen.add(skill_name)
            except re.error:
                continue
        return found


# ------------------------------------------------------------------
# Direct test entry point
# ------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    c = SemanticScholarCollector()
    result = c.collect("machine learning", max_pages=1)
    print(f"Got {len(result.records)} records in {result.duration_seconds}s")
    if result.records:
        r0 = result.records[0]
        print(f"Title: {r0.get('title', '')[:80]}...")
        print(f"Company: {r0.get('company', '')}")
        print(f"Skills: {r0.get('skills', [])}")
        print(f"Publish date: {r0.get('publish_date', '')}")
    if result.errors:
        print(f"Errors: {result.errors}")
