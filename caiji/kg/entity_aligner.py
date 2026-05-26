"""Entity alignment: fuzzy dedup for companies and skills.

Reuses SequenceMatcher pattern from etl/deduplicator.py.
"""

import logging
from difflib import SequenceMatcher

from kg.entity_extractor import EntityCollection

logger = logging.getLogger(__name__)


class EntityAligner:
    """Deduplicate entity nodes via fuzzy string matching."""

    def __init__(self, company_threshold: float = 0.85, skill_threshold: float = 0.80):
        self.company_threshold = company_threshold
        self.skill_threshold = skill_threshold

    def align(self, entities: EntityCollection) -> EntityCollection:
        """Align entities in-place, returning the same collection with dedup applied.

        Builds alias_map for downstream remapping.
        """
        entities.alias_map = {}

        self._align_companies(entities)
        self._align_skills(entities)

        logger.info(f"Entity alignment complete: {entities.summary()}")
        return entities

    # ------------------------------------------------------------------
    # Company alignment
    # ------------------------------------------------------------------

    def _align_companies(self, entities: EntityCollection):
        """Merge near-duplicate company names."""
        names = sorted(entities.companies.keys(), key=lambda n: n[0] if n else "")
        merged = {}
        processed = set()

        for i, name_a in enumerate(names):
            if name_a in processed:
                continue
            canonical = name_a
            group = [name_a]

            # Only compare with nearby entries (same first char, for efficiency)
            start_char = name_a[0] if name_a else ""
            for name_b in names[i + 1:]:
                if name_b[0] != start_char:
                    break
                if name_b in processed:
                    continue
                # Skip if both short and different
                if len(name_a) < 4 and len(name_b) < 4:
                    continue
                ratio = SequenceMatcher(None, name_a.lower(), name_b.lower()).ratio()
                if ratio >= self.company_threshold:
                    group.append(name_b)
                    processed.add(name_b)

            # Pick canonical: prefer longer name (more informative)
            if len(group) > 1:
                canonical = max(group, key=len)
                for name in group:
                    if name != canonical:
                        entities.alias_map[name] = canonical
                        # Merge properties
                        if name in entities.companies:
                            old_props = entities.companies[name]
                            if old_props.get("industry") and not entities.companies.get(canonical, {}).get("industry"):
                                entities.companies[canonical]["industry"] = old_props["industry"]
                            del entities.companies[name]
                logger.debug(f"  Merged companies: {group} → {canonical}")

            merged[canonical] = entities.companies.get(canonical, {"name": canonical})

        entities.companies = merged

    # ------------------------------------------------------------------
    # Skill alignment
    # ------------------------------------------------------------------

    def _align_skills(self, entities: EntityCollection):
        """Normalize skill names via aliases + fuzzy matching."""
        # Step 1: Apply Normalizer.SKILL_ALIASES
        from etl.normalizer import Normalizer
        normalized_skills = {}
        for name, props in entities.skills.items():
            canonical = Normalizer.SKILL_ALIASES.get(name.lower(), name)
            if canonical != name:
                entities.alias_map[name] = canonical
            if canonical in normalized_skills:
                # Merge categories if different
                existing = normalized_skills[canonical]
                if props.get("category") and not existing.get("category"):
                    existing["category"] = props["category"]
            else:
                normalized_skills[canonical] = props.copy()
                normalized_skills[canonical]["name"] = canonical

        # Step 2: Fuzzy matching on remaining skills
        names = sorted(normalized_skills.keys())
        processed = set()
        merged_skills = {}

        for i, name_a in enumerate(names):
            if name_a in processed:
                continue
            canonical = name_a
            group = [name_a]

            for name_b in names[i + 1:]:
                if name_b in processed:
                    continue
                # Only compare skills of similar length
                len_ratio = min(len(name_a), len(name_b)) / max(len(name_a), len(name_b))
                if len_ratio < 0.5:
                    continue
                ratio = SequenceMatcher(None, name_a.lower(), name_b.lower()).ratio()
                if ratio >= self.skill_threshold:
                    group.append(name_b)
                    processed.add(name_b)

            if len(group) > 1:
                canonical = max(group, key=lambda n: len(n) if n.isascii() else 1)
                canonical = max(group, key=len)  # Prefer longer form
                for name in group:
                    if name != canonical:
                        entities.alias_map[name] = canonical
                logger.debug(f"  Merged skills: {group} → {canonical}")

            merged_skills[canonical] = normalized_skills.get(canonical, {"name": canonical})

        entities.skills = merged_skills

        # Step 3: Remap job entity skill lists through alias_map
        for rid, rec_ents in entities.job_entities.items():
            if "skills" in rec_ents:
                rec_ents["skills"] = [
                    entities.alias_map.get(s, s) for s in rec_ents["skills"]
                ]
            if "preferred_skills" in rec_ents:
                rec_ents["preferred_skills"] = [
                    entities.alias_map.get(s, s) for s in rec_ents["preferred_skills"]
                ]
