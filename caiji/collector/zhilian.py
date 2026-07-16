"""Zhilian (智联招聘) collector — Playwright-based with XHR interception.

智联招聘's API (fe-api.zhaopin.com/c/i/sou) returns 200 but with 0 results
(numFound:999999) when called directly, indicating bot detection. This collector
uses Playwright to drive a real browser session and intercept the authenticated
XHR calls the page makes natively, falling back to DOM extraction if needed.

Search URL: https://sou.zhaopin.com/?kw={keyword}&city={city_code}
"""

import json
import logging
import re
import time
from typing import Any, Dict, List, Optional

from collector.base import BaseCollector

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Zhilian city codes (used in sou.zhaopin.com search URL)
# ---------------------------------------------------------------------------
CITY_CODES = {
    "北京": "530",
    "上海": "538",
    "深圳": "765",
    "广州": "763",
    "杭州": "653",
    "成都": "801",
    "南京": "635",
    "武汉": "736",
    "西安": "854",
}

SEARCH_URL = "https://sou.zhaopin.com/"
API_PATH = "/c/i/sou"


class ZhilianCollector(BaseCollector):
    """Collect job listings from 智联招聘 via browser automation.

    Uses Playwright to navigate to the search page and either intercept the
    XHR API responses (preferred — full structured data) or scrape the rendered
    DOM as a fallback.
    """

    platform = "zhilian"

    def __init__(self):
        self._pw = None
        self._browser = None

    # ------------------------------------------------------------------
    # Browser lifecycle
    # ------------------------------------------------------------------

    def _ensure_browser(self):
        """Lazily start Playwright and launch a persistent Chromium browser."""
        if self._browser is not None:
            return

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise ImportError(
                "playwright is required for ZhilianCollector. "
                "Install with: pip install playwright && playwright install chromium"
            )

        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        logger.info("[zhilian] browser launched")

    def _new_page(self):
        """Create a new page with stealthy context settings."""
        self._ensure_browser()
        context = self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
            locale="zh-CN",
        )
        # Hide webdriver property to evade detection
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            // Overwrite navigator.plugins to appear normal
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            // Overwrite navigator.languages
            Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN', 'zh', 'en']});
        """)
        return context.new_page()

    # ------------------------------------------------------------------
    # search() — core interface required by BaseCollector
    # ------------------------------------------------------------------

    def search(self, keyword: str, city: str = "", page: int = 1) -> List[dict]:
        """Fetch a single page of job listings from Zhilian.

        Strategy:
          1. Navigate to the search page with keyword + city.
          2. Set up XHR response interception on the API endpoint.
          3. Wait for results to appear (either intercepted JSON or DOM).
          4. Parse and return a list of raw job dicts.
          5. Fall back gracefully if anti-bot blocks us.

        Args:
            keyword: Search keyword, e.g. "Java", "Python开发"
            city: Target city name (must be a key in CITY_CODES)
            page: Result page number (Zhilian pages by offset; page 1 = start=0)

        Returns:
            List of raw job dicts ready for normalize()
        """
        city_code = CITY_CODES.get(city, "")
        search_url = f"{SEARCH_URL}?kw={keyword}"
        if city_code:
            search_url += f"&city={city_code}"

        # Zhilian uses start= param for pagination (60 per page)
        if page > 1:
            start = (page - 1) * 60
            search_url += f"&p={page}"

        logger.info(f"[zhilian] search: keyword='{keyword}' city='{city}' page={page} url={search_url}")

        intercepted_data: List[dict] = []

        try:
            pg = self._new_page()

            # ----------------------------------------------------------
            # Intercept XHR responses to the search API
            # ----------------------------------------------------------
            def _capture_response(response):
                if API_PATH in response.url and response.status == 200:
                    try:
                        body = response.json()
                        if body.get("code") == 200 or body.get("code") == "000":
                            data = body.get("data", {})
                            results = data.get("results") or data.get("list") or []
                            if results:
                                logger.debug(
                                    f"[zhilian] intercepted {len(results)} jobs from API"
                                )
                                intercepted_data.extend(results)
                    except Exception:
                        pass  # Non-JSON or parse error — ignore

            pg.on("response", _capture_response)

            # ----------------------------------------------------------
            # Navigate and wait for content
            # ----------------------------------------------------------
            try:
                pg.goto(search_url, wait_until="load", timeout=30000)
            pg.wait_for_load_state("networkidle")
            except Exception:
                logger.warning("[zhilian] initial navigation timed out, continuing...")

            # Wait for either API data or DOM elements
            waited = 0
            max_wait = 12  # seconds
            while waited < max_wait:
                if intercepted_data:
                    break
                # Check for DOM results
                try:
                    dom_items = pg.query_selector_all(".joblist-box__item, .contentpile__content, .jobitem")
                    if dom_items and len(dom_items) > 0:
                        break
                except Exception:
                    pass
                time.sleep(0.5)
                waited += 0.5

            # Extra settling time
            time.sleep(2)

            # ----------------------------------------------------------
            # Scroll to trigger lazy-loaded content
            # ----------------------------------------------------------
            for _ in range(3):
                pg.evaluate("window.scrollBy(0, 800)")
                time.sleep(0.5)

            # ----------------------------------------------------------
            # Extract data
            # ----------------------------------------------------------
            if intercepted_data:
                logger.info(
                    f"[zhilian] using intercepted API data: {len(intercepted_data)} records"
                )
                raw_list = [self._parse_api_item(item) for item in intercepted_data]
            else:
                logger.info("[zhilian] falling back to DOM extraction")
                raw_list = self._extract_from_dom(pg)

            # ----------------------------------------------------------
            # Close page
            # ----------------------------------------------------------
            try:
                pg.close()
            except Exception:
                pass

            logger.info(
                f"[zhilian] keyword='{keyword}' city='{city}' page={page} → {len(raw_list)} records"
            )
            return raw_list

        except Exception as exc:
            logger.error(f"[zhilian] search failed: {exc}", exc_info=True)
            try:
                pg.close()
            except Exception:
                pass
            return []

    # ------------------------------------------------------------------
    # API data parsing
    # ------------------------------------------------------------------

    def _parse_api_item(self, item: dict) -> dict:
        """Parse a single job item from Zhilian's API response into a raw dict.

        Zhilian API fields observed:
          - number            : job ID
          - jobTitle / name   : title
          - company / companyName : company name
          - city / workCity   : city display string
          - salary60 / salary : salary string (e.g. "15K-25K")
          - jobDescription    : description text
          - education         : education requirement
          - workingExp        : experience requirement
          - positionURL       : detail page URL
          - industry / industryName : industry
          - skillTags         : skills list
        """
        return {
            "title": item.get("jobTitle") or item.get("name") or item.get("jobName", ""),
            "company": (
                item.get("company", {})
                if isinstance(item.get("company"), str)
                else (item.get("company") or {}).get("name", "")
                if isinstance(item.get("company"), dict)
                else item.get("companyName") or item.get("company", "")
            ),
            "city": item.get("city") or item.get("workCity", {}).get("name", "") if isinstance(item.get("workCity"), dict) else item.get("workCity", ""),
            "salary_min": None,
            "salary_max": None,
            "salary_text": item.get("salary60") or item.get("salary") or "",
            "description": item.get("jobDescription") or item.get("description") or "",
            "education": item.get("education") or item.get("reqEducation", ""),
            "experience": item.get("workingExp") or item.get("reqExperience", ""),
            "industry": item.get("industry") or item.get("industryName", ""),
            "skills": item.get("skillTags") or [],
            "source_job_id": str(
                item.get("number") or item.get("jobId") or item.get("id", "")
            ),
            "source_url": item.get("positionURL") or item.get("detailUrl") or "",
            "source_platform": self.platform,
        }

    # ------------------------------------------------------------------
    # DOM extraction (fallback)
    # ------------------------------------------------------------------

    def _extract_from_dom(self, page) -> List[dict]:
        """Scrape job listings from the rendered page DOM.

        Selectors attempt to match Zhilian's current listing structure.
        These may need updates when the site changes its markup.
        """
        results: List[dict] = []

        # Try multiple known selectors for job cards
        card_selectors = [
            ".joblist-box__item",
            ".joblist-box__item--list",
            ".joblist__item",
            ".contentpile__content",
            ".positionlist .job-box",
            "div[class*='joblist'] > div[class*='item']",
        ]

        cards = []
        for sel in card_selectors:
            cards = page.query_selector_all(sel)
            if cards:
                logger.debug(f"[zhilian] found {len(cards)} cards with selector '{sel}'")
                break

        if not cards:
            # Last-ditch: look for any element that looks like a job card
            logger.warning("[zhilian] no known selectors matched, trying generic search")
            cards = page.query_selector_all("div[class*='job']")

        for card in cards:
            try:
                item = self._parse_dom_card(card)
                if item and item.get("title"):
                    results.append(item)
            except Exception as exc:
                logger.debug(f"[zhilian] DOM card parse error: {exc}")

        return results

    def _parse_dom_card(self, card) -> Optional[dict]:
        """Extract fields from a single DOM card element."""

        def _text(selector: str, default: str = "") -> str:
            el = card.query_selector(selector)
            return el.inner_text().strip() if el else default

        def _attr(selector: str, attr_name: str, default: str = "") -> str:
            el = card.query_selector(selector)
            return el.get_attribute(attr_name) or default if el else default

        title = (
            _text("[class*='jobTitle']")
            or _text("[class*='job-title']")
            or _text("a[class*='title']")
            or _text(".jobname")
            or _attr("[class*='jobTitle'] a", "title")
        )

        company = (
            _text("[class*='company']")
            or _text("[class*='companyName']")
            or _text(".cname")
        )

        salary_text = (
            _text("[class*='salary']")
            or _text("[class*='salar']")
            or _text(".saray")
        )

        city = (
            _text("[class*='city']")
            or _text("[class*='workCity']")
            or _text("[class*='area']")
        )

        experience = _text("[class*='exp']") or _text("[class*='experience']")
        education = _text("[class*='edu']") or _text("[class*='degree']")

        link = None
        link_el = card.query_selector("a[href*='/job_detail/'], a[href*='jobs.zhaopin.com']")
        if link_el:
            link = link_el.get_attribute("href")

        job_id = ""
        if link:
            m = re.search(r"/job_detail/(\d+)\.html|jobs\.zhaopin\.com/(?:CC)?(\d+)", link)
            if m:
                job_id = m.group(1) or m.group(2) or ""

        description = (
            _text("[class*='desc']")
            or _text("[class*='detail']")
            or _text("[class*='info']")
        )

        return {
            "title": title,
            "company": company,
            "city": city,
            "salary_min": None,
            "salary_max": None,
            "salary_text": salary_text,
            "description": description,
            "education": education,
            "experience": experience,
            "industry": "",
            "skills": [],
            "source_job_id": job_id,
            "source_url": link or "",
            "source_platform": self.platform,
        }

    # ------------------------------------------------------------------
    # normalize() — map Zhilian fields to unified schema
    # ------------------------------------------------------------------

    def normalize(self, raw: dict) -> dict:
        """Convert a raw Zhilian job dict into the unified schema.

        Handles salary parsing from Zhilian's salary-text format
        (e.g. "15K-25K", "8千-1.2万", "15K-25K·14薪", "面议").
        """
        salary_text = raw.get("salary_text", "")
        salary_min, salary_max = self._parse_salary(salary_text)

        return {
            "source_platform": self.platform,
            "source_job_id": str(raw.get("source_job_id", "")),
            "source_url": raw.get("source_url", ""),
            "title": raw.get("title", ""),
            "company": raw.get("company", ""),
            "city": raw.get("city", ""),
            "salary_min": raw.get("salary_min") if raw.get("salary_min") is not None else salary_min,
            "salary_max": raw.get("salary_max") if raw.get("salary_max") is not None else salary_max,
            "description": raw.get("description", ""),
            "education": raw.get("education", ""),
            "experience": raw.get("experience", ""),
            "industry": raw.get("industry", ""),
            "skills": raw.get("skills", []) if isinstance(raw.get("skills"), list) else [],
        }

    # ------------------------------------------------------------------
    # Salary parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_salary(salary_text: str) -> tuple:
        """Parse Zhilian salary string into (min_k, max_k) monthly in thousands.

        Handles formats:
          - "15K-25K"         → (15, 25)
          - "8千-1.2万"       → (8, 12)
          - "15K-25K·14薪"    → (15, 25)  (base monthly, ignore 薪 multiplier)
          - "15000-25000"     → (15, 25)  (raw numbers, treat as monthly)
          - "面议" / "薪资面议" → (None, None)
          - "10K以上"         → (10, None)
          - "3万-5万"         → (30, 50)
        """
        if not salary_text:
            return None, None

        text = salary_text.strip()

        # Negotiable / undisclosed
        if any(kw in text for kw in ["面议", "面談", "薪资", "保密"]):
            return None, None

        # Remove "·14薪", "·13薪" etc.
        text = re.sub(r"·\d+薪", "", text)
        # Remove commas
        text = text.replace(",", "")

        # Extract all numbers
        nums = re.findall(r"[\d.]+", text)
        if not nums:
            return None, None

        lo = float(nums[0])
        hi = float(nums[1]) if len(nums) >= 2 else lo

        # Unit detection
        # "万" = 10,000; "千"/"K"/"k" = 1,000; raw numbers < 100 probably in K
        if "万" in text:
            lo *= 10
            hi *= 10
        elif "千" in text or "K" in text.upper():
            pass  # Already in thousands
        elif lo < 100:
            # Raw numbers like "15-25" or "15000-25000"
            pass  # Already in K (15K) or raw monthly (15000)

        # Convert to monthly K if raw numbers are in raw yuan (>= 1000)
        if lo >= 1000:
            lo = lo / 1000
            hi = hi / 1000

        salary_min = round(lo, 1) if lo > 0 else None
        salary_max = round(hi, 1) if hi > 0 else None

        # Sanity check: if values are unreasonable, return None
        if salary_min is not None and salary_min > 200:
            logger.warning(f"[zhilian] unusual salary_min={salary_min} from '{salary_text}', capping")
            return None, None

        return salary_min, salary_max

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def close(self):
        """Shut down the browser and Playwright."""
        try:
            if self._browser:
                self._browser.close()
                self._browser = None
        except Exception:
            pass
        try:
            if self._pw:
                self._pw.stop()
                self._pw = None
        except Exception:
            pass

    def __del__(self):
        self.close()


# ---------------------------------------------------------------------------
# __main__ test block
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    collector = ZhilianCollector()

    try:
        # Quick smoke test: search for Python jobs in Beijing
        print("\n=== Testing ZhilianCollector ===\n")

        results = collector.search(keyword="Python开发", city="北京", page=1)
        print(f"\nRaw results count: {len(results)}")

        if results:
            print("\n--- First 3 raw items ---")
            for item in results[:3]:
                print(json.dumps(item, ensure_ascii=False, indent=2))

            print("\n--- Normalized ---")
            for raw in results[:3]:
                norm = collector.normalize(raw)
                print(json.dumps(norm, ensure_ascii=False, indent=2))
        else:
            print("No results found. Possible causes:")
            print("  1. Anti-bot detection blocked the request")
            print("  2. Network issue or site structure changed")
            print("  3. The selectors need updating")

            # Try a second attempt with different keyword
            print("\n--- Retrying with different keyword ---")
            results2 = collector.search(keyword="Java", city="上海", page=1)
            print(f"Second attempt: {len(results2)} results")

            if results2:
                for raw in results2[:2]:
                    norm = collector.normalize(raw)
                    print(json.dumps(norm, ensure_ascii=False, indent=2))

        # Test collect() with pagination
        print("\n--- Testing collect() with max_pages=2 ---")
        cr = collector.collect(keyword="数据分析", city="深圳", max_pages=2)
        print(f"CollectResult: {len(cr.records)} records, {cr.pages_crawled} pages, {cr.duration_seconds}s")
        if cr.errors:
            print(f"Errors: {cr.errors}")

    finally:
        collector.close()
