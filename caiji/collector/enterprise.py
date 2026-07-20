"""Enterprise profile collector — builds company portraits from existing job data.

This collector does NOT call external APIs. It reads the existing ``job_records``
MySQL table, aggregates data per company, and produces enterprise technology
profile records (source_type = enterprise).

Each enterprise profile includes:
  - Technology stack (aggregated from skills_required across all jobs)
  - Main recruitment directions (aggregated from job titles)
  - Salary levels (min, max, avg)
  - City distribution

Usage:
    collector = EnterpriseCollector()
    result = collector.collect(max_pages=5)   # 50 companies per page
    # result.records contains normalized enterprise profile records
"""

import logging
import os
import time
from collections import Counter
from datetime import datetime
from typing import Optional

from collector.base import BaseCollector, CollectResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

COMPANIES_PER_PAGE = 50  # Number of companies to process per collect-page

# Skill keywords for categorization (same set as recruitment pipelines)
TECH_CATEGORIES = {
    "后端开发": ["Java", "Spring", "Go", "C++", "Python", "Django", "Flask",
                 "FastAPI", "Rust", "C#", ".NET", "Node.js", "PHP", "Laravel"],
    "前端开发": ["React", "Vue", "Angular", "TypeScript", "JavaScript",
                 "HTML", "CSS", "Webpack", "Vite", "小程序"],
    "移动开发": ["Android", "iOS", "Swift", "Kotlin", "Flutter", "React Native"],
    "数据工程": ["Spark", "Flink", "Hadoop", "Kafka", "ETL", "SQL",
                 "Hive", "HBase", "数据仓库", "数据湖", "数据管道"],
    "AI/机器学习": ["TensorFlow", "PyTorch", "Keras", "Scikit-learn",
                   "Transformer", "NLP", "CV", "深度学习", "机器学习",
                   "LLM", "大模型", "RAG", "Agent"],
    "云计算/DevOps": ["Docker", "Kubernetes", "K8s", "AWS", "Azure",
                      "GCP", "CI/CD", "Jenkins", "Terraform", "DevOps",
                      "Nginx", "Linux", "Prometheus", "Grafana"],
    "数据库": ["MySQL", "PostgreSQL", "MongoDB", "Redis", "Elasticsearch",
               "TiDB", "ClickHouse", "Neo4j"],
    "安全": ["安全", "渗透", "加密", "防火墙", "WAF", "零信任"],
    "区块链": ["区块链", "Web3", "Solidity", "智能合约"],
    "嵌入式/IoT": ["嵌入式", "单片机", "RTOS", "ARM", "FPGA", "物联网"],
}

# Keywords that indicate seniority from job titles
SENIORITY_KEYWORDS = {
    "高级": "senior",
    "资深": "senior",
    "专家": "expert",
    "架构师": "architect",
    "负责人": "lead",
    "主管": "lead",
    "经理": "manager",
    "总监": "director",
    "实习": "intern",
    "初级": "junior",
    "应届": "entry",
}


# ---------------------------------------------------------------------------
# EnterpriseCollector
# ---------------------------------------------------------------------------

class EnterpriseCollector(BaseCollector):
    """Build enterprise technology profiles from existing job records.

    Reads from ``job_records`` table, aggregates per company, and outputs
    company portrait records suitable for storage as source_type=enterprise.
    """

    platform = "enterprise_profile"

    def __init__(self, settings=None):
        """Initialize with optional Settings object for DB connection.

        Args:
            settings: A config.settings.Settings instance. If None, created on demand.
        """
        self._settings = settings
        self._db_checked = False

    def _get_settings(self):
        """Lazy-load settings."""
        if self._settings is None:
            from config.settings import Settings
            self._settings = Settings()
        return self._settings

    def _get_connection(self):
        """Create a pymysql connection using current settings."""
        import pymysql
        settings = self._get_settings()
        return pymysql.connect(
            host=settings.mysql_host,
            port=settings.mysql_port,
            user=settings.mysql_user,
            password=settings.mysql_password,
            database=settings.mysql_database,
            charset="utf8mb4",
            connect_timeout=10,
        )

    def _ensure_db_available(self):
        """Check that MySQL is reachable and job_records table exists."""
        if self._db_checked:
            return True
        try:
            conn = self._get_connection()
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM job_records")
                count = cur.fetchone()[0]
                logger.info("[enterprise] job_records table has %d rows", count)
            conn.close()
            self._db_checked = True
            return True
        except Exception as e:
            logger.warning("[enterprise] Database check failed: %s", e)
            return False

    # ------------------------------------------------------------------
    # search() — one batch of companies
    # ------------------------------------------------------------------

    def search(self, keyword: str = "", city: str = "", page: int = 1) -> list[dict]:
        """Fetch one batch of enterprise profiles from aggregated job data.

        Args:
            keyword: Optional company name filter (partial match)
            city: Optional city filter
            page: 1-based page index (COMPANIES_PER_PAGE companies per page)

        Returns:
            List of raw enterprise profile dicts
        """
        if not self._ensure_db_available():
            return []

        offset = (page - 1) * COMPANIES_PER_PAGE
        records = []

        try:
            conn = self._get_connection()
            try:
                # ------------------------------------------------------------------
                # Step 1: Get distinct companies with aggregate stats
                # ------------------------------------------------------------------
                company_list = self._query_company_list(conn, keyword, city, offset)
                if not company_list:
                    return []

                company_names = [c["company_name"] for c in company_list]

                # ------------------------------------------------------------------
                # Step 2: Get all skills for these companies
                # ------------------------------------------------------------------
                company_skills = self._query_company_skills(conn, company_names)

                # ------------------------------------------------------------------
                # Step 3: Build profiles
                # ------------------------------------------------------------------
                for comp in company_list:
                    name = comp["company_name"]
                    skills_data = company_skills.get(name, [])
                    profile = self._build_company_profile(comp, skills_data)
                    records.append(profile)

            finally:
                conn.close()

            logger.info(
                "[enterprise] page=%d → %d companies processed",
                page, len(records),
            )

        except Exception as e:
            logger.error("[enterprise] page %d query failed: %s", page, e)
            if page == 1:
                raise

        return records

    # ------------------------------------------------------------------
    # Database queries
    # ------------------------------------------------------------------

    def _query_company_list(self, conn, keyword: str, city: str, offset: int) -> list[dict]:
        """Query distinct companies with aggregate stats, ordered by job count.

        Returns list of dicts with keys: company_name, job_count, avg_salary_min,
        avg_salary_max, max_salary, min_salary, industries, locations, titles.
        """
        sql = """
            SELECT
                company_name,
                COUNT(*) AS job_count,
                ROUND(AVG(salary_min), 0) AS avg_salary_min,
                ROUND(AVG(salary_max), 0) AS avg_salary_max,
                MAX(salary_max) AS max_salary,
                MIN(salary_min) AS min_salary
            FROM job_records
            WHERE company_name IS NOT NULL AND company_name != ''
        """
        params = []

        if keyword and keyword.strip():
            sql += " AND company_name LIKE %s"
            params.append(f"%{keyword.strip()}%")

        if city and city.strip():
            sql += " AND location LIKE %s"
            params.append(f"%{city.strip()}%")

        sql += """
            GROUP BY company_name
            ORDER BY job_count DESC, company_name ASC
            LIMIT %s OFFSET %s
        """
        params.extend([COMPANIES_PER_PAGE, offset])

        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

        # Get detailed breakdown (locations, industries, titles) for these companies
        company_names = [row[0] for row in rows]

        # Query detailed aggregation
        detail_sql = """
            SELECT
                company_name,
                GROUP_CONCAT(DISTINCT location ORDER BY location SEPARATOR '||') AS locations,
                GROUP_CONCAT(DISTINCT industry ORDER BY industry SEPARATOR '||') AS industries,
                GROUP_CONCAT(DISTINCT job_title ORDER BY job_title SEPARATOR '||') AS titles
            FROM job_records
            WHERE company_name IN ({})
            GROUP BY company_name
        """.format(",".join(["%s"] * len(company_names))) if company_names else ""

        details = {}
        if company_names and detail_sql:
            with conn.cursor() as cur:
                cur.execute(detail_sql, company_names)
                for row in cur.fetchall():
                    details[row[0]] = {
                        "locations": row[1] or "",
                        "industries": row[2] or "",
                        "titles": row[3] or "",
                    }

        result = []
        for row in rows:
            name = row[0]
            d = details.get(name, {})
            result.append({
                "company_name": name,
                "job_count": row[1],
                "avg_salary_min": float(row[2]) if row[2] is not None else None,
                "avg_salary_max": float(row[3]) if row[3] is not None else None,
                "max_salary": float(row[4]) if row[4] is not None else None,
                "min_salary": float(row[5]) if row[5] is not None else None,
                "locations": d.get("locations", ""),
                "industries": d.get("industries", ""),
                "titles": d.get("titles", ""),
            })

        return result

    def _query_company_skills(self, conn, company_names: list[str]) -> dict[str, list[str]]:
        """Query skills_required for a set of companies.

        Returns dict: company_name → list of all skills across their jobs.
        """
        if not company_names:
            return {}

        placeholders = ",".join(["%s"] * len(company_names))
        sql = f"""
            SELECT company_name, skills_required
            FROM job_records
            WHERE company_name IN ({placeholders})
              AND skills_required IS NOT NULL
        """

        result: dict[str, list[str]] = {name: [] for name in company_names}

        with conn.cursor() as cur:
            cur.execute(sql, company_names)
            for row in cur.fetchall():
                name = row[0]
                skills_json = row[1]
                if skills_json is None:
                    continue
                # skills_required is a JSON column — MySQL connector may return it as
                # a str (JSON string) or already parsed as list, depending on setup.
                skills = self._parse_skills_json(skills_json)
                result[name].extend(skills)

        return result

    @staticmethod
    def _parse_skills_json(skills_json) -> list[str]:
        """Parse skills_required JSON value — handles both string and list."""
        if skills_json is None:
            return []
        if isinstance(skills_json, list):
            return [str(s) for s in skills_json if s]
        if isinstance(skills_json, str):
            import json
            try:
                parsed = json.loads(skills_json)
                if isinstance(parsed, list):
                    return [str(s) for s in parsed if s]
                return []
            except (json.JSONDecodeError, TypeError):
                return []
        return []

    # ------------------------------------------------------------------
    # Profile builder
    # ------------------------------------------------------------------

    def _build_company_profile(self, comp: dict, skills: list[str]) -> dict:
        """Aggregate company data into a single enterprise profile dict.

        Args:
            comp: Company aggregate data from _query_company_list
            skills: All skills across this company's jobs

        Returns:
            Raw dict for normalize()
        """
        name = comp["company_name"]

        # --- Skill aggregation ---
        skill_counter = Counter(skills)
        top_skills = [s for s, _ in skill_counter.most_common(20)]

        # --- Technology categories ---
        all_skills_lower = [s.lower() for s in skills]
        tech_categories = []
        for cat, keywords in TECH_CATEGORIES.items():
            if any(kw.lower() in all_skills_lower for kw in keywords):
                tech_categories.append(cat)

        # --- Main recruitment directions from titles ---
        titles_raw = comp.get("titles", "")
        title_list = [t.strip() for t in titles_raw.split("||") if t.strip()]
        title_counter = Counter(title_list)
        top_titles = [t for t, _ in title_counter.most_common(10)]

        # --- Seniority distribution ---
        seniority_counts: dict[str, int] = {}
        for title in title_list:
            for kw, level in SENIORITY_KEYWORDS.items():
                if kw in title:
                    seniority_counts[level] = seniority_counts.get(level, 0) + 1
                    break

        # --- Location distribution ---
        locations_raw = comp.get("locations", "")
        location_list = [l.strip() for l in locations_raw.split("||") if l.strip()]
        location_counter = Counter(location_list)
        top_locations = [l for l, _ in location_counter.most_common(5)]

        # --- Industries ---
        industries_raw = comp.get("industries", "")
        industry_list = [i.strip() for i in industries_raw.split("||") if i.strip()]
        industry_counter = Counter(industry_list)
        top_industries = [i for i, _ in industry_counter.most_common(5)]
        primary_industry = top_industries[0] if top_industries else ""

        # --- Salary range ---
        avg_min = comp.get("avg_salary_min")
        avg_max = comp.get("avg_salary_max")

        # --- Description (synthesized) ---
        description = self._build_description(
            name, comp["job_count"], tech_categories,
            top_titles, top_locations, avg_min, avg_max,
        )

        return {
            "source_job_id": f"ent_{name}",
            "source_url": "",
            "title": name,                              # company name as title
            "company": name,
            "city": ", ".join(top_locations),
            "salary_min": avg_min,
            "salary_max": avg_max,
            "description": description,
            "education": "",
            "experience": "",
            "industry": primary_industry,
            "skills": top_skills,
            # Extended fields
            "source_type": "enterprise",
            "source_name": "enterprise_profile",
            "publish_date": datetime.now().date(),
            "extra": {
                "job_count": comp["job_count"],
                "technology_categories": tech_categories,
                "top_titles": top_titles,
                "top_locations": top_locations,
                "top_industries": top_industries,
                "seniority_distribution": seniority_counts,
                "salary_range": {
                    "avg_min": avg_min,
                    "avg_max": avg_max,
                    "overall_min": comp.get("min_salary"),
                    "overall_max": comp.get("max_salary"),
                },
            },
        }

    @staticmethod
    def _build_description(name: str, job_count: int, tech_categories: list[str],
                           top_titles: list[str], top_locations: list[str],
                           avg_min, avg_max) -> str:
        """Synthesize a human-readable enterprise profile description."""
        parts = [f"{name}共发布{job_count}条招聘信息"]

        if tech_categories:
            parts.append(f"技术方向涵盖{'、'.join(tech_categories[:5])}")

        if top_titles:
            title_preview = "、".join(top_titles[:5])
            parts.append(f"主要招聘岗位包括{title_preview}")

        if top_locations:
            parts.append(f"招聘城市：{'、'.join(top_locations[:5])}")

        if avg_min is not None and avg_max is not None:
            if avg_min >= 1000:
                parts.append(f"平均薪资{avg_min/1000:.0f}K-{avg_max/1000:.0f}K/月")
            else:
                parts.append(f"平均薪资{avg_min:.0f}-{avg_max:.0f}K/月")

        return "。".join(parts) + "。"

    # ------------------------------------------------------------------
    # normalize() — map to unified schema
    # ------------------------------------------------------------------

    def normalize(self, raw: dict) -> dict:
        """Map an enterprise profile to the unified collector schema.

        The enterprise profile maps company data onto the job-oriented schema:
          - title       → company name
          - company     → company name
          - description → synthesized profile text
          - skills      → aggregated technology stack
          - industry    → primary industry from all jobs
        """
        return {
            "source_platform": self.platform,
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
            # Extra fields for ETL
            "source_type": raw.get("source_type", "enterprise"),
            "source_name": raw.get("source_name", self.platform),
            "publish_date": raw.get("publish_date"),
            "extra": raw.get("extra", {}),
        }

    # ------------------------------------------------------------------
    # collect() — override to add enterprise-specific info
    # ------------------------------------------------------------------

    def collect(self, keyword: str = "", city: str = "", max_pages: int = 5) -> CollectResult:
        """Collect enterprise profiles with metadata summary.

        Args:
            keyword: Optional company name filter (partial match)
            city: Optional city filter
            max_pages: Max pages (COMPANIES_PER_PAGE companies per page)
        """
        result = super().collect(keyword, city, max_pages)
        if result.records:
            total_jobs = sum(
                r.get("extra", {}).get("job_count", 0)
                for r in result.records
            )
            logger.info(
                "[enterprise] Total jobs represented across %d companies: %d",
                len(result.records), total_jobs,
            )
        return result


# ---------------------------------------------------------------------------
# __main__ — direct smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # CLI args: keyword, max_pages
    keyword = sys.argv[1] if len(sys.argv) > 1 else ""
    max_pages = int(sys.argv[2]) if len(sys.argv) > 2 else 1

    collector = EnterpriseCollector()
    result = collector.collect(keyword=keyword, max_pages=max_pages)

    print(f"\n{'=' * 60}")
    print(f"Platform:     {result.platform}")
    print(f"Keyword:      {result.keyword or '(all)'}")
    print(f"Records:      {len(result.records)}")
    print(f"Pages:        {result.pages_crawled}")
    print(f"Duration:     {result.duration_seconds}s")
    print(f"Errors:       {len(result.errors)}")
    if result.errors:
        for e in result.errors:
            print(f"  - {e}")
    print(f"{'=' * 60}")

    # Summary stats
    if result.records:
        total_jobs = sum(
            r.get("extra", {}).get("job_count", 0)
            for r in result.records
        )
        print(f"Total jobs represented: {total_jobs}")
        print(f"Companies with most jobs:")
        sorted_records = sorted(
            result.records,
            key=lambda r: r.get("extra", {}).get("job_count", 0),
            reverse=True,
        )
        for rec in sorted_records[:10]:
            extra = rec.get("extra", {})
            print(
                f"  {rec.get('title', '')[:30]:30s} "
                f"jobs={extra.get('job_count', 0):4d}  "
                f"industry={rec.get('industry', '')[:15]:15s}  "
                f"locations={', '.join(extra.get('top_locations', [])[:3])}"
            )

    # Print first 3 detailed profiles
    print(f"\n--- Sample profiles ---")
    for i, rec in enumerate(result.records[:3], 1):
        extra = rec.get("extra", {})
        print(f"\n--- Company {i}: {rec.get('title', '')} ---")
        print(f"  Jobs:        {extra.get('job_count', 0)}")
        print(f"  Industry:    {rec.get('industry', '')}")
        print(f"  Tech Stack:  {', '.join(rec.get('skills', [])[:10])}")
        print(f"  Categories:  {', '.join(extra.get('technology_categories', [])[:5])}")
        print(f"  Top Titles:  {', '.join(extra.get('top_titles', [])[:5])}")
        print(f"  Locations:   {', '.join(extra.get('top_locations', [])[:5])}")
        sal = extra.get("salary_range", {})
        if sal.get("avg_max"):
            print(f"  Salary:      {sal.get('avg_min', '?')} - {sal.get('avg_max', '?')}")
        print(f"  Description: {rec.get('description', '')[:200]}")
