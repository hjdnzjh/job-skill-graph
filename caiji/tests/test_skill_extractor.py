"""Unit tests for SkillExtractor."""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kg.skill_extractor import SkillExtractor, TITLE_TO_SKILLS, SKILL_KEYWORDS, SKILL_CATEGORIES


class TestSkillExtractor:
    """Tests for the SkillExtractor class."""

    def setup_method(self):
        self.extractor = SkillExtractor()

    def test_empty_input(self):
        """Empty input should return empty list."""
        result = self.extractor.extract()
        assert result == []

    def test_title_inference_java(self):
        """Title 'Java开发工程师' should infer Java-ecosystem skills."""
        result = self.extractor.extract(title="Java开发工程师")
        result_lower = [s.lower() for s in result]
        assert "java" in result_lower
        assert "spring boot" in result_lower
        assert "mysql" in result_lower
        assert "redis" in result_lower

    def test_title_inference_python(self):
        """Title 'Python开发工程师' should infer Python-ecosystem skills."""
        result = self.extractor.extract(title="Python开发工程师")
        result_lower = [s.lower() for s in result]
        assert "python" in result_lower
        assert "django" in result_lower or "flask" in result_lower
        assert "mysql" in result_lower

    def test_keyword_extraction_english(self):
        """English skill names should be extracted from Chinese JD text."""
        raw = "要求熟练掌握Python、Java、MySQL、Redis、Docker、Linux"
        result = self.extractor.extract(description=raw)
        result_lower = [s.lower() for s in result]
        assert "python" in result_lower
        assert "java" in result_lower
        assert "mysql" in result_lower
        assert "redis" in result_lower
        assert "docker" in result_lower
        assert "linux" in result_lower

    def test_keyword_extraction_chinese(self):
        """Chinese skill names should be extracted from text."""
        raw = "熟悉微服务架构，掌握分布式系统设计，具有机器学习项目经验"
        result = self.extractor.extract(description=raw)
        result_set = set(s.lower() for s in result)
        assert "微服务" in result_set
        assert "分布式" in result_set
        assert "机器学习" in result_set

    def test_keyword_extraction_mixed(self):
        """Mixed Chinese-English text should extract both skill types."""
        raw = "需要掌握Python、深度学习、计算机视觉、Docker"
        result = self.extractor.extract(description=raw)
        result_lower = [s.lower() for s in result]
        assert "python" in result_lower
        assert "深度学习" in result_lower
        assert "计算机视觉" in result_lower
        assert "docker" in result_lower

    def test_no_false_c_plus_plus_match(self):
        """Regex pattern for C should not falsely match inside C++."""
        raw = "要求精通C++开发，熟悉STL和Boost库"
        result = self.extractor.extract(description=raw)
        result_lower = [s.lower() for s in result]
        assert "c" not in result_lower  # Should not extract "C" from "C++"

    def test_spring_boot_not_just_spring(self):
        """'Spring Boot' should be recognized as distinct skill."""
        raw = "要求Spring Boot框架经验"
        result = self.extractor.extract(description=raw)
        result_lower = [s.lower() for s in result]
        assert "spring boot" in result_lower

    def test_deduplication(self):
        """Duplicate skills should be removed."""
        # Python appears both in title and description
        result = self.extractor.extract(
            title="Python开发工程师",
            description="需要Python开发经验",
        )
        result_lower = [s.lower() for s in result]
        # Python should appear exactly once
        assert result_lower.count("python") == 1

    def test_industry_fallback(self):
        """When few skills detected, industry fallback should add defaults."""
        result = self.extractor.extract(
            description="招聘工程师",
            industry="互联网/IT",
        )
        assert len(result) == 4  # Linux, Git, MySQL, HTTP

    def test_get_category(self):
        """Skill categories should be correctly returned."""
        assert SkillExtractor.get_category("Python") == "编程语言"
        assert SkillExtractor.get_category("MySQL") == "数据库"
        assert SkillExtractor.get_category("Docker") == "DevOps"
        assert SkillExtractor.get_category("机器学习") == "AI领域"
        assert SkillExtractor.get_category("UnknownSkill") == "其他"

    def test_extract_with_existing_skills(self):
        """Existing skills should be preserved and merged."""
        result = self.extractor.extract(
            description="需要Docker经验",
            existing_skills=["Python", "Java"],
        )
        result_lower = [s.lower() for s in result]
        assert "python" in result_lower
        assert "java" in result_lower
        assert "docker" in result_lower

    def test_react_extraction(self):
        """React should be extracted from frontend JD."""
        raw = "要求React Hooks、Redux、TypeScript开发经验"
        result = self.extractor.extract(description=raw)
        result_lower = [s.lower() for s in result]
        assert "react" in result_lower
        assert "redux" in result_lower
        assert "typescript" in result_lower

    def test_ai_skills_extraction(self):
        """AI/ML skills should be extracted."""
        raw = "具有TensorFlow、PyTorch深度学习框架经验，熟悉NLP和Transformer模型"
        result = self.extractor.extract(description=raw)
        result_lower = [s.lower() for s in result]
        assert "tensorflow" in result_lower
        assert "pytorch" in result_lower
        assert "nlp" in result_lower
        assert "transformer" in result_lower

    def test_bigdata_skills_extraction(self):
        """Big data skills should be extracted."""
        raw = "要求Spark、Flink、Hadoop、Hive、Kafka大数据技术栈"
        result = self.extractor.extract(description=raw)
        result_lower = [s.lower() for s in result]
        assert "spark" in result_lower
        assert "flink" in result_lower
        assert "hadoop" in result_lower
        assert "hive" in result_lower
        assert "kafka" in result_lower


class TestTITLETOSKILLS:
    """Tests for the TITLE_TO_SKILLS mapping."""

    def test_all_titles_have_skills(self):
        """Every job title should have at least 3 associated skills."""
        for title, skills in TITLE_TO_SKILLS.items():
            assert len(skills) >= 3, f"{title} has only {len(skills)} skills"

    def test_all_skills_in_categories(self):
        """All skills in TITLE_TO_SKILLS should have category entries."""
        missing = set()
        for skills in TITLE_TO_SKILLS.values():
            for s in skills:
                if s not in SKILL_CATEGORIES:
                    missing.add(s)
        assert not missing, f"Skills without categories: {missing}"


class TestSKILLKEYWORDS:
    """Tests for the SKILL_KEYWORDS pattern list."""

    def test_no_duplicate_names(self):
        """No duplicate skill names in patterns."""
        names = [name for _, name in SKILL_KEYWORDS]
        duplicates = set(n for n in names if names.count(n) > 1)
        assert not duplicates, f"Duplicate patterns: {duplicates}"

    def test_no_empty_patterns(self):
        """All patterns should be non-empty."""
        for pat, name in SKILL_KEYWORDS:
            assert pat.strip(), f"Empty pattern for {name}"

    def test_all_patterns_compile(self):
        """All patterns should be valid regex."""
        import re
        for pat, name in SKILL_KEYWORDS:
            try:
                re.compile(pat)
            except re.error as e:
                pytest.fail(f"Pattern '{pat}' for '{name}' is invalid: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
