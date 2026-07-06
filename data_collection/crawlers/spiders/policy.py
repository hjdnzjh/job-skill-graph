"""Policy document spider.

Targets government policy portals (gov.cn, ministry sites) for labor/employment/industry
policies. These are typically HTML pages with PDF attachments.
"""

import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

from config.schema import UnifiedJobSchema, DataSourceType, DataFormat
from .base import BaseSpider

logger = logging.getLogger(__name__)


class PolicySpider(BaseSpider):
    """Crawl employment & industry policy documents from government portals."""

    source_type = DataSourceType.POLICY
    source_name = "government_policy"

    POLICY_SOURCES = [
        {
            "name": "中国政府网-政策",
            "search_url": "https://sousuo.www.gov.cn/sousuo/search.shtml",
            "params": {"code": "17", "dataTypeId": "107", "sign": "b1110d86-5e86-47f9-9b67-d352c7e4f5c8"},
        },
        {
            "name": "人社部",
            "search_url": "https://www.mohrss.gov.cn/wap/",
        },
        {
            "name": "科技部-政策法规",
            "search_url": "https://www.most.gov.cn/kjzc/",
        },
    ]

    def crawl(self, keywords: List[str] = None) -> List[UnifiedJobSchema]:
        """Crawl policy documents related to employment, talent, industries."""
        keywords = keywords or [
            "人工智能人才", "就业政策", "数字经济", "新职业", "职业技能",
            "人才培养", "大数据产业", "新兴产业",
        ]
        results: List[UnifiedJobSchema] = []

        for source in self.POLICY_SOURCES:
            for keyword in keywords:
                try:
                    items = self._crawl_source(source, keyword)
                    for item in items:
                        try:
                            results.append(self.parse_item(item, source["name"]))
                        except Exception as exc:
                            logger.warning(f"Parse policy item failed: {exc}")
                    logger.info(f"[{source['name']}] keyword={keyword} → {len(items)} docs")
                except Exception as exc:
                    logger.error(f"[{source['name']}] keyword={keyword} failed: {exc}")

        return results

    def _crawl_source(self, source: dict, keyword: str) -> List[dict]:
        """Fetch policy search results from a government portal."""
        results: List[dict] = []

        for page in range(1, 4):
            try:
                params = {
                    **source.get("params", {}),
                    "searchWord": keyword,
                    "page": str(page),
                    "pageSize": "20",
                }
                resp = self._get(source["search_url"], params=params)
                soup = self._parse_html(resp.text)

                # Government sites typically list results as <li> or <div> items
                for item_el in soup.select("li.search-result, div.result-item, ul.listTxt li"):
                    title_el = item_el.select_one("a[title], a")
                    if not title_el:
                        continue
                    results.append({
                        "source_id": title_el.get("href", ""),
                        "title": title_el.get("title", "") or title_el.get_text(strip=True),
                        "url": urljoin(source["search_url"], title_el.get("href", "")),
                        "summary": self._safe_extract(item_el, "p, span.summary, div.summary"),
                        "publish_date": self._safe_extract(item_el, "span.date, em.date"),
                        "source_name": source["name"],
                    })
            except Exception as exc:
                logger.warning(f"Page {page} for {source['name']} failed: {exc}")
                break

        return results

    # ------------------------------------------------------------------
    # Unified parser — policy docs → job/ability insight records
    # ------------------------------------------------------------------

    def parse_item(self, raw: Dict[str, Any], source_name: str = "") -> UnifiedJobSchema:
        """Parse a policy document into a UnifiedJobSchema.

        Policy docs don't have job postings per se, but they define:
        - Emerging job categories (新职业)
        - Required skills / qualifications for regulated roles
        - Industry direction → demand signals
        """
        title = raw.get("title", "")
        summary = raw.get("summary", "")
        full_text = f"{title}\n{summary}"

        # Extract job/role mentions from policy text
        job_mentions = self._extract_job_titles(full_text)

        return self._make_record(
            source_id=raw.get("source_id", raw.get("url", "")),
            source_url=raw.get("url", ""),
            job_title_raw=title,
            job_title=job_mentions[0] if job_mentions else title,
            company_name_raw="",
            company_name="政府/政策文件",
            industry=self._infer_policy_industry(full_text),
            location_raw="全国",
            location="全国",
            job_description=self._clean_text(full_text),
            skills_required=self._extract_skills(full_text),
            abilities=self._extract_abilities(full_text),
            publish_date=self._parse_date(raw.get("publish_date", "")),
            data_format=DataFormat.UNSTRUCTURED,
            extra={
                "source_name": source_name,
                "doc_type": "policy",
                "job_mentions": job_mentions,
            },
        )

    # ------------------------------------------------------------------
    # Domain-specific extractors
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_job_titles(text: str) -> List[str]:
        """Find job/role titles mentioned in policy text."""
        patterns = [
            r"(人工智能\S*(?:工程师|科学家|研究员|架构师))",
            r"(大数据\S*(?:工程师|分析师|架构师|开发))",
            r"(云计算\S*(?:工程师|架构师))",
            r"(区块链\S*(?:工程师|开发))",
            r"(物联网\S*(?:工程师))",
            r"([一-鿿]{2,6}(?:算法工程师|安全工程师|运维工程师|测试工程师))",
        ]
        found = set()
        for pat in patterns:
            found.update(re.findall(pat, text))
        return list(found)[:10]

    @staticmethod
    def _extract_skills(text: str) -> List[str]:
        skills = [
            "Python", "Java", "C\\+\\+", "R", "MATLAB",
            "TensorFlow", "PyTorch", "Hadoop", "Spark", "Storm",
            "机器学习", "深度学习", "自然语言处理", "计算机视觉", "语音识别",
            "数据挖掘", "数据分析", "数据可视化", "统计建模",
            "云计算", "边缘计算", "物联网", "5G", "工业互联网",
            "项目管理", "敏捷开发", "DevOps",
        ]
        found = []
        for s in skills:
            if re.search(s, text, re.IGNORECASE):
                found.append(s.replace("\\", ""))
        return found

    @staticmethod
    def _extract_abilities(text: str) -> List[str]:
        abilities_kw = [
            "创新能力", "团队协作", "沟通能力", "逻辑思维", "学习能力",
            "领导力", "问题解决", "抗压能力", "数据分析能力", "项目管理能力",
        ]
        return [a for a in abilities_kw if a in text]

    @staticmethod
    def _infer_policy_industry(text: str) -> str:
        industries = {
            "人工智能": "人工智能",
            "大数据": "大数据",
            "数字经济": "数字经济",
            "新能源": "新能源",
            "生物医药": "生物医药",
            "集成电路": "集成电路/半导体",
            "智能制造": "智能制造",
            "金融科技": "金融科技",
        }
        for kw, ind in industries.items():
            if kw in text:
                return ind
        return "综合"

    @staticmethod
    def _clean_text(text: str) -> str:
        return re.sub(r"\s+", " ", (text or "")).strip()

    @staticmethod
    def _parse_date(date_str: str) -> Optional[datetime]:
        if not date_str:
            return None
        date_str = re.sub(r"[年月]", "-", date_str).replace("日", "").strip()
        for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S"]:
            try:
                return datetime.strptime(date_str[:10], fmt)
            except ValueError:
                continue
        return None
