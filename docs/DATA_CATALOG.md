# DATA CATALOG -- 数据资产全目录

> **项目**: 揭榜挂帅 -- 数据采集系统
> **更新日期**: 2026-07-15
> **覆盖范围**: MySQL (job_graph) + Neo4j (job-graph) + 文件资产 (caiji/data/, data_collection/)
> **采集时间窗口**: 2026-05-15 ~ 2026-05-16 (集中采集约14小时)

---

## 一、MySQL 数据库

### 1.1 数据库概览

| 属性 | 值 |
|---|---|
| 数据库名 | `job_graph` |
| MySQL 版本 | 8.0 |
| 字符集 / 排序规则 | `utf8mb4` / `utf8mb4_0900_ai_ci` |
| 引擎 | InnoDB |
| 表数量 | 1 |
| 总行数 | 1,188 |
| 数据大小 | 2.52 MB |
| 索引大小 | 1.42 MB |

### 1.2 数据资产清单

| 资产名称 | 类型 | 规模 | 活跃度 | 用途 |
|---|---|---|---|---|
| `job_records` | 主数据表 (InnoDB) | 1,188 行 \| 30 字段 \| 14 索引 | **活跃** | 统一岗位记录主表，汇集 recruitment / enterprise / academic / industry_report / policy 五类数据源，经 ETL 清洗去重归一化后写入 |

#### 表字段字典 (`job_records`)

| # | 字段名 | 类型 | 可空 | 说明 |
|---|---|---|---|---|
| 1 | `record_id` | varchar(36) | NOT NULL | UUID v4 主键，应用层生成 |
| 2 | `source_id` | varchar(255) | NOT NULL | 原始数据源 ID，用于去重溯源 |
| 3 | `source_type` | varchar(32) | NOT NULL | 来源大类 (recruitment/enterprise/academic/industry_report/policy) |
| 4 | `source_name` | varchar(128) | NOT NULL | 具体来源平台/站点名称 (17种) |
| 5 | `source_url` | varchar(2048) | NULL | 原始页面 URL |
| 6 | `job_title` | varchar(255) | NOT NULL | 归一化职位名称 |
| 7 | `job_title_raw` | varchar(255) | NULL | 原始采集职位名称 |
| 8 | `company_name` | varchar(255) | NOT NULL | 归一化公司/机构名称 |
| 9 | `company_name_raw` | varchar(255) | NULL | 原始采集公司名称 |
| 10 | `industry` | varchar(128) | NULL | 行业分类 (69种) |
| 11 | `location` | varchar(64) | NULL | 工作地点，城市-区县二级粒度 (170+) |
| 12 | `location_raw` | varchar(128) | NULL | 原始地点文本 |
| 13 | `job_description` | text | NOT NULL | 职位描述全文 |
| 14 | `salary_min` | float | NULL | 最低月薪 (千元) |
| 15 | `salary_max` | float | NULL | 最高月薪 (千元) |
| 16 | `experience_required` | varchar(64) | NULL | 经验要求 (32种表述，归一化不彻底) |
| 17 | `education_required` | varchar(64) | NULL | 学历要求 (7种) |
| 18 | `job_type` | varchar(32) | NULL | 工作类型 (覆盖极低，仅1.7%) |
| 19 | `skills_required` | json | NULL | 必备技能列表 (覆盖2.8%) |
| 20 | `skills_preferred` | json | NULL | 优先技能列表 (覆盖1.4%) |
| 21 | `abilities` | json | NULL | 综合能力标签 (覆盖2.8%) |
| 22 | `publish_date` | datetime | NULL | 原始发布日期 |
| 23 | `crawl_timestamp` | datetime | NOT NULL | 采集入库时间 |
| 24 | `data_format` | varchar(32) | NULL | 原始格式 (semi_structured / unstructured) |
| 25 | `quality_score` | float | NULL | 综合质量评分 (0~1, 均值 0.768) |
| 26 | `quality_grade` | varchar(2) | NULL | 质量等级 A/B/C/D (97.9% 为 B) |
| 27 | `completeness_score` | float | NULL | 信息完整度 (均值 0.857) |
| 28 | `freshness_score` | float | NULL | 信息新鲜度 (均值 0.503) |
| 29 | `consistency_score` | float | NULL | 信息一致性 (均值 0.999) |
| 30 | `extra` | json | NULL | 扩展字段 (platform, merged_sources, search_keyword) |

#### 索引清单

| 索引名 | 列 | 类型 | 活跃度 | 说明 |
|---|---|---|---|---|
| PRIMARY | `record_id` | 主键 | 活跃 | 行唯一标识 |
| `ix_job_records_source_type` | `source_type` | 普通 | 活跃 | 来源类型筛选 |
| `ix_job_records_job_title` | `job_title` | 普通 | 活跃 | 职位名搜索 |
| `ix_job_records_company_name` | `company_name` | 普通 | 活跃 | 公司名搜索 |
| `ix_job_records_industry` | `industry` | 普通 | 活跃 | 行业筛选 |
| `ix_job_records_location` | `location` | 普通 | 活跃 | 地点筛选 |
| `ix_job_records_quality_score` | `quality_score` | 普通 | 活跃 | 质量分排序 |
| `ix_job_records_publish_date` | `publish_date` | 普通 | 活跃 | 发布日期排序 |
| `ix_job_records_crawl_timestamp` | `crawl_timestamp` | 普通 | 活跃 | 抓取时间排序 |
| `idx_crawl_time` | `crawl_timestamp` | 普通 | **冗余** | 与 `ix_job_records_crawl_timestamp` 重复 |
| `idx_publish` | `publish_date` | 普通 | **冗余** | 与 `ix_job_records_publish_date` 重复 |
| `idx_title_company` | `(job_title, company_name)` | 复合 | 活跃 | 职位+公司联合查询 |
| `idx_source_type_name` | `(source_type, source_name)` | 复合 | 活跃 | 来源联合查询 |
| `idx_location_industry` | `(location, industry)` | 复合 | 活跃 | 地点+行业联合查询 |

#### 数据分布

| 维度 | 分布概况 |
|---|---|
| source_type | recruitment 1,167 (98.2%), enterprise 8 (0.7%), academic 5 (0.4%), industry_report 5 (0.4%), policy 3 (0.3%) |
| source_name | recruitment_multi 1,155, ArXiv 4, boss_zhipin 4, lagou 3, liepin 3, 51job 2, 其余10个来源各1-3条 |
| industry Top 5 | 计算机/IT 368, 通信/网络 112, 金融/银行 110, 制造 68, 专业咨询服务 66 |
| location Top 5 | 上海 263, 北京 143, 杭州 115, 深圳 90, 广州 51 |
| quality_grade | A 20 (1.7%), B 1,163 (97.9%), C 5 (0.4%), D 0 |
| education | 本科 638 (53.7%), 大专 335 (28.2%), 学历不限 132 (11.1%), 硕士 56, 博士 10, 高中 4 |
| 薪资 | 有薪资数据 1,139 (95.9%), 范围 1K~150K, 均值 15.87K~24.96K |

---

## 二、Neo4j 图谱

### 2.1 图谱概览

| 属性 | 值 |
|---|---|
| 数据库 | `neo4j` |
| 连接 | `bolt://localhost:7687` |
| 节点总数 | ~2,479 |
| 关系总数 | ~15,193 |
| 节点标签数 | 9 |
| 关系类型数 | 9 |

### 2.2 节点标签清单

| 资产名称 | 类型 | 规模 | 活跃度 | 用途 |
|---|---|---|---|---|
| `Job` | 核心实体节点 | 1,175 | **活跃** | 岗位节点，与 MySQL `job_records` 对应（差13条空 company_name 记录未导入）。通过 OFFERS / HAS_TITLE / REQUIRES / LOCATED_IN / BELONGS_TO / REQUIRES_EDUCATION / REQUIRES_EXPERIENCE 七种关系连接所有维度节点 |
| `Company` | 维度节点 | 520 | **活跃** | 公司/企业节点，含 `name` (唯一)、`industry` 属性。通过 OFFERS 关系提供岗位 |
| `JobTitle` | 词典节点 | 383 | **活跃** | 标准化岗位名称节点，含 `name` (唯一)。通过 HAS_TITLE 关系归类岗位 |
| `Skill` | 维度节点 | 128 | **活跃** | 技能节点，含 `name` (唯一)、`category` (51个分类) 属性。通过 REQUIRES (6,446条) 和 PREFERS (86条) 关联岗位。技能间有 CO_OCCURS_WITH (2,511条) 自环共现关系 |
| `City` | 维度节点 | 162 | **活跃** | 城市节点，含 `name` (唯一)、`province` 属性。覆盖17个省份。通过 LOCATED_IN 关联岗位 |
| `Industry` | 维度节点 | 71 | **活跃** | 行业分类节点，含 `name` (唯一)。通过 BELONGS_TO 关联岗位 |
| `Experience` | 枚举节点 | 31 | **活跃** | 经验要求节点，含 `name` (唯一)。32种表述直接映射，通过 REQUIRES_EXPERIENCE 关联岗位 |
| `Education` | 枚举节点 | 6 | **活跃** | 学历要求节点，含 `name` (唯一)。通过 REQUIRES_EDUCATION 关联岗位 |
| `EmergingJob` | 百科节点 | 3 | **历史** | 新兴岗位节点（Node.js开发工程师、鸿蒙开发工程师、数据科学家），含 `source`、`confidence`、`job_count` 等属性。**孤立节点**，无任何出入关系，源自 `discovered_jobs.json` |

### 2.3 关系类型清单

| 关系类型 | Source -> Target | 计数 | 活跃度 | 用途 |
|---|---|---|---|---|
| `OFFERS` | Company -> Job | 1,175 | **活跃** | 企业招聘岗位 |
| `HAS_TITLE` | Job -> JobTitle | 1,175 | **活跃** | 岗位归类 |
| `REQUIRES` | Job -> Skill | 6,446 | **活跃** | 岗位必备技能要求，平均每岗位 ~5.5 个技能 |
| `PREFERS` | Job -> Skill | 86 | **活跃** | 岗位优先/加分技能，含 `crawl_timestamp` 属性 |
| `LOCATED_IN` | Job -> City | 1,175 | **活跃** | 岗位工作地点 |
| `BELONGS_TO` | Job -> Industry | 1,175 | **活跃** | 岗位行业归属 |
| `REQUIRES_EDUCATION` | Job -> Education | 1,175 | **活跃** | 岗位学历要求 |
| `REQUIRES_EXPERIENCE` | Job -> Experience | 1,175 | **活跃** | 岗位经验要求 |
| `CO_OCCURS_WITH` | Skill -> Skill | 2,511 | **活跃** | 技能共现网络，用于技能推荐和岗位相似度计算 |

### 2.4 关键统计

| 指标 | 数值 |
|---|---|
| 平均每 Job 技能数 (REQUIRES) | ~5.5 |
| Top 5 技能 | MySQL (558), Linux (506), Git (460), Java (348), Redis (343) |
| 技能分类数 | 51 (AI框架、编程语言、数据库、云平台、前端框架...) |
| 城市覆盖 | 162 城市 / 17 省份 |
| 薪资范围 | 4K ~ 80K/月 |

---

## 三、文件数据资产

### 3.1 知识图谱相关文件

| 资产名称 | 类型 | 规模 | 活跃度 | 用途 |
|---|---|---|---|---|
| `caiji/data/kg_graph.json` | JSON 导出 | 2.0 MB | **可重新生成** | NetworkX 图结构完整导出 (节点+边)，可从 Neo4j 重新生成。建议加入 .gitignore |
| `caiji/data/kg_import.cypher` | Cypher 脚本 | 2.5 MB | **可重新生成** | Neo4j 导入脚本，含全部 MERGE/CREATE 语句。可从 GraphBuilder 重新生成。建议加入 .gitignore |
| `caiji/data/kg_analytics.json` | JSON 分析报告 | 48.3 KB | **可重新生成** | 图谱统计摘要 (节点/关系分布、技能热度 Top N)，可从 Neo4j 重新生成 |

### 3.2 RAG 向量存储

| 资产名称 | 类型 | 规模 | 活跃度 | 用途 |
|---|---|---|---|---|
| `caiji/data/chroma_db/chroma.sqlite3` | SQLite (向量库) | 184 KB | **活跃** | ChromaDB 持久化向量嵌入，配合 RAG 引擎使用。gitignored，运行时生成 |
| `caiji/data/rag_index.pkl` | Python Pickle | 1.1 MB | **冗余** | RAG 文档向量索引。**已从磁盘删除但仍被 Git 跟踪**。需 `git rm --cached` 清理 |

### 3.3 质量与发现

| 资产名称 | 类型 | 规模 | 活跃度 | 用途 |
|---|---|---|---|---|
| `caiji/data/accuracy_report.json` | JSON 报告 | 58.0 KB | **历史** | JD 技能提取准确度评估报告 (95 测试用例，含 precision/recall/F1) |
| `caiji/data/discovered_jobs.json` | JSON 配置 | 10.6 KB | **活跃** | AI 发现的新兴岗位定义 (EmergingJob 3 个节点的数据源) |
| `caiji/data/test_resume.txt` | 测试数据 | 506 B | **历史** | 合成测试简历 (张三，Python 开发，3年经验) |

### 3.4 图谱演化快照

| 资产名称 | 类型 | 规模 | 活跃度 | 用途 |
|---|---|---|---|---|
| `caiji/data/snapshots/*.json` (15文件) | JSON 时间序列 | ~1.1 MB | **活跃** | 知识图谱演化快照 (2025-06 ~ 2026-06)。其中 9 个标注 `simulated:true` 为模拟数据，6 个为真实采集数据。用于 evolution 模块时序对比 |
| `caiji/data/snapshots/snapshot_index.json` | JSON 索引 | 806 B | **活跃** | 快照清单索引。gitignored |
| `data/snapshots/*.json` (15文件) | JSON 时间序列 | ~1.1 MB | **冗余** | 与 `caiji/data/snapshots/` 完全重复 (仅缺少 2026-06-08_195556.json)。**建议删除** |

### 3.5 ETL 管道产物

| 资产名称 | 类型 | 规模 | 活跃度 | 用途 |
|---|---|---|---|---|
| `caiji/data/processed/` (27文件) | JSON/JSONL | ~18 MB | **历史** | 9批次 x 3阶段 (_raw.jsonl / .json / _final.jsonl) 的管道中间产物。数据已全部入库 MySQL，可安全清除 |
| `caiji/data/processed/*_recruitment_raw.jsonl` (9文件) | JSONL | ~18 MB (Git中) | **冗余** | 原始爬取数据。**已从磁盘删除但仍被 Git 跟踪**。需 `git rm --cached` |
| `data_collection/data/processed/` (7文件) | JSON/JSONL | ~588 KB | **废弃** | V1 原型管道 (2026-05-15 16:14-16:23) 的早期测试输出。已被 caiji V2 完全取代，可安全清除 |
| `data_collection/data/raw/` | 目录 | 空 | **废弃** | V1 原型原始数据目录，始终为空 |

### 3.6 运行时与上传

| 资产名称 | 类型 | 规模 | 活跃度 | 用途 |
|---|---|---|---|---|
| `caiji/data/uploads/` | 用户上传 | ~1.5 MB | **活跃** | Web 界面用户上传目录 (简历 PDF、JD 文件)，供 resume_parser 和 job_matcher 使用。gitignored |
| `data/fix_null_salaries_rollback.csv` | CSV 备份 | 3 KB | **历史** | fix_null_salaries.py 修复操作的回滚备份 |

---

## 四、数据流概览

### 4.1 管道阶段

```
Stage 1: Raw Crawl                  Stage 2: Processed              Stage 3: Final
─────────────────                   ─────────────────               ─────────────
*_recruitment_raw.jsonl (JSONL)     *.json (JSON Array)            *_final.jsonl (JSONL)
                                                                   (下游消费格式)
  - 原始爬取字段                      - 新增 quality_score          - 与 Stage 2 结构相同
  - skills_* 为空数组                 - 新增 quality_grade           - 仅格式从 Array 改为 Lines
  - 无质量评分                        - skills_* 已填充              - 供 KG Builder / Analytics 消费
  - 无 extra 扩展                     - extra 已填充
       │                                    │
       └── ETL清洗/去重/归一化 ──────────────┘
       └── 质量评估 ────────────────────────┘
       └── 技能提取(NLP) ──────────────────┘
```

### 4.2 下游消费

```
                         ┌──────────────────────┐
                         │   MySQL (job_graph)   │
                         │   job_records (1,188) │
                         └──────────┬───────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              │                     │                     │
     ┌────────▼────────┐   ┌───────▼───────┐   ┌────────▼────────┐
     │  Neo4j Graph    │   │  RAG Engine   │   │  Web Dashboard  │
     │  (2,479 nodes)  │   │  (ChromaDB +  │   │  (React SPA)    │
     │  (15,193 edges) │   │   rag_index)  │   │                 │
     └────────┬────────┘   └───────────────┘   └─────────────────┘
              │
     ┌────────▼────────┐
     │  Snapshots      │
     │  (时间序列演化)  │
     └─────────────────┘
```

### 4.3 完整批次编目

| Batch ID | Raw | Processed (.json) | Final (.jsonl) | Records | Source |
|---|---|---|---|---|---|
| 20260515_212724 | -- | 75.9 KB | 61.5 KB (demo) | 38 | 5-type mixed |
| 20260515_212853 | -- | 84.0 KB | 68.7 KB (demo) | 45 | 5-type mixed |
| 20260515_212914 | -- | 67.7 KB | 54.6 KB (demo) | 33 | 5-type mixed |
| 20260515_221204 | 841 KB (已删) | -- | -- | -- | recruitment |
| 20260515_221721 | 841 KB (已删) | -- | -- | -- | recruitment |
| 20260515_221723 | -- | 332.5 KB | 292.1 KB | 203 | recruitment |
| 20260515_224812 | 4.3 MB (已删) | 581.9 KB | 499.7 KB | 311 | recruitment |
| 20260516_090931 | 4.2 MB (已删) | 595.4 KB | 512.2 KB | 321 | recruitment |
| 20260516_094510 | 853 KB (已删) | 123.7 KB | 106.5 KB | 67 | recruitment |
| 20260516_101401 | 1.6 MB (已删) | 221.9 KB | 191.2 KB | 119 | recruitment |
| 20260516_104254 | 801 KB (已删) | 109.5 KB | 94.6 KB | 60 | recruitment |
| 20260516_105845 | 114 KB (已删) | 54.8 KB | 48.2 KB | 33 | recruitment |
| 20260516_113814 | 115 KB (已删) | 67.5 KB | 59.3 KB | 41 | recruitment |

---

## 五、数据拓扑图

```
                              ┌────────────────────────────────────────────┐
                              │              DATA TOPOLOGY                  │
                              │         揭榜挂帅 数据采集系统               │
                              └────────────────────────────────────────────┘

    ┌─────────────────────────────────────────────────────────────────────────────────────┐
    │                                 INGEST (采集层)                                      │
    │                                                                                      │
    │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐       │
    │  │ Boss直聘 │  │  拉勾网  │  │  猎聘网  │  │ 前程无忧 │  │ recruitment_multi│       │
    │  │  (4条)   │  │  (3条)   │  │  (3条)   │  │  (2条)   │  │    (1,155条)     │       │
    │  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────────┬─────────┘       │
    │       │             │             │             │               │                   │
    │  ┌────┴─────┐  ┌────┴─────┐  ┌────┴─────┐  ┌────┴─────────────────┴──────┐           │
    │  │ 企业官网 │  │ArXiv/SS  │  │ 研究院   │  │        政策文件              │           │
    │  │ (8条)    │  │ (5条)    │  │ (5条)    │  │        (3条)                │           │
    │  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────────────┬───────────────┘           │
    │       │             │             │                     │                            │
    └───────┼─────────────┼─────────────┼─────────────────────┼────────────────────────────┘
            │             │             │                     │
            └─────────────┴──────┬──────┴─────────────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │     ETL Pipeline         │
                    │  (清洗 → 去重 → 归一化)   │
                    │  (质量评估 → 技能提取)    │
                    └────────────┬────────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         │                       │                       │
┌────────▼────────┐   ┌──────────▼──────────┐   ┌───────▼────────┐
│    STORAGE      │   │    KNOWLEDGE GRAPH  │   │  FILE ASSETS   │
│    (MySQL)      │   │      (Neo4j)        │   │   (Disk/Git)   │
├─────────────────┤   ├─────────────────────┤   ├────────────────┤
│                 │   │                     │   │                │
│ job_graph DB    │   │ ┌─────────────────┐ │   │ caiji/data/    │
│                 │   │ │  Job (1175)     │ │   │ ├─ kg_graph    │
│ job_records     │   │ │  Company (520)  │ │   │ ├─ kg_import   │
│   1 table       │   │ │  JobTitle (383) │ │   │ ├─ kg_analytics│
│   1,188 rows    │   │ │  Skill (128)    │ │   │ ├─ rag_index*  │
│   30 columns    │   │ │  City (162)     │ │   │ ├─ chroma_db/  │
│   14 indexes    │◄──┼─┼─ Industry (71)  │ │   │ ├─ accuracy_   │
│                 │   │ │  Experience(31) │ │   │ │   report.json│
│  ┌───────────┐  │   │ │  Education (6)  │ │   │ ├─ discovered_ │
│  │ quality   │  │   │ │  EmergingJob(3) │ │   │ │   jobs.json  │
│  │ score:    │  │   │ └─────────────────┘ │   │ ├─ processed/  │
│  │ 均值0.768 │  │   │                     │   │ ├─ snapshots/  │
│  │ A:20 B:1163│  │   │ ┌─────────────────┐ │   │ └─ uploads/   │
│  │ C:5  D:0  │  │   │ │REQUIRES (6446)  │ │   │                │
│  └───────────┘  │   │ │CO_OCCURS(2511)  │ │   │ data_collection│
│                 │   │ │OFFERS (1175)    │ │   │ └─ processed/  │
│  数据量:2.52MB  │   │ │HAS_TITLE(1175)  │ │   │                │
│  索引:1.42MB    │   │ │LOCATED_IN(1175) │ │   │ data/snapshots│
│                 │   │ │BELONGS_TO(1175) │ │   │ (冗余副本)    │
└────────┬────────┘   │ │REQ_EDU (1175)   │ │   └────────────────┘
         │             │ │REQ_EXP (1175)   │ │
         │             │ │PREFERS (86)     │ │
         │             │ └─────────────────┘ │
         │             │  总计: 2,479 nodes  │
         │             │        15,193 edges │
         │             └─────────────────────┘
         │
┌────────▼────────┐
│  CONSUMPTION    │
│  (消费层)        │
├─────────────────┤
│ ┌─────────────┐ │
│ │ Web Dashboard│ │
│ │ (React SPA) │ │
│ │ ~759 MB     │ │
│ └─────────────┘ │
│ ┌─────────────┐ │
│ │ RAG Engine  │ │
│ │ ChromaDB +  │ │
│ │ rag_index   │ │
│ └─────────────┘ │
│ ┌─────────────┐ │
│ │ Snapshots   │ │
│ │ Evolution   │ │
│ │ Module      │ │
│ └─────────────┘ │
└──────────────────┘

    LEGEND:
    ────►  数据流向
    *       已删除但仍被Git跟踪
    (已删)  磁盘已删除
```

---

## 六、问题与建议

### 6.1 重复与可清理项

| 优先级 | 类别 | 资产 | 说明 | 建议操作 |
|---|---|---|---|---|
| **高** | 冗余数据 | `data/snapshots/` (15文件, ~1.1 MB) | 与 `caiji/data/snapshots/` 完全重复，仅少1个文件 | 确认活跃路径后删除非活跃副本 |
| **高** | 冗余索引 | `idx_crawl_time` (MySQL) | 与 `ix_job_records_crawl_timestamp` 功能完全重复 | `DROP INDEX idx_crawl_time ON job_records;` |
| **高** | 冗余索引 | `idx_publish` (MySQL) | 与 `ix_job_records_publish_date` 功能完全重复 | `DROP INDEX idx_publish ON job_records;` |
| **高** | Git 僵尸文件 | `rag_index.pkl` (1.1 MB) | 已从磁盘删除，仍被 Git 跟踪 | `git rm --cached caiji/data/rag_index.pkl` |
| **高** | Git 僵尸文件 | `*_recruitment_raw.jsonl` (9文件, ~18 MB) | 已从磁盘删除，仍被 Git 跟踪 | `git rm --cached caiji/data/processed/*_raw.jsonl` |
| **中** | 历史中间产物 | `caiji/data/processed/` (27文件, ~18 MB) | 全量数据已入库 MySQL，无查询价值 | 归档后清理 |
| **中** | 废弃代码产物 | `data_collection/data/processed/` (7文件, 588 KB) | V1 原型输出，已被 caiji V2 完全取代 | 归档后清理 |
| **中** | 模拟数据 | `caiji/data/snapshots/` 中 9 个 simulated 快照 | 标注 `simulated:true`，非真实采集数据 | 如仅需真实演化数据可删除 |
| **低** | 一次性别名 | `data/fix_null_salaries_rollback.csv` (3 KB) | 一次性修复的回滚备份 | 确认修复无问题后删除 |
| **低** | 生成物追踪 | `kg_graph.json` (2.0 MB) + `kg_import.cypher` (2.5 MB) | 可从 Neo4j 重新生成的产物，不应入 Git | 加入 .gitignore，`git rm --cached` |
| **低** | 路径不一致 | `settings.py` 中 `raw_data_dir=./data/raw` | 实际数据在 `caiji/data/` 下，`./data/raw` 为空 | 统一配置路径 |
| **低** | Neo4j 安装包 | `neo4j-community-5.26.0.zip` (~152 MB) | 解压目录已存在，安装包冗余 | 确认 Neo4j 正常后可删除 zip |

### 6.2 数据质量问题

| 优先级 | 问题 | 详情 | 建议 |
|---|---|---|---|
| **中** | MySQL vs Neo4j 行数不一致 | MySQL 1,188 vs Neo4j Job 1,175 (差13条)。13条恰为 `company_name` 为空的记录 | 确认导入过滤逻辑是预期行为还是 bug |
| **中** | 技能提取覆盖率极低 | skills_required 仅 2.8% 填充，skills_preferred 1.4%，abilities 2.8% | 大规模运行技能提取流水线 |
| **中** | 数据新鲜度衰减 | 集中采集距今已 2 个月，academic 源 freshness 仅 0.103，policy 源 0.271 | 建立增量采集机制 |
| **中** | 多源退化为单源 | recruitment 占 98.2%，enterprise/academic/policy/industry_report 合计不足 2% | 重新评估多源采集策略 |
| **低** | 经验要求未彻底归一化 | 32 种不同表述共存 (如 "3年以上" "2年以上" "5-10年" 混用) | 统一为标准区间 |
| **低** | quality_grade 区分度低 | 97.9% 集中在 B 级 | 调整评分阈值或细分 B 级 |
| **低** | job_type 覆盖率极低 | 仅 1.7% 记录有值 | 评估是否需要该字段或改进采集逻辑 |
| **低** | 单表设计 | 缺少企业维表、行业维表等辅助表 | 若查询复杂度增加可考虑拆分 |

---

## 附录：资产统计汇总

| 层级 | 资产数 | 总规模 | 活跃 | 历史 | 冗余/废弃 |
|---|---|---|---|---|---|
| MySQL | 1 表 + 14 索引 | 3.94 MB | 1 表 + 12 索引 | 0 | 2 索引 |
| Neo4j | 9 标签 + 9 关系 | 2,479 节点 + 15,193 边 | 8 标签 + 9 关系 | 1 标签 (EmergingJob) | 0 |
| 文件资产 | ~60 文件 | ~45 MB (含 Git 历史) | ~20 文件 | ~10 文件 | ~30 文件 |
| **合计** | ~84 资产 | ~50 MB (不含 Neo4j 存储) | -- | -- | -- |

---

> **维护说明**: 本目录应在每次数据采集完成后更新。新增数据表/节点标签/文件目录时，请同步更新对应的章节表格。标记为"冗余"或"可清理"的资产建议在下一个维护窗口集中处理。
