"""File-system storage for raw documents and JSON snapshots.

Serves as both a cold-storage backup and a development fallback when
MySQL/ES are not available.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from config.schema import UnifiedJobSchema

logger = logging.getLogger(__name__)


class FileStorage:
    """JSON-line file storage with source-organization and date-partitioning."""

    def __init__(self, settings):
        self.settings = settings
        self.raw_dir = Path(settings.raw_data_dir)
        self.processed_dir = Path(settings.processed_data_dir)
        self._ensure_dirs()

    def _ensure_dirs(self):
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Raw document storage (original HTML/JSON/PDF)
    # ------------------------------------------------------------------

    def save_raw(self, source_name: str, content: str, url: str, content_type: str = "html") -> str:
        """Save raw crawled content to disk.

        Returns the file path.
        """
        date_str = datetime.now().strftime("%Y-%m-%d")
        dir_path = self.raw_dir / source_name / date_str
        dir_path.mkdir(parents=True, exist_ok=True)

        # Use URL hash as filename to avoid collisions
        url_hash = hash(url) & 0xFFFFFFFF
        ext = {"html": ".html", "json": ".json", "pdf": ".pdf", "xml": ".xml"}.get(content_type, ".txt")
        filename = f"{url_hash:08x}{ext}"
        filepath = dir_path / filename

        mode = "wb" if content_type == "pdf" else "w"
        encoding = "utf-8" if mode == "w" else None
        with open(filepath, mode, encoding=encoding) as f:
            f.write(content)

        logger.debug(f"Raw saved: {filepath}")
        return str(filepath)

    def save_raw_binary(self, source_name: str, data: bytes, url: str, content_type: str = "pdf") -> str:
        """Save raw binary content (PDFs, images)."""
        date_str = datetime.now().strftime("%Y-%m-%d")
        dir_path = self.raw_dir / source_name / date_str
        dir_path.mkdir(parents=True, exist_ok=True)

        url_hash = hash(url) & 0xFFFFFFFF
        ext = ".pdf" if content_type == "pdf" else ".bin"
        filename = f"{url_hash:08x}{ext}"
        filepath = dir_path / filename

        with open(filepath, "wb") as f:
            f.write(data)

        logger.debug(f"Raw binary saved: {filepath}")
        return str(filepath)

    # ------------------------------------------------------------------
    # Processed data (JSON Lines)
    # ------------------------------------------------------------------

    def save_processed(self, records: List[UnifiedJobSchema], batch_tag: str = "") -> str:
        """Save processed records as JSON Lines file.

        Returns the file path.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        tag = f"_{batch_tag}" if batch_tag else ""
        filename = f"jobs_{timestamp}{tag}.jsonl"
        filepath = self.processed_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            for rec in records:
                f.write(json.dumps(rec.to_dict(), ensure_ascii=False) + "\n")

        logger.info(f"Processed: {len(records)} records → {filepath}")
        return str(filepath)

    def save_processed_json(self, records: List[UnifiedJobSchema], filename: str = None) -> str:
        """Save processed records as a single JSON array."""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"jobs_{timestamp}.json"

        filepath = self.processed_dir / filename
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(
                [r.to_dict() for r in records],
                f,
                ensure_ascii=False,
                indent=2,
            )

        logger.info(f"Processed JSON: {len(records)} records → {filepath}")
        return str(filepath)

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------

    def load_processed(self, filepath: str = None) -> List[dict]:
        """Load processed records from a JSONL file."""
        if filepath is None:
            # Find the most recent processed file
            files = sorted(self.processed_dir.glob("jobs_*.jsonl"), reverse=True)
            if not files:
                logger.warning("No processed files found")
                return []
            filepath = str(files[0])

        records = []
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))

        logger.info(f"Loaded {len(records)} records from {filepath}")
        return records

    def list_raw_files(self, source_name: str = None) -> List[str]:
        """List all raw files, optionally filtered by source."""
        pattern = f"{source_name}/**/*" if source_name else "**/*"
        files = self.raw_dir.glob(pattern)
        return [str(f) for f in files if f.is_file()]

    def get_storage_stats(self) -> dict:
        """Get storage statistics."""
        raw_files = list(self.raw_dir.glob("**/*"))
        processed_files = list(self.processed_dir.glob("**/*"))

        total_raw_size = sum(f.stat().st_size for f in raw_files if f.is_file())
        total_processed_size = sum(f.stat().st_size for f in processed_files if f.is_file())

        return {
            "raw_files_count": len([f for f in raw_files if f.is_file()]),
            "processed_files_count": len([f for f in processed_files if f.is_file()]),
            "total_raw_size_mb": round(total_raw_size / 1024 / 1024, 2),
            "total_processed_size_mb": round(total_processed_size / 1024 / 1024, 2),
            "raw_dir": str(self.raw_dir),
            "processed_dir": str(self.processed_dir),
        }
