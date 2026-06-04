"""Person-job matching engine: skill comparison, gap analysis, learning paths."""

import logging
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class JobMatcher:
    """Match user skills against job requirements in the knowledge graph."""

    def __init__(self, settings):
        self.settings = settings
        self._neo4j = None
        self._skill_graph = None  # NetworkX graph for learning paths

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
    # Job title resolution
    # ------------------------------------------------------------------

    def find_title(self, keyword: str) -> Optional[str]:
        """Find canonical job title matching a keyword.

        Uses fuzzy matching against all JobTitle nodes.
        """
        rows = self.neo4j.run_query(
            "MATCH (t:JobTitle) RETURN t.name AS name ORDER BY name"
        )
        titles = [r["name"] for r in rows]
        if not titles:
            return None

        # Try exact or substring match first
        for t in titles:
            if t == keyword:
                return t
        for t in titles:
            if keyword in t or t in keyword:
                return t

        # Fuzzy match
        best = max(titles, key=lambda t: SequenceMatcher(None, keyword, t).ratio())
        score = SequenceMatcher(None, keyword, best).ratio()
        return best if score >= 0.6 else None

    def list_available_titles(self) -> list:
        """Return all unique job titles in the graph."""
        rows = self.neo4j.run_query(
            "MATCH (t:JobTitle) RETURN t.name AS name, "
            "exists((:Job)-[:HAS_TITLE]->(t)) AS has_jobs "
            "ORDER BY name"
        )
        return [r["name"] for r in rows if r["has_jobs"]]

    # ------------------------------------------------------------------
    # Core matching
    # ------------------------------------------------------------------

    def match(self, user_skills: List[str], target_title: str) -> dict:
        """Match user skills against a target job's requirements.

        Args:
            user_skills: List of skill names the user has.
            target_title: Job title to match against (resolved via find_title).

        Returns:
            Dict with match_score, matched_skills, missing_skills, etc.
        """
        # Get required and preferred skills for the target job
        required = self._get_job_skills(target_title, "REQUIRES")
        preferred = self._get_job_skills(target_title, "PREFERS")

        # Fallback to canonical skills if Neo4j has none
        if not required:
            from kg.skill_extractor import TITLE_TO_SKILLS
            canonical = TITLE_TO_SKILLS.get(target_title, [])
            required = [{"skill": s, "category": "", "demand": 1} for s in canonical]
        if not preferred:
            from kg.skill_extractor import TITLE_TO_SKILLS
            canonical = TITLE_TO_SKILLS.get(target_title, [])
            # Preferred = canonical skills not already in required
            req_names = {r["skill"].lower() for r in required}
            preferred = [{"skill": s, "category": "", "demand": 1}
                        for s in canonical if s.lower() not in req_names]

        user_lower = {s.lower() for s in user_skills}

        # Match required skills
        matched = []
        missing = []
        for skill_info in required:
            name = skill_info["skill"]
            if name.lower() in user_lower:
                matched.append(name)
            else:
                missing.append(name)

        # Match preferred skills
        pref_matched = []
        pref_missing = []
        for skill_info in preferred:
            name = skill_info["skill"]
            if name.lower() in user_lower:
                pref_matched.append(name)
            else:
                pref_missing.append(name)

        # Compute scores
        total_required = len(required)
        score = len(matched) / total_required if total_required > 0 else 1.0

        # Generate learning path for missing skills
        learning = self.learning_path(user_skills, missing + pref_missing)

        return {
            "target_title": target_title,
            "match_score": round(score, 2),
            "matched_skills": matched,
            "missing_skills": missing,
            "preferred_matched": pref_matched,
            "preferred_missing": pref_missing,
            "total_required": total_required,
            "total_preferred": len(preferred),
            "learning_path": learning,
        }

    def recommend_jobs(self, user_skills: List[str], top_n: int = 10) -> list:
        """Recommend the best-matching job titles for a given skill set.

        Uses canonical job titles (from TITLE_TO_SKILLS) plus emerging jobs
        for meaningful recommendations.
        """
        from kg.skill_extractor import TITLE_TO_SKILLS

        # Build priority list: canonical titles + emerging jobs
        titles = list(TITLE_TO_SKILLS.keys())

        # Add emerging jobs from Neo4j
        emerging_rows = self.neo4j.run_query(
            "MATCH (e:EmergingJob) RETURN e.name AS name"
        )
        for r in emerging_rows:
            if r["name"] not in titles:
                titles.append(r["name"])

        scores = []
        for title in titles:
            required = self._get_job_skills(title, "REQUIRES")
            if not required:
                continue
            req_lower = {r["skill"].lower() for r in required}
            user_lower = {s.lower() for s in user_skills}
            intersection = req_lower & user_lower
            score = len(intersection) / len(req_lower)
            scores.append({
                "title": title,
                "match_score": round(score, 2),
                "matched": len(intersection),
                "required": len(req_lower),
            })

        scores.sort(key=lambda x: (-x["match_score"], -x["matched"]))
        return scores[:top_n]

    # ------------------------------------------------------------------
    # Learning path
    # ------------------------------------------------------------------

    def learning_path(self, user_skills: List[str],
                      target_skills: List[str]) -> list:
        """Generate a learning path from current skills to target skills.

        Uses skill co-occurrence graph: for each missing target skill,
        finds a bridge from the closest user skill via BFS.
        """
        if not target_skills:
            return []

        G = self._get_skill_graph()
        if G is None:
            return [{"skill": s, "prerequisites": [], "note": "建议学习"} for s in target_skills]

        user_lower = {s.lower() for s in user_skills}
        steps = []

        for target in target_skills:
            # Find the closest matching node in the graph
            graph_nodes_lower = {n.lower(): n for n in G.nodes()}
            if target.lower() not in graph_nodes_lower:
                steps.append({"skill": target, "prerequisites": [],
                              "note": "图谱中暂无此技能数据"})
                continue

            target_node = graph_nodes_lower[target.lower()]

            # Find closest user skill that exists in the graph
            bridge = None
            path = None
            for us in user_skills:
                if us.lower() in graph_nodes_lower:
                    src_node = graph_nodes_lower[us.lower()]
                    try:
                        import networkx as nx
                        sp = nx.shortest_path(G, source=src_node, target=target_node,
                                              weight=lambda u, v, d: 1.0 / max(d.get("weight", 1), 0.5))
                        if bridge is None or len(sp) < len(path or []):
                            bridge = us
                            path = sp
                    except (ImportError, Exception):
                        pass

            if path and len(path) > 1:
                # Intermediate skills to learn (exclude user skill and target)
                steps.append({
                    "skill": target,
                    "from_skill": bridge,
                    "bridge_skills": path[1:-1],
                    "path_length": len(path) - 1,
                    "note": f"从 {bridge} 出发，需 {len(path)-1} 步到达",
                })
            else:
                steps.append({"skill": target, "prerequisites": [],
                              "note": "未找到学习路径，建议直接学习"})

        # Sort by path length (easier first)
        steps.sort(key=lambda x: (x.get("path_length", 99), x.get("skill", "")))
        return steps

    # ------------------------------------------------------------------
    # Radar scoring
    # ------------------------------------------------------------------

    def radar_score(self, user_skills: List[str], matched_skills: List[str],
                    missing_skills: List[str], total_required: int) -> dict:
        """Compute 5-dimension radar scores for skill visualization.

        Args:
            user_skills: All skills the user has.
            matched_skills: Skills that matched the target job.
            missing_skills: Required skills the user lacks.
            total_required: Total number of required skills.

        Returns:
            Dict with "radar" key containing list of {dimension, score, label}.
        """
        user_lower = {s.lower() for s in user_skills}

        # Dimension 1: 技术深度 — ratio of matched to required
        depth_score = 0
        if total_required > 0:
            depth_score = int(len(matched_skills) / total_required * 100)

        # Dimension 2: 业务理解 — skill category breadth from Neo4j
        cat_rows = self.neo4j.run_query(
            "MATCH (s:Skill) WHERE s.name IN $skills RETURN "
            "DISTINCT s.category AS cat",
            {"skills": list(user_lower)},
        ) if user_skills else []
        known_user_skills = [r["cat"] for r in cat_rows if r.get("cat")]
        breadth_score = min(len(set(known_user_skills)) * 15, 100)

        # Dimension 3: 协作沟通 — collaboration tools presence
        collab_tools = {"git", "jira", "jenkins", "slack", "confluence",
                        "notion", "teams", "agile", "scrum", "ci/cd"}
        collab_found = user_lower & collab_tools
        collab_score = min(len(collab_found) * 25, 100)

        # Dimension 4: 学习能力 — skill diversity + modern skills
        modern_skills = {"python", "docker", "kubernetes", "pytorch",
                         "tensorflow", "react", "vue", "go", "rust"}
        modern_found = user_lower & modern_skills
        learning_score = min(50 + len(modern_found) * 10, 100)

        # Dimension 5: 工具链熟练度 — DevOps/tool coverage
        tool_skills = {"docker", "kubernetes", "git", "jenkins", "maven",
                       "nginx", "linux", "shell", "ansible", "ci/cd"}
        tool_found = user_lower & tool_skills
        tool_score = min(len(tool_found) * 15, 100)

        radar = [
            {"dimension": "技术深度", "score": depth_score,
             "label": "优势领域" if depth_score >= 60 else "需要提升"},
            {"dimension": "业务理解", "score": breadth_score,
             "label": "优势领域" if breadth_score >= 60 else "需要提升"},
            {"dimension": "协作沟通", "score": collab_score,
             "label": "优势领域" if collab_score >= 60 else "需要提升"},
            {"dimension": "学习能力", "score": learning_score,
             "label": "优势领域" if learning_score >= 60 else "需要提升"},
            {"dimension": "工具链熟练度", "score": tool_score,
             "label": "优势领域" if tool_score >= 60 else "需要提升"},
        ]
        return {"radar": radar}

    def gap_suggestions(self, user_skills: List[str], missing_skills: List[str],
                        target_title: str) -> list:
        """Generate actionable suggestions for skill gaps.

        Returns list of dicts with category, suggestion, and related_skills.
        """
        suggestions = []

        if not missing_skills:
            suggestions.append({
                "category": "overall",
                "suggestion": "你的技能已覆盖目标岗位的所有核心要求",
                "related_skills": [],
            })
            return suggestions

        # Group missing skills by category from Neo4j
        cat_rows = self.neo4j.run_query(
            "MATCH (s:Skill) WHERE s.name IN $skills "
            "RETURN s.name AS skill, s.category AS category",
            {"skills": missing_skills},
        ) if missing_skills else []
        cat_map = {}
        for r in cat_rows:
            cat = r.get("category") or "未分类"
            cat_map.setdefault(cat, []).append(r["skill"])

        # Uncategorized missing skills
        categorized = {r["skill"].lower() for r in cat_rows}
        uncategorized = [s for s in missing_skills
                         if s.lower() not in categorized]

        # Generate suggestions per category
        for cat, skills in sorted(cat_map.items()):
            suggestions.append({
                "category": cat,
                "suggestion": f"建议补充 {cat} 方向的技能：{'、'.join(skills)}",
                "related_skills": skills,
            })

        if uncategorized:
            suggestions.append({
                "category": "未分类",
                "suggestion": f"建议学习：{'、'.join(uncategorized)}",
                "related_skills": uncategorized,
            })

        # Add learning resource suggestions
        for ms in missing_skills:
            ms_lower = ms.lower()
            if ms_lower in {"docker", "kubernetes", "k8s", "ci/cd", "jenkins"}:
                suggestions.append({
                    "category": "学习路径推荐",
                    "suggestion": f"「{ms}」可以通过官方文档 + 动手实验快速入门，推荐 Docker/K8s 实战课程",
                    "related_skills": [ms],
                })
                break

        return suggestions

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_job_skills(self, title: str, rel_type: str) -> list:
        """Get skills for a job title via HAS_TITLE → REQUIRES/PREFERS."""
        # Try exact match on JobTitle node
        rows = self.neo4j.run_query(
            f"MATCH (j:Job)-[:HAS_TITLE]->(t:JobTitle {{name: $title}}), "
            f"(j)-[:{rel_type}]->(s:Skill) "
            f"RETURN s.name AS skill, s.category AS category, "
            f"count(*) AS demand ORDER BY demand DESC",
            {"title": title}
        )
        if rows:
            return rows

        # Try EmergingJob node
        rows = self.neo4j.run_query(
            f"MATCH (e:EmergingJob {{name: $title}})-[:{rel_type}]->(s:Skill) "
            f"RETURN s.name AS skill, s.category AS category, "
            f"1 AS demand",
            {"title": title}
        )
        return rows

    def _get_skill_graph(self):
        """Load or return cached NetworkX skill co-occurrence graph."""
        if self._skill_graph is not None:
            return self._skill_graph

        try:
            import networkx as nx
        except ImportError:
            return None

        rows = self.neo4j.run_query(
            "MATCH (a:Skill)-[r:CO_OCCURS_WITH]->(b:Skill) "
            "RETURN a.name AS skill_a, b.name AS skill_b, r.weight AS weight"
        )

        if not rows:
            return None

        G = nx.Graph()
        for r in rows:
            G.add_edge(r["skill_a"], r["skill_b"], weight=r.get("weight", 1))

        self._skill_graph = G
        return G
