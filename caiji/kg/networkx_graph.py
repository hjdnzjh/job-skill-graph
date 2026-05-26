"""NetworkX-based knowledge graph builder (zero-install fallback).

Builds an in-memory graph from entities and relations, runs analytics,
and exports results. Works without Neo4j.
"""

import json
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)


class NxJobGraph:
    """In-memory job knowledge graph using NetworkX."""

    def __init__(self, entities, relations):
        import networkx as nx
        self.graph = nx.MultiDiGraph()
        self._entities = entities
        self._relations = relations
        self._build()

    def _build(self):
        G = self.graph
        entities = self._entities

        # Add entity nodes
        label_map = {
            "job_titles": "JobTitle", "companies": "Company", "skills": "Skill",
            "cities": "City", "industries": "Industry",
            "educations": "Education", "experiences": "Experience",
        }

        for attr, label in label_map.items():
            entity_dict = getattr(entities, attr)
            for name, props in entity_dict.items():
                G.add_node(name, label=label, **props)

        # Add edges
        relations = self._relations

        for r in relations.offers:
            G.add_edge(r["from_name"], r["to_id"],
                       type="OFFERS", company=r["from_name"])
        for r in relations.has_title:
            G.add_edge(r["from_id"], r["to_name"], type="HAS_TITLE")
        for r in relations.requires:
            G.add_edge(r["from_id"], r["to_name"], type="REQUIRES")
        for r in relations.located_in:
            G.add_edge(r["from_id"], r["to_name"], type="LOCATED_IN")
        for r in relations.belongs_to:
            G.add_edge(r["from_id"], r["to_name"], type="BELONGS_TO")
        for r in relations.requires_education:
            G.add_edge(r["from_id"], r["to_name"], type="REQUIRES_EDUCATION")
        for r in relations.requires_experience:
            G.add_edge(r["from_id"], r["to_name"], type="REQUIRES_EXPERIENCE")

        # Skill co-occurrence graph (separate, undirected for analytics)
        self.skill_graph = self._build_skill_cooccurrence()

    def _build_skill_cooccurrence(self):
        import networkx as nx
        SG = nx.Graph()
        for r in self._relations.co_occurs_with:
            SG.add_edge(r["from_name"], r["to_name"], weight=r["weight"])
        return SG

    # ------------------------------------------------------------------
    # Analytics
    # ------------------------------------------------------------------

    def top_skills(self, n: int = 20) -> list:
        """Return top N skills by demand (REQUIRES edge count)."""
        entities = self._entities
        skill_demand = {}
        for r in self._relations.requires:
            s = r["to_name"]
            skill_demand[s] = skill_demand.get(s, 0) + 1
        result = []
        for name, count in sorted(skill_demand.items(), key=lambda x: -x[1])[:n]:
            cat = entities.skills.get(name, {}).get("category", "")
            result.append({"skill": name, "demand": count, "category": cat})
        return result

    def top_companies(self, n: int = 20) -> list:
        """Return top N companies by job count."""
        company_jobs = {}
        for r in self._relations.offers:
            c = r["from_name"]
            company_jobs[c] = company_jobs.get(c, 0) + 1
        result = []
        for name, count in sorted(company_jobs.items(), key=lambda x: -x[1])[:n]:
            result.append({"company": name, "jobs": count})
        return result

    def skill_communities(self, n_clusters: int = 5) -> dict:
        """Detect skill communities using Louvain or greedy modularity."""
        import networkx as nx
        from networkx.algorithms.community import greedy_modularity_communities

        SG = self.skill_graph
        communities = list(greedy_modularity_communities(SG, weight="weight"))

        result = {}
        for i, comm in enumerate(communities[:n_clusters]):
            # Sort skills within community by PageRank
            subgraph = SG.subgraph(comm)
            pr = nx.pagerank(subgraph, weight="weight")
            sorted_skills = sorted(pr.items(), key=lambda x: -x[1])[:10]
            result[f"cluster_{i+1}"] = {
                "size": len(comm),
                "top_skills": [{"skill": s, "pagerank": round(pr, 4)}
                              for s, pr in sorted_skills],
            }
        return result

    def city_skill_profile(self, top_n_cities: int = 5) -> list:
        """Skill demand profile per city."""
        entities = self._entities
        # Aggregate skills per city
        city_skills = {}
        for r in self._relations.requires:
            job_id = r["from_id"]
            skill = r["to_name"]
            # Find city for this job
            for loc_r in self._relations.located_in:
                if loc_r["from_id"] == job_id:
                    city = loc_r["to_name"]
                    if city not in city_skills:
                        city_skills[city] = {}
                    city_skills[city][skill] = city_skills[city].get(skill, 0) + 1
                    break

        # Get top cities by job count
        city_job_count = {}
        for r in self._relations.located_in:
            c = r["to_name"]
            city_job_count[c] = city_job_count.get(c, 0) + 1

        top_cities = sorted(city_job_count.items(), key=lambda x: -x[1])[:top_n_cities]

        result = []
        for city, job_count in top_cities:
            skills = city_skills.get(city, {})
            top_skills = sorted(skills.items(), key=lambda x: -x[1])[:10]
            result.append({
                "city": city,
                "job_count": job_count,
                "top_skills": [{"skill": s, "count": c} for s, c in top_skills],
            })
        return result

    def industry_skill_profile(self) -> list:
        """Skill demand profile per industry."""
        entities = self._entities
        ind_skills = {}
        for r in self._relations.requires:
            job_id = r["from_id"]
            skill = r["to_name"]
            for ind_r in self._relations.belongs_to:
                if ind_r["from_id"] == job_id:
                    ind = ind_r["to_name"]
                    if ind not in ind_skills:
                        ind_skills[ind] = {}
                    ind_skills[ind][skill] = ind_skills[ind].get(skill, 0) + 1
                    break

        result = []
        for ind, skills in sorted(ind_skills.items()):
            top_skills = sorted(skills.items(), key=lambda x: -x[1])[:10]
            result.append({
                "industry": ind,
                "total_requirements": sum(skills.values()),
                "top_skills": [{"skill": s, "count": c} for s, c in top_skills],
            })
        return result

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def export_analytics(self, output_path: str = "data/kg_analytics.json") -> str:
        """Run all analytics and export to JSON."""
        analytics = {
            "generated": datetime.now().isoformat(),
            "graph_stats": {
                "nodes": self.graph.number_of_nodes(),
                "edges": self.graph.number_of_edges(),
            },
            "skill_graph_stats": {
                "nodes": self.skill_graph.number_of_nodes(),
                "edges": self.skill_graph.number_of_edges(),
            },
            "top_skills": self.top_skills(20),
            "top_companies": self.top_companies(20),
            "skill_communities": self.skill_communities(5),
            "city_skill_profile": self.city_skill_profile(5),
            "industry_skill_profile": self.industry_skill_profile(),
        }

        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(analytics, f, ensure_ascii=False, indent=2, default=str)

        logger.info(f"Exported analytics to {output_path}")
        return output_path

    def print_summary(self):
        """Print a human-readable summary of graph analytics."""
        print("\n" + "=" * 60)
        print("  KNOWLEDGE GRAPH ANALYTICS")
        print("=" * 60)

        print(f"\n  Graph: {self.graph.number_of_nodes()} nodes, "
              f"{self.graph.number_of_edges()} edges")

        print(f"\n  --- Top 10 Skills by Demand ---")
        for item in self.top_skills(10):
            print(f"  {item['skill']:<25} {item['demand']:>4} jobs  [{item['category']}]")

        print(f"\n  --- Top 10 Companies ---")
        for item in self.top_companies(10):
            print(f"  {item['company']:<30} {item['jobs']} jobs")

        print(f"\n  --- Skill Co-occurrence Graph ---")
        print(f"  {self.skill_graph.number_of_nodes()} skills, "
              f"{self.skill_graph.number_of_edges()} co-occurrence edges")

        print(f"\n  --- Skill Communities ---")
        for name, comm in self.skill_communities(5).items():
            print(f"  {name} ({comm['size']} skills): ", end="")
            print(", ".join(s["skill"] for s in comm["top_skills"][:5]))

        print(f"\n  --- Top 5 City Skill Profiles ---")
        for profile in self.city_skill_profile(5):
            print(f"  {profile['city']} ({profile['job_count']} jobs): ", end="")
            print(", ".join(f"{s['skill']}({s['count']})" for s in profile["top_skills"][:5]))

        print("=" * 60 + "\n")
