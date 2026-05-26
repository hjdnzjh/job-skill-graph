"""Neo4j graph database client with batch UNWIND import."""

import logging
from typing import Any, Dict, List

from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable

from kg.entity_extractor import EntityCollection
from kg.relation_extractor import RelationsCollection

logger = logging.getLogger(__name__)

# Batch size for UNWIND imports
BATCH_SIZE = 500


class Neo4jClient:
    """Neo4j connection, constraint creation, and batch import."""

    def __init__(self, settings):
        self.settings = settings
        self._driver = None

    def _get_driver(self):
        if self._driver is None:
            self._driver = GraphDatabase.driver(
                self.settings.neo4j_uri,
                auth=(self.settings.neo4j_user, self.settings.neo4j_password),
            )
            # Verify connectivity
            try:
                self._driver.verify_connectivity()
                logger.info(f"Connected to Neo4j at {self.settings.neo4j_uri}")
            except ServiceUnavailable:
                logger.warning(
                    f"Neo4j at {self.settings.neo4j_uri} not available. "
                    "Start Neo4j first (neo4j start or Neo4j Desktop)."
                )
                raise
        return self._driver

    def close(self):
        if self._driver:
            self._driver.close()
            self._driver = None

    # ------------------------------------------------------------------
    # Schema initialization
    # ------------------------------------------------------------------

    def init_db(self):
        """Create uniqueness constraints and indexes."""
        driver = self._get_driver()
        constraints = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:JobTitle) REQUIRE n.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Company) REQUIRE n.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Skill) REQUIRE n.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:City) REQUIRE n.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Industry) REQUIRE n.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Education) REQUIRE n.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Experience) REQUIRE n.name IS UNIQUE",
        ]
        indexes = [
            "CREATE INDEX IF NOT EXISTS FOR (j:Job) ON (j.record_id)",
            "CREATE INDEX IF NOT EXISTS FOR (j:Job) ON (j.crawl_timestamp)",
            "CREATE INDEX IF NOT EXISTS FOR (s:Skill) ON (s.category)",
            "CREATE INDEX IF NOT EXISTS FOR (c:Company) ON (c.industry)",
        ]
        with driver.session(database=self.settings.neo4j_database) as session:
            for stmt in constraints:
                try:
                    session.run(stmt)
                except Exception as exc:
                    logger.debug(f"Constraint skipped: {exc}")
            for stmt in indexes:
                try:
                    session.run(stmt)
                except Exception as exc:
                    logger.debug(f"Index skipped: {exc}")

        logger.info("Neo4j constraints and indexes created")

    # ------------------------------------------------------------------
    # Clear graph
    # ------------------------------------------------------------------

    def clear_graph(self):
        """Remove all nodes and relationships (for rebuild)."""
        driver = self._get_driver()
        with driver.session(database=self.settings.neo4j_database) as session:
            session.run("MATCH (n) DETACH DELETE n")
        logger.info("Graph cleared")

    # ------------------------------------------------------------------
    # Entity import
    # ------------------------------------------------------------------

    def import_entities(self, entities: EntityCollection) -> Dict[str, int]:
        """Import all entity nodes into Neo4j."""
        driver = self._get_driver()
        counts = {}

        label_map = {
            "job_titles": "JobTitle",
            "companies": "Company",
            "skills": "Skill",
            "cities": "City",
            "industries": "Industry",
            "educations": "Education",
            "experiences": "Experience",
        }

        for attr, label in label_map.items():
            entity_dict = getattr(entities, attr)  # {name: {name, ...}}
            if not entity_dict:
                counts[label] = 0
                continue

            # Convert to list of property dicts
            batch = list(entity_dict.values())
            self._import_nodes(driver, label, batch)
            counts[label] = len(batch)
            logger.info(f"  Imported {len(batch)} {label} nodes")

        return counts

    def _import_nodes(self, driver, label: str, batch: List[Dict], key: str = "name"):
        """Import entity nodes using UNWIND + MERGE."""
        # Use execute_write for auto-retry
        with driver.session(database=self.settings.neo4j_database) as session:
            for i in range(0, len(batch), BATCH_SIZE):
                chunk = batch[i:i + BATCH_SIZE]
                session.execute_write(
                    self._unwind_merge_nodes, label, chunk, key
                )

    @staticmethod
    def _unwind_merge_nodes(tx, label: str, batch: List[Dict], key: str):
        props_list = []
        for item in batch:
            # Build properties dict, filtering out None values
            props = {k: v for k, v in item.items() if v is not None and v != ""}
            props_list.append(props)

        safe_label = label.replace("`", "")
        query = f"""
        UNWIND $batch AS row
        MERGE (n:`{safe_label}` {{{key}: row.{key}}})
        SET n += row
        """
        tx.run(query, batch=props_list)

    # ------------------------------------------------------------------
    # Relation import
    # ------------------------------------------------------------------

    def import_relations(self, relations: RelationsCollection) -> Dict[str, int]:
        """Import all relationship edges into Neo4j."""
        driver = self._get_driver()
        counts = {}

        # Map: relationship type → (source_node_details, target_node_details, rel_type)
        # Each entry: list of dicts with from/to matching keys
        # has_to_name=False for relations where "to" is a Job node
        # (Jobs are created on-the-fly via to_props)
        rel_specs = [
            ("offers", "Company", "name", "Job", "record_id", "OFFERS", True, False),
            ("has_title", "Job", "record_id", "JobTitle", "name", "HAS_TITLE", False, True),
            ("requires", "Job", "record_id", "Skill", "name", "REQUIRES", False, True),
            ("prefers", "Job", "record_id", "Skill", "name", "PREFERS", False, True),
            ("located_in", "Job", "record_id", "City", "name", "LOCATED_IN", False, True),
            ("belongs_to", "Job", "record_id", "Industry", "name", "BELONGS_TO", False, True),
            ("requires_education", "Job", "record_id", "Education", "name", "REQUIRES_EDUCATION", False, True),
            ("requires_experience", "Job", "record_id", "Experience", "name", "REQUIRES_EXPERIENCE", False, True),
        ]

        for (attr, from_label, from_key, to_label, to_key,
             rel_type, has_from_name, has_to_name) in rel_specs:
            triples = getattr(relations, attr)
            if not triples:
                counts[rel_type] = 0
                continue

            count = self._import_simple_rels(
                driver, triples, from_label, from_key, to_label, to_key,
                rel_type, has_from_name, has_to_name
            )
            counts[rel_type] = count
            logger.info(f"  Imported {count} {rel_type} relationships")

        # CO_OCCURS_WITH (special case: Skill → Skill, uses weight)
        if relations.co_occurs_with:
            count = self._import_cooccurrence(driver, relations.co_occurs_with)
            counts["CO_OCCURS_WITH"] = count
            logger.info(f"  Imported {count} CO_OCCURS_WITH relationships")
        else:
            counts["CO_OCCURS_WITH"] = 0

        return counts

    def _import_simple_rels(self, driver, triples: List[Dict],
                            from_label: str, from_key: str,
                            to_label: str, to_key: str,
                            rel_type: str, has_from_name: bool, has_to_name: bool) -> int:
        """Import a simple relationship type with UNWIND."""
        total = 0
        with driver.session(database=self.settings.neo4j_database) as session:
            for i in range(0, len(triples), BATCH_SIZE):
                chunk = triples[i:i + BATCH_SIZE]

                # Prepare parameters
                rows = []
                for t in chunk:
                    row = {}
                    if has_from_name:
                        row["from_match"] = t["from_name"]
                    else:
                        row["from_id"] = t["from_id"]
                    if has_to_name:
                        row["to_match"] = t["to_name"]
                    else:
                        row["to_name"] = t.get("to_name", t.get("to_id", ""))

                    # Optional: job properties for first-time creation
                    if "to_props" in t:
                        row["to_props"] = t["to_props"]

                    # Timestamp
                    ts = t.get("timestamp", "")
                    if isinstance(ts, str):
                        row["crawl_timestamp"] = ts
                    else:
                        row["crawl_timestamp"] = str(ts)
                    rows.append(row)

                count = session.execute_write(
                    self._unwind_simple_rel,
                    from_label, from_key, to_label, to_key,
                    rel_type, has_from_name, has_to_name, rows,
                )
                total += count
        return total

    @staticmethod
    def _unwind_simple_rel(tx, from_label: str, from_key: str,
                           to_label: str, to_key: str, rel_type: str,
                           has_from_name: bool, has_to_name: bool,
                           rows: List[Dict]) -> int:
        safe_from = from_label.replace("`", "")
        safe_to = to_label.replace("`", "")
        safe_rel = rel_type.replace("`", "")

        if has_from_name:
            from_clause = f"MATCH (a:`{safe_from}` {{{from_key}: row.from_match}})"
        else:
            from_clause = f"MATCH (a:`{safe_from}` {{{from_key}: row.from_id}})"

        if has_to_name:
            to_clause = f"MATCH (b:`{safe_to}` {{{to_key}: row.to_match}})"
        else:
            if "to_id" in rows[0] if rows else False:
                to_clause = f"MATCH (b:`{safe_to}` {{{to_key}: row.to_id}})"
            else:
                to_clause = (f"MERGE (b:`{safe_to}` {{{to_key}: row.to_name}})\n"
                             f"SET b += row.to_props")

        query = f"""
        UNWIND $batch AS row
        {from_clause}
        {to_clause}
        MERGE (a)-[r:`{safe_rel}`]->(b)
        SET r.crawl_timestamp = coalesce(r.crawl_timestamp, row.crawl_timestamp)
        RETURN count(r) AS cnt
        """
        result = tx.run(query, batch=rows)
        record = result.single()
        return record["cnt"] if record else 0

    # ------------------------------------------------------------------
    # Co-occurrence import
    # ------------------------------------------------------------------

    def _import_cooccurrence(self, driver, triples: List[Dict]) -> int:
        """Import Skill → CO_OCCURS_WITH → Skill edges with weight."""
        total = 0
        with driver.session(database=self.settings.neo4j_database) as session:
            for i in range(0, len(triples), BATCH_SIZE):
                chunk = triples[i:i + BATCH_SIZE]
                rows = [{"skill_a": t["from_name"], "skill_b": t["to_name"],
                         "weight": t["weight"]} for t in chunk]

                count = session.execute_write(self._unwind_cooccur, rows)
                total += count
        return total

    @staticmethod
    def _unwind_cooccur(tx, rows: List[Dict]) -> int:
        query = """
        UNWIND $batch AS row
        MATCH (a:Skill {name: row.skill_a})
        MATCH (b:Skill {name: row.skill_b})
        MERGE (a)-[r:CO_OCCURS_WITH]->(b)
        SET r.weight = row.weight
        RETURN count(r) AS cnt
        """
        result = tx.run(query, batch=rows)
        record = result.single()
        return record["cnt"] if record else 0

    # ------------------------------------------------------------------
    # Public query interface
    # ------------------------------------------------------------------

    def run_query(self, cypher: str, params: dict = None) -> list:
        """Execute a read Cypher query and return results as list of dicts."""
        driver = self._get_driver()
        with driver.session(database=self.settings.neo4j_database) as session:
            result = session.run(cypher, params or {})
            return [dict(r) for r in result]

    # ------------------------------------------------------------------
    # Verification
    # ------------------------------------------------------------------

    def verify(self) -> Dict[str, Any]:
        """Run verification queries and return stats."""
        driver = self._get_driver()
        queries = [
            ("nodes_by_label",
             "MATCH (n) RETURN labels(n)[0] AS label, count(n) AS cnt ORDER BY label"),
            ("total_relationships",
             "MATCH ()-[r]->() RETURN count(r) AS cnt"),
            ("top_skills",
             "MATCH (:Job)-[:REQUIRES]->(s:Skill) RETURN s.name AS skill, count(*) AS demand ORDER BY demand DESC LIMIT 10"),
            ("top_companies",
             "MATCH (c:Company)-[:OFFERS]->(j:Job) RETURN c.name AS company, count(j) AS jobs ORDER BY jobs DESC LIMIT 10"),
            ("top_cooccurrences",
             "MATCH (a:Skill)-[r:CO_OCCURS_WITH]->(b:Skill) WHERE a.name < b.name RETURN a.name AS skill_a, b.name AS skill_b, r.weight AS weight ORDER BY weight DESC LIMIT 10"),
        ]

        result = {}
        with driver.session(database=self.settings.neo4j_database) as session:
            for name, query in queries:
                try:
                    rows = session.run(query)
                    result[name] = [dict(r) for r in rows]
                except Exception as exc:
                    result[name] = {"error": str(exc)}

        return result
