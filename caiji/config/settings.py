"""Global configuration for the data collection system.

安全须知：
    所有密码必须通过环境变量配置，不得在代码中硬编码。
    开发环境可创建 .env 文件设置变量，该文件已在 .gitignore 中排除。
    生产环境必须通过系统环境变量或 secrets manager 注入。
"""

import logging
import os
from dataclasses import dataclass, field
from typing import List

logger = logging.getLogger(__name__)


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
    mysql_password: str = os.getenv("MYSQL_PASSWORD", "")
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

    # --- Rate Limiting ---
    rate_limit_enabled: bool = True
    rate_limit_global: str = "100/minute"
    rate_limit_admin: str = "20/minute"

    # --- Alerting ---
    alert_collector_failure_threshold: int = 3

    # --- Cleanup ---
    cleanup_snapshot_keep: int = 30
    cleanup_processed_days: int = 30
    cleanup_request_logs_days: int = 7

    # --- Admin ---
    admin_api_key: str = os.getenv("ADMIN_API_KEY", "")

    # --- LLM (Text-to-Cypher) ---
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_base_url: str = os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1")
    llm_model: str = os.getenv("LLM_MODEL", "deepseek-chat")
    llm_temperature: float = 0.0

    # --- Neo4j Knowledge Graph ---
    neo4j_uri: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user: str = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password: str = os.getenv("NEO4J_PASSWORD", "")
    neo4j_database: str = os.getenv("NEO4J_DATABASE", "neo4j")

    def __post_init__(self):
        """初始化后检查安全配置，对不安全项发出警告。"""
        self._validate_security()

    def _validate_security(self):
        """验证安全配置。缺失密码时给出明确指引。"""
        warnings = []

        if not self.mysql_password:
            warnings.append("MYSQL_PASSWORD 未设置——MySQL 连接将失败")
        if not self.neo4j_password:
            warnings.append("NEO4J_PASSWORD 未设置——Neo4j 连接将失败")
        if not self.admin_api_key:
            warnings.append(
                "ADMIN_API_KEY 未设置——管理端点处于无认证状态，"
                "生产环境请务必设置"
            )

        for w in warnings:
            logger.warning(w)
