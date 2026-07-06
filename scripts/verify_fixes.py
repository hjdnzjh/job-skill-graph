"""
数据修复验证脚本：执行修复前后对比检查，输出数据质量报告。

执行：
    python scripts/verify_fixes.py
"""

import logging
import os
import sys
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "caiji"))

NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "12345678"
NEO4J_DATABASE = "neo4j"


def run_checks():
    from neo4j import GraphDatabase
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    driver.verify_connectivity()

    checks = {}
    with driver.session(database=NEO4J_DATABASE) as session:
        # 1. Skill completeness
        total_skills = session.run("MATCH (s:Skill) RETURN count(s) AS cnt").single()["cnt"]
        empty_cat = session.run(
            "MATCH (s:Skill) WHERE s.category IS NULL OR s.category = '' RETURN count(s) AS cnt"
        ).single()["cnt"]
        checks["skills_total"] = total_skills
        checks["skills_missing_category"] = empty_cat

        # 2. EmergingJob
        ej_count = session.run("MATCH (e:EmergingJob) RETURN count(e) AS cnt").single()["cnt"]
        ej_rels = session.run(
            "MATCH (e:EmergingJob)-[r:REQUIRES]->(s:Skill) RETURN count(r) AS cnt"
        ).single()["cnt"]
        checks["emerging_jobs"] = ej_count
        checks["emerging_job_relations"] = ej_rels

        # 3. Salary completeness
        null_sal = session.run(
            "MATCH (j:Job) WHERE j.salary_min IS NULL RETURN count(j) AS cnt"
        ).single()["cnt"]
        checks["jobs_null_salary"] = null_sal

        # 4. Orphan nodes
        orphan_skills = session.run(
            "MATCH (s:Skill) WHERE NOT (s)<-[:REQUIRES]-(:Job) RETURN count(s) AS cnt"
        ).single()["cnt"]
        orphan_jobs_no_req = session.run(
            "MATCH (j:Job) WHERE NOT (j)-[:REQUIRES]->(:Skill) RETURN count(j) AS cnt"
        ).single()["cnt"]
        checks["orphan_skills"] = orphan_skills
        checks["orphan_jobs"] = orphan_jobs_no_req

        # 5. Duplicates
        dup_skills = session.run(
            "MATCH (s:Skill) WITH s.name AS name, collect(s) AS nodes WHERE size(nodes) > 1 RETURN count(name) AS cnt"
        ).single()["cnt"]
        dup_jobs = session.run(
            "MATCH (j:Job) WITH j.record_id AS rid, collect(j) AS nodes WHERE size(nodes) > 1 RETURN count(rid) AS cnt"
        ).single()["cnt"]
        checks["duplicate_skills"] = dup_skills
        checks["duplicate_jobs"] = dup_jobs

        # 6. Snapshot count
        import json
        snapshot_index = "data/snapshots/snapshot_index.json"
        if os.path.exists(snapshot_index):
            with open(snapshot_index, "r", encoding="utf-8") as f:
                snaps = json.load(f)
            checks["snapshots"] = len(snaps)
            checks["snapshot_timespan"] = (
                f"{snaps[0]['timestamp'][:10]} ~ {snaps[-1]['timestamp'][:10]}"
                if len(snaps) >= 2 else "single"
            )
        else:
            checks["snapshots"] = 0
            checks["snapshot_timespan"] = "none"

        # 7. Graph size
        total_nodes = session.run("MATCH (n) RETURN count(n) AS cnt").single()["cnt"]
        total_edges = session.run("MATCH ()-[r]->() RETURN count(r) AS cnt").single()["cnt"]
        checks["total_nodes"] = total_nodes
        checks["total_edges"] = total_edges

        # 8. Unique constraint verification
        constraints = session.run("SHOW CONSTRAINTS").data()
        checks["constraints"] = [c.get("name", "") for c in constraints]

    driver.close()
    return checks


def print_report(checks: dict):
    print("\n" + "=" * 60)
    print("  Data Quality Fix Verification Report")
    print("=" * 60)

    all_pass = True

    print(f"\n  [GRAPH] Graph Size")
    print(f"     Total nodes: {checks['total_nodes']}")
    print(f"     Total edges: {checks['total_edges']}")

    print(f"\n  [SKILL] Skill Data")
    skills_ok = checks["skills_missing_category"] == 0
    print(f"     [{'OK' if skills_ok else 'FAIL'}] Total skills: {checks['skills_total']}")
    print(f"     [{'OK' if skills_ok else 'FAIL'}] Missing category: {checks['skills_missing_category']}")
    all_pass = all_pass and skills_ok

    print(f"\n  [EMERGING] Emerging Jobs")
    ej_ok = checks["emerging_jobs"] > 0
    print(f"     [{'OK' if ej_ok else 'FAIL'}] EmergingJob nodes: {checks['emerging_jobs']}")
    print(f"     [{'OK' if ej_ok else 'FAIL'}] Skill relations: {checks['emerging_job_relations']}")
    all_pass = all_pass and ej_ok

    print(f"\n  [SALARY] Salary Data")
    sal_ok = checks["jobs_null_salary"] == 0
    print(f"     [{'OK' if sal_ok else 'FAIL'}] NULL salary jobs: {checks['jobs_null_salary']}")
    all_pass = all_pass and sal_ok

    print(f"\n  [ORPHAN] Orphan Nodes")
    print(f"     [INFO] Orphan skills (no REQUIRES): {checks['orphan_skills']}")
    print(f"     [INFO] Orphan jobs (no REQUIRES): {checks['orphan_jobs']}")

    print(f"\n  [DUPLICATE] Duplicate Nodes")
    dup_ok = checks["duplicate_skills"] == 0 and checks["duplicate_jobs"] == 0
    print(f"     [{'OK' if checks['duplicate_skills'] == 0 else 'FAIL'}] Duplicate skills: {checks['duplicate_skills']}")
    print(f"     [{'OK' if checks['duplicate_jobs'] == 0 else 'FAIL'}] Duplicate jobs: {checks['duplicate_jobs']}")
    all_pass = all_pass and dup_ok

    print(f"\n  [SNAPSHOT] Evolution Snapshots")
    snap_ok = checks["snapshots"] >= 2
    print(f"     [{'OK' if snap_ok else 'FAIL'}] Snapshot count: {checks['snapshots']}")
    print(f"     [{'OK' if snap_ok else 'FAIL'}] Timespan: {checks['snapshot_timespan']}")
    all_pass = all_pass and snap_ok

    print(f"\n  [CONSTRAINTS] Constraints")
    print(f"     Total: {len(checks['constraints'])}")
    for c in checks["constraints"]:
        print(f"      - {c}")

    print("\n" + "=" * 60)
    if all_pass:
        print("  ALL KEY CHECKS PASSED. Data baseline is ready.")
    else:
        print("  Some checks failed. See details above.")
    print("=" * 60 + "\n")

    return all_pass


if __name__ == "__main__":
    print(f"\n  数据质量验证 — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    checks = run_checks()
    print_report(checks)
