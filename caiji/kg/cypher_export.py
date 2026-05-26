"""Export entities and relations as Cypher statements for direct Neo4j import.

Usage:
    python -m kg.cypher_export  # generates data/kg_import.cypher
"""

import json
import logging
import os
from datetime import datetime

from kg.entity_extractor import EntityCollection
from kg.relation_extractor import RelationsCollection

logger = logging.getLogger(__name__)


def export_cypher(entities: EntityCollection, relations: RelationsCollection,
                  output_path: str = "data/kg_import.cypher") -> str:
    """Generate a Cypher script file for full graph import.

    Returns the path to the generated file.
    """
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    lines = []

    lines.append("// ============================================================")
    lines.append(f"// Knowledge Graph Import Script")
    lines.append(f"// Generated: {datetime.now().isoformat()}")
    lines.append(f"// ============================================================")
    lines.append("")

    # --- Entity nodes ---
    lines.append("// ----------------------------------------------------------")
    lines.append("// ENTITY NODES")
    lines.append("// ----------------------------------------------------------")
    lines.append("")

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
        entity_dict = getattr(entities, attr)
        if not entity_dict:
            continue
        lines.append(f"// --- {label} ({len(entity_dict)} nodes) ---")
        for name, props in sorted(entity_dict.items()):
            props_str = _format_props(props)
            escaped_name = _escape(name)
            lines.append(
                f"MERGE (n:{label} {{name: \"{escaped_name}\"}}) SET n += {{{props_str}}};"
            )
        lines.append("")

    # --- Job nodes ---
    lines.append("// ----------------------------------------------------------")
    lines.append("// JOB NODES")
    lines.append("// ----------------------------------------------------------")
    lines.append("")

    job_nodes = {}  # rid -> props
    for rel_list in [relations.offers]:
        for r in rel_list:
            rid = r["to_id"]
            props = r.get("to_props", {})
            if rid not in job_nodes:
                job_nodes[rid] = props

    for rid, props in sorted(job_nodes.items()):
        props_str = _format_props(props)
        lines.append(f"CREATE (j:Job {{{props_str}}});")

    lines.append("")

    # --- Relationships ---
    lines.append("// ----------------------------------------------------------")
    lines.append("// RELATIONSHIPS")
    lines.append("// ----------------------------------------------------------")
    lines.append("")

    rel_specs = [
        (relations.offers, "Company", "name", "Job", "record_id", "OFFERS", "from_name", "to_id"),
        (relations.has_title, "Job", "record_id", "JobTitle", "name", "HAS_TITLE", "from_id", "to_name"),
        (relations.requires, "Job", "record_id", "Skill", "name", "REQUIRES", "from_id", "to_name"),
        (relations.prefers, "Job", "record_id", "Skill", "name", "PREFERS", "from_id", "to_name"),
        (relations.located_in, "Job", "record_id", "City", "name", "LOCATED_IN", "from_id", "to_name"),
        (relations.belongs_to, "Job", "record_id", "Industry", "name", "BELONGS_TO", "from_id", "to_name"),
        (relations.requires_education, "Job", "record_id", "Education", "name", "REQUIRES_EDUCATION", "from_id", "to_name"),
        (relations.requires_experience, "Job", "record_id", "Experience", "name", "REQUIRES_EXPERIENCE", "from_id", "to_name"),
    ]

    for triples, from_label, from_key, to_label, to_key, rel_type, fk, tk in rel_specs:
        if not triples:
            continue
        lines.append(f"// --- {rel_type} ({len(triples)} edges) ---")
        for t in triples:
            f_val = _escape(t[fk])
            t_val = _escape(t[tk])
            lines.append(
                f"MATCH (a:{from_label} {{{from_key}: \"{f_val}\"}})"
                f" MATCH (b:{to_label} {{{to_key}: \"{t_val}\"}})"
                f" MERGE (a)-[:{rel_type}]->(b);"
            )
        lines.append("")

    # --- CO_OCCURS_WITH ---
    if relations.co_occurs_with:
        lines.append(f"// --- CO_OCCURS_WITH ({len(relations.co_occurs_with)} edges) ---")
        for t in sorted(relations.co_occurs_with, key=lambda x: -x["weight"]):
            a = _escape(t["from_name"])
            b = _escape(t["to_name"])
            w = t["weight"]
            lines.append(
                f"MATCH (a:Skill {{name: \"{a}\"}})"
                f" MATCH (b:Skill {{name: \"{b}\"}})"
                f" MERGE (a)-[:CO_OCCURS_WITH {{weight: {w}}}]->(b);"
            )
        lines.append("")

    content = "\n".join(lines)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)

    logger.info(f"Exported Cypher script to {output_path} ({len(lines)} lines)")
    return output_path


def export_json(entities: EntityCollection, relations: RelationsCollection,
                output_path: str = "data/kg_graph.json") -> str:
    """Export graph as JSON for use with NetworkX or other tools."""
    data = {
        "nodes": {},
        "edges": [],
        "generated": datetime.now().isoformat(),
    }

    # Entity nodes
    label_map = {
        "job_titles": "JobTitle", "companies": "Company", "skills": "Skill",
        "cities": "City", "industries": "Industry",
        "educations": "Education", "experiences": "Experience",
    }

    for attr, label in label_map.items():
        entity_dict = getattr(entities, attr)
        node_list = []
        for name, props in entity_dict.items():
            node = {"id": f"{label}:{name}", "label": label, **props}
            node_list.append(node)
        data["nodes"][label] = node_list

    # Relationships
    rel_specs = [
        (relations.offers, "OFFERS"),
        (relations.has_title, "HAS_TITLE"),
        (relations.requires, "REQUIRES"),
        (relations.prefers, "PREFERS"),
        (relations.located_in, "LOCATED_IN"),
        (relations.belongs_to, "BELONGS_TO"),
        (relations.requires_education, "REQUIRES_EDUCATION"),
        (relations.requires_experience, "REQUIRES_EXPERIENCE"),
    ]

    for triples, rel_type in rel_specs:
        for t in triples:
            edge = {"type": rel_type}
            if "from_name" in t:
                edge["from"] = t.get("from_name", "")
            else:
                edge["from"] = f"Job:{t.get('from_id', '')}"
            if "to_name" in t:
                edge["to"] = t.get("to_name", "")
            if "to_props" in t:
                edge["to_job"] = True
            data["edges"].append(edge)

    for t in relations.co_occurs_with:
        data["edges"].append({
            "type": "CO_OCCURS_WITH",
            "from": t["from_name"],
            "to": t["to_name"],
            "weight": t["weight"],
        })

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)

    logger.info(f"Exported graph JSON to {output_path}")
    return output_path


def _format_props(props: dict) -> str:
    """Format dict as Cypher properties string."""
    parts = []
    for k, v in props.items():
        if v is None or v == "":
            continue
        if isinstance(v, (int, float)):
            parts.append(f"{k}: {v}")
        else:
            parts.append(f"{k}: \"{_escape(str(v))}\"")
    return ", ".join(parts)


def _escape(s: str) -> str:
    """Escape a string for Cypher."""
    if not isinstance(s, str):
        s = str(s)
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
