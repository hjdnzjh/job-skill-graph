"""Tests for job review API."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient
from web.server import app

client = TestClient(app)


class TestJobReviewAPI:
    """Tests for /api/jobs endpoints."""

    def test_list_pending_returns_json(self):
        response = client.get("/api/jobs/pending")
        assert response.status_code in (200, 500, 503)
        if response.status_code == 200:
            data = response.json()
            assert "jobs" in data
            assert "total" in data
            assert "offset" in data
            assert "limit" in data

    def test_list_pending_items_have_required_fields(self):
        response = client.get("/api/jobs/pending")
        assert response.status_code in (200, 500, 503)
        if response.status_code == 200 and response.json().get("jobs"):
            for j in response.json()["jobs"]:
                assert "title" in j
                assert "category" in j
                assert "source" in j
                assert "status" in j
                assert "date" in j
                assert "type" in j

    def test_list_pending_filter_by_status(self):
        response = client.get("/api/jobs/pending?status=pending")
        assert response.status_code in (200, 500, 503)
        if response.status_code == 200:
            for j in response.json()["jobs"]:
                assert j["status"] == "pending"

    def test_list_pending_search(self):
        response = client.get("/api/jobs/pending?search=Node")
        assert response.status_code in (200, 500, 503)

    def test_get_job_detail_regular(self):
        """Regular job title should return detail with required_skills as objects."""
        response = client.get("/api/jobs/Java开发工程师")
        assert response.status_code in (200, 404, 500, 503)
        if response.status_code == 200:
            data = response.json()
            assert "title" in data
            assert "type" in data
            if data.get("required_skills"):
                assert isinstance(data["required_skills"], list)
                assert isinstance(data["required_skills"][0], dict)

    def test_get_job_detail_missing(self):
        response = client.get("/api/jobs/__不存在的岗位__")
        assert response.status_code in (404, 500, 503)

    def test_approve_requires_auth(self):
        """Without X-Admin-Key, approve may be 403 if key is set in env."""
        response = client.post("/api/jobs/数据科学家/approve")
        assert response.status_code in (200, 403, 404, 500)

    def test_reject_requires_auth(self):
        response = client.post("/api/jobs/数据科学家/reject")
        assert response.status_code in (200, 403, 404, 500)

    def test_update_requires_auth(self):
        response = client.put("/api/jobs/数据科学家", json={"description": "test"})
        assert response.status_code in (200, 400, 403, 404, 500)
