"""Industry report spider.

Targets: iResearch (艾瑞), Analysys (易观), 36kr研究院, Deloitte, McKinsey, etc.
These reports contain macro trends on job demand and skill evolution.
"""

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

from config.schema import UnifiedJobSchema, DataSourceType, DataFormat
from .base import BaseSpider

logger = logging.getLogger(__name__)


class IndustryReportSpider(BaseSpider):
    """Crawl industry research reports for employment trend insights."""

    source_type = DataSourceType.INDUSTRY_REPORT
    source_name = "industry_reports"

    REPORT_SOURCES = [
        {
            "name": "艾瑞咨询",
            "search_url": "https://www.iresearch.cn/search.html",
        },
        {
            "name": "36氪研究院",
            "search_url": "https://36kr.com/search/articles/研究院",
        },
        {
            "name": "前瞻产业研究院",
            "search_url": "https://bg.qianzhan.com/",
        },
    ]

    def crawl(self, keywords: List[str] = None) -> List[UnifiedJobSchema]:
        keywords = keywords or [
            "人才趋势", "薪酬报告", "就业市场", "数字化转型",
            "AI人才", "技能缺口", "新兴产业", "未来职业",
        ]
        results: List[UnifiedJobSchema] = []

        for source in self.REPORT_SOURCES:
            for keyword in keywords:
                try:
                    items = self._crawl_source(source, keyword)
                    for item in items:
                        try:
                            results.append(self.parse_item(item, source["name"]))
                        except Exception as exc:
                            logger.warning(f"Parse report item failed: {exc}")
                    logger.info(f"[{source['name']}] keyword={keyword} → {len(items)} reports")
                except Exception as exc:
                    logger.error(f"[{source['name']}] keyword={keyword} failed: {exc}")

        return results

    def _crawl_source(self, source: dict, keyword: str) -> List[dict]:
        results: List[dict] = []

        for page in range(1, 4):
            try:
                if source["name"] == "艾瑞咨询":
                    params = {"wd": keyword, "page": page}
                elif source["name"] == "36氪研究院":
                    params = {"q": keyword, "page": page}
                else:
                    params = {"keyword": keyword, "page": page}

                resp = self._get(source["search_url"], params=params)
                soup = self._parse_html(resp.text)

                for item_el in soup.select(
                    "li.report-item, div.search-result, div.article-item, div.report-card"
                ):
                    title_el = item_el.select_one("a.title, h3 a, a.report-title")
                    if not title_el:
                        continue
                    results.append({
                        "source_id": title_el.get("href", ""),
                        "title": title_el.get_text(strip=True),
                        "url": urljoin(source["search_url"], title_el.get("href", "")),
                        "summary": self._safe_extract(item_el, "p.desc, p.summary, div.desc"),
                        "publish_date": self._safe_extract(item_el, "span.date, time, em.date"),
                        "source_name": source["name"],
                    })
            except Exception as exc:
                logger.warning(f"Page {page} for {source['name']} failed: {exc}")
                break

        return results

    # ------------------------------------------------------------------
    # Unified parser
    # ------------------------------------------------------------------

    def parse_item(self, raw: Dict[str, Any], source_name: str = "") -> UnifiedJobSchema:
        title = raw.get("title", "")
        summary = raw.get("summary", "")
        full_text = f"{title}\n{summary}"

        # Industry reports often mention emerging roles
        emerging_roles = self._extract_emerging_roles(full_text)

        return self._make_record(
            source_id=raw.get("source_id", raw.get("url", "")),
            source_url=raw.get("url", ""),
            job_title_raw=title,
            job_title=emerging_roles[0] if emerging_roles else title,
            company_name_raw="",
            company_name=source_name,
            industry=self._infer_industry(full_text),
            location_raw="中国",
            location="中国",
            job_description=self._clean_text(full_text),
            skills_required=self._extract_hot_skills(full_text),
            abilities=self._extract_abilities(full_text),
            publish_date=self._parse_date(raw.get("publish_date", "")),
            data_format=DataFormat.UNSTRUCTURED,
            extra={
                "source_name": source_name,
                "doc_type": "industry_report",
                "emerging_roles": emerging_roles,
            },
        )

    # ------------------------------------------------------------------
    # Domain extractors
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_emerging_roles(text: str) -> List[str]:
        """Identify emerging job roles mentioned in reports."""
        roles_pattern = [
            "提示工程师", "AI训练师", "数据标注师", "大模型工程师",
            "算法工程师", "数字化转型顾问", "智能制造工程师",
            "碳管理师", "ESG分析师", "元宇宙架构师", "Web3开发",
            "自动驾驶工程师", "量子计算研究员", "生物信息学家",
            "低代码开发", "RPA工程师", "Prompt Engineer",
        ]
        return list({r for r in roles_pattern if r in text})

    @staticmethod
    def _extract_hot_skills(text: str) -> List[str]:
        """Extract in-demand skills from report text."""
        skills = [
            "Python", "Java", "Go", "Rust", "TypeScript",
            "机器学习", "深度学习", "大语言模型", "AIGC",
            "容器化", "Kubernetes", "微服务", "云原生",
            "数据工程", "数据治理", "数据安全", "隐私计算",
            "区块链", "数字孪生", "AR/VR", "边缘计算",
            "敏捷管理", "产品设计", "用户研究", "增长黑客",
        ]
        return [s for s in skills if s in text]

    @staticmethod
    def _extract_abilities(text: str) -> List[str]:
        abilities = [
            "数字素养", "跨界协作", "持续学习", "系统思维",
            "设计思维", "数据驱动决策", "创新执行", "战略规划",
        ]
        return [a for a in abilities if a in text]

    @staticmethod
    def _infer_industry(text: str) -> str:
        industries = [
            "人工智能", "大数据", "云计算", "物联网", "区块链",
            "新能源", "生物医药", "半导体", "金融科技", "教育科技",
            "智能制造", "自动驾驶", "元宇宙", "碳中和",
        ]
        for ind in industries:
            if ind in text:
                return ind
        return "数字经济"

    @staticmethod
    def _clean_text(text: str) -> str:
        return re.sub(r"\s+", " ", (text or "")).strip()

    @staticmethod
    def _parse_date(date_str: str) -> Optional[datetime]:
        if not date_str:
            return None
        date_str = re.sub(r"[年月]", "-", date_str).replace("日", "").strip()
        for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S", "%Y.%m.%d"]:
            try:
                return datetime.strptime(date_str[:10], fmt)
            except ValueError:
                continue
        return None
