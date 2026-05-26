"""Knowledge graph evolution analysis CLI.

Compare snapshots to detect skill trends, salary changes, and
emerging/delining demand patterns.

Usage:
    python main_evolution.py                    # list all snapshots + timeline
    python main_evolution.py --compare 0 1      # compare snapshot #0 and #1
    python main_evolution.py --compare latest   # compare latest two snapshots
"""

import argparse
import logging
import sys

from config.settings import Settings
from kg.evolution import EvolutionTracker

logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="知识图谱演化分析工具"
    )
    parser.add_argument(
        "--compare", metavar="SPEC", type=str, default=None,
        help="对比快照: --compare 0,1 (按编号) 或 --compare latest (最近两个)",
    )
    parser.add_argument(
        "--list", "-l", action="store_true",
        help="列出所有快照",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    settings = Settings()
    tracker = EvolutionTracker(settings)

    try:
        snapshots = tracker.list_snapshots()

        if not snapshots:
            print("\n暂无快照。运行以下命令保存第一个快照：")
            print("  python main_kg.py --snapshot\n")
            return

        if args.compare:
            _handle_compare(tracker, snapshots, args.compare)
        else:
            # Default: list + timeline
            _handle_default(tracker, snapshots, list_only=args.list)

    finally:
        tracker.close()


def _handle_default(tracker, snapshots, list_only=False):
    """Print snapshot list and timeline overview."""
    print(f"\n共 {len(snapshots)} 个快照：\n")

    for i, path in enumerate(snapshots):
        snap = tracker.load_snapshot(path)
        ts = snap["timestamp"]
        records = snap.get("record_count", "?")
        nodes = snap["graph"]["total_nodes"]
        edges = snap["graph"]["total_edges"]
        print(f"  [{i}] {ts}  —  {records} 条记录, {nodes} 节点, {edges} 边")

    if not list_only:
        tracker.print_timeline(snapshots)


def _handle_compare(tracker, snapshots, spec):
    """Resolve comparison targets and print diff report.

    spec formats:
        "latest" — compare latest two snapshots
        "0,1" — compare by index
    """
    if spec.lower() == "latest":
        if len(snapshots) < 2:
            print("\n至少需要 2 个快照才能对比 latest\n")
            return
        idx_a = len(snapshots) - 2
        idx_b = len(snapshots) - 1
    else:
        parts = spec.split(",")
        if len(parts) != 2:
            print(f"\n无效格式: {spec}，请使用 '0,1' 或 'latest'\n")
            return
        try:
            idx_a = int(parts[0].strip())
            idx_b = int(parts[1].strip())
        except ValueError:
            print(f"\n无效编号: {spec}，请使用数字\n")
            return

    # Validate indices
    max_idx = len(snapshots) - 1
    if idx_a < 0 or idx_a > max_idx or idx_b < 0 or idx_b > max_idx:
        print(f"\n编号超出范围 (0~{max_idx})\n")
        return
    if idx_a >= idx_b:
        print(f"\n基线(A={idx_a}) 必须早于目标(B={idx_b})\n")
        return

    path_a = snapshots[idx_a]
    path_b = snapshots[idx_b]
    print(f"\n对比: [{idx_a}] vs [{idx_b}]")
    print(f"  基线: {path_a}")
    print(f"  目标: {path_b}")

    diff = tracker.compare(path_a, path_b)
    tracker.print_report(diff)

    # Also dump raw JSON for piping
    import json
    json_path = path_b.replace(".json", "_delta.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(diff, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n原始数据已保存: {json_path}")


if __name__ == "__main__":
    main()
