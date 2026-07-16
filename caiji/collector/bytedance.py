"""Bytedance (字节跳动) careers collector — Playwright browser-based.

The Bytedance careers page (https://jobs.bytedance.com/) is a React SPA.
Direct API calls to /api/v1/search return the SPA shell HTML, not JSON.
Strategy:
  1. Navigate to the search URL with query params.
  2. Intercept XHR/fetch responses that the SPA makes internally.
  3. Fall back to DOM parsing if interception yields nothing.
"""

import json
import logging
import re
import time
from typing import Any, Dict, List, Optional

from collector.base import BaseCollector

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_URL = "https://jobs.bytedance.com"
SEARCH_PATH = "/experienced/search"
DETAIL_PATH = "/experienced/position/"

# Known internal API patterns the SPA might call
API_PATTERNS = [
    "/api/v1/search",
    "/api/v1/position/search",
    "/api/v2/position/search",
    "/api/v2/search/position",
    "/api/v1/job/list",
    "/api/v1/recruit/position/list",
    "/api/gateway/position",
]

# Selectors to try when waiting for the React app to render
CONTENT_SELECTORS = [
    ".position-list .position-item",
    ".job-card",
    ".search-result-item",
    '[class*="position-item"]',
    '[class*="job-item"]',
    '[class*="SearchResult"]',
    '[class*="position"] a[href*="/position/"]',
    "a[href*='/experienced/position/']",
]

# Fallback: generic container that indicates the page has rendered
PAGE_READY_SELECTORS = [
    ".position-list",
    '[class*="search-result"]',
    '[class*="list-container"]',
    "main",  # last resort
]


class BytedanceCollector(BaseCollector):
    """Collect job listings from Bytedance (字节跳动) careers site via Playwright."""

    platform = "bytedance"

    def __init__(self, headless: bool = True, timeout: int = 30000):
        self._headless = headless
        self._timeout = timeout
        self._pw = None
        self._browser = None

    # ------------------------------------------------------------------
    # Browser lifecycle
    # ------------------------------------------------------------------

    def _ensure_browser(self):
        """Lazily start Playwright and launch a Chromium browser."""
        if self._browser is not None:
            return
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(
            headless=self._headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        logger.info("BytedanceCollector: browser launched (headless=%s)", self._headless)

    def _new_page(self):
        """Create a new browser context + page with a realistic UA and locale."""
        self._ensure_browser()
        context = self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
            locale="zh-CN",
        )
        # Hide webdriver flag
        context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )
        return context.new_page()

    def _close(self):
        """Tear down the browser and playwright."""
        try:
            if self._browser:
                self._browser.close()
        except Exception:
            pass
        try:
            if self._pw:
                self._pw.stop()
        except Exception:
            pass
        self._browser = None
        self._pw = None

    # ------------------------------------------------------------------
    # Core: search()
    # ------------------------------------------------------------------

    def search(self, keyword: str, city: str = "", page: int = 1) -> list[dict]:
        """Fetch a single page of job listings from Bytedance careers.

        Strategy:
          1. Build the search URL with query params.
          2. Register a response interceptor to capture JSON from internal APIs.
          3. Navigate and wait for the React app to render.
          4. If interception yielded data, parse it; otherwise fall back to DOM.
        """
        keyword = (keyword or "").strip()
        city = (city or "").strip()

        # ------------------------------------------------------------------
        # Build search URL
        # ------------------------------------------------------------------
        params = []
        if keyword:
            params.append(f"keyword={self._urlencode(keyword)}")
        if city:
            params.append(f"city={self._urlencode(city)}")
        params.append(f"page={page}")
        params.append("size=20")

        query_string = "&".join(params)
        url = f"{BASE_URL}{SEARCH_PATH}?{query_string}"

        logger.info(
            "[bytedance] search: keyword=%r city=%r page=%s → %s",
            keyword, city, page, url,
        )

        # ------------------------------------------------------------------
        # Response interceptor: capture JSON API responses
        # ------------------------------------------------------------------
        intercepted: List[dict] = []

        def _on_response(response):
            try:
                resp_url = response.url
                # Check if this looks like an internal API call
                is_api = any(p in resp_url for p in API_PATTERNS)
                if not is_api:
                    return
                if response.status != 200:
                    return
                content_type = response.headers.get("content-type", "")
                if "json" not in content_type:
                    return
                body = response.json()
                if body:
                    intercepted.append({"url": resp_url, "body": body})
                    logger.debug(
                        "[bytedance] intercepted API: %s (%s bytes)",
                        resp_url, len(str(body)),
                    )
            except Exception:
                pass  # ignore individual response parse errors

        # ------------------------------------------------------------------
        # Page navigation
        # ------------------------------------------------------------------
        page_obj = self._new_page()
        try:
            page_obj.on("response", _on_response)

            page_obj.goto(url, wait_until="load", timeout=self._timeout)
            page_obj.wait_for_load_state("networkidle")
            logger.debug("[bytedance] initial load complete, url=%s", page_obj.url)

            # Wait for the React app to render — try several selectors
            rendered = False
            for selector in CONTENT_SELECTORS:
                try:
                    page_obj.wait_for_selector(selector, timeout=8000)
                    rendered = True
                    logger.debug("[bytedance] content found via selector: %s", selector)
                    break
                except Exception:
                    continue

            if not rendered:
                # Fallback: wait for any page structure
                for selector in PAGE_READY_SELECTORS:
                    try:
                        page_obj.wait_for_selector(selector, timeout=5000)
                        rendered = True
                        break
                    except Exception:
                        continue

            # Extra settle time for async rendering
            time.sleep(2)

            # Scroll to trigger lazy-loaded content
            for _ in range(3):
                page_obj.evaluate("window.scrollBy(0, 800)")
                time.sleep(0.5)

            # ------------------------------------------------------------------
            # Parse intercepted data (preferred)
            # ------------------------------------------------------------------
            if intercepted:
                records = self._parse_intercepted(intercepted)
                if records:
                    logger.info(
                        "[bytedance] parsed %d records from %d intercepted API responses",
                        len(records), len(intercepted),
                    )
                    return records

            # ------------------------------------------------------------------
            # Fallback: DOM scraping
            # ------------------------------------------------------------------
            logger.debug("[bytedance] falling back to DOM scraping")
            records = self._parse_dom(page_obj)
            logger.info("[bytedance] parsed %d records from DOM", len(records))
            return records

        except Exception as exc:
            logger.error("[bytedance] search failed: %s", exc)
            return []
        finally:
            try:
                page_obj.close()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Intercepted JSON parsing
    # ------------------------------------------------------------------

    def _parse_intercepted(self, intercepted: List[dict]) -> List[dict]:
        """Walk intercepted API response bodies looking for job position data."""
        records: List[dict] = []

        for entry in intercepted:
            body = entry["body"]

            # The API response could have many shapes — try common ones
            candidates: List[dict] = []

            if isinstance(body, dict):
                # Common envelope keys
                for key in (
                    "data", "result", "results", "items", "list",
                    "positions", "jobList", "positionList", "records",
                ):
                    if key in body and isinstance(body[key], list):
                        candidates.extend(body[key])
                # Sometimes the response IS the list under "data.list" etc.
                data = body.get("data", {})
                if isinstance(data, dict):
                    for key in ("list", "items", "positions", "records", "results"):
                        if key in data and isinstance(data[key], list):
                            candidates.extend(data[key])

            elif isinstance(body, list):
                candidates.extend(body)

            for item in candidates:
                if not isinstance(item, dict):
                    continue
                rec = self._parse_api_item(item)
                if rec and rec.get("title"):
                    records.append(rec)

        return records

    def _parse_api_item(self, item: dict) -> Optional[dict]:
        """Map a single API-returned position dict to our raw schema."""
        try:
            # Title — try many possible field names
            title = (
                item.get("title")
                or item.get("name")
                or item.get("positionName")
                or item.get("jobName")
                or item.get("jobTitle")
                or ""
            )

            if not title:
                return None

            source_id = str(
                item.get("id")
                or item.get("positionId")
                or item.get("jobId")
                or item.get("requisitionId")
                or ""
            )

            # Build detail URL
            source_url = ""
            if source_id:
                source_url = f"{BASE_URL}{DETAIL_PATH}{source_id}"
            else:
                source_url = item.get("url") or item.get("detailUrl") or ""

            # Company
            company = (
                item.get("company")
                or item.get("companyName")
                or item.get("departmentName")
                or "字节跳动"
            )

            # Location / city
            location = (
                item.get("city")
                or item.get("location")
                or item.get("workCity")
                or item.get("cityName")
                or ""
            )
            if isinstance(location, list):
                location = ", ".join(str(l) for l in location if l)

            # Salary
            salary_min, salary_max = self._extract_salary(item)

            # Description
            description = (
                item.get("description")
                or item.get("jobDescription")
                or item.get("jobDetail")
                or item.get("responsibility")
                or item.get("requirement")
                or ""
            )
            # If description is split into parts, join them
            if isinstance(description, list):
                description = "\n".join(str(d) for d in description if d)

            # Education & experience
            education = (
                item.get("education")
                or item.get("degree")
                or item.get("educationLevel")
                or item.get("minimumDegree")
                or ""
            )
            experience = (
                item.get("experience")
                or item.get("workExperience")
                or item.get("workingYears")
                or item.get("seniority")
                or ""
            )

            return {
                "title": self._clean_text(title),
                "company": self._clean_text(company),
                "city": self._clean_text(location),
                "salary_min": salary_min,
                "salary_max": salary_max,
                "description": self._clean_text(description),
                "education": self._clean_text(education),
                "experience": self._clean_text(experience),
                "source_job_id": source_id,
                "source_url": source_url,
            }
        except Exception:
            return None

    @staticmethod
    def _extract_salary(item: dict) -> tuple:
        """Try to extract salary_min / salary_max from the item dict."""
        salary = (
            item.get("salary")
            or item.get("salaryRange")
            or item.get("salaryDesc")
            or ""
        )
        lo = item.get("salaryMin") or item.get("salary_min")
        hi = item.get("salaryMax") or item.get("salary_max")

        if lo is not None and hi is not None:
            try:
                return float(lo), float(hi)
            except (TypeError, ValueError):
                pass

        if isinstance(salary, str) and salary:
            return _parse_salary_text(salary)
        if isinstance(salary, dict):
            lo = salary.get("min") or salary.get("salaryMin")
            hi = salary.get("max") or salary.get("salaryMax")
            try:
                return (float(lo) if lo else None, float(hi) if hi else None)
            except (TypeError, ValueError):
                pass

        return None, None

    # ------------------------------------------------------------------
    # DOM fallback parsing
    # ------------------------------------------------------------------

    def _parse_dom(self, page_obj) -> List[dict]:
        """Scrape job cards from the rendered DOM."""
        records: List[dict] = []

        # Try multiple possible card selectors
        card_elements = []
        for sel in CONTENT_SELECTORS:
            try:
                cards = page_obj.query_selector_all(sel)
                if cards:
                    card_elements = cards
                    logger.debug("[bytedance] DOM: found %d cards via %r", len(cards), sel)
                    break
            except Exception:
                continue

        if not card_elements:
            # Broad sweep: find all links that look like position detail links
            try:
                card_elements = page_obj.query_selector_all(
                    "a[href*='/experienced/position/']"
                )
                if card_elements:
                    logger.debug(
                        "[bytedance] DOM: found %d position links as fallback",
                        len(card_elements),
                    )
            except Exception:
                pass

        for el in card_elements:
            try:
                rec = self._parse_dom_card(el, page_obj)
                if rec and rec.get("title"):
                    records.append(rec)
            except Exception as exc:
                logger.debug("[bytedance] DOM card parse error: %s", exc)

        return records

    def _parse_dom_card(self, el, page_obj) -> Optional[dict]:
        """Parse a single DOM element (job card or link) into a raw dict."""
        # ---- Title ----
        title = ""
        for attr in ["title", "aria-label", "data-title"]:
            t = el.get_attribute(attr)
            if t:
                title = t
                break
        if not title:
            title = el.inner_text().split("\n")[0] if el.inner_text() else ""

        # ---- URL and ID ----
        href = el.get_attribute("href") or ""
        if not href and el.tag_name().lower() == "a":
            href = el.get_attribute("href") or ""
        # el might not be the <a> itself — look for a child link
        if not href:
            link_el = el.query_selector("a[href]")
            if link_el:
                href = link_el.get_attribute("href") or ""
        source_url = href if href.startswith("http") else f"{BASE_URL}{href}" if href else ""

        source_id = ""
        id_m = re.search(r"/position/(\d+)", source_url) if source_url else None
        if id_m:
            source_id = id_m.group(1)

        # ---- Company / Department ----
        company = "字节跳动"
        for cls_pat in ["company", "department", "org", "team"]:
            try:
                comp_el = el.query_selector(f'[class*="{cls_pat}"]')
                if comp_el:
                    txt = comp_el.inner_text().strip()
                    if txt and len(txt) < 80:
                        company = txt
                        break
            except Exception:
                continue

        # ---- Location / City ----
        city = ""
        for cls_pat in ["city", "location", "addr", "place"]:
            try:
                loc_el = el.query_selector(f'[class*="{cls_pat}"]')
                if loc_el:
                    city = loc_el.inner_text().strip()
                    break
            except Exception:
                continue

        # ---- Description ----
        description = ""
        for cls_pat in ["desc", "detail", "summary", "intro", "requirement"]:
            try:
                desc_el = el.query_selector(f'[class*="{cls_pat}"]')
                if desc_el:
                    description = desc_el.inner_text().strip()
                    break
            except Exception:
                continue

        # ---- Salary ----
        salary_min, salary_max = None, None
        for cls_pat in ["salary", "pay", "compensation", "wage"]:
            try:
                sal_el = el.query_selector(f'[class*="{cls_pat}"]')
                if sal_el:
                    sal_text = sal_el.inner_text().strip()
                    salary_min, salary_max = _parse_salary_text(sal_text)
                    break
            except Exception:
                continue

        # ---- Tags (education / experience) ----
        education, experience = "", ""
        try:
            tag_els = el.query_selector_all('[class*="tag"], [class*="label"], [class*="badge"]')
            tags = [t.inner_text().strip() for t in tag_els if t.inner_text().strip()]
            for tag in tags:
                if any(kw in tag for kw in ["本科", "硕士", "博士", "学历", "大专", "不限"]):
                    education = tag
                if any(kw in tag for kw in ["年", "经验", "应届", "实习"]):
                    experience = tag
        except Exception:
            pass

        if not title:
            return None

        return {
            "title": self._clean_text(title),
            "company": self._clean_text(company),
            "city": self._clean_text(city),
            "salary_min": salary_min,
            "salary_max": salary_max,
            "description": self._clean_text(description),
            "education": self._clean_text(education),
            "experience": self._clean_text(experience),
            "source_job_id": source_id,
            "source_url": source_url,
        }

    # ------------------------------------------------------------------
    # normalize()
    # ------------------------------------------------------------------

    def normalize(self, raw: dict) -> dict:
        """Map Bytedance-specific fields to the unified schema."""
        return {
            "source_platform": self.platform,
            "source_job_id": str(raw.get("source_job_id", "")),
            "source_url": raw.get("source_url", ""),
            "title": raw.get("title", ""),
            "company": raw.get("company", "字节跳动"),
            "city": raw.get("city", ""),
            "salary_min": raw.get("salary_min"),
            "salary_max": raw.get("salary_max"),
            "description": raw.get("description", ""),
            "education": raw.get("education", ""),
            "experience": raw.get("experience", ""),
            "industry": raw.get("industry", "互联网/IT"),
            "skills": raw.get("skills", []) if isinstance(raw.get("skills"), list) else [],
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _clean_text(text: str) -> str:
        if not text:
            return ""
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _urlencode(s: str) -> str:
        """Minimal URL-encoding for Chinese-safe query strings."""
        from urllib.parse import quote

        return quote(s, safe="")

    def __del__(self):
        self._close()


# ---------------------------------------------------------------------------
# Salary text parser (module-level, shared)
# ---------------------------------------------------------------------------

def _parse_salary_text(salary_text: str) -> tuple:
    """Parse a salary string like '20k-40k', '15-25K', '20-35万/年' into (min, max).

    Returns (None, None) on failure.
    """
    if not salary_text:
        return None, None

    text = salary_text.replace("·", "").replace(",", "").strip()
    nums = re.findall(r"[\d.]+", text)
    if len(nums) < 1:
        return None, None

    lo = float(nums[0])
    hi = float(nums[1]) if len(nums) >= 2 else lo

    # Monthly salary: "20k-40k" style, values usually 1-100
    if any(unit in text.lower() for unit in ("k", "千")):
        pass  # already in K
    elif "万" in text:
        lo *= 10
        hi *= 10
    elif lo < 50:
        # Heuristic: small numbers are probably in K/month
        lo *= 1000
        hi *= 1000

    return round(lo, 1), round(hi, 1)


# ---------------------------------------------------------------------------
# __main__ test block
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    keyword = sys.argv[1] if len(sys.argv) > 1 else "后端开发"
    city = sys.argv[2] if len(sys.argv) > 2 else ""
    pages = int(sys.argv[3]) if len(sys.argv) > 3 else 1

    collector = BytedanceCollector(headless=True)
    try:
        result = collector.collect(keyword=keyword, city=city, max_pages=pages)
        print(f"\n{'=' * 60}")
        print(f"Platform: {result.platform}")
        print(f"Keyword:  {result.keyword}")
        print(f"City:     {result.city or '(all)'}")
        print(f"Pages:    {result.pages_crawled}")
        print(f"Records:  {len(result.records)}")
        print(f"Duration: {result.duration_seconds}s")
        print(f"Errors:   {len(result.errors)}")
        if result.errors:
            for e in result.errors:
                print(f"  - {e}")
        print(f"{'=' * 60}")

        # Print first 3 records as samples
        for i, rec in enumerate(result.records[:3], 1):
            print(f"\n--- Record {i} ---")
            print(f"  Title:       {rec.get('title', '')}")
            print(f"  Company:     {rec.get('company', '')}")
            print(f"  City:        {rec.get('city', '')}")
            print(f"  Salary:      {rec.get('salary_min')} - {rec.get('salary_max')}")
            print(f"  Education:   {rec.get('education', '')}")
            print(f"  Experience:  {rec.get('experience', '')}")
            print(f"  URL:         {rec.get('source_url', '')}")
            desc = rec.get("description", "")
            if desc:
                print(f"  Description: {desc[:120]}...")
    finally:
        collector._close()
