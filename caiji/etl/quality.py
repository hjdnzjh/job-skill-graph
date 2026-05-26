"""Data quality scoring system on completeness, freshness, consistency."""

import logging
from datetime import datetime
from typing import List

from config.schema import UnifiedJobSchema, QualityGrade

logger = logging.getLogger(__name__)


class QualityScorer:
    """Compute quality scores for each ingested record."""

    W_COMPLETENESS = 0.40
    W_FRESHNESS = 0.35
    W_CONSISTENCY = 0.25

    FIELD_WEIGHTS = {
        "job_title": 0.20,
        "company_name": 0.15,
        "industry": 0.10,
        "location": 0.10,
        "job_description": 0.20,
        "salary_range": 0.08,
        "experience_required": 0.05,
        "education_required": 0.05,
        "skills_required": 0.05,
        "publish_date": 0.02,
    }

    FRESHNESS_HALF_LIFE_DAYS = 180
    MIN_DESC_LENGTH = 50

    def __init__(self, min_score: float = 0.3):
        self.min_score = min_score

    def score_batch(self, records: List[UnifiedJobSchema]) -> List[UnifiedJobSchema]:
        passed = []
        for rec in records:
            self._score_one(rec)
            if rec.quality_score >= self.min_score:
                passed.append(rec)
            else:
                logger.debug(f"Quality filter: {rec.record_id} score={rec.quality_score:.2f} — rejected")
        logger.info(f"Quality scoring: {len(records)} scored, {len(passed)} passed (min={self.min_score})")
        return passed

    def score_one(self, rec: UnifiedJobSchema) -> UnifiedJobSchema:
        self._score_one(rec)
        return rec

    def _score_one(self, rec: UnifiedJobSchema) -> None:
        rec.completeness_score = self._score_completeness(rec)
        rec.freshness_score = self._score_freshness(rec)
        rec.consistency_score = self._score_consistency(rec)
        rec.quality_score = round(
            self.W_COMPLETENESS * rec.completeness_score
            + self.W_FRESHNESS * rec.freshness_score
            + self.W_CONSISTENCY * rec.consistency_score,
            4,
        )
        rec.quality_grade = self._grade(rec.quality_score)

    def _score_completeness(self, rec: UnifiedJobSchema) -> float:
        score = 0.0
        if rec.job_title: score += self.FIELD_WEIGHTS["job_title"]
        if rec.company_name: score += self.FIELD_WEIGHTS["company_name"]
        if rec.industry: score += self.FIELD_WEIGHTS["industry"]
        if rec.location: score += self.FIELD_WEIGHTS["location"]
        if rec.job_description and len(rec.job_description) >= self.MIN_DESC_LENGTH:
            score += self.FIELD_WEIGHTS["job_description"]
        elif rec.job_description:
            score += self.FIELD_WEIGHTS["job_description"] * 0.5
        if rec.salary_min is not None or rec.salary_max is not None:
            score += self.FIELD_WEIGHTS["salary_range"] * 0.6
        if rec.salary_min is not None and rec.salary_max is not None:
            score += self.FIELD_WEIGHTS["salary_range"] * 0.4
        if rec.experience_required: score += self.FIELD_WEIGHTS["experience_required"]
        if rec.education_required: score += self.FIELD_WEIGHTS["education_required"]
        if rec.skills_required: score += self.FIELD_WEIGHTS["skills_required"]
        if rec.publish_date: score += self.FIELD_WEIGHTS["publish_date"]
        return round(min(score, 1.0), 4)

    def _score_freshness(self, rec: UnifiedJobSchema) -> float:
        if not rec.publish_date:
            return 0.5
        age_days = (datetime.now() - rec.publish_date).total_seconds() / 86400.0
        if age_days < 0:
            return 0.3
        decay = 2.0 ** (-age_days / self.FRESHNESS_HALF_LIFE_DAYS)
        return round(min(decay, 1.0), 4)

    def _score_consistency(self, rec: UnifiedJobSchema) -> float:
        score = 1.0
        if rec.salary_min is not None and rec.salary_max is not None and rec.salary_min > rec.salary_max:
            score -= 0.2
        if rec.salary_max is not None and rec.salary_max > 200:
            score -= 0.1
        if rec.salary_min is not None and rec.salary_min < 0:
            score -= 0.5
        if rec.job_title and rec.skills_required:
            title_lower = rec.job_title.lower()
            skills_text = " ".join(rec.skills_required).lower()
            title_keywords = set(title_lower.split())
            skill_keywords = set(skills_text.split())
            if title_keywords and skill_keywords:
                overlap = title_keywords & skill_keywords
                if not overlap and len(title_keywords) > 1:
                    score -= 0.05
        if rec.job_type and "实习" in rec.job_type:
            if rec.salary_max is not None and rec.salary_max > 20:
                score -= 0.1
        if rec.salary_max is not None and rec.experience_required:
            if "应届" in rec.experience_required and rec.salary_max > 40:
                score -= 0.15
        return round(max(score, 0.0), 4)

    @staticmethod
    def _grade(score: float) -> QualityGrade:
        if score >= 0.8: return QualityGrade.A
        elif score >= 0.6: return QualityGrade.B
        elif score >= 0.4: return QualityGrade.C
        else: return QualityGrade.D

    @classmethod
    def summary(cls, records: List[UnifiedJobSchema]) -> dict:
        if not records:
            return {"total": 0}
        grades = [r.quality_grade.value for r in records]
        scores = [r.quality_score for r in records]
        completes = [r.completeness_score for r in records]
        freshness = [r.freshness_score for r in records]
        consistency = [r.consistency_score for r in records]
        return {
            "total": len(records),
            "avg_quality": round(sum(scores) / len(scores), 4),
            "min_quality": round(min(scores), 4),
            "max_quality": round(max(scores), 4),
            "grade_distribution": {g: grades.count(g) for g in "ABCD"},
            "avg_completeness": round(sum(completes) / len(completes), 4),
            "avg_freshness": round(sum(freshness) / len(freshness), 4),
            "avg_consistency": round(sum(consistency) / len(consistency), 4),
        }
