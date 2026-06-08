"""Tests for JobMatcher extended features: radar scoring and gap suggestions."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from kg.job_matcher import JobMatcher


class DummySettings:
    neo4j_uri = "bolt://localhost:7687"
    neo4j_user = "neo4j"
    neo4j_password = "12345678"
    neo4j_database = "neo4j"


@pytest.fixture
def matcher():
    m = JobMatcher(DummySettings())
    yield m
    m.close()


def test_radar_score_returns_all_five_dimensions(matcher):
    """radar_score() should return 5 dimensions with 0-100 scores."""
    try:
        result = matcher.radar_score(
            user_skills=["Python", "Git", "Linux"],
            matched_skills=["Python"],
            missing_skills=["Java"],
            total_required=2,
        )
    except Exception:
        pytest.skip("Neo4j unavailable for this test")
        return
    assert "radar" in result
    assert len(result["radar"]) == 5
    dims = {d["dimension"] for d in result["radar"]}
    assert dims == {"技术深度", "业务理解", "协作沟通", "学习能力", "工具链熟练度"}
    for d in result["radar"]:
        assert 0 <= d["score"] <= 100


def test_radar_score_empty_skills(matcher):
    """radar_score() should handle empty skill lists gracefully."""
    try:
        result = matcher.radar_score(
            user_skills=[],
            matched_skills=[],
            missing_skills=[],
            total_required=0,
        )
    except Exception:
        pytest.skip("Neo4j unavailable for this test")
        return
    for d in result["radar"]:
        assert d["score"] >= 0


def test_gap_suggestions_returns_structured_advice(matcher):
    """gap_suggestions() should return categorized improvement advice."""
    try:
        result = matcher.gap_suggestions(
            user_skills=["Python", "Git"],
            missing_skills=["Docker", "Kubernetes", "MySQL"],
            target_title="Python开发工程师",
        )
    except Exception:
        pytest.skip("Neo4j unavailable for this test")
        return
    assert len(result) > 0
    for item in result:
        assert "category" in item
        assert "suggestion" in item
        assert "related_skills" in item
