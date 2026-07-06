"""Data cleaning: whitespace normalization, HTML tag removal, encoding fix, etc."""

import html
import re
import logging
from typing import List

from config.schema import UnifiedJobSchema

logger = logging.getLogger(__name__)


class DataCleaner:
    """Applies cleaning rules to raw records before they enter the pipeline."""

    # Characters / patterns to remove entirely
    INVALID_CHARS = re.compile(r"[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]")

    # HTML entities left over from scraping
    HTML_ENTITY = re.compile(r"&[a-z]+;|&#\d+;")

    # Excessive whitespace
    MULTI_SPACE = re.compile(r"\s{2,}")
    MULTI_NEWLINE = re.compile(r"\n{3,}")

    @classmethod
    def clean(cls, records: List[UnifiedJobSchema]) -> List[UnifiedJobSchema]:
        """Clean a batch of records. Returns only non-empty, valid records."""
        cleaned = []
        for rec in records:
            try:
                rec = cls._clean_one(rec)
                # Drop records with empty core fields
                if rec.job_title and rec.job_description:
                    cleaned.append(rec)
                else:
                    logger.debug(f"Dropping record {rec.record_id}: empty title or description")
            except Exception as exc:
                logger.warning(f"Cleaning failed for {rec.record_id}: {exc}")
        logger.info(f"Cleaned: {len(records)} → {len(cleaned)} records")
        return cleaned

    @classmethod
    def _clean_one(cls, rec: UnifiedJobSchema) -> UnifiedJobSchema:
        """Apply all cleaning rules to a single record."""
        rec.job_title = cls._clean_text(rec.job_title)
        rec.job_title_raw = cls._clean_text(rec.job_title_raw)
        rec.company_name = cls._clean_text(rec.company_name)
        rec.company_name_raw = cls._clean_text(rec.company_name_raw)
        rec.industry = cls._clean_text(rec.industry)
        rec.location = cls._clean_text(rec.location)
        rec.location_raw = cls._clean_text(rec.location_raw)
        rec.job_description = cls._clean_html(rec.job_description)
        rec.experience_required = cls._clean_text(rec.experience_required or "")
        rec.education_required = cls._clean_text(rec.education_required or "")
        rec.job_type = cls._clean_text(rec.job_type or "")
        rec.skills_required = [cls._clean_text(s) for s in rec.skills_required if s]
        rec.skills_preferred = [cls._clean_text(s) for s in rec.skills_preferred if s]
        rec.abilities = [cls._clean_text(a) for a in rec.abilities if a]
        return rec

    @classmethod
    def _clean_text(cls, text: str) -> str:
        """Normalize whitespace, strip control chars, decode HTML entities."""
        if not text:
            return ""
        text = html.unescape(text)
        text = cls.INVALID_CHARS.sub("", text)
        text = cls.HTML_ENTITY.sub("", text)
        text = cls.MULTI_SPACE.sub(" ", text)
        text = cls.MULTI_NEWLINE.sub("\n\n", text)
        return text.strip()

    @classmethod
    def _clean_html(cls, html_text: str) -> str:
        """Strip HTML tags, leaving only meaningful text content."""
        if not html_text:
            return ""
        # Remove <script>, <style>
        text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html_text, flags=re.DOTALL | re.IGNORECASE)
        # Remove all remaining tags but keep their text
        text = re.sub(r"<[^>]+>", " ", text)
        # Decode common entities
        text = html.unescape(text)
        text = cls.MULTI_SPACE.sub(" ", text)
        return text.strip()
