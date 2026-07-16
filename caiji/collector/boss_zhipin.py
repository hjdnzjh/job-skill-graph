"""BOSS直聘 collector using Playwright browser automation.

BOSS直聘 is an SPA that requires JS rendering. Attempts to call the internal
``/wapi/zpgeek/search/joblist.json`` API directly return error code 37
(environment anomaly). This module uses Playwright to:
1. Visit the search page URL with a realistic browser context
2. Wait for job cards to render in the DOM
3. Extract structured data from rendered elements
4. Gracefully handle anti-bot roadblocks
"""

import logging
import re
import time
from typing import Optional

from collector.base import BaseCollector

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# City code lookup (BOSS直聘 internal codes)
# ---------------------------------------------------------------------------
CITY_CODES = {
    "北京": "101010100",
    "上海": "101020100",
    "深圳": "101280600",
    "广州": "101280100",
    "杭州": "101210100",
    "成都": "101270100",
    "南京": "101190100",
    "武汉": "101200100",
    "西安": "101110100",
    "苏州": "101190400",
    "重庆": "101040100",
    "长沙": "101250100",
    "天津": "101030100",
    "合肥": "101220100",
    "郑州": "101180100",
    "济南": "101120100",
    "青岛": "101120200",
    "厦门": "101230200",
    "福州": "101230100",
    "大连": "101070200",
    "沈阳": "101070100",
    "昆明": "101290100",
    "贵阳": "101260100",
    "东莞": "101281600",
    "佛山": "101280800",
    "宁波": "101210400",
    "无锡": "101190200",
    "珠海": "101280700",
}

# ---------------------------------------------------------------------------
# Job-card DOM selectors (tried in order of preference / confidence)
# ---------------------------------------------------------------------------
CARD_SELECTORS = [
    ".search-job-result li",
    ".job-card-box",
    ".job-card-body",
    ".job-primary",
]

TITLE_SELECTORS = [
    ".job-name",
    ".job-title",
    '[class*="job-name"]',
    'a[ka="search-job-title"]',
]

SALARY_SELECTORS = [
    ".salary",
    ".red",
    '[class*="salary"]',
]

COMPANY_SELECTORS = [
    ".company-name a",
    ".company-text a",
    '[class*="company-name"]',
    '[ka="search-company"]',
]

LOCATION_SELECTORS = [
    ".job-area",
    '[class*="area"]',
]

TAG_SELECTORS = [
    ".job-limit span",
    ".tag-item",
    ".job-limit-wrapper span",
]

SKILL_SELECTORS = [
    ".tag-item",
    ".job-tag",
    "[class*='tag']",
]

DESC_SELECTORS = [
    ".job-info",
    ".info-desc",
    '[class*="info-desc"]',
    ".job-desc",
]

LINK_SELECTOR = 'a[href*="job_detail"]'


class BossZhipinCollector(BaseCollector):
    """Collect job listings from BOSS直聘 (zhipin.com).

    Uses Playwright sync API with a headless Chromium browser.
    A single browser instance is shared across all ``search()`` calls
    within the collector's lifetime; pages are created and destroyed
    per call.
    """

    platform = "boss_zhipin"

    SEARCH_URL = "https://www.zhipin.com/web/geek/job"

    def __init__(self):
        self._playwright = None
        self._browser = None

    # ------------------------------------------------------------------
    # Browser lifecycle
    # ------------------------------------------------------------------

    def _ensure_browser(self):
        """Lazily start Playwright and launch a Chromium browser."""
        if self._browser is not None:
            return

        from playwright.sync_api import sync_playwright

        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )

    def _new_page(self):
        """Create a fresh browser context + page with realistic fingerprint."""
        self._ensure_browser()

        context = self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
            locale="zh-CN",
        )
        # Mask automation signals
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        """)
        return context.new_page()

    def close(self):
        """Tear down the browser and Playwright driver."""
        try:
            if self._browser:
                self._browser.close()
                self._browser = None
        except Exception:
            pass
        try:
            if self._playwright:
                self._playwright.stop()
                self._playwright = None
        except Exception:
            pass

    def __del__(self):
        self.close()

    # ------------------------------------------------------------------
    # BaseCollector interface
    # ------------------------------------------------------------------

    def search(self, keyword: str, city: str = "", page: int = 1) -> list[dict]:
        """Fetch one page of job cards from BOSS直聘.

        Args:
            keyword: Search keyword (e.g. ``"Java"``, ``"Python开发"``).
            city: City name matching a key in ``CITY_CODES``.
            page: 1-based page number.

        Returns:
            List of raw job dicts.  Returns an empty list on failure or
            when anti-bot measures block the request.
        """
        city_code = CITY_CODES.get(city, "101280600")  # default: 深圳
        url = f"{self.SEARCH_URL}?query={keyword}&city={city_code}&page={page}"

        page_obj = self._new_page()
        results: list[dict] = []

        try:
            # 1. Navigate — wait for full page load (React SPA hydration)
            page_obj.goto(url, wait_until="load", timeout=30000)
            page_obj.wait_for_load_state("networkidle")

            # 2. Wait for job cards to appear in the rendered DOM
            self._wait_for_cards(page_obj)

            # 3. Check for anti-bot / verification roadblock
            page_text = page_obj.content()
            if self._is_blocked(page_text):
                logger.warning(
                    "[%s] Anti-bot page detected for keyword=%r city=%r page=%d",
                    self.platform, keyword, city, page,
                )
                return []

            # 4. Let remaining JS finish and scroll to trigger lazy images
            time.sleep(1)
            for _ in range(3):
                page_obj.evaluate("window.scrollBy(0, 800)")
                time.sleep(0.3)

            # 5. Locate job cards
            cards = self._find_cards(page_obj)
            logger.debug(
                "[%s] keyword=%r city=%r page=%d → %d card elements",
                self.platform, keyword, city, page, len(cards),
            )

            # 6. Extract data from each card
            for card in cards:
                try:
                    item = self._parse_card(card, keyword, city)
                    if item and item.get("title"):
                        results.append(item)
                except Exception as exc:
                    logger.debug("[%s] Parse card failed: %s", self.platform, exc)

        except Exception as exc:
            logger.warning(
                "[%s] search failed for keyword=%r city=%r page=%d: %s",
                self.platform, keyword, city, page, exc,
            )
        finally:
            try:
                page_obj.close()
            except Exception:
                pass

        return results

    # ------------------------------------------------------------------
    # DOM helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _wait_for_cards(page_obj, timeout: int = 15000):
        """Block until at least one known card selector matches."""
        deadline = time.time() + timeout / 1000.0
        for selector in CARD_SELECTORS:
            remaining = max(0, (deadline - time.time()) * 1000)
            if remaining <= 0:
                break
            try:
                page_obj.wait_for_selector(selector, timeout=min(remaining, 5000))
                # Got at least one element — done
                return
            except Exception:
                continue
        # Best-effort: just sleep a bit more for JS rendering
        time.sleep(2)

    @staticmethod
    def _is_blocked(html: str) -> bool:
        """Heuristic to detect anti-bot / verification page."""
        indicators = ["环境异常", "验证", "请完成以下验证", "滑块验证", "请拖动滑块"]
        return any(ind in html for ind in indicators)

    @staticmethod
    def _find_cards(page_obj) -> list:
        """Try each card selector and return the first non-empty result."""
        for selector in CARD_SELECTORS:
            cards = page_obj.query_selector_all(selector)
            if cards:
                return cards
        return []

    # ------------------------------------------------------------------
    # Card parser
    # ------------------------------------------------------------------

    def _parse_card(self, card, keyword: str, city: str) -> Optional[dict]:
        """Extract structured fields from a single job-card DOM element."""
        # --- Title ---
        title = self._text_from_selectors(card, TITLE_SELECTORS)

        # --- URL & job ID ---
        link = ""
        job_id = ""
        link_el = card.query_selector(LINK_SELECTOR)
        if link_el:
            href = link_el.get_attribute("href") or ""
            link = href if href.startswith("http") else f"https://www.zhipin.com{href}" if href else ""
            m = re.search(r"job_detail/([a-zA-Z0-9]+)", link)
            if m:
                job_id = m.group(1)

        # Alternate ID extraction: some cards embed the ID in a data attribute
        if not job_id:
            data_id = card.get_attribute("data-jobid") or card.get_attribute("data-id")
            if data_id:
                job_id = data_id

        # --- Salary ---
        salary = self._text_from_selectors(card, SALARY_SELECTORS)

        # --- Company ---
        company = self._text_from_selectors(card, COMPANY_SELECTORS)

        # --- Location ---
        location = self._text_from_selectors(card, LOCATION_SELECTORS) or city

        # --- Experience & Education (inferred from tag list) ---
        experience, education = self._parse_tags(card)

        # --- Description ---
        description = self._text_from_selectors(card, DESC_SELECTORS)

        # --- Skills / tags ---
        skills = self._parse_skills(card)

        # --- Parse salary range ---
        salary_min, salary_max = self._parse_salary(salary)

        return {
            "title": title,
            "company": company,
            "city": location or city,
            "salary": salary,
            "salary_min": salary_min,
            "salary_max": salary_max,
            "description": description,
            "education": education,
            "experience": experience,
            "source_job_id": job_id,
            "source_url": link,
            "skills": skills,
        }

    @staticmethod
    def _text_from_selectors(card, selectors: list[str]) -> str:
        """Return ``inner_text()`` of the first matching selector, or ``""``."""
        for sel in selectors:
            el = card.query_selector(sel)
            if el:
                text = el.inner_text()
                if text:
                    return text.strip()
        return ""

    @staticmethod
    def _parse_tags(card) -> tuple[str, str]:
        """Extract experience and education from tag-like elements.

        BOSS直聘 typically renders tags like "3-5年", "本科" inside
        ``.job-limit span`` or ``.tag-item`` elements.
        """
        experience = ""
        education = ""

        for selector in TAG_SELECTORS:
            els = card.query_selector_all(selector)
            for el in els:
                text = el.inner_text().strip()
                if not text:
                    continue
                if not experience and any(kw in text for kw in ("经验", "年", "应届", "在校")):
                    experience = text
                if not education and any(kw in text for kw in ("学历", "本科", "大专", "硕士", "博士", "高中", "中专")):
                    education = text
            if experience and education:
                break

        return experience, education

    @staticmethod
    def _parse_skills(card) -> list[str]:
        """Collect skill/tag labels from tag-like elements."""
        skills = []
        for selector in SKILL_SELECTORS:
            els = card.query_selector_all(selector)
            for el in els:
                text = el.inner_text().strip()
                if text and text not in skills:
                    skills.append(text)
        return skills

    # ------------------------------------------------------------------
    # Salary parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_salary(salary_text: str) -> tuple:
        """Parse BOSS直聘 salary formats into (min, max) in K/month.

        Supported formats::

            "15K-25K"
            "15-25K·16薪"
            "15K-25K·16薪"
            "8千-12千"
            "1.5万-2.5万"
            "面议"  → (None, None)
        """
        if not salary_text or "面议" in salary_text:
            return None, None

        text = salary_text.strip()

        # Strip trailing salary-month notes (e.g. "·16薪", "·13薪")
        text = re.sub(r"·.*$", "", text)
        text = text.replace(",", "").replace("，", "")

        nums = re.findall(r"[\d.]+", text)
        if not nums:
            return None, None

        if len(nums) >= 2:
            lo, hi = float(nums[0]), float(nums[1])
        elif len(nums) == 1:
            lo = hi = float(nums[0])
        else:
            return None, None

        # Unit detection
        if "万" in text:
            lo *= 10
            hi *= 10
        elif "千" in text or "/日" in text or "/天" in text:
            # Daily rate — keep as-is (unusual for BOSS but safe)
            pass
        elif "/时" in text or "/小时" in text:
            pass
        # else: values like "15-25" without unit → assume K

        return round(lo, 1), round(hi, 1)

    # ------------------------------------------------------------------
    # Normalize to unified schema
    # ------------------------------------------------------------------

    def normalize(self, raw: dict) -> dict:
        """Map BOSS直聘 raw fields to the unified job schema.

        Salary is parsed from the raw ``"salary"`` string if ``salary_min`` /
        ``salary_max`` are not already set.
        """
        salary_min = raw.get("salary_min")
        salary_max = raw.get("salary_max")

        # Parse salary from text if not already numeric
        if salary_min is None and raw.get("salary"):
            salary_min, salary_max = self._parse_salary(raw.get("salary", ""))

        skills = raw.get("skills", [])
        if isinstance(skills, str):
            skills = [s.strip() for s in skills.split(",") if s.strip()]
        if not isinstance(skills, list):
            skills = []

        return {
            "source_platform": self.platform,
            "source_job_id": str(raw.get("source_job_id", "")),
            "source_url": raw.get("source_url", ""),
            "title": raw.get("title", ""),
            "company": raw.get("company", ""),
            "city": raw.get("city", ""),
            "salary_min": salary_min,
            "salary_max": salary_max,
            "description": raw.get("description", ""),
            "education": raw.get("education", ""),
            "experience": raw.get("experience", ""),
            "industry": raw.get("industry", ""),
            "skills": skills,
        }


# ---------------------------------------------------------------------------
# Quick smoke-test (run with: python -m collector.boss_zhipin)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    collector = BossZhipinCollector()
    try:
        keyword = "Java"
        city = "深圳"

        # --- Single page test ---
        print(f"\n[BossZhipin] Searching '{keyword}' in '{city}' page 1 ...")
        raw_results = collector.search(keyword, city, page=1)
        print(f"[BossZhipin] Got {len(raw_results)} raw results\n")
        for i, r in enumerate(raw_results[:3], 1):
            print(
                f"  {i}. {r.get('title')} | {r.get('company')} | "
                f"{r.get('salary')} | {r.get('city')}"
            )

        # --- Paginated + normalized test ---
        print(f"\n[BossZhipin] collect('{keyword}', '{city}', max_pages=2) ...")
        result = collector.collect(keyword, city, max_pages=2)
        print(
            f"[BossZhipin] {len(result.records)} records, "
            f"{result.pages_crawled} pages, "
            f"{result.duration_seconds:.1f}s"
        )
        if result.errors:
            print(f"[BossZhipin] Errors: {result.errors}")
        if result.records:
            r = result.records[0]
            print(f"  Sample: {r['title']} @ {r['company']} "
                  f"| {r['salary_min']}K-{r['salary_max']}K | {r['city']}")
    finally:
        collector.close()
