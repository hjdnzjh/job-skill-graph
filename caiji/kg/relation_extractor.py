"""Extract relationship edges from job records and aligned entities."""

import logging
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List

from kg.entity_extractor import EntityCollection

logger = logging.getLogger(__name__)


@dataclass
class RelationsCollection:
    """Container for all relationship triples grouped by type."""
    offers: List[Dict[str, Any]] = field(default_factory=list)
    has_title: List[Dict[str, Any]] = field(default_factory=list)
    requires: List[Dict[str, Any]] = field(default_factory=list)
    prefers: List[Dict[str, Any]] = field(default_factory=list)
    located_in: List[Dict[str, Any]] = field(default_factory=list)
    belongs_to: List[Dict[str, Any]] = field(default_factory=list)
    requires_education: List[Dict[str, Any]] = field(default_factory=list)
    requires_experience: List[Dict[str, Any]] = field(default_factory=list)
    co_occurs_with: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def total_relations(self) -> int:
        return (len(self.offers) + len(self.has_title) + len(self.requires) +
                len(self.prefers) + len(self.located_in) + len(self.belongs_to) +
                len(self.requires_education) + len(self.requires_experience) +
                len(self.co_occurs_with))

    def summary(self) -> Dict[str, int]:
        return {
            "offers": len(self.offers),
            "has_title": len(self.has_title),
            "requires": len(self.requires),
            "prefers": len(self.prefers),
            "located_in": len(self.located_in),
            "belongs_to": len(self.belongs_to),
            "requires_education": len(self.requires_education),
            "requires_experience": len(self.requires_experience),
            "co_occurs_with": len(self.co_occurs_with),
            "total": self.total_relations,
        }


class RelationExtractor:
    """Build all relationship edges from records and aligned entities."""

    def __init__(self):
        self._skill_cooccurrence: Counter = Counter()

    def extract(self, records: List[Any], entities: EntityCollection) -> RelationsCollection:
        """Extract all relationships from the given records.

        Args:
            records: List of JobRecord ORM objects or dicts.
            entities: Aligned EntityCollection with job_entities populated.

        Returns:
            RelationsCollection with all relationship triples.
        """
        relations = RelationsCollection()
        self._skill_cooccurrence.clear()

        for rec in records:
            rid = rec.record_id if hasattr(rec, 'record_id') else rec.get('record_id', '')
            rec_ents = entities.job_entities.get(rid, {})

            if not rec_ents:
                continue

            ts = self._get_timestamp(rec)

            # Job node properties
            job_props = self._build_job_props(rec, rid)

            # Company → OFFERS → Job
            company = rec_ents.get("company")
            if company:
                company = entities.alias_map.get(company, company)
                relations.offers.append({
                    "from_label": "Company", "from_name": company,
                    "to_id": rid, "to_props": job_props,
                    "timestamp": ts,
                })

            # Job → HAS_TITLE → JobTitle
            title = rec_ents.get("job_title")
            if title:
                relations.has_title.append({
                    "from_id": rid,
                    "to_label": "JobTitle", "to_name": title,
                    "timestamp": ts,
                })

            # Job → LOCATED_IN → City
            city = rec_ents.get("city")
            if city:
                city = entities.alias_map.get(city, city)
                relations.located_in.append({
                    "from_id": rid,
                    "to_label": "City", "to_name": city,
                    "timestamp": ts,
                })

            # Job → BELONGS_TO → Industry
            industry = rec_ents.get("industry")
            if industry:
                industry = entities.alias_map.get(industry, industry)
                relations.belongs_to.append({
                    "from_id": rid,
                    "to_label": "Industry", "to_name": industry,
                    "timestamp": ts,
                })

            # Job → REQUIRES → Skill
            skills = rec_ents.get("skills", [])
            for skill in skills:
                skill = entities.alias_map.get(skill, skill)
                relations.requires.append({
                    "from_id": rid,
                    "to_label": "Skill", "to_name": skill,
                    "timestamp": ts,
                })

            # Job → PREFERS → Skill
            preferred = rec_ents.get("preferred_skills", [])
            for skill in preferred:
                skill = entities.alias_map.get(skill, skill)
                relations.prefers.append({
                    "from_id": rid,
                    "to_label": "Skill", "to_name": skill,
                    "timestamp": ts,
                })

            # Job → REQUIRES_EDUCATION → Education
            education = rec_ents.get("education")
            if education:
                relations.requires_education.append({
                    "from_id": rid,
                    "to_label": "Education", "to_name": education,
                    "timestamp": ts,
                })

            # Job → REQUIRES_EXPERIENCE → Experience
            experience = rec_ents.get("experience")
            if experience:
                relations.requires_experience.append({
                    "from_id": rid,
                    "to_label": "Experience", "to_name": experience,
                    "timestamp": ts,
                })

            # Track skill co-occurrence pairs (sorted to ensure (A,B) = (B,A))
            for i, s1 in enumerate(skills):
                for s2 in skills[i + 1:]:
                    pair = tuple(sorted([s1, s2]))
                    self._skill_cooccurrence[pair] += 1

        # Build CO_OCCURS_WITH triples
        for (skill_a, skill_b), weight in self._skill_cooccurrence.items():
            relations.co_occurs_with.append({
                "from_label": "Skill", "from_name": skill_a,
                "to_label": "Skill", "to_name": skill_b,
                "weight": weight,
            })

        logger.info(f"Relation extraction complete: {relations.summary()}")
        return relations

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_timestamp(rec: Any) -> str:
        """Get crawl_timestamp as ISO string."""
        ts = None
        if hasattr(rec, 'crawl_timestamp'):
            ts = rec.crawl_timestamp
        elif isinstance(rec, dict):
            ts = rec.get('crawl_timestamp')
        if ts is None:
            return datetime.now().isoformat()
        if isinstance(ts, datetime):
            return ts.isoformat()
        return str(ts)

    @staticmethod
    def _build_job_props(rec: Any, rid: str) -> Dict[str, Any]:
        """Build property dict for a Job node."""
        props = {"record_id": rid}

        # Job title
        title = rec.job_title if hasattr(rec, 'job_title') else rec.get('job_title', '')
        props["job_title"] = title or ""

        # Salary
        smin = rec.salary_min if hasattr(rec, 'salary_min') else rec.get('salary_min')
        smax = rec.salary_max if hasattr(rec, 'salary_max') else rec.get('salary_max')
        if smin is not None:
            props["salary_min"] = float(smin)
        if smax is not None:
            props["salary_max"] = float(smax)

        # Quality
        qscore = rec.quality_score if hasattr(rec, 'quality_score') else rec.get('quality_score', 0)
        qgrade = rec.quality_grade if hasattr(rec, 'quality_grade') else rec.get('quality_grade', '')
        props["quality_score"] = float(qscore) if qscore else 0.0
        props["quality_grade"] = str(qgrade) if qgrade else ""

        # Source
        sname = rec.source_name if hasattr(rec, 'source_name') else rec.get('source_name', '')
        props["source_name"] = sname or ""

        # Timestamp
        ts = RelationExtractor._get_timestamp(rec)
        props["crawl_timestamp"] = ts

        # Truncated description
        desc = rec.job_description if hasattr(rec, 'job_description') else rec.get('job_description', '')
        if desc:
            props["description_truncated"] = desc[:200]

        return props
