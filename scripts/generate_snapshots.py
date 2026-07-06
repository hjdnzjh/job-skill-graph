"""
一次性脚本：生成演化快照基线 + 模拟历史快照 + 验证趋势分析。

执行：
    python scripts/generate_snapshots.py

输出：
    - data/snapshots/ 目录下生成快照 JSON 文件
    - 终端打印快照时间线对比
"""

import json
import logging
import os
import sys
import random
from datetime import datetime, timedelta
from copy import deepcopy

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Add project to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "caiji"))

from config.settings import Settings
from kg.evolution import EvolutionTracker, SNAPSHOT_DIR

random.seed(42)  # deterministic


def simulate_historical(snapshot: dict, months_ago: int) -> dict:
    """Create a simulated earlier snapshot by reducing numbers proportionally.

    The further back in time, the more reduction applied.
    Non-technical assumption: over the past year, the graph grew roughly linearly.
    """
    factor = 1.0 - months_ago * 0.08  # e.g., 12mo → 0.04 (96% reduction... wait that's too much)
    # Better: assume 5% growth per month
    growth_per_month = 0.05
    scale = 1.0 / (1.0 + growth_per_month * months_ago)

    sim = deepcopy(snapshot)
    # Adjust timestamp
    ts = datetime.fromisoformat(snapshot["timestamp"]) - timedelta(days=months_ago * 30)
    sim["timestamp"] = ts.isoformat()
    sim["record_count"] = max(1, int(snapshot["record_count"] * scale))

    # Adjust graph stats
    g = sim["graph"]
    g["total_nodes"] = max(1, int(g["total_nodes"] * scale))
    g["total_edges"] = max(1, int(g["total_edges"] * scale))
    for label in g["nodes_by_label"]:
        g["nodes_by_label"][label] = max(1, int(g["nodes_by_label"][label] * scale))
    for rel in g["relationships_by_type"]:
        cnt = g["relationships_by_type"][rel]
        g["relationships_by_type"][rel] = max(1, int(cnt * scale))

    # Adjust top skills (add some shuffle for realism)
    for s in sim["top_skills"]:
        s["demand"] = max(1, int(s["demand"] * scale * random.uniform(0.85, 1.0)))
    sim["top_skills"].sort(key=lambda x: -x["demand"])
    for i, s in enumerate(sim["top_skills"]):
        s["rank"] = i + 1

    # Adjust companies
    for c in sim["top_companies"]:
        c["jobs"] = max(1, int(c["jobs"] * scale * random.uniform(0.8, 1.0)))
    sim["top_companies"].sort(key=lambda x: -x["jobs"])
    for i, c in enumerate(sim["top_companies"]):
        c["rank"] = i + 1

    # Adjust salary
    for s in sim["salary"]:
        s["avg_min"] = round(s["avg_min"] * random.uniform(0.9, 1.0) if s.get("avg_min") else None, 1)
        s["avg_max"] = round(s["avg_max"] * random.uniform(0.9, 1.0) if s.get("avg_max") else None, 1)
        s["cnt"] = max(1, int(s["cnt"] * scale))

    # Adjust cities
    for c in sim["city_distribution"]:
        c["jobs"] = max(1, int(c["jobs"] * scale))
        c["rank"] = c.get("rank", 0)

    sim["_simulated"] = True
    sim["_simulation_note"] = (
        f"Simulated historical snapshot at T-{months_ago} months. "
        f"Generated from baseline by applying ~{int((1-scale)*100)}% scale-down factor. "
        "For demonstration purposes only."
    )

    return sim


def main():
    settings = Settings()
    tracker = EvolutionTracker(settings)

    # Step 1: Save baseline snapshot
    logger.info("Saving baseline snapshot...")
    baseline_path = tracker.save_snapshot(record_count=1175)
    logger.info(f"Baseline: {baseline_path}")

    # Step 2: Generate simulated historical snapshots
    baseline_data = tracker.load_snapshot(baseline_path)
    base_ts = datetime.fromisoformat(baseline_data["timestamp"])

    hist_months = [12, 6, 3]
    hist_paths = []
    for months in hist_months:
        sim_data = simulate_historical(baseline_data, months)
        hist_ts = base_ts - timedelta(days=months * 30)
        filename = hist_ts.strftime("%Y-%m-%d_%H%M%S") + ".json"
        filepath = os.path.join(SNAPSHOT_DIR, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(sim_data, f, ensure_ascii=False, indent=2, default=str)
        hist_paths.append(filepath)
        logger.info(f"Historical T-{months}mo: {filepath}")

    # Step 3: Print timeline
    all_snapshots = [baseline_path] + hist_paths
    all_snapshots.sort()  # chronological
    tracker.print_timeline(all_snapshots)

    # Step 4: Show comparison (baseline vs oldest)
    if len(all_snapshots) >= 2:
        logger.info("\n=== Baseline vs Oldest Snapshot Comparison ===")
        diff = tracker.compare(all_snapshots[0], all_snapshots[-1])
        tracker.print_report(diff)

    # Step 5: Save snapshot listing for API consumption
    listing = []
    for path in all_snapshots:
        snap = tracker.load_snapshot(path)
        listing.append({
            "path": os.path.basename(path),
            "timestamp": snap["timestamp"],
            "record_count": snap.get("record_count", 0),
            "total_nodes": snap["graph"]["total_nodes"],
            "total_edges": snap["graph"]["total_edges"],
            "simulated": snap.get("_simulated", False),
        })

    listing_path = os.path.join(SNAPSHOT_DIR, "snapshot_index.json")
    with open(listing_path, "w", encoding="utf-8") as f:
        json.dump(listing, f, ensure_ascii=False, indent=2)
    logger.info(f"Snapshot index: {listing_path}")

    tracker.close()
    logger.info("Done.")


if __name__ == "__main__":
    main()
