"""Evolution tracking: snapshot, compare, and report on knowledge graph changes.

Usage:
    tracker = EvolutionTracker(settings)
    tracker.save_snapshot(record_count=1188)
    snapshots = tracker.list_snapshots()
    diff = tracker.compare(snapshots[0], snapshots[-1])
    tracker.print_report(diff)
"""

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

SNAPSHOT_DIR = "data/snapshots"


class EvolutionTracker:
    """Save and compare knowledge graph snapshots for evolution analysis."""

    def __init__(self, settings):
        self.settings = settings
        self._neo4j = None

    @property
    def neo4j(self):
        if self._neo4j is None:
            from kg.neo4j_client import Neo4jClient
            self._neo4j = Neo4jClient(self.settings)
        return self._neo4j

    def close(self):
        if self._neo4j:
            self._neo4j.close()
            self._neo4j = None

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    def save_snapshot(self, record_count: int = 0) -> str:
        """Extract current Neo4j state and save as timestamped JSON file.

        Returns the path to the saved snapshot file.
        """
        os.makedirs(SNAPSHOT_DIR, exist_ok=True)

        snapshot = {
            "timestamp": datetime.now().isoformat(),
            "record_count": record_count,
            "graph": self._snapshot_graph_stats(),
            "top_skills": self._snapshot_top_skills(30),
            "top_companies": self._snapshot_top_companies(20),
            "salary": self._snapshot_salary(),
            "city_distribution": self._snapshot_city_distribution(),
            "industry_distribution": self._snapshot_industry_distribution(),
            "skill_communities": self._snapshot_skill_communities(),
        }

        filename = datetime.now().strftime("%Y-%m-%d_%H%M%S") + ".json"
        filepath = os.path.join(SNAPSHOT_DIR, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, ensure_ascii=False, indent=2, default=str)

        logger.info(f"Snapshot saved: {filepath} ({record_count} records)")
        return filepath

    def list_snapshots(self) -> List[str]:
        """Return sorted list of snapshot file paths (oldest first)."""
        if not os.path.isdir(SNAPSHOT_DIR):
            return []
        files = [os.path.join(SNAPSHOT_DIR, f)
                 for f in os.listdir(SNAPSHOT_DIR)
                 if f.endswith(".json") and f != "snapshot_index.json"]
        return sorted(files)

    def load_snapshot(self, path: str) -> dict:
        """Load a snapshot JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    # ------------------------------------------------------------------
    # Comparison
    # ------------------------------------------------------------------

    def compare(self, path_a: str, path_b: str) -> dict:
        """Compare two snapshots and return a structured diff.

        Args:
            path_a: Path to the OLDER snapshot (baseline).
            path_b: Path to the NEWER snapshot.

        Returns:
            Dict with delta sections for skills, companies, salary, cities, etc.
        """
        snap_a = self.load_snapshot(path_a)
        snap_b = self.load_snapshot(path_b)

        return {
            "baseline": snap_a["timestamp"],
            "current": snap_b["timestamp"],
            "record_delta": snap_b["record_count"] - snap_a["record_count"],
            "graph_delta": self._compare_graph(snap_a["graph"], snap_b["graph"]),
            "skill_changes": self._compare_ranked_list(
                snap_a["top_skills"], snap_b["top_skills"], "skill"
            ),
            "company_changes": self._compare_ranked_list(
                snap_a["top_companies"], snap_b["top_companies"], "company"
            ),
            "salary_delta": self._compare_salary(
                snap_a.get("salary", []), snap_b.get("salary", [])
            ),
            "city_changes": self._compare_ranked_list(
                snap_a.get("city_distribution", []),
                snap_b.get("city_distribution", []),
                "city",
            ),
            "community_changes": self._compare_communities(
                snap_a.get("skill_communities", []),
                snap_b.get("skill_communities", []),
            ),
        }

    def print_report(self, diff: dict):
        """Print a human-readable evolution report."""
        print("\n" + "=" * 60)
        print("  知识图谱演化分析报告")
        print("=" * 60)
        print(f"  基线: {diff['baseline']}")
        print(f"  当前: {diff['current']}")
        print(f"  记录变化: {diff['record_delta']:+d}")

        # Graph overview
        gd = diff["graph_delta"]
        print(f"\n  --- 图谱规模变化 ---")
        print(f"  节点: {gd['nodes_before']} → {gd['nodes_after']} ({gd['nodes_delta']:+d})")
        print(f"  关系: {gd['edges_before']} → {gd['edges_after']} ({gd['edges_delta']:+d})")

        # Skill changes
        sc = diff["skill_changes"]
        print(f"\n  --- 技能需求变化 ---")
        self._print_ranked_changes(sc, "技能")

        # Company changes
        cc = diff["company_changes"]
        print(f"\n  --- 公司招聘变化 ---")
        self._print_ranked_changes(cc, "公司")

        # Salary changes
        sd = diff["salary_delta"]
        if sd:
            print(f"\n  --- 薪资变化 (Top 10) ---")
            for item in sd[:10]:
                arrow = "↑" if item["delta_avg_min"] > 0 else "↓" if item["delta_avg_min"] < 0 else "→"
                print(f"  {arrow} {item['title']}: "
                      f"{item['avg_min_before']:.0f}→{item['avg_min_after']:.0f} (最低), "
                      f"{item['avg_max_before']:.0f}→{item['avg_max_after']:.0f} (最高)")

        # City changes
        city_c = diff["city_changes"]
        print(f"\n  --- 城市岗位变化 ---")
        self._print_ranked_changes(city_c, "城市")

        # Community changes
        comm_c = diff["community_changes"]
        if comm_c:
            print(f"\n  --- 技能社群变化 ---")
            for item in comm_c.get("summary", []):
                print(f"  {item}")

        print("=" * 60)

    def print_timeline(self, snapshots: List[str]):
        """Print a timeline overview of all snapshots."""
        print("\n" + "=" * 60)
        print("  快照时间线")
        print("=" * 60)

        for i, path in enumerate(snapshots):
            snap = self.load_snapshot(path)
            ts = snap["timestamp"]
            records = snap.get("record_count", "?")
            nodes = snap["graph"]["total_nodes"]
            edges = snap["graph"]["total_edges"]
            top_skill = snap["top_skills"][0]["skill"] if snap["top_skills"] else "N/A"
            print(f"\n  [{i+1}] {ts}")
            print(f"      {records} 条记录, {nodes} 节点, {edges} 边")
            print(f"      需求最高技能: {top_skill}")

        # If 2+ snapshots, show delta from first to last
        if len(snapshots) >= 2:
            diff = self.compare(snapshots[0], snapshots[-1])
            print(f"\n  --- 首末对比 ({len(snapshots)-1} 次变化间隔) ---")
            sc = diff["skill_changes"]
            print(f"  新进技能: {', '.join(sc['entered'][:5]) if sc['entered'] else '无'}")
            print(f"  上升最快: {', '.join(f'{r[0]}(+{r[1]})' for r in sc['risers'][:5]) if sc['risers'] else '无'}")

        print("=" * 60 + "\n")

    # ------------------------------------------------------------------
    # Snapshot queries (private)
    # ------------------------------------------------------------------

    def _snapshot_graph_stats(self) -> dict:
        nodes = self.neo4j.run_query(
            "MATCH (n) RETURN labels(n)[0] AS label, count(n) AS cnt ORDER BY label"
        )
        edges = self.neo4j.run_query(
            "MATCH ()-[r]->() RETURN type(r) AS rel, count(r) AS cnt ORDER BY cnt DESC"
        )
        return {
            "total_nodes": sum(r["cnt"] for r in nodes),
            "total_edges": sum(r["cnt"] for r in edges),
            "nodes_by_label": {r["label"]: r["cnt"] for r in nodes},
            "relationships_by_type": {r["rel"]: r["cnt"] for r in edges},
        }

    def _snapshot_top_skills(self, limit: int = 30) -> list:
        rows = self.neo4j.run_query(
            f"MATCH (:Job)-[:REQUIRES]->(s:Skill) "
            f"RETURN s.name AS skill, s.category AS category, count(*) AS demand "
            f"ORDER BY demand DESC LIMIT {limit}"
        )
        for i, r in enumerate(rows):
            r["rank"] = i + 1
        return rows

    def _snapshot_top_companies(self, limit: int = 20) -> list:
        rows = self.neo4j.run_query(
            f"MATCH (c:Company)-[:OFFERS]->(j:Job) "
            f"RETURN c.name AS company, count(j) AS jobs "
            f"ORDER BY jobs DESC LIMIT {limit}"
        )
        for i, r in enumerate(rows):
            r["rank"] = i + 1
        return rows

    def _snapshot_salary(self) -> list:
        return self.neo4j.run_query(
            "MATCH (j:Job)-[:HAS_TITLE]->(t:JobTitle) "
            "RETURN t.name AS title, "
            "avg(j.salary_min) AS avg_min, avg(j.salary_max) AS avg_max, "
            "count(j) AS cnt "
            "ORDER BY cnt DESC"
        )

    def _snapshot_city_distribution(self) -> list:
        rows = self.neo4j.run_query(
            "MATCH (j:Job)-[:LOCATED_IN]->(c:City) "
            "RETURN c.name AS city, count(j) AS jobs "
            "ORDER BY jobs DESC"
        )
        for i, r in enumerate(rows):
            r["rank"] = i + 1
        return rows

    def _snapshot_industry_distribution(self) -> list:
        rows = self.neo4j.run_query(
            "MATCH (j:Job)-[:BELONGS_TO]->(ind:Industry) "
            "RETURN ind.name AS industry, count(j) AS jobs "
            "ORDER BY jobs DESC"
        )
        return rows

    def _snapshot_skill_communities(self) -> list:
        """Detect skill communities via NetworkX Louvain."""
        try:
            import networkx as nx
            from networkx.algorithms.community import greedy_modularity_communities

            # Build skill co-occurrence graph from Neo4j
            rows = self.neo4j.run_query(
                "MATCH (a:Skill)-[r:CO_OCCURS_WITH]->(b:Skill) "
                "RETURN a.name AS skill_a, b.name AS skill_b, r.weight AS weight"
            )
            if not rows:
                return []

            G = nx.Graph()
            for r in rows:
                G.add_edge(r["skill_a"], r["skill_b"], weight=r.get("weight", 1))

            communities = list(greedy_modularity_communities(G, weight="weight"))
            result = []
            for i, comm in enumerate(communities[:8]):
                sub = G.subgraph(comm)
                pr = nx.pagerank(sub, weight="weight")
                top = [s for s, _ in sorted(pr.items(), key=lambda x: -x[1])[:6]]
                result.append({
                    "id": f"cluster_{i+1}",
                    "size": len(comm),
                    "top_skills": top,
                })
            return result
        except ImportError:
            return []

    # ------------------------------------------------------------------
    # Comparison helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compare_graph(ga: dict, gb: dict) -> dict:
        return {
            "nodes_before": ga["total_nodes"],
            "nodes_after": gb["total_nodes"],
            "nodes_delta": gb["total_nodes"] - ga["total_nodes"],
            "edges_before": ga["total_edges"],
            "edges_after": gb["total_edges"],
            "edges_delta": gb["total_edges"] - ga["total_edges"],
        }

    @staticmethod
    def _compare_ranked_list(
        before: list, after: list, name_key: str
    ) -> dict:
        """Diff two ranked lists. Each item must have 'rank' and a name field."""
        before_map = {r[name_key]: r for r in before}
        after_map = {r[name_key]: r for r in after}

        # Demand/value key
        val_key = next(
            (k for k in after[0].keys() if k not in ("rank", name_key, "category", "province")),
            "count",
        ) if after else "count"

        entered = [k for k in after_map if k not in before_map]
        exited = [k for k in before_map if k not in after_map]

        # Entities in both: compute rank change and demand delta
        both = []
        for k in before_map:
            if k in after_map:
                rank_delta = before_map[k]["rank"] - after_map[k]["rank"]
                val_delta = after_map[k][val_key] - before_map[k][val_key]
                both.append((k, rank_delta, val_delta,
                            after_map[k]["rank"], before_map[k]["rank"]))

        risers = sorted(
            [(k, rd, vd) for k, rd, vd, _, _ in both if rd > 0],
            key=lambda x: -x[1]
        )
        fallers = sorted(
            [(k, rd, vd) for k, rd, vd, _, _ in both if rd < 0],
            key=lambda x: x[1]
        )

        return {
            "entered": entered,
            "exited": exited,
            "risers": risers,
            "fallers": fallers,
            "unchanged_count": len(both) - len(risers) - len(fallers),
        }

    @staticmethod
    def _compare_salary(before: list, after: list) -> list:
        """Compute salary deltas per job title."""
        after_map = {r["title"]: r for r in after}
        delta = []
        for r_b in before:
            title = r_b["title"]
            if title in after_map:
                r_a = after_map[title]
                delta.append({
                    "title": title,
                    "avg_min_before": r_b["avg_min"] or 0,
                    "avg_min_after": r_a["avg_min"] or 0,
                    "delta_avg_min": (r_a["avg_min"] or 0) - (r_b["avg_min"] or 0),
                    "avg_max_before": r_b["avg_max"] or 0,
                    "avg_max_after": r_a["avg_max"] or 0,
                    "delta_avg_max": (r_a["avg_max"] or 0) - (r_b["avg_max"] or 0),
                    "count_before": r_b["cnt"],
                    "count_after": r_a["cnt"],
                })
        return sorted(delta, key=lambda x: abs(x["delta_avg_min"]), reverse=True)

    @staticmethod
    def _compare_communities(before: list, after: list) -> dict:
        if not before or not after:
            return {}
        return {
            "clusters_before": len(before),
            "clusters_after": len(after),
            "summary": [
                f"聚类数量: {len(before)} → {len(after)}",
                f"最大聚类大小: {before[0]['size']} → {after[0]['size']}",
            ],
        }

    @staticmethod
    def _print_ranked_changes(changes: dict, label: str):
        """Print ranked-list deltas in readable format."""
        if changes["entered"]:
            print(f"  新入 Top: {', '.join(changes['entered'][:8])}")
        if changes["exited"]:
            print(f"  跌出 Top: {', '.join(changes['exited'][:8])}")
        if changes["risers"]:
            tops = [f"{r[0]}(↑{r[1]})" for r in changes["risers"][:5]]
            print(f"  上升最快: {', '.join(tops)}")
        if changes["fallers"]:
            tops = [f"{r[0]}(↓{abs(r[1])})" for r in changes["fallers"][:5]]
            print(f"  下降最快: {', '.join(tops)}")
        if not any([changes["entered"], changes["exited"],
                    changes["risers"], changes["fallers"]]):
            print(f"  ({label}排名无显著变化)")
