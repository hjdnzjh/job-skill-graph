"""Hallucination checker: verify LLM outputs against knowledge graph facts.

Key mechanisms:
1. Entity verification — check if mentioned skills/jobs/companies exist in Neo4j
2. Numeric fact-checking — verify salary ranges, demand counts against graph
3. Relationship validation — confirm claimed job-skill relations exist
4. Confidence scoring — assign a trust score to each claim

Used by both RAG engine and Text-to-Cypher engine.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Patterns to extract factual claims from LLM outputs
_SKILL_PATTERN = re.compile(
    r'(?:技能|掌握|熟练|了解|会用)[：:\s]*([A-Za-z+#.0-9一-鿿\s、，,]+?)(?:[。；;]|$)'
)
_SALARY_PATTERN = re.compile(
    r'(\d{1,3}[.,]?\d*)\s*[-~至到]\s*(\d{1,3}[.,]?\d*)\s*[Kk千万元]/?(?:月|年|month|year)'
)
_DEMAND_PATTERN = re.compile(
    r'(\d+)\s*(?:个|条|家|项).*?(?:岗位|需求|职位|公司)'
)
_SKILL_NAME_PATTERN = re.compile(
    r'\b(Python|Java|MySQL|Linux|Git|Redis|Docker|Kafka|Spring\s*Boot|Django|'
    r'C\+\+|Go|JavaScript|React|Vue|Spark|Flink|Hadoop|Kubernetes|MongoDB|'
    r'PostgreSQL|TypeScript|Node\.js|TensorFlow|PyTorch|FastAPI|Flask)\b'
)


class HallucinationChecker:
    """Verify LLM-generated claims against the Neo4j knowledge graph."""

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

    def verify(self, text: str) -> dict:
        """Verify all factual claims in an LLM-generated text.

        Returns:
            dict with:
            - overall_score: 0-1 trust score
            - claims: list of {claim, type, verified, evidence, correction}
            - warnings: list of hallucination warnings
        """
        claims = self._extract_claims(text)
        verified_claims = []
        ok = 0
        total = 0

        for claim in claims:
            result = self._verify_claim(claim)
            verified_claims.append(result)
            total += 1
            if result["verified"]:
                ok += 1

        overall = ok / total if total > 0 else 1.0
        warnings = [
            c for c in verified_claims
            if not c["verified"]
        ]

        return {
            "overall_score": round(overall, 2),
            "total_claims": total,
            "verified_claims": ok,
            "claims": verified_claims,
            "warnings": warnings,
            "hallucination_detected": overall < 0.7,
        }

    def check_skill_claim(self, skill_name: str) -> Optional[dict]:
        """Verify if a skill exists in the knowledge graph.

        Returns skill info dict or None if not found.
        """
        rows = self.neo4j.run_query(
            "MATCH (s:Skill) WHERE toLower(s.name) = toLower($name) "
            "MATCH (:Job)-[:REQUIRES]->(s) "
            "RETURN s.name AS name, s.category AS category, count(*) AS demand",
            {"name": skill_name.strip()},
        )
        if rows:
            return rows[0]
        return None

    def check_job_skill_relation(self, job_title: str, skill_name: str) -> bool:
        """Verify if a specific job-skill REQUIRES relationship exists."""
        rows = self.neo4j.run_query(
            "MATCH (j:Job)-[:HAS_TITLE]->(t:JobTitle) WHERE toLower(t.name) = toLower($title) "
            "MATCH (j)-[:REQUIRES]->(s:Skill) WHERE toLower(s.name) = toLower($skill) "
            "RETURN count(*) AS cnt",
            {"title": job_title.strip(), "skill": skill_name.strip()},
        )
        return rows and rows[0]["cnt"] > 0

    def check_salary_range(self, title: str, min_sal: float, max_sal: float) -> dict:
        """Verify if claimed salary range matches graph data.

        Returns {actual_min, actual_max, deviation, reasonable}.
        Tolerance: +/- 30% deviation is considered reasonable.
        """
        rows = self.neo4j.run_query(
            "MATCH (j:Job)-[:HAS_TITLE]->(t:JobTitle) WHERE toLower(t.name) = toLower($title) "
            "RETURN avg(j.salary_min) AS avg_min, avg(j.salary_max) AS avg_max",
            {"title": title.strip()},
        )
        if not rows or rows[0]["avg_min"] is None:
            return {"verified": False, "reason": "图谱中无此岗位的薪资数据"}

        actual_min = float(rows[0]["avg_min"])
        actual_max = float(rows[0]["avg_max"])
        dev_min = abs(min_sal - actual_min) / actual_min if actual_min > 0 else 1
        dev_max = abs(max_sal - actual_max) / actual_max if actual_max > 0 else 1

        return {
            "verified": dev_min <= 0.3 and dev_max <= 0.3,
            "actual_min": round(actual_min),
            "actual_max": round(actual_max),
            "claimed_min": min_sal,
            "claimed_max": max_sal,
            "deviation_min": round(dev_min, 2),
            "deviation_max": round(dev_max, 2),
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _extract_claims(self, text: str) -> list:
        """Extract individual factual claims from text."""
        claims = []

        # Extract skill mentions with demand numbers
        for m in _SKILL_NAME_PATTERN.finditer(text):
            skill = m.group(1)
            # Look for associated demand number nearby
            near = text[max(0, m.start() - 30):m.end() + 80]
            demand_m = _DEMAND_PATTERN.search(near)
            claims.append({
                "type": "skill_demand",
                "skill": skill,
                "claimed_demand": int(demand_m.group(1)) if demand_m else None,
                "full_text": m.group(0),
            })

        # Extract salary claims
        for m in _SALARY_PATTERN.finditer(text):
            claims.append({
                "type": "salary",
                "min_val": float(m.group(1).replace(",", "")),
                "max_val": float(m.group(2).replace(",", "")),
                "full_text": m.group(0),
            })

        return claims

    def _verify_claim(self, claim: dict) -> dict:
        """Verify a single claim against the graph."""
        ctype = claim.get("type", "")

        if ctype == "skill_demand":
            skill_name = claim.get("skill", "")
            graph_info = self.check_skill_claim(skill_name)
            if graph_info:
                actual_demand = graph_info["demand"]
                claimed = claim.get("claimed_demand")
                if claimed:
                    deviation = abs(claimed - actual_demand) / actual_demand
                    verified = deviation <= 0.3
                else:
                    verified = True
                    deviation = 0
                return {
                    "claim": claim["full_text"],
                    "type": "skill_demand",
                    "verified": verified,
                    "evidence": f"图谱中存在技能 {graph_info['name']}，类别 {graph_info['category']}，需求 {actual_demand}",
                    "correction": None if verified else f"实际需求数为 {actual_demand}",
                }
            else:
                return {
                    "claim": claim["full_text"],
                    "type": "skill_demand",
                    "verified": False,
                    "evidence": None,
                    "correction": f"技能 '{skill_name}' 在知识图谱中未找到",
                }

        if ctype == "salary":
            # For salary claims without a specific job title, just check against global range
            rows = self.neo4j.run_query(
                "MATCH (j:Job) WHERE j.salary_min IS NOT NULL "
                "RETURN min(j.salary_min) AS gmin, max(j.salary_max) AS gmax, "
                "avg(j.salary_min) AS amin, avg(j.salary_max) AS amax"
            )
            if rows:
                r = rows[0]
                gmin = float(r["gmin"])
                gmax = float(r["gmax"])
                claimed_min = claim.get("min_val", 0)
                claimed_max = claim.get("max_val", 0)
                # Check if claimed range falls within global bounds (with tolerance)
                reasonable = (claimed_min >= gmin * 0.5 and
                              claimed_max <= gmax * 2.0)
                return {
                    "claim": claim["full_text"],
                    "type": "salary",
                    "verified": reasonable,
                    "evidence": f"图谱全局薪资范围: {int(gmin)}-{int(gmax)}/月",
                    "correction": None if reasonable else f"薪资范围超出正常范围 ({int(gmin)}-{int(gmax)})",
                }

        return {"claim": str(claim), "type": ctype or "unknown",
                "verified": True, "evidence": None, "correction": None}
