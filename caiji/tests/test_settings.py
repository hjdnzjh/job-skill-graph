"""Unit tests for Settings."""

import os
import pytest
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import Settings


class TestSettingsDefaults:
    """Tests for default settings values."""

    def test_default_mysql_host(self):
        s = Settings()
        assert s.mysql_host in ("localhost", "mysql")

    def test_default_mysql_port(self):
        s = Settings()
        assert s.mysql_port == 3306

    def test_default_neo4j_uri(self):
        s = Settings()
        assert "7687" in s.neo4j_uri

    def test_default_neo4j_user(self):
        s = Settings()
        assert s.neo4j_user == "neo4j"

    def test_default_llm_base_url(self):
        s = Settings()
        assert "deepseek.com" in s.llm_base_url

    def test_default_llm_model(self):
        s = Settings()
        assert s.llm_model == "deepseek-chat"

    def test_env_override(self):
        """Test that env vars are read (may be overridden by system env)."""
        s = Settings()
        # These should have SOME value (default or env)
        assert isinstance(s.mysql_host, str)
        assert isinstance(s.neo4j_uri, str)
        assert s.neo4j_uri.startswith("bolt://")

    def test_settings_are_immutable_types(self):
        """Settings fields should be standard types."""
        s = Settings()
        assert isinstance(s.mysql_host, str)
        assert isinstance(s.mysql_port, int)
        assert isinstance(s.concurrent_requests, int)
        assert isinstance(s.download_delay, float)
        assert isinstance(s.enabled_sources, list)

    def test_default_log_level(self):
        s = Settings()
        assert s.log_level == "INFO"

    def test_enabled_sources(self):
        s = Settings()
        assert "recruitment" in s.enabled_sources
        assert len(s.enabled_sources) == 4

    def test_concurrent_requests(self):
        s = Settings()
        assert s.concurrent_requests == 16
        assert s.download_delay == 1.0

    def test_quality_thresholds(self):
        s = Settings()
        assert 0 < s.dedup_similarity_threshold <= 1.0
        assert 0 < s.quality_min_score <= 1.0
        assert s.batch_size > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
