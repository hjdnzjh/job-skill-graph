"""SQLAlchemy ORM model for the unified job record table."""

import json
from datetime import datetime

from sqlalchemy import (
    Column, String, Text, Float, DateTime, Integer, JSON, Index, create_engine,
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class JobRecord(Base):
    """MySQL table for storing unified job records."""

    __tablename__ = "job_records"

    # --- primary key ---
    record_id = Column(String(36), primary_key=True, comment="UUID v4")

    # --- source tracking ---
    source_id = Column(String(255), nullable=False, comment="Original ID from source")
    source_type = Column(String(32), nullable=False, index=True, comment="recruitment|enterprise|policy|academic|industry_report")
    source_name = Column(String(128), nullable=False, comment="Concrete source name")
    source_url = Column(String(2048), comment="Original URL")

    # --- core fields ---
    job_title = Column(String(255), nullable=False, index=True, comment="Normalized job title")
    job_title_raw = Column(String(255), comment="Original job title")
    company_name = Column(String(255), nullable=False, index=True, comment="Normalized company")
    company_name_raw = Column(String(255), comment="Original company name")
    industry = Column(String(128), index=True, comment="Industry category")
    location = Column(String(64), index=True, comment="Normalized city")
    location_raw = Column(String(128), comment="Original location text")
    job_description = Column(Text, nullable=False, comment="Cleaned full JD text")

    # --- structured attributes ---
    salary_min = Column(Float, comment="Monthly salary min (K)")
    salary_max = Column(Float, comment="Monthly salary max (K)")
    experience_required = Column(String(64), comment="e.g. 1-3年")
    education_required = Column(String(64), comment="e.g. 本科")
    job_type = Column(String(32), comment="全职/兼职/实习")

    # --- skills & abilities ---
    skills_required = Column(JSON, default=list, comment="Required skills list")
    skills_preferred = Column(JSON, default=list, comment="Preferred skills list")
    abilities = Column(JSON, default=list, comment="Ability dimensions")

    # --- timestamps ---
    publish_date = Column(DateTime, index=True, comment="Original publish date")
    crawl_timestamp = Column(DateTime, nullable=False, default=datetime.now, index=True, comment="When crawled")
    data_format = Column(String(32), comment="structured|semi_structured|unstructured")

    # --- quality scores ---
    quality_score = Column(Float, default=0.0, index=True, comment="Composite quality score [0-1]")
    quality_grade = Column(String(2), comment="Quality grade A/B/C/D")
    completeness_score = Column(Float, default=0.0)
    freshness_score = Column(Float, default=0.0)
    consistency_score = Column(Float, default=0.0)

    # --- extensibility ---
    extra = Column(JSON, default=dict, comment="Extra source-specific data")

    # --- composite indexes ---
    __table_args__ = (
        Index("idx_title_company", "job_title", "company_name"),
        Index("idx_source_type_name", "source_type", "source_name"),
        Index("idx_location_industry", "location", "industry"),
        Index("idx_publish", "publish_date"),
        Index("idx_crawl_time", "crawl_timestamp"),
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"},
    )

    def __repr__(self):
        return f"<JobRecord {self.record_id[:8]} {self.job_title} @ {self.company_name}>"

    @classmethod
    def from_schema(cls, schema) -> "JobRecord":
        """Convert a UnifiedJobSchema dataclass to an ORM instance."""
        return cls(
            record_id=schema.record_id,
            source_id=schema.source_id,
            source_type=schema.source_type.value,
            source_name=schema.source_name,
            source_url=schema.source_url,
            job_title=schema.job_title,
            job_title_raw=schema.job_title_raw,
            company_name=schema.company_name,
            company_name_raw=schema.company_name_raw,
            industry=schema.industry,
            location=schema.location,
            location_raw=schema.location_raw,
            job_description=schema.job_description,
            salary_min=schema.salary_min,
            salary_max=schema.salary_max,
            experience_required=schema.experience_required,
            education_required=schema.education_required,
            job_type=schema.job_type,
            skills_required=schema.skills_required,
            skills_preferred=schema.skills_preferred,
            abilities=schema.abilities,
            publish_date=schema.publish_date,
            crawl_timestamp=schema.crawl_timestamp,
            data_format=schema.data_format.value,
            quality_score=schema.quality_score,
            quality_grade=schema.quality_grade.value,
            completeness_score=schema.completeness_score,
            freshness_score=schema.freshness_score,
            consistency_score=schema.consistency_score,
            extra=schema.extra,
        )
