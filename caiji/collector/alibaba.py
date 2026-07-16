"""Alibaba recruitment collector — Playwright-based, with auth-stub fallback.

TODO / KNOWN LIMITATION:
  The Alibaba talent platform (https://talent.alibaba.com/) is a React SPA
  that gates its search API behind token-based authentication.  Direct POST
  to ``/position/search`` returns HTTP 403 Forbidden without a valid session
  cookie + CSRF token pair.

  The page source includes a ``__token__`` value (e.g.
  ``"461f89e1-484a-4892-a141-d1afdd691206"``), but this token is scoped to
  a server-side session and cannot be used independently — the API also
  expects an authenticated ``Cookie`` header set during login/OAuth flow.

  Playwright can render the SPA, but the job list page redirects to the
  login wall when no authenticated session exists.  Until a reliable login
  flow (credential-based or cookie-injection) is implemented, search()
  returns an empty list as a safe stub.

  To activate this collector:
    1. Manually log in to talent.alibaba.com in a headed browser.
    2. Export cookies (e.g. via browser devtools or a Playwright script).
    3. Inject the saved ``storage_state`` JSON into ``search()`` via the
       Playwright ``context`` parameter.
    4. Remove the early-return at the top of ``search()``.

Strategy:
  - PRIMARY path: Playwright (sync API, headless) navigates to
    ``/off-campus/position-list?keyWord={keyword}``, waits for React to
    hydrate the DOM, and scrapes job cards.
  - SECONDARY path: intercept XHR responses to ``/position/search`` if
    authentication is available.
  - FALLBACK: return ``[]`` with a logged warning (current behaviour).
"""

from __future__ import annotations

import json
import logging
import sys
import time
from typing import Any, Dict, List, Optional

from collector.base import BaseCollector, CollectResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Playwright imports — optional; collector works as a stub without them
# ---------------------------------------------------------------------------
try:
    from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page
    _HAS_PLAYWRIGHT = True
except ImportError:  # pragma: no cover
    _HAS_PLAYWRIGHT = False
    Browser = None  # type: ignore
    BrowserContext = None  # type: ignore
    Page = None  # type: ignore
    logger.warning("playwright not installed — AlibabaCollector will operate in stub mode")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
BASE_URL = "https://talent.alibaba.com"
SEARCH_PATH = "/off-campus/position-list"
API_SEARCH_URL = f"{BASE_URL}/position/search"

# DOM selectors (subject to change as Alibaba updates their front-end)
# These are best-effort; the SPA uses React with obfuscated class names.
SELECTOR_JOB_CARD = "[class*='position-item'], [class*='jobItem'], [class*='list--item']"
SELECTOR_TITLE = "[class*='title'], [class*='name'], [class*='positionName']"
SELECTOR_DEPT = "[class*='department'], [class*='depart'], [class*='bg']"
SELECTOR_LOCATION = "[class*='location'], [class*='city'], [class*='workPlace']"
SELECTOR_DESC = "[class*='description'], [class*='desc'], [class*='require']"

TIMEOUT_MS = 30_000
WAIT_AFTER_NAV_MS = 5_000

# Alibaba field name mappings (for normalize())
_FIELD_MAP = {
    "id": "source_job_id",
    "name": "title",
    "departmentName": "department",
    "departName": "department",
    "workPlace": "city",
    "location": "city",
    "cityName": "city",
    "description": "description",
    "requirement": "description",
    "jobDescription": "description",
    "degree": "education",
    "education": "education",
    "workExperience": "experience",
    "experience": "experience",
    "firstCategory": "industry",
}

# ---------------------------------------------------------------------------
# Collector
# ---------------------------------------------------------------------------


class AlibabaCollector(BaseCollector):
    """Collect job listings from Alibaba's campus / social recruitment portal."""

    platform = "alibaba"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_search_url(keyword: str, city: str = "") -> str:
        """Build the front-end search page URL."""
        import urllib.parse

        params: Dict[str, str] = {}
        if keyword:
            params["keyWord"] = keyword
        if city:
            params["city"] = city

        base = f"{BASE_URL}{SEARCH_PATH}"
        if params:
            qs = urllib.parse.urlencode(params)
            return f"{base}?{qs}"
        return base

    def _extract_from_dom(self, page: Page) -> List[Dict[str, Any]]:
        """Scrape job cards from the rendered DOM.

        This is a heuristic extractor — Alibaba's class names are
        auto-generated by a CSS-modules / styled-components build step
        and may change without notice.  We use attribute-contains
        selectors to stay resilient.
        """
        cards = page.query_selector_all(SELECTOR_JOB_CARD)
        if not cards:
            logger.debug("No job cards matched selector %r", SELECTOR_JOB_CARD)
            return []

        results: List[Dict[str, Any]] = []
        for card in cards:
            try:
                title_el = card.query_selector(SELECTOR_TITLE)
                dept_el = card.query_selector(SELECTOR_DEPT)
                loc_el = card.query_selector(SELECTOR_LOCATION)
                desc_el = card.query_selector(SELECTOR_DESC)

                raw: Dict[str, Any] = {
                    "title": (title_el.inner_text().strip() if title_el else ""),
                    "department": (dept_el.inner_text().strip() if dept_el else ""),
                    "city": (loc_el.inner_text().strip() if loc_el else ""),
                    "description": (desc_el.inner_text().strip() if desc_el else ""),
                    "source_job_id": card.get_attribute("data-id") or "",
                    "source_url": "",
                    "company": "阿里巴巴",
                    "salary_min": None,
                    "salary_max": None,
                    "education": "",
                    "experience": "",
                    "industry": "",
                    "skills": [],
                }

                # Try to extract a detail link
                link = card.query_selector("a")
                if link:
                    href = link.get_attribute("href") or ""
                    if href.startswith("/"):
                        href = f"{BASE_URL}{href}"
                    raw["source_url"] = href

                results.append(raw)
            except Exception:
                logger.debug("Failed to parse a job card", exc_info=True)

        return results

    def _extract_from_api(
        self, json_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Parse the JSON response from ``/position/search``.

        Expected shape (best-effort, may differ from actual API)::

            {
              "success": true,
              "content": {
                "data": [
                  {
                    "id": 123,
                    "name": "Java开发工程师",
                    "departmentName": "CTO线",
                    "workPlace": "杭州",
                    "description": "...",
                    "degree": "本科",
                    "workExperience": "3年以上",
                    ...
                  }
                ]
              }
            }
        """
        data = json_data.get("content", json_data)
        items = data.get("data", []) if isinstance(data, dict) else []
        if not isinstance(items, list):
            return []

        results: List[Dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            record: Dict[str, Any] = {}
            for src, dst in _FIELD_MAP.items():
                if src in item:
                    record[dst] = item[src]
            # Ensure all required fields exist
            record.setdefault("source_job_id", str(item.get("id", "")))
            record.setdefault("source_url", "")
            record.setdefault("title", item.get("name", ""))
            record.setdefault("company", "阿里巴巴")
            record.setdefault("city", "")
            record.setdefault("salary_min", None)
            record.setdefault("salary_max", None)
            record.setdefault("description", "")
            record.setdefault("education", "")
            record.setdefault("experience", "")
            record.setdefault("industry", "")
            record.setdefault("skills", [])
            # Build detail URL when id is present
            if record.get("source_job_id"):
                record["source_url"] = (
                    f"{BASE_URL}/off-campus/position-detail?"
                    f"positionId={record['source_job_id']}"
                )
            results.append(record)

        return results

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def search(
        self, keyword: str, city: str = "", page: int = 1
    ) -> List[Dict[str, Any]]:
        """Search Alibaba jobs.

        Implementation notes
        --------------------
        1. If Playwright is not installed, logs a warning and returns ``[]``.
        2. Launches a headless Chromium browser, navigates to the search
           page, and attempts DOM extraction + XHR interception.
        3. If the page redirects to the login wall (most likely), returns
           ``[]`` with a logged warning — the collector is effectively a
           stub until authentication is wired up.
        """
        # ------------------------------------------------------------------
        # STUB GUARD — remove this block once authentication is configured
        # ------------------------------------------------------------------
        # msg = (
        #     "AlibabaCollector.search() is in stub mode because the Alibaba "
        #     "talent platform requires authentication.  See the module-level "
        #     "TODO in alibaba.py for setup instructions."
        # )
        # logger.warning(msg)
        # return []
        # ------------------------------------------------------------------

        if not _HAS_PLAYWRIGHT:
            logger.warning(
                "playwright not installed — AlibabaCollector returning empty result"
            )
            return []

        target_url = self._build_search_url(keyword, city)
        logger.info("Navigating to %s (page=%s)", target_url, page)

        results: List[Dict[str, Any]] = []
        xhr_bodies: List[Dict[str, Any]] = []

        with sync_playwright() as pw:
            browser: Browser = pw.chromium.launch(headless=True)
            context: BrowserContext = browser.new_context(
                # If you have a saved auth state, load it here:
                # storage_state="alibaba_auth.json",
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                ),
            )
            page_obj: Page = context.new_page()

            # Intercept XHR calls to the position-search API.
            def _capture_response(response):
                if API_SEARCH_URL in response.url and response.status == 200:
                    try:
                        body = response.json()
                        xhr_bodies.append(body)
                    except Exception:
                        logger.debug("Failed to parse XHR response JSON", exc_info=True)

            page_obj.on("response", _capture_response)

            try:
                page_obj.goto(target_url, wait_until="load", timeout=TIMEOUT_MS)
                page_obj.wait_for_load_state("networkidle")

                # Wait for React to render job list (or the login wall).
                try:
                    page_obj.wait_for_selector(
                        SELECTOR_JOB_CARD, timeout=WAIT_AFTER_NAV_MS
                    )
                except Exception:
                    # Could also be the login page — check URL.
                    current = page_obj.url
                    if "login" in current.lower():
                        logger.warning(
                            "Redirected to login page (%s) — Alibaba requires "
                            "authentication.  Returning empty result.",
                            current,
                        )
                        browser.close()
                        return []
                    logger.info(
                        "Job card selector not found within %d ms; "
                        "trying XHR capture fallback.",
                        WAIT_AFTER_NAV_MS,
                    )

                # Let outstanding XHRs settle.
                page_obj.wait_for_timeout(2_000)

                # 1) Prefer API-captured data.
                if xhr_bodies:
                    for body in xhr_bodies:
                        parsed = self._extract_from_api(body)
                        results.extend(parsed)
                    logger.info(
                        "Captured %d job(s) from %d XHR response(s)",
                        len(results),
                        len(xhr_bodies),
                    )

                # 2) Fall back to DOM scraping if API capture yielded nothing.
                if not results:
                    dom_results = self._extract_from_dom(page_obj)
                    results.extend(dom_results)
                    if dom_results:
                        logger.info("Extracted %d job(s) from DOM", len(dom_results))

            except Exception as exc:
                logger.error("Playwright navigation/parsing error: %s", exc)
            finally:
                browser.close()

        return results

    # ------------------------------------------------------------------
    # Normalize
    # ------------------------------------------------------------------

    def normalize(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Map Alibaba-specific fields to the unified schema.

        Alibaba raw fields
        ------------------
        - ``name`` / ``title``        → ``title``
        - ``departmentName``          → (mapped to ``industry`` for grouping)
        - ``workPlace`` / ``cityName``→ ``city``
        - ``description``             → ``description``
        - ``degree``                  → ``education``
        - ``workExperience``          → ``experience``
        - ``id``                      → ``source_job_id``
        """
        record = super().normalize(raw)

        # Ensure company is always set (raw may not include it).
        if not record.get("company"):
            record["company"] = "阿里巴巴"

        # Override source_platform.
        record["source_platform"] = "alibaba"

        # Coerce source_job_id to string.
        sid = raw.get("id") or raw.get("source_job_id") or ""
        record["source_job_id"] = str(sid)

        # Build source_url if missing.
        if not record.get("source_url") and sid:
            record["source_url"] = (
                f"{BASE_URL}/off-campus/position-detail?positionId={sid}"
            )

        # city: Alibaba sometimes stores it as a JSON array string.
        city = record.get("city", "")
        if city.startswith("[") and city.endswith("]"):
            try:
                parsed = json.loads(city)
                if isinstance(parsed, list) and parsed:
                    city = str(parsed[0])
            except (json.JSONDecodeError, TypeError):
                pass
        record["city"] = city

        # education / degree normalisation.
        raw_edu = raw.get("degree") or raw.get("education") or ""
        if raw_edu and not record.get("education"):
            record["education"] = raw_edu

        # experience normalisation.
        raw_exp = raw.get("workExperience") or raw.get("experience") or ""
        if raw_exp and not record.get("experience"):
            record["experience"] = raw_exp

        return record


# ---------------------------------------------------------------------------
# Smoke test (run with: python -m collector.alibaba)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    collector = AlibabaCollector()
    keywords = ["Java", "前端", "数据"]

    for kw in keywords:
        print(f"\n{'=' * 60}")
        print(f"Searching: keyword={kw!r}")
        print("=" * 60)

        result: CollectResult = collector.collect(keyword=kw, max_pages=1)

        print(f"  Platform    : {result.platform}")
        print(f"  Records     : {len(result.records)}")
        print(f"  Pages       : {result.pages_crawled}")
        print(f"  Duration    : {result.duration_seconds}s")
        print(f"  Errors      : {len(result.errors)}")

        if result.errors:
            for err in result.errors:
                print(f"    [ERROR] {err}")

        if result.records:
            for i, rec in enumerate(result.records[:3], 1):
                print(f"  --- Record {i} ---")
                print(f"    Title       : {rec.get('title')}")
                print(f"    Company     : {rec.get('company')}")
                print(f"    City        : {rec.get('city')}")
                print(f"    Education   : {rec.get('education')}")
                print(f"    Experience  : {rec.get('experience')}")
                print(f"    Source URL  : {rec.get('source_url')}")
                desc = rec.get("description", "")
                print(f"    Description : {desc[:120]}{'...' if len(desc) > 120 else ''}")
        else:
            print("  (no results — see module-level TODO for auth setup)")

        # Small delay between keywords.
        time.sleep(2.0)

    print(f"\n{'=' * 60}")
    print("Done.")
