-- ============================================================================
-- 岗位能力分类体系 — MySQL 迁移脚本
-- ============================================================================
-- 版本：v1.1
-- 日期：2026-07-15
--
-- 执行前必须确保客户端字符集为 utf8mb4：
--   mysql -uroot -p --default-character-set=utf8mb4 <database> < this_file.sql
-- 基于：TAXONOMY_DESIGN.md
--
-- 用途：
--   1. 创建分类体系查找表（岗位域/类别、行业门类/大类/中类、
--      技能域/组/类型、教育/经验有序层级）
--   2. 为 job_records 表添加分类标注字段
--   3. 基于现有数据回填分类
--
-- 执行方式：
--   mysql -u<user> -p<password> --default-character-set=utf8mb4 <database> < taxonomy_mysql.sql
--
-- 重要提示：
--   - 本脚本设计为单次执行。若需重复执行（如开发/测试环境），
--     请先手动执行回滚脚本 taxonomy_mysql_rollback.sql 清理旧数据。
--   - ALTER TABLE ADD COLUMN 语句不可自动重入；如已执行过，
--     重复执行会报错，需手动跳过或先回滚。
--   - 若需仅重新执行种子数据部分（第三部分），可单独复制该段执行，
--     INSERT ... ON DUPLICATE KEY UPDATE 语句是幂等的。
--
-- 回滚：
--   见本文件末尾 "ROLLBACK" 节，或执行 taxonomy_mysql_rollback.sql。
-- ============================================================================

START TRANSACTION;


-- ============================================================================
-- 第一部分：创建分类体系查找表
-- ============================================================================

-- ---------------------------------------------------------------------------
-- 1.1 岗位职能域 (Job Domain) — 对应 TAXONOMY_DESIGN.md §2 第1层
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS taxonomy_job_domains (
    code         VARCHAR(8)   NOT NULL PRIMARY KEY COMMENT '编码，如 DOM-01',
    name         VARCHAR(64)  NOT NULL COMMENT '中文名称',
    name_en      VARCHAR(128) NOT NULL COMMENT '英文名称',
    description  TEXT         NULL     COMMENT '定义说明',
    gb_code      VARCHAR(32)  NULL     COMMENT 'GB/T 6565 映射编码',
    esco_uri     VARCHAR(256) NULL     COMMENT 'ESCO URI',
    sort_order   TINYINT      NOT NULL DEFAULT 0,
    created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_domain_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='岗位职能域 — 第1层分类 (GB/T 6565 大类/中类)';


-- ---------------------------------------------------------------------------
-- 1.2 岗位类别 (Job Category) — 对应 TAXONOMY_DESIGN.md §2 第2层
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS taxonomy_job_categories (
    code         VARCHAR(10)  NOT NULL PRIMARY KEY COMMENT '编码，如 CAT-0101',
    name         VARCHAR(64)  NOT NULL COMMENT '中文名称',
    name_en      VARCHAR(128) NOT NULL COMMENT '英文名称',
    domain_code  VARCHAR(8)   NOT NULL COMMENT '所属职能域编码',
    description  TEXT         NULL     COMMENT '定义说明',
    gb_code      VARCHAR(32)  NULL     COMMENT 'GB/T 6565 映射编码',
    esco_uri     VARCHAR(256) NULL     COMMENT 'ESCO URI',
    sort_order   TINYINT      NOT NULL DEFAULT 0,
    created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_category_name (name),
    INDEX idx_category_domain (domain_code),
    CONSTRAINT fk_category_domain FOREIGN KEY (domain_code)
        REFERENCES taxonomy_job_domains(code)
        ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='岗位类别 — 第2层分类 (岗位族)';


-- ---------------------------------------------------------------------------
-- 1.3 技能域 (Skill Domain) — 对应 TAXONOMY_DESIGN.md §3 第1层
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS taxonomy_skill_domains (
    code         VARCHAR(8)   NOT NULL PRIMARY KEY COMMENT '编码，如 SKD-01',
    name         VARCHAR(64)  NOT NULL COMMENT '中文名称',
    name_en      VARCHAR(128) NOT NULL COMMENT '英文名称',
    description  TEXT         NULL,
    esco_uri     VARCHAR(256) NULL     COMMENT 'ESCO skill pillar URI',
    sort_order   TINYINT      NOT NULL DEFAULT 0,
    created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_skill_domain_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='技能域 — 第1层分类 (ESCO skill pillar groups)';


-- ---------------------------------------------------------------------------
-- 1.4 技能组 (Skill Group) — 对应 TAXONOMY_DESIGN.md §3 第2层
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS taxonomy_skill_groups (
    code         VARCHAR(10)  NOT NULL PRIMARY KEY COMMENT '编码，如 GRP-0101',
    name         VARCHAR(64)  NOT NULL COMMENT '中文名称',
    name_en      VARCHAR(128) NOT NULL COMMENT '英文名称',
    domain_code  VARCHAR(8)   NOT NULL COMMENT '所属技能域编码',
    description  TEXT         NULL,
    esco_uri     VARCHAR(256) NULL,
    sort_order   TINYINT      NOT NULL DEFAULT 0,
    created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_skill_group_name (name),
    INDEX idx_skill_group_domain (domain_code),
    CONSTRAINT fk_skill_group_domain FOREIGN KEY (domain_code)
        REFERENCES taxonomy_skill_domains(code)
        ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='技能组 — 第2层分类 (技能功能集群)';


-- ---------------------------------------------------------------------------
-- 1.5 技能类型 (Skill Type) — 对应 TAXONOMY_DESIGN.md §3 第3层
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS taxonomy_skill_types (
    code         VARCHAR(12)  NOT NULL PRIMARY KEY COMMENT '编码，如 T-01011',
    name         VARCHAR(64)  NOT NULL COMMENT '中文名称',
    name_en      VARCHAR(128) NOT NULL COMMENT '英文名称',
    group_code   VARCHAR(10)  NOT NULL COMMENT '所属技能组编码',
    description  TEXT         NULL,
    esco_uri     VARCHAR(256) NULL,
    sort_order   TINYINT      NOT NULL DEFAULT 0,
    created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_skill_type_name (name),
    INDEX idx_skill_type_group (group_code),
    CONSTRAINT fk_skill_type_group FOREIGN KEY (group_code)
        REFERENCES taxonomy_skill_groups(code)
        ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='技能类型 — 第3层分类 (原59个分类的归并升级版)';


-- ---------------------------------------------------------------------------
-- 1.6 行业门类 (Industry Sector) — GB/T 4754 第1层
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS taxonomy_industry_sectors (
    code         VARCHAR(4)   NOT NULL PRIMARY KEY COMMENT '门类字母编码，如 I',
    name         VARCHAR(64)  NOT NULL COMMENT '门类中文名称',
    sort_order   TINYINT      NOT NULL DEFAULT 0,
    created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_sector_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='行业门类 — 第1层 (GB/T 4754-2017 门类 A~T)';


-- ---------------------------------------------------------------------------
-- 1.7 行业大类 (Industry Division) — GB/T 4754 第2层
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS taxonomy_industry_divisions (
    code         VARCHAR(4)   NOT NULL PRIMARY KEY COMMENT '大类2位数字编码，如 64',
    name         VARCHAR(64)  NOT NULL COMMENT '大类中文名称',
    sector_code  VARCHAR(4)   NOT NULL COMMENT '所属门类编码',
    sort_order   TINYINT      NOT NULL DEFAULT 0,
    created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_division_sector (sector_code),
    CONSTRAINT fk_division_sector FOREIGN KEY (sector_code)
        REFERENCES taxonomy_industry_sectors(code)
        ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='行业大类 — 第2层 (GB/T 4754-2017 2位数字)';


-- ---------------------------------------------------------------------------
-- 1.8 行业中类 (Industry Group) — GB/T 4754 第3层
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS taxonomy_industry_groups (
    code          VARCHAR(6)   NOT NULL PRIMARY KEY COMMENT '中类3位数字编码，如 645',
    name          VARCHAR(64)  NOT NULL COMMENT '中类中文名称',
    division_code VARCHAR(4)   NOT NULL COMMENT '所属大类编码',
    sort_order    TINYINT      NOT NULL DEFAULT 0,
    created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_group_division (division_code),
    CONSTRAINT fk_group_division FOREIGN KEY (division_code)
        REFERENCES taxonomy_industry_divisions(code)
        ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='行业中类 — 第3层 (GB/T 4754-2017 3位数字)';


-- ---------------------------------------------------------------------------
-- 1.9 教育层级查找表
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS taxonomy_education_levels (
    ordinal      TINYINT      NOT NULL PRIMARY KEY COMMENT '有序层级 0~6',
    name         VARCHAR(32)  NOT NULL COMMENT '学历名称',
    sort_order   TINYINT      NOT NULL DEFAULT 0,
    created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_education_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='教育层级有序化 — 对应 TAXONOMY_DESIGN.md §6.1';


-- ---------------------------------------------------------------------------
-- 1.10 经验层级查找表
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS taxonomy_experience_levels (
    ordinal      TINYINT      NOT NULL PRIMARY KEY COMMENT '有序层级 0~6',
    name         VARCHAR(32)  NOT NULL COMMENT '经验区间名称',
    min_years    FLOAT        NOT NULL DEFAULT 0 COMMENT '最小年数',
    max_years    FLOAT        NOT NULL DEFAULT 99 COMMENT '最大年数',
    sort_order   TINYINT      NOT NULL DEFAULT 0,
    created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_experience_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='经验层级有序化 — 对应 TAXONOMY_DESIGN.md §6.2';


-- ============================================================================
-- 第二部分：为 job_records 添加分类字段
-- ============================================================================

-- 注意：
--   以下 ALTER TABLE 语句不可自动重入。若重复执行本脚本，若字段已存在则会报错。
--   如需幂等执行，可在每条 ALTER TABLE 前使用存储过程检查列是否存在。
--   示例存储过程包装（取消注释后使用）：
--
-- DELIMITER //
-- CREATE PROCEDURE IF NOT EXISTS add_column_if_not_exists(
--     IN tbl VARCHAR(128), IN col VARCHAR(128), IN col_def TEXT
-- )
-- BEGIN
--     SET @col_exists = (SELECT COUNT(*) FROM information_schema.COLUMNS
--         WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = tbl AND COLUMN_NAME = col);
--     IF @col_exists = 0 THEN
--         SET @sql = CONCAT('ALTER TABLE ', tbl, ' ADD COLUMN ', col_def);
--         PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;
--     END IF;
-- END//
-- DELIMITER ;
--
-- 或直接执行 taxonomy_mysql_rollback.sql 回滚后再重新运行本脚本。

-- ---------------------------------------------------------------------------
-- 2.1 岗位分类字段
-- ---------------------------------------------------------------------------
ALTER TABLE job_records
    ADD COLUMN job_domain_code     VARCHAR(8)   NULL COMMENT '岗位职能域编码 (DOM-xx)'  AFTER job_title_raw,
    ADD COLUMN job_domain_name     VARCHAR(64)  NULL COMMENT '岗位职能域名称'            AFTER job_domain_code,
    ADD COLUMN job_category_code   VARCHAR(10)  NULL COMMENT '岗位类别编码 (CAT-xxxx)'   AFTER job_domain_name,
    ADD COLUMN job_category_name   VARCHAR(64)  NULL COMMENT '岗位类别名称'               AFTER job_category_code;

-- ---------------------------------------------------------------------------
-- 2.2 行业分类字段 (GB/T 4754)
-- ---------------------------------------------------------------------------
ALTER TABLE job_records
    ADD COLUMN industry_sector_code VARCHAR(4)   NULL COMMENT '行业门类编码'                                  AFTER industry,
    ADD COLUMN industry_sector_name VARCHAR(64)  NULL COMMENT '行业门类名称'                                  AFTER industry_sector_code,
    ADD COLUMN industry_division_code VARCHAR(4) NULL COMMENT '行业大类编码'                                  AFTER industry_sector_name,
    ADD COLUMN industry_division_name VARCHAR(64) NULL COMMENT '行业大类名称'                                 AFTER industry_division_code,
    ADD COLUMN industry_group_code  VARCHAR(6)   NULL COMMENT '行业中类编码'                                  AFTER industry_division_name,
    ADD COLUMN industry_group_name  VARCHAR(64)  NULL COMMENT '行业中类名称'                                  AFTER industry_group_code;

-- ---------------------------------------------------------------------------
-- 2.3 教育与经验有序化字段
-- ---------------------------------------------------------------------------
ALTER TABLE job_records
    ADD COLUMN education_ordinal    TINYINT      NULL COMMENT '教育有序层级 (0~6)'         AFTER education_required,
    ADD COLUMN experience_ordinal   TINYINT      NULL COMMENT '经验有序层级 (0~6)'         AFTER experience_required,
    ADD COLUMN experience_min_years FLOAT        NULL COMMENT '经验最低年数'               AFTER experience_ordinal,
    ADD COLUMN experience_max_years FLOAT        NULL COMMENT '经验最高年数'               AFTER experience_min_years;

-- ---------------------------------------------------------------------------
-- 2.4 索引
-- ---------------------------------------------------------------------------
CREATE INDEX idx_job_domain     ON job_records (job_domain_code);
CREATE INDEX idx_job_category   ON job_records (job_category_code);
CREATE INDEX idx_industry_sector ON job_records (industry_sector_code);
CREATE INDEX idx_education_ord  ON job_records (education_ordinal);
CREATE INDEX idx_experience_ord ON job_records (experience_ordinal);


-- ============================================================================
-- 第三部分：填充分类体系的种子数据
-- ============================================================================

-- ---------------------------------------------------------------------------
-- 3.1 岗位职能域 (7个，含 DOM-99 待分类)
-- ---------------------------------------------------------------------------
INSERT INTO taxonomy_job_domains (code, name, name_en, description, gb_code, sort_order) VALUES
('DOM-01', '软件与算法开发',        'Software & Algorithm Engineering',      '负责各类软件应用程序的设计、开发与维护。',           '2-02-10-01', 1),
('DOM-02', '数据与人工智能',         'Data & Artificial Intelligence',         '负责数据挖掘、AI模型研发、大数据工程与商业智能。',   '2-02-10-02', 2),
('DOM-03', '基础设施与运维',         'Infrastructure & Operations',            '负责IT基础设施、云平台与网络的建设、运维与可靠性。', '2-02-10-05', 3),
('DOM-04', '产品与项目管理',         'Product & Project Management',            '负责产品规划、项目管理与技术团队管理。',              '2-06-03-01', 4),
('DOM-05', '质量与安全',            'Quality & Security',                      '负责软件测试、质量保证与信息安全体系建设。',          '2-02-10-06', 5),
('DOM-06', '新兴与交叉技术',         'Emerging & Cross-disciplinary Tech',      '区块链、游戏开发、金融科技等新兴与交叉领域。',        NULL,         6),
('DOM-99', '待分类',                'Unclassified',                            '自动分类规则未命中的岗位，留待人工审核与归类。',      NULL,         99)
ON DUPLICATE KEY UPDATE
    name = VALUES(name),
    name_en = VALUES(name_en),
    description = VALUES(description),
    gb_code = VALUES(gb_code),
    sort_order = VALUES(sort_order);


-- ---------------------------------------------------------------------------
-- 3.2 岗位类别 (22个)
-- ---------------------------------------------------------------------------
INSERT INTO taxonomy_job_categories (code, name, name_en, domain_code, description, sort_order) VALUES
-- DOM-01 软件与算法开发
('CAT-0101', '后端开发',           'Backend Development',            'DOM-01', '负责服务端应用程序的设计、开发与维护。',                       1),
('CAT-0102', '前端与全栈开发',     'Frontend & Full-Stack',          'DOM-01', '负责Web前端界面开发及跨前后端的全流程开发。',                 2),
('CAT-0103', '移动开发',           'Mobile Development',             'DOM-01', '负责Android/iOS/跨平台移动端应用程序开发。',                  3),
('CAT-0104', '架构设计',           'Architecture',                   'DOM-01', '负责系统架构设计、技术选型与技术战略。',                       4),
('CAT-0105', '嵌入式与物联网开发', 'Embedded & IoT',                 'DOM-01', '面向硬件平台的固件、驱动及应用软件开发。',                    5),
('CAT-0106', '其他软件开发',       'Other Software Dev',             'DOM-01', '音视频、区块链开发等特定垂直方向的开发岗位。',               6),
-- DOM-02 数据与人工智能
('CAT-0201', '算法研究与AI模型',   'Algorithm Research & AI Modeling','DOM-02', '负责机器学习/深度学习模型的研究、设计、训练与优化。',         7),
('CAT-0202', 'AI工程化与应用',     'AI Engineering & Application',   'DOM-02', '将AI模型产品化、工程化部署与大模型应用开发。',               8),
('CAT-0203', '大数据工程',         'Big Data Engineering',           'DOM-02', '负责大数据平台建设、ETL、数据仓库设计与维护。',              9),
('CAT-0204', '数据分析与商业智能', 'Data Analysis & BI',             'DOM-02', '对业务数据进行分析、建模和可视化，为决策提供支撑。',         10),
-- DOM-03 基础设施与运维
('CAT-0301', '运维与站点可靠性',   'Operations & SRE',               'DOM-03', '负责生产环境运维、监控、故障处理与可用性保障。',             11),
('CAT-0302', '云计算与平台工程',   'Cloud & Platform Engineering',   'DOM-03', '负责云基础设施规划、云原生平台建设与自动化部署。',           12),
('CAT-0303', '网络与通信工程',     'Network & Communications',       'DOM-03', '负责企业网络架构、通信协议实现与网络设备管理。',             13),
-- DOM-04 产品与项目管理
('CAT-0401', '产品管理',           'Product Management',             'DOM-04', '负责产品规划、需求定义、用户研究与产品生命周期管理。',       14),
('CAT-0402', '项目管理',           'Project/Program Management',     'DOM-04', '负责项目计划、进度跟踪、风险管控与资源协调。',               15),
('CAT-0403', '技术管理',           'Engineering Management',         'DOM-04', '负责技术团队管理、技术战略规划与跨团队协调。',               16),
-- DOM-05 质量与安全
('CAT-0501', '测试与质量保证',     'Testing & QA',                   'DOM-05', '负责软件测试、缺陷管理与质量体系建设。',                     17),
('CAT-0502', '信息安全',           'Information Security',           'DOM-05', '负责信息安全体系建设、渗透测试与安全监控。',                 18),
-- DOM-06 新兴与交叉技术
('CAT-0601', '区块链与Web3',       'Blockchain & Web3',              'DOM-06', '负责区块链底层开发、智能合约编写与DApp开发。',              19),
('CAT-0602', '游戏开发',           'Game Development',               'DOM-06', '负责游戏客户端/服务端开发、引擎定制与渲染优化。',           20),
('CAT-0603', '金融科技',           'FinTech',                        'DOM-06', '负责量化交易系统、风控模型与金融技术交叉领域。',             21),
('CAT-0604', '其他新兴岗位',       'Other Emerging',                 'DOM-06', 'LLM/大模型驱动的新型岗位预留分类。',                          22)
ON DUPLICATE KEY UPDATE
    name = VALUES(name),
    name_en = VALUES(name_en),
    domain_code = VALUES(domain_code),
    description = VALUES(description),
    sort_order = VALUES(sort_order);


-- ---------------------------------------------------------------------------
-- 3.3 技能域 (8个)
-- ---------------------------------------------------------------------------
INSERT INTO taxonomy_skill_domains (code, name, name_en, sort_order) VALUES
('SKD-01', '编程语言与框架',          'Programming Languages & Frameworks',      1),
('SKD-02', '数据存储与管理',          'Data Storage & Management',               2),
('SKD-03', '人工智能与机器学习',      'Artificial Intelligence & Machine Learning', 3),
('SKD-04', '云计算与基础设施',        'Cloud & Infrastructure',                   4),
('SKD-05', 'DevOps与工程效能',        'DevOps & Engineering Productivity',         5),
('SKD-06', '测试、安全与质量',        'Testing, Security & Quality',              6),
('SKD-07', '业务、产品与软技能',      'Business, Product & Soft Skills',          7),
('SKD-99', '其他',                   'Uncategorized',                             99)
ON DUPLICATE KEY UPDATE
    name = VALUES(name),
    name_en = VALUES(name_en),
    sort_order = VALUES(sort_order);


-- ---------------------------------------------------------------------------
-- 3.4 技能组 (29个)
-- ---------------------------------------------------------------------------
INSERT INTO taxonomy_skill_groups (code, name, name_en, domain_code, sort_order) VALUES
-- SKD-01
('GRP-0101', '后端编程语言',      'Backend Languages',              'SKD-01', 1),
('GRP-0102', '前端技术',          'Frontend Technologies',          'SKD-01', 2),
('GRP-0103', '后端框架',          'Backend Frameworks',             'SKD-01', 3),
('GRP-0104', '移动开发技术',      'Mobile Development Technologies','SKD-01', 4),
('GRP-0105', '游戏与图形开发',    'Game & Graphics',                'SKD-01', 5),
-- SKD-02
('GRP-0201', '关系型数据库',      'Relational Databases',           'SKD-02', 1),
('GRP-0202', '非关系型数据库',    'NoSQL & Cache',                  'SKD-02', 2),
('GRP-0203', '大数据与流处理',    'Big Data & Stream Processing',   'SKD-02', 3),
('GRP-0204', '消息队列与事件流',  'Message Queues & Event Streaming','SKD-02', 4),
-- SKD-03
('GRP-0301', 'AI/ML框架',         'AI/ML Frameworks',               'SKD-03', 1),
('GRP-0302', 'AI/ML模型',         'AI/ML Models',                   'SKD-03', 2),
('GRP-0303', 'AI/ML应用领域',     'AI/ML Application Domains',      'SKD-03', 3),
('GRP-0304', 'AI/ML工程化',       'AI/ML Engineering',              'SKD-03', 4),
('GRP-0305', 'AI工具与库',        'AI Tools & Libraries',           'SKD-03', 5),
-- SKD-04
('GRP-0401', '云平台',            'Cloud Platforms',                'SKD-04', 1),
('GRP-0402', '容器与编排',        'Containers & Orchestration',     'SKD-04', 2),
('GRP-0403', '网络与通信',        'Networking & Communication',     'SKD-04', 3),
('GRP-0404', '系统与基础设施',    'Systems & Infra',                'SKD-04', 4),
-- SKD-05
('GRP-0501', 'CI/CD与构建',       'CI/CD & Build',                  'SKD-05', 1),
('GRP-0502', '可观测性与监控',    'Observability & Monitoring',     'SKD-05', 2),
('GRP-0503', '配置与基础设施即代码','Config & IaC',                 'SKD-05', 3),
-- SKD-06
('GRP-0601', '软件测试',          'Software Testing',               'SKD-06', 1),
('GRP-0602', '信息安全',          'Information Security',           'SKD-06', 2),
('GRP-0603', '代码与架构质量',    'Code & Architecture Quality',    'SKD-06', 3),
-- SKD-07
('GRP-0701', '产品与设计工具',    'Product & Design Tools',         'SKD-07', 1),
('GRP-0702', '数据分析与商业智能', 'Data Analysis & BI',            'SKD-07', 2),
('GRP-0703', '管理与方法论',      'Management & Methodologies',     'SKD-07', 3),
('GRP-0704', '产品能力',          'Product Capabilities',           'SKD-07', 4),
('GRP-0705', '架构与系统设计',    'Architecture & System Design',   'SKD-07', 5)
ON DUPLICATE KEY UPDATE
    name = VALUES(name),
    name_en = VALUES(name_en),
    domain_code = VALUES(domain_code),
    sort_order = VALUES(sort_order);


-- ---------------------------------------------------------------------------
-- 3.5 行业门类 (与数据相关的门类)
-- ---------------------------------------------------------------------------
INSERT INTO taxonomy_industry_sectors (code, name, sort_order) VALUES
('C', '制造业',                                1),
('I', '信息传输、软件和信息技术服务业',         2),
('J', '金融业',                                3),
('M', '科学研究和技术服务业',                   4),
('P', '教育',                                  5),
('Q', '卫生和社会工作',                         6),
('R', '文化、体育和娱乐业',                     7)
ON DUPLICATE KEY UPDATE
    name = VALUES(name),
    sort_order = VALUES(sort_order);


-- ---------------------------------------------------------------------------
-- 3.6 行业大类 (与数据相关)
-- ---------------------------------------------------------------------------
INSERT INTO taxonomy_industry_divisions (code, name, sector_code, sort_order) VALUES
('34', '通用设备制造业',               'C', 1),
('35', '专用设备制造业',               'C', 2),
('36', '汽车制造业',                   'C', 3),
('38', '电气机械和器材制造业',         'C', 4),
('39', '计算机、通信和其他电子设备制造业','C', 5),
('63', '电信、广播电视和卫星传输服务', 'I', 1),
('64', '互联网和相关服务',             'I', 2),
('65', '软件和信息技术服务业',         'I', 3),
('66', '货币金融服务',                 'J', 1),
('67', '资本市场服务',                 'J', 2),
('69', '其他金融业',                   'J', 3),
('73', '研究和试验发展',               'M', 1),
('83', '教育',                         'P', 1),
('84', '卫生',                         'Q', 1),
('86', '娱乐业',                       'R', 1)
ON DUPLICATE KEY UPDATE
    name = VALUES(name),
    sector_code = VALUES(sector_code),
    sort_order = VALUES(sort_order);


-- ---------------------------------------------------------------------------
-- 3.7 行业中类 (与数据相关)
-- ---------------------------------------------------------------------------
INSERT INTO taxonomy_industry_groups (code, name, division_code, sort_order) VALUES
('361', '汽车整车制造',         '36', 1),
('384', '电池制造',             '38', 1),
('391', '计算机制造',           '39', 1),
('392', '通信设备制造',         '39', 2),
('397', '电子器件制造',         '39', 3),
('631', '电信',                 '63', 1),
('642', '互联网信息服务',       '64', 1),
('643', '互联网平台',           '64', 2),
('645', '互联网数据服务',       '64', 3),
('651', '软件开发',             '65', 1),
('652', '集成电路设计',         '65', 2),
('654', '运行维护服务',         '65', 3),
('659', '其他信息技术服务业',   '65', 4),
-- J-66 货币金融服务 中类 (GB/T 4754-2017)
('661', '中央银行服务',         '66', 1),
('662', '货币银行服务',         '66', 2),
('663', '非货币银行服务',       '66', 3),
('664', '银行理财服务',         '66', 4),
('665', '银行监管服务',         '66', 5),
-- J-67 资本市场服务 中类
('671', '证券市场服务',         '67', 1),
('672', '期货市场服务',         '67', 2),
('673', '证券期货监管服务',     '67', 3),
('679', '其他资本市场服务',     '67', 4),
-- J-69 其他金融业 中类
('691', '金融信息服务',         '69', 1),
('699', '其他未列明金融业',     '69', 2),
-- 其他
('832', '高等教育',             '83', 1),
('839', '其他教育',             '83', 2),
('841', '医院',                 '84', 1),
('862', '数字内容服务',         '86', 1)
ON DUPLICATE KEY UPDATE
    name = VALUES(name),
    division_code = VALUES(division_code),
    sort_order = VALUES(sort_order);


-- ---------------------------------------------------------------------------
-- 3.8 教育层级
-- ---------------------------------------------------------------------------
INSERT INTO taxonomy_education_levels (ordinal, name, sort_order) VALUES
(0, '学历不限',         0),
(1, '高中/中专及以下',  1),
(2, '大专',             2),
(3, '本科',             3),
(4, '硕士',             4),
(5, '博士',             5),
(6, '博士后',           6)
ON DUPLICATE KEY UPDATE
    name = VALUES(name),
    sort_order = VALUES(sort_order);


-- ---------------------------------------------------------------------------
-- 3.9 经验层级
-- ---------------------------------------------------------------------------
INSERT INTO taxonomy_experience_levels (ordinal, name, min_years, max_years, sort_order) VALUES
(0, '经验不限',  0,  99, 0),
(1, '应届生',    0,   0, 1),
(2, '1年以下',   0,   1, 2),
(3, '1-3年',     1,   3, 3),
(4, '3-5年',     3,   5, 4),
(5, '5-10年',    5,  10, 5),
(6, '10年以上', 10,  99, 6)
ON DUPLICATE KEY UPDATE
    name = VALUES(name),
    min_years = VALUES(min_years),
    max_years = VALUES(max_years),
    sort_order = VALUES(sort_order);


-- ============================================================================
-- 第四部分：数据回填 — 基于现有数据推断分类
-- ============================================================================

-- ---------------------------------------------------------------------------
-- 4.1 岗位分类回填
-- ---------------------------------------------------------------------------
-- 策略：对 job_title 进行关键字匹配，按优先级分配。若匹配到多项，取最先匹配的分类。
-- 注意：MySQL 8.0 不支持 (?!...) 负向前瞻断言语法，所有排除逻辑已改用
--       "AND job_title NOT REGEXP '...'" 追加条件实现，保证语义等价。

-- 4.1.1 DOM-01 软件与算法开发

-- CAT-0101 后端开发: Java, Go, Golang, C++, C#, PHP, Rust, 后端, 服务端, .NET
-- 注意：Python 关键字匹配过宽，额外排除数据分析/测试/运维/AI 等岗位，
--       这些岗位会被后续 CAT-0204/CAT-0501/CAT-0301/CAT-0201/CAT-0202 匹配。
UPDATE job_records SET
    job_domain_code   = 'DOM-01',
    job_domain_name   = '软件与算法开发',
    job_category_code = 'CAT-0101',
    job_category_name = '后端开发'
WHERE job_domain_code IS NULL
  AND (
      (job_title REGEXP 'Java|Go(\\\\s|$|开发|语言)|Golang|C\\\\+\\\\+|C#|PHP|Rust|后端|服务端|\\\\.NET|Node\\\\.js.*后端')
      OR (job_title REGEXP 'Python' AND job_title NOT REGEXP '数据|分析|测试|运维|机器学习|AI|算法')
  );

-- CAT-0102 前端与全栈开发: 前端, Web前端, H5, 全栈, 页面, UI开发, 小程序(开发)
-- 排除: 前端 + 后端 同时出现（归入 全栈 或 后端）
UPDATE job_records SET
    job_domain_code   = 'DOM-01',
    job_domain_name   = '软件与算法开发',
    job_category_code = 'CAT-0102',
    job_category_name = '前端与全栈开发'
WHERE job_domain_code IS NULL
  AND (
      (job_title REGEXP '前端|页面' AND job_title NOT REGEXP '后端')
      OR job_title REGEXP 'Web前端|H5|全栈|HTML|CSS|小程序.*开发|跨端'
  );

-- CAT-0103 移动开发: Android, iOS, 移动端, 移动开发, Flutter, React Native, Swift, Kotlin(Android)
-- 排除: 移动端测试、Swift 测试
UPDATE job_records SET
    job_domain_code   = 'DOM-01',
    job_domain_name   = '软件与算法开发',
    job_category_code = 'CAT-0103',
    job_category_name = '移动开发'
WHERE job_domain_code IS NULL
  AND (
      (job_title REGEXP '移动端|Swift' AND job_title NOT REGEXP '测试')
      OR job_title REGEXP 'Android|iOS|移动开发|Flutter|React\\\\s*Native|Kotlin'
  );

-- CAT-0104 架构设计: 架构师, 系统架构, 解决方案架构, 技术总监(架构相关)
UPDATE job_records SET
    job_domain_code   = 'DOM-01',
    job_domain_name   = '软件与算法开发',
    job_category_code = 'CAT-0104',
    job_category_name = '架构设计'
WHERE job_domain_code IS NULL
  AND job_title REGEXP '架构师|系统架构|解决方案架构|架构专家';

-- CAT-0105 嵌入式与物联网开发: 嵌入式, 物联网, 驱动, MCU, FPGA, 单片机
-- 排除: 驱动测试
UPDATE job_records SET
    job_domain_code   = 'DOM-01',
    job_domain_name   = '软件与算法开发',
    job_category_code = 'CAT-0105',
    job_category_name = '嵌入式与物联网开发'
WHERE job_domain_code IS NULL
  AND (
      (job_title REGEXP '驱动' AND job_title NOT REGEXP '测试')
      OR job_title REGEXP '嵌入式|物联网|MCU|FPGA|单片机|固件'
  );

-- CAT-0106 其他软件开发: 音视频, 流媒体, RTMP, FFmpeg, 多媒体
UPDATE job_records SET
    job_domain_code   = 'DOM-01',
    job_domain_name   = '软件与算法开发',
    job_category_code = 'CAT-0106',
    job_category_name = '其他软件开发'
WHERE job_domain_code IS NULL
  AND job_title REGEXP '音视频|流媒体|RTMP|FFmpeg|多媒体';

-- 4.1.2 DOM-02 数据与人工智能

-- CAT-0201 算法研究与AI模型: 算法(非加密/非安全/非推荐), 机器学习(非工程), 深度学习, NLP, CV, 计算机视觉, 强化学习
UPDATE job_records SET
    job_domain_code   = 'DOM-02',
    job_domain_name   = '数据与人工智能',
    job_category_code = 'CAT-0201',
    job_category_name = '算法研究与AI模型'
WHERE job_domain_code IS NULL
  AND (
      (job_title REGEXP '算法' AND job_title NOT REGEXP '加密|安全|推荐')
      OR (job_title REGEXP '机器学习' AND job_title NOT REGEXP '工程')
      OR job_title REGEXP '深度学习|NLP|计算机视觉|CV(算法|工程|研究)|强化学习|知识图谱'
  );

-- CAT-0202 AI工程化与应用: 人工智能, AI(非标注/非训练), AIGC, 提示词, MLOps, 大模型
UPDATE job_records SET
    job_domain_code   = 'DOM-02',
    job_domain_name   = '数据与人工智能',
    job_category_code = 'CAT-0202',
    job_category_name = 'AI工程化与应用'
WHERE job_domain_code IS NULL
  AND (
      (job_title REGEXP '人工智能|AI' AND job_title NOT REGEXP '标注|训练')
      OR job_title REGEXP 'AIGC|提示词|Prompt|MLOps|大模型|LLM|ChatGPT|AGI'
  );

-- CAT-0203 大数据工程: 大数据, 数据仓库, 数据平台, ETL, Hadoop, Spark(非ML), Flink
UPDATE job_records SET
    job_domain_code   = 'DOM-02',
    job_domain_name   = '数据与人工智能',
    job_category_code = 'CAT-0203',
    job_category_name = '大数据工程'
WHERE job_domain_code IS NULL
  AND (
      (job_title REGEXP '大数据|Spark' AND job_title NOT REGEXP '分析|ML')
      OR job_title REGEXP '数据仓库|数据平台|ETL|Hadoop|Flink|数仓'
  );

-- CAT-0204 数据分析与商业智能: 数据分析, 数据科学, 商业分析, BI, 数据分析师
UPDATE job_records SET
    job_domain_code   = 'DOM-02',
    job_domain_name   = '数据与人工智能',
    job_category_code = 'CAT-0204',
    job_category_name = '数据分析与商业智能'
WHERE job_domain_code IS NULL
  AND job_title REGEXP '数据分析|数据科学|商业分析|BI(工程师|分析师)|数据挖掘|统计分析';

-- 4.1.3 DOM-03 基础设施与运维

-- CAT-0301 运维与站点可靠性: 运维, SRE, 系统管理员, 系统管理
-- 排除: 数据库运维, 大数据运维
UPDATE job_records SET
    job_domain_code   = 'DOM-03',
    job_domain_name   = '基础设施与运维',
    job_category_code = 'CAT-0301',
    job_category_name = '运维与站点可靠性'
WHERE job_domain_code IS NULL
  AND (
      (job_title REGEXP '运维|系统管理' AND job_title NOT REGEXP '数据库|大数据')
      OR (job_title REGEXP 'SRE' AND job_title NOT REGEXP '数据库')
  );

-- CAT-0302 云计算与平台工程: 云计算, 云平台, DevOps, 平台工程, K8s, Kubernetes
-- 排除: 数据平台
UPDATE job_records SET
    job_domain_code   = 'DOM-03',
    job_domain_name   = '基础设施与运维',
    job_category_code = 'CAT-0302',
    job_category_name = '云计算与平台工程'
WHERE job_domain_code IS NULL
  AND (
      (job_title REGEXP '平台工程' AND job_title NOT REGEXP '数据')
      OR job_title REGEXP '云计算|云平台|云原生|DevOps|K8s|Kubernetes|容器'
  );

-- CAT-0303 网络与通信工程: 网络, 通信
-- 排除: 通信协议开发、通信框架
UPDATE job_records SET
    job_domain_code   = 'DOM-03',
    job_domain_name   = '基础设施与运维',
    job_category_code = 'CAT-0303',
    job_category_name = '网络与通信工程'
WHERE job_domain_code IS NULL
  AND (
      (job_title REGEXP '通信' AND job_title NOT REGEXP '协议|框架')
      OR job_title REGEXP '网络工程师'
  );

-- 4.1.4 DOM-04 产品与项目管理

-- CAT-0401 产品管理: 产品经理, 产品总监, 产品VP
-- 排除: 产品开发、产品研发、产品测试、产品运营
UPDATE job_records SET
    job_domain_code   = 'DOM-04',
    job_domain_name   = '产品与项目管理',
    job_category_code = 'CAT-0401',
    job_category_name = '产品管理'
WHERE job_domain_code IS NULL
  AND (
      (job_title REGEXP '产品经理' AND job_title NOT REGEXP '开发|研发|测试|运营')
      OR job_title REGEXP '产品总监|产品VP|产品负责人|产品主管'
  );

-- CAT-0402 项目管理: 项目经理, Scrum, 敏捷教练, PMO
-- 排除: 技术项目经理、敏捷开发
UPDATE job_records SET
    job_domain_code   = 'DOM-04',
    job_domain_name   = '产品与项目管理',
    job_category_code = 'CAT-0402',
    job_category_name = '项目管理'
WHERE job_domain_code IS NULL
  AND (
      (job_title REGEXP '项目经理' AND job_title NOT REGEXP '技术')
      OR (job_title REGEXP '敏捷' AND job_title NOT REGEXP '开发')
      OR job_title REGEXP 'Scrum|PMO|项目主管|项目总监'
  );

-- CAT-0403 技术管理: 技术经理, 研发总监, 技术VP, CTO, 技术主管
UPDATE job_records SET
    job_domain_code   = 'DOM-04',
    job_domain_name   = '产品与项目管理',
    job_category_code = 'CAT-0403',
    job_category_name = '技术管理'
WHERE job_domain_code IS NULL
  AND job_title REGEXP '技术经理|研发总监|技术VP|CTO|技术主管|技术负责人|工程经理|技术总监';

-- 4.1.5 DOM-05 质量与安全

-- CAT-0501 测试与质量保证: 测试, QA, 质量
-- 排除: 安全测试、渗透测试
UPDATE job_records SET
    job_domain_code   = 'DOM-05',
    job_domain_name   = '质量与安全',
    job_category_code = 'CAT-0501',
    job_category_name = '测试与质量保证'
WHERE job_domain_code IS NULL
  AND (
      (job_title REGEXP '测试|QA' AND job_title NOT REGEXP '安全|渗透')
      OR job_title REGEXP '质量保证|质量工程'
  );

-- CAT-0502 信息安全: 安全, 渗透, 安全架构
-- 排除: 安全测试、质量安全
UPDATE job_records SET
    job_domain_code   = 'DOM-05',
    job_domain_name   = '质量与安全',
    job_category_code = 'CAT-0502',
    job_category_name = '信息安全'
WHERE job_domain_code IS NULL
  AND (
      (job_title REGEXP '安全' AND job_title NOT REGEXP '测试|质量')
      OR job_title REGEXP '渗透|安全架构|网络安全|信息安全|数据安全|安全工程'
  );

-- 4.1.6 DOM-06 新兴与交叉技术

-- CAT-0601 区块链与Web3
UPDATE job_records SET
    job_domain_code   = 'DOM-06',
    job_domain_name   = '新兴与交叉技术',
    job_category_code = 'CAT-0601',
    job_category_name = '区块链与Web3'
WHERE job_domain_code IS NULL
  AND job_title REGEXP '区块链|Web3|智能合约|DApp|NFT|DeFi';

-- CAT-0602 游戏开发: 游戏, Unity, Unreal
-- 排除: 游戏运营、游戏策划、游戏测试、游戏产品
UPDATE job_records SET
    job_domain_code   = 'DOM-06',
    job_domain_name   = '新兴与交叉技术',
    job_category_code = 'CAT-0602',
    job_category_name = '游戏开发'
WHERE job_domain_code IS NULL
  AND (
      (job_title REGEXP '游戏' AND job_title NOT REGEXP '运营|策划|测试|产品')
      OR job_title REGEXP 'Unity|Unreal|UE[45]|Cocos'
  );

-- CAT-0603 金融科技: 量化, 金融科技, FinTech
-- 排除: 量化分析
UPDATE job_records SET
    job_domain_code   = 'DOM-06',
    job_domain_name   = '新兴与交叉技术',
    job_category_code = 'CAT-0603',
    job_category_name = '金融科技'
WHERE job_domain_code IS NULL
  AND (
      (job_title REGEXP '量化' AND job_title NOT REGEXP '分析')
      OR (job_title REGEXP '风控模型' AND job_title NOT REGEXP '合规')
      OR job_title REGEXP '金融科技|FinTech|量化交易|量化策略'
  );

-- CAT-0604 其他新兴岗位: 数据标注, AI训练, AI伦理, 自动驾驶
UPDATE job_records SET
    job_domain_code   = 'DOM-06',
    job_domain_name   = '新兴与交叉技术',
    job_category_code = 'CAT-0604',
    job_category_name = '其他新兴岗位'
WHERE job_domain_code IS NULL
  AND job_title REGEXP '数据标注|AI训练|人工智能训练|自动驾驶|感知(算法|工程)|AI伦理|AI治理';

-- ---------------------------------------------------------------------------
-- 4.1.7 兜底 — 对仍未匹配的岗位，用更宽泛的规则尝试
-- ---------------------------------------------------------------------------

-- 包含"开发"、"工程师"但未匹配的 → DOM-01 CAT-0106
-- 排除: 开发测试
UPDATE job_records SET
    job_domain_code   = 'DOM-01',
    job_domain_name   = '软件与算法开发',
    job_category_code = 'CAT-0106',
    job_category_name = '其他软件开发'
WHERE job_domain_code IS NULL
  AND (
      (job_title REGEXP '开发' AND job_title NOT REGEXP '测试')
      OR job_title REGEXP '软件|程序员'
  );

-- 包含"数据"但未匹配的 → DOM-02 CAT-0204
-- 排除: 数据标注、数据库管理
UPDATE job_records SET
    job_domain_code   = 'DOM-02',
    job_domain_name   = '数据与人工智能',
    job_category_code = 'CAT-0204',
    job_category_name = '数据分析与商业智能'
WHERE job_domain_code IS NULL
  AND (
      job_title REGEXP '数据'
      AND job_title NOT REGEXP '标注|库'
  );

-- 包含"产品"但未匹配的 → DOM-04 CAT-0401
UPDATE job_records SET
    job_domain_code   = 'DOM-04',
    job_domain_name   = '产品与项目管理',
    job_category_code = 'CAT-0401',
    job_category_name = '产品管理'
WHERE job_domain_code IS NULL
  AND job_title REGEXP '产品';

-- ---------------------------------------------------------------------------
-- 注意：
--   以下为兜底逻辑。
--   将所有仍未匹配的岗位归入 DOM-06 CAT-0604 是不合理的，因为很多未匹配岗位
--   实际上属于传统或非技术岗位。
--   因此，不再使用此兜底逻辑，未匹配的岗位将保持 job_domain_code = NULL，
--   留待人工审核后手动归类。
--   若确实需要将所有未匹配岗位强制归入某个分类以便分析，可取消下面注释并执行：
--
-- UPDATE job_records SET
--     job_domain_code   = 'DOM-99',
--     job_domain_name   = '待分类',
--     job_category_code = NULL,
--     job_category_name = NULL
-- WHERE job_domain_code IS NULL
--   AND job_title IS NOT NULL
--   AND job_title != '';
-- ---------------------------------------------------------------------------


-- ---------------------------------------------------------------------------
-- 4.2 行业分类回填
-- ---------------------------------------------------------------------------
-- 策略：将现有 industry 字段的值映射到 GB/T 4754 标准分类。
-- 每个 UPDATE 匹配一个行业名称及其变体。

-- 互联网/IT → I-64-645 (互联网和相关服务 > 互联网数据服务/软件开发)
UPDATE job_records SET
    industry_code          = 'I-64-645',
    industry_sector_code   = 'I',
    industry_sector_name   = '信息传输、软件和信息技术服务业',
    industry_division_code = '64',
    industry_division_name = '互联网和相关服务',
    industry_group_code    = '645',
    industry_group_name    = '互联网数据服务'
WHERE industry_code IS NULL
  AND industry IN ('互联网/IT', '互联网', 'IT', 'IT/互联网', '移动互联网',
                   '互联网/电子商务', '计算机软件', '计算机服务');

-- 人工智能 → I-65-659 (软件和信息技术服务业 > 其他信息技术服务业)
UPDATE job_records SET
    industry_code          = 'I-65-659',
    industry_sector_code   = 'I',
    industry_sector_name   = '信息传输、软件和信息技术服务业',
    industry_division_code = '65',
    industry_division_name = '软件和信息技术服务业',
    industry_group_code    = '659',
    industry_group_name    = '其他信息技术服务业'
WHERE industry_code IS NULL
  AND industry IN ('人工智能', 'AI', 'AI/LLM', '大模型', '机器学习');

-- 通信/电子 → C-39-392 (计算机、通信和其他电子设备制造业 > 通信设备制造)
UPDATE job_records SET
    industry_code          = 'C-39-392',
    industry_sector_code   = 'C',
    industry_sector_name   = '制造业',
    industry_division_code = '39',
    industry_division_name = '计算机、通信和其他电子设备制造业',
    industry_group_code    = '392',
    industry_group_name    = '通信设备制造'
WHERE industry_code IS NULL
  AND industry IN ('通信/电子', '通信', '电子', '通信设备', '电子技术');

-- 金融 → J-66 (货币金融服务) — 使用中类 662 (货币银行服务) 作为默认
UPDATE job_records SET
    industry_code          = 'J-66-662',
    industry_sector_code   = 'J',
    industry_sector_name   = '金融业',
    industry_division_code = '66',
    industry_division_name = '货币金融服务',
    industry_group_code    = '662',
    industry_group_name    = '货币银行服务'
WHERE industry_code IS NULL
  AND industry IN ('金融', '银行', '证券', '保险', '基金', '投资');

-- 金融科技 → J-69 (其他金融业) — 使用中类 691 (金融信息服务)
UPDATE job_records SET
    industry_code          = 'J-69-691',
    industry_sector_code   = 'J',
    industry_sector_name   = '金融业',
    industry_division_code = '69',
    industry_division_name = '其他金融业',
    industry_group_code    = '691',
    industry_group_name    = '金融信息服务'
WHERE industry_code IS NULL
  AND industry IN ('金融科技', 'FinTech', '互联网金融');

-- 教育/培训 → P-83-839
UPDATE job_records SET
    industry_code          = 'P-83-839',
    industry_sector_code   = 'P',
    industry_sector_name   = '教育',
    industry_division_code = '83',
    industry_division_name = '教育',
    industry_group_code    = '839',
    industry_group_name    = '其他教育'
WHERE industry_code IS NULL
  AND industry IN ('教育/培训', '教育', '培训', '在线教育', 'K12', '职业教育');

-- 医疗健康 → Q-84-841
UPDATE job_records SET
    industry_code          = 'Q-84-841',
    industry_sector_code   = 'Q',
    industry_sector_name   = '卫生和社会工作',
    industry_division_code = '84',
    industry_division_name = '卫生',
    industry_group_code    = '841',
    industry_group_name    = '医院'
WHERE industry_code IS NULL
  AND industry IN ('医疗健康', '医疗', '医药', '健康', '生物医药', '医院');

-- 汽车/出行 → C-36-361
UPDATE job_records SET
    industry_code          = 'C-36-361',
    industry_sector_code   = 'C',
    industry_sector_name   = '制造业',
    industry_division_code = '36',
    industry_division_name = '汽车制造业',
    industry_group_code    = '361',
    industry_group_name    = '汽车整车制造'
WHERE industry_code IS NULL
  AND industry IN ('汽车/出行', '汽车', '出行', '新能源车', '智能汽车', '自动驾驶');

-- 电商/零售 → I-64-643 (互联网平台)
UPDATE job_records SET
    industry_code          = 'I-64-643',
    industry_sector_code   = 'I',
    industry_sector_name   = '信息传输、软件和信息技术服务业',
    industry_division_code = '64',
    industry_division_name = '互联网和相关服务',
    industry_group_code    = '643',
    industry_group_name    = '互联网平台'
WHERE industry_code IS NULL
  AND industry IN ('电商/零售', '电商', '电子商务', '零售', '新零售');

-- 游戏/娱乐 → R-86-862
UPDATE job_records SET
    industry_code          = 'R-86-862',
    industry_sector_code   = 'R',
    industry_sector_name   = '文化、体育和娱乐业',
    industry_division_code = '86',
    industry_division_name = '娱乐业',
    industry_group_code    = '862',
    industry_group_name    = '数字内容服务'
WHERE industry_code IS NULL
  AND industry IN ('游戏/娱乐', '游戏', '娱乐', '电竞', '动漫');

-- 半导体/集成电路 → C-39-397
UPDATE job_records SET
    industry_code          = 'C-39-397',
    industry_sector_code   = 'C',
    industry_sector_name   = '制造业',
    industry_division_code = '39',
    industry_division_name = '计算机、通信和其他电子设备制造业',
    industry_group_code    = '397',
    industry_group_name    = '电子器件制造'
WHERE industry_code IS NULL
  AND industry IN ('半导体/集成电路', '半导体', '芯片', '集成电路', 'IC设计');

-- 新能源 → C-38-384
UPDATE job_records SET
    industry_code          = 'C-38-384',
    industry_sector_code   = 'C',
    industry_sector_name   = '制造业',
    industry_division_code = '38',
    industry_division_name = '电气机械和器材制造业',
    industry_group_code    = '384',
    industry_group_name    = '电池制造'
WHERE industry_code IS NULL
  AND industry IN ('新能源', '光伏', '风电', '储能', '电池');

-- 智能制造 → C-35 (专用设备制造业)
UPDATE job_records SET
    industry_code          = 'C-35',
    industry_sector_code   = 'C',
    industry_sector_name   = '制造业',
    industry_division_code = '35',
    industry_division_name = '专用设备制造业',
    industry_group_code    = NULL,
    industry_group_name    = NULL
WHERE industry_code IS NULL
  AND industry IN ('智能制造', '工业自动化', '机器人', '工业互联网');

-- 广告/媒体 → I-64-642
UPDATE job_records SET
    industry_code          = 'I-64-642',
    industry_sector_code   = 'I',
    industry_sector_name   = '信息传输、软件和信息技术服务业',
    industry_division_code = '64',
    industry_division_name = '互联网和相关服务',
    industry_group_code    = '642',
    industry_group_name    = '互联网信息服务'
WHERE industry_code IS NULL
  AND industry IN ('广告/媒体', '广告', '媒体', '新媒体', '自媒体', '短视频', '直播');

-- 物流/供应链 → I-64-643 (平台经济相关)
UPDATE job_records SET
    industry_code          = 'I-64-643',
    industry_sector_code   = 'I',
    industry_sector_name   = '信息传输、软件和信息技术服务业',
    industry_division_code = '64',
    industry_division_name = '互联网和相关服务',
    industry_group_code    = '643',
    industry_group_name    = '互联网平台'
WHERE industry_code IS NULL
  AND industry IN ('物流/供应链', '物流', '供应链', '快递', '货运');

-- 房地产/建筑 → C-34 (通用设备制造业 — 偏工程)
UPDATE job_records SET
    industry_code          = 'C-34',
    industry_sector_code   = 'C',
    industry_sector_name   = '制造业',
    industry_division_code = '34',
    industry_division_name = '通用设备制造业',
    industry_group_code    = NULL,
    industry_group_name    = NULL
WHERE industry_code IS NULL
  AND industry IN ('房地产/建筑', '房地产', '建筑', '物业', '智慧城市');

-- 兜底 —— 所有仍有 industry 值但未匹配的记录
UPDATE job_records SET
    industry_sector_code   = 'I',
    industry_sector_name   = '信息传输、软件和信息技术服务业',
    industry_division_code = '65',
    industry_division_name = '软件和信息技术服务业',
    industry_group_code    = '659',
    industry_group_name    = '其他信息技术服务业',
    industry_code          = 'I-65-659'
WHERE industry_code IS NULL
  AND industry IS NOT NULL
  AND industry != ''
  AND industry != '不限'
  AND industry != '其他';


-- ---------------------------------------------------------------------------
-- 4.3 教育有序化回填
-- ---------------------------------------------------------------------------
UPDATE job_records SET education_ordinal = 0 WHERE education_required = '学历不限';
UPDATE job_records SET education_ordinal = 1 WHERE education_required IN (
    '高中/中专及以下', '高中及以上', '高中', '中专', '中技', '高中及以下', '高中以下');
UPDATE job_records SET education_ordinal = 2 WHERE education_required IN ('大专', '专科', '大专及以上');
UPDATE job_records SET education_ordinal = 3 WHERE education_required IN ('本科', '本科及以上', '统招本科', '大学本科');
UPDATE job_records SET education_ordinal = 4 WHERE education_required IN ('硕士', '硕士及以上', '研究生', '硕士研究生');
UPDATE job_records SET education_ordinal = 5 WHERE education_required IN ('博士', '博士及以上', '博士研究生');
UPDATE job_records SET education_ordinal = 6 WHERE education_required IN ('博士后');


-- ---------------------------------------------------------------------------
-- 4.4 经验有序化回填
-- ---------------------------------------------------------------------------

-- 经验不限
UPDATE job_records SET experience_ordinal = 0, experience_min_years = 0, experience_max_years = 99
WHERE experience_required IN ('经验不限', '不限经验', '不限');

-- 应届生
UPDATE job_records SET experience_ordinal = 1, experience_min_years = 0, experience_max_years = 0
WHERE experience_required IN ('应届生', '应届毕业生', '在校生', '实习生');

-- 1年以下
UPDATE job_records SET experience_ordinal = 2, experience_min_years = 0, experience_max_years = 1
WHERE experience_required IN ('1年以下', '一年以下', '1年以内');

-- 1-3年
-- 修复: "一年" 排除 "十一年"
UPDATE job_records SET experience_ordinal = 3, experience_min_years = 1, experience_max_years = 3
WHERE experience_required REGEXP '1-3|1~3|1-2|1~2'
   OR (experience_required REGEXP '一年' AND experience_required NOT REGEXP '十一');

-- 3-5年
-- 修复: "三年" 排除 "十三年"
UPDATE job_records SET experience_ordinal = 4, experience_min_years = 3, experience_max_years = 5
WHERE experience_ordinal IS NULL
  AND (experience_required REGEXP '3-5|3~5|3至5|2-5'
       OR (experience_required REGEXP '三年' AND experience_required NOT REGEXP '十三'));

-- 5-10年
-- 修复: "五年" 排除 "十五年", "八年" 排除 "十八年"
UPDATE job_records SET experience_ordinal = 5, experience_min_years = 5, experience_max_years = 10
WHERE experience_ordinal IS NULL
  AND (experience_required REGEXP '5-10|5~10|5至10'
       OR (experience_required REGEXP '五年' AND experience_required NOT REGEXP '十五')
       OR (experience_required REGEXP '八年' AND experience_required NOT REGEXP '十八'));

-- N年以上 (2-9年) — 补充匹配，防止遗漏
-- "2年以上" "3年以上" → ordinal 3 (1-3年, 保守归入)
UPDATE job_records SET experience_ordinal = 3, experience_min_years = 1, experience_max_years = 3
WHERE experience_ordinal IS NULL
  AND experience_required REGEXP '[2-3]年以上';

-- "4年以上" "5年以上" "6年以上" → ordinal 4 (3-5年)
UPDATE job_records SET experience_ordinal = 4, experience_min_years = 3, experience_max_years = 5
WHERE experience_ordinal IS NULL
  AND experience_required REGEXP '[4-6]年以上';

-- "7年以上" "8年以上" "9年以上" → ordinal 5 (5-10年)
UPDATE job_records SET experience_ordinal = 5, experience_min_years = 5, experience_max_years = 10
WHERE experience_ordinal IS NULL
  AND experience_required REGEXP '[7-9]年以上';

-- 10年以上
-- 修复: "十五年" "二十年" 等不会被前面的规则误匹配
UPDATE job_records SET experience_ordinal = 6, experience_min_years = 10, experience_max_years = 99
WHERE experience_ordinal IS NULL
  AND experience_required REGEXP '10年|[1-9][0-9]年|十年|二十年|十五年以上';

-- 兜底：解析包含数字的
UPDATE job_records SET experience_ordinal = 3, experience_min_years = 1, experience_max_years = 3
WHERE experience_ordinal IS NULL
  AND experience_required REGEXP '经验'
  AND experience_required IS NOT NULL
  AND experience_required != '';


-- ============================================================================
-- 第五部分：验证查询
-- ============================================================================

-- 说明：
--   以下查询用于 COMMIT 后手动验证数据质量，执行前需取消注释。
--   建议在每次迁移执行后依次运行这些查询，确认分类覆盖率和分布符合预期。

-- 验证 1：分类覆盖率
-- SELECT
--     COUNT(*)                                                                     AS total_job_records,
--     SUM(CASE WHEN job_domain_code   IS NOT NULL THEN 1 ELSE 0 END)               AS classified_jobs,
--     SUM(CASE WHEN industry_code     IS NOT NULL THEN 1 ELSE 0 END)               AS classified_industries,
--     SUM(CASE WHEN education_ordinal IS NOT NULL THEN 1 ELSE 0 END)               AS classified_education,
--     SUM(CASE WHEN experience_ordinal IS NOT NULL THEN 1 ELSE 0 END)              AS classified_experience,
--     ROUND(100.0 * SUM(CASE WHEN job_domain_code IS NOT NULL THEN 1 ELSE 0 END)
--           / COUNT(*), 1)                                                          AS job_coverage_pct
-- FROM job_records
-- WHERE job_title IS NOT NULL AND job_title != '';

-- 验证 2：各域岗位分布
-- SELECT
--     job_domain_code   AS domain_code,
--     job_domain_name   AS domain_name,
--     job_category_code AS category_code,
--     job_category_name AS category_name,
--     COUNT(*)          AS cnt
-- FROM job_records
-- WHERE job_domain_code IS NOT NULL
-- GROUP BY job_domain_code, job_domain_name, job_category_code, job_category_name
-- ORDER BY job_domain_code, cnt DESC;

-- 验证 3：未匹配的岗位（待人工审核）
-- SELECT DISTINCT job_title, job_title_raw
-- FROM job_records
-- WHERE job_domain_code IS NULL
--   AND job_title IS NOT NULL
--   AND job_title != ''
-- ORDER BY job_title
-- LIMIT 100;

-- 验证 4：行业分布
-- SELECT
--     industry_sector_code   AS s_code,
--     industry_sector_name   AS s_name,
--     industry_division_code AS d_code,
--     industry_division_name AS d_name,
--     industry_group_code    AS g_code,
--     industry_group_name    AS g_name,
--     COUNT(*)               AS cnt
-- FROM job_records
-- WHERE industry_sector_code IS NOT NULL
-- GROUP BY s_code, s_name, d_code, d_name, g_code, g_name
-- ORDER BY cnt DESC;

-- 验证 5：教育分布
-- SELECT education_ordinal, COUNT(*) AS cnt
-- FROM job_records
-- WHERE education_ordinal IS NOT NULL
-- GROUP BY education_ordinal
-- ORDER BY education_ordinal;

-- 验证 6：经验分布
-- SELECT experience_ordinal, COUNT(*) AS cnt
-- FROM job_records
-- WHERE experience_ordinal IS NOT NULL
-- GROUP BY experience_ordinal
-- ORDER BY experience_ordinal;


COMMIT;


-- ============================================================================
-- 回滚脚本 (单独执行)
-- ============================================================================
-- 若需回滚本次迁移，请执行以下语句（以事务包裹）。
-- 推荐直接执行 taxonomy_mysql_rollback.sql 独立文件，其中使用了 IF EXISTS 语法。
--
-- MySQL 8.0+ 支持 DROP COLUMN IF EXISTS 和 DROP INDEX IF EXISTS，
-- 下面使用该语法以保证可重复执行。

/*
START TRANSACTION;

-- 1. 删除分类字段
ALTER TABLE job_records
    DROP COLUMN IF EXISTS job_domain_code,
    DROP COLUMN IF EXISTS job_domain_name,
    DROP COLUMN IF EXISTS job_category_code,
    DROP COLUMN IF EXISTS job_category_name,
    DROP COLUMN IF EXISTS job_canonical_title,
    DROP COLUMN IF EXISTS industry_code,
    DROP COLUMN IF EXISTS industry_sector_code,
    DROP COLUMN IF EXISTS industry_sector_name,
    DROP COLUMN IF EXISTS industry_division_code,
    DROP COLUMN IF EXISTS industry_division_name,
    DROP COLUMN IF EXISTS industry_group_code,
    DROP COLUMN IF EXISTS industry_group_name,
    DROP COLUMN IF EXISTS education_ordinal,
    DROP COLUMN IF EXISTS experience_ordinal,
    DROP COLUMN IF EXISTS experience_min_years,
    DROP COLUMN IF EXISTS experience_max_years;

-- 2. 删除索引 (MySQL 8.0+ 支持 DROP INDEX IF EXISTS)
DROP INDEX IF EXISTS idx_job_domain     ON job_records;
DROP INDEX IF EXISTS idx_job_category   ON job_records;
DROP INDEX IF EXISTS idx_industry_sector ON job_records;
DROP INDEX IF EXISTS idx_education_ord  ON job_records;
DROP INDEX IF EXISTS idx_experience_ord ON job_records;

-- 3. 删除查找表
DROP TABLE IF EXISTS taxonomy_experience_levels;
DROP TABLE IF EXISTS taxonomy_education_levels;
DROP TABLE IF EXISTS taxonomy_industry_groups;
DROP TABLE IF EXISTS taxonomy_industry_divisions;
DROP TABLE IF EXISTS taxonomy_industry_sectors;
DROP TABLE IF EXISTS taxonomy_skill_types;
DROP TABLE IF EXISTS taxonomy_skill_groups;
DROP TABLE IF EXISTS taxonomy_skill_domains;
DROP TABLE IF EXISTS taxonomy_job_categories;
DROP TABLE IF EXISTS taxonomy_job_domains;

COMMIT;
*/
