"""Tencent careers collector — requests-based API client.

Target API: careers.tencent.com/tencentcareer/api/post/Query
No browser/Playwright needed — pure HTTP requests.
"""

import logging
import re

import requests

from collector.base import BaseCollector

logger = logging.getLogger(__name__)

# Skill keywords for extraction from Responsibility text
# Same pattern as recruitment.py._extract_skills
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


class TencentCollector(BaseCollector):
    """Collect job listings from Tencent careers (careers.tencent.com)."""

    platform = "tencent"

    API_URL = "https://careers.tencent.com/tencentcareer/api/post/Query"

    def search(self, keyword: str, city: str = "", page: int = 1) -> list[dict]:
        """Fetch a single page of jobs from the Tencent careers API.

        Args:
            keyword: Search keyword (e.g. "Java", "数据工程")
            city: Optional city name to filter results (post-processing)
            page: Page index (1-based)

        Returns:
            List of normalized job dicts matching the unified schema.
            Returns empty list on any error.
        """
        params = {
            "keyword": keyword,
            "pageIndex": page,
            "pageSize": 20,
        }

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json",
        }

        try:
            resp = requests.get(self.API_URL, params=params, headers=headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            if data.get("Code") != 200:
                logger.warning(
                    "[tencent] API returned Code=%s: %s",
                    data.get("Code"), data.get("Message", ""),
                )
                return []

            posts = data.get("Data", {}).get("Posts", [])
            if not posts:
                return []

            # Return raw API dicts — BaseCollector.collect() calls normalize()
            return list(posts)

        except requests.RequestException as e:
            logger.error("[tencent] Request failed: %s", e)
            return []
        except (ValueError, KeyError, TypeError) as e:
            logger.error("[tencent] JSON parse / data error: %s", e)
            return []

    def normalize(self, raw: dict) -> dict:
        """Map a Tencent API Post dict to the unified job schema.

        Field mapping:
            PostId            → source_job_id
            PostURL           → source_url
            RecruitPostName   → title
            ComName or "腾讯"  → company
            LocationName      → city
            Responsibility    → description
            RequireWorkYearsName → experience
            CategoryName      → industry
            (none)            → salary_min / salary_max / education
        """
        responsibility = raw.get("Responsibility", "")

        return {
            "source_platform": raw.get("source_platform", self.platform),
            "source_job_id": str(raw.get("PostId", "")),
            "source_url": raw.get("PostURL", ""),
            "title": raw.get("RecruitPostName", ""),
            "company": raw.get("ComName") or raw.get("company") or "腾讯",
            "city": raw.get("LocationName", ""),
            "salary_min": raw.get("salary_min"),
            "salary_max": raw.get("salary_max"),
            "description": responsibility,
            "education": raw.get("education", ""),
            "experience": raw.get("RequireWorkYearsName", ""),
            "industry": raw.get("CategoryName", ""),
            "skills": self._extract_skills(responsibility),
        }

    # ------------------------------------------------------------------
    # Skill extraction (same keyword set as recruitment.py)
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_skills(text: str) -> list[str]:
        """Extract technology keywords from job description text using regex."""
        if not text:
            return []
        found = []
        for kw in SKILL_KEYWORDS:
            if re.search(kw, text, re.IGNORECASE):
                found.append(kw.replace("\\", ""))
        return found


# ------------------------------------------------------------------
# Direct test / smoke-test entry point
# ------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    c = TencentCollector()
    result = c.collect("Java", "深圳", max_pages=1)
    print(f"Got {len(result.records)} records in {result.duration_seconds}s")
    if result.records:
        print(result.records[0])
    if result.errors:
        print(f"Errors: {result.errors}")
