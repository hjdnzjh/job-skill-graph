"""
一次性脚本：填充 Job 节点中为 NULL 的薪资字段。

策略：
1. 按 job_title 分组取中位数（同一岗位的薪资更接近）
2. 若某 title 组全部为空，退化为全局中位数（14k/20k）

执行：
    python scripts/fix_null_salaries.py

可回滚：本脚本记录所有被修改的节点 ID 和填充值。
"""

import csv
import logging
import sys
from datetime import datetime

from neo4j import GraphDatabase

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "12345678"
NEO4J_DATABASE = "neo4j"

ROLLBACK_LOG = "data/fix_null_salaries_rollback.csv"


def main():
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    driver.verify_connectivity()
    logger.info("Connected to Neo4j")

    rollback_rows = []  # For rollback log

    with driver.session(database=NEO4J_DATABASE) as session:
        # Step 1: Get global median
        global_stats = session.run("""
            MATCH (j:Job)
            WHERE j.salary_min IS NOT NULL
            RETURN percentileCont(j.salary_min, 0.5) AS p50_min,
                   percentileCont(j.salary_max, 0.5) AS p50_max
        """).single()
        global_min = round(global_stats["p50_min"], 1)
        global_max = round(global_stats["p50_max"], 1)
        logger.info(f"Global median salary: {global_min}k - {global_max}k")

        # Step 2: Get median by job_title
        title_medians = session.run("""
            MATCH (j:Job)
            WHERE j.salary_min IS NOT NULL AND j.job_title IS NOT NULL
            WITH j.job_title AS title,
                 percentileCont(j.salary_min, 0.5) AS med_min,
                 percentileCont(j.salary_max, 0.5) AS med_max
            WHERE med_min IS NOT NULL
            RETURN title, med_min, med_max
        """)
        title_map = {}
        for r in title_medians:
            title_map[r["title"]] = (round(r["med_min"], 1), round(r["med_max"], 1))
        logger.info(f"Got title-level medians for {len(title_map)} job titles")

        # Step 3: Find NULL salary jobs and fill
        null_jobs = session.run("""
            MATCH (j:Job)
            WHERE j.salary_min IS NULL
            RETURN j.record_id AS rid, j.job_title AS title
        """)

        fixed_count = 0
        skipped_count = 0
        for job in null_jobs:
            rid = job["rid"]
            title = job["title"]

            # Determine fill values
            if title and title in title_map:
                fill_min, fill_max = title_map[title]
                method = f"title_median:{title}"
            else:
                fill_min, fill_max = global_min, global_max
                method = "global_median"

            # Record before state for rollback
            rollback_rows.append({
                "record_id": rid,
                "old_min": "NULL",
                "old_max": "NULL",
                "new_min": fill_min,
                "new_max": fill_max,
                "method": method,
            })

            # Apply fix
            result = session.run("""
                MATCH (j:Job {record_id: $rid})
                SET j.salary_min = $fill_min,
                    j.salary_max = $fill_max
                RETURN j.record_id
            """, {"rid": rid, "fill_min": fill_min, "fill_max": fill_max})

            if result.single():
                fixed_count += 1
                logger.debug(f"  Fixed {rid}: salary=({fill_min}, {fill_max}) via {method}")

        logger.info(f"Fixed: {fixed_count}, Skipped: {skipped_count}")

        # Step 4: Verify
        remaining = session.run("""
            MATCH (j:Job) WHERE j.salary_min IS NULL RETURN count(j) AS cnt
        """).single()["cnt"]
        logger.info(f"Remaining NULL salary jobs: {remaining}")

    # Step 5: Write rollback log
    if rollback_rows:
        with open(ROLLBACK_LOG, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "record_id", "old_min", "old_max", "new_min", "new_max", "method"
            ])
            writer.writeheader()
            writer.writerows(rollback_rows)
        logger.info(f"Rollback log written to {ROLLBACK_LOG} ({len(rollback_rows)} records)")

    driver.close()
    logger.info("Done.")


if __name__ == "__main__":
    main()
