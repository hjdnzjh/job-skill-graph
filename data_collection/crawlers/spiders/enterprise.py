"""Enterprise official website career-page spider.

Targets company career portals (e.g. https://careers.huawei.com, https://hr.tencent.com).
These are usually server-rendered HTML pages or internal JSON APIs.
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


class EnterpriseSpider(BaseSpider):
    """Crawl job openings from enterprise official career portals."""

    source_type = DataSourceType.ENTERPRISE
    source_name = "enterprise_official"

    # Representative enterprise career pages. In production, expand this list.
    ENTERPRISE_SOURCES = [
        {
            "name": "华为招聘",
            "career_url": "https://career.huawei.com/socRecruitment/",
            "api_url": "https://career.huawei.com/socRecruitment/queryPortalJobList",
            "method": "POST",
        },
        {
            "name": "腾讯招聘",
            "career_url": "https://careers.tencent.com/search.html",
            "api_url": "https://careers.tencent.com/tencentcareer/api/post/Query",
            "method": "POST",
        },
        {
            "name": "字节跳动",
            "career_url": "https://jobs.bytedance.com/experienced/position",
            "api_url": "https://jobs.bytedance.com/api/recruit/position/list",
            "method": "POST",
        },
        {
            "name": "阿里巴巴",
            "career_url": "https://talent.alibaba.com/off-campus/",
            "api_url": "https://talent.alibaba.com/position/search",
            "method": "POST",
        },
    ]

    def crawl(
        self, companies: List[str] = None, keywords: List[str] = None
    ) -> List[UnifiedJobSchema]:
        """Crawl enterprise career pages."""
        keywords = keywords or [""]
        results: List[UnifiedJobSchema] = []

        for source in self.ENTERPRISE_SOURCES:
            if companies and source["name"] not in companies:
                continue
            for keyword in (keywords or [""]):
                try:
                    items = self._crawl_enterprise(source, keyword)
                    results.extend(items)
                    logger.info(f"[{source['name']}] keyword={keyword or '*'} → {len(items)} records")
                except Exception as exc:
                    logger.error(f"[{source['name']}] failed: {exc}")

        return results

    def _crawl_enterprise(self, source: dict, keyword: str) -> List[UnifiedJobSchema]:
        """Paginate through one enterprise's career API."""
        records: List[UnifiedJobSchema] = []
        page = 1

        while page <= 5:  # safety limit
            try:
                payload = self._build_request(source, keyword, page)
                if source["method"] == "POST":
                    resp = self._post(
                        source["api_url"],
                        json_data=payload,
                        headers={"Referer": source["career_url"]},
                    )
                else:
                    resp = self._get(source["api_url"], params=payload)

                data = resp.json()
                items = self._extract_items(source["name"], data)
                if not items:
                    break

                for item in items:
                    try:
                        records.append(self.parse_item(item, source["name"]))
                    except Exception as exc:
                        logger.warning(f"Parse item failed: {exc}")

                page += 1
            except Exception as exc:
                logger.warning(f"Page {page} for {source['name']} failed: {exc}")
                break

        return records

    def _build_request(self, source: dict, keyword: str, page: int) -> dict:
        """Build request payload for each enterprise."""
        name = source["name"]
        if name == "华为招聘":
            return {"pageNo": page, "pageSize": 20, "keyWord": keyword}
        elif name == "腾讯招聘":
            return {"pageIndex": page, "pageSize": 20, "keyword": keyword}
        elif name == "字节跳动":
            return {"page": page, "size": 20, "keyword": keyword}
        elif name == "阿里巴巴":
            return {"page": page, "pageSize": 20, "keyWord": keyword}
        return {"page": page, "keyword": keyword, "pageSize": 20}

    def _extract_items(self, source_name: str, data: dict) -> List[dict]:
        """Extract job list from each enterprise's response envelope."""
        if source_name == "华为招聘":
            return data.get("data", {}).get("list", [])
        elif source_name == "腾讯招聘":
            return data.get("Data", {}).get("Posts", [])
        elif source_name == "字节跳动":
            return data.get("data", {}).get("list", [])
        elif source_name == "阿里巴巴":
            return data.get("data", {}).get("list", [])
        return data.get("data", {}).get("list", data.get("data", []))

    # ------------------------------------------------------------------
    # Unified parser
    # ------------------------------------------------------------------

    def parse_item(self, raw: Dict[str, Any], source_name: str = "") -> UnifiedJobSchema:
        job_title = self._clean_text(
            raw.get("positionName") or raw.get("title") or raw.get("jobName", "")
        )
        company = source_name or raw.get("companyName", "")
        location = self._clean_text(
            raw.get("workCity") or raw.get("city") or raw.get("location", "")
        )
        description = raw.get("description") or raw.get("jobRequirement") or raw.get("detail", "")
        department = raw.get("departmentName") or raw.get("department", "")
        source_id = str(raw.get("id") or raw.get("postId") or raw.get("positionId", ""))

        salary_min, salary_max = self._parse_salary(
            raw.get("salary") or raw.get("salaryRange", "")
        )

        # Enterprise pages often include detailed qualifications
        full_text = f"{description} {department} {raw.get('requirement', '')}"

        return self._make_record(
            source_id=source_id,
            source_url=raw.get("url", raw.get("detailUrl", "")),
            job_title_raw=job_title,
            job_title=job_title,
            company_name_raw=company,
            company_name=company,
            industry=self._infer_industry(company),
            location_raw=location,
            location=location,
            job_description=self._clean_text(description),
            salary_min=salary_min,
            salary_max=salary_max,
            experience_required=raw.get("workExperience", raw.get("experience", "")),
            education_required=raw.get("education", raw.get("degree", "")),
            job_type=raw.get("jobType", raw.get("type", "全职")),
            skills_required=self._extract_skills(full_text),
            publish_date=self._parse_date(raw.get("publishTime", raw.get("createTime", ""))),
            data_format=DataFormat.SEMI_STRUCTURED,
            extra={
                "department": department,
                "enterprise_source": source_name,
            },
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _clean_text(text: str) -> str:
        return re.sub(r"\s+", " ", (text or "")).strip()

    @staticmethod
    def _parse_salary(text: str) -> tuple:
        if not text:
            return None, None
        nums = re.findall(r"[\d.]+", text)
        if len(nums) >= 2:
            lo, hi = float(nums[0]), float(nums[1])
        elif len(nums) == 1:
            lo = hi = float(nums[0])
        else:
            return None, None
        if "万" in text:
            lo *= 10; hi *= 10
        return round(lo, 1), round(hi, 1)

    @staticmethod
    def _extract_skills(text: str) -> List[str]:
        skill_kw = [
            "Python", "Java", "Go", "C\\+\\+", "Rust", "TypeScript",
            "React", "Vue", "Spring", "Django", "Flask",
            "TensorFlow", "PyTorch", "Kubernetes", "Docker",
            "MySQL", "Redis", "Kafka", "Spark", "Flink",
        ]
        found = []
        for kw in skill_kw:
            if re.search(kw, text, re.IGNORECASE):
                found.append(kw.replace("\\", ""))
        return found

    @staticmethod
    def _parse_date(date_str: str) -> Optional[datetime]:
        if not date_str:
            return None
        for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"]:
            try:
                return datetime.strptime(date_str.strip()[:19], fmt)
            except ValueError:
                continue
        return None

    @staticmethod
    def _infer_industry(company: str) -> str:
        mapping = {
            "华为": "通信/IT", "腾讯": "互联网", "字节跳动": "互联网",
            "阿里巴巴": "电商/互联网", "百度": "互联网", "京东": "电商/互联网",
            "美团": "互联网", "滴滴": "出行/互联网", "小米": "消费电子/互联网",
        }
        for k, v in mapping.items():
            if k in company:
                return v
        return "IT/互联网"
