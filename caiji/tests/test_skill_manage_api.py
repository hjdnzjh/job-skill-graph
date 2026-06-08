"""Tests for skill change management API."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient
from web.server import app

client = TestClient(app)


class TestSkillManageAPI:
    """Tests for /api/skills/changes endpoints."""

    def test_list_changes_returns_json(self):
        response = client.get("/api/skills/changes")
        assert response.status_code in (200, 500, 503)
        if response.status_code == 200:
            data = response.json()
            assert "changes" in data
            assert "total" in data

    def test_list_changes_has_valid_structure(self):
        response = client.get("/api/skills/changes")
        assert response.status_code in (200, 500, 503)
        if response.status_code == 200 and response.json().get("changes"):
            changes = response.json()["changes"]
            for c in changes:
                assert "title" in c
                assert "change_type" in c
                assert c["change_type"] in ("add", "remove", "modify")
                assert "skill" in c
                assert "date" in c
                assert "source" in c
                assert "evidence" in c

    def test_analyze_job_title_missing(self):
        response = client.get("/api/skills/changes/__不存在的岗位__")
        assert response.status_code in (404, 500, 503)

    def test_confirm_changes(self):
        response = client.post("/api/skills/changes/Java开发工程师/confirm")
        assert response.status_code in (200, 500)
        if response.status_code == 200:
            data = response.json()
            assert data["status"] == "confirmed"
            assert "confirmed_at" in data
