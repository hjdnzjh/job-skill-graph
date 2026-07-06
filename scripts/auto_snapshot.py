"""
自动快照脚本：定期保存知识图谱演化快照。

部署方式（Windows 任务计划程序）：
    schtasks /create /tn "JobSkill-Snapshot" /tr "python scripts/auto_snapshot.py" /sc weekly /d MON /st 02:00

也可以手动运行：
    python scripts/auto_snapshot.py
"""

import logging
import os
import sys
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "caiji"))


def main():
    from config.settings import Settings
    from kg.evolution import EvolutionTracker

    settings = Settings()
    tracker = EvolutionTracker(settings)

    # Get current record count from Neo4j
    from neo4j import GraphDatabase
    driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
    )
    with driver.session(database=settings.neo4j_database) as session:
        result = session.run("MATCH (j:Job) RETURN count(j) AS cnt").single()
        record_count = result["cnt"] if result else 0
    driver.close()

    # Save snapshot
    path = tracker.save_snapshot(record_count=record_count)
    logger.info(f"Auto-snapshot saved: {path}")

    # Rebuild snapshot index
    snapshots = tracker.list_snapshots()
    import json
    listing = []
    for p in snapshots:
        snap = tracker.load_snapshot(p)
        listing.append({
            "path": os.path.basename(p),
            "timestamp": snap["timestamp"],
            "record_count": snap.get("record_count", 0),
            "total_nodes": snap["graph"]["total_nodes"],
            "total_edges": snap["graph"]["total_edges"],
            "simulated": snap.get("_simulated", False),
        })
    index_path = os.path.join(
        os.path.dirname(path), "snapshot_index.json"
    )
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(listing, f, ensure_ascii=False, indent=2)
    logger.info(f"Snapshot index updated: {index_path}")

    tracker.close()


if __name__ == "__main__":
    main()
