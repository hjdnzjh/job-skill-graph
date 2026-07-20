"""Deep academic paper collection — multi-keyword, multi-threaded ArXiv + Semantic Scholar.

Expands beyond the existing arxiv.py/semantic_scholar.py single-keyword test
pattern. Uses 20 keywords x 2 pages each, writes directly to MySQL via pymysql
INSERT IGNORE, and triggers Neo4j sync on completion.

Usage:
    python -m collector.deep_academic          # run both ArXiv and Semantic Scholar
    python -m collector.deep_academic --arxiv-only
    python -m collector.deep_academic --semantic-only
    python -m collector.deep_academic --test   # 1 keyword, 1 page quick test
"""

import hashlib
import json
import logging
import os
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import pymysql

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from collector.arxiv import ArxivCollector
from collector.semantic_scholar import SemanticScholarCollector

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 20 expanded keywords across CS/AI subfields
# ---------------------------------------------------------------------------
KEYWORDS = [
    "machine learning",
    "deep learning",
    "natural language processing",
    "computer vision",
    "reinforcement learning",
    "software engineering",
    "data mining",
    "cloud computing",
    "blockchain",
    "DevOps",
    "cybersecurity",
    "quantum computing",
    "edge computing",
    "knowledge graph",
    "recommender system",
    "large language model",
    "federated learning",
    "graph neural network",
    "information retrieval",
    "human computer interaction",
]

# ---------------------------------------------------------------------------
# MySQL connection config (matches user-provided credentials)
# ---------------------------------------------------------------------------
MYSQL_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "123456",
    "database": "job_graph",
    "charset": "utf8mb4",
}

# Per-keyword page count
PAGES_PER_KEYWORD = 2
# Records per page (defined in each collector)
MAX_WORKERS = 4  # concurrent keyword workers


# ---------------------------------------------------------------------------
# MySQL direct write helpers
# ---------------------------------------------------------------------------

def get_mysql_connection():
    return pymysql.connect(**MYSQL_CONFIG)


def generate_record_id(source_type: str, source_id: str) -> str:
    """Generate a deterministic UUID v5 from source_type + source_id.

    This ensures the same source record always maps to the same UUID,
    making INSERT IGNORE effective for deduplication.
    """
    namespace = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")  # standard DNS namespace
    raw = f"{source_type}:{source_id}"
    return str(uuid.uuid5(namespace, raw))


def compute_quality(record: dict) -> tuple:
    """Compute a simple quality score and grade for academic records."""
    score = 0.0
    # Title present
    if record.get("title"):
        score += 25
    # Description/abstract present
    desc = record.get("description") or record.get("job_description", "")
    if desc and len(desc) > 100:
        score += 30
    elif desc:
        score += 15
    # Skills extracted
    skills = record.get("skills_required") or record.get("skills", [])
    if isinstance(skills, list) and len(skills) >= 3:
        score += 20
    elif isinstance(skills, list) and len(skills) >= 1:
        score += 10
    # Publish date present
    if record.get("publish_date"):
        score += 10
    # Source URL present
    if record.get("source_url"):
        score += 10
    # Industry present
    if record.get("industry"):
        score += 5

    if score >= 80:
        grade = "A"
    elif score >= 60:
        grade = "B"
    elif score >= 40:
        grade = "C"
    else:
        grade = "D"
    return score, grade


def insert_records(records: list, source_type: str) -> int:
    """Insert normalized records into MySQL using INSERT IGNORE.

    Returns the number of newly inserted rows.
    """
    if not records:
        return 0

    conn = get_mysql_connection()
    inserted = 0
    now = datetime.now()

    sql = """
        INSERT IGNORE INTO job_records (
            record_id, source_id, source_type, source_name, source_url,
            job_title, job_title_raw, company_name, company_name_raw,
            industry, location, location_raw, job_description,
            salary_min, salary_max, experience_required, education_required,
            job_type, skills_required, skills_preferred, abilities,
            publish_date, crawl_timestamp, data_format,
            quality_score, quality_grade, completeness_score,
            freshness_score, consistency_score, extra
        ) VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s
        )
    """

    try:
        with conn.cursor() as cursor:
            for rec in records:
                source_id = str(rec.get("source_job_id", ""))
                if not source_id:
                    # Fallback: hash the title as source_id
                    source_id = hashlib.md5(
                        rec.get("title", "untitled").encode()
                    ).hexdigest()[:16]

                record_id = generate_record_id(source_type, source_id)
                title = (rec.get("title") or "")[:255]
                description = (rec.get("description") or "")[:65535]
                company = (rec.get("company") or "")[:255]
                industry = (rec.get("industry") or "")[:128]
                source_url = (rec.get("source_url") or "")[:2048]
                source_name = rec.get("source_name", source_type)
                skills = rec.get("skills") or rec.get("skills_required", [])
                if isinstance(skills, str):
                    skills = [skills]
                skills = list(skills) if skills else []

                publish_date = rec.get("publish_date")
                if isinstance(publish_date, str) and publish_date:
                    try:
                        publish_date = datetime.fromisoformat(publish_date.replace("Z", "+00:00"))
                    except (ValueError, TypeError):
                        publish_date = None

                quality_score, quality_grade = compute_quality(rec)

                cursor.execute(sql, (
                    record_id,                     # record_id
                    source_id,                     # source_id
                    source_type,                   # source_type
                    source_name,                   # source_name
                    source_url,                    # source_url
                    title,                         # job_title
                    title,                         # job_title_raw
                    company,                       # company_name
                    company,                       # company_name_raw
                    industry,                      # industry
                    "",                             # location
                    "",                             # location_raw
                    description,                   # job_description
                    None,                          # salary_min
                    None,                          # salary_max
                    "",                             # experience_required
                    "",                             # education_required
                    "",                             # job_type
                    json.dumps(skills, ensure_ascii=False),  # skills_required
                    json.dumps([], ensure_ascii=False),      # skills_preferred
                    json.dumps([], ensure_ascii=False),      # abilities
                    publish_date,                  # publish_date
                    now,                           # crawl_timestamp
                    "semi_structured",             # data_format
                    quality_score,                 # quality_score
                    quality_grade,                 # quality_grade
                    0.0,                           # completeness_score
                    0.0,                           # freshness_score
                    0.0,                           # consistency_score
                    json.dumps({}, ensure_ascii=False),  # extra
                ))
                inserted += 1
        conn.commit()
    except Exception as e:
        logger.error("MySQL insert error: %s", e)
        conn.rollback()
    finally:
        conn.close()

    return inserted


# ---------------------------------------------------------------------------
# Collection logic
# ---------------------------------------------------------------------------

def collect_keyword_arxiv(kw: str) -> tuple:
    """Collect ArXiv papers for a single keyword. Returns (keyword, records, errors)."""
    collector = ArxivCollector()
    records = []
    errors = []
    try:
        for page in range(1, PAGES_PER_KEYWORD + 1):
            raw = collector.search(kw, page=page)
            if not raw:
                break
            normalized = [collector.normalize(r) for r in raw]
            # Tag with source_name for MySQL
            for n in normalized:
                n["source_name"] = "arxiv"
            records.extend(normalized)
            if page < PAGES_PER_KEYWORD:
                time.sleep(3)  # ArXiv rate limit: be polite
    except Exception as e:
        errors.append(f"ArXiv '{kw}': {e}")

    return kw, records, errors


def collect_keyword_semantic(kw: str) -> tuple:
    """Collect Semantic Scholar papers for a single keyword. Returns (keyword, records, errors)."""
    collector = SemanticScholarCollector()
    records = []
    errors = []
    try:
        for page in range(1, PAGES_PER_KEYWORD + 1):
            raw = collector.search(kw, page=page)
            if not raw:
                # 429 rate limit or no results
                break
            normalized = [collector.normalize(r) for r in raw]
            for n in normalized:
                n["source_name"] = "semantic_scholar"
            records.extend(normalized)
            if page < PAGES_PER_KEYWORD:
                time.sleep(5)  # Semantic Scholar: ~100 req/5 min, very conservative
    except Exception as e:
        errors.append(f"SemanticScholar '{kw}': {e}")

    return kw, records, errors


def run_arxiv_collection(keywords: list) -> dict:
    """Multi-threaded ArXiv collection across all keywords."""
    logger.info("=" * 60)
    logger.info("TASK A1: ArXiv multi-keyword collection")
    logger.info(f"  Keywords: {len(keywords)}")
    logger.info(f"  Pages per keyword: {PAGES_PER_KEYWORD}")
    logger.info(f"  Max workers: {MAX_WORKERS}")
    logger.info("=" * 60)

    all_records = []
    all_errors = []
    results_by_keyword = {}

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(collect_keyword_arxiv, kw): kw
            for kw in keywords
        }
        for future in as_completed(futures):
            kw, records, errors = future.result()
            results_by_keyword[kw] = len(records)
            all_records.extend(records)
            all_errors.extend(errors)
            logger.info(
                "  [arxiv] '%s' → %d records%s",
                kw, len(records),
                f" (errors: {errors})" if errors else "",
            )

    # Write to MySQL
    logger.info("Writing %d ArXiv records to MySQL...", len(all_records))
    inserted = insert_records(all_records, "academic")
    logger.info("MySQL: %d new records inserted (total: %d)", inserted, len(all_records))

    return {
        "source": "arxiv",
        "total_collected": len(all_records),
        "inserted": inserted,
        "by_keyword": results_by_keyword,
        "errors": all_errors,
    }


def run_semantic_collection(keywords: list) -> dict:
    """Multi-threaded Semantic Scholar collection across all keywords."""
    logger.info("=" * 60)
    logger.info("TASK A2: Semantic Scholar multi-keyword collection")
    logger.info(f"  Keywords: {len(keywords)}")
    logger.info(f"  Pages per keyword: {PAGES_PER_KEYWORD}")
    logger.info(f"  Max workers: 2 (conservative for rate limits)")
    logger.info("=" * 60)

    all_records = []
    all_errors = []
    results_by_keyword = {}

    # Very conservative — Semantic Scholar has strict rate limits
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {
            executor.submit(collect_keyword_semantic, kw): kw
            for kw in keywords
        }
        for future in as_completed(futures):
            kw, records, errors = future.result()
            results_by_keyword[kw] = len(records)
            all_records.extend(records)
            all_errors.extend(errors)
            logger.info(
                "  [semantic_scholar] '%s' → %d records%s",
                kw, len(records),
                f" (errors: {errors})" if errors else "",
            )

    if all_records:
        logger.info("Writing %d Semantic Scholar records to MySQL...", len(all_records))
        inserted = insert_records(all_records, "academic")
        logger.info("MySQL: %d new records inserted (total: %d)", inserted, len(all_records))
    else:
        inserted = 0
        logger.warning("Semantic Scholar: zero records collected (rate limited or no results)")

    return {
        "source": "semantic_scholar",
        "total_collected": len(all_records),
        "inserted": inserted,
        "by_keyword": results_by_keyword,
        "errors": all_errors,
    }


def trigger_neo4j_sync():
    """Trigger Neo4j knowledge graph synchronization."""
    logger.info("=" * 60)
    logger.info("NEO4J SYNC: Running graph builder...")
    logger.info("=" * 60)

    try:
        from config.settings import Settings
        from kg.graph_builder import GraphBuilder

        settings = Settings()
        # Override passwords from known config
        settings.mysql_password = "123456"
        settings.neo4j_password = "12345678"

        builder = GraphBuilder(settings)
        stats = builder.build(clear_existing=False)
        logger.info("Neo4j sync complete. Stats: %s", stats)
        return stats
    except Exception as e:
        logger.error("Neo4j sync failed: %s", e)
        return {"error": str(e)}


def print_mysql_stats():
    """Query and print current MySQL record counts by source_type."""
    logger.info("=" * 60)
    logger.info("MySQL: record counts by source_type")
    logger.info("=" * 60)

    try:
        conn = get_mysql_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT source_type, source_name, COUNT(*) as cnt "
                "FROM job_records "
                "GROUP BY source_type, source_name "
                "ORDER BY source_type, cnt DESC"
            )
            rows = cursor.fetchall()
            if rows:
                print(f"\n{'source_type':<20} {'source_name':<30} {'count':>8}")
                print("-" * 60)
                for source_type, source_name, cnt in rows:
                    print(f"{source_type:<20} {source_name:<30} {cnt:>8}")

            # Total
            cursor.execute("SELECT COUNT(*) FROM job_records")
            total = cursor.fetchone()[0]
            print(f"\n  TOTAL: {total} records")
        conn.close()
    except Exception as e:
        logger.error("MySQL query failed: %s", e)


# ---------------------------------------------------------------------------
# __main__
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    args = set(sys.argv[1:])
    test_mode = "--test" in args
    arxiv_only = "--arxiv-only" in args
    semantic_only = "--semantic-only" in args
    skip_sync = "--skip-sync" in args

    if not arxiv_only and not semantic_only:
        arxiv_only = semantic_only = True  # run both

    keywords = KEYWORDS[:1] if test_mode else KEYWORDS
    pages = 1 if test_mode else PAGES_PER_KEYWORD
    PAGES_PER_KEYWORD = pages

    logger.info("Deep Academic Collection starting...")
    logger.info("  Keywords: %d, Pages per keyword: %d", len(keywords), pages)
    logger.info("  Test mode: %s", test_mode)
    start = time.time()

    stats = {}

    if arxiv_only:
        stats["arxiv"] = run_arxiv_collection(keywords)

    if semantic_only:
        stats["semantic_scholar"] = run_semantic_collection(keywords)

    duration = round(time.time() - start, 1)
    logger.info("Collection duration: %.1fs", duration)

    # Print summary
    print("\n" + "=" * 60)
    print("ACADEMIC COLLECTION SUMMARY")
    print("=" * 60)
    for source, s in stats.items():
        print(f"\n  [{source}]")
        print(f"    Total collected: {s['total_collected']}")
        print(f"    MySQL inserted:  {s['inserted']}")
        print(f"    Errors:          {len(s['errors'])}")
        if s["by_keyword"]:
            print(f"    Keywords:        {len(s['by_keyword'])}")
            total_per_kw = sum(s["by_keyword"].values())
            print(f"    Avg/keyword:     {total_per_kw / max(len(s['by_keyword']), 1):.1f}")

    # MySQL stats
    print_mysql_stats()

    # Neo4j sync
    if not skip_sync:
        trigger_neo4j_sync()
    else:
        logger.info("Skipping Neo4j sync (--skip-sync)")

    print(f"\nTotal duration: {duration}s")
