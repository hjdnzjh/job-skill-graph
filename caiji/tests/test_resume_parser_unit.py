"""Unit tests for ResumeParser (no external dependencies)."""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kg.resume_parser import ResumeParser


class DummySettings:
    llm_api_key = ""
    llm_base_url = "https://api.deepseek.com/v1"
    llm_model = "deepseek-chat"
    neo4j_uri = "bolt://localhost:7687"
    neo4j_user = "neo4j"
    neo4j_password = "12345678"
    neo4j_database = "neo4j"


class TestResumeParserUnit:
    """Unit tests for ResumeParser that do not require LLM or Neo4j."""

    def test_read_text_file(self):
        """read_file() should extract plain text from a .txt file."""
        content = "姓名：张三\n技能：Python、Java\n"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write(content)
            tmp_path = f.name
        try:
            result = ResumeParser.read_file(tmp_path)
            assert result == content
        finally:
            os.unlink(tmp_path)

    def test_parse_with_fallback_no_llm(self):
        """parse_with_fallback() should use keyword fallback when LLM is unavailable."""
        parser = ResumeParser(DummySettings())
        text = "5年Java开发经验，熟悉Spring Boot、MySQL、Redis"
        result = parser.parse_with_fallback(text, skills_from_text=["Java", "Spring Boot"])
        assert result["method"] == "keyword_fallback"
        assert "Java" in result.get("skills", [])
        assert "Spring Boot" in result.get("skills", [])
        assert result.get("years_of_experience") == 5.0
        parser.close()


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
