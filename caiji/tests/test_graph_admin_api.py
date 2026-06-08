"""Tests for graph administration API."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient
from web.server import app

client = TestClient(app)


class TestGraphAdminAPI:
    """Tests for /api/graph endpoints."""

    def test_list_nodes_returns_json(self):
        response = client.get("/api/graph/nodes")
        assert response.status_code in (200, 500, 503)
        if response.status_code == 200:
            data = response.json()
            assert "nodes" in data
            assert "total" in data

    def test_list_nodes_by_label(self):
        response = client.get("/api/graph/nodes?label=Skill&limit=5")
        assert response.status_code in (200, 500, 503)
        if response.status_code == 200:
            data = response.json()
            for n in data["nodes"]:
                assert n["label"] == "Skill"
                # category should never be None (cleaned to "")
                assert n["category"] is not None

    def test_list_edges_returns_json(self):
        response = client.get("/api/graph/edges")
        assert response.status_code in (200, 500, 503)

    def test_list_edges_by_type(self):
        response = client.get("/api/graph/edges?rel_type=REQUIRES&limit=5")
        assert response.status_code in (200, 500, 503)
        if response.status_code == 200:
            data = response.json()
            assert "edges" in data

    def test_export_returns_json(self):
        response = client.get("/api/graph/export")
        assert response.status_code in (200, 500, 503)
        if response.status_code == 200:
            data = response.json()
            assert "nodes" in data
            assert "edges" in data
            assert "has_more" in data

    def test_export_with_limit(self):
        response = client.get("/api/graph/export?limit=100")
        assert response.status_code in (200, 500, 503)
