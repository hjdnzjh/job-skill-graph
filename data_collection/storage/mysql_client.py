"""MySQL client for batch insert/upsert of unified job records."""

import logging
from contextlib import contextmanager
from typing import List

from sqlalchemy import create_engine, inspect
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.orm import sessionmaker, Session

from config.schema import UnifiedJobSchema
from .models import Base, JobRecord

logger = logging.getLogger(__name__)


class MySQLClient:
    """Manages MySQL connections and batch writes."""

    def __init__(self, settings):
        self.settings = settings
        self._engine = None
        self._session_factory = None

    def _get_engine(self):
        if self._engine is None:
            url = (
                f"mysql+pymysql://{self.settings.mysql_user}:{self.settings.mysql_password}"
                f"@{self.settings.mysql_host}:{self.settings.mysql_port}"
                f"/{self.settings.mysql_database}?charset=utf8mb4"
            )
            self._engine = create_engine(url, pool_pre_ping=True, pool_recycle=3600)
            self._session_factory = sessionmaker(bind=self._engine)
        return self._engine

    @contextmanager
    def session(self) -> Session:
        engine = self._get_engine()
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    # ------------------------------------------------------------------
    # Schema management
    # ------------------------------------------------------------------

    def init_db(self):
        """Create all tables if they don't exist."""
        engine = self._get_engine()
        Base.metadata.create_all(engine)
        logger.info("MySQL tables initialized")

    def drop_all(self):
        """Drop all tables (development only)."""
        engine = self._get_engine()
        Base.metadata.drop_all(engine)
        logger.warning("MySQL tables dropped")

    def table_exists(self) -> bool:
        engine = self._get_engine()
        inspector = inspect(engine)
        return "job_records" in inspector.get_table_names()

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def insert_batch(self, records: List[UnifiedJobSchema], batch_size: int = 500) -> int:
        """Insert a batch of records. Uses upsert to handle duplicates."""
        inserted = 0
        orm_objs = [JobRecord.from_schema(r) for r in records]

        with self.session() as session:
            for i in range(0, len(orm_objs), batch_size):
                batch = orm_objs[i : i + batch_size]
                for obj in batch:
                    session.merge(obj)  # merge = upsert
                session.flush()
                inserted += len(batch)

        logger.info(f"MySQL: inserted/updated {inserted} records")
        return inserted

    def query_by_source(self, source_type: str, limit: int = 100) -> List[dict]:
        """Query records by source type."""
        with self.session() as session:
            rows = (
                session.query(JobRecord)
                .filter(JobRecord.source_type == source_type)
                .order_by(JobRecord.crawl_timestamp.desc())
                .limit(limit)
                .all()
            )
            return [self._to_dict(r) for r in rows]

    def query_by_quality(self, min_score: float = 0.6, limit: int = 100) -> List[dict]:
        """Query high-quality records."""
        with self.session() as session:
            rows = (
                session.query(JobRecord)
                .filter(JobRecord.quality_score >= min_score)
                .order_by(JobRecord.quality_score.desc())
                .limit(limit)
                .all()
            )
            return [self._to_dict(r) for r in rows]

    def count(self) -> int:
        with self.session() as session:
            return session.query(JobRecord).count()

    def count_by_source(self) -> dict:
        with self.session() as session:
            from sqlalchemy import func
            rows = (
                session.query(JobRecord.source_type, func.count(JobRecord.record_id))
                .group_by(JobRecord.source_type)
                .all()
            )
            return {source: cnt for source, cnt in rows}

    @staticmethod
    def _to_dict(rec: JobRecord) -> dict:
        return {
            "record_id": rec.record_id,
            "source_type": rec.source_type,
            "source_name": rec.source_name,
            "job_title": rec.job_title,
            "company_name": rec.company_name,
            "industry": rec.industry,
            "location": rec.location,
            "job_description": rec.job_description[:200] + "..." if len(rec.job_description) > 200 else rec.job_description,
            "quality_score": rec.quality_score,
            "quality_grade": rec.quality_grade,
            "publish_date": rec.publish_date.isoformat() if rec.publish_date else None,
            "crawl_timestamp": rec.crawl_timestamp.isoformat() if rec.crawl_timestamp else None,
        }
