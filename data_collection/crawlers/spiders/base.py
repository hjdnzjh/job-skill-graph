"""Base spider with shared anti-crawl, retry, and data-extraction logic."""

import hashlib
import json
import logging
import random
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    import requests
except ImportError:
    requests = None

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

from config.schema import UnifiedJobSchema, DataSourceType, DataFormat

logger = logging.getLogger(__name__)


class BaseSpider:
    source_type: DataSourceType
    source_name: str

    def __init__(self, settings):
        self.settings = settings
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": random.choice(settings.user_agent_pool),
            "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        })
        self._request_count = 0

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    def _get(self, url: str, params: dict = None, **kwargs) -> requests.Response:
        self._rate_limit()
        timeout = kwargs.pop("timeout", self.settings.request_timeout)
        resp = self.session.get(url, params=params, timeout=timeout, **kwargs)
        resp.raise_for_status()
        return resp

    def _post(self, url: str, data: dict = None, json_data: dict = None, **kwargs) -> requests.Response:
        self._rate_limit()
        timeout = kwargs.pop("timeout", self.settings.request_timeout)
        resp = self.session.post(url, data=data, json=json_data, timeout=timeout, **kwargs)
        resp.raise_for_status()
        return resp

    def _rate_limit(self):
        delay = self.settings.download_delay
        if self.settings.randomize_delay:
            delay *= random.uniform(0.5, 1.5)
        time.sleep(delay)

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_html(html: str) -> BeautifulSoup:
        return BeautifulSoup(html, "lxml")

    @staticmethod
    def _safe_extract(soup, selector: str, default: str = "") -> str:
        el = soup.select_one(selector)
        return el.get_text(strip=True) if el else default

    # ------------------------------------------------------------------
    # Record builder
    # ------------------------------------------------------------------

    def _make_record(
        self,
        source_id: str,
        source_url: str,
        job_title_raw: str,
        job_title: str,
        company_name_raw: str,
        company_name: str,
        industry: str,
        location_raw: str,
        location: str,
        job_description: str,
        salary_min: Optional[float] = None,
        salary_max: Optional[float] = None,
        experience_required: Optional[str] = None,
        education_required: Optional[str] = None,
        job_type: Optional[str] = None,
        skills_required: Optional[List[str]] = None,
        skills_preferred: Optional[List[str]] = None,
        abilities: Optional[List[str]] = None,
        publish_date: Optional[datetime] = None,
        data_format: DataFormat = DataFormat.SEMI_STRUCTURED,
        extra: Optional[Dict[str, Any]] = None,
    ) -> UnifiedJobSchema:

        return UnifiedJobSchema(
            record_id=str(uuid.uuid4()),
            source_id=source_id,
            source_type=self.source_type,
            source_name=self.source_name,
            source_url=source_url,
            job_title=job_title,
            job_title_raw=job_title_raw,
            company_name=company_name,
            company_name_raw=company_name_raw,
            industry=industry,
            location=location,
            location_raw=location_raw,
            job_description=job_description,
            salary_min=salary_min,
            salary_max=salary_max,
            experience_required=experience_required,
            education_required=education_required,
            job_type=job_type,
            skills_required=skills_required or [],
            skills_preferred=skills_preferred or [],
            abilities=abilities or [],
            publish_date=publish_date,
            crawl_timestamp=datetime.now(),
            data_format=data_format,
            extra=extra or {},
        )

    # ------------------------------------------------------------------
    # Interface — subclasses must implement
    # ------------------------------------------------------------------

    def crawl(self) -> List[UnifiedJobSchema]:
        raise NotImplementedError

    def parse_item(self, raw: Dict[str, Any]) -> UnifiedJobSchema:
        raise NotImplementedError
