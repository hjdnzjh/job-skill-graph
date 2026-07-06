"""Academic paper & industry report spider.

Targets: CNKI (知网), Wanfang (万方), ArXiv, industry research portals.
"""

import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, quote

from config.schema import UnifiedJobSchema, DataSourceType, DataFormat
from .base import BaseSpider

logger = logging.getLogger(__name__)


class AcademicSpider(BaseSpider):
    """Crawl academic papers related to employment trends, skill evolution, job markets."""

    source_type = DataSourceType.ACADEMIC
    source_name = "academic_papers"

    ACADEMIC_SOURCES = [
        {
            "name": "知网 (CNKI)",
            "search_url": "https://kns.cnki.net/kns8/defaultresult/index",
        },
        {
            "name": "ArXiv CS",
            "search_url": "https://arxiv.org/search/",
            "params": {"searchtype": "all"},
        },
        {
            "name": "Semantic Scholar",
            "search_url": "https://api.semanticscholar.org/graph/v1/paper/search",
        },
    ]

    def crawl(self, keywords: List[str] = None) -> List[UnifiedJobSchema]:
        """Crawl academic papers."""
        keywords = keywords or [
            "人工智能 就业", "技能需求 演化", "劳动力市场", "数字经济 岗位",
            "skill evolution job market", "AI employment impact",
            "emerging occupations", "competency model",
        ]
        results: List[UnifiedJobSchema] = []

        for source in self.ACADEMIC_SOURCES:
            for keyword in keywords:
                try:
                    items = self._crawl_source(source, keyword)
                    for item in items:
                        try:
                            results.append(self.parse_item(item, source["name"]))
                        except Exception as exc:
                            logger.warning(f"Parse academic item failed: {exc}")
                    logger.info(f"[{source['name']}] keyword={keyword} → {len(items)} papers")
                except Exception as exc:
                    logger.error(f"[{source['name']}] keyword={keyword} failed: {exc}")

        return results

    def _crawl_source(self, source: dict, keyword: str) -> List[dict]:
        """Fetch academic paper metadata."""
        results: List[dict] = []

        if source["name"] == "Semantic Scholar":
            return self._crawl_semantic_scholar(keyword)

        # HTML-based sources
        for page in range(1, 3):
            try:
                params = {
                    **source.get("params", {}),
                    "query": keyword,
                    "start": (page - 1) * 20,
                }
                if source["name"] == "ArXiv CS":
                    params["query"] = keyword
                else:
                    params["kns"] = keyword
                    params["pageNum"] = str(page)

                resp = self._get(source["search_url"], params=params)
                soup = self._parse_html(resp.text)

                for item_el in soup.select("li.result-item, div.paper-item, li.arxiv-result"):
                    title_el = item_el.select_one("a.title, p.title a, a")
                    if not title_el:
                        continue
                    results.append({
                        "source_id": title_el.get("href", ""),
                        "title": title_el.get_text(strip=True),
                        "url": urljoin(source["search_url"], title_el.get("href", "")),
                        "abstract": self._safe_extract(item_el, "p.abstract, span.abstract, div.abstract"),
                        "authors": self._safe_extract(item_el, "span.authors, p.authors"),
                        "publish_date": self._safe_extract(item_el, "span.date, time"),
                        "source_name": source["name"],
                    })
            except Exception as exc:
                logger.warning(f"Page {page} for {source['name']} failed: {exc}")
                break

        return results

    def _crawl_semantic_scholar(self, keyword: str, limit: int = 30) -> List[dict]:
        """Use Semantic Scholar's free API."""
        try:
            resp = self._get(
                "https://api.semanticscholar.org/graph/v1/paper/search",
                params={
                    "query": keyword,
                    "limit": limit,
                    "fields": "title,abstract,authors,year,url,externalIds",
                },
            )
            data = resp.json()
            items = []
            for paper in data.get("data", []):
                items.append({
                    "source_id": paper.get("paperId", ""),
                    "title": paper.get("title", ""),
                    "url": paper.get("url", ""),
                    "abstract": paper.get("abstract", ""),
                    "authors": ", ".join(
                        a.get("name", "") for a in (paper.get("authors") or [])
                    ),
                    "publish_date": str(paper.get("year", "")),
                    "source_name": "Semantic Scholar",
                })
            return items
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Unified parser
    # ------------------------------------------------------------------

    def parse_item(self, raw: Dict[str, Any], source_name: str = "") -> UnifiedJobSchema:
        title = raw.get("title", "")
        abstract = raw.get("abstract", "")
        full_text = f"{title}\n{abstract}"

        # Extract domain topics from paper
        topics = self._extract_topics(title + " " + abstract)

        # Derive job/industry signals
        industry = self._infer_industry(full_text)

        return self._make_record(
            source_id=raw.get("source_id", raw.get("url", "")),
            source_url=raw.get("url", ""),
            job_title_raw=title,
            job_title=topics[0] if topics else title,
            company_name_raw="",
            company_name=raw.get("authors", ""),
            industry=industry,
            location_raw="学术研究",
            location="学术研究",
            job_description=self._clean_text(full_text),
            skills_required=self._extract_skills(full_text),
            abilities=self._extract_abilities(full_text),
            publish_date=self._parse_date(raw.get("publish_date", "")),
            data_format=DataFormat.UNSTRUCTURED,
            extra={
                "source_name": source_name,
                "doc_type": "academic",
                "authors": raw.get("authors", ""),
                "topics": topics,
            },
        )

    # ------------------------------------------------------------------
    # Domain extractors
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_topics(text: str) -> List[str]:
        topic_kw = [
            "大语言模型", "知识图谱", "自然语言处理", "计算机视觉",
            "人岗匹配", "推荐系统", "命名实体识别", "关系抽取",
            "技能演化", "劳动力市场", "岗位能力模型", "职业胜任力",
            "深度学习", "迁移学习", "联邦学习", "对比学习",
        ]
        return list({t for t in topic_kw if t in text})

    @staticmethod
    def _extract_skills(text: str) -> List[str]:
        skills = [
            "Python", "PyTorch", "TensorFlow", "BERT", "GPT",
            "Transformer", "NER", "知识图谱", "图神经网络",
            "机器学习", "深度学习", "NLP", "CV", "数据挖掘",
            "统计分析", "计量经济学", "因果推断",
        ]
        found = []
        for s in skills:
            if re.search(re.escape(s), text, re.IGNORECASE):
                found.append(s)
        return found

    @staticmethod
    def _extract_abilities(text: str) -> List[str]:
        abilities = [
            "分析能力", "建模能力", "实证研究", "文献综述",
            "实验设计", "数据收集", "批判性思维",
        ]
        return [a for a in abilities if a in text]

    @staticmethod
    def _infer_industry(text: str) -> str:
        mapping = {
            "医疗": "医疗健康", "金融": "金融", "教育": "教育",
            "制造": "智能制造", "交通": "交通运输", "能源": "能源",
            "零售": "零售电商", "农业": "农业",
            "人工智能": "人工智能", "大数据": "大数据",
        }
        for kw, ind in mapping.items():
            if kw in text:
                return ind
        return "跨行业"

    @staticmethod
    def _clean_text(text: str) -> str:
        return re.sub(r"\s+", " ", (text or "")).strip()

    @staticmethod
    def _parse_date(date_str: str) -> Optional[datetime]:
        if not date_str:
            return None
        if re.match(r"^\d{4}$", date_str.strip()):
            return datetime(int(date_str.strip()), 1, 1)
        for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%Y"]:
            try:
                return datetime.strptime(date_str.strip()[:10], fmt)
            except ValueError:
                continue
        return None
