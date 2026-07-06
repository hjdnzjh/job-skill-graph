from .spiders.recruitment import RecruitmentSpider
from .spiders.enterprise import EnterpriseSpider
from .spiders.policy import PolicySpider
from .spiders.academic import AcademicSpider
from .spiders.industry_report import IndustryReportSpider

__all__ = [
    "RecruitmentSpider",
    "EnterpriseSpider",
    "PolicySpider",
    "AcademicSpider",
    "IndustryReportSpider",
]
