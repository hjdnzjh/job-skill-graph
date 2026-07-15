#!/usr/bin/env python3
"""Generate taxonomy_neo4j.cypher from TAXONOMY_DESIGN.md data."""

import os

OUTPUT = os.path.join(os.path.dirname(__file__), "taxonomy_neo4j.cypher")

def w(f, s=""):
    f.write(s + "\n")

def header(f):
    w(f, "// =============================================================================")
    w(f, "// 岗位能力分类体系 — Neo4j 图数据库迁移脚本")
    w(f, "// =============================================================================")
    w(f, "// 版本: v1.0")
    w(f, "// 日期: 2026-07-15")
    w(f, "// 基于: TAXONOMY_DESIGN.md")
    w(f, "// 幂等性: 全部使用 MERGE (不用 CREATE), 可重复执行")
    w(f, "//")
    w(f, "// 执行方式:")
    w(f, "//   cypher-shell -u neo4j -p <password> -f taxonomy_neo4j.cypher")
    w(f, "//   或在 Neo4j Browser/Bloom 中逐段执行")
    w(f, "//")
    w(f, "// 包含以下分类体系:")
    w(f, "//   Section A — 约束与索引")
    w(f, "//   Section B — 岗位三层分类体系 (Domain->Category->Title)")
    w(f, "//   Section C — 技能四层分类体系 (Domain->Group->Type->Skill)")
    w(f, "//   Section D — 行业三层分类体系 (Sector->Division->Group->Industry)")
    w(f, "//   Section E — 能力三层分类体系 (Dimension->Cluster->Competency)")
    w(f, "//   Section F — 教育与经验有序化")
    w(f, "//   Section G — 现有节点属性回填 (JobTitle/Skill/Industry/Education/Experience)")
    w(f, "//   Section H — 跨体系关系 (岗位-能力映射)")
    w(f, "// =============================================================================")
    w(f)

# ============ DATA DEFINITIONS ============

JOB_DOMAINS = [
    ("DOM-01", "软件与算法开发", "负责软件开发、算法设计、系统架构等核心技术工作的职能领域，涵盖后端、前端、移动端、嵌入式等多方向开发。"),
    ("DOM-02", "数据与人工智能", "负责数据处理、分析、挖掘及人工智能模型研究、开发与应用的职能领域，涵盖大数据、机器学习、商业智能等方向。"),
    ("DOM-03", "基础设施与运维", "负责IT基础设施规划、建设、运维及云计算平台管理的职能领域，涵盖运维、网络、通信等方向。"),
    ("DOM-04", "产品与项目管理", "负责产品规划、需求管理、项目交付及技术团队管理的职能领域，涵盖产品管理、项目管理、技术管理方向。"),
    ("DOM-05", "质量与安全", "负责软件质量保障、测试体系及信息安全的职能领域，涵盖功能测试、性能测试、渗透测试、安全合规等方向。"),
    ("DOM-06", "新兴与交叉技术", "负责区块链、Web3、游戏开发、金融科技及其他前沿交叉技术领域开发与应用的职能领域。"),
]

JOB_CATEGORIES = [
    # DOM-01
    ("CAT-0101", "后端开发", "DOM-01", "负责服务端应用程序的设计、开发与维护，包括业务逻辑、数据访问、API接口等。", "2-02-10-01", "2512.1"),
    ("CAT-0102", "前端与全栈开发", "DOM-01", "负责Web前端界面开发及跨前后端的全流程开发，涵盖UI实现、交互逻辑、全栈整合。", "2-02-10-01", "2513.1"),
    ("CAT-0103", "移动开发", "DOM-01", "专责Android/iOS/跨平台移动端原生或混合应用程序开发。", "2-02-10-01", "2514.1"),
    ("CAT-0104", "架构设计", "DOM-01", "负责系统架构设计、技术选型、技术战略，指导团队技术方向。", "2-02-10-03", "2511.1"),
    ("CAT-0105", "嵌入式与物联网开发", "DOM-01", "面向硬件平台(MCU/SoC/FPGA)的固件、驱动及应用软件开发。", "2-02-10-04", "2519.3"),
    ("CAT-0106", "其他软件开发", "DOM-01", "跨领域或特定垂直方向(音视频、区块链、Web3等)的开发岗位。", "", ""),
    # DOM-02
    ("CAT-0201", "算法研究与AI模型", "DOM-02", "负责机器学习/深度学习模型的研究、设计、训练与优化，解决核心算法问题。", "2-02-10-02", "2519.6"),
    ("CAT-0202", "AI工程化与应用", "DOM-02", "将AI模型产品化、工程化部署，或基于LLM/GPT等大模型进行应用开发。", "", "2519.7"),
    ("CAT-0203", "大数据工程", "DOM-02", "负责大数据平台建设、数据处理流水线(ETL)、数据仓库设计与维护。", "2-02-10-02", "2521.1"),
    ("CAT-0204", "数据分析与商业智能", "DOM-02", "对业务数据进行分析、建模和可视化，为决策提供数据支撑。", "2-06-01-01", "3311.1"),
    # DOM-03
    ("CAT-0301", "运维与站点可靠性", "DOM-03", "负责生产环境运维、监控、故障处理，保障服务可用性(SLA)。", "2-02-10-05", "3512.1"),
    ("CAT-0302", "云计算与平台工程", "DOM-03", "负责云基础设施规划、云原生平台建设、自动化部署与弹性伸缩。", "2-02-10-05", "2529.2"),
    ("CAT-0303", "网络与通信工程", "DOM-03", "负责企业网络架构、通信协议实现、网络设备管理与优化。", "2-02-10-05", "2523.1"),
    # DOM-04
    ("CAT-0401", "产品管理", "DOM-04", "负责产品规划、需求定义、用户研究、产品生命周期管理。", "2-06-07-04", "2431.6"),
    ("CAT-0402", "项目管理", "DOM-04", "负责项目计划、进度跟踪、风险管控、资源协调与交付管理。", "2-06-03-01", "2412.1"),
    ("CAT-0403", "技术管理", "DOM-04", "负责技术团队管理、技术战略规划、跨团队协调与人才培养。", "1-05-01-01", "1330.2"),
    # DOM-05
    ("CAT-0501", "测试与质量保证", "DOM-05", "负责软件测试(功能/性能/安全/自动化)、缺陷管理、质量体系建立。", "2-02-10-06", "2519.4"),
    ("CAT-0502", "信息安全", "DOM-05", "负责信息安全体系建设、渗透测试、安全监控、应急响应与合规管理。", "2-02-10-07", "2529.5"),
    # DOM-06
    ("CAT-0601", "区块链与Web3", "DOM-06", "负责区块链底层开发、智能合约编写、DApp开发与链上数据分析。", "", "2519.8"),
    ("CAT-0602", "游戏开发", "DOM-06", "负责游戏客户端/服务端开发、引擎定制、渲染优化与玩法实现。", "2-09-06-04", "2519.9"),
    ("CAT-0603", "金融科技", "DOM-06", "负责量化交易系统、风控模型、支付系统等金融与技术的交叉领域。", "", "3312.1"),
    ("CAT-0604", "其他新兴岗位", "DOM-06", "LLM/大模型驱动的新型岗位(提示词工程师、AI训练师、AI伦理师等)的预留分类。", "", ""),
]

SKILL_DOMAINS = [
    ("SKD-01", "编程语言与框架", "涵盖所有编程语言、前端/后端/移动端框架、游戏引擎及图形多媒体工具。"),
    ("SKD-02", "数据存储与管理", "涵盖关系型数据库、非关系型数据库、大数据处理框架、消息队列及事件流平台。"),
    ("SKD-03", "人工智能与机器学习", "涵盖AI/ML框架、模型、应用领域、工程化工具及相关领域库。"),
    ("SKD-04", "云计算与基础设施", "涵盖云平台、容器编排、网络通信、操作系统及Web服务器等基础设施。"),
    ("SKD-05", "DevOps与工程效能", "涵盖CI/CD工具、构建系统、可观测性监控、配置管理及基础设施即代码工具。"),
    ("SKD-06", "测试、安全与质量", "涵盖软件测试、信息安全、代码与架构质量等领域工具与实践。"),
    ("SKD-07", "业务、产品与软技能", "涵盖产品工具、数据分析、管理方法、架构设计及业务领域知识。"),
    ("SKD-99", "其他", "未匹配新技能的临时存放区，待审核后重新归类。"),
]

SKILL_GROUPS = [
    # SKD-01
    ("GRP-0101", "后端编程语言", "SKD-01", "Java, Python, Go, C++, Rust, PHP, Ruby, Scala 等服务端编程语言。"),
    ("GRP-0102", "前端技术", "SKD-01", "JavaScript, TypeScript, HTML5, CSS3, React, Vue, Angular 等前端技术栈。"),
    ("GRP-0103", "后端框架", "SKD-01", "Spring, Django, Flask, Express, Laravel 等服务端开发框架。"),
    ("GRP-0104", "移动开发技术", "SKD-01", "Android SDK, iOS UIKit, Flutter, React Native 等移动端开发框架与工具。"),
    ("GRP-0105", "游戏与图形开发", "SKD-01", "Unity, Unreal, OpenGL, WebGL, FFmpeg, WebRTC 等游戏引擎与图形工具。"),
    # SKD-02
    ("GRP-0201", "关系型数据库", "SKD-02", "MySQL, PostgreSQL, Oracle, SQLite 等关系型数据库管理系统。"),
    ("GRP-0202", "非关系型数据库", "SKD-02", "MongoDB, Redis, Elasticsearch, HBase, ClickHouse 及向量数据库等 NoSQL 系统。"),
    ("GRP-0203", "大数据与流处理", "SKD-02", "Spark, Flink, Hadoop, Hive, Doris 等大数据计算及数据仓库技术。"),
    ("GRP-0204", "消息队列与事件流", "SKD-02", "Kafka, RabbitMQ, RocketMQ 等消息队列与事件流平台。"),
    # SKD-03
    ("GRP-0301", "AI/ML框架", "SKD-03", "TensorFlow, PyTorch, Keras, Scikit-learn, XGBoost 等AI/机器学习框架。"),
    ("GRP-0302", "AI/ML模型", "SKD-03", "Transformer, BERT, GPT, LLM, CNN, RNN, YOLO, Stable Diffusion 等模型架构。"),
    ("GRP-0303", "AI/ML应用领域", "SKD-03", "机器学习、深度学习、NLP、计算机视觉、数据挖掘、推荐系统等应用方向。"),
    ("GRP-0304", "AI/ML工程化", "SKD-03", "模型部署、CUDA、TensorRT、MLflow、Kubeflow、LangChain、RAG 等工程化工具。"),
    ("GRP-0305", "AI工具与库", "SKD-03", "OpenCV, jieba, spaCy, Kaldi, Matplotlib 等AI辅助工具与领域库。"),
    # SKD-04
    ("GRP-0401", "云平台", "SKD-04", "AWS, Azure, Google Cloud 等公有云及私有云平台服务。"),
    ("GRP-0402", "容器与编排", "SKD-04", "Docker, Kubernetes 等容器化及编排技术。"),
    ("GRP-0403", "网络与通信", "SKD-04", "TCP/IP, gRPC, GraphQL, WebSocket, Istio, Envoy, Consul 等网络与通信技术。"),
    ("GRP-0404", "系统与基础设施", "SKD-04", "Linux, Nginx, Gunicorn, ZooKeeper, Nacos, Harbor, Helix 等系统基础设施。"),
    # SKD-05
    ("GRP-0501", "CI/CD与构建", "SKD-05", "Jenkins, Maven, Gradle, CMake, SonarQube 等持续集成/构建/代码质量工具。"),
    ("GRP-0502", "可观测性与监控", "SKD-05", "Prometheus, Grafana, ELK, Jaeger 等监控、日志、追踪工具。"),
    ("GRP-0503", "配置与基础设施即代码", "SKD-05", "Terraform, Ansible, Helm 等IaC及配置管理工具。"),
    # SKD-06
    ("GRP-0601", "软件测试", "SKD-06", "自动化测试、性能测试、单元测试、Selenium、JMeter、Postman 等测试工具。"),
    ("GRP-0602", "信息安全", "SKD-06", "网络安全、渗透测试、密码学、WAF、SOC、ISO27001 等安全领域与工具。"),
    ("GRP-0603", "代码与架构质量", "SKD-06", "领域驱动设计、设计模式、代码重构等架构质量实践。"),
    # SKD-07
    ("GRP-0701", "产品与设计工具", "SKD-07", "Axure, Figma, Sketch, XMind 等产品原型与设计协作工具。"),
    ("GRP-0702", "数据分析与商业智能", "SKD-07", "Pandas, NumPy, Tableau, ECharts, Excel 等数据分析与可视化工具。"),
    ("GRP-0703", "管理与方法论", "SKD-07", "项目管理、敏捷开发、Scrum、风险管理、JIRA 等管理能力与方法论。"),
    ("GRP-0704", "产品能力", "SKD-07", "PRD、用户研究、竞品分析、需求分析、原型设计、用户体验等产品技能。"),
    ("GRP-0705", "架构与系统设计", "SKD-07", "微服务、MVVM、分布式、高并发、系统设计、金融科技等架构与领域知识。"),
    # SKD-99
    ("GRP-9901", "未分类", "SKD-99", "暂未匹配到标准分类体系的技能临时存放区。"),
]

SKILL_TYPES = [
    # GRP-0101
    ("T-01011", "主要后端语言", "GRP-0101"),
    ("T-01012", "脚本与其他语言", "GRP-0101"),
    # GRP-0102
    ("T-01021", "前端编程语言", "GRP-0102"),
    ("T-01022", "前端框架", "GRP-0102"),
    ("T-01023", "前端基础技术", "GRP-0102"),
    ("T-01024", "前端工具与运行时", "GRP-0102"),
    # GRP-0103
    ("T-01031", "Java生态框架", "GRP-0103"),
    ("T-01032", "Python生态框架", "GRP-0103"),
    ("T-01033", "其他后端框架", "GRP-0103"),
    # GRP-0104
    ("T-01041", "移动开发框架", "GRP-0104"),
    ("T-01042", "移动开发工具", "GRP-0104"),
    # GRP-0105
    ("T-01051", "游戏引擎", "GRP-0105"),
    ("T-01052", "图形与多媒体", "GRP-0105"),
    # GRP-0201
    ("T-02011", "SQL数据库", "GRP-0201"),
    # GRP-0202
    ("T-02021", "文档/键值数据库", "GRP-0202"),
    ("T-02022", "列存/搜索数据库", "GRP-0202"),
    ("T-02023", "向量数据库", "GRP-0202"),
    # GRP-0203
    ("T-02031", "大数据计算框架", "GRP-0203"),
    ("T-02032", "数据仓库", "GRP-0203"),
    # GRP-0204
    ("T-02041", "消息队列", "GRP-0204"),
    # GRP-0301
    ("T-03011", "深度学习框架", "GRP-0301"),
    ("T-03012", "机器学习框架", "GRP-0301"),
    # GRP-0302
    ("T-03021", "语言模型", "GRP-0302"),
    ("T-03022", "视觉模型", "GRP-0302"),
    ("T-03023", "传统ML模型", "GRP-0302"),
    # GRP-0303
    ("T-03031", "AI/ML应用领域", "GRP-0303"),
    # GRP-0304
    ("T-03041", "模型部署与优化", "GRP-0304"),
    ("T-03042", "MLOps工具", "GRP-0304"),
    ("T-03043", "LLM应用框架", "GRP-0304"),
    # GRP-0305
    ("T-03051", "AI工具与库", "GRP-0305"),
    # GRP-0401
    ("T-04011", "云平台", "GRP-0401"),
    # GRP-0402
    ("T-04021", "容器与编排", "GRP-0402"),
    # GRP-0403
    ("T-04031", "网络协议", "GRP-0403"),
    ("T-04032", "API协议", "GRP-0403"),
    ("T-04033", "服务网格", "GRP-0403"),
    # GRP-0404
    ("T-04041", "操作系统", "GRP-0404"),
    ("T-04042", "Web服务器", "GRP-0404"),
    ("T-04043", "存储与注册中心", "GRP-0404"),
    # GRP-0501
    ("T-05011", "CI/CD工具", "GRP-0501"),
    ("T-05012", "构建工具", "GRP-0501"),
    ("T-05013", "代码质量", "GRP-0501"),
    # GRP-0502
    ("T-05021", "监控工具", "GRP-0502"),
    ("T-05022", "日志与追踪", "GRP-0502"),
    ("T-05023", "前端监控", "GRP-0502"),
    # GRP-0503
    ("T-05031", "IaC工具", "GRP-0503"),
    ("T-05032", "配置管理", "GRP-0503"),
    ("T-05033", "容器编排辅助", "GRP-0503"),
    # GRP-0601
    ("T-06011", "测试领域", "GRP-0601"),
    ("T-06012", "测试工具", "GRP-0601"),
    ("T-06013", "安全测试", "GRP-0601"),
    # GRP-0602
    ("T-06021", "安全领域", "GRP-0602"),
    ("T-06022", "安全工具", "GRP-0602"),
    ("T-06023", "安全运营", "GRP-0602"),
    ("T-06024", "安全标准", "GRP-0602"),
    # GRP-0603
    ("T-06031", "架构质量", "GRP-0603"),
    # GRP-0701
    ("T-07011", "产品与设计工具", "GRP-0701"),
    # GRP-0702
    ("T-07021", "数据分析库", "GRP-0702"),
    ("T-07022", "数据可视化", "GRP-0702"),
    ("T-07023", "BI工具", "GRP-0702"),
    ("T-07024", "办公工具", "GRP-0702"),
    # GRP-0703
    ("T-07031", "管理能力", "GRP-0703"),
    ("T-07032", "方法论", "GRP-0703"),
    ("T-07033", "项目管理工具", "GRP-0703"),
    # GRP-0704
    ("T-07041", "产品能力", "GRP-0704"),
    # GRP-0705
    ("T-07051", "架构模式", "GRP-0705"),
    ("T-07052", "非功能需求", "GRP-0705"),
    ("T-07053", "领域知识", "GRP-0705"),
    # GRP-9901
    ("T-99011", "未分类", "GRP-9901"),
]

INDUSTRY_SECTORS = [
    ("C",  "制造业",       "GB/T 4754-2017 门类C: 制造业"),
    ("I",  "信息传输、软件和信息技术服务业", "GB/T 4754-2017 门类I: 信息传输、软件和信息技术服务业"),
    ("J",  "金融业",       "GB/T 4754-2017 门类J: 金融业"),
    ("M",  "科学研究和技术服务业", "GB/T 4754-2017 门类M: 科学研究和技术服务业"),
    ("P",  "教育",         "GB/T 4754-2017 门类P: 教育"),
    ("Q",  "卫生和社会工作", "GB/T 4754-2017 门类Q: 卫生和社会工作"),
    ("R",  "文化、体育和娱乐业", "GB/T 4754-2017 门类R: 文化、体育和娱乐业"),
]

INDUSTRY_DIVISIONS = [
    ("34", "通用设备制造业",                 "C"),
    ("35", "专用设备制造业",                 "C"),
    ("36", "汽车制造业",                     "C"),
    ("38", "电气机械和器材制造业",           "C"),
    ("39", "计算机、通信和其他电子设备制造业", "C"),
    ("40", "仪器仪表制造业",                 "C"),
    ("63", "电信、广播电视和卫星传输服务",   "I"),
    ("64", "互联网和相关服务",               "I"),
    ("65", "软件和信息技术服务业",           "I"),
    ("66", "货币金融服务",                   "J"),
    ("67", "资本市场服务",                   "J"),
    ("69", "其他金融业",                     "J"),
    ("73", "研究和试验发展",                 "M"),
    ("83", "教育",                           "P"),
    ("84", "卫生",                           "Q"),
    ("86", "娱乐业",                         "R"),
]

INDUSTRY_GROUPS = [
    ("361", "汽车整车制造",       "36"),
    ("384", "电池制造",           "38"),
    ("391", "计算机制造",         "39"),
    ("392", "通信设备制造",       "39"),
    ("397", "电子器件制造",       "39"),
    ("631", "电信",               "63"),
    ("642", "互联网信息服务",     "64"),
    ("643", "互联网平台",         "64"),
    ("645", "互联网数据服务",     "64"),
    ("651", "软件开发",           "65"),
    ("652", "集成电路设计",       "65"),
    ("654", "运行维护服务",       "65"),
    ("659", "其他信息技术服务业", "65"),
    ("832", "高等教育",           "83"),
    ("839", "其他教育",           "83"),
    ("841", "医院",               "84"),
    ("862", "数字内容服务",       "86"),
]

ABILITY_DIMENSIONS = [
    ("ABL-01", "技术能力", "编程、AI/ML、基础设施、安全等方面的专业技术能力。"),
    ("ABL-02", "业务能力", "产品需求分析、行业知识、市场分析等方面的业务能力。"),
    ("ABL-03", "管理能力", "项目管理、团队管理、战略规划等方面的管理能力。"),
    ("ABL-04", "软技能",   "沟通协作、思维学习、职业素养等方面的跨领域通用能力。"),
    ("ABL-05", "领域专项能力", "金融科技、医疗AI、自动驾驶等特定垂直领域的专项能力。"),
]

COMPETENCY_CLUSTERS = [
    # ABL-01
    ("CLS-0101", "编程与软件开发能力", "ABL-01", "代码编写调试、算法数据结构、系统设计架构、技术方案设计。"),
    ("CLS-0102", "数据与AI能力",       "ABL-01", "数据建模分析、机器学习建模、数据工程(ETL/数仓)、数据可视化。"),
    ("CLS-0103", "基础设施与运维能力", "ABL-01", "云基础设施管理、自动化运维(IaC)、故障诊断恢复、性能优化。"),
    ("CLS-0104", "安全与质量能力",     "ABL-01", "安全风险评估、渗透测试防御、测试策略设计、代码审查质量保证。"),
    # ABL-02
    ("CLS-0201", "产品与需求能力",   "ABL-02", "需求分析定义、用户研究画像、产品路线图规划、竞品市场分析。"),
    ("CLS-0202", "行业与应用能力",   "ABL-02", "行业知识(金融/医疗/教育/制造)、业务流程理解、法规合规、技术趋势洞察。"),
    # ABL-03
    ("CLS-0301", "项目管理能力",     "ABL-03", "项目计划控制、敏捷/Scrum管理、风险管理、资源协调分配。"),
    ("CLS-0302", "团队管理能力",     "ABL-03", "技术团队领导、绩效管理激励、冲突解决决策、跨部门协作。"),
    ("CLS-0303", "战略与规划能力",   "ABL-03", "技术战略制定、预算成本控制、组织架构设计。"),
    # ABL-04
    ("CLS-0401", "沟通与协作",       "ABL-04", "技术文档撰写、口头表达演讲、团队协作、跨职能沟通。"),
    ("CLS-0402", "思维与学习能力",   "ABL-04", "分析批判性思维、快速学习技术适应、问题解决、创新创造力。"),
    ("CLS-0403", "职业素养",         "ABL-04", "时间管理自我驱动、责任心抗压能力、职业道德保密、用户/客户为中心。"),
    # ABL-05
    ("CLS-0501", "金融科技专项",     "ABL-05", "量化策略开发、风控建模、金融产品设计。"),
    ("CLS-0502", "医疗AI专项",       "ABL-05", "医学影像分析、临床决策支持、医疗数据处理(HIPAA)。"),
    ("CLS-0503", "自动驾驶专项",     "ABL-05", "传感器融合、路径规划与控制、功能安全(ISO 26262)。"),
]

COMPETENCIES = [
    # CLS-0101
    ("CMP-010101", "代码编写与调试", "CLS-0101"),
    ("CMP-010102", "算法与数据结构", "CLS-0101"),
    ("CMP-010103", "系统设计与架构", "CLS-0101"),
    ("CMP-010104", "技术方案设计",   "CLS-0101"),
    # CLS-0102
    ("CMP-010201", "数据建模与分析", "CLS-0102"),
    ("CMP-010202", "机器学习建模",   "CLS-0102"),
    ("CMP-010203", "数据工程",       "CLS-0102"),
    ("CMP-010204", "数据可视化",     "CLS-0102"),
    # CLS-0103
    ("CMP-010301", "云基础设施管理",     "CLS-0103"),
    ("CMP-010302", "自动化运维",         "CLS-0103"),
    ("CMP-010303", "故障诊断与恢复",     "CLS-0103"),
    ("CMP-010304", "性能优化与容量规划", "CLS-0103"),
    # CLS-0104
    ("CMP-010401", "安全风险评估",     "CLS-0104"),
    ("CMP-010402", "渗透测试与防御",   "CLS-0104"),
    ("CMP-010403", "测试策略设计",     "CLS-0104"),
    ("CMP-010404", "代码审查与质量保证", "CLS-0104"),
    # CLS-0201
    ("CMP-020101", "需求分析与定义",   "CLS-0201"),
    ("CMP-020102", "用户研究与画像",   "CLS-0201"),
    ("CMP-020103", "产品路线图规划",   "CLS-0201"),
    ("CMP-020104", "竞品与市场分析",   "CLS-0201"),
    # CLS-0202
    ("CMP-020201", "行业知识",         "CLS-0202"),
    ("CMP-020202", "业务流程理解",     "CLS-0202"),
    ("CMP-020203", "法规与合规知识",   "CLS-0202"),
    ("CMP-020204", "技术趋势洞察",     "CLS-0202"),
    # CLS-0301
    ("CMP-030101", "项目计划与控制",   "CLS-0301"),
    ("CMP-030102", "敏捷/Scrum管理",   "CLS-0301"),
    ("CMP-030103", "风险管理",         "CLS-0301"),
    ("CMP-030104", "资源协调与分配",   "CLS-0301"),
    # CLS-0302
    ("CMP-030201", "技术团队领导",     "CLS-0302"),
    ("CMP-030202", "绩效管理与激励",   "CLS-0302"),
    ("CMP-030203", "冲突解决与决策",   "CLS-0302"),
    ("CMP-030204", "跨部门协作",       "CLS-0302"),
    # CLS-0303
    ("CMP-030301", "技术战略制定",     "CLS-0303"),
    ("CMP-030302", "预算与成本控制",   "CLS-0303"),
    ("CMP-030303", "组织架构设计",     "CLS-0303"),
    # CLS-0401
    ("CMP-040101", "技术文档撰写",     "CLS-0401"),
    ("CMP-040102", "口头表达与演讲",   "CLS-0401"),
    ("CMP-040103", "团队协作",         "CLS-0401"),
    ("CMP-040104", "跨职能沟通",       "CLS-0401"),
    # CLS-0402
    ("CMP-040201", "分析与批判性思维", "CLS-0402"),
    ("CMP-040202", "快速学习与技术适应", "CLS-0402"),
    ("CMP-040203", "问题解决能力",     "CLS-0402"),
    ("CMP-040204", "创新与创造力",     "CLS-0402"),
    # CLS-0403
    ("CMP-040301", "时间管理与自我驱动", "CLS-0403"),
    ("CMP-040302", "责任心与抗压能力",   "CLS-0403"),
    ("CMP-040303", "职业道德与保密意识", "CLS-0403"),
    ("CMP-040304", "以用户/客户为中心",  "CLS-0403"),
    # CLS-0501
    ("CMP-050101", "量化策略开发", "CLS-0501"),
    ("CMP-050102", "风控建模",     "CLS-0501"),
    ("CMP-050103", "金融产品设计", "CLS-0501"),
    # CLS-0502
    ("CMP-050201", "医学影像分析",     "CLS-0502"),
    ("CMP-050202", "临床决策支持",     "CLS-0502"),
    ("CMP-050203", "医疗数据处理",     "CLS-0502"),
    # CLS-0503
    ("CMP-050301", "传感器融合",       "CLS-0503"),
    ("CMP-050302", "路径规划与控制",   "CLS-0503"),
    ("CMP-050303", "功能安全",         "CLS-0503"),
]

# JobTitle keyword → Category mapping rules (ordered, first match wins)
# Format: (keyword_list, category_code, domain_code)
JOB_TITLE_KEYWORD_RULES = [
    # DOM-01 软件与算法开发
    (["Java", "Golang", "Go开发", "GO开发"], "CAT-0101", "DOM-01"),
    (["Python", "PYTHON"], "CAT-0101", "DOM-01"),
    (["C++", "C/C++", "CPP"], "CAT-0101", "DOM-01"),
    (["PHP"], "CAT-0101", "DOM-01"),
    (["后端", "服务端"], "CAT-0101", "DOM-01"),
    (["前端", "web前端", "Web前端", "WEB前端", "H5"], "CAT-0102", "DOM-01"),
    (["全栈"], "CAT-0102", "DOM-01"),
    (["Android", "安卓", "android"], "CAT-0103", "DOM-01"),
    (["iOS", "ios", "IOS"], "CAT-0103", "DOM-01"),
    (["移动端", "移动开发"], "CAT-0103", "DOM-01"),
    (["Flutter", "React Native", "RN开发"], "CAT-0103", "DOM-01"),
    (["架构师", "架构"], "CAT-0104", "DOM-01"),
    (["技术总监", "CTO"], "CAT-0104", "DOM-01"),
    (["嵌入式"], "CAT-0105", "DOM-01"),
    (["物联网", "IOT", "IoT"], "CAT-0105", "DOM-01"),
    (["驱动开发"], "CAT-0105", "DOM-01"),
    (["音视频"], "CAT-0106", "DOM-01"),
    (["软件开发", "软件工程师"], "CAT-0106", "DOM-01"),

    # DOM-02 数据与人工智能
    (["算法工程师", "算法"], "CAT-0201", "DOM-02"),
    (["机器学习"], "CAT-0201", "DOM-02"),
    (["深度学习"], "CAT-0201", "DOM-02"),
    (["NLP", "自然语言"], "CAT-0201", "DOM-02"),
    (["计算机视觉", "CV算法"], "CAT-0201", "DOM-02"),
    (["人工智能", "AI工程师", "AI应用"], "CAT-0202", "DOM-02"),
    (["提示词", "Prompt"], "CAT-0202", "DOM-02"),
    (["MLOps", "MLOPS"], "CAT-0202", "DOM-02"),
    (["AIGC"], "CAT-0202", "DOM-02"),
    (["大数据", "数据开发", "数据平台", "ETL"], "CAT-0203", "DOM-02"),
    (["数据仓库", "数仓"], "CAT-0203", "DOM-02"),
    (["数据分析", "数据分析师"], "CAT-0204", "DOM-02"),
    (["数据科学", "数据科学家"], "CAT-0204", "DOM-02"),
    (["商业分析", "BA", "商业智能", "BI工程师", "BI "], "CAT-0204", "DOM-02"),

    # DOM-03 基础设施与运维
    (["运维", "SRE", "sre"], "CAT-0301", "DOM-03"),
    (["系统管理员"], "CAT-0301", "DOM-03"),
    (["云计算", "云平台", "云原生"], "CAT-0302", "DOM-03"),
    (["平台工程", "DevOps", "DEVOPS", "devops"], "CAT-0302", "DOM-03"),
    (["网络工程师", "网络"], "CAT-0303", "DOM-03"),
    (["通信工程师", "通信"], "CAT-0303", "DOM-03"),

    # DOM-04 产品与项目管理
    (["产品经理", "产品总监", "产品VP", "产品负责人"], "CAT-0401", "DOM-04"),
    (["产品"], "CAT-0401", "DOM-04"),
    (["项目经理", "项目助理", "项目主管"], "CAT-0402", "DOM-04"),
    (["敏捷教练", "Scrum Master", "SCRUM"], "CAT-0402", "DOM-04"),
    (["PMO", "pmo"], "CAT-0402", "DOM-04"),
    (["技术经理", "研发总监", "研发经理"], "CAT-0403", "DOM-04"),
    (["技术VP", "技术副总"], "CAT-0403", "DOM-04"),

    # DOM-05 质量与安全
    (["测试", "QA", "qa", "Qa"], "CAT-0501", "DOM-05"),
    (["质量", "品控"], "CAT-0501", "DOM-05"),
    (["安全工程师", "安全架构", "安全"], "CAT-0502", "DOM-05"),
    (["渗透", "渗透测试"], "CAT-0502", "DOM-05"),
    (["数据安全"], "CAT-0502", "DOM-05"),

    # DOM-06 新兴与交叉技术
    (["区块链", "web3", "Web3", "WEB3", "智能合约", "DApp"], "CAT-0601", "DOM-06"),
    (["游戏开发", "游戏", "Unity", "UNITY", "Unreal", "UNREAL"], "CAT-0602", "DOM-06"),
    (["量化", "Quant", "quant"], "CAT-0603", "DOM-06"),
    (["金融科技", "FinTech", "fintech"], "CAT-0603", "DOM-06"),
    (["数据标注", "标注师", "AI训练师", "训练师"], "CAT-0604", "DOM-06"),
]

# Existing Industry node name → GB/T mapping
INDUSTRY_GB_MAPPING = [
    ("互联网/IT",   "I", "信息传输、软件和信息技术服务业", "64", "互联网和相关服务",             "645", "软件开发"),
    ("人工智能",     "I", "信息传输、软件和信息技术服务业", "65", "软件和信息技术服务业",         "659", "其他信息技术服务业"),
    ("通信/电子",   "C", "制造业",                         "39", "计算机、通信和其他电子设备制造业", "392", "通信设备制造"),
    ("金融",         "J", "金融业",                         "66", "货币金融服务",                 "",   ""),
    ("金融科技",     "J", "金融业",                         "69", "其他金融业",                   "",   ""),
    ("教育/培训",   "P", "教育",                           "83", "教育",                         "839", "其他教育"),
    ("医疗健康",     "Q", "卫生和社会工作",                 "84", "卫生",                         "841", "医院"),
    ("智能制造",     "C", "制造业",                         "35", "专用设备制造业",               "",   ""),
    ("汽车/出行",   "C", "制造业",                         "36", "汽车制造业",                   "361", "汽车整车制造"),
    ("电商/零售",   "I", "信息传输、软件和信息技术服务业", "64", "互联网和相关服务",             "643", "互联网平台"),
    ("游戏/娱乐",   "R", "文化、体育和娱乐业",             "86", "娱乐业",                       "862", "数字内容服务"),
    ("半导体/集成电路", "C", "制造业",                     "39", "计算机、通信和其他电子设备制造业", "397", "电子器件制造"),
    ("新能源",       "C", "制造业",                         "38", "电气机械和器材制造业",         "384", "电池制造"),
    ("云计算",       "I", "信息传输、软件和信息技术服务业", "64", "互联网和相关服务",             "645", "互联网数据服务"),
]

# Education ordering
EDUCATION_ORDERED = [
    ("学历不限",        0),
    ("高中/中专及以下", 1),
    ("大专",            2),
    ("本科",            3),
    ("硕士",            4),
    ("博士",            5),
    ("博士后",          6),
]

# Experience ordering
EXPERIENCE_ORDERED = [
    ("经验不限",    0, 0.0, 99.0),
    ("应届生",      1, 0.0, 0.0),
    ("1年以下",     2, 0.0, 1.0),
    ("1-3年",       3, 1.0, 3.0),
    ("3-5年",       4, 3.0, 5.0),
    ("5-10年",      5, 5.0, 10.0),
    ("10年以上",    6, 10.0, 99.0),
]

# ============ SCRIPT GENERATION ============

def generate(fp):
    f = open(fp, "w", encoding="utf-8")
    header(f)

    # ---- Section A ----
    w(f, "// =============================================================================")
    w(f, "// SECTION A: CONSTRAINTS & INDEXES")
    w(f, "// =============================================================================")
    w(f)
    w(f, "// --- Job taxonomy constraints ---")
    w(f, "CREATE CONSTRAINT job_domain_code_unique IF NOT EXISTS")
    w(f, "FOR (n:JobDomain) REQUIRE n.code IS UNIQUE;")
    w(f)
    w(f, "CREATE CONSTRAINT job_category_code_unique IF NOT EXISTS")
    w(f, "FOR (n:JobCategory) REQUIRE n.code IS UNIQUE;")
    w(f)
    w(f, "// --- Skill taxonomy constraints ---")
    w(f, "CREATE CONSTRAINT skill_domain_code_unique IF NOT EXISTS")
    w(f, "FOR (n:SkillDomain) REQUIRE n.code IS UNIQUE;")
    w(f)
    w(f, "CREATE CONSTRAINT skill_group_code_unique IF NOT EXISTS")
    w(f, "FOR (n:SkillGroup) REQUIRE n.code IS UNIQUE;")
    w(f)
    w(f, "CREATE CONSTRAINT skill_type_code_unique IF NOT EXISTS")
    w(f, "FOR (n:SkillType) REQUIRE n.code IS UNIQUE;")
    w(f)
    w(f, "// --- Industry taxonomy constraints ---")
    w(f, "CREATE CONSTRAINT industry_sector_code_unique IF NOT EXISTS")
    w(f, "FOR (n:IndustrySector) REQUIRE n.code IS UNIQUE;")
    w(f)
    w(f, "CREATE CONSTRAINT industry_division_code_unique IF NOT EXISTS")
    w(f, "FOR (n:IndustryDivision) REQUIRE n.code IS UNIQUE;")
    w(f)
    w(f, "CREATE CONSTRAINT industry_group_code_unique IF NOT EXISTS")
    w(f, "FOR (n:IndustryGroup) REQUIRE n.code IS UNIQUE;")
    w(f)
    w(f, "// --- Ability taxonomy constraints ---")
    w(f, "CREATE CONSTRAINT ability_dimension_code_unique IF NOT EXISTS")
    w(f, "FOR (n:AbilityDimension) REQUIRE n.code IS UNIQUE;")
    w(f)
    w(f, "CREATE CONSTRAINT competency_cluster_code_unique IF NOT EXISTS")
    w(f, "FOR (n:CompetencyCluster) REQUIRE n.code IS UNIQUE;")
    w(f)
    w(f, "CREATE CONSTRAINT competency_code_unique IF NOT EXISTS")
    w(f, "FOR (n:Competency) REQUIRE n.code IS UNIQUE;")
    w(f)
    w(f, "// --- Indexes for existing node attribute lookups ---")
    w(f, "CREATE INDEX job_title_domain_idx   IF NOT EXISTS FOR (n:JobTitle)  ON (n.domain_code);")
    w(f, "CREATE INDEX job_title_category_idx IF NOT EXISTS FOR (n:JobTitle)  ON (n.category_code);")
    w(f, "CREATE INDEX skill_domain_idx       IF NOT EXISTS FOR (s:Skill)     ON (s.domain_code);")
    w(f, "CREATE INDEX skill_group_idx        IF NOT EXISTS FOR (s:Skill)     ON (s.group_code);")
    w(f, "CREATE INDEX industry_sector_idx    IF NOT EXISTS FOR (i:Industry)  ON (i.sector_code);")
    w(f, "CREATE INDEX industry_division_idx  IF NOT EXISTS FOR (i:Industry)  ON (i.division_code);")
    w(f)

    # ---- Section B ----
    w(f, "// =============================================================================")
    w(f, "// SECTION B: JOB TAXONOMY (3-level: Domain -> Category -> Title)")
    w(f, "// =============================================================================")
    w(f)
    w(f, "// --- B.1 Create JobDomain nodes ---")
    w(f, "UNWIND [")
    for i, (code, name, desc) in enumerate(JOB_DOMAINS):
        comma = "," if i < len(JOB_DOMAINS) - 1 else ""
        desc_escaped = desc.replace("'", "\\'")
        w(f, f"  {{code:'{code}', name:'{name}', description:'{desc_escaped}'}}{comma}")
    w(f, "] AS row")
    w(f, "MERGE (d:JobDomain {code: row.code})")
    w(f, "SET d.name = row.name,")
    w(f, "    d.description = row.description,")
    w(f, "    d.taxonomy_version = '1.0',")
    w(f, "    d.standard_ref = 'GB/T 6565-2015';")
    w(f)

    w(f, "// --- B.2 Create JobCategory nodes and link to JobDomain ---")
    w(f, "UNWIND [")
    for i, (code, name, domain_code, desc, gb_code, esco_code) in enumerate(JOB_CATEGORIES):
        comma = "," if i < len(JOB_CATEGORIES) - 1 else ""
        desc_escaped = desc.replace("'", "\\'")
        w(f, f"  {{code:'{code}', name:'{name}', domain_code:'{domain_code}', description:'{desc_escaped}', gb_code:'{gb_code}', esco_code:'{esco_code}'}}{comma}")
    w(f, "] AS row")
    w(f, "MERGE (c:JobCategory {code: row.code})")
    w(f, "SET c.name = row.name,")
    w(f, "    c.description = row.description,")
    w(f, "    c.gb_code = row.gb_code,")
    w(f, "    c.esco_code = row.esco_code,")
    w(f, "    c.taxonomy_version = '1.0'")
    w(f, "WITH c, row")
    w(f, "MATCH (d:JobDomain {code: row.domain_code})")
    w(f, "MERGE (c)-[:BELONGS_TO_DOMAIN]->(d);")
    w(f)

    # ---- Section C ----
    w(f, "// =============================================================================")
    w(f, "// SECTION C: SKILL TAXONOMY (4-level: Domain -> Group -> Type -> Skill)")
    w(f, "// =============================================================================")
    w(f)
    w(f, "// --- C.1 Create SkillDomain nodes ---")
    w(f, "UNWIND [")
    for i, (code, name, desc) in enumerate(SKILL_DOMAINS):
        comma = "," if i < len(SKILL_DOMAINS) - 1 else ""
        desc_escaped = desc.replace("'", "\\'")
        w(f, f"  {{code:'{code}', name:'{name}', description:'{desc_escaped}'}}{comma}")
    w(f, "] AS row")
    w(f, "MERGE (d:SkillDomain {code: row.code})")
    w(f, "SET d.name = row.name,")
    w(f, "    d.description = row.description,")
    w(f, "    d.taxonomy_version = '1.0',")
    w(f, "    d.standard_ref = 'ESCO v1.2';")
    w(f)

    w(f, "// --- C.2 Create SkillGroup nodes and link to SkillDomain ---")
    w(f, "UNWIND [")
    for i, (code, name, domain_code, desc) in enumerate(SKILL_GROUPS):
        comma = "," if i < len(SKILL_GROUPS) - 1 else ""
        desc_escaped = desc.replace("'", "\\'")
        w(f, f"  {{code:'{code}', name:'{name}', domain_code:'{domain_code}', description:'{desc_escaped}'}}{comma}")
    w(f, "] AS row")
    w(f, "MERGE (g:SkillGroup {code: row.code})")
    w(f, "SET g.name = row.name,")
    w(f, "    g.description = row.description,")
    w(f, "    g.taxonomy_version = '1.0'")
    w(f, "WITH g, row")
    w(f, "MATCH (d:SkillDomain {code: row.domain_code})")
    w(f, "MERGE (g)-[:BELONGS_TO_DOMAIN]->(d);")
    w(f)

    w(f, "// --- C.3 Create SkillType nodes and link to SkillGroup ---")
    w(f, "UNWIND [")
    for i, (code, name, group_code) in enumerate(SKILL_TYPES):
        comma = "," if i < len(SKILL_TYPES) - 1 else ""
        w(f, f"  {{code:'{code}', name:'{name}', group_code:'{group_code}'}}{comma}")
    w(f, "] AS row")
    w(f, "MERGE (t:SkillType {code: row.code})")
    w(f, "SET t.name = row.name,")
    w(f, "    t.taxonomy_version = '1.0'")
    w(f, "WITH t, row")
    w(f, "MATCH (g:SkillGroup {code: row.group_code})")
    w(f, "MERGE (t)-[:BELONGS_TO_GROUP]->(g);")
    w(f)

    # ---- Section D ----
    w(f, "// =============================================================================")
    w(f, "// SECTION D: INDUSTRY TAXONOMY (3-level: Sector -> Division -> Group)")
    w(f, "// =============================================================================")
    w(f)
    w(f, "// --- D.1 Create IndustrySector nodes ---")
    w(f, "UNWIND [")
    for i, (code, name, desc) in enumerate(INDUSTRY_SECTORS):
        comma = "," if i < len(INDUSTRY_SECTORS) - 1 else ""
        desc_escaped = desc.replace("'", "\\'")
        w(f, f"  {{code:'{code}', name:'{name}', description:'{desc_escaped}'}}{comma}")
    w(f, "] AS row")
    w(f, "MERGE (s:IndustrySector {code: row.code})")
    w(f, "SET s.name = row.name,")
    w(f, "    s.description = row.description,")
    w(f, "    s.taxonomy_version = '1.0',")
    w(f, "    s.standard_ref = 'GB/T 4754-2017';")
    w(f)

    w(f, "// --- D.2 Create IndustryDivision nodes and link to IndustrySector ---")
    w(f, "UNWIND [")
    for i, (code, name, sector_code) in enumerate(INDUSTRY_DIVISIONS):
        comma = "," if i < len(INDUSTRY_DIVISIONS) - 1 else ""
        w(f, f"  {{code:'{code}', name:'{name}', sector_code:'{sector_code}'}}{comma}")
    w(f, "] AS row")
    w(f, "MERGE (d:IndustryDivision {code: row.code})")
    w(f, "SET d.name = row.name,")
    w(f, "    d.taxonomy_version = '1.0'")
    w(f, "WITH d, row")
    w(f, "MATCH (s:IndustrySector {code: row.sector_code})")
    w(f, "MERGE (d)-[:BELONGS_TO_SECTOR]->(s);")
    w(f)

    w(f, "// --- D.3 Create IndustryGroup nodes and link to IndustryDivision ---")
    w(f, "UNWIND [")
    for i, (code, name, division_code) in enumerate(INDUSTRY_GROUPS):
        comma = "," if i < len(INDUSTRY_GROUPS) - 1 else ""
        w(f, f"  {{code:'{code}', name:'{name}', division_code:'{division_code}'}}{comma}")
    w(f, "] AS row")
    w(f, "MERGE (g:IndustryGroup {code: row.code})")
    w(f, "SET g.name = row.name,")
    w(f, "    g.taxonomy_version = '1.0'")
    w(f, "WITH g, row")
    w(f, "MATCH (d:IndustryDivision {code: row.division_code})")
    w(f, "MERGE (g)-[:BELONGS_TO_DIVISION]->(d);")
    w(f)

    # ---- Section E ----
    w(f, "// =============================================================================")
    w(f, "// SECTION E: ABILITY TAXONOMY (3-level: Dimension -> Cluster -> Competency)")
    w(f, "// =============================================================================")
    w(f)
    w(f, "// --- E.1 Create AbilityDimension nodes ---")
    w(f, "UNWIND [")
    for i, (code, name, desc) in enumerate(ABILITY_DIMENSIONS):
        comma = "," if i < len(ABILITY_DIMENSIONS) - 1 else ""
        desc_escaped = desc.replace("'", "\\'")
        w(f, f"  {{code:'{code}', name:'{name}', description:'{desc_escaped}'}}{comma}")
    w(f, "] AS row")
    w(f, "MERGE (d:AbilityDimension {code: row.code})")
    w(f, "SET d.name = row.name,")
    w(f, "    d.description = row.description,")
    w(f, "    d.taxonomy_version = '1.0',")
    w(f, "    d.standard_ref = \"O*NET Content Model\";")
    w(f)

    w(f, "// --- E.2 Create CompetencyCluster nodes and link to AbilityDimension ---")
    w(f, "UNWIND [")
    for i, (code, name, dim_code, desc) in enumerate(COMPETENCY_CLUSTERS):
        comma = "," if i < len(COMPETENCY_CLUSTERS) - 1 else ""
        desc_escaped = desc.replace("'", "\\'")
        w(f, f"  {{code:'{code}', name:'{name}', dim_code:'{dim_code}', description:'{desc_escaped}'}}{comma}")
    w(f, "] AS row")
    w(f, "MERGE (c:CompetencyCluster {code: row.code})")
    w(f, "SET c.name = row.name,")
    w(f, "    c.description = row.description,")
    w(f, "    c.taxonomy_version = '1.0'")
    w(f, "WITH c, row")
    w(f, "MATCH (d:AbilityDimension {code: row.dim_code})")
    w(f, "MERGE (c)-[:BELONGS_TO_DIMENSION]->(d);")
    w(f)

    w(f, "// --- E.3 Create Competency nodes and link to CompetencyCluster ---")
    w(f, "UNWIND [")
    for i, (code, name, cluster_code) in enumerate(COMPETENCIES):
        comma = "," if i < len(COMPETENCIES) - 1 else ""
        w(f, f"  {{code:'{code}', name:'{name}', cluster_code:'{cluster_code}'}}{comma}")
    w(f, "] AS row")
    w(f, "MERGE (c:Competency {code: row.code})")
    w(f, "SET c.name = row.name,")
    w(f, "    c.taxonomy_version = '1.0'")
    w(f, "WITH c, row")
    w(f, "MATCH (cl:CompetencyCluster {code: row.cluster_code})")
    w(f, "MERGE (c)-[:BELONGS_TO_CLUSTER]->(cl);")
    w(f)

    # ---- Section F ----
    w(f, "// =============================================================================")
    w(f, "// SECTION F: EDUCATION & EXPERIENCE ORDERING")
    w(f, "// =============================================================================")
    w(f)
    w(f, "// --- F.1 Education ordered levels ---")
    w(f, "// Updates existing Education nodes with ordinal integer ranking (0=不限 ~ 6=博士后)")
    for name, ordinal in EDUCATION_ORDERED:
        w(f, f"MATCH (e:Education {{name: '{name}'}})")
        w(f, f"SET e.ordinal = {ordinal};")
        w(f)
    w(f, "// --- F.2 Experience ordered levels ---")
    w(f, "// Updates existing Experience nodes with ordinal, min_years, max_years")
    for name, ordinal, min_y, max_y in EXPERIENCE_ORDERED:
        min_str = str(min_y) if min_y != int(min_y) else str(int(min_y))
        max_str = str(max_y) if max_y != int(max_y) else str(int(max_y))
        w(f, f"MATCH (e:Experience {{name: '{name}'}})")
        w(f, f"SET e.ordinal = {ordinal},")
        w(f, f"    e.min_years = {min_str},")
        w(f, f"    e.max_years = {max_str};")
        w(f)

    # ---- Section G ----
    w(f, "// =============================================================================")
    w(f, "// SECTION G: EXISTING NODE ATTRIBUTE BACKFILL")
    w(f, "// =============================================================================")
    w(f)
    w(f, "// --- G.1 JobTitle -> JobCategory keyword-based classification ---")
    w(f, "// Uses CONTAINS-based matching rules. Order matters: first match wins.")
    w(f, "// Unmatched job titles remain unclassified (can be handled manually).")
    w(f)

    # For each keyword rule, generate a MATCH + MERGE block
    for keywords, cat_code, dom_code in JOB_TITLE_KEYWORD_RULES:
        conditions = " OR ".join([f"t.name CONTAINS '{kw}'" for kw in keywords])
        w(f, f"MATCH (t:JobTitle)")
        w(f, f"WHERE ({conditions})")
        w(f, f"  AND t.category_code IS NULL")
        w(f, f"MATCH (c:JobCategory {{code: '{cat_code}'}})")
        w(f, f"MERGE (t)-[:BELONGS_TO_CATEGORY]->(c)")
        w(f, f"SET t.domain_code = '{dom_code}',")
        w(f, f"    t.domain_name = c.name,")
        w(f, f"    t.category_code = '{cat_code}';")
        w(f)

    w(f, "// --- G.2 JobTitle: relabel unmatched as 'Unclassified' in category_code ---")
    w(f, "MATCH (t:JobTitle)")
    w(f, "WHERE t.category_code IS NULL")
    w(f, "SET t.category_code = 'UNCLASSIFIED',")
    w(f, "    t.domain_code = 'UNCLASSIFIED';")
    w(f)

    w(f, "// --- G.3 Industry -> GB/T 4754 mapping ---")
    w(f, "// Maps existing Industry node names to GB/T 4754-2017 codes")
    for ind_name, sec_code, sec_name, div_code, div_name, grp_code, grp_name in INDUSTRY_GB_MAPPING:
        w(f, f"MATCH (i:Industry {{name: '{ind_name}'}})")
        w(f, f"SET i.sector_code = '{sec_code}',")
        w(f, f"    i.sector_name = '{sec_name}',")
        w(f, f"    i.division_code = '{div_code}',")
        w(f, f"    i.division_name = '{div_name}',")
        if grp_code:
            w(f, f"    i.group_code = '{grp_code}',")
            w(f, f"    i.group_name = '{grp_name}',")
        else:
            w(f, f"    i.group_code = '',")
            w(f, f"    i.group_name = '',")
        w(f, f"    i.gb_code = '{sec_code}-{div_code}" + (f"-{grp_code}" if grp_code else "") + "';")
        w(f, f"WITH i")
        w(f, f"MATCH (s:IndustrySector {{code: '{sec_code}'}})")
        w(f, f"MERGE (i)-[:BELONGS_TO_SECTOR]->(s);")
        w(f)

    w(f, "// --- G.4 Industry: link to IndustryDivision ---")
    for ind_name, sec_code, sec_name, div_code, div_name, grp_code, grp_name in INDUSTRY_GB_MAPPING:
        w(f, f"MATCH (i:Industry {{name: '{ind_name}'}})")
        w(f, f"MATCH (d:IndustryDivision {{code: '{div_code}'}})")
        w(f, f"MERGE (i)-[:BELONGS_TO_DIVISION]->(d);")
        w(f)

    w(f, "// --- G.5 Industry: link to IndustryGroup (when group_code is present) ---")
    for ind_name, sec_code, sec_name, div_code, div_name, grp_code, grp_name in INDUSTRY_GB_MAPPING:
        if grp_code:
            w(f, f"MATCH (i:Industry {{name: '{ind_name}'}})")
            w(f, f"MATCH (g:IndustryGroup {{code: '{grp_code}'}})")
            w(f, f"MERGE (i)-[:BELONGS_TO_GROUP]->(g);")
            w(f)

    w(f, "// --- G.6 Unmatched Industry nodes: set sector_code to UNCLASSIFIED ---")
    w(f, "MATCH (i:Industry)")
    w(f, "WHERE i.sector_code IS NULL")
    w(f, "SET i.sector_code = 'UNCLASSIFIED';")
    w(f)

    w(f, "// --- G.7 Skill nodes: basic domain/group classification by old category name ---")
    w(f, "// Programming language skills -> SKD-01")
    w(f, "MATCH (s:Skill)")
    w(f, "WHERE s.category IN ['编程语言', '脚本语言', '前端编程语言']")
    w(f, "SET s.domain_code = 'SKD-01', s.domain_name = '编程语言与框架';")
    w(f)
    w(f, "// Frontend skills -> SKD-01")
    w(f, "MATCH (s:Skill)")
    w(f, "WHERE s.category IN ['前端框架', '前端技术', '前端工具', '运行时']")
    w(f, "SET s.domain_code = 'SKD-01', s.domain_name = '编程语言与框架';")
    w(f)
    w(f, "// Backend framework skills -> SKD-01")
    w(f, "MATCH (s:Skill)")
    w(f, "WHERE s.category IN ['后端框架', '网络框架', 'C++库', '程序基础']")
    w(f, "SET s.domain_code = 'SKD-01', s.domain_name = '编程语言与框架';")
    w(f)
    w(f, "// Mobile development -> SKD-01")
    w(f, "MATCH (s:Skill)")
    w(f, "WHERE s.category IN ['移动开发框架', '移动开发工具', 'UI框架']")
    w(f, "SET s.domain_code = 'SKD-01', s.domain_name = '编程语言与框架';")
    w(f)
    w(f, "// Database skills -> SKD-02")
    w(f, "MATCH (s:Skill)")
    w(f, "WHERE s.category IN ['关系型数据库', 'NoSQL', '数据库', '消息队列', '大数据', '数据领域', '数据仓库']")
    w(f, "SET s.domain_code = 'SKD-02', s.domain_name = '数据存储与管理';")
    w(f)
    w(f, "// AI/ML skills -> SKD-03")
    w(f, "MATCH (s:Skill)")
    w(f, "WHERE s.category IN ['AI框架', 'AI模型', 'AI领域', 'AI工具', 'AI加速', 'AI推理', '视觉库']")
    w(f, "SET s.domain_code = 'SKD-03', s.domain_name = '人工智能与机器学习';")
    w(f)
    w(f, "// Cloud & Infra skills -> SKD-04")
    w(f, "MATCH (s:Skill)")
    w(f, "WHERE s.category IN ['云平台', '容器', '网络协议', '通信协议', '操作系统', 'Web服务器', 'API协议']")
    w(f, "SET s.domain_code = 'SKD-04', s.domain_name = '云计算与基础设施';")
    w(f)
    w(f, "// DevOps skills -> SKD-05")
    w(f, "MATCH (s:Skill)")
    w(f, "WHERE s.category IN ['CI/CD', '构建工具', '版本控制', 'IDE工具', '监控工具', '配置管理', 'IaC']")
    w(f, "SET s.domain_code = 'SKD-05', s.domain_name = 'DevOps与工程效能';")
    w(f)
    w(f, "// Testing & Security skills -> SKD-06")
    w(f, "MATCH (s:Skill)")
    w(f, "WHERE s.category IN ['测试领域', '测试工具', '安全领域', '安全工具', '安全标准', '安全运营', '安全测试', '代码质量', '架构质量']")
    w(f, "SET s.domain_code = 'SKD-06', s.domain_name = '测试、安全与质量';")
    w(f)
    w(f, "// Business & Product skills -> SKD-07")
    w(f, "MATCH (s:Skill)")
    w(f, "WHERE s.category IN ['产品工具', '产品文档', '产品能力', '产品设计', '管理能力', '管理方法', '项目管理工具', '数据分析', '数据可视化', 'BI工具', '办公工具', '设计工具', '金融科技', '区块链', '智能合约', '架构设计', '系统设计', '设计模式']")
    w(f, "SET s.domain_code = 'SKD-07', s.domain_name = '业务、产品与软技能';")
    w(f)
    w(f, "// --- G.8 Skill: link Skill nodes to SkillGroup/SkillType where applicable ---")
    w(f, "// Specific skill-to-group mappings (by skill name)")
    w(f, "// Java ecosystem -> GRP-0101")
    w(f, "MATCH (s:Skill)")
    w(f, "WHERE s.name IN ['Java', 'Python', 'Go', 'C++', 'Rust', 'PHP', 'Ruby', 'Scala', 'Shell']")
    w(f, "SET s.group_code = 'GRP-0101', s.group_name = '后端编程语言';")
    w(f)
    w(f, "// Frontend languages/tech -> GRP-0102")
    w(f, "MATCH (s:Skill)")
    w(f, "WHERE s.name IN ['JavaScript', 'TypeScript', 'HTML5', 'CSS3', 'React', 'Vue', 'Angular', 'Webpack', 'Vite', 'Node.js', '小程序']")
    w(f, "SET s.group_code = 'GRP-0102', s.group_name = '前端技术';")
    w(f)
    w(f, "// Backend frameworks -> GRP-0103")
    w(f, "MATCH (s:Skill)")
    w(f, "WHERE s.name IN ['Spring', 'Spring Boot', 'Spring Cloud', 'MyBatis', 'Hibernate', 'Django', 'Flask', 'FastAPI', 'Express', 'Laravel', 'Netty']")
    w(f, "SET s.group_code = 'GRP-0103', s.group_name = '后端框架';")
    w(f)
    w(f, "// Mobile dev -> GRP-0104")
    w(f, "MATCH (s:Skill)")
    w(f, "WHERE s.name IN ['Android SDK', 'Jetpack', 'UIKit', 'SwiftUI', 'Flutter', 'React Native', 'Retrofit', 'Core Data', 'Combine', 'Room']")
    w(f, "SET s.group_code = 'GRP-0104', s.group_name = '移动开发技术';")
    w(f)
    w(f, "// Game & graphics -> GRP-0105")
    w(f, "MATCH (s:Skill)")
    w(f, "WHERE s.name IN ['Unity', 'Unreal Engine', 'OpenGL', 'WebGL', 'FFmpeg', 'WebRTC']")
    w(f, "SET s.group_code = 'GRP-0105', s.group_name = '游戏与图形开发';")
    w(f)
    w(f, "// SQL databases -> GRP-0201")
    w(f, "MATCH (s:Skill)")
    w(f, "WHERE s.name IN ['MySQL', 'PostgreSQL', 'Oracle', 'SQLite']")
    w(f, "SET s.group_code = 'GRP-0201', s.group_name = '关系型数据库';")
    w(f)
    w(f, "// NoSQL -> GRP-0202")
    w(f, "MATCH (s:Skill)")
    w(f, "WHERE s.name IN ['MongoDB', 'Redis', 'Elasticsearch', 'HBase', 'ClickHouse'] OR s.name CONTAINS '向量数据库'")
    w(f, "SET s.group_code = 'GRP-0202', s.group_name = '非关系型数据库';")
    w(f)
    w(f, "// Big data -> GRP-0203")
    w(f, "MATCH (s:Skill)")
    w(f, "WHERE s.name IN ['Spark', 'Flink', 'Hadoop', 'Hive'] OR s.name IN ['数据仓库', 'Doris']")
    w(f, "SET s.group_code = 'GRP-0203', s.group_name = '大数据与流处理';")
    w(f)
    w(f, "// Message queues -> GRP-0204")
    w(f, "MATCH (s:Skill)")
    w(f, "WHERE s.name IN ['Kafka', 'RabbitMQ', 'RocketMQ']")
    w(f, "SET s.group_code = 'GRP-0204', s.group_name = '消息队列与事件流';")
    w(f)
    w(f, "// AI frameworks -> GRP-0301")
    w(f, "MATCH (s:Skill)")
    w(f, "WHERE s.name IN ['TensorFlow', 'PyTorch', 'Keras', 'Scikit-learn', 'XGBoost', 'LightGBM']")
    w(f, "SET s.group_code = 'GRP-0301', s.group_name = 'AI/ML框架';")
    w(f)
    w(f, "// AI models -> GRP-0302")
    w(f, "MATCH (s:Skill)")
    w(f, "WHERE s.name IN ['Transformer', 'BERT', 'GPT', 'CNN', 'RNN', 'YOLO', 'Stable Diffusion'] OR s.name = 'LLM'")
    w(f, "SET s.group_code = 'GRP-0302', s.group_name = 'AI/ML模型';")
    w(f)
    w(f, "// AI application domains -> GRP-0303")
    w(f, "MATCH (s:Skill)")
    w(f, "WHERE s.name IN ['机器学习', '深度学习', 'NLP', '计算机视觉', '数据挖掘', '推荐系统', '强化学习', '语音识别', '语音合成', '多模态']")
    w(f, "SET s.group_code = 'GRP-0303', s.group_name = 'AI/ML应用领域';")
    w(f)
    w(f, "// AI engineering -> GRP-0304")
    w(f, "MATCH (s:Skill)")
    w(f, "WHERE s.name IN ['模型部署', '模型优化', 'CUDA', 'TensorRT', 'ONNX', 'MLflow', 'Kubeflow', 'HuggingFace', 'LangChain', 'RAG']")
    w(f, "SET s.group_code = 'GRP-0304', s.group_name = 'AI/ML工程化';")
    w(f)
    w(f, "// AI tools -> GRP-0305")
    w(f, "MATCH (s:Skill)")
    w(f, "WHERE s.name IN ['OpenCV', 'jieba', 'spaCy', 'Kaldi', 'Matplotlib']")
    w(f, "SET s.group_code = 'GRP-0305', s.group_name = 'AI工具与库';")
    w(f)
    w(f, "// Cloud platforms -> GRP-0401")
    w(f, "MATCH (s:Skill)")
    w(f, "WHERE s.name IN ['AWS', 'Azure', 'Google Cloud']")
    w(f, "SET s.group_code = 'GRP-0401', s.group_name = '云平台';")
    w(f)
    w(f, "// Containers -> GRP-0402")
    w(f, "MATCH (s:Skill)")
    w(f, "WHERE s.name IN ['Docker', 'Kubernetes']")
    w(f, "SET s.group_code = 'GRP-0402', s.group_name = '容器与编排';")
    w(f)
    w(f, "// Networking -> GRP-0403")
    w(f, "MATCH (s:Skill)")
    w(f, "WHERE s.name IN ['TCP/IP', '通信协议', 'gRPC', 'GraphQL', 'WebSocket', 'Istio', 'Envoy', 'Consul']")
    w(f, "SET s.group_code = 'GRP-0403', s.group_name = '网络与通信';")
    w(f)
    w(f, "// System & infra -> GRP-0404")
    w(f, "MATCH (s:Skill)")
    w(f, "WHERE s.name IN ['Linux', 'Nginx', 'Gunicorn', 'ZooKeeper', 'Nacos', 'Harbor', 'Helix']")
    w(f, "SET s.group_code = 'GRP-0404', s.group_name = '系统与基础设施';")
    w(f)
    w(f, "// CI/CD -> GRP-0501")
    w(f, "MATCH (s:Skill)")
    w(f, "WHERE s.name IN ['Jenkins', 'CI/CD', 'Maven', 'Gradle', 'CMake', 'SonarQube']")
    w(f, "SET s.group_code = 'GRP-0501', s.group_name = 'CI/CD与构建';")
    w(f)
    w(f, "// Observability -> GRP-0502")
    w(f, "MATCH (s:Skill)")
    w(f, "WHERE s.name IN ['Prometheus', 'Grafana', 'ELK', 'Jaeger', '前端监控']")
    w(f, "SET s.group_code = 'GRP-0502', s.group_name = '可观测性与监控';")
    w(f)
    w(f, "// IaC -> GRP-0503")
    w(f, "MATCH (s:Skill)")
    w(f, "WHERE s.name IN ['Terraform', 'Ansible', 'Helm']")
    w(f, "SET s.group_code = 'GRP-0503', s.group_name = '配置与基础设施即代码';")
    w(f)
    w(f, "// Testing -> GRP-0601")
    w(f, "MATCH (s:Skill)")
    w(f, "WHERE s.name IN ['自动化测试', '性能测试', '单元测试', 'Selenium', 'JMeter', 'Postman', 'Appium', 'Pytest', '安全测试']")
    w(f, "SET s.group_code = 'GRP-0601', s.group_name = '软件测试';")
    w(f)
    w(f, "// Security -> GRP-0602")
    w(f, "MATCH (s:Skill)")
    w(f, "WHERE s.name IN ['网络安全', '渗透测试', '密码学', 'WAF', '漏洞扫描', 'SOC', 'ISO27001']")
    w(f, "SET s.group_code = 'GRP-0602', s.group_name = '信息安全';")
    w(f)
    w(f, "// Code quality -> GRP-0603")
    w(f, "MATCH (s:Skill)")
    w(f, "WHERE s.name IN ['领域驱动设计', '设计模式', '代码重构']")
    w(f, "SET s.group_code = 'GRP-0603', s.group_name = '代码与架构质量';")
    w(f)
    w(f, "// Product & design tools -> GRP-0701")
    w(f, "MATCH (s:Skill)")
    w(f, "WHERE s.name IN ['Axure', 'Figma', 'Sketch', 'XMind']")
    w(f, "SET s.group_code = 'GRP-0701', s.group_name = '产品与设计工具';")
    w(f)
    w(f, "// Data analysis & BI -> GRP-0702")
    w(f, "MATCH (s:Skill)")
    w(f, "WHERE s.name IN ['Pandas', 'NumPy', 'SciPy', 'Tableau', 'ECharts', 'D3.js', '数据分析', 'Excel']")
    w(f, "SET s.group_code = 'GRP-0702', s.group_name = '数据分析与商业智能';")
    w(f)
    w(f, "// Management -> GRP-0703")
    w(f, "MATCH (s:Skill)")
    w(f, "WHERE s.name IN ['项目管理', '风险管理', '沟通协调', 'PMO', '技术管理', '敏捷开发', 'Scrum', 'JIRA']")
    w(f, "SET s.group_code = 'GRP-0703', s.group_name = '管理与方法论';")
    w(f)
    w(f, "// Product capabilities -> GRP-0704")
    w(f, "MATCH (s:Skill)")
    w(f, "WHERE s.name IN ['PRD', '用户研究', '竞品分析', '需求分析', '原型设计', '用户体验', 'AB实验']")
    w(f, "SET s.group_code = 'GRP-0704', s.group_name = '产品能力';")
    w(f)
    w(f, "// Architecture & system design -> GRP-0705")
    w(f, "MATCH (s:Skill)")
    w(f, "WHERE s.name IN ['微服务', 'MVVM', '分布式', '高并发', '系统设计', '金融科技']")
    w(f, "SET s.group_code = 'GRP-0705', s.group_name = '架构与系统设计';")
    w(f)
    w(f, "// --- G.9 Skill: link Skill nodes to SkillDomain/Group/Type taxonomy nodes ---")
    w(f, "// Link to SkillDomain")
    w(f, "MATCH (s:Skill)")
    w(f, "WHERE s.domain_code IS NOT NULL")
    w(f, "MATCH (d:SkillDomain {code: s.domain_code})")
    w(f, "MERGE (s)-[:BELONGS_TO_DOMAIN]->(d);")
    w(f)
    w(f, "// Link to SkillGroup")
    w(f, "MATCH (s:Skill)")
    w(f, "WHERE s.group_code IS NOT NULL")
    w(f, "MATCH (g:SkillGroup {code: s.group_code})")
    w(f, "MERGE (s)-[:BELONGS_TO_GROUP]->(g);")
    w(f)
    w(f, "// --- G.10 Unmatched Skill nodes: set domain_code to SKD-99 ---")
    w(f, "MATCH (s:Skill)")
    w(f, "WHERE s.domain_code IS NULL")
    w(f, "SET s.domain_code = 'SKD-99',")
    w(f, "    s.domain_name = '其他',")
    w(f, "    s.group_code = 'GRP-9901',")
    w(f, "    s.group_name = '未分类';")
    w(f)

    # ---- Section H ----
    w(f, "// =============================================================================")
    w(f, "// SECTION H: CROSS-TAXONOMY RELATIONSHIPS")
    w(f, "// =============================================================================")
    w(f)
    w(f, "// --- H.1 EmergingJob -> JobCategory ---")
    w(f, "MATCH (e:EmergingJob)")
    w(f, "WHERE e.category_code IS NULL")
    w(f, "MATCH (c:JobCategory {code: 'CAT-0604'})")
    w(f, "MERGE (e)-[:BELONGS_TO_CATEGORY]->(c)")
    w(f, "SET e.domain_code = 'DOM-06',")
    w(f, "    e.category_code = 'CAT-0604';")
    w(f)
    w(f, "// --- H.2 Job -> JobTitle -> JobCategory chain (if Job nodes exist) ---")
    w(f, "// Ensures Job nodes inherit taxonomy via their linked JobTitle")
    w(f, "MATCH (j:Job)-[:HAS_TITLE]->(t:JobTitle)")
    w(f, "WHERE t.category_code IS NOT NULL")
    w(f, "MATCH (c:JobCategory {code: t.category_code})")
    w(f, "MERGE (j)-[:BELONGS_TO_CATEGORY]->(c);")
    w(f)
    w(f, "// --- H.3 JobDomain <- JobCategory summary aggregation ---")
    w(f, "// Create a summary property on JobDomain counting direct JobTitles")
    w(f, "MATCH (d:JobDomain)<-[:BELONGS_TO_DOMAIN]-(c:JobCategory)<-[:BELONGS_TO_CATEGORY]-(t:JobTitle)")
    w(f, "WITH d, count(DISTINCT t) AS title_count")
    w(f, "SET d.job_title_count = title_count;")
    w(f)
    w(f, "// --- H.4 SkillDomain summary aggregation ---")
    w(f, "MATCH (d:SkillDomain)<-[:BELONGS_TO_DOMAIN]-(s:Skill)")
    w(f, "WITH d, count(DISTINCT s) AS skill_count")
    w(f, "SET d.skill_count = skill_count;")
    w(f)

    w(f, "// =============================================================================")
    w(f, "// END OF MIGRATION SCRIPT")
    w(f, "// =============================================================================")
    w(f, "//")
    w(f, "// VERIFICATION QUERIES (run after migration to validate):")
    w(f, "//")
    w(f, "// -- Count taxonomy nodes created --")
    w(f, "// MATCH (n:JobDomain)    RETURN 'JobDomain',    count(n) UNION ALL")
    w(f, "// MATCH (n:JobCategory)  RETURN 'JobCategory',  count(n) UNION ALL")
    w(f, "// MATCH (n:SkillDomain)  RETURN 'SkillDomain',  count(n) UNION ALL")
    w(f, "// MATCH (n:SkillGroup)   RETURN 'SkillGroup',   count(n) UNION ALL")
    w(f, "// MATCH (n:SkillType)    RETURN 'SkillType',    count(n) UNION ALL")
    w(f, "// MATCH (n:IndustrySector)    RETURN 'IndustrySector',    count(n) UNION ALL")
    w(f, "// MATCH (n:IndustryDivision)  RETURN 'IndustryDivision',  count(n) UNION ALL")
    w(f, "// MATCH (n:IndustryGroup)     RETURN 'IndustryGroup',     count(n) UNION ALL")
    w(f, "// MATCH (n:AbilityDimension)    RETURN 'AbilityDimension',    count(n) UNION ALL")
    w(f, "// MATCH (n:CompetencyCluster)   RETURN 'CompetencyCluster',   count(n) UNION ALL")
    w(f, "// MATCH (n:Competency)          RETURN 'Competency',          count(n);")
    w(f, "//")
    w(f, "// -- Check JobTitle classification coverage --")
    w(f, "// MATCH (t:JobTitle) RETURN t.category_code AS category, count(t) AS cnt ORDER BY cnt DESC;")
    w(f, "//")
    w(f, "// -- Check Skill domain coverage --")
    w(f, "// MATCH (s:Skill) RETURN s.domain_code AS domain, count(s) AS cnt ORDER BY cnt DESC;")
    w(f, "//")
    w(f, "// -- Check relationship integrity --")
    w(f, "// MATCH ()-[r:BELONGS_TO_DOMAIN]->() RETURN type(r), count(r)")
    w(f, "// UNION ALL")
    w(f, "// MATCH ()-[r:BELONGS_TO_CATEGORY]->() RETURN type(r), count(r)")
    w(f, "// UNION ALL")
    w(f, "// MATCH ()-[r:BELONGS_TO_GROUP]->() RETURN type(r), count(r)")
    w(f, "// UNION ALL")
    w(f, "// MATCH ()-[r:BELONGS_TO_SECTOR]->() RETURN type(r), count(r)")
    w(f, "// UNION ALL")
    w(f, "// MATCH ()-[r:BELONGS_TO_DIVISION]->() RETURN type(r), count(r)")
    w(f, "// UNION ALL")
    w(f, "// MATCH ()-[r:BELONGS_TO_DIMENSION]->() RETURN type(r), count(r)")
    w(f, "// UNION ALL")
    w(f, "// MATCH ()-[r:BELONGS_TO_CLUSTER]->() RETURN type(r), count(r);")
    w(f)

    f.close()
    return OUTPUT


if __name__ == "__main__":
    out = generate(OUTPUT)
    print(f"Generated: {out}")
    print(f"Size: {os.path.getsize(out)} bytes")
