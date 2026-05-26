"""Global configuration for the data collection system."""

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

    # --- MySQL Storage ---
    mysql_host: str = os.getenv("MYSQL_HOST", "localhost")
    mysql_port: int = int(os.getenv("MYSQL_PORT", "3306"))
    mysql_user: str = os.getenv("MYSQL_USER", "root")
    mysql_password: str = os.getenv("MYSQL_PASSWORD", "123456")
    mysql_database: str = os.getenv("MYSQL_DATABASE", "job_graph")

    # --- File Storage ---
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

    # --- LLM (Text-to-Cypher) ---
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_base_url: str = os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1")
    llm_model: str = os.getenv("LLM_MODEL", "deepseek-chat")
    llm_temperature: float = 0.0

    # --- Neo4j Knowledge Graph ---
    neo4j_uri: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user: str = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password: str = os.getenv("NEO4J_PASSWORD", "12345678")
    neo4j_database: str = os.getenv("NEO4J_DATABASE", "neo4j")
