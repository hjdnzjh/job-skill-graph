"""Extract unique entity nodes from job records across all entity types."""

from dataclasses import dataclass, field
from typing import Any, Dict, List

from kg.skill_extractor import SkillExtractor


@dataclass
class EntityCollection:
    """Container for all extracted entity nodes, keyed by canonical name."""
    job_titles: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    companies: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    skills: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    cities: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    industries: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    educations: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    experiences: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    # Link each job record_id to its entity keys
    job_entities: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # Alias map: original_name → canonical_name (populated by entity_aligner)
    alias_map: Dict[str, str] = field(default_factory=dict)

    @property
    def total_entities(self) -> int:
        return (len(self.job_titles) + len(self.companies) + len(self.skills) +
                len(self.cities) + len(self.industries) + len(self.educations) +
                len(self.experiences))

    def summary(self) -> Dict[str, int]:
        return {
            "job_titles": len(self.job_titles),
            "companies": len(self.companies),
            "skills": len(self.skills),
            "cities": len(self.cities),
            "industries": len(self.industries),
            "educations": len(self.educations),
            "experiences": len(self.experiences),
            "jobs": len(self.job_entities),
            "total": self.total_entities,
        }


# Province lookup for major Chinese cities
CITY_PROVINCE = {
    "北京": "北京", "上海": "上海", "天津": "天津", "重庆": "重庆",
    "深圳": "广东", "广州": "广东", "东莞": "广东", "佛山": "广东",
    "珠海": "广东", "惠州": "广东", "中山": "广东",
    "杭州": "浙江", "宁波": "浙江", "温州": "浙江",
    "南京": "江苏", "苏州": "江苏", "无锡": "江苏", "常州": "江苏",
    "成都": "四川", "绵阳": "四川",
    "武汉": "湖北", "宜昌": "湖北",
    "西安": "陕西",
    "长沙": "湖南",
    "合肥": "安徽",
    "郑州": "河南",
    "济南": "山东", "青岛": "山东", "烟台": "山东",
    "厦门": "福建", "福州": "福建",
    "大连": "辽宁", "沈阳": "辽宁",
    "昆明": "云南",
    "贵阳": "贵州",
    "哈尔滨": "黑龙江",
    "长春": "吉林",
    "南宁": "广西",
    "海口": "海南",
    "南昌": "江西",
    "太原": "山西",
    "石家庄": "河北",
    "兰州": "甘肃",
    "乌鲁木齐": "新疆",
    "呼和浩特": "内蒙古",
    "银川": "宁夏",
    "西宁": "青海",
    "拉萨": "西藏",
}


class EntityExtractor:
    """Extract all entity types from job records."""

    def __init__(self, skill_extractor: SkillExtractor = None):
        self.skill_extractor = skill_extractor or SkillExtractor()

    def extract_all(self, records: List[Any]) -> EntityCollection:
        """Extract unique entities across all records.

        Args:
            records: List of JobRecord ORM objects or UnifiedJobSchema instances.

        Returns:
            EntityCollection with deduplicated entity nodes.
        """
        entities = EntityCollection()

        for rec in records:
            rid = rec.record_id if hasattr(rec, 'record_id') else rec.get('record_id', '')

            # Extract per-record entity keys for later relationship construction
            rec_entities = {}

            # Job title
            title = rec.job_title if hasattr(rec, 'job_title') else rec.get('job_title', '')
            if title:
                entities.job_titles[title] = {"name": title}
                rec_entities["job_title"] = title

            # Company
            company = rec.company_name if hasattr(rec, 'company_name') else rec.get('company_name', '')
            if company:
                industry = rec.industry if hasattr(rec, 'industry') else rec.get('industry', '')
                entities.companies[company] = {"name": company, "industry": industry or ""}
                rec_entities["company"] = company

            # Skills — use SkillExtractor
            desc = rec.job_description if hasattr(rec, 'job_description') else rec.get('job_description', '')
            ind = rec.industry if hasattr(rec, 'industry') else rec.get('industry', '')
            existing_skills = (rec.skills_required if hasattr(rec, 'skills_required')
                               else rec.get('skills_required', []))
            extracted_skills = self.skill_extractor.extract(
                title=title, description=desc or "", industry=ind or "",
                existing_skills=existing_skills or [],
            )
            for skill_name in extracted_skills:
                category = SkillExtractor.get_category(skill_name)
                entities.skills[skill_name] = {"name": skill_name, "category": category}
            rec_entities["skills"] = extracted_skills

            # Preferred skills
            preferred = (rec.skills_preferred if hasattr(rec, 'skills_preferred')
                         else rec.get('skills_preferred', []))
            if preferred:
                rec_entities["preferred_skills"] = []
                for s in preferred:
                    s_clean = s.strip() if isinstance(s, str) else str(s)
                    if s_clean:
                        category = SkillExtractor.get_category(s_clean)
                        entities.skills[s_clean] = {"name": s_clean, "category": category}
                        rec_entities["preferred_skills"].append(s_clean)

            # City
            location = rec.location if hasattr(rec, 'location') else rec.get('location', '')
            if location:
                province = CITY_PROVINCE.get(location, "")
                entities.cities[location] = {"name": location, "province": province}
                rec_entities["city"] = location

            # Industry
            if ind:
                entities.industries[ind] = {"name": ind}
                rec_entities["industry"] = ind

            # Education
            edu = rec.education_required if hasattr(rec, 'education_required') else rec.get('education_required', '')
            if edu:
                entities.educations[edu] = {"name": edu}
                rec_entities["education"] = edu

            # Experience
            exp = rec.experience_required if hasattr(rec, 'experience_required') else rec.get('experience_required', '')
            if exp:
                entities.experiences[exp] = {"name": exp}
                rec_entities["experience"] = exp

            entities.job_entities[rid] = rec_entities

        return entities
