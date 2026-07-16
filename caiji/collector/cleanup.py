"""Data cleanup utilities.

- Snapshots: keep only the most recent N snapshot JSON files.
- Processed files: delete old ``_recruitment_raw.jsonl`` files.
- Request logs: delete old rows from ``api_request_logs`` table.
"""

import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Tuple

logger = logging.getLogger(__name__)

SNAPSHOT_DIR = "data/snapshots"


def _get_project_root() -> Path:
    """Return the project root (parent of the caiji package)."""
    return Path(__file__).resolve().parent.parent.parent


def cleanup_snapshots(keep: int = 30) -> Tuple[int, str]:
    """Delete snapshot JSON files beyond the most recent *keep*.

    Returns (deleted_count, message).
    """
    root = _get_project_root()
    snap_dir = root / SNAPSHOT_DIR
    if not snap_dir.is_dir():
        return 0, f"Snapshots directory not found: {snap_dir}"

    files = sorted(
        [f for f in snap_dir.glob("*.json") if f.name != "snapshot_index.json"],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    deleted = 0
    for fp in files[keep:]:
        try:
            fp.unlink()
            deleted += 1
            logger.info("Cleanup: deleted old snapshot %s", fp.name)
        except OSError as exc:
            logger.warning("Cleanup: failed to delete snapshot %s: %s", fp.name, exc)

    msg = f"Snapshots: kept {min(keep, len(files))}, deleted {deleted}"
    logger.info(msg)
    return deleted, msg


def cleanup_processed_files(days: int = 30) -> Tuple[int, str]:
    """Delete ``_recruitment_raw.jsonl`` files in ``data/processed/``
    that are older than *days*.
    """
    root = _get_project_root()
    processed_dir = root / "data" / "processed"
    if not processed_dir.is_dir():
        return 0, f"Processed directory not found: {processed_dir}"

    cutoff = time.time() - days * 86400
    deleted = 0
    for fp in processed_dir.glob("*_recruitment_raw.jsonl"):
        try:
            if fp.stat().st_mtime < cutoff:
                fp.unlink()
                deleted += 1
                logger.info("Cleanup: deleted old processed file %s", fp.name)
        except OSError as exc:
            logger.warning("Cleanup: failed to delete processed file %s: %s", fp.name, exc)

    msg = f"Processed files: deleted {deleted} files older than {days} days"
    logger.info(msg)
    return deleted, msg


def cleanup_request_logs(days: int = 7) -> Tuple[int, str]:
    """Delete rows from ``api_request_logs`` table older than *days*.

    Returns (deleted_count, message).
    """
    try:
        from sqlalchemy import text
        from storage.mysql_client import MySQLClient
        from config.settings import Settings

        settings = Settings()
        client = MySQLClient(settings)
        engine = client._get_engine()

        cutoff_date = datetime.now() - timedelta(days=days)
        with engine.connect() as conn:
            result = conn.execute(
                text("DELETE FROM api_request_logs WHERE created_at < :cutoff"),
                {"cutoff": cutoff_date},
            )
            conn.commit()
            deleted = result.rowcount

        msg = f"Request logs: deleted {deleted} rows older than {days} days"
        logger.info(msg)
        return deleted, msg

    except Exception as exc:
        msg = f"Request logs cleanup failed: {exc}"
        logger.error(msg)
        return 0, msg


def cleanup_all(
    snapshot_keep: int = 30,
    processed_days: int = 30,
    logs_days: int = 7,
) -> dict:
    """Run all cleanup tasks and return a summary dict."""
    results = {}
    for name, func, args in [
        ("snapshots", cleanup_snapshots, (snapshot_keep,)),
        ("processed", cleanup_processed_files, (processed_days,)),
        ("logs", cleanup_request_logs, (logs_days,)),
    ]:
        try:
            deleted, msg = func(*args)
            results[name] = {"deleted": deleted, "message": msg}
        except Exception as exc:
            results[name] = {"deleted": 0, "message": str(exc)}
            logger.exception("Cleanup %s failed", name)
    return results
