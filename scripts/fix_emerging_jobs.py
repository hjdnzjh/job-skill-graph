"""
一次性脚本：从 discovered_jobs.json 导入 EmergingJob 节点到 Neo4j。

执行：
    python scripts/fix_emerging_jobs.py

功能：
1. 建立 EmergingJob 唯一名称约束
2. 读取 discovered_jobs.json 中 category=emerging 且有关键技能的条目
3. 创建 EmergingJob 节点（含职责、技能要求等信息）
4. 与已有 Skill 节点建立 REQUIRES 关系
"""

import json
import logging
import sys
from pathlib import Path

from neo4j import GraphDatabase

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "12345678"
NEO4J_DATABASE = "neo4j"

DISCOVERED_PATH = Path("caiji/data/discovered_jobs.json")


def main():
    # 1. Connect
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    driver.verify_connectivity()
    logger.info(f"Connected to Neo4j at {NEO4J_URI}")

    # 2. Create uniqueness constraint
    with driver.session(database=NEO4J_DATABASE) as session:
        session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (e:EmergingJob) REQUIRE e.name IS UNIQUE")
        logger.info("EmergingJob uniqueness constraint created/verified")

    # 3. Read discovered jobs
    if not DISCOVERED_PATH.exists():
        logger.error(f"File not found: {DISCOVERED_PATH}")
        sys.exit(1)

    with open(DISCOVERED_PATH, "r", encoding="utf-8") as f:
        discovered = json.load(f)

    # 4. Filter emerging entries with skills
    emerging = [
        j for j in discovered
        if j.get("category") == "emerging"
        and len(j.get("required_skills", [])) > 0
    ]

    # Deduplicate by normalized_title
    seen_titles = set()
    unique_emerging = []
    for j in emerging:
        title = j["normalized_title"]
        if title not in seen_titles:
            seen_titles.add(title)
            unique_emerging.append(j)

    logger.info(f"Found {len(emerging)} emerging entries, {len(unique_emerging)} unique after dedup")

    # 5. Import each emerging job
    stats = {"created": 0, "skipped": 0, "relations": 0}
    with driver.session(database=NEO4J_DATABASE) as session:
        for job in unique_emerging:
            title = job["normalized_title"]
            resp = job.get("responsibilities", "")
            required = job.get("required_skills", [])
            preferred = job.get("preferred_skills", [])
            industries = job.get("industries", [])
            confidence = job.get("confidence", 0)
            job_count = job.get("job_count", 0)

            # Create node
            result = session.run(
                """
                MERGE (e:EmergingJob {name: $name})
                SET e += {
                    responsibilities: $resp,
                    confidence: $confidence,
                    job_count: $job_count,
                    industries: $industries_str,
                    preferred_skills: $preferred_str,
                    source: 'discovered_jobs.json',
                    imported_at: timestamp()
                }
                RETURN e.name AS name, coalesce(e._imported, false) AS existed
                """,
                {
                    "name": title,
                    "resp": resp,
                    "confidence": confidence,
                    "job_count": job_count,
                    "industries_str": ", ".join(industries),
                    "preferred_str": ", ".join(preferred),
                },
            )
            record = result.single()
            if record and not record.get("existed"):
                stats["created"] += 1
                logger.info(f"  Created: {title}")
            else:
                stats["skipped"] += 1
                logger.info(f"  Skipped (already exists): {title}")

            # Link to existing Skill nodes
            all_skills = required + [s for s in preferred if s not in required]
            for skill_name in all_skills:
                # Skip compound skill names like "Express/Koa"
                if "/" in skill_name:
                    continue
                # Clean up skill name (remove framework prefixes)
                clean_name = skill_name.strip()
                result2 = session.run(
                    """
                    MATCH (e:EmergingJob {name: $ename})
                    MATCH (s:Skill {name: $sname})
                    MERGE (e)-[r:REQUIRES]->(s)
                    SET r.source = 'job_discovery'
                    RETURN count(r) AS linked
                    """,
                    {"ename": title, "sname": clean_name},
                )
                rec = result2.single()
                if rec and rec["linked"] > 0:
                    stats["relations"] += 1
                    logger.debug(f"    Linked {title} -> {clean_name}")
                else:
                    logger.debug(f"    Skill not found: {clean_name}")

    logger.info(f"\nImport complete:")
    logger.info(f"  Nodes created: {stats['created']}")
    logger.info(f"  Nodes skipped: {stats['skipped']}")
    logger.info(f"  Relations created: {stats['relations']}")

    # 6. Verify
    with driver.session(database=NEO4J_DATABASE) as session:
        total = session.run("MATCH (e:EmergingJob) RETURN count(e) AS cnt").single()["cnt"]
        logger.info(f"Total EmergingJob nodes now: {total}")

    driver.close()
    logger.info("Done.")


if __name__ == "__main__":
    main()
