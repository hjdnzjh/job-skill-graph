"""Liepin (猎聘) collector — Playwright browser-based.

Extends BaseCollector to scrape job listings from liepin.com.
Shares the same DOM parsing logic as crawlers/recruitment.py.
"""

import atexit
import logging
import random
import re
import time
from typing import Any, Dict, List, Optional

try:
    import nest_asyncio
    nest_asyncio.apply()
except ImportError:
    pass

from collector.base import BaseCollector

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level persistent browser (shared across all LiepinCollector instances)
# ---------------------------------------------------------------------------
_module_browser = None
_module_pw = None


def _cleanup_browser():
    """Close the module-level browser and stop Playwright."""
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


# ---------------------------------------------------------------------------
# City code mapping
# ---------------------------------------------------------------------------
LIEPIN_CITY_CODES = {
    "北京": "010", "上海": "020", "深圳": "050090", "广州": "050020",
    "杭州": "060020", "成都": "280020", "南京": "060080", "武汉": "170020",
    "西安": "200020", "苏州": "060050", "重庆": "060040", "长沙": "140030",
    "天津": "030020", "合肥": "080010", "郑州": "170010", "济南": "120010",
    "青岛": "120030", "厦门": "090010", "福州": "090020", "大连": "230020",
    "沈阳": "230010", "昆明": "250010", "贵阳": "240010", "东莞": "050070",
    "佛山": "050050", "宁波": "060070", "无锡": "060030", "珠海": "050080",
}

# ---------------------------------------------------------------------------
# Skill keywords for extraction
# ---------------------------------------------------------------------------
SKILL_KEYWORDS = [
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


class LiepinCollector(BaseCollector):
    """Collect job listings from Liepin (猎聘) using Playwright."""

    platform = "liepin"

    SEARCH_URL = "https://www.liepin.com/zhaopin/"

    def __init__(self, fetch_details: bool = False, headless: bool = True,
                 executable_path: Optional[str] = None):
        """Initialize the Liepin collector.

        Args:
            fetch_details: If True, also fetch each job's detail page for
                           richer description and skill tags.
            headless: Run the browser in headless mode.
            executable_path: Optional path to a Chromium/Chrome executable.
        """
        super().__init__()
        self.fetch_details = fetch_details
        self.headless = headless
        self.executable_path = executable_path or (
            r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        )
        self._browser = None
        self._pw = None
        self._pages_created = 0

    # ------------------------------------------------------------------
    # Browser lifecycle
    # ------------------------------------------------------------------

    def _ensure_browser(self):
        """Lazily initialise the module-level Playwright browser."""
        global _module_browser, _module_pw
        if _module_browser is None:
            from playwright.sync_api import sync_playwright
            _module_pw = sync_playwright().start()
            _module_browser = _module_pw.chromium.launch(
                executable_path=self.executable_path,
                headless=self.headless,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
            )
            atexit.register(_cleanup_browser)
        self._browser = _module_browser
        self._pw = _module_pw

    def _new_page(self):
        """Create a fresh browser context and page with anti-detection measures."""
        self._ensure_browser()
        self._pages_created += 1
        context = self._browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="zh-CN",
        )
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        """)
        return context.new_page()

    # ------------------------------------------------------------------
    # BaseCollector interface
    # ------------------------------------------------------------------

    def search(self, keyword: str, city: str = "", page: int = 1) -> list:
        """Fetch a single page of raw job listings from Liepin.

        Args:
            keyword: Search keyword (e.g. "Java开发").
            city: Target city name (must be a key in LIEPIN_CITY_CODES).
            page: 1-indexed page number (Liepin uses 0-indexed, so we subtract 1).

        Returns:
            list of raw job dicts with keys: title, company, salary, city,
            education, experience, source_job_id, source_url, description,
            industry, skills_text.
        """
        city_code = LIEPIN_CITY_CODES.get(city, "010")
        liepin_page = page - 1  # Liepin pages are 0-indexed
        url = f"{self.SEARCH_URL}?city={city_code}&key={keyword}&page={liepin_page}"

        browser_page = self._new_page()
        results = []

        try:
            browser_page.goto(url, wait_until="load", timeout=30000)

            # Check for CAPTCHA / verification redirect
            if "wow.liepin.com" in browser_page.url or "verify" in browser_page.url.lower():
                logger.warning(f"[{self.platform}] CAPTCHA detected, returning empty list")
                browser_page.close()
                return []

            try:
                browser_page.wait_for_selector("div.job-card-pc-container", timeout=10000)
            except Exception:
                logger.debug(f"[{self.platform}] No job cards for {keyword}/{city} page={page}")
                browser_page.close()
                return []

            time.sleep(1)
            # Scroll to trigger lazy loading
            for _ in range(2):
                browser_page.evaluate("window.scrollBy(0, 800)")
                time.sleep(0.3)

            cards = browser_page.query_selector_all("div.job-card-pc-container")

            for card in cards:
                try:
                    item = self._parse_liepin_card(card)
                    if item and item.get("title"):
                        # Optionally fetch detail page for description
                        if self.fetch_details and item.get("source_url"):
                            detail = self._fetch_detail(item["source_url"])
                            item["description"] = detail.get("description", "")
                            item["skills_text"] = detail.get("skillTags", "")
                        results.append(item)
                except Exception as exc:
                    logger.debug(f"[{self.platform}] Parse card failed: {exc}")

            logger.debug(
                f"[{self.platform}] {keyword}/{city} page={page}: "
                f"{len(cards)} cards → {len(results)} parsed"
            )

        except Exception as exc:
            logger.warning(f"[{self.platform}] {keyword}/{city} page={page} failed: {exc}")
            return []
        finally:
            try:
                browser_page.close()
            except Exception:
                pass

        return results

    def normalize(self, raw: dict) -> dict:
        """Map a Liepin raw job dict to the unified schema.

        Performs salary range parsing and skill keyword extraction from
        the job description text.
        """
        description = raw.get("description", "")
        skills_text = raw.get("skills_text", "")
        combined_text = f"{description} {skills_text}"

        salary_min, salary_max = self._parse_salary(raw.get("salary", ""))
        skills = self._extract_skills(combined_text)

        return {
            "source_platform": self.platform,
            "source_job_id": str(raw.get("source_job_id", "")),
            "source_url": raw.get("source_url", ""),
            "title": raw.get("title", ""),
            "company": raw.get("company", ""),
            "city": raw.get("city", ""),
            "salary_min": salary_min,
            "salary_max": salary_max,
            "description": description,
            "education": raw.get("education", ""),
            "experience": raw.get("experience", ""),
            "industry": raw.get("industry", ""),
            "skills": skills,
        }

    # ------------------------------------------------------------------
    # Liepin card parser (same DOM logic as recruitment.py)
    # ------------------------------------------------------------------

    def _parse_liepin_card(self, card) -> Optional[dict]:
        """Parse a single job card DOM element into a raw dict."""
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
                "title": title,
                "salary": salary,
                "company": company,
                "city": location,
                "experience": experience,
                "education": education,
                "source_job_id": job_id,
                "source_url": link,
                "industry": industry,
                "description": "",
                "skills_text": "",
            }
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Detail page fetcher
    # ------------------------------------------------------------------

    def _fetch_detail(self, detail_url: str) -> dict:
        """Fetch a single job detail page for description and skill tags."""
        if not detail_url:
            return {}
        browser_page = self._new_page()
        try:
            browser_page.goto(detail_url, wait_until="load", timeout=15000)
            time.sleep(1)

            desc_el = (
                browser_page.query_selector("[class*='job-description']")
                or browser_page.query_selector("[class*='job-desc']")
                or browser_page.query_selector("[class*='content-word']")
                or browser_page.query_selector("[class*='job-main']")
            )
            description = desc_el.inner_text() if desc_el else ""

            skill_els = (
                browser_page.query_selector_all("[class*='skill']")
                or browser_page.query_selector_all("[class*='job-tag']")
            )
            skill_tags = [el.inner_text().strip() for el in skill_els]

            browser_page.close()
            return {
                "description": LiepinCollector._clean_text(description),
                "skillTags": " ".join(skill_tags),
            }
        except Exception:
            try:
                browser_page.close()
            except Exception:
                pass
            return {}

    # ------------------------------------------------------------------
    # Static helpers (same logic as recruitment.py)
    # ------------------------------------------------------------------

    @staticmethod
    def _clean_text(text: str) -> str:
        """Collapse whitespace and strip."""
        if not text:
            return ""
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _parse_salary(salary_text: str) -> tuple:
        """Parse a salary string into (min, max) in thousands (K/year).

        Handles formats like "15-25K", "10K-20K·15薪", "2-3万", "8000-12000".
        Returns (None, None) when parsing fails.
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
            hi *= 10  # 万 → K
        elif "千" in text or "k" in text.lower():
            pass  # already in K
        elif lo < 50:
            lo *= 1000
            hi *= 1000  # bare numbers (e.g. "8000") → K

        return round(lo, 1), round(hi, 1)

    @staticmethod
    def _extract_skills(text: str) -> list:
        """Extract known skill keywords from arbitrary text."""
        found = []
        for kw in SKILL_KEYWORDS:
            if re.search(kw, text, re.IGNORECASE):
                found.append(kw.replace("\\", ""))
        return found


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    c = LiepinCollector()
    result = c.collect("Java开发", "深圳", max_pages=1)
    print(f"Got {len(result.records)} records in {result.duration_seconds}s")
    if result.records:
        print(result.records[0])
