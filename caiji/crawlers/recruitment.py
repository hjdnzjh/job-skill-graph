"""Recruitment platform spider — Playwright browser-based.

Primary target: Liepin (猎聘) — verified accessible.
Supports multi-city, detail fetching for full job descriptions.
"""

import atexit
import logging
import random
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

# Apply nest_asyncio at module level to prevent event loop conflicts
try:
    import nest_asyncio
    nest_asyncio.apply()
except ImportError:
    pass

from config.schema import UnifiedJobSchema, DataSourceType, DataFormat

logger = logging.getLogger(__name__)

# Module-level persistent browser (shared across spider instances)
_module_browser = None
_module_pw = None

# Expanded keyword sets covering full tech spectrum
KEYWORD_GROUPS = {
    "backend": [
        "Java开发", "Python开发", "Go开发", "C++开发", "PHP开发",
        "Node.js开发", "后端开发", ".NET开发", "Ruby开发",
    ],
    "frontend": [
        "前端开发", "Web前端", "React开发", "Vue开发", "Angular开发",
        "TypeScript", "小程序开发", "H5开发",
    ],
    "data_ai": [
        "算法工程师", "人工智能", "机器学习", "深度学习", "NLP算法",
        "计算机视觉", "数据科学家", "数据分析师", "数据挖掘",
        "推荐算法", "搜索算法", "强化学习",
    ],
    "bigdata": [
        "大数据开发", "数据仓库", "ETL工程师", "Hadoop", "Spark",
        "Flink", "数据平台", "数据架构师",
    ],
    "devops": [
        "运维工程师", "DevOps", "SRE", "云平台", "Kubernetes",
        "Docker运维", "CI/CD", "自动化运维",
    ],
    "mobile": [
        "Android开发", "iOS开发", "Flutter开发", "移动端开发",
        "React Native", "鸿蒙开发",
    ],
    "testing": [
        "测试工程师", "自动化测试", "性能测试", "测试开发",
        "软件测试", "安全测试",
    ],
    "product_design": [
        "产品经理", "产品总监", "产品运营", "UI设计", "UX设计",
        "交互设计", "视觉设计",
    ],
    "security": [
        "安全工程师", "网络安全", "信息安全", "渗透测试",
        "安全运维", "安全架构",
    ],
    "blockchain": [
        "区块链开发", "智能合约", "Web3", "Solidity", "DApp",
    ],
    "game": [
        "游戏开发", "Unity", "Unreal", "游戏引擎", "游戏策划",
    ],
    "embedded": [
        "嵌入式开发", "物联网", "RTOS", "单片机", "硬件工程师",
        "FPGA", "芯片设计",
    ],
    "management": [
        "技术总监", "CTO", "架构师", "技术经理", "项目经理",
        "技术主管", "研发经理",
    ],
}

CITY_GROUPS = {
    "tier1": ["北京", "上海", "深圳", "广州", "杭州"],
    "tier2": ["成都", "南京", "武汉", "西安", "苏州", "重庆", "长沙", "天津"],
    "tier3": ["合肥", "郑州", "济南", "青岛", "厦门", "福州", "大连", "沈阳", "昆明", "贵阳"],
}


class RecruitmentSpider:
    """Crawl job listings using Playwright browser automation."""

    source_type = DataSourceType.RECRUITMENT
    source_name = "recruitment_multi"

    LIEPIN_SEARCH_URL = "https://www.liepin.com/zhaopin/"

    LIEPIN_CITY_CODES = {
        "北京": "010", "上海": "020", "深圳": "050090", "广州": "050020",
        "杭州": "060020", "成都": "280020", "南京": "060080", "武汉": "170020",
        "西安": "200020", "苏州": "060050", "重庆": "060040", "长沙": "140030",
        "天津": "030020", "合肥": "080010", "郑州": "170010", "济南": "120010",
        "青岛": "120030", "厦门": "090010", "福州": "090020", "大连": "230020",
        "沈阳": "230010", "昆明": "250010", "贵阳": "240010", "东莞": "050070",
        "佛山": "050050", "宁波": "060070", "无锡": "060030", "珠海": "050080",
    }

    def __init__(self, settings):
        self.settings = settings
        self._browser = None
        self._pw = None
        self._pages_created = 0

    def _ensure_browser(self):
        global _module_browser, _module_pw
        if _module_browser is None:
            from playwright.sync_api import sync_playwright
            _module_pw = sync_playwright().start()
            _module_browser = _module_pw.chromium.launch(
                executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                headless=self.settings.playwright_headless,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
            )
            atexit.register(_cleanup_browser)
        self._browser = _module_browser
        self._pw = _module_pw

    def _new_page(self):
        self._ensure_browser()
        self._pages_created += 1
        # Rotate user agent every ~30 pages
        ua_idx = self._pages_created // 30 % len(self.settings.user_agent_pool)
        context = self._browser.new_context(
            user_agent=self.settings.user_agent_pool[ua_idx],
            viewport={"width": 1920, "height": 1080},
            locale="zh-CN",
        )
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        """)
        return context.new_page()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def crawl(self, keywords: List[str] = None, cities: List[str] = None,
              pages: int = 3, fetch_details: bool = False) -> List[UnifiedJobSchema]:
        """Crawl Liepin across keywords × cities × pages.

        Args:
            keywords: List of search keywords.
            cities: List of target cities.
            pages: Number of search result pages per query.
            fetch_details: If True, fetch detail page for richer description.
        """
        keywords = keywords or ["Java开发", "Python开发", "前端开发", "算法工程师"]
        cities = cities or ["北京", "上海", "深圳", "杭州"]
        results = []

        for keyword in keywords:
            for city in cities:
                try:
                    records = self._crawl_liepin(keyword, city, pages=pages,
                                                  fetch_details=fetch_details)
                    results.extend(records)
                    logger.info(f"[Liepin] keyword={keyword} city={city} pgs={pages} → {len(records)} records")
                except Exception as exc:
                    logger.error(f"[Liepin] keyword={keyword} city={city} failed: {exc}")
                # Brief delay between queries
                time.sleep(random.uniform(1, 2))

        return results

    # ------------------------------------------------------------------
    # Liepin crawler
    # ------------------------------------------------------------------

    def _crawl_liepin(self, keyword: str, city: str, pages: int = 3,
                       fetch_details: bool = False) -> List[UnifiedJobSchema]:
        records = []
        city_code = self.LIEPIN_CITY_CODES.get(city, "010")

        for page_num in range(pages):
            url = f"{self.LIEPIN_SEARCH_URL}?city={city_code}&key={keyword}&page={page_num}"

            page = self._new_page()
            try:
                page.goto(url, wait_until="domcontentloaded",
                          timeout=self.settings.playwright_timeout)

                # Check for CAPTCHA / verification redirect
                if "wow.liepin.com" in page.url or "verify" in page.url.lower():
                    logger.warning(f"  Liepin CAPTCHA detected, cooling down 120s...")
                    page.close()
                    time.sleep(120)
                    page = self._new_page()
                    page.goto(url, wait_until="domcontentloaded",
                              timeout=self.settings.playwright_timeout)

                try:
                    page.wait_for_selector("div.job-card-pc-container", timeout=10000)
                except Exception:
                    logger.debug(f"  Liepin: no job cards for {keyword}/{city} p{page_num}")
                    page.close()
                    break

                time.sleep(1)
                # Scroll to trigger lazy loading
                for _ in range(2):
                    page.evaluate("window.scrollBy(0, 800)")
                    time.sleep(0.3)

                cards = page.query_selector_all("div.job-card-pc-container")

                for card in cards:
                    try:
                        item = self._parse_liepin_card(card)
                        if item and item.get("jobTitle"):
                            record = self.parse_item(item)
                            record.extra["platform"] = "liepin"
                            record.extra["search_keyword"] = keyword
                            records.append(record)
                    except Exception as exc:
                        logger.debug(f"Parse card failed: {exc}")

                logger.debug(f"  Liepin {keyword}/{city} p{page_num}: {len(cards)} cards")
                page.close()
                time.sleep(random.uniform(0.5, 1.5))

            except Exception as exc:
                logger.warning(f"Liepin {keyword}/{city} p{page_num} failed: {exc}")
                try:
                    page.close()
                except Exception:
                    pass
                break

        # Optionally fetch detail pages for better descriptions
        if fetch_details and records:
            detail_count = min(10, len(records))  # sample up to 10 per batch
            for rec in records[:detail_count]:
                if rec.source_url:
                    detail = self._crawl_detail(rec.source_url)
                    if detail.get("description") and len(detail["description"]) > 50:
                        rec.job_description = detail["description"]
                    if detail.get("skillTags"):
                        extra_skills = self._extract_skills(detail["skillTags"])
                        rec.skills_required = list(set(rec.skills_required + extra_skills))
                    time.sleep(random.uniform(1, 3))

        return records

    def _parse_liepin_card(self, card) -> Optional[dict]:
        try:
            link_el = card.query_selector('a[data-nick="job-detail-job-info"]')
            href = link_el.get_attribute("href") if link_el else ""
            link = href if href.startswith("http") else f"https://www.liepin.com{href}" if href else ""

            job_id = ""
            if link:
                m = re.search(r"/job/(\d+)", link)
                if m:
                    job_id = m.group(1)

            title_el = card.query_selector('div.ellipsis-1[title]')
            title = title_el.get_attribute("title") if title_el else ""
            if not title and title_el:
                title = title_el.inner_text().strip()

            salary = ""
            if link_el:
                salary_el = link_el.query_selector('[class*=E8PWS]')
                if salary_el:
                    salary = salary_el.inner_text().strip()

            location = ""
            if link_el:
                loc = link_el.query_selector('[class*=__9nJ]')
                if loc:
                    loc_text = loc.inner_text().strip()
                    parts = re.split(r"[·\s]+", loc_text)
                    parts = [p for p in parts if p and len(p) > 1]
                    location = parts[0] if parts else ""

            tag_els = card.query_selector_all('[class*=hJbMl]')
            experience = tag_els[0].inner_text().strip() if len(tag_els) >= 1 else ""
            education = tag_els[1].inner_text().strip() if len(tag_els) >= 2 else ""

            company_el = card.query_selector('[class*=K6Y1c]')
            company = company_el.inner_text().strip() if company_el else ""

            industry = ""
            info_el = card.query_selector('[class*=hFeAm]')
            if info_el:
                spans = info_el.query_selector_all("span")
                info_parts = [s.inner_text().strip() for s in spans]
                industry = info_parts[0] if info_parts else ""

            return {
                "jobTitle": title, "salary": salary, "companyName": company,
                "location": location, "experience": experience, "degree": education,
                "detailUrl": link, "jobId": job_id, "industryName": industry,
            }
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Detail page crawler
    # ------------------------------------------------------------------

    def _crawl_detail(self, detail_url: str) -> dict:
        if not detail_url:
            return {}
        page = self._new_page()
        try:
            page.goto(detail_url, wait_until="domcontentloaded", timeout=15000)
            time.sleep(1)

            desc_el = (page.query_selector("[class*='job-description']") or
                       page.query_selector("[class*='job-desc']") or
                       page.query_selector("[class*='content-word']") or
                       page.query_selector("[class*='job-main']"))
            description = desc_el.inner_text() if desc_el else ""

            skill_els = (page.query_selector_all("[class*='skill']") or
                         page.query_selector_all("[class*='job-tag']"))
            skill_tags = [el.inner_text().strip() for el in skill_els]

            page.close()
            return {"description": self._clean_text(description),
                    "skillTags": " ".join(skill_tags)}
        except Exception:
            try: page.close()
            except Exception: pass
            return {}

    # ------------------------------------------------------------------
    # Unified parser
    # ------------------------------------------------------------------

    def parse_item(self, raw: Dict[str, Any]) -> UnifiedJobSchema:
        job_title = self._clean_text(raw.get("jobTitle") or raw.get("job_title") or "")
        company = self._clean_text(raw.get("companyName") or raw.get("company_name") or "")
        location = self._clean_text(raw.get("city") or raw.get("location") or "")
        salary = raw.get("salary") or raw.get("provideSalary") or raw.get("salaryDesc") or ""
        description = raw.get("jobDescription") or raw.get("job_detail") or raw.get("description") or ""
        source_id = str(raw.get("jobId") or raw.get("job_id") or "")
        salary_min, salary_max = self._parse_salary(salary)

        return self._make_record(
            source_id=source_id,
            source_url=raw.get("detailUrl") or raw.get("source_url") or "",
            job_title_raw=job_title, job_title=job_title,
            company_name_raw=company, company_name=company,
            industry=raw.get("industryName") or raw.get("industry") or "",
            location_raw=location, location=location,
            job_description=self._clean_text(description),
            salary_min=salary_min, salary_max=salary_max,
            experience_required=raw.get("workingExp") or raw.get("experience") or "",
            education_required=raw.get("education") or raw.get("degree") or "",
            job_type=raw.get("jobType") or raw.get("emplType") or "",
            skills_required=self._extract_skills(description + " " + raw.get("skillTags", "")),
            publish_date=self._parse_date(raw.get("publishDate") or raw.get("createTime") or ""),
            data_format=DataFormat.SEMI_STRUCTURED,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _clean_text(text: str) -> str:
        if not text: return ""
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _parse_salary(salary_text: str) -> tuple:
        if not salary_text: return None, None
        text = salary_text.replace("·", "").replace(",", "")
        nums = re.findall(r"[\d.]+", text)
        if len(nums) >= 2:
            lo, hi = float(nums[0]), float(nums[1])
        elif len(nums) == 1:
            lo = hi = float(nums[0])
        else:
            return None, None
        if "万" in text:
            lo *= 10; hi *= 10
        elif "千" in text or "k" in text.lower():
            pass
        elif lo < 50:
            lo *= 1000; hi *= 1000
        return round(lo, 1), round(hi, 1)

    @staticmethod
    def _extract_skills(text: str) -> List[str]:
        skill_keywords = [
            "Python", "Java", "Go", "C\\+\\+", "Rust", "Scala", "Kotlin", "TypeScript",
            "React", "Vue", "Angular", "Spring", "Django", "Flask", "FastAPI",
            "TensorFlow", "PyTorch", "Keras", "Scikit-learn", "Transformer",
            "MySQL", "PostgreSQL", "MongoDB", "Redis", "Elasticsearch",
            "Docker", "Kubernetes", "K8s", "AWS", "Azure", "GCP",
            "Spark", "Flink", "Hadoop", "Kafka", "RabbitMQ",
            "Linux", "Git", "DevOps", "CI/CD", "Maven", "Gradle",
            "Spring Boot", "MyBatis", "Hibernate", "Nginx", "GraphQL",
            "微服务", "分布式", "高并发", "系统设计",
        ]
        found = []
        for kw in skill_keywords:
            if re.search(kw, text, re.IGNORECASE):
                found.append(kw.replace("\\", ""))
        return found

    @staticmethod
    def _parse_date(date_str: str) -> Optional[datetime]:
        if not date_str: return None
        for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S"]:
            try: return datetime.strptime(date_str.strip(), fmt)
            except ValueError: continue
        return None

    def _make_record(self, source_id, source_url, job_title_raw, job_title,
                     company_name_raw, company_name, industry, location_raw,
                     location, job_description, salary_min=None, salary_max=None,
                     experience_required=None, education_required=None, job_type=None,
                     skills_required=None, skills_preferred=None, abilities=None,
                     publish_date=None, data_format=DataFormat.SEMI_STRUCTURED,
                     extra=None) -> UnifiedJobSchema:
        import uuid
        return UnifiedJobSchema(
            record_id=str(uuid.uuid4()), source_id=source_id,
            source_type=self.source_type, source_name=self.source_name,
            source_url=source_url,
            job_title=job_title, job_title_raw=job_title_raw,
            company_name=company_name, company_name_raw=company_name_raw,
            industry=industry, location=location, location_raw=location_raw,
            job_description=job_description,
            salary_min=salary_min, salary_max=salary_max,
            experience_required=experience_required,
            education_required=education_required, job_type=job_type,
            skills_required=skills_required or [], skills_preferred=skills_preferred or [],
            abilities=abilities or [],
            publish_date=publish_date, crawl_timestamp=datetime.now(),
            data_format=data_format, extra=extra or {},
        )

    def __del__(self):
        pass  # Browser lifecycle managed at module level


def _cleanup_browser():
    global _module_browser, _module_pw
    try:
        if _module_browser:
            _module_browser.close()
            _module_browser = None
        if _module_pw:
            _module_pw.stop()
            _module_pw = None
    except Exception:
        pass
