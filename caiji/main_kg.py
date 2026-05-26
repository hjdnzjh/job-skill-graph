"""Standalone Knowledge Graph construction entry point.

Reads all job records from MySQL and builds a Neo4j knowledge graph.

Usage:
    python main_kg.py              # incremental build (MERGE, safe to re-run)
    python main_kg.py --clear      # full rebuild (clears existing graph first)
"""

import argparse
import logging
import sys

from config.settings import Settings
from kg.graph_builder import GraphBuilder

logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Build knowledge graph from job records")
    parser.add_argument("--clear", action="store_true",
                        help="Clear existing graph before import (full rebuild)")
    parser.add_argument("--snapshot", action="store_true",
                        help="Save evolution snapshot after import")
    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    settings = Settings()

    print("\n" + "=" * 60)
    print("  Phase 2: Knowledge Graph Construction")
    print("=" * 60)
    print(f"  Neo4j: {settings.neo4j_uri}")
    print(f"  Database: {settings.neo4j_database}")
    print(f"  Clear existing: {args.clear}")
    print("=" * 60 + "\n")

    builder = GraphBuilder(settings)
    stats = builder.build(clear_existing=args.clear)

    if stats.get("neo4j_error"):
        print(f"\nERROR: {stats['neo4j_error']}")
        print("Make sure Neo4j is running (neo4j start or Neo4j Desktop)")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("  Construction Complete")
    print("=" * 60)
    print(f"  MySQL records:      {stats.get('mysql_records', 'N/A')}")
    print(f"  Extraction time:    {stats.get('extract_time', 'N/A')}s")
    print(f"  Alignment time:     {stats.get('align_time', 'N/A')}s")
    print(f"  Relation time:      {stats.get('extract_relations_time', 'N/A')}s")

    entity_counts = stats.get("neo4j_entity_counts", {})
    print(f"  Entity nodes:       {sum(entity_counts.values())}")
    for label, count in entity_counts.items():
        print(f"    - {label}: {count}")

    relation_counts = stats.get("neo4j_relation_counts", {})
    print(f"  Relationship edges: {sum(relation_counts.values())}")
    for rel_type, count in relation_counts.items():
        print(f"    - {rel_type}: {count}")

    print(f"  Total time:         {stats.get('total_time', 'N/A')}s")
    print("=" * 60)

    # Save evolution snapshot if requested
    if args.snapshot and not stats.get("neo4j_error"):
        from kg.evolution import EvolutionTracker
        tracker = EvolutionTracker(settings)
        path = tracker.save_snapshot(record_count=stats.get("mysql_records", 0))
        print(f"\n  Snapshot saved: {path}")
        tracker.close()

    # Print top skills from verification
    verification = stats.get("verification", {})
    top_skills = verification.get("top_skills", [])
    if top_skills:
        print("\n  Top 10 Most Demanded Skills:")
        for i, s in enumerate(top_skills[:10], 1):
            print(f"    {i:2}. {s['skill']:<30} {s['demand']} jobs")

    top_companies = verification.get("top_companies", [])
    if top_companies:
        print("\n  Top 10 Companies by Job Count:")
        for i, c in enumerate(top_companies[:10], 1):
            print(f"    {i:2}. {c['company']:<30} {c['jobs']} jobs")

    print()


if __name__ == "__main__":
    main()
