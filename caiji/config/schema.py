"""Unified data schema — the canonical format all sources map into."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any


class DataSourceType(str, Enum):
    RECRUITMENT = "recruitment"
    ENTERPRISE = "enterprise"
    POLICY = "policy"
    ACADEMIC = "academic"
    INDUSTRY_REPORT = "industry_report"


class DataFormat(str, Enum):
    STRUCTURED = "structured"
    SEMI_STRUCTURED = "semi_structured"
    UNSTRUCTURED = "unstructured"


class QualityGrade(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"


@dataclass
class UnifiedJobSchema:
    """Canonical job / position record after ETL unification."""

    record_id: str
    source_id: str
    source_type: DataSourceType
    source_name: str
    source_url: str

    job_title: str
    job_title_raw: str
    company_name: str
    company_name_raw: str
    industry: str
    location: str
    location_raw: str
    job_description: str

    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    experience_required: Optional[str] = None
    education_required: Optional[str] = None
    job_type: Optional[str] = None

    skills_required: List[str] = field(default_factory=list)
    skills_preferred: List[str] = field(default_factory=list)
    abilities: List[str] = field(default_factory=list)

    publish_date: Optional[datetime] = None
    crawl_timestamp: datetime = field(default_factory=datetime.now)
    data_format: DataFormat = DataFormat.SEMI_STRUCTURED

    quality_score: float = 0.0
    quality_grade: QualityGrade = QualityGrade.D
    completeness_score: float = 0.0
    freshness_score: float = 0.0
    consistency_score: float = 0.0

    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "source_id": self.source_id,
            "source_type": self.source_type.value,
            "source_name": self.source_name,
            "source_url": self.source_url,
            "job_title": self.job_title,
            "job_title_raw": self.job_title_raw,
            "company_name": self.company_name,
            "company_name_raw": self.company_name_raw,
            "industry": self.industry,
            "location": self.location,
            "location_raw": self.location_raw,
            "job_description": self.job_description,
            "salary_min": self.salary_min,
            "salary_max": self.salary_max,
            "experience_required": self.experience_required,
            "education_required": self.education_required,
            "job_type": self.job_type,
            "skills_required": self.skills_required,
            "skills_preferred": self.skills_preferred,
            "abilities": self.abilities,
            "publish_date": self.publish_date.isoformat() if self.publish_date else None,
            "crawl_timestamp": self.crawl_timestamp.isoformat(),
            "data_format": self.data_format.value,
            "quality_score": self.quality_score,
            "quality_grade": self.quality_grade.value,
            "completeness_score": self.completeness_score,
            "freshness_score": self.freshness_score,
            "consistency_score": self.consistency_score,
            "extra": self.extra,
        }
