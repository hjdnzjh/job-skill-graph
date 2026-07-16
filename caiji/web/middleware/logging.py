"""Request-logging ASGI middleware with async MySQL batch-write buffer."""

import logging
import queue
import threading
import time
import uuid
from datetime import datetime

import pymysql
from fastapi import Request

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared buffer state — initialized once via init_log_buffer()
# ---------------------------------------------------------------------------
_log_queue: queue.Queue = queue.Queue()
_flush_thread: threading.Thread | None = None
_stop_event: threading.Event = threading.Event()
_mysql_conn_kwargs: dict = {}
_buffer_ready = False

FLUSH_BATCH_SIZE = 50
FLUSH_INTERVAL_SEC = 5

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS api_request_logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    request_id VARCHAR(36) NOT NULL,
    timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    method VARCHAR(10) NOT NULL,
    path VARCHAR(256) NOT NULL,
    status_code INT NOT NULL,
    duration_ms FLOAT NOT NULL,
    client_ip VARCHAR(45) NOT NULL,
    INDEX idx_timestamp (timestamp),
    INDEX idx_path (path),
    INDEX idx_status_code (status_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""


def _get_mysql_connection():
    """Create a fresh pymysql connection from stored kwargs."""
    return pymysql.connect(
        **_mysql_conn_kwargs,
        charset="utf8mb4",
    )


def _ensure_table(conn):
    """Create the api_request_logs table if it doesn't exist."""
    with conn.cursor() as cur:
        cur.execute(CREATE_TABLE_SQL)
    conn.commit()


def _flush_loop():
    """Background-thread loop: drain the queue and batch-INSERT to MySQL."""
    logger.info("Log flush thread started")

    batch: list[tuple] = []
    last_flush = time.time()

    while not _stop_event.is_set():
        try:
            # Block up to FLUSH_INTERVAL_SEC for the next item
            item = _log_queue.get(timeout=1.0)
            batch.append(item)
        except queue.Empty:
            pass  # timeout just lets us check _stop_event

        now = time.time()
        should_flush = (len(batch) >= FLUSH_BATCH_SIZE) or (
            batch and (now - last_flush) >= FLUSH_INTERVAL_SEC
        )

        if should_flush:
            _flush_batch(batch)
            batch.clear()
            last_flush = time.time()

    # Final flush on shutdown
    if batch:
        _flush_batch(batch)
        batch.clear()

    logger.info("Log flush thread stopped")


def _flush_batch(batch: list[tuple]):
    """INSERT a batch of rows into api_request_logs."""
    if not batch:
        return
    sql = (
        "INSERT INTO api_request_logs "
        "(request_id, timestamp, method, path, status_code, duration_ms, client_ip) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s)"
    )
    try:
        conn = _get_mysql_connection()
        try:
            _ensure_table(conn)
            with conn.cursor() as cur:
                cur.executemany(sql, batch)
            conn.commit()
            logger.debug(f"Flushed {len(batch)} log entries to MySQL")
        finally:
            conn.close()
    except Exception:
        logger.exception(f"Failed to flush {len(batch)} log entries")


def init_log_buffer(settings):
    """Start the background flush thread. Call once during app startup.

    Requires a ``settings`` object with mysql_host, mysql_port, mysql_user,
    mysql_password, mysql_database attributes.
    """
    global _mysql_conn_kwargs, _buffer_ready, _flush_thread, _stop_event

    if _buffer_ready:
        return

    _mysql_conn_kwargs = {
        "host": settings.mysql_host,
        "port": settings.mysql_port,
        "user": settings.mysql_user,
        "password": settings.mysql_password,
        "database": settings.mysql_database,
    }

    _stop_event.clear()

    # Verify connectivity and create table before starting thread
    try:
        conn = _get_mysql_connection()
        try:
            _ensure_table(conn)
            logger.info("api_request_logs table ready")
        finally:
            conn.close()
    except Exception:
        logger.exception("Cannot connect to MySQL for request logging")

    _flush_thread = threading.Thread(target=_flush_loop, daemon=True)
    _flush_thread.start()
    _buffer_ready = True
    logger.info("Request log buffer initialized")


def shutdown_log_buffer():
    """Signal the flush thread to stop and wait for it to drain."""
    global _buffer_ready
    _stop_event.set()
    if _flush_thread is not None:
        _flush_thread.join(timeout=10)
    _buffer_ready = False


# ---------------------------------------------------------------------------
# ASGI middleware factory (to be registered via app.middleware("http"))
# ---------------------------------------------------------------------------
async def request_logging_middleware(request: Request, call_next):
    """Log every HTTP request to the MySQL buffer queue asynchronously."""
    request_id = request.state.request_id if hasattr(request.state, "request_id") else str(uuid.uuid4())
    request.state.request_id = request_id

    start = time.time()

    response = await call_next(request)

    duration_ms = (time.time() - start) * 1000

    # Enqueue log entry (non-blocking — the background thread writes to MySQL)
    if _buffer_ready:
        # Determine client IP (handle proxies)
        client_ip = (
            request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            or request.headers.get("X-Real-IP", "")
            or (request.client.host if request.client else "unknown")
        )
        entry = (
            request_id,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            request.method,
            request.url.path,
            response.status_code,
            round(duration_ms, 3),
            client_ip,
        )
        try:
            _log_queue.put_nowait(entry)
        except queue.Full:
            logger.warning("Log queue full, dropping entry")

    response.headers["X-Request-Id"] = request_id
    return response
