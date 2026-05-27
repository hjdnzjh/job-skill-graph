"""Unit tests for Normalizer."""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from etl.normalizer import Normalizer


class TestSkillNormalization:
    """Tests for skill alias normalization."""

    def test_k8s_alias(self):
        result = Normalizer.normalize_skills(["k8s"])
        assert "Kubernetes" in result

    def test_kubernetes_alias(self):
        result = Normalizer.normalize_skills(["kubernetes"])
        assert "Kubernetes" in result

    def test_tf_alias(self):
        result = Normalizer.normalize_skills(["tf"])
        assert "TensorFlow" in result

    def test_torch_alias(self):
        result = Normalizer.normalize_skills(["torch"])
        assert "PyTorch" in result

    def test_js_alias(self):
        result = Normalizer.normalize_skills(["js"])
        assert "JavaScript" in result

    def test_ts_alias(self):
        result = Normalizer.normalize_skills(["ts"])
        assert "TypeScript" in result

    def test_cicd_alias(self):
        result = Normalizer.normalize_skills(["ci/cd"])
        assert "CI/CD" in result

    def test_devops_alias(self):
        result = Normalizer.normalize_skills(["devops"])
        assert "DevOps" in result

    def test_aws_alias(self):
        result = Normalizer.normalize_skills(["aws"])
        assert "AWS" in result

    def test_reactjs_alias(self):
        result = Normalizer.normalize_skills(["reactjs"])
        assert "React" in result

    def test_nodejs_alias(self):
        result = Normalizer.normalize_skills(["nodejs"])
        assert "Node.js" in result

    def test_cv_alias(self):
        result = Normalizer.normalize_skills(["cv"])
        assert "计算机视觉" in result

    def test_unknown_skill_passthrough(self):
        result = Normalizer.normalize_skills(["UnknownTech"])
        assert "UnknownTech" in result

    def test_mixed_skills(self):
        result = Normalizer.normalize_skills(["k8s", "Python", "aws", "UnknownSkill"])
        assert "Kubernetes" in result
        assert "Python" in result
        assert "AWS" in result
        assert "UnknownSkill" in result

    def test_empty_input(self):
        result = Normalizer.normalize_skills([])
        assert result == []

    def test_dedup_after_normalization(self):
        """After normalization, duplicate aliases should be deduplicated."""
        result = Normalizer.normalize_skills(["k8s", "kubernetes"])
        assert result.count("Kubernetes") == 1


class TestJobTitleNormalization:
    """Tests for job title normalization."""

    def test_java_title(self):
        assert Normalizer.normalize_job_title("Java开发工程师") == "Java开发工程师"
        # "java开发" has no 工程师/程序员 ending, so it won't match pattern
        assert Normalizer.normalize_job_title("Java程序员") == "Java开发工程师"

    def test_python_title(self):
        assert Normalizer.normalize_job_title("Python开发工程师") == "Python开发工程师"
        assert Normalizer.normalize_job_title("python后端工程师") == "Python开发工程师"

    def test_frontend_title(self):
        assert Normalizer.normalize_job_title("前端开发工程师") == "前端开发工程师"
        assert Normalizer.normalize_job_title("web前端工程师") == "前端开发工程师"

    def test_algo_title(self):
        assert Normalizer.normalize_job_title("算法工程师") == "算法工程师"
        assert Normalizer.normalize_job_title("NLP算法工程师") == "NLP算法工程师"

    def test_empty_title(self):
        assert Normalizer.normalize_job_title("") == ""

    def test_unknown_title_passthrough(self):
        result = Normalizer.normalize_job_title("Unknown Role Title")
        assert result == "Unknown Role Title".title()


class TestEducationNormalization:
    """Tests for education normalization."""

    def test_doctor(self):
        assert Normalizer.normalize_education("博士") == "博士"
        assert Normalizer.normalize_education("博士研究生") == "博士"

    def test_master(self):
        assert Normalizer.normalize_education("硕士") == "硕士"
        assert Normalizer.normalize_education("研究生") == "硕士"

    def test_bachelor(self):
        assert Normalizer.normalize_education("本科") == "本科"
        assert Normalizer.normalize_education("学士") == "本科"

    def test_college(self):
        assert Normalizer.normalize_education("大专") == "大专"
        assert Normalizer.normalize_education("专科") == "大专"

    def test_empty(self):
        assert Normalizer.normalize_education("") == ""


class TestIndustryNormalization:
    """Tests for industry normalization."""

    def test_it_industry(self):
        assert Normalizer.normalize_industry("互联网") == "互联网/IT"
        assert Normalizer.normalize_industry("IT") == "互联网/IT"
        assert Normalizer.normalize_industry("软件") == "互联网/IT"

    def test_finance_industry(self):
        assert Normalizer.normalize_industry("金融") == "金融"
        assert Normalizer.normalize_industry("银行") == "金融"

    def test_ai_industry(self):
        assert Normalizer.normalize_industry("人工智能") == "人工智能"
        assert Normalizer.normalize_industry("AI") == "人工智能"

    def test_unknown_industry(self):
        result = Normalizer.normalize_industry("未知行业")
        assert result == "未知行业"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
