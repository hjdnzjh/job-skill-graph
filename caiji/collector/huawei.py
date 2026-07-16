"""
Huawei careers recruitment collector.

TODO (2026-07-16):
    Huawei careers portal (https://career.huawei.com/) has redesigned its URL
    structure. All previously documented API endpoints return 404:

        - /reccampportal/api/job/search                              → 404
        - /reccampportal/portal5/search.html                          → 404
        - /reccampportal/services/rs/position/searchPositionList      → "No service was found"

    This collector is currently NON-FUNCTIONAL for live collection.
    To restore it, someone needs to:

        1. Visit https://career.huawei.com/ in a browser with DevTools open.
        2. Perform a job search and capture the XHR/Fetch requests on the
           Network tab.
        3. Identify the new search API endpoint, request method (GET/POST),
           headers, and query/body parameter names.
        4. Update the search() method below with the correct endpoint,
           request format, and response parsing logic.
        5. Adjust normalize() if the response field names have changed.
"""

import logging

from collector.base import BaseCollector

logger = logging.getLogger(__name__)


class HuaweiCollector(BaseCollector):
    """Collector for Huawei careers via the public recruitment API.

    Currently disabled — the career portal API endpoints have changed and
    have not yet been reverse-engineered.  search() returns an empty list.
    """

    platform = "huawei"

    def search(self, keyword: str, city: str = "", page: int = 1) -> list[dict]:
        """Fetch a single page of job listings.

        Returns an empty list because the Huawei careers API endpoints are
        currently unknown (see module-level TODO).
        """
        logger.warning(
            "[huawei] search() called but API endpoints are unknown — "
            "Huawei careers portal has been redesigned.  "
            "See module docstring for details."
        )
        return []

    def normalize(self, raw: dict) -> dict:
        """Map Huawei-specific response fields to the unified schema.

        This is written for the *previous* API response shape and may need
        to be updated once the new endpoints are reverse-engineered.
        The field names below are best-effort guesses based on the old API.
        """
        return {
            "source_platform": raw.get("source_platform", self.platform),
            "source_job_id": str(raw.get("positionId", raw.get("source_job_id", ""))),
            "source_url": raw.get(
                "source_url",
                raw.get("positionDetailUrl", raw.get("applyUrl", "")),
            ),
            "title": raw.get("positionName", raw.get("title", "")),
            "company": raw.get("company", "华为"),
            "city": raw.get("cityName", raw.get("workCity", raw.get("city", ""))),
            "salary_min": raw.get("salaryMin", raw.get("salary_min")),
            "salary_max": raw.get("salaryMax", raw.get("salary_max")),
            "description": raw.get(
                "positionDesc",
                raw.get("description", raw.get("jobDesc", "")),
            ),
            "education": raw.get(
                "degreeName",
                raw.get("education", raw.get("educationName", "")),
            ),
            "experience": raw.get(
                "workExperience",
                raw.get("experience", raw.get("experienceName", "")),
            ),
            "industry": raw.get("industry", ""),
            "skills": raw.get("skillList", raw.get("skills", [])),
            # Preserve any extra Huawei-specific fields for debugging
            "_raw": {
                k: v
                for k, v in raw.items()
                if k not in {
                    "positionId", "source_job_id", "source_url",
                    "positionDetailUrl", "applyUrl",
                    "positionName", "title",
                    "cityName", "workCity", "city",
                    "salaryMin", "salary_max", "salaryMax",
                    "positionDesc", "description", "jobDesc",
                    "degreeName", "education", "educationName",
                    "workExperience", "experience", "experienceName",
                    "skillList", "skills",
                    "source_platform", "company", "industry",
                }
            },
        }


# ---------------------------------------------------------------------------
# Quick self-check
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("HuaweiCollector status: DISABLED")
    print(
        "Reason: Huawei careers portal has redesigned its URL structure; "
        "all known API endpoints return 404."
    )
    print()
    print("Action required:")
    print("  1. Visit https://career.huawei.com/ with DevTools open")
    print("  2. Perform a job search and capture XHR/Fetch requests")
    print("  3. Identify the new search API endpoint and parameters")
    print("  4. Update search() and normalize() in this module")
    print()
    collector = HuaweiCollector()
    result = collector.search(keyword="Java", city="深圳")
    assert result == [], f"Expected empty list, got {result}"
    print("search() returns empty list as expected — OK")
