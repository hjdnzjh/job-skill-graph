"""File-based storage for JSON and JSONL output."""

import json
import logging
import os
from datetime import datetime
from typing import List

from config.schema import UnifiedJobSchema

logger = logging.getLogger(__name__)


class FileStorage:
    """Save records to local filesystem in JSONL and JSON formats."""

    def __init__(self, settings):
        self.settings = settings
        os.makedirs(settings.processed_data_dir, exist_ok=True)
        os.makedirs(settings.raw_data_dir, exist_ok=True)

    def save_processed(self, records: List[UnifiedJobSchema], batch_tag: str = "final") -> str:
        """Save records as JSONL (one JSON object per line)."""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = os.path.join(
            self.settings.processed_data_dir, f"jobs_{ts}_{batch_tag}.jsonl"
        )
        with open(filepath, "w", encoding="utf-8") as f:
            for rec in records:
                f.write(json.dumps(rec.to_dict(), ensure_ascii=False) + "\n")
        logger.info(f"Saved {len(records)} records to {filepath}")
        return filepath

    def save_processed_json(self, records: List[UnifiedJobSchema]) -> str:
        """Save records as a single JSON array."""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = os.path.join(
            self.settings.processed_data_dir, f"jobs_{ts}.json"
        )
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump([r.to_dict() for r in records], f, ensure_ascii=False, indent=2)
        logger.info(f"Saved {len(records)} records to {filepath}")
        return filepath
