"""Unified data schema — the canonical format all sources map into."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any


class DataSourceType(str, Enum):
    RECRUITMENT = "recruitment"       # 招聘平台 (51job, Zhaopin, BOSS, etc.)
    ENTERPRISE = "enterprise"          # 企业官网招聘页
    POLICY = "policy"                  # 政策文件
    ACADEMIC = "academic"              # 学术论文 / 行业报告
    INDUSTRY_REPORT = "industry_report"  # 行业研究报告


class DataFormat(str, Enum):
    STRUCTURED = "structured"           # 表格 / 数据库导出
    SEMI_STRUCTURED = "semi_structured"  # JSON / XML
    UNSTRUCTURED = "unstructured"        # 文本 / PDF


class QualityGrade(str, Enum):
    A = "A"  # ≥ 0.8 — high confidence, complete fields
    B = "B"  # ≥ 0.6 — moderate confidence
    C = "C"  # ≥ 0.4 — usable with caution
    D = "D"  # < 0.4 — rejected by default


# ---------------------------------------------------------------------------
# Core unified schema — every record maps into this
# ---------------------------------------------------------------------------

@dataclass
class UnifiedJobSchema:
    """Canonical job / position record after ETL unification."""

    # --- identifiers ---
    record_id: str                           # UUID, system-generated
    source_id: str                           # original ID from source system
    source_type: DataSourceType              # which source category
    source_name: str                         # concrete source name, e.g. "51job", "boss_zhipin"
    source_url: str                          # original URL

    # --- core job fields ---
    job_title: str                           # normalized job title
    job_title_raw: str                       # original job title text
    company_name: str                        # normalized company name
    company_name_raw: str                    # original company name
    industry: str                            # e.g. 互联网/IT, 金融, 制造业
    location: str                            # normalized location (city level)
    location_raw: str                        # original location text
    job_description: str                     # full JD text (cleaned)

    # --- structured attributes ---
    salary_min: Optional[float] = None       # monthly salary, normalized to K
    salary_max: Optional[float] = None
    experience_required: Optional[str] = None  # e.g. "1-3年"
    education_required: Optional[str] = None   # e.g. "本科"
    job_type: Optional[str] = None           # 全职/兼职/实习

    # --- skill & ability extraction ---
    skills_required: List[str] = field(default_factory=list)
    skills_preferred: List[str] = field(default_factory=list)
    abilities: List[str] = field(default_factory=list)   # e.g. 沟通能力, 逻辑思维

    # --- metadata ---
    publish_date: Optional[datetime] = None
    crawl_timestamp: datetime = field(default_factory=datetime.now)
    data_format: DataFormat = DataFormat.SEMI_STRUCTURED

    # --- quality ---
    quality_score: float = 0.0
    quality_grade: QualityGrade = QualityGrade.D
    completeness_score: float = 0.0          # field fill rate
    freshness_score: float = 0.0             # recency penalty
    consistency_score: float = 0.0           # cross-field coherence

    # --- extensibility ---
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
