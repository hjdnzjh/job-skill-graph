"""Global configuration for the multi-source data collection system."""

import os
from dataclasses import dataclass, field
from typing import List


@dataclass
class Settings:
    # --- Crawler ---
    concurrent_requests: int = 16
    download_delay: float = 1.0
    randomize_delay: bool = True
    request_timeout: int = 30
    retry_times: int = 3
    user_agent_pool: List[str] = field(default_factory=lambda: [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    ])

    # --- Proxy ---
    proxy_enabled: bool = False
    proxy_pool: List[str] = field(default_factory=list)

    # --- Playwright ---
    playwright_headless: bool = True
    playwright_timeout: int = 30000

    # --- Storage ---
    mysql_host: str = os.getenv("MYSQL_HOST", "localhost")
    mysql_port: int = int(os.getenv("MYSQL_PORT", "3306"))
    mysql_user: str = os.getenv("MYSQL_USER", "root")
    mysql_password: str = os.getenv("MYSQL_PASSWORD", "")
    mysql_database: str = os.getenv("MYSQL_DATABASE", "job_graph")

    es_hosts: List[str] = field(default_factory=lambda: ["http://localhost:9200"])
    es_index: str = "job_positions"

    raw_data_dir: str = os.getenv("RAW_DATA_DIR", "./data/raw")
    processed_data_dir: str = os.getenv("PROCESSED_DATA_DIR", "./data/processed")

    # --- ETL ---
    dedup_similarity_threshold: float = 0.85
    quality_min_score: float = 0.3
    batch_size: int = 500

    # --- Data sources ---
    enabled_sources: List[str] = field(default_factory=lambda: [
        "recruitment", "enterprise", "policy", "academic"
    ])

    # --- Logging ---
    log_level: str = "INFO"
    log_dir: str = "./logs"
