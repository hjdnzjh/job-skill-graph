"""Dynamic job capability updater: track and report skill requirement changes.

Compares current graph data against:
1. Canonical baseline (TITLE_TO_SKILLS) — detects deviations from standard
2. Evolution snapshots — detects temporal changes across time points

Outputs: new/removed/modified skills with evidence and trend direction.
"""

import json
import logging
import os
import hashlib
from typing import Any, Dict, List, Optional

from kg.skill_extractor import TITLE_TO_SKILLS

logger = logging.getLogger(__name__)


class JobUpdater:
    """Detect and report changes in job skill requirements over time."""

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

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(self, job_title: str) -> dict:
        """Analyze current skill profile vs canonical baseline.

        Returns a comprehensive change report for one job title.
        """
        from kg.skill_extractor import TITLE_TO_SKILLS

        # Get canonical skills (baseline)
        canonical = set(TITLE_TO_SKILLS.get(job_title, []))

        # Get real-world skills from Neo4j (current state)
        current_skills = self._get_current_skills(job_title)
        current_names = {s["skill"] for s in current_skills}

        # Diff: new skills (in graph but not in canonical)
        new_skills = [s for s in current_skills if s["skill"] not in canonical]

        # Diff: removed skills (in canonical but not in graph)
        removed_skills = list(canonical - current_names)

        # Diff: common skills with demand info
        common_skills = [s for s in current_skills if s["skill"] in canonical]

        # Check evolution snapshots for demand trends
        trends = self._get_skill_trends(job_title)

        # Compute update recommendations
        recommendations = self._make_recommendations(
            job_title, new_skills, removed_skills, trends
        )

        return {
            "job_title": job_title,
            "canonical_skills": sorted(canonical),
            "current_skills": current_skills,
            "new_skills": new_skills,
            "removed_skills": removed_skills,
            "common_skills": common_skills,
            "trends": trends,
            "recommendations": recommendations,
            "summary": self._summarize(new_skills, removed_skills, trends),
        }

    def list_updatable_jobs(self) -> list:
        """List job titles that have canonical baselines for comparison."""
        from kg.skill_extractor import TITLE_TO_SKILLS
        titles = list(TITLE_TO_SKILLS.keys())

        # Check which ones exist in Neo4j
        results = []
        for title in titles:
            skills = self._get_current_skills(title)
            if skills:
                results.append({
                    "title": title,
                    "canonical_count": len(TITLE_TO_SKILLS[title]),
                    "current_count": len(skills),
                })
        return sorted(results, key=lambda x: -abs(
            x["current_count"] - x["canonical_count"]
        ))

    def list_all_changes(self, limit: int = 50, offset: int = 0) -> list:
        """Aggregate skill change records across all updatable jobs.

        Returns a flat list of change records (new/removed/modified skills) with
        timestamps and evidence, suitable for the skill management table.

        Supports pagination via offset and limit parameters.

        Note: Dates are deterministically derived from the skill name hash
        for reproducible results. These are demonstration-quality dates.
        """
        records = []
        all_titles = list(TITLE_TO_SKILLS.keys())
        titles = all_titles[offset : offset + limit]

        for title in titles:
            try:
                analysis = self.analyze(title)
            except Exception:
                continue

            # New skills
            for s in analysis.get("new_skills", []):
                day_offset = (hashlib.md5(s["skill"].encode()).digest()[0] % 28) + 1
                records.append({
                    "title": title,
                    "change_type": "add",
                    "skill": s["skill"],
                    "date": f"2026-05-{day_offset:02d}",
                    "source": "招聘热度分析",
                    "evidence": f"该技能在 {s.get('demand', 1)} 个岗位招聘数据中出现",
                    "demand": s.get("demand", 1),
                })

            # Removed skills
            for s in analysis.get("removed_skills", []):
                day_offset = (hashlib.md5(("removed_" + s).encode()).digest()[0] % 28) + 1
                records.append({
                    "title": title,
                    "change_type": "remove",
                    "skill": s,
                    "date": f"2026-04-{day_offset:02d}",
                    "source": "招聘数据比对",
                    "evidence": "标准技能列表中存在，但当前招聘数据中未发现需求",
                    "demand": 0,
                })

            # Modified (demand changed significantly)
            for s in analysis.get("common_skills", []):
                trends = analysis.get("trends", {})
                if s["skill"] in trends:
                    t = trends[s["skill"]]
                    if t.get("direction") in ("up", "down") and abs(t.get("change", 0)) > 10:
                        day_offset = (hashlib.md5(("mod_" + s["skill"]).encode()).digest()[0] % 28) + 1
                        records.append({
                            "title": title,
                            "change_type": "modify",
                            "skill": s["skill"],
                            "date": f"2026-05-{day_offset:02d}",
                            "source": "需求趋势分析",
                            "evidence": f"需求变化: {t.get('old_demand', 0)} → {t.get('current_demand', 0)} ({t.get('direction', 'stable')})",
                            "demand": t.get("current_demand", 0),
                        })

        records.sort(key=lambda x: x["date"], reverse=True)
        return records

    def count_all_changes(self) -> int:
        """Return total count of change records across all jobs.

        This counts all flattened records (one per skill-change), not
        just job titles.  Useful for pagination metadata.

        Note: This iterates all titles and computes the full record set;
        for large datasets a cached count in a store would be preferable.
        """
        total = 0
        for title in TITLE_TO_SKILLS.keys():
            try:
                analysis = self.analyze(title)
            except Exception:
                continue
            total += (
                len(analysis.get("new_skills", []))
                + len(analysis.get("removed_skills", []))
                + len(analysis.get("common_skills", []))
            )
        return total

    def report(self, job_title: str) -> str:
        """Generate a human-readable update report for one job title."""
        data = self.analyze(job_title)
        lines = [
            f"岗位能力动态更新报告: {job_title}",
            "=" * 50,
            f"标准技能数: {len(data['canonical_skills'])}",
            f"当前图谱技能数: {len(data['current_skills'])}",
        ]

        if data["new_skills"]:
            lines.append(f"\n[新增技能] (图谱中有但标准未覆盖):")
            for s in data["new_skills"]:
                trend = ""
                if s["skill"] in data.get("trends", {}):
                    t = data["trends"][s["skill"]]
                    trend = f" (趋势: {t.get('direction', 'stable')}, 需求{t.get('current_demand', '?')})"
                lines.append(f"  + {s['skill']} (需求: {s.get('demand', '?')}){trend}")

        if data["removed_skills"]:
            lines.append(f"\n[可能淘汰的技能] (标准中有但图谱中未见):")
            for s in data["removed_skills"]:
                lines.append(f"  - {s}")

        if data["recommendations"]:
            lines.append(f"\n[更新建议]:")
            for r in data["recommendations"][:5]:
                lines.append(f"  * {r}")

        lines.append(f"\n[总结]: {data.get('summary', '无特别变化')}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _get_current_skills(self, title: str) -> list:
        """Get all skills for a job title from Neo4j with demand counts."""
        rows = self.neo4j.run_query(
            "MATCH (j:Job)-[:HAS_TITLE]->(t:JobTitle {name: $title}), "
            "(j)-[:REQUIRES]->(s:Skill) "
            "RETURN s.name AS skill, s.category AS category, count(*) AS demand "
            "ORDER BY demand DESC",
            {"title": title},
        )
        if not rows:
            # Try emerging jobs
            rows = self.neo4j.run_query(
                "MATCH (e:EmergingJob {name: $title})-[:REQUIRES]->(s:Skill) "
                "RETURN s.name AS skill, s.category AS category, 1 AS demand",
                {"title": title},
            )
        return rows

    def _get_skill_trends(self, title: str) -> dict:
        """Check evolution snapshots for skill demand trends."""
        snapshot_dir = "data/snapshots"
        if not os.path.isdir(snapshot_dir):
            return {}

        files = sorted(os.listdir(snapshot_dir))
        if len(files) < 2:
            return {}

        # Pre-load skill domain mapping from Neo4j
        domain_map = {}
        try:
            domain_rows = self.neo4j.run_query(
                "MATCH (s:Skill)-[:BELONGS_TO_TYPE]->(:SkillType)"
                "-[:BELONGS_TO_GROUP]->(:SkillGroup)"
                "-[:BELONGS_TO_DOMAIN]->(d:SkillDomain) "
                "RETURN s.name AS skill, d.code AS domain_code"
            )
            domain_map = {r["skill"]: r["domain_code"] for r in domain_rows}
        except Exception:
            pass

        trends = {}
        try:
            # Load oldest and newest snapshots
            with open(os.path.join(snapshot_dir, files[0]), encoding="utf-8") as f:
                old_snap = json.load(f)
            with open(os.path.join(snapshot_dir, files[-1]), encoding="utf-8") as f:
                new_snap = json.load(f)

            old_skills = old_snap.get("top_skills", [])
            new_skills = new_snap.get("top_skills", [])

            old_map = {s["skill"]: s for s in old_skills}
            new_map = {s["skill"]: s for s in new_skills}

            all_skills = set(list(old_map.keys()) + list(new_map.keys()))
            for skill in all_skills:
                old_demand = old_map.get(skill, {}).get("demand", 0)
                new_demand = new_map.get(skill, {}).get("demand", 0)
                if old_demand == 0 and new_demand == 0:
                    continue
                direction = "up" if new_demand > old_demand else (
                    "down" if new_demand < old_demand else "stable"
                )
                trends[skill] = {
                    "old_demand": old_demand,
                    "current_demand": new_demand,
                    "change": new_demand - old_demand,
                    "direction": direction,
                    "domain_code": domain_map.get(skill, ""),
                }
        except Exception as e:
            logger.warning(f"Could not load snapshots: {e}")

        return trends

    def _make_recommendations(self, title: str, new_skills: list,
                               removed_skills: list, trends: dict) -> list:
        """Generate update recommendations based on findings."""
        recs = []

        if new_skills:
            top_new = sorted(new_skills, key=lambda x: -x.get("demand", 0))[:5]
            names = [s["skill"] for s in top_new]
            recs.append(f"建议将以下高频新技能加入{title}的标准要求: {', '.join(names)}")

        if removed_skills:
            recs.append(f"以下标准技能在招聘数据中未出现，可能已过时: {', '.join(removed_skills[:5])}")

        up_trends = [(s, t) for s, t in trends.items()
                     if t.get("direction") == "up"]
        if up_trends:
            up_trends.sort(key=lambda x: -x[1].get("change", 0))
            top = [f"{s}(+{t['change']})" for s, t in up_trends[:3]]
            recs.append(f"需求上升技能: {', '.join(top)}")

        down_trends = [(s, t) for s, t in trends.items()
                       if t.get("direction") == "down"]
        if down_trends:
            down_trends.sort(key=lambda x: x[1].get("change", 0))
            top = [f"{s}({t['change']})" for s, t in down_trends[:3]]
            recs.append(f"需求下降技能: {', '.join(top)}")

        return recs

    def _summarize(self, new_skills: list, removed_skills: list, trends: dict) -> str:
        """Generate a one-sentence summary."""
        parts = []
        if new_skills:
            parts.append(f"新增{len(new_skills)}个技能")
        if removed_skills:
            parts.append(f"移除{len(removed_skills)}个技能")
        if trends:
            up = sum(1 for t in trends.values() if t.get("direction") == "up")
            down = sum(1 for t in trends.values() if t.get("direction") == "down")
            if up or down:
                parts.append(f"{up}个技能需求上升，{down}个下降")
        return "；".join(parts) if parts else "无特别变化"
