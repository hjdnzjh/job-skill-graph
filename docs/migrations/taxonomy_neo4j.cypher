// =============================================================================
// 岗位能力分类体系 — Neo4j 图数据库迁移脚本
// =============================================================================
// 版本: v1.1
// 日期: 2026-07-15
// 基于: TAXONOMY_DESIGN.md
// 幂等性: 全部使用 MERGE (不用 CREATE), 可重复执行
//
// 修复记录:
//   v1.1 - C-1: 修复 G.1 节 domain_name = c.name 错误 (改为硬编码域名)
//          C-2: 补充 BELONGS_TO_TYPE 关系 + G.8 节 type_code/type_name
//          C-3: 新增 H.5 节 REQUIRES_COMPETENCY 关系
//          C-4: 修复 互联网/IT 行业 group_code/group_name 映射
//          C-5: 新增 TEXT INDEX 提升 G.1 节全文扫描性能
//          C-6: 新增 UNCLASSIFIED 占位节点
//          C-9: 补充 人工智能 行业 M-73 映射
//          C-10: 移除空字符串赋值, 改用 REMOVE
//          C-15: Experience min_years/max_years 改为 toFloat()
//
// 执行方式:
//   cypher-shell -u neo4j -p <password> -f taxonomy_neo4j.cypher
//   或在 Neo4j Browser/Bloom 中逐段执行
//
// 包含以下分类体系:
//   Section A — 约束与索引
//   Section B — 岗位三层分类体系 (Domain->Category->Title)
//   Section C — 技能四层分类体系 (Domain->Group->Type->Skill)
//   Section D — 行业三层分类体系 (Sector->Division->Group->Industry)
//   Section E — 能力三层分类体系 (Dimension->Cluster->Competency)
//   Section F — 教育与经验有序化
//   Section G — 现有节点属性回填 (JobTitle/Skill/Industry/Education/Experience)
//   Section H — 跨体系关系 (岗位-能力映射)
// =============================================================================

// =============================================================================
// SECTION A: CONSTRAINTS & INDEXES
// =============================================================================

// --- Job taxonomy constraints ---
CREATE CONSTRAINT job_domain_code_unique IF NOT EXISTS
FOR (n:JobDomain) REQUIRE n.code IS UNIQUE;

CREATE CONSTRAINT job_category_code_unique IF NOT EXISTS
FOR (n:JobCategory) REQUIRE n.code IS UNIQUE;

// --- Skill taxonomy constraints ---
CREATE CONSTRAINT skill_domain_code_unique IF NOT EXISTS
FOR (n:SkillDomain) REQUIRE n.code IS UNIQUE;

CREATE CONSTRAINT skill_group_code_unique IF NOT EXISTS
FOR (n:SkillGroup) REQUIRE n.code IS UNIQUE;

CREATE CONSTRAINT skill_type_code_unique IF NOT EXISTS
FOR (n:SkillType) REQUIRE n.code IS UNIQUE;

// --- Industry taxonomy constraints ---
CREATE CONSTRAINT industry_sector_code_unique IF NOT EXISTS
FOR (n:IndustrySector) REQUIRE n.code IS UNIQUE;

CREATE CONSTRAINT industry_division_code_unique IF NOT EXISTS
FOR (n:IndustryDivision) REQUIRE n.code IS UNIQUE;

CREATE CONSTRAINT industry_group_code_unique IF NOT EXISTS
FOR (n:IndustryGroup) REQUIRE n.code IS UNIQUE;

// --- Ability taxonomy constraints ---
CREATE CONSTRAINT ability_dimension_code_unique IF NOT EXISTS
FOR (n:AbilityDimension) REQUIRE n.code IS UNIQUE;

CREATE CONSTRAINT competency_cluster_code_unique IF NOT EXISTS
FOR (n:CompetencyCluster) REQUIRE n.code IS UNIQUE;

CREATE CONSTRAINT competency_code_unique IF NOT EXISTS
FOR (n:Competency) REQUIRE n.code IS UNIQUE;

// --- Indexes for existing node attribute lookups ---
CREATE INDEX job_title_domain_idx   IF NOT EXISTS FOR (n:JobTitle)  ON (n.domain_code);
CREATE INDEX job_title_category_idx IF NOT EXISTS FOR (n:JobTitle)  ON (n.category_code);
CREATE INDEX skill_domain_idx       IF NOT EXISTS FOR (s:Skill)     ON (s.domain_code);
CREATE INDEX skill_group_idx        IF NOT EXISTS FOR (s:Skill)     ON (s.group_code);
CREATE INDEX industry_sector_idx    IF NOT EXISTS FOR (i:Industry)  ON (i.sector_code);
CREATE INDEX industry_division_idx  IF NOT EXISTS FOR (i:Industry)  ON (i.division_code);

// --- TEXT INDEX for G.1 keyword-based JobTitle classification ---
// Avoids 50+ full label scans when matching JobTitle by name substring
CREATE TEXT INDEX job_title_name_text IF NOT EXISTS FOR (n:JobTitle) ON (n.name);

// =============================================================================
// SECTION B: JOB TAXONOMY (3-level: Domain -> Category -> Title)
// =============================================================================

// --- B.1 Create JobDomain nodes ---
UNWIND [
  {code:'DOM-01', name:'软件与算法开发', description:'负责软件开发、算法设计、系统架构等核心技术工作的职能领域，涵盖后端、前端、移动端、嵌入式等多方向开发。'},
  {code:'DOM-02', name:'数据与人工智能', description:'负责数据处理、分析、挖掘及人工智能模型研究、开发与应用的职能领域，涵盖大数据、机器学习、商业智能等方向。'},
  {code:'DOM-03', name:'基础设施与运维', description:'负责IT基础设施规划、建设、运维及云计算平台管理的职能领域，涵盖运维、网络、通信等方向。'},
  {code:'DOM-04', name:'产品与项目管理', description:'负责产品规划、需求管理、项目交付及技术团队管理的职能领域，涵盖产品管理、项目管理、技术管理方向。'},
  {code:'DOM-05', name:'质量与安全', description:'负责软件质量保障、测试体系及信息安全的职能领域，涵盖功能测试、性能测试、渗透测试、安全合规等方向。'},
  {code:'DOM-06', name:'新兴与交叉技术', description:'负责区块链、Web3、游戏开发、金融科技及其他前沿交叉技术领域开发与应用的职能领域。'}
] AS row
MERGE (d:JobDomain {code: row.code})
SET d.name = row.name,
    d.description = row.description,
    d.taxonomy_version = '1.0',
    d.standard_ref = 'GB/T 6565-2015';

// --- B.2 Create JobCategory nodes and link to JobDomain ---
UNWIND [
  {code:'CAT-0101', name:'后端开发', domain_code:'DOM-01', description:'负责服务端应用程序的设计、开发与维护，包括业务逻辑、数据访问、API接口等。', gb_code:'2-02-10-01', esco_code:'2512.1'},
  {code:'CAT-0102', name:'前端与全栈开发', domain_code:'DOM-01', description:'负责Web前端界面开发及跨前后端的全流程开发，涵盖UI实现、交互逻辑、全栈整合。', gb_code:'2-02-10-01', esco_code:'2513.1'},
  {code:'CAT-0103', name:'移动开发', domain_code:'DOM-01', description:'专责Android/iOS/跨平台移动端原生或混合应用程序开发。', gb_code:'2-02-10-01', esco_code:'2514.1'},
  {code:'CAT-0104', name:'架构设计', domain_code:'DOM-01', description:'负责系统架构设计、技术选型、技术战略，指导团队技术方向。', gb_code:'2-02-10-03', esco_code:'2511.1'},
  {code:'CAT-0105', name:'嵌入式与物联网开发', domain_code:'DOM-01', description:'面向硬件平台(MCU/SoC/FPGA)的固件、驱动及应用软件开发。', gb_code:'2-02-10-04', esco_code:'2519.3'},
  {code:'CAT-0106', name:'其他软件开发', domain_code:'DOM-01', description:'跨领域或特定垂直方向(音视频、区块链、Web3等)的开发岗位。', gb_code:'', esco_code:''},
  {code:'CAT-0201', name:'算法研究与AI模型', domain_code:'DOM-02', description:'负责机器学习/深度学习模型的研究、设计、训练与优化，解决核心算法问题。', gb_code:'2-02-10-02', esco_code:'2519.6'},
  {code:'CAT-0202', name:'AI工程化与应用', domain_code:'DOM-02', description:'将AI模型产品化、工程化部署，或基于LLM/GPT等大模型进行应用开发。', gb_code:'', esco_code:'2519.7'},
  {code:'CAT-0203', name:'大数据工程', domain_code:'DOM-02', description:'负责大数据平台建设、数据处理流水线(ETL)、数据仓库设计与维护。', gb_code:'2-02-10-02', esco_code:'2521.1'},
  {code:'CAT-0204', name:'数据分析与商业智能', domain_code:'DOM-02', description:'对业务数据进行分析、建模和可视化，为决策提供数据支撑。', gb_code:'2-06-01-01', esco_code:'3311.1'},
  {code:'CAT-0301', name:'运维与站点可靠性', domain_code:'DOM-03', description:'负责生产环境运维、监控、故障处理，保障服务可用性(SLA)。', gb_code:'2-02-10-05', esco_code:'3512.1'},
  {code:'CAT-0302', name:'云计算与平台工程', domain_code:'DOM-03', description:'负责云基础设施规划、云原生平台建设、自动化部署与弹性伸缩。', gb_code:'2-02-10-05', esco_code:'2529.2'},
  {code:'CAT-0303', name:'网络与通信工程', domain_code:'DOM-03', description:'负责企业网络架构、通信协议实现、网络设备管理与优化。', gb_code:'2-02-10-05', esco_code:'2523.1'},
  {code:'CAT-0401', name:'产品管理', domain_code:'DOM-04', description:'负责产品规划、需求定义、用户研究、产品生命周期管理。', gb_code:'2-06-07-04', esco_code:'2431.6'},
  {code:'CAT-0402', name:'项目管理', domain_code:'DOM-04', description:'负责项目计划、进度跟踪、风险管控、资源协调与交付管理。', gb_code:'2-06-03-01', esco_code:'2412.1'},
  {code:'CAT-0403', name:'技术管理', domain_code:'DOM-04', description:'负责技术团队管理、技术战略规划、跨团队协调与人才培养。', gb_code:'1-05-01-01', esco_code:'1330.2'},
  {code:'CAT-0501', name:'测试与质量保证', domain_code:'DOM-05', description:'负责软件测试(功能/性能/安全/自动化)、缺陷管理、质量体系建立。', gb_code:'2-02-10-06', esco_code:'2519.4'},
  {code:'CAT-0502', name:'信息安全', domain_code:'DOM-05', description:'负责信息安全体系建设、渗透测试、安全监控、应急响应与合规管理。', gb_code:'2-02-10-07', esco_code:'2529.5'},
  {code:'CAT-0601', name:'区块链与Web3', domain_code:'DOM-06', description:'负责区块链底层开发、智能合约编写、DApp开发与链上数据分析。', gb_code:'', esco_code:'2519.8'},
  {code:'CAT-0602', name:'游戏开发', domain_code:'DOM-06', description:'负责游戏客户端/服务端开发、引擎定制、渲染优化与玩法实现。', gb_code:'2-09-06-04', esco_code:'2519.9'},
  {code:'CAT-0603', name:'金融科技', domain_code:'DOM-06', description:'负责量化交易系统、风控模型、支付系统等金融与技术的交叉领域。', gb_code:'', esco_code:'3312.1'},
  {code:'CAT-0604', name:'其他新兴岗位', domain_code:'DOM-06', description:'LLM/大模型驱动的新型岗位(提示词工程师、AI训练师、AI伦理师等)的预留分类。', gb_code:'', esco_code:''}
] AS row
MERGE (c:JobCategory {code: row.code})
SET c.name = row.name,
    c.description = row.description,
    c.gb_code = row.gb_code,
    c.esco_code = row.esco_code,
    c.taxonomy_version = '1.0'
WITH c, row
MATCH (d:JobDomain {code: row.domain_code})
MERGE (c)-[:BELONGS_TO_DOMAIN]->(d);

// --- B.3 UNCLASSIFIED placeholder nodes ---
MERGE (d:JobDomain {code: 'UNCLASSIFIED'})
SET d.name = '待分类',
    d.description = '暂未归入任何已知领域的岗位',
    d.taxonomy_version = '1.0';

MERGE (c:JobCategory {code: 'UNCLASSIFIED'})
SET c.name = '待分类',
    c.description = '暂未归入任何已知类别的岗位',
    c.taxonomy_version = '1.0'
WITH c
MATCH (d:JobDomain {code: 'UNCLASSIFIED'})
MERGE (c)-[:BELONGS_TO_DOMAIN]->(d);

// =============================================================================
// SECTION C: SKILL TAXONOMY (4-level: Domain -> Group -> Type -> Skill)
// =============================================================================

// --- C.1 Create SkillDomain nodes ---
UNWIND [
  {code:'SKD-01', name:'编程语言与框架', description:'涵盖所有编程语言、前端/后端/移动端框架、游戏引擎及图形多媒体工具。'},
  {code:'SKD-02', name:'数据存储与管理', description:'涵盖关系型数据库、非关系型数据库、大数据处理框架、消息队列及事件流平台。'},
  {code:'SKD-03', name:'人工智能与机器学习', description:'涵盖AI/ML框架、模型、应用领域、工程化工具及相关领域库。'},
  {code:'SKD-04', name:'云计算与基础设施', description:'涵盖云平台、容器编排、网络通信、操作系统及Web服务器等基础设施。'},
  {code:'SKD-05', name:'DevOps与工程效能', description:'涵盖CI/CD工具、构建系统、可观测性监控、配置管理及基础设施即代码工具。'},
  {code:'SKD-06', name:'测试、安全与质量', description:'涵盖软件测试、信息安全、代码与架构质量等领域工具与实践。'},
  {code:'SKD-07', name:'业务、产品与软技能', description:'涵盖产品工具、数据分析、管理方法、架构设计及业务领域知识。'},
  {code:'SKD-99', name:'其他', description:'未匹配新技能的临时存放区，待审核后重新归类。'}
] AS row
MERGE (d:SkillDomain {code: row.code})
SET d.name = row.name,
    d.description = row.description,
    d.taxonomy_version = '1.0',
    d.standard_ref = 'ESCO v1.2';

// --- C.2 Create SkillGroup nodes and link to SkillDomain ---
UNWIND [
  {code:'GRP-0101', name:'后端编程语言', domain_code:'SKD-01', description:'Java, Python, Go, C++, Rust, PHP, Ruby, Scala 等服务端编程语言。'},
  {code:'GRP-0102', name:'前端技术', domain_code:'SKD-01', description:'JavaScript, TypeScript, HTML5, CSS3, React, Vue, Angular 等前端技术栈。'},
  {code:'GRP-0103', name:'后端框架', domain_code:'SKD-01', description:'Spring, Django, Flask, Express, Laravel 等服务端开发框架。'},
  {code:'GRP-0104', name:'移动开发技术', domain_code:'SKD-01', description:'Android SDK, iOS UIKit, Flutter, React Native 等移动端开发框架与工具。'},
  {code:'GRP-0105', name:'游戏与图形开发', domain_code:'SKD-01', description:'Unity, Unreal, OpenGL, WebGL, FFmpeg, WebRTC 等游戏引擎与图形工具。'},
  {code:'GRP-0201', name:'关系型数据库', domain_code:'SKD-02', description:'MySQL, PostgreSQL, Oracle, SQLite 等关系型数据库管理系统。'},
  {code:'GRP-0202', name:'非关系型数据库', domain_code:'SKD-02', description:'MongoDB, Redis, Elasticsearch, HBase, ClickHouse 及向量数据库等 NoSQL 系统。'},
  {code:'GRP-0203', name:'大数据与流处理', domain_code:'SKD-02', description:'Spark, Flink, Hadoop, Hive, Doris 等大数据计算及数据仓库技术。'},
  {code:'GRP-0204', name:'消息队列与事件流', domain_code:'SKD-02', description:'Kafka, RabbitMQ, RocketMQ 等消息队列与事件流平台。'},
  {code:'GRP-0301', name:'AI/ML框架', domain_code:'SKD-03', description:'TensorFlow, PyTorch, Keras, Scikit-learn, XGBoost 等AI/机器学习框架。'},
  {code:'GRP-0302', name:'AI/ML模型', domain_code:'SKD-03', description:'Transformer, BERT, GPT, LLM, CNN, RNN, YOLO, Stable Diffusion 等模型架构。'},
  {code:'GRP-0303', name:'AI/ML应用领域', domain_code:'SKD-03', description:'机器学习、深度学习、NLP、计算机视觉、数据挖掘、推荐系统等应用方向。'},
  {code:'GRP-0304', name:'AI/ML工程化', domain_code:'SKD-03', description:'模型部署、CUDA、TensorRT、MLflow、Kubeflow、LangChain、RAG 等工程化工具。'},
  {code:'GRP-0305', name:'AI工具与库', domain_code:'SKD-03', description:'OpenCV, jieba, spaCy, Kaldi, Matplotlib 等AI辅助工具与领域库。'},
  {code:'GRP-0401', name:'云平台', domain_code:'SKD-04', description:'AWS, Azure, Google Cloud 等公有云及私有云平台服务。'},
  {code:'GRP-0402', name:'容器与编排', domain_code:'SKD-04', description:'Docker, Kubernetes 等容器化及编排技术。'},
  {code:'GRP-0403', name:'网络与通信', domain_code:'SKD-04', description:'TCP/IP, gRPC, GraphQL, WebSocket, Istio, Envoy, Consul 等网络与通信技术。'},
  {code:'GRP-0404', name:'系统与基础设施', domain_code:'SKD-04', description:'Linux, Nginx, Gunicorn, ZooKeeper, Nacos, Harbor, Helix 等系统基础设施。'},
  {code:'GRP-0501', name:'CI/CD与构建', domain_code:'SKD-05', description:'Jenkins, Maven, Gradle, CMake, SonarQube 等持续集成/构建/代码质量工具。'},
  {code:'GRP-0502', name:'可观测性与监控', domain_code:'SKD-05', description:'Prometheus, Grafana, ELK, Jaeger 等监控、日志、追踪工具。'},
  {code:'GRP-0503', name:'配置与基础设施即代码', domain_code:'SKD-05', description:'Terraform, Ansible, Helm 等IaC及配置管理工具。'},
  {code:'GRP-0601', name:'软件测试', domain_code:'SKD-06', description:'自动化测试、性能测试、单元测试、Selenium、JMeter、Postman 等测试工具。'},
  {code:'GRP-0602', name:'信息安全', domain_code:'SKD-06', description:'网络安全、渗透测试、密码学、WAF、SOC、ISO27001 等安全领域与工具。'},
  {code:'GRP-0603', name:'代码与架构质量', domain_code:'SKD-06', description:'领域驱动设计、设计模式、代码重构等架构质量实践。'},
  {code:'GRP-0701', name:'产品与设计工具', domain_code:'SKD-07', description:'Axure, Figma, Sketch, XMind 等产品原型与设计协作工具。'},
  {code:'GRP-0702', name:'数据分析与商业智能', domain_code:'SKD-07', description:'Pandas, NumPy, Tableau, ECharts, Excel 等数据分析与可视化工具。'},
  {code:'GRP-0703', name:'管理与方法论', domain_code:'SKD-07', description:'项目管理、敏捷开发、Scrum、风险管理、JIRA 等管理能力与方法论。'},
  {code:'GRP-0704', name:'产品能力', domain_code:'SKD-07', description:'PRD、用户研究、竞品分析、需求分析、原型设计、用户体验等产品技能。'},
  {code:'GRP-0705', name:'架构与系统设计', domain_code:'SKD-07', description:'微服务、MVVM、分布式、高并发、系统设计、金融科技等架构与领域知识。'},
  {code:'GRP-9901', name:'未分类', domain_code:'SKD-99', description:'暂未匹配到标准分类体系的技能临时存放区。'}
] AS row
MERGE (g:SkillGroup {code: row.code})
SET g.name = row.name,
    g.description = row.description,
    g.taxonomy_version = '1.0'
WITH g, row
MATCH (d:SkillDomain {code: row.domain_code})
MERGE (g)-[:BELONGS_TO_DOMAIN]->(d);

// --- C.3 Create SkillType nodes and link to SkillGroup ---
UNWIND [
  {code:'T-01011', name:'主要后端语言', group_code:'GRP-0101'},
  {code:'T-01012', name:'脚本与其他语言', group_code:'GRP-0101'},
  {code:'T-01021', name:'前端编程语言', group_code:'GRP-0102'},
  {code:'T-01022', name:'前端框架', group_code:'GRP-0102'},
  {code:'T-01023', name:'前端基础技术', group_code:'GRP-0102'},
  {code:'T-01024', name:'前端工具与运行时', group_code:'GRP-0102'},
  {code:'T-01031', name:'Java生态框架', group_code:'GRP-0103'},
  {code:'T-01032', name:'Python生态框架', group_code:'GRP-0103'},
  {code:'T-01033', name:'其他后端框架', group_code:'GRP-0103'},
  {code:'T-01041', name:'移动开发框架', group_code:'GRP-0104'},
  {code:'T-01042', name:'移动开发工具', group_code:'GRP-0104'},
  {code:'T-01051', name:'游戏引擎', group_code:'GRP-0105'},
  {code:'T-01052', name:'图形与多媒体', group_code:'GRP-0105'},
  {code:'T-02011', name:'SQL数据库', group_code:'GRP-0201'},
  {code:'T-02021', name:'文档/键值数据库', group_code:'GRP-0202'},
  {code:'T-02022', name:'列存/搜索数据库', group_code:'GRP-0202'},
  {code:'T-02023', name:'向量数据库', group_code:'GRP-0202'},
  {code:'T-02031', name:'大数据计算框架', group_code:'GRP-0203'},
  {code:'T-02032', name:'数据仓库', group_code:'GRP-0203'},
  {code:'T-02041', name:'消息队列', group_code:'GRP-0204'},
  {code:'T-03011', name:'深度学习框架', group_code:'GRP-0301'},
  {code:'T-03012', name:'机器学习框架', group_code:'GRP-0301'},
  {code:'T-03021', name:'语言模型', group_code:'GRP-0302'},
  {code:'T-03022', name:'视觉模型', group_code:'GRP-0302'},
  {code:'T-03023', name:'传统ML模型', group_code:'GRP-0302'},
  {code:'T-03031', name:'AI/ML应用领域', group_code:'GRP-0303'},
  {code:'T-03041', name:'模型部署与优化', group_code:'GRP-0304'},
  {code:'T-03042', name:'MLOps工具', group_code:'GRP-0304'},
  {code:'T-03043', name:'LLM应用框架', group_code:'GRP-0304'},
  {code:'T-03051', name:'AI工具与库', group_code:'GRP-0305'},
  {code:'T-04011', name:'云平台', group_code:'GRP-0401'},
  {code:'T-04021', name:'容器与编排', group_code:'GRP-0402'},
  {code:'T-04031', name:'网络协议', group_code:'GRP-0403'},
  {code:'T-04032', name:'API协议', group_code:'GRP-0403'},
  {code:'T-04033', name:'服务网格', group_code:'GRP-0403'},
  {code:'T-04041', name:'操作系统', group_code:'GRP-0404'},
  {code:'T-04042', name:'Web服务器', group_code:'GRP-0404'},
  {code:'T-04043', name:'存储与注册中心', group_code:'GRP-0404'},
  {code:'T-05011', name:'CI/CD工具', group_code:'GRP-0501'},
  {code:'T-05012', name:'构建工具', group_code:'GRP-0501'},
  {code:'T-05013', name:'代码质量', group_code:'GRP-0501'},
  {code:'T-05021', name:'监控工具', group_code:'GRP-0502'},
  {code:'T-05022', name:'日志与追踪', group_code:'GRP-0502'},
  {code:'T-05023', name:'前端监控', group_code:'GRP-0502'},
  {code:'T-05031', name:'IaC工具', group_code:'GRP-0503'},
  {code:'T-05032', name:'配置管理', group_code:'GRP-0503'},
  {code:'T-05033', name:'容器编排辅助', group_code:'GRP-0503'},
  {code:'T-06011', name:'测试领域', group_code:'GRP-0601'},
  {code:'T-06012', name:'测试工具', group_code:'GRP-0601'},
  {code:'T-06013', name:'安全测试', group_code:'GRP-0601'},
  {code:'T-06021', name:'安全领域', group_code:'GRP-0602'},
  {code:'T-06022', name:'安全工具', group_code:'GRP-0602'},
  {code:'T-06023', name:'安全运营', group_code:'GRP-0602'},
  {code:'T-06024', name:'安全标准', group_code:'GRP-0602'},
  {code:'T-06031', name:'架构质量', group_code:'GRP-0603'},
  {code:'T-07011', name:'产品与设计工具', group_code:'GRP-0701'},
  {code:'T-07021', name:'数据分析库', group_code:'GRP-0702'},
  {code:'T-07022', name:'数据可视化', group_code:'GRP-0702'},
  {code:'T-07023', name:'BI工具', group_code:'GRP-0702'},
  {code:'T-07024', name:'办公工具', group_code:'GRP-0702'},
  {code:'T-07031', name:'管理能力', group_code:'GRP-0703'},
  {code:'T-07032', name:'方法论', group_code:'GRP-0703'},
  {code:'T-07033', name:'项目管理工具', group_code:'GRP-0703'},
  {code:'T-07041', name:'产品能力', group_code:'GRP-0704'},
  {code:'T-07051', name:'架构模式', group_code:'GRP-0705'},
  {code:'T-07052', name:'非功能需求', group_code:'GRP-0705'},
  {code:'T-07053', name:'领域知识', group_code:'GRP-0705'},
  {code:'T-99011', name:'未分类', group_code:'GRP-9901'}
] AS row
MERGE (t:SkillType {code: row.code})
SET t.name = row.name,
    t.taxonomy_version = '1.0'
WITH t, row
MATCH (g:SkillGroup {code: row.group_code})
MERGE (t)-[:BELONGS_TO_GROUP]->(g);

// --- C.4 UNCLASSIFIED placeholder nodes ---
MERGE (d:SkillDomain {code: 'UNCLASSIFIED'})
SET d.name = '待分类',
    d.description = '暂未归入任何已知技能域的技能',
    d.taxonomy_version = '1.0';

MERGE (g:SkillGroup {code: 'UNCLASSIFIED'})
SET g.name = '待分类',
    g.description = '暂未归入任何已知技能组的技能',
    g.taxonomy_version = '1.0'
WITH g
MATCH (d:SkillDomain {code: 'UNCLASSIFIED'})
MERGE (g)-[:BELONGS_TO_DOMAIN]->(d);

MERGE (t:SkillType {code: 'UNCLASSIFIED'})
SET t.name = '待分类',
    t.taxonomy_version = '1.0'
WITH t
MATCH (g:SkillGroup {code: 'UNCLASSIFIED'})
MERGE (t)-[:BELONGS_TO_GROUP]->(g);

// =============================================================================
// SECTION D: INDUSTRY TAXONOMY (3-level: Sector -> Division -> Group)
// =============================================================================

// --- D.1 Create IndustrySector nodes ---
UNWIND [
  {code:'C', name:'制造业', description:'GB/T 4754-2017 门类C: 制造业'},
  {code:'I', name:'信息传输、软件和信息技术服务业', description:'GB/T 4754-2017 门类I: 信息传输、软件和信息技术服务业'},
  {code:'J', name:'金融业', description:'GB/T 4754-2017 门类J: 金融业'},
  {code:'M', name:'科学研究和技术服务业', description:'GB/T 4754-2017 门类M: 科学研究和技术服务业'},
  {code:'P', name:'教育', description:'GB/T 4754-2017 门类P: 教育'},
  {code:'Q', name:'卫生和社会工作', description:'GB/T 4754-2017 门类Q: 卫生和社会工作'},
  {code:'R', name:'文化、体育和娱乐业', description:'GB/T 4754-2017 门类R: 文化、体育和娱乐业'}
] AS row
MERGE (s:IndustrySector {code: row.code})
SET s.name = row.name,
    s.description = row.description,
    s.taxonomy_version = '1.0',
    s.standard_ref = 'GB/T 4754-2017';

// --- D.2 Create IndustryDivision nodes and link to IndustrySector ---
UNWIND [
  {code:'34', name:'通用设备制造业', sector_code:'C'},
  {code:'35', name:'专用设备制造业', sector_code:'C'},
  {code:'36', name:'汽车制造业', sector_code:'C'},
  {code:'38', name:'电气机械和器材制造业', sector_code:'C'},
  {code:'39', name:'计算机、通信和其他电子设备制造业', sector_code:'C'},
  {code:'40', name:'仪器仪表制造业', sector_code:'C'},
  {code:'63', name:'电信、广播电视和卫星传输服务', sector_code:'I'},
  {code:'64', name:'互联网和相关服务', sector_code:'I'},
  {code:'65', name:'软件和信息技术服务业', sector_code:'I'},
  {code:'66', name:'货币金融服务', sector_code:'J'},
  {code:'67', name:'资本市场服务', sector_code:'J'},
  {code:'69', name:'其他金融业', sector_code:'J'},
  {code:'73', name:'研究和试验发展', sector_code:'M'},
  {code:'83', name:'教育', sector_code:'P'},
  {code:'84', name:'卫生', sector_code:'Q'},
  {code:'86', name:'娱乐业', sector_code:'R'}
] AS row
MERGE (d:IndustryDivision {code: row.code})
SET d.name = row.name,
    d.taxonomy_version = '1.0'
WITH d, row
MATCH (s:IndustrySector {code: row.sector_code})
MERGE (d)-[:BELONGS_TO_SECTOR]->(s);

// --- D.3 Create IndustryGroup nodes and link to IndustryDivision ---
UNWIND [
  {code:'361', name:'汽车整车制造', division_code:'36'},
  {code:'384', name:'电池制造', division_code:'38'},
  {code:'391', name:'计算机制造', division_code:'39'},
  {code:'392', name:'通信设备制造', division_code:'39'},
  {code:'397', name:'电子器件制造', division_code:'39'},
  {code:'631', name:'电信', division_code:'63'},
  {code:'642', name:'互联网信息服务', division_code:'64'},
  {code:'643', name:'互联网平台', division_code:'64'},
  {code:'645', name:'互联网数据服务', division_code:'64'},
  {code:'651', name:'软件开发', division_code:'65'},
  {code:'652', name:'集成电路设计', division_code:'65'},
  {code:'654', name:'运行维护服务', division_code:'65'},
  {code:'659', name:'其他信息技术服务业', division_code:'65'},
  {code:'832', name:'高等教育', division_code:'83'},
  {code:'839', name:'其他教育', division_code:'83'},
  {code:'841', name:'医院', division_code:'84'},
  {code:'862', name:'数字内容服务', division_code:'86'}
] AS row
MERGE (g:IndustryGroup {code: row.code})
SET g.name = row.name,
    g.taxonomy_version = '1.0'
WITH g, row
MATCH (d:IndustryDivision {code: row.division_code})
MERGE (g)-[:BELONGS_TO_DIVISION]->(d);

// --- D.4 UNCLASSIFIED placeholder nodes ---
MERGE (s:IndustrySector {code: 'UNCLASSIFIED'})
SET s.name = '待分类',
    s.description = '暂未归入任何已知门类的行业',
    s.taxonomy_version = '1.0';

MERGE (d:IndustryDivision {code: 'UNCLASSIFIED'})
SET d.name = '待分类',
    d.description = '暂未归入任何已知大类的行业',
    d.taxonomy_version = '1.0'
WITH d
MATCH (s:IndustrySector {code: 'UNCLASSIFIED'})
MERGE (d)-[:BELONGS_TO_SECTOR]->(s);

MERGE (g:IndustryGroup {code: 'UNCLASSIFIED'})
SET g.name = '待分类',
    g.description = '暂未归入任何已知中类的行业',
    g.taxonomy_version = '1.0'
WITH g
MATCH (d:IndustryDivision {code: 'UNCLASSIFIED'})
MERGE (g)-[:BELONGS_TO_DIVISION]->(d);

// =============================================================================
// SECTION E: ABILITY TAXONOMY (3-level: Dimension -> Cluster -> Competency)
// =============================================================================

// --- E.1 Create AbilityDimension nodes ---
UNWIND [
  {code:'ABL-01', name:'技术能力', description:'编程、AI/ML、基础设施、安全等方面的专业技术能力。'},
  {code:'ABL-02', name:'业务能力', description:'产品需求分析、行业知识、市场分析等方面的业务能力。'},
  {code:'ABL-03', name:'管理能力', description:'项目管理、团队管理、战略规划等方面的管理能力。'},
  {code:'ABL-04', name:'软技能', description:'沟通协作、思维学习、职业素养等方面的跨领域通用能力。'},
  {code:'ABL-05', name:'领域专项能力', description:'金融科技、医疗AI、自动驾驶等特定垂直领域的专项能力。'}
] AS row
MERGE (d:AbilityDimension {code: row.code})
SET d.name = row.name,
    d.description = row.description,
    d.taxonomy_version = '1.0',
    d.standard_ref = "O*NET Content Model";

// --- E.2 Create CompetencyCluster nodes and link to AbilityDimension ---
UNWIND [
  {code:'CLS-0101', name:'编程与软件开发能力', dim_code:'ABL-01', description:'代码编写调试、算法数据结构、系统设计架构、技术方案设计。'},
  {code:'CLS-0102', name:'数据与AI能力', dim_code:'ABL-01', description:'数据建模分析、机器学习建模、数据工程(ETL/数仓)、数据可视化。'},
  {code:'CLS-0103', name:'基础设施与运维能力', dim_code:'ABL-01', description:'云基础设施管理、自动化运维(IaC)、故障诊断恢复、性能优化。'},
  {code:'CLS-0104', name:'安全与质量能力', dim_code:'ABL-01', description:'安全风险评估、渗透测试防御、测试策略设计、代码审查质量保证。'},
  {code:'CLS-0201', name:'产品与需求能力', dim_code:'ABL-02', description:'需求分析定义、用户研究画像、产品路线图规划、竞品市场分析。'},
  {code:'CLS-0202', name:'行业与应用能力', dim_code:'ABL-02', description:'行业知识(金融/医疗/教育/制造)、业务流程理解、法规合规、技术趋势洞察。'},
  {code:'CLS-0301', name:'项目管理能力', dim_code:'ABL-03', description:'项目计划控制、敏捷/Scrum管理、风险管理、资源协调分配。'},
  {code:'CLS-0302', name:'团队管理能力', dim_code:'ABL-03', description:'技术团队领导、绩效管理激励、冲突解决决策、跨部门协作。'},
  {code:'CLS-0303', name:'战略与规划能力', dim_code:'ABL-03', description:'技术战略制定、预算成本控制、组织架构设计。'},
  {code:'CLS-0401', name:'沟通与协作', dim_code:'ABL-04', description:'技术文档撰写、口头表达演讲、团队协作、跨职能沟通。'},
  {code:'CLS-0402', name:'思维与学习能力', dim_code:'ABL-04', description:'分析批判性思维、快速学习技术适应、问题解决、创新创造力。'},
  {code:'CLS-0403', name:'职业素养', dim_code:'ABL-04', description:'时间管理自我驱动、责任心抗压能力、职业道德保密、用户/客户为中心。'},
  {code:'CLS-0501', name:'金融科技专项', dim_code:'ABL-05', description:'量化策略开发、风控建模、金融产品设计。'},
  {code:'CLS-0502', name:'医疗AI专项', dim_code:'ABL-05', description:'医学影像分析、临床决策支持、医疗数据处理(HIPAA)。'},
  {code:'CLS-0503', name:'自动驾驶专项', dim_code:'ABL-05', description:'传感器融合、路径规划与控制、功能安全(ISO 26262)。'}
] AS row
MERGE (c:CompetencyCluster {code: row.code})
SET c.name = row.name,
    c.description = row.description,
    c.taxonomy_version = '1.0'
WITH c, row
MATCH (d:AbilityDimension {code: row.dim_code})
MERGE (c)-[:BELONGS_TO_DIMENSION]->(d);

// --- E.3 Create Competency nodes and link to CompetencyCluster ---
UNWIND [
  {code:'CMP-010101', name:'代码编写与调试', cluster_code:'CLS-0101'},
  {code:'CMP-010102', name:'算法与数据结构', cluster_code:'CLS-0101'},
  {code:'CMP-010103', name:'系统设计与架构', cluster_code:'CLS-0101'},
  {code:'CMP-010104', name:'技术方案设计', cluster_code:'CLS-0101'},
  {code:'CMP-010201', name:'数据建模与分析', cluster_code:'CLS-0102'},
  {code:'CMP-010202', name:'机器学习建模', cluster_code:'CLS-0102'},
  {code:'CMP-010203', name:'数据工程', cluster_code:'CLS-0102'},
  {code:'CMP-010204', name:'数据可视化', cluster_code:'CLS-0102'},
  {code:'CMP-010301', name:'云基础设施管理', cluster_code:'CLS-0103'},
  {code:'CMP-010302', name:'自动化运维', cluster_code:'CLS-0103'},
  {code:'CMP-010303', name:'故障诊断与恢复', cluster_code:'CLS-0103'},
  {code:'CMP-010304', name:'性能优化与容量规划', cluster_code:'CLS-0103'},
  {code:'CMP-010401', name:'安全风险评估', cluster_code:'CLS-0104'},
  {code:'CMP-010402', name:'渗透测试与防御', cluster_code:'CLS-0104'},
  {code:'CMP-010403', name:'测试策略设计', cluster_code:'CLS-0104'},
  {code:'CMP-010404', name:'代码审查与质量保证', cluster_code:'CLS-0104'},
  {code:'CMP-020101', name:'需求分析与定义', cluster_code:'CLS-0201'},
  {code:'CMP-020102', name:'用户研究与画像', cluster_code:'CLS-0201'},
  {code:'CMP-020103', name:'产品路线图规划', cluster_code:'CLS-0201'},
  {code:'CMP-020104', name:'竞品与市场分析', cluster_code:'CLS-0201'},
  {code:'CMP-020201', name:'行业知识', cluster_code:'CLS-0202'},
  {code:'CMP-020202', name:'业务流程理解', cluster_code:'CLS-0202'},
  {code:'CMP-020203', name:'法规与合规知识', cluster_code:'CLS-0202'},
  {code:'CMP-020204', name:'技术趋势洞察', cluster_code:'CLS-0202'},
  {code:'CMP-030101', name:'项目计划与控制', cluster_code:'CLS-0301'},
  {code:'CMP-030102', name:'敏捷/Scrum管理', cluster_code:'CLS-0301'},
  {code:'CMP-030103', name:'风险管理', cluster_code:'CLS-0301'},
  {code:'CMP-030104', name:'资源协调与分配', cluster_code:'CLS-0301'},
  {code:'CMP-030201', name:'技术团队领导', cluster_code:'CLS-0302'},
  {code:'CMP-030202', name:'绩效管理与激励', cluster_code:'CLS-0302'},
  {code:'CMP-030203', name:'冲突解决与决策', cluster_code:'CLS-0302'},
  {code:'CMP-030204', name:'跨部门协作', cluster_code:'CLS-0302'},
  {code:'CMP-030301', name:'技术战略制定', cluster_code:'CLS-0303'},
  {code:'CMP-030302', name:'预算与成本控制', cluster_code:'CLS-0303'},
  {code:'CMP-030303', name:'组织架构设计', cluster_code:'CLS-0303'},
  {code:'CMP-040101', name:'技术文档撰写', cluster_code:'CLS-0401'},
  {code:'CMP-040102', name:'口头表达与演讲', cluster_code:'CLS-0401'},
  {code:'CMP-040103', name:'团队协作', cluster_code:'CLS-0401'},
  {code:'CMP-040104', name:'跨职能沟通', cluster_code:'CLS-0401'},
  {code:'CMP-040201', name:'分析与批判性思维', cluster_code:'CLS-0402'},
  {code:'CMP-040202', name:'快速学习与技术适应', cluster_code:'CLS-0402'},
  {code:'CMP-040203', name:'问题解决能力', cluster_code:'CLS-0402'},
  {code:'CMP-040204', name:'创新与创造力', cluster_code:'CLS-0402'},
  {code:'CMP-040301', name:'时间管理与自我驱动', cluster_code:'CLS-0403'},
  {code:'CMP-040302', name:'责任心与抗压能力', cluster_code:'CLS-0403'},
  {code:'CMP-040303', name:'职业道德与保密意识', cluster_code:'CLS-0403'},
  {code:'CMP-040304', name:'以用户/客户为中心', cluster_code:'CLS-0403'},
  {code:'CMP-050101', name:'量化策略开发', cluster_code:'CLS-0501'},
  {code:'CMP-050102', name:'风控建模', cluster_code:'CLS-0501'},
  {code:'CMP-050103', name:'金融产品设计', cluster_code:'CLS-0501'},
  {code:'CMP-050201', name:'医学影像分析', cluster_code:'CLS-0502'},
  {code:'CMP-050202', name:'临床决策支持', cluster_code:'CLS-0502'},
  {code:'CMP-050203', name:'医疗数据处理', cluster_code:'CLS-0502'},
  {code:'CMP-050301', name:'传感器融合', cluster_code:'CLS-0503'},
  {code:'CMP-050302', name:'路径规划与控制', cluster_code:'CLS-0503'},
  {code:'CMP-050303', name:'功能安全', cluster_code:'CLS-0503'}
] AS row
MERGE (c:Competency {code: row.code})
SET c.name = row.name,
    c.taxonomy_version = '1.0'
WITH c, row
MATCH (cl:CompetencyCluster {code: row.cluster_code})
MERGE (c)-[:BELONGS_TO_CLUSTER]->(cl);

// --- E.4 UNCLASSIFIED placeholder nodes ---
MERGE (d:AbilityDimension {code: 'UNCLASSIFIED'})
SET d.name = '待分类',
    d.description = '暂未归入任何已知维度的能力',
    d.taxonomy_version = '1.0';

MERGE (c:CompetencyCluster {code: 'UNCLASSIFIED'})
SET c.name = '待分类',
    c.description = '暂未归入任何已知能力群的能力',
    c.taxonomy_version = '1.0'
WITH c
MATCH (d:AbilityDimension {code: 'UNCLASSIFIED'})
MERGE (c)-[:BELONGS_TO_DIMENSION]->(d);

MERGE (cmp:Competency {code: 'UNCLASSIFIED'})
SET cmp.name = '待分类',
    cmp.taxonomy_version = '1.0'
WITH cmp
MATCH (c:CompetencyCluster {code: 'UNCLASSIFIED'})
MERGE (cmp)-[:BELONGS_TO_CLUSTER]->(c);

// =============================================================================
// SECTION F: EDUCATION & EXPERIENCE ORDERING
// =============================================================================

// --- F.1 Education ordered levels ---
// Updates existing Education nodes with ordinal integer ranking (0=不限 ~ 6=博士后)
MATCH (e:Education {name: '学历不限'})
SET e.ordinal = 0;

MATCH (e:Education {name: '高中/中专及以下'})
SET e.ordinal = 1;

MATCH (e:Education {name: '大专'})
SET e.ordinal = 2;

MATCH (e:Education {name: '本科'})
SET e.ordinal = 3;

MATCH (e:Education {name: '硕士'})
SET e.ordinal = 4;

MATCH (e:Education {name: '博士'})
SET e.ordinal = 5;

MATCH (e:Education {name: '博士后'})
SET e.ordinal = 6;

// --- F.2 Experience ordered levels ---
// Updates existing Experience nodes with ordinal, min_years (float), max_years (float)
MATCH (e:Experience {name: '经验不限'})
SET e.ordinal = 0,
    e.min_years = toFloat(0),
    e.max_years = toFloat(99);

MATCH (e:Experience {name: '应届生'})
SET e.ordinal = 1,
    e.min_years = toFloat(0),
    e.max_years = toFloat(0);

MATCH (e:Experience {name: '1年以下'})
SET e.ordinal = 2,
    e.min_years = toFloat(0),
    e.max_years = toFloat(1);

MATCH (e:Experience {name: '1-3年'})
SET e.ordinal = 3,
    e.min_years = toFloat(1),
    e.max_years = toFloat(3);

MATCH (e:Experience {name: '3-5年'})
SET e.ordinal = 4,
    e.min_years = toFloat(3),
    e.max_years = toFloat(5);

MATCH (e:Experience {name: '5-10年'})
SET e.ordinal = 5,
    e.min_years = toFloat(5),
    e.max_years = toFloat(10);

MATCH (e:Experience {name: '10年以上'})
SET e.ordinal = 6,
    e.min_years = toFloat(10),
    e.max_years = toFloat(99);

// =============================================================================
// SECTION G: EXISTING NODE ATTRIBUTE BACKFILL
// =============================================================================

// --- G.1 JobTitle -> JobCategory keyword-based classification ---
// Uses CONTAINS-based matching rules. Order matters: first match wins.
// Unmatched job titles remain unclassified (can be handled manually).
// [C-1 FIXED] domain_name is now hardcoded instead of referencing c.name (which was JobCategory.name)

MATCH (t:JobTitle)
WHERE (t.name CONTAINS 'Java' OR t.name CONTAINS 'Golang' OR t.name CONTAINS 'Go开发' OR t.name CONTAINS 'GO开发')
  AND t.category_code IS NULL
MATCH (c:JobCategory {code: 'CAT-0101'})
MERGE (t)-[:BELONGS_TO_CATEGORY]->(c)
SET t.domain_code = 'DOM-01',
    t.domain_name = '软件与算法开发',
    t.category_code = 'CAT-0101';

MATCH (t:JobTitle)
WHERE (t.name CONTAINS 'Python' OR t.name CONTAINS 'PYTHON')
  AND t.category_code IS NULL
MATCH (c:JobCategory {code: 'CAT-0101'})
MERGE (t)-[:BELONGS_TO_CATEGORY]->(c)
SET t.domain_code = 'DOM-01',
    t.domain_name = '软件与算法开发',
    t.category_code = 'CAT-0101';

MATCH (t:JobTitle)
WHERE (t.name CONTAINS 'C++' OR t.name CONTAINS 'C/C++' OR t.name CONTAINS 'CPP')
  AND t.category_code IS NULL
MATCH (c:JobCategory {code: 'CAT-0101'})
MERGE (t)-[:BELONGS_TO_CATEGORY]->(c)
SET t.domain_code = 'DOM-01',
    t.domain_name = '软件与算法开发',
    t.category_code = 'CAT-0101';

MATCH (t:JobTitle)
WHERE (t.name CONTAINS 'PHP')
  AND t.category_code IS NULL
MATCH (c:JobCategory {code: 'CAT-0101'})
MERGE (t)-[:BELONGS_TO_CATEGORY]->(c)
SET t.domain_code = 'DOM-01',
    t.domain_name = '软件与算法开发',
    t.category_code = 'CAT-0101';

MATCH (t:JobTitle)
WHERE (t.name CONTAINS '后端' OR t.name CONTAINS '服务端')
  AND t.category_code IS NULL
MATCH (c:JobCategory {code: 'CAT-0101'})
MERGE (t)-[:BELONGS_TO_CATEGORY]->(c)
SET t.domain_code = 'DOM-01',
    t.domain_name = '软件与算法开发',
    t.category_code = 'CAT-0101';

MATCH (t:JobTitle)
WHERE (t.name CONTAINS '前端' OR t.name CONTAINS 'web前端' OR t.name CONTAINS 'Web前端' OR t.name CONTAINS 'WEB前端' OR t.name CONTAINS 'H5')
  AND t.category_code IS NULL
MATCH (c:JobCategory {code: 'CAT-0102'})
MERGE (t)-[:BELONGS_TO_CATEGORY]->(c)
SET t.domain_code = 'DOM-01',
    t.domain_name = '软件与算法开发',
    t.category_code = 'CAT-0102';

MATCH (t:JobTitle)
WHERE (t.name CONTAINS '全栈')
  AND t.category_code IS NULL
MATCH (c:JobCategory {code: 'CAT-0102'})
MERGE (t)-[:BELONGS_TO_CATEGORY]->(c)
SET t.domain_code = 'DOM-01',
    t.domain_name = '软件与算法开发',
    t.category_code = 'CAT-0102';

MATCH (t:JobTitle)
WHERE (t.name CONTAINS 'Android' OR t.name CONTAINS '安卓' OR t.name CONTAINS 'android')
  AND t.category_code IS NULL
MATCH (c:JobCategory {code: 'CAT-0103'})
MERGE (t)-[:BELONGS_TO_CATEGORY]->(c)
SET t.domain_code = 'DOM-01',
    t.domain_name = '软件与算法开发',
    t.category_code = 'CAT-0103';

MATCH (t:JobTitle)
WHERE (t.name CONTAINS 'iOS' OR t.name CONTAINS 'ios' OR t.name CONTAINS 'IOS')
  AND t.category_code IS NULL
MATCH (c:JobCategory {code: 'CAT-0103'})
MERGE (t)-[:BELONGS_TO_CATEGORY]->(c)
SET t.domain_code = 'DOM-01',
    t.domain_name = '软件与算法开发',
    t.category_code = 'CAT-0103';

MATCH (t:JobTitle)
WHERE (t.name CONTAINS '移动端' OR t.name CONTAINS '移动开发')
  AND t.category_code IS NULL
MATCH (c:JobCategory {code: 'CAT-0103'})
MERGE (t)-[:BELONGS_TO_CATEGORY]->(c)
SET t.domain_code = 'DOM-01',
    t.domain_name = '软件与算法开发',
    t.category_code = 'CAT-0103';

MATCH (t:JobTitle)
WHERE (t.name CONTAINS 'Flutter' OR t.name CONTAINS 'React Native' OR t.name CONTAINS 'RN开发')
  AND t.category_code IS NULL
MATCH (c:JobCategory {code: 'CAT-0103'})
MERGE (t)-[:BELONGS_TO_CATEGORY]->(c)
SET t.domain_code = 'DOM-01',
    t.domain_name = '软件与算法开发',
    t.category_code = 'CAT-0103';

MATCH (t:JobTitle)
WHERE (t.name CONTAINS '架构师' OR t.name CONTAINS '架构')
  AND t.category_code IS NULL
MATCH (c:JobCategory {code: 'CAT-0104'})
MERGE (t)-[:BELONGS_TO_CATEGORY]->(c)
SET t.domain_code = 'DOM-01',
    t.domain_name = '软件与算法开发',
    t.category_code = 'CAT-0104';

MATCH (t:JobTitle)
WHERE (t.name CONTAINS '技术总监' OR t.name CONTAINS 'CTO')
  AND t.category_code IS NULL
MATCH (c:JobCategory {code: 'CAT-0104'})
MERGE (t)-[:BELONGS_TO_CATEGORY]->(c)
SET t.domain_code = 'DOM-01',
    t.domain_name = '软件与算法开发',
    t.category_code = 'CAT-0104';

MATCH (t:JobTitle)
WHERE (t.name CONTAINS '嵌入式')
  AND t.category_code IS NULL
MATCH (c:JobCategory {code: 'CAT-0105'})
MERGE (t)-[:BELONGS_TO_CATEGORY]->(c)
SET t.domain_code = 'DOM-01',
    t.domain_name = '软件与算法开发',
    t.category_code = 'CAT-0105';

MATCH (t:JobTitle)
WHERE (t.name CONTAINS '物联网' OR t.name CONTAINS 'IOT' OR t.name CONTAINS 'IoT')
  AND t.category_code IS NULL
MATCH (c:JobCategory {code: 'CAT-0105'})
MERGE (t)-[:BELONGS_TO_CATEGORY]->(c)
SET t.domain_code = 'DOM-01',
    t.domain_name = '软件与算法开发',
    t.category_code = 'CAT-0105';

MATCH (t:JobTitle)
WHERE (t.name CONTAINS '驱动开发')
  AND t.category_code IS NULL
MATCH (c:JobCategory {code: 'CAT-0105'})
MERGE (t)-[:BELONGS_TO_CATEGORY]->(c)
SET t.domain_code = 'DOM-01',
    t.domain_name = '软件与算法开发',
    t.category_code = 'CAT-0105';

MATCH (t:JobTitle)
WHERE (t.name CONTAINS '音视频')
  AND t.category_code IS NULL
MATCH (c:JobCategory {code: 'CAT-0106'})
MERGE (t)-[:BELONGS_TO_CATEGORY]->(c)
SET t.domain_code = 'DOM-01',
    t.domain_name = '软件与算法开发',
    t.category_code = 'CAT-0106';

MATCH (t:JobTitle)
WHERE (t.name CONTAINS '软件开发' OR t.name CONTAINS '软件工程师')
  AND t.category_code IS NULL
MATCH (c:JobCategory {code: 'CAT-0106'})
MERGE (t)-[:BELONGS_TO_CATEGORY]->(c)
SET t.domain_code = 'DOM-01',
    t.domain_name = '软件与算法开发',
    t.category_code = 'CAT-0106';

MATCH (t:JobTitle)
WHERE (t.name CONTAINS '算法工程师' OR t.name CONTAINS '算法')
  AND t.category_code IS NULL
MATCH (c:JobCategory {code: 'CAT-0201'})
MERGE (t)-[:BELONGS_TO_CATEGORY]->(c)
SET t.domain_code = 'DOM-02',
    t.domain_name = '数据与人工智能',
    t.category_code = 'CAT-0201';

MATCH (t:JobTitle)
WHERE (t.name CONTAINS '机器学习')
  AND t.category_code IS NULL
MATCH (c:JobCategory {code: 'CAT-0201'})
MERGE (t)-[:BELONGS_TO_CATEGORY]->(c)
SET t.domain_code = 'DOM-02',
    t.domain_name = '数据与人工智能',
    t.category_code = 'CAT-0201';

MATCH (t:JobTitle)
WHERE (t.name CONTAINS '深度学习')
  AND t.category_code IS NULL
MATCH (c:JobCategory {code: 'CAT-0201'})
MERGE (t)-[:BELONGS_TO_CATEGORY]->(c)
SET t.domain_code = 'DOM-02',
    t.domain_name = '数据与人工智能',
    t.category_code = 'CAT-0201';

MATCH (t:JobTitle)
WHERE (t.name CONTAINS 'NLP' OR t.name CONTAINS '自然语言')
  AND t.category_code IS NULL
MATCH (c:JobCategory {code: 'CAT-0201'})
MERGE (t)-[:BELONGS_TO_CATEGORY]->(c)
SET t.domain_code = 'DOM-02',
    t.domain_name = '数据与人工智能',
    t.category_code = 'CAT-0201';

MATCH (t:JobTitle)
WHERE (t.name CONTAINS '计算机视觉' OR t.name CONTAINS 'CV算法')
  AND t.category_code IS NULL
MATCH (c:JobCategory {code: 'CAT-0201'})
MERGE (t)-[:BELONGS_TO_CATEGORY]->(c)
SET t.domain_code = 'DOM-02',
    t.domain_name = '数据与人工智能',
    t.category_code = 'CAT-0201';

MATCH (t:JobTitle)
WHERE (t.name CONTAINS '人工智能' OR t.name CONTAINS 'AI工程师' OR t.name CONTAINS 'AI应用')
  AND t.category_code IS NULL
MATCH (c:JobCategory {code: 'CAT-0202'})
MERGE (t)-[:BELONGS_TO_CATEGORY]->(c)
SET t.domain_code = 'DOM-02',
    t.domain_name = '数据与人工智能',
    t.category_code = 'CAT-0202';

MATCH (t:JobTitle)
WHERE (t.name CONTAINS '提示词' OR t.name CONTAINS 'Prompt')
  AND t.category_code IS NULL
MATCH (c:JobCategory {code: 'CAT-0202'})
MERGE (t)-[:BELONGS_TO_CATEGORY]->(c)
SET t.domain_code = 'DOM-02',
    t.domain_name = '数据与人工智能',
    t.category_code = 'CAT-0202';

MATCH (t:JobTitle)
WHERE (t.name CONTAINS 'MLOps' OR t.name CONTAINS 'MLOPS')
  AND t.category_code IS NULL
MATCH (c:JobCategory {code: 'CAT-0202'})
MERGE (t)-[:BELONGS_TO_CATEGORY]->(c)
SET t.domain_code = 'DOM-02',
    t.domain_name = '数据与人工智能',
    t.category_code = 'CAT-0202';

MATCH (t:JobTitle)
WHERE (t.name CONTAINS 'AIGC')
  AND t.category_code IS NULL
MATCH (c:JobCategory {code: 'CAT-0202'})
MERGE (t)-[:BELONGS_TO_CATEGORY]->(c)
SET t.domain_code = 'DOM-02',
    t.domain_name = '数据与人工智能',
    t.category_code = 'CAT-0202';

MATCH (t:JobTitle)
WHERE (t.name CONTAINS '大数据' OR t.name CONTAINS '数据开发' OR t.name CONTAINS '数据平台' OR t.name CONTAINS 'ETL')
  AND t.category_code IS NULL
MATCH (c:JobCategory {code: 'CAT-0203'})
MERGE (t)-[:BELONGS_TO_CATEGORY]->(c)
SET t.domain_code = 'DOM-02',
    t.domain_name = '数据与人工智能',
    t.category_code = 'CAT-0203';

MATCH (t:JobTitle)
WHERE (t.name CONTAINS '数据仓库' OR t.name CONTAINS '数仓')
  AND t.category_code IS NULL
MATCH (c:JobCategory {code: 'CAT-0203'})
MERGE (t)-[:BELONGS_TO_CATEGORY]->(c)
SET t.domain_code = 'DOM-02',
    t.domain_name = '数据与人工智能',
    t.category_code = 'CAT-0203';

MATCH (t:JobTitle)
WHERE (t.name CONTAINS '数据分析' OR t.name CONTAINS '数据分析师')
  AND t.category_code IS NULL
MATCH (c:JobCategory {code: 'CAT-0204'})
MERGE (t)-[:BELONGS_TO_CATEGORY]->(c)
SET t.domain_code = 'DOM-02',
    t.domain_name = '数据与人工智能',
    t.category_code = 'CAT-0204';

MATCH (t:JobTitle)
WHERE (t.name CONTAINS '数据科学' OR t.name CONTAINS '数据科学家')
  AND t.category_code IS NULL
MATCH (c:JobCategory {code: 'CAT-0204'})
MERGE (t)-[:BELONGS_TO_CATEGORY]->(c)
SET t.domain_code = 'DOM-02',
    t.domain_name = '数据与人工智能',
    t.category_code = 'CAT-0204';

MATCH (t:JobTitle)
WHERE (t.name CONTAINS '商业分析' OR t.name CONTAINS 'BA' OR t.name CONTAINS '商业智能' OR t.name CONTAINS 'BI工程师' OR t.name CONTAINS 'BI ')
  AND t.category_code IS NULL
MATCH (c:JobCategory {code: 'CAT-0204'})
MERGE (t)-[:BELONGS_TO_CATEGORY]->(c)
SET t.domain_code = 'DOM-02',
    t.domain_name = '数据与人工智能',
    t.category_code = 'CAT-0204';

MATCH (t:JobTitle)
WHERE (t.name CONTAINS '运维' OR t.name CONTAINS 'SRE' OR t.name CONTAINS 'sre')
  AND t.category_code IS NULL
MATCH (c:JobCategory {code: 'CAT-0301'})
MERGE (t)-[:BELONGS_TO_CATEGORY]->(c)
SET t.domain_code = 'DOM-03',
    t.domain_name = '基础设施与运维',
    t.category_code = 'CAT-0301';

MATCH (t:JobTitle)
WHERE (t.name CONTAINS '系统管理员')
  AND t.category_code IS NULL
MATCH (c:JobCategory {code: 'CAT-0301'})
MERGE (t)-[:BELONGS_TO_CATEGORY]->(c)
SET t.domain_code = 'DOM-03',
    t.domain_name = '基础设施与运维',
    t.category_code = 'CAT-0301';

MATCH (t:JobTitle)
WHERE (t.name CONTAINS '云计算' OR t.name CONTAINS '云平台' OR t.name CONTAINS '云原生')
  AND t.category_code IS NULL
MATCH (c:JobCategory {code: 'CAT-0302'})
MERGE (t)-[:BELONGS_TO_CATEGORY]->(c)
SET t.domain_code = 'DOM-03',
    t.domain_name = '基础设施与运维',
    t.category_code = 'CAT-0302';

MATCH (t:JobTitle)
WHERE (t.name CONTAINS '平台工程' OR t.name CONTAINS 'DevOps' OR t.name CONTAINS 'DEVOPS' OR t.name CONTAINS 'devops')
  AND t.category_code IS NULL
MATCH (c:JobCategory {code: 'CAT-0302'})
MERGE (t)-[:BELONGS_TO_CATEGORY]->(c)
SET t.domain_code = 'DOM-03',
    t.domain_name = '基础设施与运维',
    t.category_code = 'CAT-0302';

MATCH (t:JobTitle)
WHERE (t.name CONTAINS '网络工程师' OR t.name CONTAINS '网络')
  AND t.category_code IS NULL
MATCH (c:JobCategory {code: 'CAT-0303'})
MERGE (t)-[:BELONGS_TO_CATEGORY]->(c)
SET t.domain_code = 'DOM-03',
    t.domain_name = '基础设施与运维',
    t.category_code = 'CAT-0303';

MATCH (t:JobTitle)
WHERE (t.name CONTAINS '通信工程师' OR t.name CONTAINS '通信')
  AND t.category_code IS NULL
MATCH (c:JobCategory {code: 'CAT-0303'})
MERGE (t)-[:BELONGS_TO_CATEGORY]->(c)
SET t.domain_code = 'DOM-03',
    t.domain_name = '基础设施与运维',
    t.category_code = 'CAT-0303';

MATCH (t:JobTitle)
WHERE (t.name CONTAINS '产品经理' OR t.name CONTAINS '产品总监' OR t.name CONTAINS '产品VP' OR t.name CONTAINS '产品负责人')
  AND t.category_code IS NULL
MATCH (c:JobCategory {code: 'CAT-0401'})
MERGE (t)-[:BELONGS_TO_CATEGORY]->(c)
SET t.domain_code = 'DOM-04',
    t.domain_name = '产品与项目管理',
    t.category_code = 'CAT-0401';

MATCH (t:JobTitle)
WHERE (t.name CONTAINS '产品')
  AND t.category_code IS NULL
MATCH (c:JobCategory {code: 'CAT-0401'})
MERGE (t)-[:BELONGS_TO_CATEGORY]->(c)
SET t.domain_code = 'DOM-04',
    t.domain_name = '产品与项目管理',
    t.category_code = 'CAT-0401';

MATCH (t:JobTitle)
WHERE (t.name CONTAINS '项目经理' OR t.name CONTAINS '项目助理' OR t.name CONTAINS '项目主管')
  AND t.category_code IS NULL
MATCH (c:JobCategory {code: 'CAT-0402'})
MERGE (t)-[:BELONGS_TO_CATEGORY]->(c)
SET t.domain_code = 'DOM-04',
    t.domain_name = '产品与项目管理',
    t.category_code = 'CAT-0402';

MATCH (t:JobTitle)
WHERE (t.name CONTAINS '敏捷教练' OR t.name CONTAINS 'Scrum Master' OR t.name CONTAINS 'SCRUM')
  AND t.category_code IS NULL
MATCH (c:JobCategory {code: 'CAT-0402'})
MERGE (t)-[:BELONGS_TO_CATEGORY]->(c)
SET t.domain_code = 'DOM-04',
    t.domain_name = '产品与项目管理',
    t.category_code = 'CAT-0402';

MATCH (t:JobTitle)
WHERE (t.name CONTAINS 'PMO' OR t.name CONTAINS 'pmo')
  AND t.category_code IS NULL
MATCH (c:JobCategory {code: 'CAT-0402'})
MERGE (t)-[:BELONGS_TO_CATEGORY]->(c)
SET t.domain_code = 'DOM-04',
    t.domain_name = '产品与项目管理',
    t.category_code = 'CAT-0402';

MATCH (t:JobTitle)
WHERE (t.name CONTAINS '技术经理' OR t.name CONTAINS '研发总监' OR t.name CONTAINS '研发经理')
  AND t.category_code IS NULL
MATCH (c:JobCategory {code: 'CAT-0403'})
MERGE (t)-[:BELONGS_TO_CATEGORY]->(c)
SET t.domain_code = 'DOM-04',
    t.domain_name = '产品与项目管理',
    t.category_code = 'CAT-0403';

MATCH (t:JobTitle)
WHERE (t.name CONTAINS '技术VP' OR t.name CONTAINS '技术副总')
  AND t.category_code IS NULL
MATCH (c:JobCategory {code: 'CAT-0403'})
MERGE (t)-[:BELONGS_TO_CATEGORY]->(c)
SET t.domain_code = 'DOM-04',
    t.domain_name = '产品与项目管理',
    t.category_code = 'CAT-0403';

MATCH (t:JobTitle)
WHERE (t.name CONTAINS '测试' OR t.name CONTAINS 'QA' OR t.name CONTAINS 'qa' OR t.name CONTAINS 'Qa')
  AND t.category_code IS NULL
MATCH (c:JobCategory {code: 'CAT-0501'})
MERGE (t)-[:BELONGS_TO_CATEGORY]->(c)
SET t.domain_code = 'DOM-05',
    t.domain_name = '质量与安全',
    t.category_code = 'CAT-0501';

MATCH (t:JobTitle)
WHERE (t.name CONTAINS '质量' OR t.name CONTAINS '品控')
  AND t.category_code IS NULL
MATCH (c:JobCategory {code: 'CAT-0501'})
MERGE (t)-[:BELONGS_TO_CATEGORY]->(c)
SET t.domain_code = 'DOM-05',
    t.domain_name = '质量与安全',
    t.category_code = 'CAT-0501';

MATCH (t:JobTitle)
WHERE (t.name CONTAINS '安全工程师' OR t.name CONTAINS '安全架构' OR t.name CONTAINS '安全')
  AND t.category_code IS NULL
MATCH (c:JobCategory {code: 'CAT-0502'})
MERGE (t)-[:BELONGS_TO_CATEGORY]->(c)
SET t.domain_code = 'DOM-05',
    t.domain_name = '质量与安全',
    t.category_code = 'CAT-0502';

MATCH (t:JobTitle)
WHERE (t.name CONTAINS '渗透' OR t.name CONTAINS '渗透测试')
  AND t.category_code IS NULL
MATCH (c:JobCategory {code: 'CAT-0502'})
MERGE (t)-[:BELONGS_TO_CATEGORY]->(c)
SET t.domain_code = 'DOM-05',
    t.domain_name = '质量与安全',
    t.category_code = 'CAT-0502';

MATCH (t:JobTitle)
WHERE (t.name CONTAINS '数据安全')
  AND t.category_code IS NULL
MATCH (c:JobCategory {code: 'CAT-0502'})
MERGE (t)-[:BELONGS_TO_CATEGORY]->(c)
SET t.domain_code = 'DOM-05',
    t.domain_name = '质量与安全',
    t.category_code = 'CAT-0502';

MATCH (t:JobTitle)
WHERE (t.name CONTAINS '区块链' OR t.name CONTAINS 'web3' OR t.name CONTAINS 'Web3' OR t.name CONTAINS 'WEB3' OR t.name CONTAINS '智能合约' OR t.name CONTAINS 'DApp')
  AND t.category_code IS NULL
MATCH (c:JobCategory {code: 'CAT-0601'})
MERGE (t)-[:BELONGS_TO_CATEGORY]->(c)
SET t.domain_code = 'DOM-06',
    t.domain_name = '新兴与交叉技术',
    t.category_code = 'CAT-0601';

MATCH (t:JobTitle)
WHERE (t.name CONTAINS '游戏开发' OR t.name CONTAINS '游戏' OR t.name CONTAINS 'Unity' OR t.name CONTAINS 'UNITY' OR t.name CONTAINS 'Unreal' OR t.name CONTAINS 'UNREAL')
  AND t.category_code IS NULL
MATCH (c:JobCategory {code: 'CAT-0602'})
MERGE (t)-[:BELONGS_TO_CATEGORY]->(c)
SET t.domain_code = 'DOM-06',
    t.domain_name = '新兴与交叉技术',
    t.category_code = 'CAT-0602';

MATCH (t:JobTitle)
WHERE (t.name CONTAINS '量化' OR t.name CONTAINS 'Quant' OR t.name CONTAINS 'quant')
  AND t.category_code IS NULL
MATCH (c:JobCategory {code: 'CAT-0603'})
MERGE (t)-[:BELONGS_TO_CATEGORY]->(c)
SET t.domain_code = 'DOM-06',
    t.domain_name = '新兴与交叉技术',
    t.category_code = 'CAT-0603';

MATCH (t:JobTitle)
WHERE (t.name CONTAINS '金融科技' OR t.name CONTAINS 'FinTech' OR t.name CONTAINS 'fintech')
  AND t.category_code IS NULL
MATCH (c:JobCategory {code: 'CAT-0603'})
MERGE (t)-[:BELONGS_TO_CATEGORY]->(c)
SET t.domain_code = 'DOM-06',
    t.domain_name = '新兴与交叉技术',
    t.category_code = 'CAT-0603';

MATCH (t:JobTitle)
WHERE (t.name CONTAINS '数据标注' OR t.name CONTAINS '标注师' OR t.name CONTAINS 'AI训练师' OR t.name CONTAINS '训练师')
  AND t.category_code IS NULL
MATCH (c:JobCategory {code: 'CAT-0604'})
MERGE (t)-[:BELONGS_TO_CATEGORY]->(c)
SET t.domain_code = 'DOM-06',
    t.domain_name = '新兴与交叉技术',
    t.category_code = 'CAT-0604';

// --- G.2 JobTitle: relabel unmatched as 'Unclassified' in category_code ---
MATCH (t:JobTitle)
WHERE t.category_code IS NULL
SET t.category_code = 'UNCLASSIFIED',
    t.domain_code = 'UNCLASSIFIED';

// --- G.2b Backfill: resolve category_name from JobCategory nodes ---
// Placed after G.2 so UNCLASSIFIED codes (set in G.2) are also resolved.
MATCH (t:JobTitle)
WHERE t.category_code IS NOT NULL AND t.category_name IS NULL
MATCH (c:JobCategory {code: t.category_code})
SET t.category_name = c.name;

// --- G.3 Industry -> GB/T 4754 mapping ---
// Maps existing Industry node names to GB/T 4754-2017 codes
// [C-4 FIXED] 互联网/IT: group_code changed from '645' to '642' (互联网信息服务),
//   D.3 defines 645 as '互联网数据服务', not '软件开发'. 642 is a better match.
// [C-9 FIXED] 人工智能: added secondary BELONGS_TO_SECTOR for M-73.
// [C-10 FIXED] Removed empty string assignments for missing group codes.

MATCH (i:Industry {name: '互联网/IT'})
SET i.sector_code = 'I',
    i.sector_name = '信息传输、软件和信息技术服务业',
    i.division_code = '64',
    i.division_name = '互联网和相关服务',
    i.group_code = '642',
    i.group_name = '互联网信息服务',
    i.gb_code = 'I-64-642';
WITH i
MATCH (s:IndustrySector {code: 'I'})
MERGE (i)-[:BELONGS_TO_SECTOR]->(s);

MATCH (i:Industry {name: '人工智能'})
SET i.sector_code = 'I',
    i.sector_name = '信息传输、软件和信息技术服务业',
    i.division_code = '65',
    i.division_name = '软件和信息技术服务业',
    i.group_code = '659',
    i.group_name = '其他信息技术服务业',
    i.gb_code = 'I-65-659';
WITH i
MATCH (s:IndustrySector {code: 'I'})
MERGE (i)-[:BELONGS_TO_SECTOR]->(s)
WITH i
MATCH (m:IndustrySector {code: 'M'})
MERGE (i)-[:BELONGS_TO_SECTOR]->(m);

MATCH (i:Industry {name: '通信/电子'})
SET i.sector_code = 'C',
    i.sector_name = '制造业',
    i.division_code = '39',
    i.division_name = '计算机、通信和其他电子设备制造业',
    i.group_code = '392',
    i.group_name = '通信设备制造',
    i.gb_code = 'C-39-392';
WITH i
MATCH (s:IndustrySector {code: 'C'})
MERGE (i)-[:BELONGS_TO_SECTOR]->(s);

MATCH (i:Industry {name: '金融'})
SET i.sector_code = 'J',
    i.sector_name = '金融业',
    i.division_code = '66',
    i.division_name = '货币金融服务',
    i.gb_code = 'J-66';
WITH i
MATCH (s:IndustrySector {code: 'J'})
MERGE (i)-[:BELONGS_TO_SECTOR]->(s)
WITH i
REMOVE i.group_code, i.group_name;

MATCH (i:Industry {name: '金融科技'})
SET i.sector_code = 'J',
    i.sector_name = '金融业',
    i.division_code = '69',
    i.division_name = '其他金融业',
    i.gb_code = 'J-69';
WITH i
MATCH (s:IndustrySector {code: 'J'})
MERGE (i)-[:BELONGS_TO_SECTOR]->(s)
WITH i
REMOVE i.group_code, i.group_name;

MATCH (i:Industry {name: '教育/培训'})
SET i.sector_code = 'P',
    i.sector_name = '教育',
    i.division_code = '83',
    i.division_name = '教育',
    i.group_code = '839',
    i.group_name = '其他教育',
    i.gb_code = 'P-83-839';
WITH i
MATCH (s:IndustrySector {code: 'P'})
MERGE (i)-[:BELONGS_TO_SECTOR]->(s);

MATCH (i:Industry {name: '医疗健康'})
SET i.sector_code = 'Q',
    i.sector_name = '卫生和社会工作',
    i.division_code = '84',
    i.division_name = '卫生',
    i.group_code = '841',
    i.group_name = '医院',
    i.gb_code = 'Q-84-841';
WITH i
MATCH (s:IndustrySector {code: 'Q'})
MERGE (i)-[:BELONGS_TO_SECTOR]->(s);

MATCH (i:Industry {name: '智能制造'})
SET i.sector_code = 'C',
    i.sector_name = '制造业',
    i.division_code = '35',
    i.division_name = '专用设备制造业',
    i.gb_code = 'C-35';
WITH i
MATCH (s:IndustrySector {code: 'C'})
MERGE (i)-[:BELONGS_TO_SECTOR]->(s)
WITH i
REMOVE i.group_code, i.group_name;

MATCH (i:Industry {name: '汽车/出行'})
SET i.sector_code = 'C',
    i.sector_name = '制造业',
    i.division_code = '36',
    i.division_name = '汽车制造业',
    i.group_code = '361',
    i.group_name = '汽车整车制造',
    i.gb_code = 'C-36-361';
WITH i
MATCH (s:IndustrySector {code: 'C'})
MERGE (i)-[:BELONGS_TO_SECTOR]->(s);

MATCH (i:Industry {name: '电商/零售'})
SET i.sector_code = 'I',
    i.sector_name = '信息传输、软件和信息技术服务业',
    i.division_code = '64',
    i.division_name = '互联网和相关服务',
    i.group_code = '643',
    i.group_name = '互联网平台',
    i.gb_code = 'I-64-643';
WITH i
MATCH (s:IndustrySector {code: 'I'})
MERGE (i)-[:BELONGS_TO_SECTOR]->(s);

MATCH (i:Industry {name: '游戏/娱乐'})
SET i.sector_code = 'R',
    i.sector_name = '文化、体育和娱乐业',
    i.division_code = '86',
    i.division_name = '娱乐业',
    i.group_code = '862',
    i.group_name = '数字内容服务',
    i.gb_code = 'R-86-862';
WITH i
MATCH (s:IndustrySector {code: 'R'})
MERGE (i)-[:BELONGS_TO_SECTOR]->(s);

MATCH (i:Industry {name: '半导体/集成电路'})
SET i.sector_code = 'C',
    i.sector_name = '制造业',
    i.division_code = '39',
    i.division_name = '计算机、通信和其他电子设备制造业',
    i.group_code = '397',
    i.group_name = '电子器件制造',
    i.gb_code = 'C-39-397';
WITH i
MATCH (s:IndustrySector {code: 'C'})
MERGE (i)-[:BELONGS_TO_SECTOR]->(s);

MATCH (i:Industry {name: '新能源'})
SET i.sector_code = 'C',
    i.sector_name = '制造业',
    i.division_code = '38',
    i.division_name = '电气机械和器材制造业',
    i.group_code = '384',
    i.group_name = '电池制造',
    i.gb_code = 'C-38-384';
WITH i
MATCH (s:IndustrySector {code: 'C'})
MERGE (i)-[:BELONGS_TO_SECTOR]->(s);

MATCH (i:Industry {name: '云计算'})
SET i.sector_code = 'I',
    i.sector_name = '信息传输、软件和信息技术服务业',
    i.division_code = '64',
    i.division_name = '互联网和相关服务',
    i.group_code = '645',
    i.group_name = '互联网数据服务',
    i.gb_code = 'I-64-645';
WITH i
MATCH (s:IndustrySector {code: 'I'})
MERGE (i)-[:BELONGS_TO_SECTOR]->(s);

// --- G.4 Industry: link to IndustryDivision ---
MATCH (i:Industry {name: '互联网/IT'})
MATCH (d:IndustryDivision {code: '64'})
MERGE (i)-[:BELONGS_TO_DIVISION]->(d);

MATCH (i:Industry {name: '人工智能'})
MATCH (d:IndustryDivision {code: '65'})
MERGE (i)-[:BELONGS_TO_DIVISION]->(d)
WITH i
MATCH (d2:IndustryDivision {code: '73'})
MERGE (i)-[:BELONGS_TO_DIVISION]->(d2);

MATCH (i:Industry {name: '通信/电子'})
MATCH (d:IndustryDivision {code: '39'})
MERGE (i)-[:BELONGS_TO_DIVISION]->(d);

MATCH (i:Industry {name: '金融'})
MATCH (d:IndustryDivision {code: '66'})
MERGE (i)-[:BELONGS_TO_DIVISION]->(d);

MATCH (i:Industry {name: '金融科技'})
MATCH (d:IndustryDivision {code: '69'})
MERGE (i)-[:BELONGS_TO_DIVISION]->(d);

MATCH (i:Industry {name: '教育/培训'})
MATCH (d:IndustryDivision {code: '83'})
MERGE (i)-[:BELONGS_TO_DIVISION]->(d);

MATCH (i:Industry {name: '医疗健康'})
MATCH (d:IndustryDivision {code: '84'})
MERGE (i)-[:BELONGS_TO_DIVISION]->(d);

MATCH (i:Industry {name: '智能制造'})
MATCH (d:IndustryDivision {code: '35'})
MERGE (i)-[:BELONGS_TO_DIVISION]->(d);

MATCH (i:Industry {name: '汽车/出行'})
MATCH (d:IndustryDivision {code: '36'})
MERGE (i)-[:BELONGS_TO_DIVISION]->(d);

MATCH (i:Industry {name: '电商/零售'})
MATCH (d:IndustryDivision {code: '64'})
MERGE (i)-[:BELONGS_TO_DIVISION]->(d);

MATCH (i:Industry {name: '游戏/娱乐'})
MATCH (d:IndustryDivision {code: '86'})
MERGE (i)-[:BELONGS_TO_DIVISION]->(d);

MATCH (i:Industry {name: '半导体/集成电路'})
MATCH (d:IndustryDivision {code: '39'})
MERGE (i)-[:BELONGS_TO_DIVISION]->(d);

MATCH (i:Industry {name: '新能源'})
MATCH (d:IndustryDivision {code: '38'})
MERGE (i)-[:BELONGS_TO_DIVISION]->(d);

MATCH (i:Industry {name: '云计算'})
MATCH (d:IndustryDivision {code: '64'})
MERGE (i)-[:BELONGS_TO_DIVISION]->(d);

// --- G.5 Industry: link to IndustryGroup (when group_code is present) ---
// [C-4 FIXED] 互联网/IT now links to Group '642' instead of '645'
// [C-9 FIXED] 人工智能 now also links to Division '73' and Group '73' is a division-level only (no group)
MATCH (i:Industry {name: '互联网/IT'})
MATCH (g:IndustryGroup {code: '642'})
MERGE (i)-[:BELONGS_TO_GROUP]->(g);

MATCH (i:Industry {name: '人工智能'})
MATCH (g:IndustryGroup {code: '659'})
MERGE (i)-[:BELONGS_TO_GROUP]->(g);

MATCH (i:Industry {name: '通信/电子'})
MATCH (g:IndustryGroup {code: '392'})
MERGE (i)-[:BELONGS_TO_GROUP]->(g);

MATCH (i:Industry {name: '教育/培训'})
MATCH (g:IndustryGroup {code: '839'})
MERGE (i)-[:BELONGS_TO_GROUP]->(g);

MATCH (i:Industry {name: '医疗健康'})
MATCH (g:IndustryGroup {code: '841'})
MERGE (i)-[:BELONGS_TO_GROUP]->(g);

MATCH (i:Industry {name: '汽车/出行'})
MATCH (g:IndustryGroup {code: '361'})
MERGE (i)-[:BELONGS_TO_GROUP]->(g);

MATCH (i:Industry {name: '电商/零售'})
MATCH (g:IndustryGroup {code: '643'})
MERGE (i)-[:BELONGS_TO_GROUP]->(g);

MATCH (i:Industry {name: '游戏/娱乐'})
MATCH (g:IndustryGroup {code: '862'})
MERGE (i)-[:BELONGS_TO_GROUP]->(g);

MATCH (i:Industry {name: '半导体/集成电路'})
MATCH (g:IndustryGroup {code: '397'})
MERGE (i)-[:BELONGS_TO_GROUP]->(g);

MATCH (i:Industry {name: '新能源'})
MATCH (g:IndustryGroup {code: '384'})
MERGE (i)-[:BELONGS_TO_GROUP]->(g);

MATCH (i:Industry {name: '云计算'})
MATCH (g:IndustryGroup {code: '645'})
MERGE (i)-[:BELONGS_TO_GROUP]->(g);

// --- G.6 Unmatched Industry nodes: set sector_code to UNCLASSIFIED ---
MATCH (i:Industry)
WHERE i.sector_code IS NULL
SET i.sector_code = 'UNCLASSIFIED';

// --- G.6b Backfill: resolve industry name fields from taxonomy nodes ---
// Placed after G.6 so UNCLASSIFIED sector_codes are also resolved.
MATCH (i:Industry)
WHERE i.sector_code IS NOT NULL AND i.sector_name IS NULL
MATCH (s:IndustrySector {code: i.sector_code})
SET i.sector_name = s.name;

MATCH (i:Industry)
WHERE i.division_code IS NOT NULL AND i.division_name IS NULL
MATCH (d:IndustryDivision {code: i.division_code})
SET i.division_name = d.name;

MATCH (i:Industry)
WHERE i.group_code IS NOT NULL AND i.group_name IS NULL
MATCH (g:IndustryGroup {code: i.group_code})
SET i.group_name = g.name;

// --- G.7 Skill nodes: basic domain/group classification by old category name ---
// Programming language skills -> SKD-01
MATCH (s:Skill)
WHERE s.category IN ['编程语言', '脚本语言', '前端编程语言']
SET s.domain_code = 'SKD-01', s.domain_name = '编程语言与框架';

// Frontend skills -> SKD-01
MATCH (s:Skill)
WHERE s.category IN ['前端框架', '前端技术', '前端工具', '运行时']
SET s.domain_code = 'SKD-01', s.domain_name = '编程语言与框架';

// Backend framework skills -> SKD-01
MATCH (s:Skill)
WHERE s.category IN ['后端框架', '网络框架', 'C++库', '程序基础']
SET s.domain_code = 'SKD-01', s.domain_name = '编程语言与框架';

// Mobile development -> SKD-01
MATCH (s:Skill)
WHERE s.category IN ['移动开发框架', '移动开发工具', 'UI框架']
SET s.domain_code = 'SKD-01', s.domain_name = '编程语言与框架';

// Database skills -> SKD-02
MATCH (s:Skill)
WHERE s.category IN ['关系型数据库', 'NoSQL', '数据库', '消息队列', '大数据', '数据领域', '数据仓库']
SET s.domain_code = 'SKD-02', s.domain_name = '数据存储与管理';

// AI/ML skills -> SKD-03
MATCH (s:Skill)
WHERE s.category IN ['AI框架', 'AI模型', 'AI领域', 'AI工具', 'AI加速', 'AI推理', '视觉库']
SET s.domain_code = 'SKD-03', s.domain_name = '人工智能与机器学习';

// Cloud & Infra skills -> SKD-04
MATCH (s:Skill)
WHERE s.category IN ['云平台', '容器', '网络协议', '通信协议', '操作系统', 'Web服务器', 'API协议']
SET s.domain_code = 'SKD-04', s.domain_name = '云计算与基础设施';

// DevOps skills -> SKD-05
MATCH (s:Skill)
WHERE s.category IN ['CI/CD', '构建工具', '版本控制', 'IDE工具', '监控工具', '配置管理', 'IaC']
SET s.domain_code = 'SKD-05', s.domain_name = 'DevOps与工程效能';

// Testing & Security skills -> SKD-06
MATCH (s:Skill)
WHERE s.category IN ['测试领域', '测试工具', '安全领域', '安全工具', '安全标准', '安全运营', '安全测试', '代码质量', '架构质量']
SET s.domain_code = 'SKD-06', s.domain_name = '测试、安全与质量';

// Business & Product skills -> SKD-07
MATCH (s:Skill)
WHERE s.category IN ['产品工具', '产品文档', '产品能力', '产品设计', '管理能力', '管理方法', '项目管理工具', '数据分析', '数据可视化', 'BI工具', '办公工具', '设计工具', '金融科技', '区块链', '智能合约', '架构设计', '系统设计', '设计模式']
SET s.domain_code = 'SKD-07', s.domain_name = '业务、产品与软技能';

// --- G.8 Skill: link Skill nodes to SkillGroup/SkillType where applicable ---
// [C-2 FIXED] Added type_code and type_name to enable BELONGS_TO_TYPE in G.9
// Specific skill-to-group mappings (by skill name)

// Java ecosystem -> GRP-0101
MATCH (s:Skill)
WHERE s.name IN ['Java', 'Python', 'Go', 'C++', 'Rust']
SET s.group_code = 'GRP-0101', s.group_name = '后端编程语言',
    s.type_code = 'T-01011', s.type_name = '主要后端语言';

MATCH (s:Skill)
WHERE s.name IN ['PHP', 'Ruby', 'Scala', 'Shell']
SET s.group_code = 'GRP-0101', s.group_name = '后端编程语言',
    s.type_code = 'T-01012', s.type_name = '脚本与其他语言';

// Frontend languages/tech -> GRP-0102
MATCH (s:Skill)
WHERE s.name IN ['JavaScript', 'TypeScript']
SET s.group_code = 'GRP-0102', s.group_name = '前端技术',
    s.type_code = 'T-01021', s.type_name = '前端编程语言';

MATCH (s:Skill)
WHERE s.name IN ['React', 'Vue', 'Angular']
SET s.group_code = 'GRP-0102', s.group_name = '前端技术',
    s.type_code = 'T-01022', s.type_name = '前端框架';

MATCH (s:Skill)
WHERE s.name IN ['HTML5', 'CSS3']
SET s.group_code = 'GRP-0102', s.group_name = '前端技术',
    s.type_code = 'T-01023', s.type_name = '前端基础技术';

MATCH (s:Skill)
WHERE s.name IN ['Webpack', 'Vite', 'Node.js', '小程序']
SET s.group_code = 'GRP-0102', s.group_name = '前端技术',
    s.type_code = 'T-01024', s.type_name = '前端工具与运行时';

// Backend frameworks -> GRP-0103
MATCH (s:Skill)
WHERE s.name IN ['Spring', 'Spring Boot', 'Spring Cloud', 'MyBatis', 'Hibernate']
SET s.group_code = 'GRP-0103', s.group_name = '后端框架',
    s.type_code = 'T-01031', s.type_name = 'Java生态框架';

MATCH (s:Skill)
WHERE s.name IN ['Django', 'Flask', 'FastAPI']
SET s.group_code = 'GRP-0103', s.group_name = '后端框架',
    s.type_code = 'T-01032', s.type_name = 'Python生态框架';

MATCH (s:Skill)
WHERE s.name IN ['Express', 'Laravel', 'Netty']
SET s.group_code = 'GRP-0103', s.group_name = '后端框架',
    s.type_code = 'T-01033', s.type_name = '其他后端框架';

// Mobile dev -> GRP-0104
MATCH (s:Skill)
WHERE s.name IN ['Android SDK', 'Jetpack', 'UIKit', 'SwiftUI', 'Flutter', 'React Native']
SET s.group_code = 'GRP-0104', s.group_name = '移动开发技术',
    s.type_code = 'T-01041', s.type_name = '移动开发框架';

MATCH (s:Skill)
WHERE s.name IN ['Retrofit', 'Core Data', 'Combine', 'Room']
SET s.group_code = 'GRP-0104', s.group_name = '移动开发技术',
    s.type_code = 'T-01042', s.type_name = '移动开发工具';

// Game & graphics -> GRP-0105
MATCH (s:Skill)
WHERE s.name IN ['Unity', 'Unreal Engine']
SET s.group_code = 'GRP-0105', s.group_name = '游戏与图形开发',
    s.type_code = 'T-01051', s.type_name = '游戏引擎';

MATCH (s:Skill)
WHERE s.name IN ['OpenGL', 'WebGL', 'FFmpeg', 'WebRTC']
SET s.group_code = 'GRP-0105', s.group_name = '游戏与图形开发',
    s.type_code = 'T-01052', s.type_name = '图形与多媒体';

// SQL databases -> GRP-0201
MATCH (s:Skill)
WHERE s.name IN ['MySQL', 'PostgreSQL', 'Oracle', 'SQLite']
SET s.group_code = 'GRP-0201', s.group_name = '关系型数据库',
    s.type_code = 'T-02011', s.type_name = 'SQL数据库';

// NoSQL -> GRP-0202
MATCH (s:Skill)
WHERE s.name IN ['MongoDB', 'Redis']
SET s.group_code = 'GRP-0202', s.group_name = '非关系型数据库',
    s.type_code = 'T-02021', s.type_name = '文档/键值数据库';

MATCH (s:Skill)
WHERE s.name IN ['Elasticsearch', 'HBase', 'ClickHouse']
SET s.group_code = 'GRP-0202', s.group_name = '非关系型数据库',
    s.type_code = 'T-02022', s.type_name = '列存/搜索数据库';

MATCH (s:Skill)
WHERE s.name CONTAINS '向量数据库'
SET s.group_code = 'GRP-0202', s.group_name = '非关系型数据库',
    s.type_code = 'T-02023', s.type_name = '向量数据库';

// Big data -> GRP-0203
MATCH (s:Skill)
WHERE s.name IN ['Spark', 'Flink', 'Hadoop', 'Hive']
SET s.group_code = 'GRP-0203', s.group_name = '大数据与流处理',
    s.type_code = 'T-02031', s.type_name = '大数据计算框架';

MATCH (s:Skill)
WHERE s.name IN ['数据仓库', 'Doris']
SET s.group_code = 'GRP-0203', s.group_name = '大数据与流处理',
    s.type_code = 'T-02032', s.type_name = '数据仓库';

// Message queues -> GRP-0204
MATCH (s:Skill)
WHERE s.name IN ['Kafka', 'RabbitMQ', 'RocketMQ']
SET s.group_code = 'GRP-0204', s.group_name = '消息队列与事件流',
    s.type_code = 'T-02041', s.type_name = '消息队列';

// AI frameworks -> GRP-0301
MATCH (s:Skill)
WHERE s.name IN ['TensorFlow', 'PyTorch', 'Keras']
SET s.group_code = 'GRP-0301', s.group_name = 'AI/ML框架',
    s.type_code = 'T-03011', s.type_name = '深度学习框架';

MATCH (s:Skill)
WHERE s.name IN ['Scikit-learn', 'XGBoost', 'LightGBM']
SET s.group_code = 'GRP-0301', s.group_name = 'AI/ML框架',
    s.type_code = 'T-03012', s.type_name = '机器学习框架';

// AI models -> GRP-0302
MATCH (s:Skill)
WHERE s.name IN ['Transformer', 'BERT', 'GPT'] OR s.name = 'LLM'
SET s.group_code = 'GRP-0302', s.group_name = 'AI/ML模型',
    s.type_code = 'T-03021', s.type_name = '语言模型';

MATCH (s:Skill)
WHERE s.name IN ['CNN', 'RNN', 'YOLO', 'Stable Diffusion']
SET s.group_code = 'GRP-0302', s.group_name = 'AI/ML模型',
    s.type_code = 'T-03022', s.type_name = '视觉模型';

// AI application domains -> GRP-0303
MATCH (s:Skill)
WHERE s.name IN ['机器学习', '深度学习', 'NLP', '计算机视觉', '数据挖掘', '推荐系统', '强化学习', '语音识别', '语音合成', '多模态']
SET s.group_code = 'GRP-0303', s.group_name = 'AI/ML应用领域',
    s.type_code = 'T-03031', s.type_name = 'AI/ML应用领域';

// AI engineering -> GRP-0304
MATCH (s:Skill)
WHERE s.name IN ['模型部署', '模型优化', 'CUDA', 'TensorRT', 'ONNX']
SET s.group_code = 'GRP-0304', s.group_name = 'AI/ML工程化',
    s.type_code = 'T-03041', s.type_name = '模型部署与优化';

MATCH (s:Skill)
WHERE s.name IN ['MLflow', 'Kubeflow', 'HuggingFace']
SET s.group_code = 'GRP-0304', s.group_name = 'AI/ML工程化',
    s.type_code = 'T-03042', s.type_name = 'MLOps工具';

MATCH (s:Skill)
WHERE s.name IN ['LangChain', 'RAG']
SET s.group_code = 'GRP-0304', s.group_name = 'AI/ML工程化',
    s.type_code = 'T-03043', s.type_name = 'LLM应用框架';

// AI tools -> GRP-0305
MATCH (s:Skill)
WHERE s.name IN ['OpenCV', 'jieba', 'spaCy', 'Kaldi', 'Matplotlib']
SET s.group_code = 'GRP-0305', s.group_name = 'AI工具与库',
    s.type_code = 'T-03051', s.type_name = 'AI工具与库';

// Cloud platforms -> GRP-0401
MATCH (s:Skill)
WHERE s.name IN ['AWS', 'Azure', 'Google Cloud']
SET s.group_code = 'GRP-0401', s.group_name = '云平台',
    s.type_code = 'T-04011', s.type_name = '云平台';

// Containers -> GRP-0402
MATCH (s:Skill)
WHERE s.name IN ['Docker', 'Kubernetes']
SET s.group_code = 'GRP-0402', s.group_name = '容器与编排',
    s.type_code = 'T-04021', s.type_name = '容器与编排';

// Networking -> GRP-0403
MATCH (s:Skill)
WHERE s.name IN ['TCP/IP', '通信协议']
SET s.group_code = 'GRP-0403', s.group_name = '网络与通信',
    s.type_code = 'T-04031', s.type_name = '网络协议';

MATCH (s:Skill)
WHERE s.name IN ['gRPC', 'GraphQL', 'WebSocket']
SET s.group_code = 'GRP-0403', s.group_name = '网络与通信',
    s.type_code = 'T-04032', s.type_name = 'API协议';

MATCH (s:Skill)
WHERE s.name IN ['Istio', 'Envoy', 'Consul']
SET s.group_code = 'GRP-0403', s.group_name = '网络与通信',
    s.type_code = 'T-04033', s.type_name = '服务网格';

// System & infra -> GRP-0404
MATCH (s:Skill)
WHERE s.name = 'Linux'
SET s.group_code = 'GRP-0404', s.group_name = '系统与基础设施',
    s.type_code = 'T-04041', s.type_name = '操作系统';

MATCH (s:Skill)
WHERE s.name IN ['Nginx', 'Gunicorn']
SET s.group_code = 'GRP-0404', s.group_name = '系统与基础设施',
    s.type_code = 'T-04042', s.type_name = 'Web服务器';

MATCH (s:Skill)
WHERE s.name IN ['ZooKeeper', 'Nacos', 'Harbor', 'Helix']
SET s.group_code = 'GRP-0404', s.group_name = '系统与基础设施',
    s.type_code = 'T-04043', s.type_name = '存储与注册中心';

// CI/CD -> GRP-0501
MATCH (s:Skill)
WHERE s.name IN ['Jenkins', 'CI/CD']
SET s.group_code = 'GRP-0501', s.group_name = 'CI/CD与构建',
    s.type_code = 'T-05011', s.type_name = 'CI/CD工具';

MATCH (s:Skill)
WHERE s.name IN ['Maven', 'Gradle', 'CMake']
SET s.group_code = 'GRP-0501', s.group_name = 'CI/CD与构建',
    s.type_code = 'T-05012', s.type_name = '构建工具';

MATCH (s:Skill)
WHERE s.name = 'SonarQube'
SET s.group_code = 'GRP-0501', s.group_name = 'CI/CD与构建',
    s.type_code = 'T-05013', s.type_name = '代码质量';

// Observability -> GRP-0502
MATCH (s:Skill)
WHERE s.name IN ['Prometheus', 'Grafana']
SET s.group_code = 'GRP-0502', s.group_name = '可观测性与监控',
    s.type_code = 'T-05021', s.type_name = '监控工具';

MATCH (s:Skill)
WHERE s.name IN ['ELK', 'Jaeger']
SET s.group_code = 'GRP-0502', s.group_name = '可观测性与监控',
    s.type_code = 'T-05022', s.type_name = '日志与追踪';

MATCH (s:Skill)
WHERE s.name = '前端监控'
SET s.group_code = 'GRP-0502', s.group_name = '可观测性与监控',
    s.type_code = 'T-05023', s.type_name = '前端监控';

// IaC -> GRP-0503
MATCH (s:Skill)
WHERE s.name = 'Terraform'
SET s.group_code = 'GRP-0503', s.group_name = '配置与基础设施即代码',
    s.type_code = 'T-05031', s.type_name = 'IaC工具';

MATCH (s:Skill)
WHERE s.name = 'Ansible'
SET s.group_code = 'GRP-0503', s.group_name = '配置与基础设施即代码',
    s.type_code = 'T-05032', s.type_name = '配置管理';

MATCH (s:Skill)
WHERE s.name = 'Helm'
SET s.group_code = 'GRP-0503', s.group_name = '配置与基础设施即代码',
    s.type_code = 'T-05033', s.type_name = '容器编排辅助';

// Testing -> GRP-0601
MATCH (s:Skill)
WHERE s.name IN ['自动化测试', '性能测试', '单元测试']
SET s.group_code = 'GRP-0601', s.group_name = '软件测试',
    s.type_code = 'T-06011', s.type_name = '测试领域';

MATCH (s:Skill)
WHERE s.name IN ['Selenium', 'JMeter', 'Postman', 'Appium', 'Pytest']
SET s.group_code = 'GRP-0601', s.group_name = '软件测试',
    s.type_code = 'T-06012', s.type_name = '测试工具';

MATCH (s:Skill)
WHERE s.name = '安全测试'
SET s.group_code = 'GRP-0601', s.group_name = '软件测试',
    s.type_code = 'T-06013', s.type_name = '安全测试';

// Security -> GRP-0602
MATCH (s:Skill)
WHERE s.name IN ['网络安全', '渗透测试', '密码学']
SET s.group_code = 'GRP-0602', s.group_name = '信息安全',
    s.type_code = 'T-06021', s.type_name = '安全领域';

MATCH (s:Skill)
WHERE s.name IN ['WAF', '漏洞扫描']
SET s.group_code = 'GRP-0602', s.group_name = '信息安全',
    s.type_code = 'T-06022', s.type_name = '安全工具';

MATCH (s:Skill)
WHERE s.name = 'SOC'
SET s.group_code = 'GRP-0602', s.group_name = '信息安全',
    s.type_code = 'T-06023', s.type_name = '安全运营';

MATCH (s:Skill)
WHERE s.name = 'ISO27001'
SET s.group_code = 'GRP-0602', s.group_name = '信息安全',
    s.type_code = 'T-06024', s.type_name = '安全标准';

// Code quality -> GRP-0603
MATCH (s:Skill)
WHERE s.name IN ['领域驱动设计', '设计模式', '代码重构']
SET s.group_code = 'GRP-0603', s.group_name = '代码与架构质量',
    s.type_code = 'T-06031', s.type_name = '架构质量';

// Product & design tools -> GRP-0701
MATCH (s:Skill)
WHERE s.name IN ['Axure', 'Figma', 'Sketch', 'XMind']
SET s.group_code = 'GRP-0701', s.group_name = '产品与设计工具',
    s.type_code = 'T-07011', s.type_name = '产品与设计工具';

// Data analysis & BI -> GRP-0702
MATCH (s:Skill)
WHERE s.name IN ['Pandas', 'NumPy', 'SciPy']
SET s.group_code = 'GRP-0702', s.group_name = '数据分析与商业智能',
    s.type_code = 'T-07021', s.type_name = '数据分析库';

MATCH (s:Skill)
WHERE s.name IN ['Tableau', 'ECharts', 'D3.js']
SET s.group_code = 'GRP-0702', s.group_name = '数据分析与商业智能',
    s.type_code = 'T-07022', s.type_name = '数据可视化';

MATCH (s:Skill)
WHERE s.name = '数据分析'
SET s.group_code = 'GRP-0702', s.group_name = '数据分析与商业智能',
    s.type_code = 'T-07023', s.type_name = 'BI工具';

MATCH (s:Skill)
WHERE s.name = 'Excel'
SET s.group_code = 'GRP-0702', s.group_name = '数据分析与商业智能',
    s.type_code = 'T-07024', s.type_name = '办公工具';

// Management -> GRP-0703
MATCH (s:Skill)
WHERE s.name IN ['项目管理', '风险管理', '沟通协调', 'PMO', '技术管理']
SET s.group_code = 'GRP-0703', s.group_name = '管理与方法论',
    s.type_code = 'T-07031', s.type_name = '管理能力';

MATCH (s:Skill)
WHERE s.name IN ['敏捷开发', 'Scrum']
SET s.group_code = 'GRP-0703', s.group_name = '管理与方法论',
    s.type_code = 'T-07032', s.type_name = '方法论';

MATCH (s:Skill)
WHERE s.name = 'JIRA'
SET s.group_code = 'GRP-0703', s.group_name = '管理与方法论',
    s.type_code = 'T-07033', s.type_name = '项目管理工具';

// Product capabilities -> GRP-0704
MATCH (s:Skill)
WHERE s.name IN ['PRD', '用户研究', '竞品分析', '需求分析', '原型设计', '用户体验', 'AB实验']
SET s.group_code = 'GRP-0704', s.group_name = '产品能力',
    s.type_code = 'T-07041', s.type_name = '产品能力';

// Architecture & system design -> GRP-0705
MATCH (s:Skill)
WHERE s.name IN ['微服务', 'MVVM']
SET s.group_code = 'GRP-0705', s.group_name = '架构与系统设计',
    s.type_code = 'T-07051', s.type_name = '架构模式';

MATCH (s:Skill)
WHERE s.name IN ['分布式', '高并发', '系统设计']
SET s.group_code = 'GRP-0705', s.group_name = '架构与系统设计',
    s.type_code = 'T-07052', s.type_name = '非功能需求';

MATCH (s:Skill)
WHERE s.name = '金融科技'
SET s.group_code = 'GRP-0705', s.group_name = '架构与系统设计',
    s.type_code = 'T-07053', s.type_name = '领域知识';

// --- G.9 Skill: link Skill nodes to SkillDomain/Group/Type taxonomy nodes ---
// Link to SkillDomain
MATCH (s:Skill)
WHERE s.domain_code IS NOT NULL
MATCH (d:SkillDomain {code: s.domain_code})
MERGE (s)-[:BELONGS_TO_DOMAIN]->(d);

// Link to SkillGroup
MATCH (s:Skill)
WHERE s.group_code IS NOT NULL
MATCH (g:SkillGroup {code: s.group_code})
MERGE (s)-[:BELONGS_TO_GROUP]->(g);

// [C-2 FIXED] Link to SkillType (third layer of 4-level skill taxonomy)
MATCH (s:Skill)
WHERE s.type_code IS NOT NULL
MATCH (st:SkillType {code: s.type_code})
MERGE (s)-[:BELONGS_TO_TYPE]->(st);

// --- G.9b Backfill: resolve skill name fields from taxonomy nodes ---
MATCH (s:Skill)
WHERE s.domain_code IS NOT NULL AND s.domain_name IS NULL
MATCH (d:SkillDomain {code: s.domain_code})
SET s.domain_name = d.name;

MATCH (s:Skill)
WHERE s.group_code IS NOT NULL AND s.group_name IS NULL
MATCH (g:SkillGroup {code: s.group_code})
SET s.group_name = g.name;

MATCH (s:Skill)
WHERE s.type_code IS NOT NULL AND s.type_name IS NULL
MATCH (st:SkillType {code: s.type_code})
SET s.type_name = st.name;

// --- G.10 Unmatched Skill nodes: set domain_code to SKD-99 ---
MATCH (s:Skill)
WHERE s.domain_code IS NULL
SET s.domain_code = 'SKD-99',
    s.domain_name = '其他',
    s.group_code = 'GRP-9901',
    s.group_name = '未分类',
    s.type_code = 'T-99011',
    s.type_name = '未分类';

// =============================================================================
// SECTION H: CROSS-TAXONOMY RELATIONSHIPS
// =============================================================================

// --- H.1 EmergingJob -> JobCategory ---
MATCH (e:EmergingJob)
WHERE e.category_code IS NULL
MATCH (c:JobCategory {code: 'CAT-0604'})
MERGE (e)-[:BELONGS_TO_CATEGORY]->(c)
SET e.domain_code = 'DOM-06',
    e.category_code = 'CAT-0604';

// --- H.2 Job -> JobTitle -> JobCategory chain (if Job nodes exist) ---
// Ensures Job nodes inherit taxonomy via their linked JobTitle
MATCH (j:Job)-[:HAS_TITLE]->(t:JobTitle)
WHERE t.category_code IS NOT NULL
MATCH (c:JobCategory {code: t.category_code})
MERGE (j)-[:BELONGS_TO_CATEGORY]->(c);

// --- H.3 JobDomain <- JobCategory summary aggregation ---
// Create a summary property on JobDomain counting direct JobTitles
MATCH (d:JobDomain)<-[:BELONGS_TO_DOMAIN]-(c:JobCategory)<-[:BELONGS_TO_CATEGORY]-(t:JobTitle)
WITH d, count(DISTINCT t) AS title_count
SET d.job_title_count = title_count;

// --- H.4 SkillDomain summary aggregation ---
MATCH (d:SkillDomain)<-[:BELONGS_TO_DOMAIN]-(s:Skill)
WITH d, count(DISTINCT s) AS skill_count
SET d.skill_count = skill_count;

// --- H.5 JobTitle -> Competency: REQUIRES_COMPETENCY mappings ---
// [C-3 FIXED] Maps JobTitle categories to their most relevant competencies
// based on the design doc §7.2.3: (:JobTitle)-[:REQUIRES_COMPETENCY {level: 1-5}]->(:Competency)

// CAT-0101 后端开发: 需要 代码编写、算法、系统设计、数据建模
MATCH (t:JobTitle {category_code: 'CAT-0101'})
MATCH (c:Competency) WHERE c.code IN ['CMP-010101', 'CMP-010102', 'CMP-010103', 'CMP-010201']
MERGE (t)-[:REQUIRES_COMPETENCY {level: 3}]->(c);

// CAT-0102 前端与全栈开发: 需要 代码编写、系统设计
MATCH (t:JobTitle {category_code: 'CAT-0102'})
MATCH (c:Competency) WHERE c.code IN ['CMP-010101', 'CMP-010103']
MERGE (t)-[:REQUIRES_COMPETENCY {level: 3}]->(c);

// CAT-0103 移动开发: 需要 代码编写、系统设计
MATCH (t:JobTitle {category_code: 'CAT-0103'})
MATCH (c:Competency) WHERE c.code IN ['CMP-010101', 'CMP-010103']
MERGE (t)-[:REQUIRES_COMPETENCY {level: 3}]->(c);

// CAT-0104 架构设计: 需要 系统设计、技术方案设计、技术战略
MATCH (t:JobTitle {category_code: 'CAT-0104'})
MATCH (c:Competency) WHERE c.code IN ['CMP-010103', 'CMP-010104', 'CMP-030301']
MERGE (t)-[:REQUIRES_COMPETENCY {level: 4}]->(c);

// CAT-0105 嵌入式与物联网: 需要 代码编写、算法
MATCH (t:JobTitle {category_code: 'CAT-0105'})
MATCH (c:Competency) WHERE c.code IN ['CMP-010101', 'CMP-010102']
MERGE (t)-[:REQUIRES_COMPETENCY {level: 3}]->(c);

// CAT-0201 算法研究与AI模型: 需要 机器学习建模、数据建模、算法
MATCH (t:JobTitle {category_code: 'CAT-0201'})
MATCH (c:Competency) WHERE c.code IN ['CMP-010202', 'CMP-010201', 'CMP-010102']
MERGE (t)-[:REQUIRES_COMPETENCY {level: 4}]->(c);

// CAT-0202 AI工程化与应用: 需要 机器学习建模、数据工程、云基础设施
MATCH (t:JobTitle {category_code: 'CAT-0202'})
MATCH (c:Competency) WHERE c.code IN ['CMP-010202', 'CMP-010203', 'CMP-010301']
MERGE (t)-[:REQUIRES_COMPETENCY {level: 3}]->(c);

// CAT-0203 大数据工程: 需要 数据工程、系统设计
MATCH (t:JobTitle {category_code: 'CAT-0203'})
MATCH (c:Competency) WHERE c.code IN ['CMP-010203', 'CMP-010103']
MERGE (t)-[:REQUIRES_COMPETENCY {level: 3}]->(c);

// CAT-0204 数据分析与商业智能: 需要 数据建模、数据可视化
MATCH (t:JobTitle {category_code: 'CAT-0204'})
MATCH (c:Competency) WHERE c.code IN ['CMP-010201', 'CMP-010204']
MERGE (t)-[:REQUIRES_COMPETENCY {level: 3}]->(c);

// CAT-0301 运维与站点可靠性: 需要 云基础设施、自动化运维、故障诊断
MATCH (t:JobTitle {category_code: 'CAT-0301'})
MATCH (c:Competency) WHERE c.code IN ['CMP-010301', 'CMP-010302', 'CMP-010303']
MERGE (t)-[:REQUIRES_COMPETENCY {level: 3}]->(c);

// CAT-0302 云计算与平台工程: 需要 云基础设施、自动化运维、性能优化
MATCH (t:JobTitle {category_code: 'CAT-0302'})
MATCH (c:Competency) WHERE c.code IN ['CMP-010301', 'CMP-010302', 'CMP-010304']
MERGE (t)-[:REQUIRES_COMPETENCY {level: 3}]->(c);

// CAT-0401 产品管理: 需要 需求分析、用户研究、产品路线图、竞品分析
MATCH (t:JobTitle {category_code: 'CAT-0401'})
MATCH (c:Competency) WHERE c.code IN ['CMP-020101', 'CMP-020102', 'CMP-020103', 'CMP-020104']
MERGE (t)-[:REQUIRES_COMPETENCY {level: 3}]->(c);

// CAT-0402 项目管理: 需要 项目计划、敏捷管理、风险管理、资源协调
MATCH (t:JobTitle {category_code: 'CAT-0402'})
MATCH (c:Competency) WHERE c.code IN ['CMP-030101', 'CMP-030102', 'CMP-030103', 'CMP-030104']
MERGE (t)-[:REQUIRES_COMPETENCY {level: 3}]->(c);

// CAT-0403 技术管理: 需要 技术团队领导、技术战略、跨部门协作
MATCH (t:JobTitle {category_code: 'CAT-0403'})
MATCH (c:Competency) WHERE c.code IN ['CMP-030201', 'CMP-030301', 'CMP-030204']
MERGE (t)-[:REQUIRES_COMPETENCY {level: 4}]->(c);

// CAT-0501 测试与质量保证: 需要 测试策略、代码审查
MATCH (t:JobTitle {category_code: 'CAT-0501'})
MATCH (c:Competency) WHERE c.code IN ['CMP-010403', 'CMP-010404']
MERGE (t)-[:REQUIRES_COMPETENCY {level: 3}]->(c);

// CAT-0502 信息安全: 需要 安全风险评估、渗透测试
MATCH (t:JobTitle {category_code: 'CAT-0502'})
MATCH (c:Competency) WHERE c.code IN ['CMP-010401', 'CMP-010402']
MERGE (t)-[:REQUIRES_COMPETENCY {level: 3}]->(c);

// CAT-0603 金融科技: 需要 量化策略、风控建模
MATCH (t:JobTitle {category_code: 'CAT-0603'})
MATCH (c:Competency) WHERE c.code IN ['CMP-050101', 'CMP-050102']
MERGE (t)-[:REQUIRES_COMPETENCY {level: 4}]->(c);

// --- H.6 Cross-cutting soft skills for all technical roles ---
// All DOM-01 and DOM-02 roles implicitly need: 问题解决、快速学习、团队协作
MATCH (t:JobTitle)
WHERE t.domain_code IN ['DOM-01', 'DOM-02']
MATCH (c:Competency) WHERE c.code IN ['CMP-040203', 'CMP-040202', 'CMP-040103']
MERGE (t)-[:REQUIRES_COMPETENCY {level: 2}]->(c);

// =============================================================================
// END OF MIGRATION SCRIPT
// =============================================================================
//
// VERIFICATION QUERIES (run after migration to validate):
//
// -- Count taxonomy nodes created --
// MATCH (n:JobDomain)    RETURN 'JobDomain',    count(n) UNION ALL
// MATCH (n:JobCategory)  RETURN 'JobCategory',  count(n) UNION ALL
// MATCH (n:SkillDomain)  RETURN 'SkillDomain',  count(n) UNION ALL
// MATCH (n:SkillGroup)   RETURN 'SkillGroup',   count(n) UNION ALL
// MATCH (n:SkillType)    RETURN 'SkillType',    count(n) UNION ALL
// MATCH (n:IndustrySector)    RETURN 'IndustrySector',    count(n) UNION ALL
// MATCH (n:IndustryDivision)  RETURN 'IndustryDivision',  count(n) UNION ALL
// MATCH (n:IndustryGroup)     RETURN 'IndustryGroup',     count(n) UNION ALL
// MATCH (n:AbilityDimension)    RETURN 'AbilityDimension',    count(n) UNION ALL
// MATCH (n:CompetencyCluster)   RETURN 'CompetencyCluster',   count(n) UNION ALL
// MATCH (n:Competency)          RETURN 'Competency',          count(n);
//
// -- Check JobTitle classification coverage --
// MATCH (t:JobTitle) RETURN t.category_code AS category, count(t) AS cnt ORDER BY cnt DESC;
//
// -- Check Skill domain coverage --
// MATCH (s:Skill) RETURN s.domain_code AS domain, count(s) AS cnt ORDER BY cnt DESC;
//
// -- Check relationship integrity --
// MATCH ()-[r:BELONGS_TO_DOMAIN]->() RETURN type(r), count(r)
// UNION ALL
// MATCH ()-[r:BELONGS_TO_CATEGORY]->() RETURN type(r), count(r)
// UNION ALL
// MATCH ()-[r:BELONGS_TO_GROUP]->() RETURN type(r), count(r)
// UNION ALL
// MATCH ()-[r:BELONGS_TO_TYPE]->() RETURN type(r), count(r)
// UNION ALL
// MATCH ()-[r:BELONGS_TO_SECTOR]->() RETURN type(r), count(r)
// UNION ALL
// MATCH ()-[r:BELONGS_TO_DIVISION]->() RETURN type(r), count(r)
// UNION ALL
// MATCH ()-[r:BELONGS_TO_DIMENSION]->() RETURN type(r), count(r)
// UNION ALL
// MATCH ()-[r:BELONGS_TO_CLUSTER]->() RETURN type(r), count(r)
// UNION ALL
// MATCH ()-[r:REQUIRES_COMPETENCY]->() RETURN type(r), count(r);
