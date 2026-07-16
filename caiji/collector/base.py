"""Base collector class with unified schema for all recruitment platforms."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import hashlib
import time
import logging

logger = logging.getLogger(__name__)


@dataclass
class CollectResult:
    """Result of a single collection run."""
    platform: str
    keyword: str
    city: str
    records: list   # list of normalized dicts
    pages_crawled: int
    duration_seconds: float
    errors: list = field(default_factory=list)


class BaseCollector(ABC):
    """Abstract base class for all platform collectors.

    Each subclass must implement search() and may override normalize().
    The collect() method provides pagination, error handling, and polite delay.
    """

    platform: str = "unknown"

    @abstractmethod
    def search(self, keyword: str, city: str = "", page: int = 1) -> list[dict]:
        """Fetch a single page of raw job listings from the platform.

        Each returned dict MUST contain at minimum:
            title, company, city, salary_min, salary_max,
            description, education, experience, source_job_id, source_url

        Returns:
            list of raw job dicts (one page worth)
        """

    def normalize(self, raw: dict) -> dict:
        """Map platform-specific fields to the unified schema.

        Subclasses should override this to handle platform-specific field names.
        The default implementation passes through.

        Unified schema fields:
            source_platform, source_job_id, source_url,
            title, company, city, salary_min, salary_max,
            description, education, experience, industry, skills[]
        """
        return {
            "source_platform": raw.get("source_platform", self.platform),
            "source_job_id": str(raw.get("source_job_id", "")),
            "source_url": raw.get("source_url", ""),
            "title": raw.get("title", ""),
            "company": raw.get("company", ""),
            "city": raw.get("city", ""),
            "salary_min": raw.get("salary_min"),
            "salary_max": raw.get("salary_max"),
            "description": raw.get("description", ""),
            "education": raw.get("education", ""),
            "experience": raw.get("experience", ""),
            "industry": raw.get("industry", ""),
            "skills": raw.get("skills", []) if isinstance(raw.get("skills"), list) else [],
        }

    def collect(self, keyword: str, city: str = "", max_pages: int = 3) -> CollectResult:
        """Main collection entry point: paginate, collect, normalize.

        Args:
            keyword: Search keyword (e.g. "Java", "Python开发")
            city: Target city name
            max_pages: Maximum number of search result pages to crawl

        Returns:
            CollectResult with all records, timing, and errors
        """
        records = []
        errors = []
        start = time.time()
        pages_actually_crawled = 0

        for page in range(1, max_pages + 1):
            try:
                logger.info(f"[{self.platform}] searching keyword='{keyword}' city='{city}' page={page}")
                batch = self.search(keyword, city, page)
                if not batch:
                    logger.info(f"[{self.platform}] no results on page={page}, stopping")
                    break
                normalized = [self.normalize(r) for r in batch]
                records.extend(normalized)
                pages_actually_crawled = page
                logger.info(f"[{self.platform}] page={page} → {len(batch)} records")
                time.sleep(1.5)  # polite delay between pages
            except Exception as e:
                err_msg = f"page={page}: {e}"
                errors.append(err_msg)
                logger.error(f"[{self.platform}] {err_msg}")
                # If the first page fails, stop; otherwise continue
                if page == 1:
                    break

        duration = round(time.time() - start, 2)
        logger.info(
            f"[{self.platform}] finished: {len(records)} records, "
            f"{pages_actually_crawled} pages, {duration}s, {len(errors)} errors"
        )
        return CollectResult(
            platform=self.platform,
            keyword=keyword,
            city=city,
            records=records,
            pages_crawled=pages_actually_crawled,
            duration_seconds=duration,
            errors=errors,
        )
