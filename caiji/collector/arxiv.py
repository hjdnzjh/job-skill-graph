"""ArXiv academic paper collector — requests-based API client.

Target API: export.arxiv.org/api/query
No authentication required. Returns Atom XML with paper metadata.

Extracts CS/AI papers relevant to job skills and normalizes them
into the unified job schema for cross-source analysis.
"""

import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Optional

import requests

from collector.base import BaseCollector

logger = logging.getLogger(__name__)

# Skill keywords for extraction from title + abstract
# Reuses the same pattern set as kg/skill_extractor.py SKILL_KEYWORDS
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

# ArXiv Atom XML namespace map
_ATOM_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}


class ArxivCollector(BaseCollector):
    """Collect academic papers from ArXiv (export.arxiv.org)."""

    platform = "arxiv"

    API_URL = "http://export.arxiv.org/api/query"
    PAGE_SIZE = 20

    def search(self, keyword: str, city: str = "", page: int = 1) -> list[dict]:
        """Fetch a single page of papers from the ArXiv API.

        Args:
            keyword: Search keyword (e.g. "large language model")
            city: Ignored (academic papers not location-based)
            page: Page index (1-based), maps to API start parameter

        Returns:
            List of raw paper dicts. Returns empty list on any error.
        """
        start = (page - 1) * self.PAGE_SIZE

        params = {
            "search_query": f"all:{keyword}",
            "start": start,
            "max_results": self.PAGE_SIZE,
        }

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "application/atom+xml, application/xml, text/xml",
        }

        try:
            resp = requests.get(
                self.API_URL, params=params, headers=headers, timeout=30
            )
            resp.raise_for_status()

            if not resp.text or not resp.text.strip():
                logger.warning("[arxiv] Empty response body")
                return []

            root = ET.fromstring(resp.text)
            entries = root.findall("atom:entry", _ATOM_NS)
            if not entries:
                logger.info("[arxiv] No entries found for keyword='%s' page=%d", keyword, page)
                return []

            results = []
            for entry in entries:
                raw = self._parse_entry(entry)
                if raw:
                    results.append(raw)

            return results

        except requests.RequestException as e:
            logger.error("[arxiv] Request failed: %s", e)
            return []
        except ET.ParseError as e:
            logger.error("[arxiv] XML parse error: %s", e)
            return []
        except Exception as e:
            logger.error("[arxiv] Unexpected error: %s", e)
            return []

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _text(self, elem: Optional[ET.Element], tag: str) -> str:
        """Get text content of a child element, stripping namespace."""
        child = elem.find(f"atom:{tag}", _ATOM_NS) if elem is not None else None
        if child is not None and child.text:
            return child.text.strip()
        return ""

    def _parse_entry(self, entry: ET.Element) -> Optional[dict]:
        """Parse a single Atom <entry> into a raw paper dict."""
        try:
            title = self._text(entry, "title")
            summary = self._text(entry, "summary")
            published = self._text(entry, "published")
            arxiv_url = self._text(entry, "id")

            # Parse arxiv ID from URL, e.g. http://arxiv.org/abs/2301.12345v1 → 2301.12345
            arxiv_id = ""
            if arxiv_url:
                # Extract ID part: remove http://arxiv.org/abs/ and version suffix
                match = re.search(r"abs/([^/]+)$", arxiv_url)
                if match:
                    arxiv_id = match.group(1)

            # Extract authors (names) from <author><name> sub-elements
            authors = []
            first_author_affiliation = ""
            for author_elem in entry.findall("atom:author", _ATOM_NS):
                name = self._text(author_elem, "name")
                if name:
                    authors.append(name)
                # Try to get affiliation from arxiv namespace
                affiliation_elems = author_elem.findall("arxiv:affiliation", _ATOM_NS)
                for aff in affiliation_elems:
                    if aff is not None and aff.text:
                        if not first_author_affiliation:
                            first_author_affiliation = aff.text.strip()
                        break

            # Extract primary category
            categories = []
            for cat_elem in entry.findall("atom:category", _ATOM_NS):
                term = cat_elem.get("term", "")
                if term:
                    categories.append(term)

            return {
                "title": title,
                "summary": summary,
                "published": published,
                "arxiv_url": arxiv_url,
                "arxiv_id": arxiv_id,
                "authors": authors,
                "first_author_affiliation": first_author_affiliation,
                "categories": categories,
            }

        except Exception as e:
            logger.warning("[arxiv] Failed to parse entry: %s", e)
            return None

    def normalize(self, raw: dict) -> dict:
        """Map a raw ArXiv paper dict to the unified job schema.

        Field mapping:
            title   → job_title
            summary → job_description
            first_author_affiliation → company
            published → publish_date
            arxiv_url → source_url
            arxiv_id  → source_job_id
        """
        title = raw.get("title", "")
        summary = raw.get("summary", "")
        published_str = raw.get("published", "")
        categories = raw.get("categories", [])

        # Determine industry from arxiv category
        industry = ""
        if categories:
            primary = categories[0]
            if primary.startswith("cs."):
                industry = "计算机科学"
            elif primary.startswith("stat."):
                industry = "统计学"
            elif primary.startswith("math."):
                industry = "数学"
            elif primary.startswith("physics."):
                industry = "物理学"
            elif primary.startswith("q-bio.") or primary.startswith("q-fin."):
                industry = "交叉学科"
            else:
                industry = primary

        # Extract skills from title + summary
        skills = self._extract_skills(title + " " + summary)

        return {
            "source_platform": raw.get("source_platform", self.platform),
            "source_job_id": str(raw.get("arxiv_id", "")),
            "source_url": raw.get("arxiv_url", ""),
            "title": title,
            "company": raw.get("first_author_affiliation", ""),
            "city": "",
            "salary_min": None,
            "salary_max": None,
            "description": summary,
            "education": "",
            "experience": "",
            "industry": industry,
            "skills": skills,
            "publish_date": published_str if published_str else None,
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

    c = ArxivCollector()
    result = c.collect("large language model", max_pages=1)
    print(f"Got {len(result.records)} records in {result.duration_seconds}s")
    if result.records:
        r0 = result.records[0]
        print(f"Title: {r0.get('title', '')[:80]}...")
        print(f"Company: {r0.get('company', '')}")
        print(f"Skills: {r0.get('skills', [])}")
        print(f"Publish date: {r0.get('publish_date', '')}")
    if result.errors:
        print(f"Errors: {result.errors}")
