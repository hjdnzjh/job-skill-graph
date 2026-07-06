"""Format normalization: unify job titles, locations, salaries into canonical forms.

This ensures cross-source comparability — "Java开发工程师" and "Java软件工程师"
map to the same canonical title.
"""

import logging
import re
from typing import Any, Dict, List, Optional

from config.schema import UnifiedJobSchema

logger = logging.getLogger(__name__)


class Normalizer:
    """Normalize key fields to canonical forms for cross-source consistency."""

    # --- City name canonicalization ---
    CITY_ALIASES = {
        "北京": "北京", "北京市": "北京", "bj": "北京", "beijing": "北京",
        "上海": "上海", "上海市": "上海", "sh": "上海", "shanghai": "上海",
        "深圳": "深圳", "深圳市": "深圳", "sz": "深圳", "shenzhen": "深圳",
        "广州": "广州", "广州市": "广州", "gz": "广州", "guangzhou": "广州",
        "杭州": "杭州", "杭州市": "杭州", "hz": "杭州", "hangzhou": "杭州",
        "成都": "成都", "成都市": "成都", "cd": "成都", "chengdu": "成都",
        "南京": "南京", "南京市": "南京", "nj": "南京", "nanjing": "南京",
        "武汉": "武汉", "武汉市": "武汉", "wh": "武汉", "wuhan": "武汉",
        "西安": "西安", "西安市": "西安", "xa": "西安", "xian": "西安",
    }

    # --- Job title canonicalization ---
    TITLE_NORMALIZE = [
        # (pattern, canonical_name)
        (r"java\s*(开发|软件|后端|研发)?(工程师|程序员)", "Java开发工程师"),
        (r"python\s*(开发|后端)?(工程师|程序员)", "Python开发工程师"),
        (r"go(lang)?\s*(开发|后端)?(工程师|程序员)", "Go开发工程师"),
        (r"(前端|web\s*前端|h5)\s*(开发)?(工程师|程序员)", "前端开发工程师"),
        (r"(全栈|full\s*stack)\s*(开发)?(工程师|程序员)", "全栈开发工程师"),
        (r"算法(工程师|研究员)", "算法工程师"),
        (r"人工智能(工程师|研究员)", "人工智能工程师"),
        (r"机器学习(工程师|研究员)", "机器学习工程师"),
        (r"深度学习(工程师|研究员)", "深度学习工程师"),
        (r"nlp\s*(算法)?(工程师|研究员)", "NLP算法工程师"),
        (r"cv\s*(算法)?(工程师|研究员)", "计算机视觉工程师"),
        (r"大数据\s*(开发|平台)?(工程师|架构师)", "大数据开发工程师"),
        (r"数据(分析|挖掘)(工程师|分析师|科学家)", "数据分析师"),
        (r"(运维|devops|sre)\s*(工程师|经理)", "运维工程师"),
        (r"(测试|qa)\s*(工程师|开发)?", "测试工程师"),
        (r"产品(经理|总监)", "产品经理"),
        (r"项目经理", "项目经理"),
        (r"架构师", "架构师"),
        (r"(c|cpp|c\+\+)\s*(开发|后端|软件)?(工程师|程序员)", "C++开发工程师"),
        (r"android\s*(开发)?(工程师|程序员)", "Android开发工程师"),
        (r"ios\s*(开发)?(工程师|程序员)", "iOS开发工程师"),
        (r"云计算(工程师|架构师)", "云计算工程师"),
        (r"安全(工程师|专家)", "安全工程师"),
        (r"区块链(工程师|开发)", "区块链工程师"),
    ]

    # --- Skills canonicalization ---
    SKILL_ALIASES = {
        "k8s": "Kubernetes", "kubernetes": "Kubernetes",
        "tf": "TensorFlow", "tensorflow": "TensorFlow",
        "torch": "PyTorch", "pytorch": "PyTorch",
        "nlp": "自然语言处理",
        "cv": "计算机视觉",
        "rdbms": "关系数据库",
        "nosql": "NoSQL",
        "ci/cd": "CI/CD",
        "cicd": "CI/CD",
        "devops": "DevOps",
        "aws": "AWS",
        "gcp": "Google Cloud",
        "azure": "Azure",
        "js": "JavaScript",
        "ts": "TypeScript",
        "reactjs": "React",
        "vuejs": "Vue",
        "nodejs": "Node.js",
        "node": "Node.js",
    }

    @classmethod
    def normalize(cls, records: List[UnifiedJobSchema]) -> List[UnifiedJobSchema]:
        """Apply full normalization pipeline to a batch of records."""
        for rec in records:
            cls._normalize_one(rec)
        logger.info(f"Normalized {len(records)} records")
        return records

    @classmethod
    def _normalize_one(cls, rec: UnifiedJobSchema) -> None:
        """Normalize all fields of a single record in place."""
        # Normalize job title
        rec.job_title = cls.normalize_job_title(rec.job_title_raw)

        # Normalize location to city level
        rec.location = cls.normalize_location(rec.location_raw)

        # Normalize company name (remove legal suffixes)
        rec.company_name = cls.normalize_company(rec.company_name_raw)

        # Normalize salary to K/month
        rec.salary_min, rec.salary_max = cls.normalize_salary(
            rec.salary_min, rec.salary_max, rec.extra.get("salary_raw", "")
        )

        # Normalize skills
        rec.skills_required = cls.normalize_skills(rec.skills_required)
        rec.skills_preferred = cls.normalize_skills(rec.skills_preferred)

        # Normalize experience
        rec.experience_required = cls.normalize_experience(rec.experience_required)

        # Normalize education
        rec.education_required = cls.normalize_education(rec.education_required)

        # Normalize industry
        rec.industry = cls.normalize_industry(rec.industry)

    # ------------------------------------------------------------------
    # Field normalizers
    # ------------------------------------------------------------------

    @classmethod
    def normalize_job_title(cls, raw: str) -> str:
        """Map a raw job title to its canonical form."""
        if not raw:
            return ""
        raw = raw.strip().lower()
        for pattern, canonical in cls.TITLE_NORMALIZE:
            if re.search(pattern, raw, re.IGNORECASE):
                return canonical
        return raw.title()

    @classmethod
    def normalize_location(cls, raw: str) -> str:
        """Map raw location to canonical Chinese city name."""
        if not raw:
            return ""
        raw_lower = raw.strip().lower()
        # Direct lookup
        if raw_lower in cls.CITY_ALIASES:
            return cls.CITY_ALIASES[raw_lower]
        # Substring match
        for alias, city in cls.CITY_ALIASES.items():
            if alias in raw_lower or raw_lower in alias:
                return city
        # Try to extract a known city name
        for alias, city in cls.CITY_ALIASES.items():
            if city in raw or alias in raw:
                return city
        return raw.strip()

    @classmethod
    def normalize_company(cls, raw: str) -> str:
        """Remove legal suffixes: 有限公司, Inc., Ltd., etc."""
        if not raw:
            return ""
        raw = raw.strip()
        raw = re.sub(
            r"(有限(责任)?公司|股份有限公司|（中国）|\(中国\)|Inc\.?|Ltd\.?|Corp\.?|LLC)$",
            "",
            raw,
            flags=re.IGNORECASE,
        ).strip()
        return raw

    @classmethod
    def normalize_salary(
        cls, salary_min: Optional[float], salary_max: Optional[float], raw: str
    ) -> tuple:
        """Ensure salary units are in K/month."""
        if salary_min is None and salary_max is None:
            return None, None
        # If values look like raw annual (e.g. > 200), convert to monthly
        if salary_max and salary_max > 200:
            salary_min = (salary_min or 0) / 12
            salary_max = salary_max / 12
        if salary_min and salary_min > 200:
            salary_min = salary_min / 12
            salary_max = (salary_max or salary_min) / 12
        return (
            round(salary_min, 1) if salary_min else None,
            round(salary_max, 1) if salary_max else None,
        )

    @classmethod
    def normalize_skills(cls, skills: List[str]) -> List[str]:
        """Canonicalize skill names."""
        result = []
        for s in skills:
            key = s.lower().strip()
            canonical = cls.SKILL_ALIASES.get(key, s)
            result.append(canonical)
        return list(set(result))  # dedup

    @classmethod
    def normalize_experience(cls, raw: str) -> str:
        """Normalize experience requirement to standard format."""
        if not raw:
            return ""
        raw = raw.strip()
        # "3-5年" → "3-5年"
        m = re.match(r"(\d+)\s*[-~至到]\s*(\d+)\s*年?", raw)
        if m:
            return f"{m.group(1)}-{m.group(2)}年"
        # "应届生" / "不限"
        if "应届" in raw or "毕业生" in raw:
            return "应届生"
        if "不限" in raw or "无经验" in raw:
            return "经验不限"
        # "3年以上" → "3年以上"
        m = re.match(r"(\d+)\s*年\s*以[上内]", raw)
        if m:
            return f"{m.group(1)}年以上"
        return raw

    @classmethod
    def normalize_education(cls, raw: str) -> str:
        """Normalize education requirement."""
        if not raw:
            return ""
        raw = raw.strip()
        if "博士" in raw:
            return "博士"
        if "硕士" in raw or "研究生" in raw:
            return "硕士"
        if "本科" in raw or "学士" in raw:
            return "本科"
        if "大专" in raw or "专科" in raw:
            return "大专"
        if "高中" in raw or "中专" in raw:
            return "高中"
        if "不限" in raw:
            return "学历不限"
        return raw

    @classmethod
    def normalize_industry(cls, raw: str) -> str:
        """Map industry names to a controlled vocabulary."""
        if not raw:
            return ""
        INDUSTRY_MAP = {
            "互联网": "互联网/IT",
            "计算机": "互联网/IT",
            "软件": "互联网/IT",
            "IT": "互联网/IT",
            "通信": "通信/电子",
            "电子": "通信/电子",
            "金融": "金融",
            "银行": "金融",
            "保险": "金融",
            "证券": "金融",
            "教育": "教育/培训",
            "培训": "教育/培训",
            "医疗": "医疗健康",
            "医药": "医疗健康",
            "制造": "智能制造",
            "汽车": "汽车/出行",
            "出行": "汽车/出行",
            "电商": "电商/零售",
            "零售": "电商/零售",
            "人工智能": "人工智能",
            "AI": "人工智能",
            "新能源": "新能源",
            "半导体": "半导体/集成电路",
            "集成电路": "半导体/集成电路",
            "芯片": "半导体/集成电路",
            "游戏": "游戏/娱乐",
        }
        raw_lower = raw.strip().lower()
        for kw, canonical in INDUSTRY_MAP.items():
            if kw.lower() in raw_lower:
                return canonical
        return raw.strip()
