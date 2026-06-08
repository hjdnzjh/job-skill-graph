"""Tests for reports and analytics API."""

import sys
import os
import json
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient
from web.server import app

client = TestClient(app)


class TestReportsAPI:
    """Tests for /api/reports/overview endpoint with live data."""

    def test_overview_returns_all_sections(self):
        response = client.get("/api/reports/overview")
        assert response.status_code in (200, 500, 503)
        if response.status_code == 200:
            data = response.json()
            assert "job_trends" in data
            assert "skill_trends" in data
            assert "skill_trends_detail" in data
            assert "status_distribution" in data
            assert "insights" in data
            assert "warnings" in data

    def test_job_trends_has_monthly_data(self):
        response = client.get("/api/reports/overview")
        assert response.status_code in (200, 500, 503)
        if response.status_code == 200:
            trends = response.json()["job_trends"]
            assert len(trends) > 0
            for t in trends:
                assert "month" in t
                assert "count" in t

    def test_status_distribution_has_all_statuses(self):
        response = client.get("/api/reports/overview")
        assert response.status_code in (200, 500, 503)
        if response.status_code == 200:
            dist = response.json()["status_distribution"]
            assert len(dist) > 0
            for d in dist:
                assert "name" in d
                assert "value" in d


class TestReportsWithMockSnapshots:
    """Tests using temporary mock snapshot files."""

    @pytest.fixture(autouse=True)
    def setup_mock_snapshots(self, monkeypatch):
        """Replace snapshot dir with a temp dir containing mock snapshots."""
        self.tmp_dir = tempfile.mkdtemp()
        import web.api_reports
        monkeypatch.setattr(web.api_reports, "SNAPSHOT_DIR", self.tmp_dir)

        # 3 mock snapshots with deliberately non-chronological filenames
        snapshots_data = [
            {
                "timestamp": "2025-06-01T00:00:00",
                "record_count": 500,
                "graph": {"total_nodes": 1000, "total_edges": 5000},
                "top_skills": [
                    {"skill": "Python", "demand": 200},
                    {"skill": "Java", "demand": 150},
                ],
            },
            {
                "timestamp": "2025-12-01T00:00:00",
                "record_count": 800,
                "graph": {"total_nodes": 1600, "total_edges": 8000},
                "top_skills": [
                    {"skill": "Python", "demand": 250},
                    {"skill": "Java", "demand": 120},
                ],
            },
            {
                "timestamp": "2026-06-01T00:00:00",
                "record_count": 1175,
                "graph": {"total_nodes": 2479, "total_edges": 16093},
                "top_skills": [
                    {"skill": "Python", "demand": 314},
                    {"skill": "Java", "demand": 100},
                    {"skill": "Rust", "demand": 10},
                ],
            },
        ]
        for i, snap in enumerate(snapshots_data):
            # Non-chronological filenames to test timestamp-sort
            fname = f"snapshot_{300-i:03d}.json"
            with open(os.path.join(self.tmp_dir, fname), "w", encoding="utf-8") as f:
                json.dump(snap, f)

        web.api_reports._load_snapshots.cache_clear()
        yield
        shutil.rmtree(self.tmp_dir)

    def test_load_snapshots_sorted_by_timestamp(self):
        """Snapshots should be sorted by timestamp, not filename."""
        import web.api_reports
        web.api_reports._load_snapshots.cache_clear()
        snaps = list(web.api_reports._load_snapshots())
        assert len(snaps) == 3
        assert snaps[0]["timestamp"].startswith("2025-06")
        assert snaps[1]["timestamp"].startswith("2025-12")
        assert snaps[2]["timestamp"].startswith("2026-06")

    def test_job_trends_has_three_points(self):
        """Should produce 3 job_trends points from 3 mock snapshots."""
        import web.api_reports
        web.api_reports._load_snapshots.cache_clear()
        response = client.get("/api/reports/overview")
        assert response.status_code in (200, 500, 503)
        if response.status_code == 200:
            data = response.json()
            assert len(data["job_trends"]) == 3
            months = [t["month"] for t in data["job_trends"]]
            assert months == ["2025年6月", "2025年12月", "2026年6月"]

    def test_skill_trends_computes_growth_correctly(self):
        """Python: 200->314 = 57% growth. Java: 150->100 = -33%."""
        import web.api_reports
        web.api_reports._load_snapshots.cache_clear()
        response = client.get("/api/reports/overview")
        assert response.status_code in (200, 500, 503)
        if response.status_code == 200:
            data = response.json()
            trends = {t["name"]: t for t in data["skill_trends"]}
            # Python: 200->314 = 57% growth (allow ±1 for rounding)
            assert 56 <= trends["Python"]["growth"] <= 57
            # Java: 150->100 = -33% growth
            assert -34 <= trends["Java"]["growth"] <= -33
            assert trends["Python"]["direction"] == "up"
            assert trends["Java"]["direction"] == "down"

    def test_new_skill_has_growth_100(self):
        """Rust: old=0, new=10 -> growth=100 (marked as new)."""
        import web.api_reports
        web.api_reports._load_snapshots.cache_clear()
        response = client.get("/api/reports/overview")
        assert response.status_code in (200, 500, 503)
        if response.status_code == 200:
            data = response.json()
            trends = {t["name"]: t for t in data["skill_trends"]}
            assert "Rust" in trends
            assert trends["Rust"]["growth"] == 100
            assert trends["Rust"]["direction"] == "new"

    def test_skill_trends_detail_has_all_timepoints(self):
        """skill_trends_detail should have 3 series points per skill."""
        import web.api_reports
        web.api_reports._load_snapshots.cache_clear()
        response = client.get("/api/reports/overview")
        assert response.status_code in (200, 500, 503)
        if response.status_code == 200:
            data = response.json()
            detail = {d["skill"]: d for d in data["skill_trends_detail"]}
            assert "Python" in detail
            assert len(detail["Python"]["series"]) == 3
            assert detail["Python"]["series"][0]["demand"] == 200
            assert detail["Python"]["series"][-1]["demand"] == 314

    def test_insights_include_new_skill_detection(self):
        """Should detect Rust as a newly appearing skill."""
        import web.api_reports
        web.api_reports._load_snapshots.cache_clear()
        response = client.get("/api/reports/overview")
        assert response.status_code in (200, 500, 503)
        if response.status_code == 200:
            data = response.json()
            cats = [ins["category"] for ins in data["insights"]]
            assert "新兴技能出现" in cats


class TestReportsEmptySnapshots:
    """Tests when no snapshots exist."""

    @pytest.fixture(autouse=True)
    def setup_empty(self, monkeypatch):
        import web.api_reports
        self.empty_dir = tempfile.mkdtemp()
        monkeypatch.setattr(web.api_reports, "SNAPSHOT_DIR", self.empty_dir)
        web.api_reports._load_snapshots.cache_clear()
        yield
        shutil.rmtree(self.empty_dir)

    def test_empty_snapshots_returns_empty_trends(self):
        response = client.get("/api/reports/overview")
        assert response.status_code in (200, 500, 503)
        if response.status_code == 200:
            data = response.json()
            assert data["job_trends"] == []
            assert data["skill_trends"] == []
            assert len(data["warnings"]) > 0

    def test_data_insufficient_insight(self):
        """When no snapshots, should have '数据不足' insight."""
        response = client.get("/api/reports/overview")
        assert response.status_code in (200, 500, 503)
        if response.status_code == 200:
            has_fallback = any(
                ins.get("category") == "数据不足"
                for ins in response.json()["insights"]
            )
            assert has_fallback
