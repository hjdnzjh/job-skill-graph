"""Emerging job discovery CLI.

Usage:
    python main_discover.py                 # scan and classify titles
    python main_discover.py --analyze       # scan + LLM analysis of unknown titles
    python main_discover.py --review       # review saved emerging jobs
    python main_discover.py --save         # analyze and save to Neo4j
    python main_discover.py --full         # scan + analyze + save, full pipeline
"""

import argparse
import json
import logging
import sys

from config.settings import Settings
from kg.job_discovery import EmergingJobDetector

logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="新兴岗位发现系统"
    )
    parser.add_argument("--analyze", "-a", action="store_true",
                        help="用 LLM 分析未知岗位标题")
    parser.add_argument("--review", "-r", action="store_true",
                        help="查看已保存的新兴岗位")
    parser.add_argument("--save", "-s", action="store_true",
                        help="将分析结果保存到 Neo4j")
    parser.add_argument("--full", action="store_true",
                        help="完整流程：扫描 + 分析 + 保存")
    parser.add_argument("--limit", type=int, default=30,
                        help="最多分析 N 个未知标题 (默认 30)")
    parser.add_argument("--batch-size", type=int, default=15,
                        help="每批 LLM 调用的标题数 (默认 15)")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    settings = Settings()
    detector = EmergingJobDetector(settings)

    try:
        if args.full:
            _run_full_pipeline(detector, args)
        elif args.review:
            _run_review(detector)
        elif args.save:
            _run_scan_analyze_save(detector, args)
        elif args.analyze:
            _run_scan_analyze(detector, args)
        else:
            _run_scan(detector)

    finally:
        detector.close()


def _run_scan(detector):
    """Scan and classify all titles without LLM."""
    result = detector.scan_titles()
    _print_scan_summary(result)


def _run_scan_analyze(detector, args):
    """Scan + LLM analyze, show results without saving."""
    result = detector.scan_titles()
    _print_scan_summary(result)

    unknown = result["unknown"]
    if not unknown:
        print("\n没有未分类的岗位标题")
        return

    # Sort by job count desc, take top N
    unknown_sorted = sorted(unknown, key=lambda x: -x["cnt"])[:args.limit]
    print(f"\n正在用 LLM 分析 {len(unknown_sorted)} 个未知标题...\n")

    analyzed = detector.analyze_batch(unknown_sorted, batch_size=args.batch_size)
    _print_analysis(analyzed)

    # Save to JSON for inspection
    with open("data/discovered_jobs.json", "w", encoding="utf-8") as f:
        json.dump(analyzed, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n分析结果已保存到 data/discovered_jobs.json")


def _run_scan_analyze_save(detector, args):
    """Scan + analyze + save to Neo4j."""
    result = detector.scan_titles()
    _print_scan_summary(result)

    unknown = result["unknown"]
    if not unknown:
        print("\n没有未分类的岗位标题")
        return

    unknown_sorted = sorted(unknown, key=lambda x: -x["cnt"])[:args.limit]
    print(f"\n正在用 LLM 分析 {len(unknown_sorted)} 个未知标题...")

    analyzed = detector.analyze_batch(unknown_sorted, batch_size=args.batch_size)
    _print_analysis(analyzed)

    detector.save_emerging_jobs(analyzed)
    print(f"\n已保存到 Neo4j")

    # Also save JSON
    with open("data/discovered_jobs.json", "w", encoding="utf-8") as f:
        json.dump(analyzed, f, ensure_ascii=False, indent=2, default=str)


def _run_full_pipeline(detector, args):
    """Full pipeline: scan + analyze + save + review."""
    _run_scan_analyze_save(detector, args)
    print("\n" + "=" * 60)
    _run_review(detector)


def _run_review(detector):
    """Show saved emerging jobs."""
    jobs = detector.list_emerging()
    if not jobs:
        print("\n暂无已保存的新兴岗位")
        return

    print(f"\n已保存 {len(jobs)} 个新兴岗位：\n")
    for i, j in enumerate(jobs, 1):
        print(f"  [{i}] {j['name']}")
        print(f"      置信度: {j.get('confidence', 'N/A')}")
        print(f"      关联岗位数: {j.get('job_count', 0)}")
        resp = j.get("responsibilities", "")
        if resp:
            first_line = resp.strip().split("\n")[0][:80]
            print(f"      职责: {first_line}...")
        print()


def _print_scan_summary(result):
    """Print scan classification summary."""
    stats = result["stats"]
    print("\n" + "=" * 60)
    print("  岗位标题扫描结果")
    print("=" * 60)
    print(f"  总标题数: {stats['total_titles']}")
    print(f"  已知岗位 (精确匹配):  {stats['canonical']}")
    print(f"  已知岗位 (模糊匹配):  {stats['variation']}")
    print(f"  未分类 (潜在新兴):    {stats['unknown']}")
    print(f"  未分类关联岗位总数:    {stats['total_jobs_in_unknown']}")
    print("=" * 60)

    # Show sample of each category
    if result["variation"]:
        print("\n  模糊匹配示例 (→ 匹配到已知岗位):")
        for v in result["variation"][:8]:
            print(f"    {v['cleaned']:<35} → {v['matched_to']} ({v['similarity']})")

    if result["unknown"]:
        print(f"\n  未分类标题 (前 20 / 共 {stats['unknown']}):")
        for u in result["unknown"][:20]:
            print(f"    [{u['cnt']:3d}] {u['cleaned']}")


def _print_analysis(analyzed):
    """Print LLM analysis results by category."""
    emerging = [a for a in analyzed if a.get("category") == "emerging"]
    variations = [a for a in analyzed if a.get("category") == "variation_of_known"]
    generic = [a for a in analyzed if a.get("category") == "generic"]

    print(f"\n  分析结果: {len(emerging)} 新兴 / {len(variations)} 变体 / {len(generic)} 通用")

    if emerging:
        print(f"\n  {'='*50}")
        print(f"  ★ 新兴岗位 ({len(emerging)})")
        print(f"  {'='*50}")
        for e in emerging:
            print(f"\n  【{e.get('normalized_title', '?')}】 (置信度: {e.get('confidence', 0):.0%})")
            print(f"  原标题: {e.get('original_title', '')}")
            print(f"  关联岗位数: {e.get('job_count', 0)}")
            resp = e.get("responsibilities", "")
            if resp:
                print(f"  职责: {resp[:150]}")
            print(f"  必备技能: {', '.join(e.get('required_skills', []))}")
            print(f"  加分技能: {', '.join(e.get('preferred_skills', []))}")
            print(f"  行业: {', '.join(e.get('industries', []))}")

    if variations:
        print(f"\n  已知岗位变体 ({len(variations)}):")
        for v in variations:
            print(f"    {v.get('normalized_title', '')} → {v.get('known_match', '')}")

    if generic:
        print(f"\n  通用/非技术岗位 ({len(generic)}):")
        names = [g.get("normalized_title", "?") for g in generic[:15]]
        print(f"    {', '.join(names)}")


if __name__ == "__main__":
    main()
