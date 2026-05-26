"""MySQL storage client using SQLAlchemy."""

import logging
from typing import List

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config.schema import UnifiedJobSchema

logger = logging.getLogger(__name__)


class MySQLClient:
    """MySQL storage backend for unified job records."""

    def __init__(self, settings):
        self.settings = settings
        self._engine = None
        self._Session = None

    def _get_engine(self):
        if self._engine is None:
            url = (
                f"mysql+pymysql://{self.settings.mysql_user}:{self.settings.mysql_password}"
                f"@{self.settings.mysql_host}:{self.settings.mysql_port}/"
            )
            # Create engine without database first, then create db if needed
            self._engine = create_engine(
                f"mysql+pymysql://{self.settings.mysql_user}:{self.settings.mysql_password}"
                f"@{self.settings.mysql_host}:{self.settings.mysql_port}/{self.settings.mysql_database}"
                f"?charset=utf8mb4",
                pool_size=10,
                pool_recycle=3600,
                echo=False,
            )
            self._Session = sessionmaker(bind=self._engine)
        return self._engine

    def init_db(self):
        """Create all tables."""
        from storage.models import Base
        engine = self._get_engine()
        Base.metadata.create_all(engine)
        logger.info(f"MySQL tables initialized on {self.settings.mysql_database}")

    def insert_batch(self, records: List[UnifiedJobSchema], batch_size: int = 500) -> int:
        """Insert a batch of records into MySQL. Returns count inserted."""
        from storage.models import JobRecord
        engine = self._get_engine()
        Session = sessionmaker(bind=engine)
        session = Session()
        inserted = 0

        try:
            for i in range(0, len(records), batch_size):
                batch = records[i:i + batch_size]
                orm_records = [JobRecord.from_schema(r) for r in batch]
                session.add_all(orm_records)
                session.commit()
                inserted += len(orm_records)
                logger.info(f"MySQL: inserted batch {i // batch_size + 1}, {inserted}/{len(records)}")
        except Exception as exc:
            session.rollback()
            logger.error(f"MySQL insert failed: {exc}")
            raise
        finally:
            session.close()

        return inserted

    def query_all(self, min_quality: str = None) -> list:
        """Query all records, optionally filtering by minimum quality grade.

        Args:
            min_quality: Minimum quality grade ('A', 'B', 'C', 'D'). None = all.
        """
        from storage.models import JobRecord
        engine = self._get_engine()
        Session = sessionmaker(bind=engine)
        session = Session()
        try:
            q = session.query(JobRecord)
            if min_quality:
                # Only filter out grades below threshold
                grades = ['A', 'B', 'C', 'D']
                if min_quality in grades:
                    allowed = grades[:grades.index(min_quality) + 1]
                    q = q.filter(JobRecord.quality_grade.in_(allowed))
            # Filter out records with empty job_title
            q = q.filter(JobRecord.job_title != "")
            return q.all()
        finally:
            session.close()

    def query_recent(self, limit: int = 100):
        """Query most recent records."""
        from storage.models import JobRecord
        engine = self._get_engine()
        Session = sessionmaker(bind=engine)
        session = Session()
        try:
            return session.query(JobRecord).order_by(
                JobRecord.crawl_timestamp.desc()
            ).limit(limit).all()
        finally:
            session.close()
