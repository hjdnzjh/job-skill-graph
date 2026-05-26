"""Knowledge Graph construction pipeline orchestrator.

Reads all records from MySQL, runs entity extraction / alignment / relation
extraction, and imports into Neo4j.

Usage:
    from kg.graph_builder import GraphBuilder
    builder = GraphBuilder(settings)
    stats = builder.build()          # incremental (default)
    stats = builder.build(clear_existing=True)  # full rebuild
"""

import logging
import time
from datetime import datetime
from typing import Dict, Any

from storage.mysql_client import MySQLClient
from kg.skill_extractor import SkillExtractor
from kg.entity_extractor import EntityExtractor, EntityCollection
from kg.entity_aligner import EntityAligner
from kg.relation_extractor import RelationExtractor, RelationsCollection
from kg.neo4j_client import Neo4jClient

logger = logging.getLogger(__name__)


class GraphBuilder:
    """Full KG construction pipeline: MySQL → entities → relations → Neo4j."""

    def __init__(self, settings):
        self.settings = settings
        self.mysql = MySQLClient(settings)
        self.skill_extractor = SkillExtractor()
        self.entity_extractor = EntityExtractor(self.skill_extractor)
        self.entity_aligner = EntityAligner()
        self.relation_extractor = RelationExtractor()
        self.neo4j = Neo4jClient(settings)

    def build(self, clear_existing: bool = False) -> Dict[str, Any]:
        """Run the full KG construction pipeline.

        Args:
            clear_existing: If True, clear the graph before importing.

        Returns:
            Stats dict with node/relationship counts and timing.
        """
        start_time = time.time()
        stats = {}

        # ------------------------------------------------------------------
        # Phase A: Read from MySQL
        # ------------------------------------------------------------------
        logger.info("=" * 60)
        logger.info("PHASE A: Reading records from MySQL")
        logger.info("=" * 60)

        records = self.mysql.query_all(min_quality="C")
        stats["mysql_records"] = len(records)
        logger.info(f"  Read {len(records)} records from MySQL")

        if not records:
            logger.warning("No records found. Aborting.")
            return stats

        # ------------------------------------------------------------------
        # Phase B: Extract entities
        # ------------------------------------------------------------------
        logger.info("=" * 60)
        logger.info("PHASE B: Extracting entities")
        logger.info("=" * 60)

        t0 = time.time()
        entities: EntityCollection = self.entity_extractor.extract_all(records)
        stats["extract_time"] = round(time.time() - t0, 1)
        stats["entity_summary"] = entities.summary()
        logger.info(f"  Extracted {entities.total_entities} entities in {stats['extract_time']}s")
        logger.info(f"  Summary: {stats['entity_summary']}")

        # ------------------------------------------------------------------
        # Phase C: Align entities
        # ------------------------------------------------------------------
        logger.info("=" * 60)
        logger.info("PHASE C: Aligning entities (dedup)")
        logger.info("=" * 60)

        t0 = time.time()
        entities = self.entity_aligner.align(entities)
        stats["align_time"] = round(time.time() - t0, 1)
        stats["aligned_summary"] = entities.summary()
        stats["alias_count"] = len(entities.alias_map)
        logger.info(f"  Aligned in {stats['align_time']}s, {stats['alias_count']} aliases created")
        logger.info(f"  After alignment: {stats['aligned_summary']}")

        # ------------------------------------------------------------------
        # Phase D: Extract relations
        # ------------------------------------------------------------------
        logger.info("=" * 60)
        logger.info("PHASE D: Extracting relationships")
        logger.info("=" * 60)

        t0 = time.time()
        relations: RelationsCollection = self.relation_extractor.extract(records, entities)
        stats["extract_relations_time"] = round(time.time() - t0, 1)
        stats["relation_summary"] = relations.summary()
        logger.info(f"  Extracted {relations.total_relations} relationships in {stats['extract_relations_time']}s")
        logger.info(f"  Summary: {stats['relation_summary']}")

        # ------------------------------------------------------------------
        # Phase E: Import into Neo4j
        # ------------------------------------------------------------------
        logger.info("=" * 60)
        logger.info("PHASE E: Importing into Neo4j")
        logger.info("=" * 60)

        try:
            self.neo4j.init_db()

            if clear_existing:
                self.neo4j.clear_graph()

            t0 = time.time()
            entity_counts = self.neo4j.import_entities(entities)
            stats["neo4j_entity_import_time"] = round(time.time() - t0, 1)
            stats["neo4j_entity_counts"] = entity_counts

            t0 = time.time()
            relation_counts = self.neo4j.import_relations(relations)
            stats["neo4j_relation_import_time"] = round(time.time() - t0, 1)
            stats["neo4j_relation_counts"] = relation_counts

            logger.info(f"  Entities: {entity_counts}")
            logger.info(f"  Relations: {relation_counts}")

        except Exception as exc:
            logger.error(f"Neo4j import failed: {exc}")
            stats["neo4j_error"] = str(exc)
            return stats

        # ------------------------------------------------------------------
        # Phase F: Verify
        # ------------------------------------------------------------------
        logger.info("=" * 60)
        logger.info("PHASE F: Verification")
        logger.info("=" * 60)

        try:
            verification = self.neo4j.verify()
            stats["verification"] = verification

            node_info = verification.get("nodes_by_label", [])
            if node_info:
                logger.info("  Nodes by label:")
                for row in node_info:
                    logger.info(f"    {row['label']}: {row['cnt']}")

            rel_info = verification.get("total_relationships", [])
            if rel_info:
                logger.info(f"  Total relationships: {rel_info[0]['cnt']}")

            top_skills = verification.get("top_skills", [])
            if top_skills:
                logger.info("  Top 5 skills:")
                for s in top_skills[:5]:
                    logger.info(f"    {s['skill']}: {s['demand']}")
        except Exception as exc:
            logger.warning(f"Verification failed: {exc}")
            stats["verification_error"] = str(exc)

        # ------------------------------------------------------------------
        # Summary
        # ------------------------------------------------------------------
        total_time = time.time() - start_time
        stats["total_time"] = round(total_time, 1)
        stats["completed_at"] = datetime.now().isoformat()

        logger.info("=" * 60)
        logger.info(f"GRAPH CONSTRUCTION COMPLETE — {total_time:.1f}s")
        logger.info(f"  Total nodes:   {sum(entity_counts.values()) if 'neo4j_entity_counts' in stats else 'N/A'}")
        logger.info(f"  Total edges:   {sum(relation_counts.values()) if 'neo4j_relation_counts' in stats else 'N/A'}")
        logger.info("=" * 60)

        return stats
