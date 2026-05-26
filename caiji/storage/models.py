"""SQLAlchemy ORM model for the unified job record table."""

from datetime import datetime

from sqlalchemy import (
    Column, String, Text, Float, DateTime, JSON, Index,
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class JobRecord(Base):
    """MySQL table for storing unified job records."""

    __tablename__ = "job_records"

    record_id = Column(String(36), primary_key=True, comment="UUID v4")
    source_id = Column(String(255), nullable=False, comment="Original ID from source")
    source_type = Column(String(32), nullable=False, index=True)
    source_name = Column(String(128), nullable=False)
    source_url = Column(String(2048))

    job_title = Column(String(255), nullable=False, index=True)
    job_title_raw = Column(String(255))
    company_name = Column(String(255), nullable=False, index=True)
    company_name_raw = Column(String(255))
    industry = Column(String(128), index=True)
    location = Column(String(64), index=True)
    location_raw = Column(String(128))
    job_description = Column(Text, nullable=False)

    salary_min = Column(Float)
    salary_max = Column(Float)
    experience_required = Column(String(64))
    education_required = Column(String(64))
    job_type = Column(String(32))

    skills_required = Column(JSON, default=list)
    skills_preferred = Column(JSON, default=list)
    abilities = Column(JSON, default=list)

    publish_date = Column(DateTime, index=True)
    crawl_timestamp = Column(DateTime, nullable=False, default=datetime.now, index=True)
    data_format = Column(String(32))

    quality_score = Column(Float, default=0.0, index=True)
    quality_grade = Column(String(2))
    completeness_score = Column(Float, default=0.0)
    freshness_score = Column(Float, default=0.0)
    consistency_score = Column(Float, default=0.0)

    extra = Column(JSON, default=dict)

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
