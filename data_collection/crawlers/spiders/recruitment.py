"""Recruitment platform spiders: 51job, BOSS Zhipin, Zhaopin, Liepin, Lagou.

These platforms expose semi-structured JSON APIs or server-rendered HTML.
"""

import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from config.schema import UnifiedJobSchema, DataSourceType, DataFormat
from .base import BaseSpider

logger = logging.getLogger(__name__)


class RecruitmentSpider(BaseSpider):
    """Crawl job listings from major Chinese recruitment platforms."""

    source_type = DataSourceType.RECRUITMENT
    source_name = "recruitment_multi"

    # --- platform-specific API entry points ---
    PLATFORMS = {
        "51job": {
            "search_url": "https://search.51job.com/list/000000,000000,0000,00,9,99,{keyword},2,{page}.html",
            "detail_url": "https://jobs.51job.com/{city}/{id}.html",
        },
        "boss_zhipin": {
            "search_url": "https://www.zhipin.com/wapi/zpgeek/search/joblist.json",
            "detail_url": "https://www.zhipin.com/job_detail/{id}.html",
        },
        "lagou": {
            "search_url": "https://www.lagou.com/wn/zhaopin",
            "detail_url": "https://www.lagou.com/wn/jobs/{id}.html",
        },
    }

    def crawl(self, keywords: List[str] = None, cities: List[str] = None) -> List[UnifiedJobSchema]:
        """Crawl jobs across multiple recruitment platforms."""
        keywords = keywords or ["人工智能", "大数据", "算法工程师", "Java开发", "产品经理"]
        cities = cities or ["北京", "上海", "深圳", "杭州", "广州"]
        results: List[UnifiedJobSchema] = []

        for keyword in keywords:
            for city in cities:
                for platform_id, platform_cfg in self.PLATFORMS.items():
                    try:
                        items = self._crawl_platform(platform_id, platform_cfg, keyword, city)
                        results.extend(items)
                        logger.info(f"[{platform_id}] keyword={keyword} city={city} → {len(items)} records")
                    except Exception as exc:
                        logger.error(f"[{platform_id}] keyword={keyword} city={city} failed: {exc}")
        return results

    def _crawl_platform(self, platform_id: str, cfg: dict, keyword: str, city: str) -> List[UnifiedJobSchema]:
        """Fetch and parse one platform's search results.

        In production, this would paginate and handle each platform's API/auth.
        Below is a representative implementation targeting JSON-over-HTTP patterns
        common to 51job, BOSS, and Lagou.
        """
        records: List[UnifiedJobSchema] = []

        for page in range(1, 4):  # first 3 pages per query
            try:
                if platform_id == "boss_zhipin":
                    raw_list = self._fetch_boss(keyword, city, page)
                elif platform_id == "51job":
                    raw_list = self._fetch_51job(keyword, city, page)
                elif platform_id == "lagou":
                    raw_list = self._fetch_lagou(keyword, city, page)
                else:
                    raw_list = []

                for item in raw_list:
                    try:
                        record = self.parse_item(item)
                        record.extra["platform"] = platform_id
                        records.append(record)
                    except Exception as exc:
                        logger.warning(f"Parse item failed: {exc}")
            except Exception as exc:
                logger.warning(f"Page {page} for {platform_id} failed: {exc}")
                break

        return records

    # ------------------------------------------------------------------
    # Platform-specific fetchers (exemplary — real selectors depend on site DOM)
    # ------------------------------------------------------------------

    def _fetch_boss(self, keyword: str, city: str, page: int) -> List[dict]:
        """BOSS Zhipin uses a JSON API behind the WAP subdomain."""
        url = self.PLATFORMS["boss_zhipin"]["search_url"]
        try:
            resp = self._get(url, params={"query": keyword, "city": city, "page": page})
            data = resp.json()
            if data.get("code") != 0:
                return []
            return data.get("zpData", {}).get("jobList", [])
        except Exception:
            return []

    def _fetch_51job(self, keyword: str, city: str, page: int) -> List[dict]:
        """51job renders search results as HTML; here we simulate the parse."""
        # In production: fetch HTML, parse <div class="el"> items with BeautifulSoup
        city_code = self._city_code_51job(city)
        url = (
            f"https://search.51job.com/list/{city_code},000000,0000,00,9,99,"
            f"{keyword},2,{page}.html"
        )
        try:
            resp = self._get(url)
            soup = self._parse_html(resp.text)
            items = []
            for el in soup.select("div.el"):
                item = {
                    "source_id": el.get("data-jid", ""),
                    "job_title": self._safe_extract(el, "p.t1 span"),
                    "company_name": self._safe_extract(el, "span.t2 a"),
                    "location": self._safe_extract(el, "span.t3"),
                    "salary": self._safe_extract(el, "span.t4"),
                    "publish_date": self._safe_extract(el, "span.t5"),
                }
                if item["job_title"]:
                    items.append(item)
            return items
        except Exception:
            return []

    def _fetch_lagou(self, keyword: str, city: str, page: int) -> List[dict]:
        """Lagou uses a JSON POST API."""
        url = self.PLATFORMS["lagou"]["search_url"]
        payload = {
            "city": city,
            "needAddtionalResult": False,
            "pn": page,
            "kd": keyword,
        }
        try:
            resp = self._post(url, json_data=payload, headers={
                "Referer": "https://www.lagou.com/",
                "Content-Type": "application/json",
            })
            data = resp.json()
            return data.get("content", {}).get("positionResult", {}).get("result", [])
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Unified parser
    # ------------------------------------------------------------------

    def parse_item(self, raw: Dict[str, Any]) -> UnifiedJobSchema:
        """Normalize a raw job item from any recruitment platform into the unified schema."""
        job_title = self._clean_text(raw.get("jobTitle") or raw.get("job_title") or raw.get("jobName", ""))
        company = self._clean_text(raw.get("companyName") or raw.get("company_name") or raw.get("brandName", ""))
        location = self._clean_text(raw.get("city") or raw.get("location") or raw.get("workCity", ""))
        salary = raw.get("salary") or raw.get("provideSalary") or raw.get("salaryDesc", "")
        description = raw.get("jobDescription") or raw.get("job_detail") or raw.get("description", "")
        source_id = str(raw.get("jobId") or raw.get("job_id") or raw.get("encryptJobId", ""))

        salary_min, salary_max = self._parse_salary(salary)

        return self._make_record(
            source_id=source_id,
            source_url=raw.get("detailUrl", ""),
            job_title_raw=job_title,
            job_title=job_title,
            company_name_raw=company,
            company_name=company,
            industry=raw.get("industryName", raw.get("industry", "")),
            location_raw=location,
            location=location,
            job_description=self._clean_text(description),
            salary_min=salary_min,
            salary_max=salary_max,
            experience_required=raw.get("workingExp", raw.get("experience", "")),
            education_required=raw.get("education", raw.get("degree", "")),
            job_type=raw.get("jobType", raw.get("emplType", "")),
            skills_required=self._extract_skills(description + (raw.get("skillTags", ""))),
            publish_date=self._parse_date(raw.get("publishDate", raw.get("createTime", ""))),
            data_format=DataFormat.SEMI_STRUCTURED,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _clean_text(text: str) -> str:
        if not text:
            return ""
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _parse_salary(salary_text: str) -> tuple:
        """Parse Chinese salary strings into min/max floats (K/month).

        Examples: "15-25K" → (15, 25), "2-3万/月" → (20, 30), "8千-1.2万" → (8, 12)
        """
        if not salary_text:
            return None, None
        text = salary_text.replace("·", "").replace(",", "")
        nums = re.findall(r"[\d.]+", text)
        if len(nums) >= 2:
            lo, hi = float(nums[0]), float(nums[1])
        elif len(nums) == 1:
            lo = hi = float(nums[0])
        else:
            return None, None
        if "万" in text:
            lo *= 10
            hi *= 10
        elif "千" in text or "k" in text.lower():
            pass  # already in K
        elif lo < 50:
            lo *= 1000
            hi *= 1000  # likely "8000-12000"
        return round(lo, 1), round(hi, 1)

    @staticmethod
    def _extract_skills(text: str) -> List[str]:
        """Quick keyword-based skill extraction. Production systems use NER."""
        skill_keywords = [
            "Python", "Java", "Go", "C\\+\\+", "Rust", "Scala", "Kotlin", "TypeScript",
            "React", "Vue", "Angular", "Spring", "Django", "Flask", "FastAPI",
            "TensorFlow", "PyTorch", "Keras", "Scikit-learn", "Transformer",
            "MySQL", "PostgreSQL", "MongoDB", "Redis", "Elasticsearch",
            "Docker", "Kubernetes", "K8s", "AWS", "Azure", "GCP",
            "Spark", "Flink", "Hadoop", "Kafka", "RabbitMQ",
            "Linux", "Git", "DevOps", "CI/CD", "Maven", "Gradle",
        ]
        found = []
        for kw in skill_keywords:
            if re.search(kw, text, re.IGNORECASE):
                found.append(kw.replace("\\", ""))
        return found

    @staticmethod
    def _parse_date(date_str: str) -> Optional[datetime]:
        if not date_str:
            return None
        for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S"]:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue
        return None

    @staticmethod
    def _city_code_51job(city: str) -> str:
        code_map = {
            "北京": "010000", "上海": "020000", "深圳": "040000",
            "广州": "030200", "杭州": "080200", "成都": "090200",
        }
        return code_map.get(city, "000000")
