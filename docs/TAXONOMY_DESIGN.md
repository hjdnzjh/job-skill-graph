# 岗位能力分类体系设计文档

> 版本：v1.0  
> 日期：2026-07-15  
> 基于：国家职业分类大典 (GB/T 6565)、ESCO (v1.2)、O*NET (2024)、GB/T 4754 国民经济行业分类

---

## 目录

1. [概述与设计原则](#1-概述与设计原则)
2. [岗位三层分类体系](#2-岗位三层分类体系)
3. [技能四层分类体系](#3-技能四层分类体系)
4. [行业分类体系](#4-行业分类体系)
5. [能力/胜任力分类体系](#5-能力胜任力分类体系)
6. [教育/经验有序化](#6-教育经验有序化)
7. [分类与知识图谱的映射方案](#7-分类与知识图谱的映射方案)
8. [API与前端集成路径](#8-api与前端集成路径)
9. [数据迁移与实施计划](#9-数据迁移与实施计划)
10. [附录](#10-附录)

---

## 1. 概述与设计原则

### 1.1 背景

当前系统存在以下分类体系缺陷：

| 缺陷等级 | 问题 | 影响 |
|---------|------|------|
| 严重 | 383个JobTitle无分类标签，无法按职业大类聚合 | 聚合分析、趋势洞察受阻 |
| 严重 | 技能59个分类完全扁平、无层级 | 无法做下钻分析和语义推理 |
| 高 | 18个单技能分类碎片化 | 分类冗余，维护成本高 |
| 高 | 71个Industry无层级、无标准编码 | 行业维度不可做层级分析 |
| 高 | 无能力/胜任力分类 | 无法从岗位需求映射到能力模型 |
| 中 | 分类命名不一致 | "通信协议"同时用于两个不同含义的组 |
| 中 | 教育/经验无有序维度 | 无法做趋势分析 |

### 1.2 设计原则

1. **标准对齐**：优先引用国家标准（GB/T 6565、GB/T 4754）和国际标准（ESCO、O*NET），保证互操作性。
2. **层级渐进**：每个分类体系至少三个层级，支持从宏观到微观的下钻分析。
3. **覆盖完备**：分类体系必须覆盖当前数据中所有已知实体（383个岗位、128个技能、71个行业）。
4. **编码规范**：每个分类节点分配稳定编码，支持版本化管理。
5. **关系显式化**：分类之间的关系通过知识图谱的关系边显式表达，而非隐式字符串匹配。
6. **可演化**：分类体系设计预留"other"/"emerging"类别，支持新实体自动归类。

### 1.3 分类体系总览

```
┌────────────────────────────────────────────────────────────┐
│                    岗位能力分类体系                           │
├───────────────┬──────────────┬───────────────┬──────────────┤
│  岗位分类      │  技能分类     │  行业分类      │  能力分类     │
│  (GB/T 6565)  │  (ESCO)      │  (GB/T 4754)  │  (O*NET)     │
├───────────────┼──────────────┼───────────────┼──────────────┤
│ 领域→类别→岗位 │ 技能域→技能组  │ 门类→大类→中类 │ 能力维度→能力群 │
│  (3层)        │  →技能类型    │  (3层)        │  →具体能力     │
│               │  →具体技能    │               │  (3层)        │
│               │  (4层)       │               │              │
└───────────────┴──────────────┴───────────────┴──────────────┘
```

---

## 2. 岗位三层分类体系

### 2.1 体系结构

参考 **国家职业分类大典 (GB/T 6565-2015)** 和 **ESCO Occupations pillar**, 将岗位分为三层：

```
第1层：职能域 (Domain)          — 6个大类，对应GB/T 6565的大类/中类
第2层：岗位类别 (Category)       — 22个中类，对应岗位族
第3层：具体岗位 (Title)          — 383个已收集 + 预期扩展至~80个规范岗位名
                                  对应ESCO occupation / GB/T 6565小类
```

### 2.2 分类树形图

```
岗位分类体系
│
├── DOM-01  软件与算法开发 (Software & Algorithm Engineering)
│   ├── CAT-0101  后端开发 (Backend Development)
│   │   ├── Java开发工程师              [GB/T 6565: 2-02-10-01]
│   │   ├── Go开发工程师                [ESCO: 2512.1]
│   │   ├── Python开发工程师
│   │   ├── C++开发工程师
│   │   ├── PHP开发工程师
│   │   └── 后端开发工程师 (通用)
│   │
│   ├── CAT-0102  前端与全栈开发 (Frontend & Full-Stack)
│   │   ├── 前端开发工程师
│   │   ├── 全栈开发工程师
│   │   └── Web前端工程师 (变体)
│   │
│   ├── CAT-0103  移动开发 (Mobile Development)
│   │   ├── Android开发工程师
│   │   ├── iOS开发工程师
│   │   ├── 移动端开发工程师 (通用)
│   │   └── Flutter/RN开发工程师 (新兴)
│   │
│   ├── CAT-0104  架构设计 (Architecture)
│   │   ├── 架构师
│   │   ├── 系统架构师
│   │   ├── 解决方案架构师
│   │   └── 技术总监/CTO (管理交叉)
│   │
│   ├── CAT-0105  嵌入式与物联网开发 (Embedded & IoT)
│   │   ├── 嵌入式开发工程师
│   │   ├── 物联网工程师
│   │   └── 驱动开发工程师
│   │
│   └── CAT-0106  其他软件开发 (Other Software Dev)
│       ├── 区块链开发工程师 (也见DOM-06)
│       ├── 游戏开发工程师 (也见DOM-06)
│       └── 音视频开发工程师
│
├── DOM-02  数据与人工智能 (Data & Artificial Intelligence)
│   ├── CAT-0201  算法研究与AI模型 (Algorithm Research & AI Modeling)
│   │   ├── 算法工程师
│   │   ├── 机器学习工程师
│   │   ├── 深度学习工程师
│   │   ├── NLP算法工程师
│   │   └── 计算机视觉工程师
│   │
│   ├── CAT-0202  AI工程化与应用 (AI Engineering & Application)
│   │   ├── 人工智能工程师
│   │   ├── 提示词工程师 (Prompt Engineer)
│   │   ├── MLOps工程师
│   │   └── AIGC应用工程师
│   │
│   ├── CAT-0203  大数据工程 (Big Data Engineering)
│   │   ├── 大数据开发工程师
│   │   ├── 数据仓库工程师
│   │   └── 数据平台工程师
│   │
│   └── CAT-0204  数据分析与商业智能 (Data Analysis & BI)
│       ├── 数据分析师
│       ├── 数据科学家
│       ├── 商业分析师 (BA)
│       └── BI工程师
│
├── DOM-03  基础设施与运维 (Infrastructure & Operations)
│   ├── CAT-0301  运维与站点可靠性 (Operations & SRE)
│   │   ├── 运维工程师
│   │   ├── SRE工程师
│   │   └── 系统管理员
│   │
│   ├── CAT-0302  云计算与平台工程 (Cloud & Platform Engineering)
│   │   ├── 云计算工程师
│   │   ├── 平台工程师
│   │   └── DevOps工程师
│   │
│   └── CAT-0303  网络与通信工程 (Network & Communications)
│       ├── 网络工程师
│       ├── 通信工程师
│       └── 网络安全工程师 (也见DOM-05)
│
├── DOM-04  产品与项目管理 (Product & Project Management)
│   ├── CAT-0401  产品管理 (Product Management)
│   │   ├── 产品经理
│   │   ├── 产品总监/VP
│   │   └── AIGC产品经理 (新兴)
│   │
│   ├── CAT-0402  项目管理 (Project/Program Management)
│   │   ├── 项目经理
│   │   ├── 敏捷教练 (Scrum Master)
│   │   └── PMO
│   │
│   └── CAT-0403  技术管理 (Engineering Management)
│       ├── 技术经理
│       ├── 研发总监
│       └── 技术VP/CTO
│
├── DOM-05  质量与安全 (Quality & Security)
│   ├── CAT-0501  测试与质量保证 (Testing & QA)
│   │   ├── 测试工程师
│   │   ├── 自动化测试工程师
│   │   ├── 性能测试工程师
│   │   └── QA经理
│   │
│   └── CAT-0502  信息安全 (Information Security)
│       ├── 安全工程师
│       ├── 安全架构师
│       ├── 渗透测试工程师
│       └── 数据安全工程师
│
└── DOM-06  新兴与交叉技术 (Emerging & Cross-disciplinary Tech)
    ├── CAT-0601  区块链与Web3 (Blockchain & Web3)
    │   ├── 区块链工程师
    │   └── 智能合约开发工程师
    │
    ├── CAT-0602  游戏开发 (Game Development)
    │   ├── 游戏开发工程师
    │   ├── Unity开发工程师
    │   └── Unreal开发工程师
    │
    ├── CAT-0603  金融科技 (FinTech)
    │   ├── 量化交易员/工程师
    │   └── 金融科技工程师
    │
    └── CAT-0604  其他新兴岗位 (Other Emerging)
        ├── 数据标注师
        ├── AI训练师
        └── [EmergingJob预留]
```

### 2.3 分类定义

#### DOM-01 软件与算法开发

| 编码 | 类别 | 定义 | GB/T 6565映射 | ESCO映射 |
|------|------|------|--------------|----------|
| CAT-0101 | 后端开发 | 负责服务端应用程序的设计、开发与维护，包括业务逻辑、数据访问、API接口等。 | 2-02-10-01 计算机软件技术人员 | 2512.1 Software Developer |
| CAT-0102 | 前端与全栈开发 | 负责Web前端界面开发及跨前后端的全流程开发，涵盖UI实现、交互逻辑、全栈整合。 | 2-02-10-01 | 2513.1 Web Developer |
| CAT-0103 | 移动开发 | 专责Android/iOS/跨平台移动端原生或混合应用程序开发。 | 2-02-10-01 | 2514.1 Mobile App Developer |
| CAT-0104 | 架构设计 | 负责系统架构设计、技术选型、技术战略，指导团队技术方向。 | 2-02-10-03 计算机系统分析技术人员 | 2511.1 Systems Architect |
| CAT-0105 | 嵌入式与物联网开发 | 面向硬件平台（MCU/SoC/FPGA）的固件、驱动及应用软件开发。 | 2-02-10-04 | 2519.3 Embedded Systems Developer |
| CAT-0106 | 其他软件开发 | 跨领域或特定垂直方向（音视频、区块链、Web3等）的开发岗位。 | — | — |

#### DOM-02 数据与人工智能

| 编码 | 类别 | 定义 | GB/T 6565映射 | ESCO映射 |
|------|------|------|--------------|----------|
| CAT-0201 | 算法研究与AI模型 | 负责机器学习/深度学习模型的研究、设计、训练与优化，解决核心算法问题。 | 2-02-10-02 计算机应用技术人员 | 2519.6 ML Engineer |
| CAT-0202 | AI工程化与应用 | 将AI模型产品化、工程化部署，或基于LLM/GPT等大模型进行应用开发。 | — | 2519.7 AI Engineer |
| CAT-0203 | 大数据工程 | 负责大数据平台建设、数据处理流水线（ETL）、数据仓库设计与维护。 | 2-02-10-02 | 2521.1 Big Data Engineer |
| CAT-0204 | 数据分析与商业智能 | 对业务数据进行分析、建模和可视化，为决策提供数据支撑。 | 2-06-01-01 经济计划专业人员 | 3311.1 Data Analyst |

#### DOM-03 基础设施与运维

| 编码 | 类别 | 定义 | GB/T 6565映射 | ESCO映射 |
|------|------|------|--------------|----------|
| CAT-0301 | 运维与站点可靠性 | 负责生产环境运维、监控、故障处理，保障服务可用性（SLA）。 | 2-02-10-05 计算机网络技术人员 | 3512.1 IT Operations Technician |
| CAT-0302 | 云计算与平台工程 | 负责云基础设施规划、云原生平台建设、自动化部署与弹性伸缩。 | 2-02-10-05 | 2529.2 Cloud Engineer |
| CAT-0303 | 网络与通信工程 | 负责企业网络架构、通信协议实现、网络设备管理与优化。 | 2-02-10-05 | 2523.1 Network Engineer |

#### DOM-04 产品与项目管理

| 编码 | 类别 | 定义 | GB/T 6565映射 | ESCO映射 |
|------|------|------|--------------|----------|
| CAT-0401 | 产品管理 | 负责产品规划、需求定义、用户研究、产品生命周期管理。 | 2-06-07-04 品牌专业人员 | 2431.6 Product Manager |
| CAT-0402 | 项目管理 | 负责项目计划、进度跟踪、风险管控、资源协调与交付管理。 | 2-06-03-01 项目管理专业人员 | 2412.1 Project Manager |
| CAT-0403 | 技术管理 | 负责技术团队管理、技术战略规划、跨团队协调与人才培养。 | 1-05-01-01 企业负责人 | 1330.2 ICT Manager |

#### DOM-05 质量与安全

| 编码 | 类别 | 定义 | GB/T 6565映射 | ESCO映射 |
|------|------|------|--------------|----------|
| CAT-0501 | 测试与质量保证 | 负责软件测试（功能/性能/安全/自动化）、缺陷管理、质量体系建立。 | 2-02-10-06 计算机软件测试技术人员 | 2519.4 Software Tester |
| CAT-0502 | 信息安全 | 负责信息安全体系建设、渗透测试、安全监控、应急响应与合规管理。 | 2-02-10-07 | 2529.5 Security Engineer |

#### DOM-06 新兴与交叉技术

| 编码 | 类别 | 定义 | GB/T 6565映射 | ESCO映射 |
|------|------|------|--------------|----------|
| CAT-0601 | 区块链与Web3 | 负责区块链底层开发、智能合约编写、DApp开发与链上数据分析。 | — | 2519.8 Blockchain Developer |
| CAT-0602 | 游戏开发 | 负责游戏客户端/服务端开发、引擎定制、渲染优化与玩法实现。 | 2-09-06-04 数字媒体艺术专业人员 | 2519.9 Game Developer |
| CAT-0603 | 金融科技 | 负责量化交易系统、风控模型、支付系统等金融与技术的交叉领域。 | — | 3312.1 Quantitative Analyst |
| CAT-0604 | 其他新兴岗位 | LLM/大模型驱动的新型岗位（如提示词工程师、AI训练师、AI伦理师等）的预留分类。 | — | — |

### 2.4 岗位映射表（部分示例）

完整的 CSV 映射文件将存放于 `data/taxonomy/job_title_mapping.csv`，示例如下：

```csv
raw_title,canonical_title,domain_code,domain_name,category_code,category_name
"招聘Java后端开发","Java开发工程师","DOM-01","软件与算法开发","CAT-0101","后端开发"
"高级Java工程师","Java开发工程师","DOM-01","软件与算法开发","CAT-0101","后端开发"
"Golang开发","Go开发工程师","DOM-01","软件与算法开发","CAT-0101","后端开发"
"Web前端工程师","前端开发工程师","DOM-01","软件与算法开发","CAT-0102","前端与全栈开发"
"数据科学家","数据科学家","DOM-02","数据与人工智能","CAT-0204","数据分析与商业智能"
"AIGC产品经理","AIGC产品经理","DOM-04","产品与项目管理","CAT-0401","产品管理"
"SRE工程师","SRE工程师","DOM-03","基础设施与运维","CAT-0301","运维与站点可靠性"
```

---

## 3. 技能四层分类体系

### 3.1 体系结构

参考 **ESCO Skills pillar** 和 **O*NET Skills taxonomy**, 将技能分为四层：

```
第1层：技能域 (Skill Domain)         — 8个大类（含 SKD-99 其他），对应 ESCO skill pillar groups
第2层：技能组 (Skill Group)           — 29个分组，对应技能功能集群
第3层：技能类型 (Skill Type)          — 原59个分类的归并升级版 ~50个类型
第4层：具体技能 (Concrete Skill)      — 当前128个技能 + 扩展预留
```

### 3.2 分类树形图

```
技能分类体系
│
├── SKD-01  编程语言与框架 (Programming Languages & Frameworks)
│   ├── GRP-0101  后端编程语言 (Backend Languages)
│   │   ├── 类型: 主要后端语言
│   │   │   ├── Java
│   │   │   ├── Python
│   │   │   ├── Go
│   │   │   ├── C++
│   │   │   └── Rust
│   │   └── 类型: 脚本与其他语言
│   │       ├── Shell
│   │       ├── Ruby
│   │       ├── PHP
│   │       └── Scala
│   │
│   ├── GRP-0102  前端技术 (Frontend Technologies)
│   │   ├── 类型: 前端编程语言
│   │   │   ├── JavaScript
│   │   │   ├── TypeScript
│   │   │   └── Kotlin (前端用)
│   │   ├── 类型: 前端框架
│   │   │   ├── React
│   │   │   ├── Vue
│   │   │   └── Angular
│   │   ├── 类型: 前端基础技术
│   │   │   ├── HTML5
│   │   │   └── CSS3
│   │   └── 类型: 前端工具与运行时
│   │       ├── Webpack
│   │       ├── Vite
│   │       ├── Node.js
│   │       └── 小程序
│   │
│   ├── GRP-0103  后端框架 (Backend Frameworks)
│   │   ├── 类型: Java生态框架
│   │   │   ├── Spring
│   │   │   ├── Spring Boot
│   │   │   ├── Spring Cloud
│   │   │   ├── MyBatis
│   │   │   └── Hibernate
│   │   ├── 类型: Python生态框架
│   │   │   ├── Django
│   │   │   ├── Flask
│   │   │   └── FastAPI
│   │   └── 类型: 其他后端框架
│   │       ├── Express
│   │       ├── Laravel
│   │       └── Netty
│   │
│   ├── GRP-0104  移动开发技术 (Mobile Development Technologies)
│   │   ├── 类型: 移动开发框架
│   │   │   ├── Android SDK
│   │   │   ├── Jetpack
│   │   │   ├── UIKit
│   │   │   ├── SwiftUI
│   │   │   ├── Flutter
│   │   │   └── React Native
│   │   └── 类型: 移动开发工具
│   │       ├── Retrofit
│   │       ├── Core Data
│   │       ├── Combine
│   │       └── Room
│   │
│   └── GRP-0105  游戏与图形开发 (Game & Graphics)
│       ├── 类型: 游戏引擎
│       │   ├── Unity
│       │   └── Unreal Engine
│       └── 类型: 图形与多媒体
│           ├── OpenGL
│           ├── WebGL
│           ├── FFmpeg
│           └── WebRTC
│
├── SKD-02  数据存储与管理 (Data Storage & Management)
│   ├── GRP-0201  关系型数据库 (Relational Databases)
│   │   └── 类型: SQL数据库
│   │       ├── MySQL
│   │       ├── PostgreSQL
│   │       ├── Oracle
│   │       └── SQLite
│   │
│   ├── GRP-0202  非关系型数据库 (NoSQL & Cache)
│   │   ├── 类型: 文档/键值数据库
│   │   │   ├── MongoDB
│   │   │   └── Redis
│   │   ├── 类型: 列存/搜索数据库
│   │   │   ├── Elasticsearch
│   │   │   ├── HBase
│   │   │   └── ClickHouse
│   │   └── 类型: 向量数据库
│   │       └── 向量数据库 (Milvus/Pinecone/Weaviate等)
│   │
│   ├── GRP-0203  大数据与流处理 (Big Data & Stream Processing)
│   │   ├── 类型: 大数据计算框架
│   │   │   ├── Spark
│   │   │   ├── Flink
│   │   │   ├── Hadoop
│   │   │   └── Hive
│   │   └── 类型: 数据仓库
│   │       ├── 数据仓库
│   │       └── Doris
│   │
│   └── GRP-0204  消息队列与事件流 (Message Queues & Event Streaming)
│       ├── Kafka
│       ├── RabbitMQ
│       └── RocketMQ
│
├── SKD-03  人工智能与机器学习 (Artificial Intelligence & Machine Learning)
│   ├── GRP-0301  AI/ML框架 (AI/ML Frameworks)
│   │   ├── 类型: 深度学习框架
│   │   │   ├── TensorFlow
│   │   │   ├── PyTorch
│   │   │   └── Keras
│   │   └── 类型: 机器学习框架
│   │       ├── Scikit-learn
│   │       ├── XGBoost
│   │       └── LightGBM
│   │
│   ├── GRP-0302  AI/ML模型 (AI/ML Models)
│   │   ├── 类型: 语言模型
│   │   │   ├── Transformer
│   │   │   ├── BERT
│   │   │   ├── GPT
│   │   │   └── LLM
│   │   ├── 类型: 视觉模型
│   │   │   ├── CNN
│   │   │   ├── RNN
│   │   │   ├── YOLO
│   │   │   └── Stable Diffusion
│   │   └── 类型: 传统ML模型
│   │       └── XGBoost (also GRP-0301)
│   │
│   ├── GRP-0303  AI/ML应用领域 (AI/ML Application Domains)
│   │   ├── 机器学习
│   │   ├── 深度学习
│   │   ├── NLP
│   │   ├── 计算机视觉
│   │   ├── 数据挖掘
│   │   ├── 推荐系统
│   │   ├── 强化学习
│   │   ├── 语音识别
│   │   ├── 语音合成
│   │   └── 多模态
│   │
│   ├── GRP-0304  AI/ML工程化 (AI/ML Engineering)
│   │   ├── 类型: 模型部署与优化
│   │   │   ├── 模型部署
│   │   │   ├── 模型优化
│   │   │   ├── CUDA
│   │   │   ├── TensorRT
│   │   │   └── ONNX
│   │   ├── 类型: MLOps工具
│   │   │   ├── MLflow
│   │   │   ├── Kubeflow
│   │   │   └── HuggingFace
│   │   └── 类型: LLM应用框架
│   │       ├── LangChain
│   │       └── RAG
│   │
│   └── GRP-0305  AI工具与库 (AI Tools & Libraries)
│       ├── OpenCV
│       ├── jieba
│       ├── spaCy
│       ├── Kaldi
│       └── Matplotlib (跨界: 归入数据可视化)
│
├── SKD-04  云计算与基础设施 (Cloud & Infrastructure)
│   ├── GRP-0401  云平台 (Cloud Platforms)
│   │   ├── AWS
│   │   ├── Azure
│   │   └── Google Cloud
│   │
│   ├── GRP-0402  容器与编排 (Containers & Orchestration)
│   │   ├── Docker
│   │   └── Kubernetes
│   │
│   ├── GRP-0403  网络与通信 (Networking & Communication)
│   │   ├── 类型: 网络协议
│   │   │   ├── TCP/IP
│   │   │   └── 通信协议 (通用)
│   │   ├── 类型: API协议
│   │   │   ├── gRPC
│   │   │   ├── GraphQL
│   │   │   └── WebSocket
│   │   └── 类型: 服务网格
│   │       ├── Istio
│   │       ├── Envoy
│   │       └── Consul
│   │
│   └── GRP-0404  系统与基础设施 (Systems & Infra)
│       ├── 类型: 操作系统
│       │   └── Linux
│       ├── 类型: Web服务器
│       │   ├── Nginx
│       │   └── Gunicorn
│       └── 类型: 存储与注册中心
│           ├── ZooKeeper
│           ├── Nacos
│           ├── Harbor
│           └── Helix
│
├── SKD-05  DevOps与工程效能 (DevOps & Engineering Productivity)
│   ├── GRP-0501  CI/CD与构建 (CI/CD & Build)
│   │   ├── 类型: CI/CD工具
│   │   │   ├── Jenkins
│   │   │   └── CI/CD (概念)
│   │   ├── 类型: 构建工具
│   │   │   ├── Maven
│   │   │   ├── Gradle
│   │   │   └── CMake
│   │   └── 类型: 代码质量
│   │       └── SonarQube
│   │
│   ├── GRP-0502  可观测性与监控 (Observability & Monitoring)
│   │   ├── 类型: 监控工具
│   │   │   ├── Prometheus
│   │   │   └── Grafana
│   │   ├── 类型: 日志与追踪
│   │   │   ├── ELK
│   │   │   └── Jaeger
│   │   └── 类型: 前端监控
│   │       └── 前端监控 (概念)
│   │
│   └── GRP-0503  配置与基础设施即代码 (Config & IaC)
│       ├── 类型: IaC工具
│       │   └── Terraform
│       ├── 类型: 配置管理
│       │   └── Ansible
│       └── 类型: 容器编排辅助
│           └── Helm
│
├── SKD-06  测试、安全与质量 (Testing, Security & Quality)
│   ├── GRP-0601  软件测试 (Software Testing)
│   │   ├── 类型: 测试领域
│   │   │   ├── 自动化测试
│   │   │   ├── 性能测试
│   │   │   └── 单元测试
│   │   ├── 类型: 测试工具
│   │   │   ├── Selenium
│   │   │   ├── JMeter
│   │   │   ├── Postman
│   │   │   ├── Appium
│   │   │   └── Pytest
│   │   └── 类型: 安全测试
│   │       └── 安全测试 (概念)
│   │
│   ├── GRP-0602  信息安全 (Information Security)
│   │   ├── 类型: 安全领域
│   │   │   ├── 网络安全
│   │   │   ├── 渗透测试
│   │   │   └── 密码学
│   │   ├── 类型: 安全工具
│   │   │   ├── WAF
│   │   │   └── 漏洞扫描
│   │   ├── 类型: 安全运营
│   │   │   └── SOC
│   │   └── 类型: 安全标准
│   │       └── ISO27001
│   │
│   └── GRP-0603  代码与架构质量 (Code & Architecture Quality)
│       └── 类型: 架构质量
│           ├── 领域驱动设计
│           ├── 设计模式
│           └── 代码重构
│
├── SKD-07  业务、产品与软技能 (Business, Product & Soft Skills)
│   ├── GRP-0701  产品与设计工具 (Product & Design Tools)
│   │   ├── Axure
│   │   ├── Figma
│   │   ├── Sketch
│   │   └── XMind (概念: 思维导图)
│   │
│   ├── GRP-0702  数据分析与商业智能 (Data Analysis & BI)
│   │   ├── 类型: 数据分析库
│   │   │   ├── Pandas
│   │   │   ├── NumPy
│   │   │   └── SciPy
│   │   ├── 类型: 数据可视化
│   │   │   ├── Tableau
│   │   │   ├── ECharts
│   │   │   └── D3.js
│   │   ├── 类型: BI工具
│   │   │   └── 数据分析 (概念)
│   │   └── 类型: 办公工具
│   │       └── Excel
│   │
│   ├── GRP-0703  管理与方法论 (Management & Methodologies)
│   │   ├── 类型: 管理能力
│   │   │   ├── 项目管理
│   │   │   ├── 风险管理
│   │   │   ├── 沟通协调
│   │   │   ├── PMO
│   │   │   └── 技术管理
│   │   ├── 类型: 方法论
│   │   │   ├── 敏捷开发
│   │   │   └── Scrum
│   │   └── 类型: 项目管理工具
│   │       └── JIRA
│   │
│   ├── GRP-0704  产品能力 (Product Capabilities)
│   │   ├── PRD (产品需求文档)
│   │   ├── 用户研究
│   │   ├── 竞品分析
│   │   ├── 需求分析
│   │   ├── 原型设计
│   │   ├── 用户体验
│   │   └── AB实验
│   │
│   └── GRP-0705  架构与系统设计 (Architecture & System Design)
│       ├── 类型: 架构模式
│       │   ├── 微服务
│       │   └── MVVM
│       ├── 类型: 非功能需求
│       │   ├── 分布式
│       │   ├── 高并发
│       │   └── 系统设计
│       └── 类型: 领域知识
│           └── 金融科技
│
└── SKD-99  其他 (Uncategorized)
    └── [未匹配新技能的临时存放区]
```

### 3.3 新旧分类对照表

以下是现有59个平级分类到新体系的映射（完整映射存储于 `data/taxonomy/skill_category_mapping.csv`）：

| 旧分类 (59个) | 新域名 (SKD) | 新组名 (GRP) | 新类型 | 合并策略 |
|--------------|-------------|-------------|--------|---------|
| 编程语言(13) | SKD-01 | GRP-0101 后端编程语言 | 主要后端语言 | 保持 |
| JavaScript/TypeScript | SKD-01 | GRP-0102 前端技术 | 前端编程语言 | 从"编程语言"中拆分 |
| 前端框架(3) | SKD-01 | GRP-0102 前端技术 | 前端框架 | 重归类 |
| 前端技术(3) | SKD-01 | GRP-0102 前端技术 | 前端基础技术 | 重归类 |
| 构建工具(4) | SKD-05 | GRP-0501 CI/CD与构建 | 构建工具 | 重归类 |
| 后端框架(8) | SKD-01 | GRP-0103 后端框架 | (拆分为子类型) | 保持 |
| 通信协议(2): gRPC/GraphQL | SKD-04 | GRP-0403 网络与通信 | API协议 | **修复**: 与TCP/IP分离 |
| 通信协议: TCP/IP | SKD-04 | GRP-0403 网络与通信 | 网络协议 | **修复**: 合并入网络协议 |
| 数据库(8) | SKD-02 | (拆分为GRP-0201/0202) | — | 按数据库类型拆分 |
| AI框架(5) | SKD-03 | GRP-0301 AI/ML框架 | 深度学习框架/ML框架 | **合并**: 6个AI分类→4个GRP |
| AI模型(5) | SKD-03 | GRP-0302 AI/ML模型 | (拆分为子类型) | 合并 |
| AI领域(10) | SKD-03 | GRP-0303 AI/ML应用领域 | — | 合并 |
| AI工具(3) | SKD-03 | GRP-0304 AI/ML工程化 | LLM应用框架 | 合并 |
| AI加速(1) | SKD-03 | GRP-0304 AI/ML工程化 | 模型部署与优化 | **合并**: 单技能分类 |
| AI推理(1) | SKD-03 | GRP-0304 AI/ML工程化 | 模型部署与优化 | **合并**: 单技能分类 |
| 安全领域(3) | SKD-06 | GRP-0602 信息安全 | 安全领域 | **合并**: 4个安全分类→1个GRP |
| 安全工具(2) | SKD-06 | GRP-0602 信息安全 | 安全工具 | 合并 |
| 安全标准(1) | SKD-06 | GRP-0602 信息安全 | 安全标准 | **合并**: 单技能→属性 |
| 安全运营(1) | SKD-06 | GRP-0602 信息安全 | 安全运营 | **合并**: 单技能→属性 |
| 产品工具(1) | SKD-07 | GRP-0701 产品与设计工具 | — | **合并**: 4个产品分类→2个GRP |
| 产品文档(1) | SKD-07 | GRP-0704 产品能力 | — | 合并 |
| 产品能力(1) | SKD-07 | GRP-0704 产品能力 | — | 合并 |
| 产品设计(1) | SKD-07 | GRP-0704 产品能力 | — | 合并 |
| 管理能力(4) | SKD-07 | GRP-0703 管理与方法论 | 管理能力 | **合并**: 3个管理分类→1个GRP |
| 管理方法(2) | SKD-07 | GRP-0703 管理与方法论 | 方法论 | 合并 |
| 项目管理工具(1) | SKD-07 | GRP-0703 管理与方法论 | 项目管理工具 | **合并**: 单技能 |
| 操作系统(1) | SKD-04 | GRP-0404 系统与基础设施 | 操作系统 | **合并**: 单技能→归属大GRP |
| 版本控制(1) | SKD-05 | — | — | **合并**: 归入工程效能域 |
| Web服务器(1) | SKD-04 | GRP-0404 系统与基础设施 | Web服务器 | **合并**: 单技能→归属大GRP |
| 脚本语言(1) | SKD-01 | GRP-0101 后端编程语言 | 脚本与其他语言 | **合并**: 单技能→归属 |
| 运行时(1) | SKD-01 | GRP-0102 前端技术 | 前端工具与运行时 | **合并**: Node.js重归类 |
| 视觉库(1) | SKD-03 | GRP-0305 AI工具与库 | — | **合并**: OpenCV归入AI工具 |
| IDE工具(1) | SKD-05 | — | — | **合并**: Xcode归入工程工具 |
| C++库(1) | SKD-01 | GRP-0101 后端编程语言 | — | **合并**: STL归入C++生态系统 |
| 网络框架(1) | SKD-01 | GRP-0104 移动开发技术 | 移动开发工具 | **合并**: Retrofit归入移动开发 |
| UI框架(1) | SKD-01 | GRP-0104 移动开发技术 | — | **合并**: Qt归入移动/桌面开发 |
| 程序基础(1) | SKD-01 | — | — | **合并**: 多线程归入编程通用基础 |
| 数据领域(1) | SKD-02 | GRP-0203 大数据与流处理 | — | **合并**: 数据仓库归入大数据 |
| BI工具(1) | SKD-07 | GRP-0702 数据分析与商业智能 | BI工具 | **合并**: 单技能 |
| 办公工具(1) | SKD-07 | GRP-0702 数据分析与商业智能 | 办公工具 | **合并**: 单技能 |
| 设计工具(1) | SKD-07 | GRP-0701 产品与设计工具 | — | **合并**: Figma归入产品设计 |
| 金融科技(1) | SKD-07 | GRP-0705 架构与系统设计 | 领域知识 | **合并**: 量化交易→领域知识 |
| 区块链(5) | SKD-07 | GRP-0705 (或独立) | 领域知识 | 保留为领域知识标签 |
| 智能合约(1) | SKD-07 | GRP-0705 (或独立) | 领域知识 | **合并**: 归入区块链生态系统 |

### 3.4 ESCO 技能参考映射

| ESCO技能概念 | 本体系映射 | ESCO URI |
|-------------|-----------|----------|
| programming | SKD-01 编程语言与框架 | http://data.europa.eu/esco/skill/4e0f... |
| machine learning | SKD-03 人工智能与ML | http://data.europa.eu/esco/skill/... |
| data analysis | SKD-07 > GRP-0702 数据分析 | http://data.europa.eu/esco/skill/... |
| DevOps | SKD-05 DevOps与工程效能 | http://data.europa.eu/esco/skill/... |
| cybersecurity | SKD-06 > GRP-0602 信息安全 | http://data.europa.eu/esco/skill/F3 |
| cloud computing | SKD-04 > GRP-0401 云平台 | http://data.europa.eu/esco/skill/... |
| project management | SKD-07 > GRP-0703 管理与方法论 | http://data.europa.eu/esco/skill/T2 |

---

## 4. 行业分类体系

### 4.1 体系结构

参考 **GB/T 4754-2017 国民经济行业分类**，将现有71个行业文本映射为标准分类：

```
第1层：行业门类 (Section)       — A~T 共20个门类，如 "I 信息传输、软件和信息技术服务业"
第2层：行业大类 (Division)      — 2位数字编码，如 "64 互联网和相关服务"
第3层：行业中类 (Group)         — 3位数字编码，如 "645 软件开发"
```

### 4.2 分类树形图（仅列出与数据相关的门类）

```
行业分类体系 (GB/T 4754-2017)
│
├── C 制造业
│   ├── 34 通用设备制造业
│   ├── 35 专用设备制造业
│   ├── 36 汽车制造业
│   │   └── 361 汽车整车制造 → "汽车/出行"
│   ├── 38 电气机械和器材制造业
│   │   └── 384 电池制造 → "新能源"
│   ├── 39 计算机、通信和其他电子设备制造业
│   │   ├── 391 计算机制造 → "互联网/IT" (制造端)
│   │   ├── 392 通信设备制造 → "通信/电子"
│   │   └── 397 电子器件制造 → "半导体/集成电路"
│   └── 40 仪器仪表制造业
│
├── I 信息传输、软件和信息技术服务业
│   ├── 63 电信、广播电视和卫星传输服务
│   │   └── 631 电信 → "通信/电子"
│   ├── 64 互联网和相关服务
│   │   ├── 642 互联网信息服务 → "互联网/IT"
│   │   ├── 643 互联网平台 → "互联网/IT" (平台型)
│   │   └── 645 互联网数据服务 → "云计算"
│   └── 65 软件和信息技术服务业
│       ├── 651 软件开发 → "互联网/IT"
│       ├── 652 集成电路设计 → "半导体/集成电路"
│       ├── 654 运行维护服务 → "互联网/IT"
│       └── 659 其他信息技术服务业 → "人工智能" (专项)
│
├── J 金融业
│   ├── 66 货币金融服务 → "金融" (银行)
│   ├── 67 资本市场服务 → "金融" (证券/基金)
│   └── 69 其他金融业 → "金融科技" (新兴)
│
├── M 科学研究和技术服务业
│   └── 73 研究和试验发展 → "人工智能" (研究端)
│
├── P 教育
│   ├── 832 高等教育 → "教育/培训"
│   └── 839 其他教育 → "教育/培训"
│
├── Q 卫生和社会工作
│   └── 841 医院 → "医疗健康"
│
└── R 文化、体育和娱乐业
    └── 862 数字内容服务 → "游戏/娱乐"
```

### 4.3 现有行业映射表（部分）

完整的CSV映射文件存放于 `data/taxonomy/industry_mapping.csv`。

| 现有行业值 (约71个) | GB/T 4754 门类 | 编码 | 大类名称 | 中类编码 | 中类名称 |
|----------|---------|------|---------|---------|------|
| 互联网/IT | I | 64 | 互联网和相关服务 | 642 | 互联网信息服务 |
| 人工智能 | I | 65 | 软件和信息技术服务业 | 659 | 其他信息技术服务业 |
| 人工智能 (研究端) | M | 73 | 研究和试验发展 | — | — |
| 通信/电子 | C | 39 | 计算机、通信和其他电子设备制造业 | 392 | 通信设备制造 |
| 金融 | J | 66 | 货币金融服务 | — | — |
| 教育/培训 | P | 83 | 教育 | 839 | 其他教育 |
| 医疗健康 | Q | 84 | 卫生 | 841 | 医院 |
| 智能制造 | C | 35 | 专用设备制造业 | — | — |
| 汽车/出行 | C | 36 | 汽车制造业 | 361 | 汽车整车制造 |
| 电商/零售 | I | 64 | 互联网和相关服务 | 643 | 互联网平台 |
| 游戏/娱乐 | R | 86 | 娱乐业 | 862 | 数字内容服务 |
| 半导体/集成电路 | C | 39 | 制造业 | 397 | 电子器件制造 |
| 新能源 | C | 38 | 电气机械和器材制造业 | 384 | 电池制造 |

---

## 5. 能力/胜任力分类体系

### 5.1 体系结构

参考 **O*NET Content Model** 和 **ESCO Transversal Skills**, 将岗位能力分为三个维度：

```
第1层：能力维度 (Ability Dimension) — 5个核心维度
第2层：能力群 (Competency Cluster)  — 12个能力群
第3层：具体能力 (Competency)        — ~40项具体能力
```

### 5.2 分类树形图

```
能力分类体系
│
├── ABL-01  技术能力 (Technical Competencies)
│   ├── CLS-0101  编程与软件开发能力
│   │   ├── 代码编写与调试
│   │   ├── 算法与数据结构
│   │   ├── 系统设计与架构
│   │   └── 技术方案设计
│   │
│   ├── CLS-0102  数据与AI能力
│   │   ├── 数据建模与分析
│   │   ├── 机器学习建模
│   │   ├── 数据工程 (ETL/数仓)
│   │   └── 数据可视化
│   │
│   ├── CLS-0103  基础设施与运维能力
│   │   ├── 云基础设施管理
│   │   ├── 自动化运维 (IaC)
│   │   ├── 故障诊断与恢复
│   │   └── 性能优化与容量规划
│   │
│   └── CLS-0104  安全与质量能力
│       ├── 安全风险评估
│       ├── 渗透测试与防御
│       ├── 测试策略设计
│       └── 代码审查与质量保证
│
├── ABL-02  业务能力 (Business Competencies)
│   ├── CLS-0201  产品与需求能力
│   │   ├── 需求分析与定义
│   │   ├── 用户研究与画像
│   │   ├── 产品路线图规划
│   │   └── 竞品与市场分析
│   │
│   └── CLS-0202  行业与应用能力
│       ├── 行业知识 (金融/医疗/教育/制造...)
│       ├── 业务流程理解
│       ├── 法规与合规知识
│       └── 技术趋势洞察
│
├── ABL-03  管理能力 (Management Competencies)
│   ├── CLS-0301  项目管理能力
│   │   ├── 项目计划与控制
│   │   ├── 敏捷/Scrum管理
│   │   ├── 风险管理
│   │   └── 资源协调与分配
│   │
│   ├── CLS-0302  团队管理能力
│   │   ├── 技术团队领导
│   │   ├── 绩效管理与激励
│   │   ├── 冲突解决与决策
│   │   └── 跨部门协作
│   │
│   └── CLS-0303  战略与规划能力
│       ├── 技术战略制定
│       ├── 预算与成本控制
│       └── 组织架构设计
│
├── ABL-04  软技能 (Soft Skills / Transversal)
│   ├── CLS-0401  沟通与协作
│   │   ├── 技术文档撰写
│   │   ├── 口头表达与演讲
│   │   ├── 团队协作
│   │   └── 跨职能沟通
│   │
│   ├── CLS-0402  思维与学习能力
│   │   ├── 分析与批判性思维
│   │   ├── 快速学习与技术适应
│   │   ├── 问题解决能力
│   │   └── 创新与创造力
│   │
│   └── CLS-0403  职业素养
│       ├── 时间管理与自我驱动
│       ├── 责任心与抗压能力
│       ├── 职业道德与保密意识
│       └── 以用户/客户为中心
│
└── ABL-05  领域专项能力 (Domain-specific Competencies)
    ├── CLS-0501  金融科技专项
    │   ├── 量化策略开发
    │   ├── 风控建模
    │   └── 金融产品设计
    │
    ├── CLS-0502  医疗AI专项
    │   ├── 医学影像分析
    │   ├── 临床决策支持
    │   └── 医疗数据处理 (HIPAA)
    │
    └── CLS-0503  自动驾驶专项
        ├── 传感器融合
        ├── 路径规划与控制
        └── 功能安全 (ISO 26262)
```

### 5.3 O*NET 内容模型映射

| O*NET 维度 | 本体系映射 | 说明 |
|-----------|-----------|------|
| Skills: Technical Skills | ABL-01 技术能力 | 编程、数据分析、AI/ML |
| Skills: Resource Management | ABL-03 > CLS-0301 | 项目管理能力 |
| Skills: Social Skills | ABL-04 > CLS-0401 | 沟通与协作 |
| Skills: Complex Problem Solving | ABL-04 > CLS-0402 | 分析与问题解决 |
| Knowledge: Business & Management | ABL-02 > CLS-0201 | 业务与产品 |
| Work Styles | ABL-04 > CLS-0403 | 职业素养 |

---

## 6. 教育/经验有序化

### 6.1 教育层级有序化

```yaml
education_ordered:
  0: "学历不限"
  1: "高中/中专及以下"
  2: "大专"
  3: "本科"
  4: "硕士"
  5: "博士"
  6: "博士后"

# 新增属性: level (int), is_minimum_required (bool)
```

### 6.2 经验范围有序化

```yaml
experience_ordered:
  # 离散值映射为有序区间
  "经验不限": {min_years: 0, max_years: 99, ordinal: 0}
  "应届生":   {min_years: 0, max_years: 0, ordinal: 1}
  "1年以下":  {min_years: 0, max_years: 1, ordinal: 2}
  "1-3年":    {min_years: 1, max_years: 3, ordinal: 3}
  "3-5年":    {min_years: 3, max_years: 5, ordinal: 4}
  "5-10年":   {min_years: 5, max_years: 10, ordinal: 5}
  "10年以上": {min_years: 10, max_years: 99, ordinal: 6}

# 新增属性: ordinal (int), min_years (float), max_years (float)
```

---

## 7. 分类与知识图谱的映射方案

### 7.1 Neo4j 新增标签

```
原有标签 9 种                             新增标签 12 种
───────────────────────────              ──────────────────────────
JobTitle   ──保持不变                      JobDomain        (岗位职能域)
Skill      ──增加层级属性                   JobCategory      (岗位类别)
Company    ──保持不变                      SkillDomain      (技能域)
City       ──保持不变                      SkillGroup       (技能组)
Industry   ──增加层级编码和属性             SkillType        (技能类型)
Education  ──增加ordered_level属性          IndustrySector   (行业门类)
Experience ──增加ordered_level属性          IndustryDivision (行业大类)
Job        ──保持不变                      IndustryGroup    (行业中类)
EmergingJob──增加category标签              AbilityDimension (能力维度)
                                          CompetencyCluster(能力群)
                                          Competency       (具体能力)
```

### 7.2 图模型设计

#### 7.2.1 岗位分类图模型

```
┌──────────┐                            ┌──────────┐
│ JobDomain│                            │JobCategory│
│  name    │◄──── HAS_DOMAIN ──────────│  name    │
│  code    │                            │  code    │
│  desc    │                            │  desc    │
└────┬─────┘                            └────┬─────┘
     │                                       │
     │ HAS_SUBCLASS                          │ HAS_SUBCLASS
     │                                       │
     ▼                                       ▼
┌──────────┐                            ┌──────────┐
│ JobTitle │                            │  Job     │
│  name    │                            │record_id │
│ domain   │◄─── HAS_TITLE ────────────│  ...     │
│ category │                            │          │
│  code    │                            └──────────┘
└──────────┘
     ▲
     │ IS_VARIANT_OF
     │
┌──────────┐
│EmergingJob│
│  name    │
│  category│  = "emerging"
└──────────┘
```

#### 7.2.2 Neo4j 约束与索引定义

```cypher
-- 岗位层级
CREATE CONSTRAINT job_domain_code IF NOT EXISTS FOR (n:JobDomain)      REQUIRE n.code IS UNIQUE;
CREATE CONSTRAINT job_category_code IF NOT EXISTS FOR (n:JobCategory)  REQUIRE n.code IS UNIQUE;

-- 技能层级
CREATE CONSTRAINT skill_domain_code IF NOT EXISTS FOR (n:SkillDomain)  REQUIRE n.code IS UNIQUE;
CREATE CONSTRAINT skill_group_code IF NOT EXISTS FOR (n:SkillGroup)    REQUIRE n.code IS UNIQUE;
CREATE CONSTRAINT skill_type_code IF NOT EXISTS FOR (n:SkillType)      REQUIRE n.code IS UNIQUE;

-- 行业层级 (GB/T 4754)
CREATE CONSTRAINT industry_sector_code IF NOT EXISTS FOR (n:IndustrySector)      REQUIRE n.code IS UNIQUE;
CREATE CONSTRAINT industry_division_code IF NOT EXISTS FOR (n:IndustryDivision)  REQUIRE n.code IS UNIQUE;
CREATE CONSTRAINT industry_group_code IF NOT EXISTS FOR (n:IndustryGroup)        REQUIRE n.code IS UNIQUE;

-- 能力层级
CREATE CONSTRAINT ability_dimension_code IF NOT EXISTS FOR (n:AbilityDimension)     REQUIRE n.code IS UNIQUE;
CREATE CONSTRAINT competency_cluster_code IF NOT EXISTS FOR (n:CompetencyCluster)    REQUIRE n.code IS UNIQUE;
CREATE CONSTRAINT competency_code IF NOT EXISTS FOR (n:Competency)                   REQUIRE n.code IS UNIQUE;

-- 索引
CREATE INDEX job_title_domain_idx      IF NOT EXISTS FOR (n:JobTitle)     ON (n.domain_code);
CREATE INDEX job_title_category_idx    IF NOT EXISTS FOR (n:JobTitle)     ON (n.category_code);
CREATE INDEX skill_domain_idx          IF NOT EXISTS FOR (s:Skill)        ON (s.domain_code);
CREATE INDEX skill_group_idx           IF NOT EXISTS FOR (s:Skill)        ON (s.group_code);
CREATE INDEX industry_division_idx     IF NOT EXISTS FOR (i:Industry)     ON (i.division_code);
```

#### 7.2.3 新增关系类型

```cypher
-- 岗位分类关系
(:JobTitle)-[:BELONGS_TO_CATEGORY]->(:JobCategory)
(:JobCategory)-[:BELONGS_TO_DOMAIN]->(:JobDomain)

-- 技能层级关系
(:Skill)-[:BELONGS_TO_TYPE]->(:SkillType)
(:SkillType)-[:BELONGS_TO_GROUP]->(:SkillGroup)
(:SkillGroup)-[:BELONGS_TO_DOMAIN]->(:SkillDomain)

-- 行业层级关系
(:Industry)-[:BELONGS_TO_GROUP]->(:IndustryGroup)
(:IndustryGroup)-[:BELONGS_TO_DIVISION]->(:IndustryDivision)
(:IndustryDivision)-[:BELONGS_TO_SECTOR]->(:IndustrySector)

-- 岗位-能力映射关系
(:JobTitle)-[:REQUIRES_COMPETENCY {level: 1|2|3|4|5}]->(:Competency)
(:Competency)-[:BELONGS_TO_CLUSTER]->(:CompetencyCluster)
(:CompetencyCluster)-[:BELONGS_TO_DIMENSION]->(:AbilityDimension)
```

### 7.3 节点属性设计

#### JobTitle 节点（扩展）

```yaml
JobTitle:
  name: "Java开发工程师"        # 原有
  canonical_name: "Java开发工程师"  # 原有（清理后）
  domain_code: "DOM-01"         # 新增：职能域编码
  domain_name: "软件与算法开发"   # 新增：职能域名称
  category_code: "CAT-0101"     # 新增：类别编码
  category_name: "后端开发"      # 新增：类别名称
  gb_code: "2-02-10-01"         # 新增：GB/T 6565映射编码
  esco_uri: "..."               # 新增：ESCO URI（可选）
  onet_code: "..."              # 新增：O*NET SOC（可选）
```

#### Skill 节点（扩展）

```yaml
Skill:
  name: "Python"                # 原有
  category: "主要后端语言"        # 原有（改为新编码）
  domain_code: "SKD-01"         # 新增：技能域编码
  domain_name: "编程语言与框架"   # 新增：技能域名称
  group_code: "GRP-0101"        # 新增：技能组编码
  group_name: "后端编程语言"      # 新增：技能组名称
  type_code: "T-01011"          # 新增：技能类型编码
  type_name: "主要后端语言"       # 新增：技能类型名称
  esco_uri: "..."               # 新增：ESCO技能URI
  proficiency_levels: [1,2,3]   # 新增：熟练度等级范围
```

#### Industry 节点（扩展）

```yaml
Industry:
  name: "互联网/IT"              # 原有
  code: "I-64-645"              # 新增：GB/T 4754编码 (门类-大类-中类)
  sector_code: "I"              # 新增：门类编码
  sector_name: "信息传输、软件和信息技术服务业"
  division_code: "64"           # 新增：大类编码
  division_name: "互联网和相关服务"
  group_code: "645"             # 新增：中类编码
  group_name: "软件开发"
```

#### Education 节点（扩展）

```yaml
Education:
  name: "本科"                  # 原有
  ordinal: 3.0                  # 新增：有序层级 (0~6)
```

#### Experience 节点（扩展）

```yaml
Experience:
  name: "3-5年"                # 原有
  ordinal: 4                    # 新增：有序层级
  min_years: 3.0                # 新增：最小年数
  max_years: 5.0                # 新增：最大年数
```

### 7.4 数据导入Cypher脚本（示例）

```cypher
// ========== 岗位分类导入 ==========
// 1. 创建职能域节点
UNWIND [
  {code:"DOM-01", name:"软件与算法开发", desc:"..."},
  {code:"DOM-02", name:"数据与人工智能", desc:"..."},
  {code:"DOM-03", name:"基础设施与运维", desc:"..."},
  {code:"DOM-04", name:"产品与项目管理", desc:"..."},
  {code:"DOM-05", name:"质量与安全", desc:"..."},
  {code:"DOM-06", name:"新兴与交叉技术", desc:"..."}
] AS row
MERGE (d:JobDomain {code: row.code})
SET d.name = row.name, d.description = row.desc;

// 2. 创建岗位类别节点
UNWIND [
  {code:"CAT-0101", name:"后端开发", domain_code:"DOM-01"},
  {code:"CAT-0102", name:"前端与全栈开发", domain_code:"DOM-01"},
  {code:"CAT-0103", name:"移动开发", domain_code:"DOM-01"},
  {code:"CAT-0104", name:"架构设计", domain_code:"DOM-01"},
  {code:"CAT-0105", name:"嵌入式与物联网开发", domain_code:"DOM-01"},
  {code:"CAT-0106", name:"其他软件开发", domain_code:"DOM-01"},
  {code:"CAT-0201", name:"算法研究与AI模型", domain_code:"DOM-02"},
  {code:"CAT-0202", name:"AI工程化与应用", domain_code:"DOM-02"},
  {code:"CAT-0203", name:"大数据工程", domain_code:"DOM-02"},
  {code:"CAT-0204", name:"数据分析与商业智能", domain_code:"DOM-02"},
  {code:"CAT-0301", name:"运维与站点可靠性", domain_code:"DOM-03"},
  {code:"CAT-0302", name:"云计算与平台工程", domain_code:"DOM-03"},
  {code:"CAT-0303", name:"网络与通信工程", domain_code:"DOM-03"},
  {code:"CAT-0401", name:"产品管理", domain_code:"DOM-04"},
  {code:"CAT-0402", name:"项目管理", domain_code:"DOM-04"},
  {code:"CAT-0403", name:"技术管理", domain_code:"DOM-04"},
  {code:"CAT-0501", name:"测试与质量保证", domain_code:"DOM-05"},
  {code:"CAT-0502", name:"信息安全", domain_code:"DOM-05"},
  {code:"CAT-0601", name:"区块链与Web3", domain_code:"DOM-06"},
  {code:"CAT-0602", name:"游戏开发", domain_code:"DOM-06"},
  {code:"CAT-0603", name:"金融科技", domain_code:"DOM-06"},
  {code:"CAT-0604", name:"其他新兴岗位", domain_code:"DOM-06"}
] AS row
MERGE (c:JobCategory {code: row.code})
SET c.name = row.name
WITH c, row
MATCH (d:JobDomain {code: row.domain_code})
MERGE (c)-[:BELONGS_TO_DOMAIN]->(d);

// 3. 将现有JobTitle关联到JobCategory（分类映射逻辑）
// Java系 → CAT-0101 后端开发
MATCH (t:JobTitle)
WHERE t.name CONTAINS 'Java' OR t.name CONTAINS 'Go' OR t.name CONTAINS 'Python'
   OR t.name CONTAINS 'C++' OR t.name CONTAINS 'PHP' OR t.name CONTAINS '后端'
WITH t
MATCH (c:JobCategory {code: 'CAT-0101'})
MERGE (t)-[:BELONGS_TO_CATEGORY]->(c)
SET t.domain_code = 'DOM-01', t.category_code = 'CAT-0101';

// ... (类似逻辑覆盖其他岗位映射)

// ========== 技能分类导入 ==========
// 4. 创建技能域
UNWIND [
  {code:"SKD-01", name:"编程语言与框架", desc:"..."},
  {code:"SKD-02", name:"数据存储与管理", desc:"..."},
  {code:"SKD-03", name:"人工智能与机器学习", desc:"..."},
  {code:"SKD-04", name:"云计算与基础设施", desc:"..."},
  {code:"SKD-05", name:"DevOps与工程效能", desc:"..."},
  {code:"SKD-06", name:"测试、安全与质量", desc:"..."},
  {code:"SKD-07", name:"业务、产品与软技能", desc:"..."},
  {code:"SKD-99", name:"其他", desc:"..."}
] AS row
MERGE (d:SkillDomain {code: row.code}) SET d.name = row.name;

// 5. 更新现有Skill节点的分类属性
// Python → SKD-01 > GRP-0101 > T-01011
MATCH (s:Skill {name: "Python"})
SET s.domain_code = "SKD-01",
    s.group_code = "GRP-0101",
    s.type_code = "T-01011",
    s.group_name = "后端编程语言",
    s.type_name = "主要后端语言";

// ... (批量更新128个技能，从映射CSV文件读取)
```

---

## 8. API与前端集成路径

### 8.1 API变更

```
受影响API端点                                  变更说明
────────────────────────────────────────────────────────────────────
GET  /api/skills/categories        → 返回层级结构而非平级列表，新增parent字段
GET  /api/skills/ranking           → 新增domain/group分组参数
GET  /api/skills/network           → 节点颜色按domain_code着色
GET  /api/skills/communities       → 新增分类交叉验证结果
GET  /api/overview/*               → 新增按DOM-xx聚合的岗位分布
POST /api/overview/job-distribution → 新增category维度（现有仅行业/城市/学历）
新增  GET  /api/taxonomy/job-tree       → 返回岗位三层树形结构
新增  GET  /api/taxonomy/skill-tree     → 返回技能四层树形结构
新增  GET  /api/taxonomy/industry-tree  → 返回行业三层树形结构
新增  GET  /api/taxonomy/ability-tree   → 返回能力三层树形结构
新增  GET  /api/taxonomy/cross-walk     → 岗位↔技能↔行业↔能力的交叉关联
```

### 8.2 API 响应格式设计

```json
// GET /api/taxonomy/job-tree
{
  "tree": [
    {
      "code": "DOM-01",
      "name": "软件与算法开发",
      "children": [
        {
          "code": "CAT-0101",
          "name": "后端开发",
          "job_count": 342,
          "top_skills": ["Java", "Spring Boot", "MySQL", "Redis"],
          "children": [
            { "name": "Java开发工程师", "job_count": 205 },
            { "name": "Go开发工程师", "job_count": 87 },
            { "name": "Python开发工程师", "job_count": 50 }
          ]
        },
        { "code": "CAT-0102", "name": "前端与全栈开发", "job_count": 180, "...": "..." }
      ]
    }
  ]
}

// GET /api/skills/categories (增强版)
{
  "tree": [
    {
      "code": "SKD-01",
      "name": "编程语言与框架",
      "total_demand": 5400,
      "children": [
        {
          "code": "GRP-0101",
          "name": "后端编程语言",
          "total_demand": 2100,
          "children": [
            { "code": "T-01011", "name": "主要后端语言", "total_demand": 1800,
              "skills": [{"name":"Java","demand":800}, {"name":"Python","demand":600}] }
          ]
        }
      ]
    }
  ]
}
```

### 8.3 前端可视化升级

| 当前组件 | 升级后 | 技术方案 |
|---------|--------|---------|
| 技能分布饼图 (平级59类) | 技能旭日图 (sunburst, 4层) | ECharts sunburst series |
| 技能排名柱状图 | 带分组着色和筛选 | ECharts bar + select filter |
| 岗位分布统计 (仅label) | 岗位树形图 (treemap/sunburst) | ECharts treemap |
| — | 行业分布树形图 | ECharts tree |
| — | 分类交叉桑基图 (岗位↔行业↔技能) | ECharts sankey |

---

## 9. 数据迁移与实施计划

### 9.1 实施分阶段

```
Phase 1: 分类体系发布 (Week 1-2)
├── 发布 TAXONOMY_DESIGN.md (本文档)
├── 创建 CSV 映射文件
│   ├── data/taxonomy/job_title_mapping.csv      (383 rows)
│   ├── data/taxonomy/skill_category_mapping.csv  (200 rows)
│   ├── data/taxonomy/industry_mapping.csv        (71 rows)
│   └── data/taxonomy/ability_mapping.csv         (initial seed)
├── 编写分类节点导入脚本 (taxonomy_importer.py)
└── 单元测试：分类映射覆盖率达到 100%

Phase 2: Neo4j图模型更新 (Week 2-3)
├── 新增12种节点标签和约束
├── 导入分类节点 (JobDomain, JobCategory, SkillDomain, SkillGroup, SkillType, ...)
├── 更新现有节点属性 (JobTitle, Skill, Industry, Education, Experience)
├── 创建分类层级关系边
└── 验证：节点数量、关系完整性、层级引用一致性

Phase 3: API升级 (Week 3-4)
├── 新增 /api/taxonomy/* 端点
├── 修改 /api/skills/* 端点（向后兼容，新增层级字段）
├── 修改 /api/overview/* 端点（新增分类维度聚合）
└── 集成测试：新旧API输出对比

Phase 4: 前端适配 (Week 4-5)
├── 技能旭日图替换饼图
├── 岗位树形图
├── 行业分类筛选器
├── 能力雷达图
└── E2E测试

Phase 5: 持续优化 (Ongoing)
├── 分类自动化更新（新技能/岗位的半自动归类）
├── 社群检测结果与分类体系的交叉验证
├── 趋势分析增强（按分类层级的时间序列）
└── 与外部数据源（ESCO API, O*NET API）的自动同步
```

### 9.2 向后兼容策略

1. **Skill.category**: 保留旧字段值，新增 `domain_code`/`group_code`/`type_code` 字段。
2. **API兼容**：旧API端点输出增加 `tree` 字段（可选），旧 `categories` 字段保持不变。
3. **前端渐进式**：旧图表保留，新图表作为Tab切换展示。
4. **Cypher查询兼容**：所有基于 `s.category` 的查询增加基于新字段的备选查询逻辑。

### 9.3 分类自动化更新规则

新技能归类规则：
```
1. 通过关键字匹配预分类（正则规则表）
2. 通过LLM辅助分类（给定技能名+上下位技能，返回最可能的GRP）
3. 人工审核标记（confidence < 0.7 的归入 SKD-99，待审核）
```

新岗位归类规则：
```
1. 通过已规范化的岗位名与JobCategory的映射表精确匹配
2. 通过LLM语义匹配（给定岗位名称+JD摘要，匹配最可能的CAT-xxxx）
3. 置信度 < 0.7 的标记为 "待审核"，归入对应域的"其他"类别
```

---

## 10. 附录

### 10.1 编码体系约定

```
JobDomain:       DOM-01 ~ DOM-99
JobCategory:     CAT-{domain}{seq}  如 CAT-0101
SkillDomain:     SKD-01 ~ SKD-99
SkillGroup:      GRP-{domain}{seq}  如 GRP-0101
SkillType:       T-{group}{seq}      如 T-01011
IndustrySector:  GB/T 4754 门类字母 (A~T)
IndustryDivision: GB/T 4754 大类2位数字 (01~97)
IndustryGroup:   GB/T 4754 中类3位数字 (011~979)
AbilityDimension: ABL-01 ~ ABL-99
CompetencyCluster: CLS-{dim}{seq}   如 CLS-0101
Competency:      CMP-{cluster}{seq} 如 CMP-010101
```

### 10.2 CSV映射文件格式

**job_title_mapping.csv**:
```csv
raw_title,canonical_title,domain_code,domain_name,category_code,category_name,gb_code,esco_uri,confidence
"Java后端工程师",Java开发工程师,DOM-01,软件与算法开发,CAT-0101,后端开发,2-02-10-01,,1.0
"高级Java开发",Java开发工程师,DOM-01,软件与算法开发,CAT-0101,后端开发,2-02-10-01,,1.0
"AIGC产品经理",AIGC产品经理,DOM-04,产品与项目管理,CAT-0401,产品管理,,,0.85
```

**skill_category_mapping.csv**:
```csv
skill_name,old_category,domain_code,domain_name,group_code,group_name,type_code,type_name,esco_uri
Python,编程语言,SKD-01,编程语言与框架,GRP-0101,后端编程语言,T-01011,主要后端语言,
React,前端框架,SKD-01,编程语言与框架,GRP-0102,前端技术,T-01021,前端框架,
TensorFlow,AI框架,SKD-03,人工智能与机器学习,GRP-0301,AI/ML框架,T-03011,深度学习框架,
Kafka,消息队列,SKD-02,数据存储与管理,GRP-0204,消息队列与事件流,T-02041,消息队列,
```

**industry_mapping.csv**:
```csv
industry_name,sector_code,sector_name,division_code,division_name,group_code,group_name
互联网/IT,I,信息传输软件和信息技术服务业,64,互联网和相关服务,642,互联网信息服务
人工智能,I,信息传输软件和信息技术服务业,65,软件和信息技术服务业,659,其他信息技术服务业
人工智能(研究端),M,科学研究和技术服务业,73,研究和试验发展,,
通信/电子,C,制造业,39,计算机通信和其他电子设备制造业,392,通信设备制造
金融,J,金融业,66,货币金融服务,,
教育/培训,P,教育,83,教育,839,其他教育
```

### 10.3 文件清单

```
data/taxonomy/
├── TAXONOMY_DESIGN.md                 ← 本文档
├── job_title_mapping.csv              ← 383+ 条岗位→域/类别映射
├── skill_category_mapping.csv         ← 200+ 条技能→域/组/类型映射
├── industry_mapping.csv               ← 71 条行业→GB/T 4754映射
├── ability_mapping.csv                ← 能力初始种子数据
├── taxonomy_importer.py               ← 分类节点批量导入脚本
└── verify_taxonomy.py                 ← 分类覆盖率验证脚本
```

### 10.4 关键指标

| 指标 | 当前状态 | 目标状态 |
|------|---------|---------|
| 岗位分类覆盖率 | 0% (383个JobTitle无分类) | 100% (每个JobTitle映射到JobCategory) |
| 技能分类层级数 | 1层 (59扁平分类) | 3-4层 (域→组→类型→技能) |
| 单技能分类数 | 18个 | 0个 (全部归并) |
| 行业层级数 | 0 | 3层 (GB/T 4754) |
| 分类编码标准化 | 无 | 100% (GB/T + ESCO + O*NET) |
| 重名/歧义分类 | 2处 ("通信协议") | 0处 |
| 能力分类 | 无 | 5维度 × 12能力群 × ~40能力 |
| 教育有序化 | 无 | 6级有序整数 |
| 经验有序化 | 无 | 7级有序整数 + 年数范围 |

---

> **下一步**: 将本设计文档提交团队评审，确认分类颗粒度和命名约定后，进入 Phase 1 实施。
