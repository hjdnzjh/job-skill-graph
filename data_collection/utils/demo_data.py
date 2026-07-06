"""Generate synthetic / demo job records for testing the ETL pipeline.

Used when real crawling is not available (no network, dev environment, etc.).
"""

import random
import uuid
from datetime import datetime, timedelta
from typing import List

from config.schema import (
    UnifiedJobSchema,
    DataSourceType,
    DataFormat,
)

# --- realistic Chinese job data pools ---

JOB_TITLES = [
    "Java开发工程师", "Python开发工程师", "Go后端开发", "前端开发工程师",
    "全栈开发工程师", "算法工程师", "人工智能工程师", "机器学习工程师",
    "深度学习研究员", "NLP算法工程师", "计算机视觉工程师", "大数据开发工程师",
    "数据分析师", "数据挖掘工程师", "数据科学家", "运维工程师",
    "DevOps工程师", "测试工程师", "产品经理", "项目经理",
    "架构师", "C++开发工程师", "Android开发工程师", "iOS开发工程师",
    "云计算工程师", "安全工程师", "区块链工程师", "嵌入式工程师",
    "游戏开发工程师", "技术总监",
]

COMPANIES = [
    ("华为", "通信/IT"), ("腾讯", "互联网"), ("阿里巴巴", "电商/互联网"),
    ("字节跳动", "互联网"), ("百度", "互联网"), ("京东", "电商/互联网"),
    ("美团", "互联网"), ("滴滴", "出行/互联网"), ("小米", "消费电子"),
    ("网易", "互联网"), ("快手", "互联网"), ("拼多多", "电商/互联网"),
    ("蔚来", "汽车/出行"), ("商汤科技", "人工智能"), ("科大讯飞", "人工智能"),
    ("大疆", "智能硬件"), ("海康威视", "安防/AI"), ("宁德时代", "新能源"),
    ("比亚迪", "汽车/新能源"), ("中兴通讯", "通信/IT"),
]

LOCATIONS = ["北京", "上海", "深圳", "杭州", "广州", "成都", "南京", "武汉", "西安"]

SKILLS_POOL = [
    "Python", "Java", "Go", "C++", "Rust", "TypeScript", "JavaScript",
    "React", "Vue", "Angular", "Spring Boot", "Django", "Flask", "FastAPI",
    "TensorFlow", "PyTorch", "Keras", "Scikit-learn", "Transformer",
    "MySQL", "PostgreSQL", "MongoDB", "Redis", "Elasticsearch",
    "Docker", "Kubernetes", "AWS", "Azure", "GCP",
    "Spark", "Flink", "Hadoop", "Kafka", "RabbitMQ", "gRPC",
    "Linux", "Git", "DevOps", "CI/CD", "微服务", "分布式系统",
]

ABILITIES_POOL = [
    "沟通能力", "团队协作", "逻辑思维", "学习能力", "创新能力",
    "领导力", "问题解决", "抗压能力", "数据分析能力", "项目管理能力",
    "系统思维", "执行力", "自驱力", "文档编写能力", "时间管理",
]

JOB_DESCRIPTION_TEMPLATES = [
    """
岗位职责：
1. 负责公司核心业务系统的架构设计与开发；
2. 参与系统性能优化和高可用方案设计；
3. 编写高质量代码，进行代码审查；
4. 与产品、测试团队紧密协作，推动项目交付。

任职要求：
1. 计算机相关专业本科及以上学历；
2. 精通{skill1}，熟悉{skill2}、{skill3}等常用技术栈；
3. 具备良好的数据结构和算法基础；
4. 有大规模分布式系统开发经验者优先；
5. 具备较强的{ability1}和{ability2}。
""".strip(),

    """
工作内容：
- 参与公司AI平台的建设与优化；
- 负责机器学习模型的训练、调优与部署；
- 跟踪前沿技术发展，将新技术应用于实际业务场景；
- 撰写技术文档和专利。

职位要求：
- 硕士及以上学历，计算机、数学、统计等相关专业；
- 熟练掌握{skill1}、{skill2}等深度学习框架；
- 有NLP/CV/推荐系统至少一个方向的项目经验；
- 在国际顶级会议或期刊发表过论文者优先；
- 有较强的{ability1}和{ability2}。
""".strip(),

    """
岗位描述：
1. 负责公司数据平台的搭建和维护；
2. 设计并实现数据采集、清洗、存储的完整Pipeline；
3. 开发数据分析和可视化工具；
4. 为业务部门提供数据支持。

技能要求：
- 精通{skill1}编程语言；
- 熟悉{skill2}、{skill3}等大数据处理框架；
- 了解数据仓库建设和ETL流程；
- 有良好的{ability1}和{ability2}。
""".strip(),

    """
我们正在寻找一位充满热情的技术专家加入我们快速发展的团队。

主要职责：
• 主导系统技术方案选型和架构设计
• 解决核心技术难题，指导团队成员成长
• 推动技术标准与最佳实践的落地

理想人选：
• 5年以上相关工作经验
• 深度掌握{skill1}和{skill2}
• 有带领技术团队的经验
• 出色的{ability1}和{ability2}
""".strip(),

    """
【岗位名称】：{title}
【工作地点】：{location}
【薪资范围】：{salary}

工作职责：
1. {duty1}
2. {duty2}
3. {duty3}

任职资格：
- 精通{skill1}，熟悉{skill2}
- 具备{ability1}
- {edu}及以上学历
- {exp}相关工作经验
""".strip(),

    """
About the Role:
We are seeking a talented {title} to join our team in {location}.

Key Responsibilities:
• Design and implement scalable solutions using {skill1} and {skill2}
• Collaborate with cross-functional teams to deliver high-impact projects
• Drive technical excellence and mentor junior team members

Requirements:
• Bachelor's degree or above in CS or related field
• Strong proficiency in {skill1}, {skill2}, and {skill3}
• Experience with {skill4} is a plus
• {ability1} and {ability2}
""".strip(),

    """
业务部门直招：{title}

我们是谁？
{company}是{industry}领域的领先企业，目前正在快速扩张中。

你需要做什么？
- 负责{duty1}
- 参与{duty2}
- 协助{duty3}

我们希望你：
1. 熟练掌握{skill1}、{skill2}
2. 了解{skill3}的基本原理和应用
3. 具备{ability1}
4. {exp}以上相关经验
""".strip(),

    """
【急聘】{title} — {company}

团队简介：
我们是一个充满活力的技术团队，专注于{industry}领域的创新应用。

工作内容：
• {duty1}
• {duty2}

职位要求：
• {edu}及以上学历，{exp}工作经验
• 精通{skill1}
• 有{skill2}项目经验优先
• {ability1}强
• 能够承受工作压力，适应快速迭代的开发节奏
""".strip(),

    """
{company} {industry}事业部 招聘 {title}

我们提供：
- 有竞争力的薪酬：{salary}/月
- 弹性工作制，扁平化管理
- 完善的培训体系和晋升通道

岗位职责：
1. {duty1}
2. {duty2}

任职要求：
- 熟悉{skill1}、{skill2}
- 具备{ability1}和{ability2}
- {edu}以上学历
- 有{skill3}开发经验者优先考虑
""".strip(),
]

# --- Source-specific record pools ---

POLICY_TITLES = [
    "关于印发《新一代人工智能发展规划》的通知",
    "关于促进数字经济高质量发展的指导意见",
    "关于加强新时代高技能人才队伍建设的意见",
    "数字中国建设整体布局规划",
    "关于加快培育发展未来产业的意见",
    "关于推动平台经济规范健康持续发展的若干意见",
    "新能源汽车产业发展规划（2021-2035年）",
    "关于促进数据要素市场发展的若干措施",
]

ACADEMIC_TITLES = [
    "基于深度学习的在线招聘岗位需求分析与技能演化研究",
    "人工智能技术对劳动力市场结构性影响研究",
    "面向产业需求的大数据人才能力模型构建",
    "数字经济背景下新职业形成机制与演化规律研究",
    "技能偏向型技术进步与就业极化：基于中国数据的实证分析",
    "基于知识图谱的人岗匹配方法综述",
    "大语言模型在招聘领域的应用与挑战",
    "产业数字化转型中的技能需求变化研究",
]


def generate_demo_records(count: int = 200) -> List[UnifiedJobSchema]:
    """Generate a batch of synthetic job records covering all source types."""

    records = []
    now = datetime.now()

    for i in range(count):
        source_type = random.choice(list(DataSourceType))

        if source_type == DataSourceType.RECRUITMENT:
            rec = _make_recruitment_record(i, now)
        elif source_type == DataSourceType.ENTERPRISE:
            rec = _make_enterprise_record(i, now)
        elif source_type == DataSourceType.POLICY:
            rec = _make_policy_record(i, now)
        elif source_type == DataSourceType.ACADEMIC:
            rec = _make_academic_record(i, now)
        elif source_type == DataSourceType.INDUSTRY_REPORT:
            rec = _make_report_record(i, now)
        else:
            rec = _make_recruitment_record(i, now)

        records.append(rec)

    return records


def _random_date(days_back: int = 180) -> datetime:
    return datetime.now() - timedelta(days=random.randint(1, days_back))


def _pick_skills(n: int = 3) -> List[str]:
    n = min(n, len(SKILLS_POOL))
    return random.sample(SKILLS_POOL, n)


def _pick_abilities(n: int = 2) -> List[str]:
    n = min(n, len(ABILITIES_POOL))
    return random.sample(ABILITIES_POOL, n)


def _make_recruitment_record(idx: int, now: datetime) -> UnifiedJobSchema:
    company, industry = random.choice(COMPANIES)
    title = random.choice(JOB_TITLES)
    location = random.choice(LOCATIONS)
    skills = _pick_skills(random.randint(3, 6))
    abilities = _pick_abilities(random.randint(1, 3))
    desc_template = random.choice(JOB_DESCRIPTION_TEMPLATES)

    # Build unique context for this record
    duties = [
        f"负责{skills[0]}相关模块的设计与开发",
        f"优化{random.choice(['系统性能', '数据库查询', 'API响应时间', '代码结构'])}",
        f"参与{random.choice(['技术方案评审', '代码审查', '项目规划', '架构升级'])}",
        f"编写{random.choice(['单元测试', '集成测试', '技术文档', '设计文档'])}",
        f"跟踪{random.choice(['前沿技术发展', '行业动态', '竞品分析', '用户反馈'])}",
    ]
    random.shuffle(duties)

    salary_min = round(random.uniform(8, 35), 1)
    salary_max = round(salary_min + random.uniform(5, 25), 1)

    description = desc_template.format(
        title=title,
        company=company,
        industry=industry,
        location=location,
        salary=f"{salary_min:.0f}K-{salary_max:.0f}K",
        skill1=skills[0],
        skill2=skills[1] if len(skills) > 1 else "N/A",
        skill3=skills[2] if len(skills) > 2 else "N/A",
        skill4=skills[3] if len(skills) > 3 else "N/A",
        ability1=abilities[0] if abilities else "沟通能力",
        ability2=abilities[1] if len(abilities) > 1 else "学习能力",
        duty1=duties[0],
        duty2=duties[1],
        duty3=duties[2],
        exp=random.choice(["应届生", "1-3年", "3-5年", "5-10年"]),
        edu=random.choice(["本科", "硕士", "博士", "大专"]),
    )

    return UnifiedJobSchema(
        record_id=str(uuid.uuid4()),
        source_id=f"recruit_{idx:06d}",
        source_type=DataSourceType.RECRUITMENT,
        source_name=random.choice(["51job", "boss_zhipin", "lagou", "liepin"]),
        source_url=f"https://example.com/jobs/{idx}",
        job_title=title,
        job_title_raw=title,
        company_name=company,
        company_name_raw=f"{company}有限公司",
        industry=industry,
        location=location,
        location_raw=f"{location}市",
        job_description=description,
        salary_min=salary_min,
        salary_max=salary_max,
        experience_required=random.choice(["应届生", "1-3年", "3-5年", "5-10年", "经验不限"]),
        education_required=random.choice(["本科", "硕士", "博士", "大专"]),
        job_type=random.choice(["全职", "全职", "全职", "实习"]),
        skills_required=skills,
        skills_preferred=_pick_skills(random.randint(0, 3)),
        abilities=abilities,
        publish_date=_random_date(90),
        crawl_timestamp=now,
        data_format=DataFormat.SEMI_STRUCTURED,
    )


def _make_enterprise_record(idx: int, now: datetime) -> UnifiedJobSchema:
    company, industry = random.choice(COMPANIES)
    title = random.choice(JOB_TITLES)
    location = random.choice(LOCATIONS)
    skills = _pick_skills(random.randint(3, 6))
    abilities = _pick_abilities(random.randint(1, 3))
    desc_template = random.choice(JOB_DESCRIPTION_TEMPLATES)

    duties = [
        f"负责{skills[0]}相关模块的设计与开发",
        f"优化{random.choice(['系统架构', '数据流程', '部署效率', '团队协作'])}",
        f"参与{random.choice(['技术方案评审', '代码审查', '项目规划', '架构升级'])}",
        f"编写{random.choice(['技术文档', '设计文档', 'API文档'])}",
        f"跟踪{random.choice(['前沿技术发展', '行业动态', '竞品分析', '用户反馈'])}",
    ]
    random.shuffle(duties)

    salary_min = round(random.uniform(10, 40), 1)
    salary_max = round(salary_min + random.uniform(10, 30), 1)

    description = desc_template.format(
        title=title,
        company=company,
        industry=industry,
        location=location,
        salary=f"{salary_min:.0f}K-{salary_max:.0f}K",
        skill1=skills[0],
        skill2=skills[1] if len(skills) > 1 else "N/A",
        skill3=skills[2] if len(skills) > 2 else "N/A",
        skill4=skills[3] if len(skills) > 3 else "N/A",
        ability1=abilities[0] if abilities else "沟通能力",
        ability2=abilities[1] if len(abilities) > 1 else "学习能力",
        duty1=duties[0],
        duty2=duties[1],
        duty3=duties[2],
        exp=random.choice(["3-5年", "5-10年", "10年以上"]),
        edu=random.choice(["本科", "硕士", "博士"]),
    )

    return UnifiedJobSchema(
        record_id=str(uuid.uuid4()),
        source_id=f"ent_{idx:06d}",
        source_type=DataSourceType.ENTERPRISE,
        source_name=random.choice(["华为招聘", "腾讯招聘", "字节跳动", "阿里巴巴"]),
        source_url=f"https://career.example.com/position/{idx}",
        job_title=title,
        job_title_raw=title,
        company_name=company,
        company_name_raw=f"{company}",
        industry=industry,
        location=location,
        location_raw=location,
        job_description=description,
        salary_min=round(random.uniform(10, 40), 1),
        salary_max=round(random.uniform(20, 60), 1),
        experience_required=random.choice(["1-3年", "3-5年", "5-10年"]),
        education_required=random.choice(["本科", "硕士", "博士"]),
        job_type="全职",
        skills_required=skills,
        skills_preferred=_pick_skills(random.randint(0, 2)),
        abilities=abilities,
        publish_date=_random_date(60),
        crawl_timestamp=now,
        data_format=DataFormat.SEMI_STRUCTURED,
        extra={"department": random.choice(["技术部", "AI研究院", "数据平台部", "基础架构部"])},
    )


def _make_policy_record(idx: int, now: datetime) -> UnifiedJobSchema:
    title = random.choice(POLICY_TITLES)
    skills = _pick_skills(random.randint(2, 4))
    abilities = _pick_abilities(random.randint(1, 3))

    description = (
        f"【{title}】\n\n"
        f"为贯彻落实国家科技创新战略，推动新一代信息技术与实体经济深度融合，"
        f"现就加强{random.choice(['人工智能', '大数据', '云计算', '物联网'])}领域人才培养工作提出以下意见：\n\n"
        f"一、总体要求\n"
        f"坚持创新驱动发展战略，以提升自主创新能力为核心，"
        f"加快建设知识型、技能型、创新型劳动者大军。\n\n"
        f"二、重点任务\n"
        f"（一）完善职业技能培训体系，鼓励企业开展{skills[0]}、{skills[1]}等前沿技术培训。\n"
        f"（二）建立健全人才评价机制，将{abilities[0] if abilities else '创新能力'}纳入核心评价指标。\n"
        f"（三）推动产学研深度融合，支持高校与企业联合培养高层次人才。\n\n"
        f"三、保障措施\n"
        f"加大财政投入，完善配套政策，营造良好的人才发展环境。"
    )

    return UnifiedJobSchema(
        record_id=str(uuid.uuid4()),
        source_id=f"policy_{idx:06d}",
        source_type=DataSourceType.POLICY,
        source_name=random.choice(["中国政府网", "人社部", "科技部", "工信部"]),
        source_url=f"https://www.gov.cn/policy/{idx}.html",
        job_title=title,
        job_title_raw=title,
        company_name="政府/政策文件",
        company_name_raw="",
        industry=random.choice(["人工智能", "数字经济", "新能源", "智能制造", "大数据"]),
        location="全国",
        location_raw="全国",
        job_description=description,
        salary_min=None,
        salary_max=None,
        experience_required="",
        education_required="",
        job_type="",
        skills_required=skills,
        skills_preferred=[],
        abilities=abilities,
        publish_date=_random_date(365),
        crawl_timestamp=now,
        data_format=DataFormat.UNSTRUCTURED,
        extra={"doc_type": "policy"},
    )


def _make_academic_record(idx: int, now: datetime) -> UnifiedJobSchema:
    title = random.choice(ACADEMIC_TITLES)
    skills = _pick_skills(random.randint(2, 4))
    abilities = _pick_abilities(random.randint(1, 2))

    description = (
        f"论文标题：{title}\n\n"
        f"摘要：随着数字经济的快速发展，新兴技术对劳动力市场产生了深远影响。"
        f"本研究采用{random.choice(['自然语言处理', '深度学习', '计量经济学', '社交网络分析'])}方法，"
        f"基于大规模在线招聘数据，系统分析了{skills[0]}、{skills[1]}等相关技能的需求变化趋势。"
        f"研究发现，复合型人才需求显著增长，企业对于{abilities[0] if abilities else '创新能力'}的重视程度持续提升。"
        f"本文的研究成果对高校人才培养和劳动者技能提升具有重要参考价值。\n\n"
        f"关键词：{'; '.join(skills[:3])}；就业市场；技能需求；知识图谱"
    )

    return UnifiedJobSchema(
        record_id=str(uuid.uuid4()),
        source_id=f"academic_{idx:06d}",
        source_type=DataSourceType.ACADEMIC,
        source_name=random.choice(["知网", "ArXiv", "Semantic Scholar"]),
        source_url=f"https://scholar.example.com/paper/{idx}",
        job_title=title,
        job_title_raw=title,
        company_name=random.choice(["清华大学", "北京大学", "浙江大学", "上海交通大学", "中科院"]),
        company_name_raw="",
        industry=random.choice(["人工智能", "大数据", "数字经济", "教育科技"]),
        location="学术研究",
        location_raw="",
        job_description=description,
        salary_min=None,
        salary_max=None,
        experience_required="",
        education_required="",
        job_type="",
        skills_required=skills,
        skills_preferred=[],
        abilities=abilities,
        publish_date=_random_date(730),
        crawl_timestamp=now,
        data_format=DataFormat.UNSTRUCTURED,
        extra={"doc_type": "academic", "authors": random.choice(["张三", "李四", "王五", "赵六"])},
    )


def _make_report_record(idx: int, now: datetime) -> UnifiedJobSchema:
    title = random.choice([
        "2025年中国AI人才市场白皮书",
        "数字化转型中的人才缺口分析报告",
        "中国数字经济就业发展研究报告",
        "2025年薪酬趋势与人才流动报告",
        "新兴产业人才需求预测报告（2025-2030）",
        "中国科技创新人才发展报告",
    ])
    skills = _pick_skills(random.randint(2, 5))
    abilities = _pick_abilities(random.randint(1, 3))

    description = (
        f"【{title}】\n\n"
        f"核心发现：\n"
        f"1. 2025年，{random.choice(['人工智能', '大数据', '云计算'])}领域人才缺口达到{random.randint(50, 300)}万人。\n"
        f"2. 企业对{skills[0]}和{skills[1]}技能的需求同比增长{random.randint(30, 150)}%。\n"
        f"3. 复合型人才（技术+业务理解）薪酬溢价达到{random.randint(20, 50)}%。\n"
        f"4. {abilities[0] if abilities else '创新能力'}被评为2025年最重要的职场竞争力之一。\n"
        f"5. 新一线城市人才吸引力持续增强，杭州、成都、武汉成为AI人才净流入前三。\n\n"
        f"趋势预测：\n"
        f"预计未来3-5年，AIGC、大语言模型相关岗位将增长{random.randint(200, 500)}%，"
        f"传统编程岗位将向AI辅助开发方向转型。"
    )

    return UnifiedJobSchema(
        record_id=str(uuid.uuid4()),
        source_id=f"report_{idx:06d}",
        source_type=DataSourceType.INDUSTRY_REPORT,
        source_name=random.choice(["艾瑞咨询", "36氪研究院", "前瞻产业研究院", "德勤"]),
        source_url=f"https://report.example.com/{idx}",
        job_title=title,
        job_title_raw=title,
        company_name="",
        company_name_raw="",
        industry=random.choice(["人工智能", "大数据", "数字经济", "综合"]),
        location="中国",
        location_raw="中国",
        job_description=description,
        salary_min=None,
        salary_max=None,
        experience_required="",
        education_required="",
        job_type="",
        skills_required=skills,
        skills_preferred=[],
        abilities=abilities,
        publish_date=_random_date(180),
        crawl_timestamp=now,
        data_format=DataFormat.UNSTRUCTURED,
        extra={"doc_type": "industry_report", "emerging_roles": ["提示工程师", "AI训练师", "数据标注师"]},
    )
