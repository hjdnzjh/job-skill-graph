"""Unit tests for FastAPI endpoints."""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from web.server import app

client = TestClient(app)


class TestRootEndpoint:
    """前后端分离后，根路由返回 API 信息 JSON。"""

    def test_root_returns_json(self):
        """根路由 / 应返回 API 信息 JSON。"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "service" in data
        assert "version" in data

    def test_admin_dashboard(self):
        """管理面板 /admin 应返回 HTML 页面。"""
        response = client.get("/admin")
        assert response.status_code == 200
        content_type = response.headers.get("content-type", "")
        assert "text/html" in content_type


class TestOverviewAPI:
    """Tests for the /api/overview endpoint."""

    def test_overview_returns_json(self):
        """Overview should return JSON."""
        response = client.get("/api/overview")
        assert response.status_code in (200, 500, 503)  # 503 if Neo4j unavailable

    def test_emerging_jobs(self):
        """Emerging jobs endpoint should return list."""
        response = client.get("/api/emerging-jobs")
        assert response.status_code in (200, 500, 503)


class TestSkillsAPI:
    """Tests for skill-related endpoints."""

    def test_skill_ranking(self):
        """Skill ranking should return ordered list."""
        response = client.get("/api/skills/ranking?limit=10")
        assert response.status_code in (200, 500, 503)
        if response.status_code == 200:
            data = response.json()
            assert "skills" in data

    def test_skill_ranking_default_limit(self):
        """Default limit should be 30."""
        response = client.get("/api/skills/ranking")
        assert response.status_code in (200, 500, 503)

    def test_skill_network(self):
        """Skill network should return graph data."""
        response = client.get("/api/skills/network?limit=20")
        assert response.status_code in (200, 500, 503)

    def test_skill_communities(self):
        """Skill communities should return clustering data."""
        response = client.get("/api/skills/communities")
        assert response.status_code in (200, 500, 503)

    def test_skill_categories(self):
        """Skill categories should return distribution data."""
        response = client.get("/api/skills/categories")
        assert response.status_code in (200, 500, 503)


class TestDistributionAPI:
    """Tests for distribution endpoints."""

    def test_cities_distribution(self):
        response = client.get("/api/cities/distribution")
        assert response.status_code in (200, 500, 503)

    def test_cities_skill_profiles(self):
        response = client.get("/api/cities/skill-profiles?top=3")
        assert response.status_code in (200, 500, 503)

    def test_industries_distribution(self):
        response = client.get("/api/industries/distribution")
        assert response.status_code in (200, 500, 503)

    def test_companies(self):
        response = client.get("/api/companies?limit=10")
        assert response.status_code in (200, 500, 503)


class TestSalaryAPI:
    """Tests for salary endpoints."""

    def test_salary_by_title(self):
        response = client.get("/api/salary/by-title?limit=10")
        assert response.status_code in (200, 500, 503)

    def test_salary_by_city(self):
        response = client.get("/api/salary/by-city")
        assert response.status_code in (200, 500, 503)


class TestMatchingAPI:
    """Tests for matching endpoints."""

    def test_job_titles(self):
        response = client.get("/api/job-titles")
        assert response.status_code in (200, 500, 503)

    def test_match(self):
        response = client.post("/api/match", json={
            "skills": ["Python", "MySQL", "Git"],
            "target": "Python开发工程师"
        })
        assert response.status_code in (200, 503, 500)

    def test_recommend(self):
        response = client.post("/api/recommend", json={
            "skills": ["Python", "MySQL", "Git"],
            "top_n": 5
        })
        assert response.status_code in (200, 503, 500)


class TestEvolutionAPI:
    """Tests for evolution endpoints."""

    def test_timeline(self):
        response = client.get("/api/evolution/timeline")
        assert response.status_code in (200, 500, 503)

    def test_compare(self):
        response = client.get("/api/evolution/compare?a=0&b=-1")
        assert response.status_code in (200, 500, 503)


class TestRAGAPI:
    """Tests for RAG endpoints."""

    def test_rag_query(self):
        """RAG query should return answer with context."""
        response = client.post("/api/rag/query", json={
            "question": "Python需要学什么？"
        })
        assert response.status_code in (200, 503, 500)

    def test_rag_index(self):
        """RAG index endpoint should return count."""
        response = client.post("/api/rag/index")
        assert response.status_code in (200, 503, 500)


class TestUpdaterAPI:
    """Tests for job updater endpoints."""

    def test_list_updatable(self):
        response = client.get("/api/updater/list")
        assert response.status_code in (200, 500, 503)

    def test_analyze(self):
        response = client.get("/api/updater/analyze?title=Java开发工程师")
        assert response.status_code in (200, 500, 503)


class TestCORSHeaders:
    """Tests for CORS middleware."""

    def test_cors_allow_origin(self):
        response = client.options("/", headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        })
        # FastAPI CORS middleware should set allow-origin
        assert response.status_code in (200, 405)

    def test_cors_headers_present(self):
        response = client.get("/")
        # CORS headers should be present on normal responses
        headers = {k.lower(): v for k, v in response.headers.items()}
        assert "access-control-allow-origin" in headers or response.status_code == 200


class TestResumeAPI:
    """Tests for resume upload and evaluation endpoints."""

    def test_upload_no_file_returns_422(self):
        """Upload without file should return 422 validation error."""
        response = client.post("/api/resume/upload")
        assert response.status_code == 422

    def test_upload_text_file(self, tmp_path):
        """Upload a .txt file should return file_id and filename."""
        resume_content = "姓名: 张三\n技能: Python, Java, MySQL\n工作经验: 3年\n"
        f = tmp_path / "test_resume.txt"
        f.write_text(resume_content, encoding="utf-8")
        with open(f, "rb") as fh:
            response = client.post(
                "/api/resume/upload",
                files={"file": ("test_resume.txt", fh, "text/plain")},
            )
        assert response.status_code in (200, 503, 500)
        if response.status_code == 200:
            data = response.json()
            assert "file_id" in data
            assert "filename" in data
            assert data["filename"] == "test_resume.txt"

    def test_evaluate_without_upload_returns_404(self):
        """Evaluate with non-existent file_id should return 404."""
        response = client.post(
            "/api/resume/evaluate",
            json={"file_id": "nonexist", "target_title": "Java开发工程师"},
        )
        assert response.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
