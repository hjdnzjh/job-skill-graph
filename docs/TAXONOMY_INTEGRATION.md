# 岗位能力分类体系集成指南

> 版本：v1.0  
> 日期：2026-07-15  
> 前置文档：[TAXONOMY_DESIGN.md](./TAXONOMY_DESIGN.md)

---

## 目录

1. [执行顺序](#1-执行顺序)
2. [验证步骤](#2-验证步骤)
3. [API 改动清单](#3-api-改动清单)
4. [前端改动建议](#4-前端改动建议)
5. [回滚步骤](#5-回滚步骤)
6. [附录：文件清单](#6-附录文件清单)

---

## 1. 执行顺序

### 核心原则：先 MySQL 后 Neo4j

分类体系的数据流向是"MySQL (源记录) -> Neo4j (图谱)", 因此必须先完成关系型数据库的分类标注, 再将带标注的数据同步到图数据库。

```
Phase 1: 备份现有数据
  ├── mysqldump 全量备份 job_records 表
  └── neo4j-admin dump 备份图谱
      │
Phase 2: MySQL 迁移 (taxonomy_mysql.sql)
  ├── 创建 10 张分类查找表
  ├── 为 job_records 添加 17 个分类字段 + 5 个索引
  ├── 填充种子数据 (6+22+8+28+66 岗位/技能 等)
  ├── 基于关键字回填 job_records 分类
  └── 执行验证查询
      │
Phase 3: Neo4j 迁移 (taxonomy_neo4j.cypher)
  ├── 创建 12 个唯一约束 + 6 个索引
  ├── 导入 JobDomain / JobCategory / SkillDomain / SkillGroup / SkillType 等新标签节点
  ├── 创建 BELONGS_TO_* 层级关系
  ├── 回填现有节点属性 (JobTitle.domain_code, Skill.group_code 等)
  └── 执行验证查询
      │
Phase 4: API 层更新
  ├── 新增 /api/taxonomy/* 端点
  ├── 修改现有端点 (向后兼容)
  └── 集成测试
      │
Phase 5: 前端适配
  ├── 新增分类筛选组件
  ├── 升级图表 (旭日图 / 树图 / 桑基图)
  └── E2E 测试
```

### 1.1 详细执行命令

#### Step 1: 备份

```bash
# MySQL 备份
mysqldump -u<user> -p<password> <database> job_records > backup_job_records_$(date +%Y%m%d).sql

# Neo4j 备份 (需停止或使用在线备份)
neo4j-admin dump --database=neo4j --to=backup_neo4j_$(date +%Y%m%d).dump
```

#### Step 2: MySQL 迁移

```bash
mysql -u<user> -p<password> <database> < docs/migrations/taxonomy_mysql.sql
```

脚本结构（5 部分, 1066 行, 单事务）:

| 部分 | 内容 | 说明 |
|------|------|------|
| 一 | CREATE TABLE (10 张) | 分类查找表：岗位 2 + 技能 3 + 行业 3 + 教育 1 + 经验 1 |
| 二 | ALTER TABLE + INDEX | job_records 新增 17 字段 + 5 索引 |
| 三 | INSERT 种子数据 | 6DOM + 22CAT + 8SKD + 28GRP + 66 技能类型 + 行业/教育/经验 |
| 四 | UPDATE 回填 | 基于 REGEXP 关键字匹配, 按优先级回填分类 |
| 五 | 验证查询 (已注释) | 覆盖率、各域分布、未匹配记录、行业分布 |

#### Step 3: Neo4j 迁移

```bash
cypher-shell -u neo4j -p <password> -f docs/migrations/taxonomy_neo4j.cypher
```

脚本结构（8 部分, 1588 行, 全部用 MERGE 保证幂等）:

| 部分 | 内容 | 说明 |
|------|------|------|
| A | 约束 (12 UNIQUE) + 索引 (6) | 覆盖所有新标签的唯一码约束 |
| B | 岗位分类节点 | 6 JobDomain + 22 JobCategory + BELONGS_TO_DOMAIN 关系 |
| C | 技能分类节点 | 8 SkillDomain + 28 SkillGroup + 66 SkillType + 层级关系 |
| D | 行业分类节点 | 7 IndustrySector + 15 IndustryDivision + 17 IndustryGroup + 层级关系 |
| E | 能力分类节点 | 5 AbilityDimension + 12 CompetencyCluster + 40 Competency + 层级关系 |
| F | 教育/经验有序化 | 7 Education + 7 Experience 有序属性 |
| G | 现有节点属性回填 | JobTitle / Skill / Industry / Education / Experience 编码回填 |
| H | 跨体系关系 | 岗位-能力映射 (REQUIRES_COMPETENCY) |

---

## 2. 验证步骤

每个迁移执行后, 必须执行以下验证。**出现异常则中止后续步骤**。

### 2.1 MySQL 迁移后验证

#### 检查项 M1: 查找表数据完整性

```sql
-- 应返回：10 行, 每行 row_count 匹配预期值
SELECT 'taxonomy_job_domains'       AS table_name, COUNT(*) AS row_count, 6  AS expected FROM taxonomy_job_domains UNION ALL
SELECT 'taxonomy_job_categories',    COUNT(*), 22 FROM taxonomy_job_categories UNION ALL
SELECT 'taxonomy_skill_domains',     COUNT(*), 8  FROM taxonomy_skill_domains UNION ALL
SELECT 'taxonomy_skill_groups',      COUNT(*), 28 FROM taxonomy_skill_groups UNION ALL
SELECT 'taxonomy_skill_types',       COUNT(*), 66 FROM taxonomy_skill_types UNION ALL
SELECT 'taxonomy_industry_sectors',  COUNT(*), 7  FROM taxonomy_industry_sectors UNION ALL
SELECT 'taxonomy_industry_divisions',COUNT(*), 15 FROM taxonomy_industry_divisions UNION ALL
SELECT 'taxonomy_industry_groups',   COUNT(*), 17 FROM taxonomy_industry_groups UNION ALL
SELECT 'taxonomy_education_levels',  COUNT(*), 7  FROM taxonomy_education_levels UNION ALL
SELECT 'taxonomy_experience_levels', COUNT(*), 7  FROM taxonomy_experience_levels;
```

#### 检查项 M2: job_records 字段添加

```sql
-- 应返回 17 个新增字段
SELECT COLUMN_NAME, DATA_TYPE
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME = 'job_records'
  AND COLUMN_NAME IN ('job_domain_code','job_domain_name','job_category_code','job_category_name',
                      'job_canonical_title','industry_code','industry_sector_code','industry_sector_name',
                      'industry_division_code','industry_division_name','industry_group_code','industry_group_name',
                      'education_ordinal','experience_ordinal','experience_min_years','experience_max_years');
```

#### 检查项 M3: 索引创建

```sql
-- 应返回 5 行
SHOW INDEX FROM job_records WHERE Key_name IN (
    'idx_job_domain', 'idx_job_category', 'idx_industry_sector',
    'idx_education_ord', 'idx_experience_ord'
);
```

#### 检查项 M4: 岗位分类覆盖率

```sql
SELECT
    COUNT(*) AS total,
    SUM(CASE WHEN job_domain_code   IS NOT NULL THEN 1 ELSE 0 END) AS classified_domain,
    SUM(CASE WHEN job_category_code IS NOT NULL THEN 1 ELSE 0 END) AS classified_category,
    ROUND(100.0 * SUM(CASE WHEN job_category_code IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 1) AS coverage_pct
FROM job_records
WHERE job_title IS NOT NULL AND job_title != '';
-- 预期: coverage_pct >= 80%, 目标是 >= 95%
```

#### 检查项 M5: 行业分类覆盖率

```sql
SELECT
    COUNT(*) AS total_with_industry,
    SUM(CASE WHEN industry_sector_code IS NOT NULL THEN 1 ELSE 0 END) AS classified,
    ROUND(100.0 * SUM(CASE WHEN industry_sector_code IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 1) AS coverage_pct
FROM job_records
WHERE industry IS NOT NULL AND industry != '' AND industry != '不限';
-- 预期: coverage_pct >= 90%
```

#### 检查项 M6: 教育/经验有序化覆盖率

```sql
SELECT
    SUM(CASE WHEN education_ordinal  IS NOT NULL THEN 1 ELSE 0 END) AS edu_classified,
    SUM(CASE WHEN experience_ordinal IS NOT NULL THEN 1 ELSE 0 END) AS exp_classified
FROM job_records
WHERE education_required IS NOT NULL AND education_required != ''
   OR experience_required IS NOT NULL AND experience_required != '';
-- 预期: 两项均接近 100%
```

#### 检查项 M7: 外键完整性

```sql
-- 应返回 0 行 (没有孤立引用)
SELECT jr.job_category_code
FROM job_records jr
LEFT JOIN taxonomy_job_categories tjc ON jr.job_category_code = tjc.code
WHERE jr.job_category_code IS NOT NULL AND tjc.code IS NULL;
```

#### 检查项 M8: 各域岗位分布（合理性检查）

```sql
SELECT job_domain_code, job_domain_name, COUNT(*) AS cnt
FROM job_records
WHERE job_domain_code IS NOT NULL
GROUP BY job_domain_code, job_domain_name
ORDER BY cnt DESC;
-- 预期: 6 个域都有数据, DOM-01 (软件) 通常最多
```

### 2.2 Neo4j 迁移后验证

#### 检查项 N1: 新标签节点计数

```cypher
// 应依次返回: 6, 22, 8, 28, 66, 7, 15, 17, 5, 12, 40
MATCH (n:JobDomain)         RETURN 'JobDomain'         AS label, count(n) AS cnt UNION ALL
MATCH (n:JobCategory)       RETURN 'JobCategory'       AS label, count(n) AS cnt UNION ALL
MATCH (n:SkillDomain)       RETURN 'SkillDomain'       AS label, count(n) AS cnt UNION ALL
MATCH (n:SkillGroup)        RETURN 'SkillGroup'        AS label, count(n) AS cnt UNION ALL
MATCH (n:SkillType)         RETURN 'SkillType'         AS label, count(n) AS cnt UNION ALL
MATCH (n:IndustrySector)    RETURN 'IndustrySector'    AS label, count(n) AS cnt UNION ALL
MATCH (n:IndustryDivision)  RETURN 'IndustryDivision'  AS label, count(n) AS cnt UNION ALL
MATCH (n:IndustryGroup)     RETURN 'IndustryGroup'     AS label, count(n) AS cnt UNION ALL
MATCH (n:AbilityDimension)  RETURN 'AbilityDimension'  AS label, count(n) AS cnt UNION ALL
MATCH (n:CompetencyCluster) RETURN 'CompetencyCluster' AS label, count(n) AS cnt UNION ALL
MATCH (n:Competency)        RETURN 'Competency'        AS label, count(n) AS cnt;
```

#### 检查项 N2: 约束有效

```cypher
SHOW CONSTRAINTS;
// 预期: 至少 12 条 UNIQUE 约束 (根据 Neo4j 版本, 4.x 为 CREATE CONSTRAINT, 5.x 语法不同)
```

#### 检查项 N3: 索引有效

```cypher
SHOW INDEXES;
// 预期: 至少 6 条新索引 (job_title_domain_idx, job_title_category_idx, skill_domain_idx 等)
```

#### 检查项 N4: JobTitle 分类属性回填

```cypher
MATCH (t:JobTitle)
RETURN count(t) AS total,
       count(t.domain_code) AS with_domain,
       count(t.category_code) AS with_category,
       round(100.0 * count(t.domain_code) / count(t), 1) AS coverage_pct;
// 预期: coverage_pct >= 80%
```

#### 检查项 N5: Skill 分类属性回填

```cypher
MATCH (s:Skill)
RETURN count(s) AS total,
       count(s.domain_code) AS with_domain,
       count(s.group_code) AS with_group,
       round(100.0 * count(s.domain_code) / count(s), 1) AS coverage_pct;
// 预期: coverage_pct >= 95%
```

#### 检查项 N6: Industry 分类属性回填

```cypher
MATCH (i:Industry)
RETURN count(i) AS total,
       count(i.sector_code) AS with_sector,
       count(i.division_code) AS with_division,
       round(100.0 * count(i.sector_code) / count(i), 1) AS coverage_pct;
// 预期: coverage_pct >= 90%
```

#### 检查项 N7: 层级关系完整性

```cypher
// 岗位: JobCategory -> JobDomain (每个 Category 必须有 Domain)
MATCH (c:JobCategory) WHERE NOT (c)-[:BELONGS_TO_DOMAIN]->(:JobDomain) RETURN c.code AS orphan;
// 预期: 0 行

// 技能: SkillGroup -> SkillDomain
MATCH (g:SkillGroup) WHERE NOT (g)-[:BELONGS_TO_DOMAIN]->(:SkillDomain) RETURN g.code AS orphan;
// 预期: 0 行

// 技能: SkillType -> SkillGroup
MATCH (t:SkillType) WHERE NOT (t)-[:BELONGS_TO_GROUP]->(:SkillGroup) RETURN t.code AS orphan;
// 预期: 0 行

// 行业: IndustryGroup -> IndustryDivision
MATCH (g:IndustryGroup) WHERE NOT (g)-[:BELONGS_TO_DIVISION]->(:IndustryDivision) RETURN g.code AS orphan;
// 预期: 0 行
```

#### 检查项 N8: 无孤立节点

```cypher
// 检查 SkillDomain 下是否有 SkillGroup
MATCH (d:SkillDomain) WHERE NOT (d)<-[:BELONGS_TO_DOMAIN]-(:SkillGroup)
RETURN d.code AS empty_domain;
// 预期: 仅 SKD-99 (其他) 可能为空
```

### 2.3 API 层验证 (迁移后)

```bash
# 快速验证所有新增端点可访问
curl -s http://localhost:8000/api/taxonomy/job-tree    | python -m json.tool | head -20
curl -s http://localhost:8000/api/taxonomy/skill-tree  | python -m json.tool | head -20
curl -s http://localhost:8000/api/taxonomy/industry-tree | python -m json.tool | head -20
curl -s http://localhost:8000/api/taxonomy/ability-tree  | python -m json.tool | head -20
curl -s http://localhost:8000/api/skills/categories    | python -m json.tool | head -30

# 旧端点向后兼容验证
curl -s http://localhost:8000/api/skills/ranking?limit=5 | python -m json.tool
curl -s http://localhost:8000/api/overview               | python -m json.tool
```

---

## 3. API 改动清单

下面列出所有 13 个 `api_*.py` 文件所需的改动, 按影响程度排序。

### 3.1 需要新增端点的文件

#### `api_skills.py` — 影响程度: 高

**当前端点**:
- `GET /api/skills/ranking` — 返回平级技能排名
- `GET /api/skills/network` — 返回技能共现网络
- `GET /api/skills/communities` — 返回社群检测结果
- `GET /api/skills/categories` — 返回平级 59 类分组

**需要改动**:

1. **修改 `/api/skills/categories`** — 返回层级树而非平级列表
   - 新增 `parent_code` 字段, 使 API 返回从 59 个平级分类升级为 `SkillDomain > SkillGroup > SkillType` 三层嵌套结构
   - 向后兼容：增加可选参数 `?format=tree` (新) / `?format=flat` (旧, 默认)
   - 从 Neo4j 查询改为:
     ```cypher
     MATCH (d:SkillDomain)<-[:BELONGS_TO_DOMAIN]-(g:SkillGroup)
           <-[:BELONGS_TO_GROUP]-(t:SkillType)
     OPTIONAL MATCH (t)<-[:BELONGS_TO_TYPE]-(s:Skill)<-[:REQUIRES]-(:Job)
     RETURN d.code AS domain_code, d.name AS domain_name,
            g.code AS group_code, g.name AS group_name,
            t.code AS type_code, t.name AS type_name,
            collect(DISTINCT s.name) AS skills, count(DISTINCT s) AS skill_demand
     ORDER BY d.sort_order, g.sort_order, t.sort_order
     ```

2. **修改 `/api/skills/ranking`** — 新增 `domain_code` / `group_code` 筛选参数
   - 新增 Query 参数: `domain_code: Optional[str] = None`, `group_code: Optional[str] = None`
   - 返回新增: `domain_code`, `domain_name`, `group_code`, `group_name`, `type_code`

3. **修改 `/api/skills/network`** — 节点颜色按 `domain_code` 分组

4. **修改 `/api/skills/communities`** — 新增分类交叉验证字段

#### `api_overview.py` — 影响程度: 高

**当前端点**:
- `GET /api/overview` — 返回图谱 KPI
- `GET /api/emerging-jobs` — 返回新兴岗位

**需要改动**:

1. **修改 `GET /api/overview`** — 新增分类体系统计
   - 返回新增字段:
     ```json
     {
       "taxonomy": {
         "job_domains": 6,
         "job_categories": 22,
         "classified_job_titles": 350,
         "job_classification_coverage": 91.4,
         "skill_domains": 8,
         "skill_groups": 28,
         "industry_sectors": 7
       }
     }
     ```
   - Neo4j 查询新增:
     ```cypher
     MATCH (d:JobDomain) RETURN count(d)
     MATCH (c:JobCategory) RETURN count(c)
     MATCH (t:JobTitle) WHERE t.domain_code IS NOT NULL RETURN count(t)
     ```

2. **新增 `GET /api/overview/job-distribution`** (可选: 将现有岗位分布聚合逻辑独立)
   - 接受 Query 参数: `dimension = "domain" | "category" | "industry" | "education"`
   - 按指定维度聚合岗位数量

### 3.2 需要新增 taxonomy 专属端点的文件

**建议新建 `api_taxonomy.py`** — 专用于分类体系查询

```python
router = APIRouter(prefix="/api/taxonomy", tags=["taxonomy"])
```

| 端点 | 方法 | 说明 | 返回格式 |
|------|------|------|---------|
| `/api/taxonomy/job-tree` | GET | 岗位三层树形结构 (含岗位计数) | 嵌套 JSON tree |
| `/api/taxonomy/skill-tree` | GET | 技能四层树形结构 (含需求数) | 嵌套 JSON tree |
| `/api/taxonomy/industry-tree` | GET | 行业三层树形结构 | 嵌套 JSON tree |
| `/api/taxonomy/ability-tree` | GET | 能力三层树形结构 | 嵌套 JSON tree |
| `/api/taxonomy/cross-walk` | GET | 岗位-技能-行业交叉关联 | 关联矩阵 |
| `/api/taxonomy/education-levels` | GET | 教育有序层级列表 | 数组 |
| `/api/taxonomy/experience-levels` | GET | 经验有序层级列表 | 数组 |

响应格式参考 (来自 TAXONOMY_DESIGN.md Section 8.2):

```json
// GET /api/taxonomy/job-tree
{
  "tree": [
    {
      "code": "DOM-01",
      "name": "软件与算法开发",
      "name_en": "Software & Algorithm Engineering",
      "job_count": 1240,
      "children": [
        {
          "code": "CAT-0101",
          "name": "后端开发",
          "job_count": 520,
          "top_skills": ["Java", "Spring Boot", "MySQL", "Redis"],
          "children": [
            { "name": "Java开发工程师", "job_count": 205 },
            { "name": "Go开发工程师", "job_count": 87 }
          ]
        }
      ]
    }
  ]
}
```

### 3.3 需要中等改动的文件

#### `api_salary.py` — 影响程度: 中

**当前端点**:
- `GET /api/salary/by-title` — 按岗位薪资
- `GET /api/salary/by-city` — 按城市薪资

**需要改动**:

1. **新增 `GET /api/salary/by-domain`** — 按职能域聚合薪资
   ```cypher
   MATCH (j:Job)-[:HAS_TITLE]->(t:JobTitle)
   WHERE j.salary_min IS NOT NULL AND j.salary_max IS NOT NULL
     AND t.domain_code IS NOT NULL
   RETURN t.domain_code AS domain_code, t.domain_name AS domain_name,
          round(avg(j.salary_min), 1) AS avg_min,
          round(avg(j.salary_max), 1) AS avg_max,
          count(j) AS cnt
   ORDER BY cnt DESC
   ```

2. **修改 `/api/salary/by-title`** — 新增可选 `domain_code` / `category_code` 筛选参数

#### `api_distribution.py` — 影响程度: 中

**当前端点**:
- `GET /api/cities/distribution` — 城市分布
- `GET /api/industries/distribution` — 行业分布
- `GET /api/companies/distribution` — 公司分布

**需要改动**:

1. **新增 `GET /api/jobs/by-domain`** — 按岗位域聚合
2. **修改 `GET /api/industries/distribution`** — 新增层级字段, 支持 `?sector_code=I` 筛选
3. **新增 `GET /api/jobs/by-education`** — 教育层级分布
4. **新增 `GET /api/jobs/by-experience`** — 经验层级分布

#### `api_reports.py` — 影响程度: 中

**当前端点**:
- `GET /api/reports/overview` — 管理端综合概览
- `GET /api/reports/job-trends` — 岗位趋势
- `GET /api/reports/skill-trends` — 技能趋势
- `GET /api/reports/insights` — AI 洞察

**需要改动**:

1. **修改 `GET /api/reports/overview`** — 新增分类维度统计 (岗位域分布、技能域分布)
2. **修改 `GET /api/reports/job-trends`** — 支持 `?domain_code=DOM-01` 按域筛选
3. **修改 `GET /api/reports/skill-trends`** — 支持 `?domain_code=SKD-01` 按域筛选
4. **新增 `GET /api/reports/domain-growth`** — 各岗位域的增长趋势对比

#### `api_job_review.py` — 影响程度: 中

**当前端点**:
- `GET /api/jobs/pending` — 待审核岗位列表
- `POST /api/jobs/approve` — 审批通过
- `POST /api/jobs/reject` — 驳回
- `GET /api/jobs/{title}` — 岗位详情

**需要改动**:

1. **修改 `GET /api/jobs/pending`** — 返回新增 `domain_code`, `category_code` 字段, 新增 `?domain_code=` 筛选
2. **新增 `GET /api/jobs/unclassified`** — 列出未被分类覆盖的岗位 (待人工标注)
3. **修改 `POST /api/jobs/approve`** — 审批时自动分配分类编码

### 3.4 需要轻微改动的文件

#### `api_matching.py` — 影响程度: 低

**改动**: 匹配结果中新增 `target_domain` 和 `target_category` 字段, 让用户了解目标岗位所属分类。

#### `api_evolution.py` — 影响程度: 低

**改动**: `/api/evolution/compare` 结果新增按分类维度的聚合格差 (各域技能需求变化)。

#### `api_skill_manage.py` — 影响程度: 低

**改动**: `/api/skills/changes` 返回新增 `domain_code`, `group_code` 字段。

#### `api_graph_admin.py` — 影响程度: 低

**改动**: 新增对 JobDomain, JobCategory, SkillDomain 等新标签节点的 CRUD 支持 (默认已有, 检查 Schema 定义覆盖)。

#### `api_updater.py` — 影响程度: 极低

**改动**: 无结构变更, 仅确保新增分类字段不被覆盖。

#### `api_resume.py` — 影响程度: 极低

**改动**: 无结构变更, 简历评估结果可附带 `target_domain` 上下文信息。

#### `api_rag.py` — 影响程度: 极低

**改动**: 无结构变更, RAG 引擎可受益于分类知识自动丰富上下文 (非强制)。

### 3.5 API 改动汇总表

| 文件 | 改动类型 | 新增端点 | 修改端点 | 优先级 |
|------|---------|---------|---------|--------|
| `api_skills.py` | 高 | 0 | 4 (categories, ranking, network, communities) | P0 |
| `api_overview.py` | 高 | 1 | 1 (overview) | P0 |
| **`api_taxonomy.py` (新)** | 高 | 7 | 0 | P0 |
| `api_salary.py` | 中 | 1 | 1 (by-title) | P1 |
| `api_distribution.py` | 中 | 3 | 1 (industries) | P1 |
| `api_reports.py` | 中 | 1 | 3 (overview, job-trends, skill-trends) | P1 |
| `api_job_review.py` | 中 | 1 | 2 (pending, approve) | P1 |
| `api_matching.py` | 低 | 0 | 2 (match, recommend) | P2 |
| `api_evolution.py` | 低 | 0 | 1 (compare) | P2 |
| `api_skill_manage.py` | 低 | 0 | 1 (changes) | P2 |
| `api_graph_admin.py` | 低 | 0 | 0 (Schema 覆盖检查) | P2 |
| `api_updater.py` | 极低 | 0 | 0 | P3 |
| `api_resume.py` | 极低 | 0 | 0 | P3 |
| `api_rag.py` | 极低 | 0 | 0 | P3 |

---

## 4. 前端改动建议

### 4.1 新增 UI 组件

#### `TaxonomyFilter` — 分类筛选器（核心组件）

一个可复用的分类筛选控件, 支持级联选择。

```
Props:
  - type: "job" | "skill" | "industry"   // 分类体系类型
  - value: string[]                      // 已选 code 列表
  - onChange: (codes: string[]) => void
  - multiple: boolean                    // 是否多选
  - placeholder: string

Behavior:
  - 左列: 第1层(域), 点击展开第2层
  - 中列: 第2层(类别/组), 点击展开第3层
  - 右列: 第3层(具体实体列表 + 计数)
  - 每行显示: code 标签, 名称, 该层数据计数
  - 选中高亮 + Checkbox
```

**建议实现位置**: `caiji/web/spa/src/components/common/TaxonomyFilter.tsx`

**数据源**: 调用 `/api/taxonomy/job-tree` 和 `/api/taxonomy/skill-tree`

#### `TaxonomySunburst` / `TaxonomyTreemap` — 分类旭日图/树图

替换现有技能分布饼图 (基于 ECharts sunburst 或 treemap series)。

```
Props:
  - data: TaxonomyTreeNode               // 来自 /api/taxonomy/* 的树形数据
  - type: "job" | "skill" | "industry"
  - onDrillDown: (node: TreeNode) => void // 下钻回调
  - height: number

Behavior:
  - 多层环状旭日图, 从内到外: 域 -> 组 -> 类型 -> 具体
  - 悬停显示: 名称, 需求数, 占比
  - 点击内环下钻到子层
  - 面包屑导航显示当前层级路径
```

**建议实现位置**: `caiji/web/spa/src/components/charts/TaxonomySunburst.tsx`

#### `TaxonomySankey` — 分类交叉桑基图

展示岗位-行业-技能之间的关联流。

```
Props:
  - crosswalkData: CrossWalkData         // 来自 /api/taxonomy/cross-walk

Behavior:
  - 三列: 岗位域 | 行业门类 | 技能域
  - 连线粗细代表关联强度 (REQUIRES 关系数)
  - 悬停显示具体数值
```

**建议实现位置**: `caiji/web/spa/src/components/charts/TaxonomySankey.tsx`

### 4.2 各页面改动

#### B-end 管理端

| 页面 | 当前状态 | 集成后 | 改动点 |
|------|---------|--------|--------|
| **Dashboard** (`b-end/Dashboard.tsx`) | 4 个统计卡片 + 技能/岗位趋势图 | + 岗位域分布卡片 + 分类覆盖率进度条 | 在 stats 区域新增 "岗位分类覆盖率" 指标; 图表区域新增岗位域分布柱状图 |
| **SkillManage** (`b-end/SkillManage.tsx`) | 技能变更列表 | + TaxonomyFilter 筛选 + 按域/组分组 | 顶部新增分类筛选器; 列表项显示 domain_code 标签; 支持按技能域折叠 |
| **GraphManage** (`b-end/GraphManage.tsx`) | 图谱节点管理 | + 新增标签 Tab (JobDomain 等) | 左侧节点类型列表新增 12 个分类标签 |
| **JobReview** (`b-end/JobReview.tsx`) | 待审核岗位列表 | + domain_code/category_code 列 + 筛选 | 表格新增分类字段列; 顶部新增 TaxonomyFilter |
| **BatchMatch / QuickMatch** | 技能-岗位匹配 | + 目标岗位 domain 展示 | 匹配结果卡片新增所属域和类别 |
| **Reports** (`b-end/Reports.tsx`) | 趋势与洞察 | + 按域下钻的趋势对比 | 新增维度切换下拉框 |

#### C-end 用户端

| 页面 | 当前状态 | 集成后 | 改动点 |
|------|---------|--------|--------|
| **Home** (`c-end/Home.tsx`) | 全局概览 | + 岗位域热力分布 | 新增分类旭日图 (仅展示 1-2 层) |
| **SkillGraphPage** (`c-end/SkillGraphPage.tsx`) | 技能网络图 | + 节点颜色按 domain 着色 + sidebar 图例 | 节点颜色映射从 `domain_code`; 图例显示技能域中文名 |
| **NewJobs** (`c-end/NewJobs.tsx`) | 新兴岗位 | + "所属域"标签 | 每个新兴岗位卡片新增领域标签 (Badge) |
| **Profile** | 个人能力画像 | + 能力雷达图引用分类维度 | 雷达图可用 5 大能力维度 (ABL-01 ~ ABL-05) 做参考线 |
| **ResumeEvaluate** | 简历评估 | + 岗位分类上下文 | 匹配结果附带分类信息 |
| **RAGChat** | 智能问答 | 无直接改动 | 问答可能引用分类知识(后端处理) |

### 4.3 前端 API 服务层改动

**文件**: `caiji/web/spa/src/services/api.ts`

新增接口定义:

```typescript
// ── Taxonomy ──
export interface TaxonomyNode {
  code: string;
  name: string;
  name_en?: string;
  job_count?: number;
  total_demand?: number;
  top_skills?: string[];
  children?: TaxonomyNode[];
}

export const getJobTree = () =>
  request<{ tree: TaxonomyNode[] }>('/taxonomy/job-tree');

export const getSkillTree = () =>
  request<{ tree: TaxonomyNode[] }>('/taxonomy/skill-tree');

export const getIndustryTree = () =>
  request<{ tree: TaxonomyNode[] }>('/taxonomy/industry-tree');

export const getAbilityTree = () =>
  request<{ tree: TaxonomyNode[] }>('/taxonomy/ability-tree');

export const getCrosswalk = (params?: { dimension?: string }) =>
  request<any>('/taxonomy/cross-walk?' + new URLSearchParams(params));

export const getEducationLevels = () =>
  request<{ levels: { ordinal: number; name: string }[] }>('/taxonomy/education-levels');

export const getExperienceLevels = () =>
  request<{ levels: { ordinal: number; name: string; min_years: number; max_years: number }[] }>('/taxonomy/experience-levels');
```

修改现有接口:

```typescript
// SkillRank 新增字段
export interface SkillRank {
  name: string;
  category: string;
  domain_code?: string;
  domain_name?: string;
  group_code?: string;
  group_name?: string;
  type_code?: string;
  demand: number;
}

// getSkillRanking 新增参数
export const getSkillRanking = (limit = 30, domainCode?: string, groupCode?: string) => {
  const params = new URLSearchParams({ limit: String(limit) });
  if (domainCode) params.set('domain_code', domainCode);
  if (groupCode) params.set('group_code', groupCode);
  return request<{ skills: SkillRank[] }>(`/skills/ranking?${params}`);
};
```

### 4.4 图表组件升级路线

```
当前                      过渡期 (并存)               目标
──────────────────────────────────────────────────────────
技能饼图 (59 平级)  ──→  饼图 + 旭日图 Tab 切换  ──→  技能旭日图 (4 层)
岗位标签列表        ──→  标签云 + 树图 Tab        ──→  岗位树图 (treemap)
行业柱状图          ──→  柱状图 + 树图 Tab        ──→  行业树图 (treemap)
无                  ──→  桑基图新增               ──→  分类交叉桑基图
```

---

## 5. 回滚步骤

如果迁移后发现问题需回滚, 按以下步骤操作。

### 5.1 回滚原则

- **逆序执行**: 先回滚 Neo4j, 再回滚 MySQL
- **先验证**: 回滚前确认备份可用
- **保留数据**: 回滚只删除迁移新增的结构, 不删除原始业务数据

### 5.2 Neo4j 回滚

```cypher
// 步骤 1: 删除通过 Section G 回填的属性 (恢复 NULL)
MATCH (t:JobTitle)
REMOVE t.domain_code, t.domain_name, t.category_code, t.category_name,
       t.gb_code, t.esco_uri, t.onet_code;

MATCH (s:Skill)
REMOVE s.domain_code, s.domain_name, s.group_code, s.group_name,
       s.type_code, s.type_name, s.esco_uri, s.proficiency_levels;

MATCH (i:Industry)
REMOVE i.code, i.sector_code, i.sector_name,
       i.division_code, i.division_name, i.group_code, i.group_name;

MATCH (e:Education)
REMOVE e.ordinal;

MATCH (x:Experience)
REMOVE x.ordinal, x.min_years, x.max_years;

// 步骤 2: 删除分类层级关系
MATCH ()-[r:BELONGS_TO_CATEGORY]->() DELETE r;
MATCH ()-[r:BELONGS_TO_DOMAIN]->() DELETE r;
MATCH ()-[r:BELONGS_TO_TYPE]->() DELETE r;
MATCH ()-[r:BELONGS_TO_GROUP]->() DELETE r;
MATCH ()-[r:BELONGS_TO_SECTOR]->() DELETE r;
MATCH ()-[r:BELONGS_TO_DIVISION]->() DELETE r;
MATCH ()-[r:REQUIRES_COMPETENCY]->() DELETE r;
MATCH ()-[r:BELONGS_TO_CLUSTER]->() DELETE r;
MATCH ()-[r:BELONGS_TO_DIMENSION]->() DELETE r;

// 步骤 3: 删除分类节点
MATCH (n:Competency)        DELETE n;
MATCH (n:CompetencyCluster) DELETE n;
MATCH (n:AbilityDimension)  DELETE n;
MATCH (n:IndustryGroup)     DELETE n;
MATCH (n:IndustryDivision)  DELETE n;
MATCH (n:IndustrySector)    DELETE n;
MATCH (n:SkillType)         DELETE n;
MATCH (n:SkillGroup)        DELETE n;
MATCH (n:SkillDomain)       DELETE n;
MATCH (n:JobCategory)       DELETE n;
MATCH (n:JobDomain)         DELETE n;

// 步骤 4: 删除约束与索引 (使用 SHOW CONSTRAINTS / SHOW INDEXES 获取名称)
DROP CONSTRAINT job_domain_code_unique      IF EXISTS;
DROP CONSTRAINT job_category_code_unique    IF EXISTS;
DROP CONSTRAINT skill_domain_code_unique    IF EXISTS;
DROP CONSTRAINT skill_group_code_unique     IF EXISTS;
DROP CONSTRAINT skill_type_code_unique      IF EXISTS;
DROP CONSTRAINT industry_sector_code_unique IF EXISTS;
DROP CONSTRAINT industry_division_code_unique IF EXISTS;
DROP CONSTRAINT industry_group_code_unique  IF EXISTS;
DROP CONSTRAINT ability_dimension_code_unique IF EXISTS;
DROP CONSTRAINT competency_cluster_code_unique IF EXISTS;
DROP CONSTRAINT competency_code_unique      IF EXISTS;

DROP INDEX job_title_domain_idx   IF EXISTS;
DROP INDEX job_title_category_idx IF EXISTS;
DROP INDEX skill_domain_idx       IF EXISTS;
DROP INDEX skill_group_idx        IF EXISTS;
DROP INDEX industry_sector_idx    IF EXISTS;
DROP INDEX industry_division_idx  IF EXISTS;
```

### 5.3 MySQL 回滚

执行预置的回滚脚本:

```bash
mysql -u<user> -p<password> <database> < docs/migrations/taxonomy_mysql_rollback.sql
```

回滚脚本内容 (61 行, 单事务):

1. `ALTER TABLE job_records DROP COLUMN` (删除 17 个分类字段)
2. `DROP INDEX` (删除 5 个分类索引)
3. `DROP TABLE IF EXISTS` (删除 10 张查找表, 按依赖逆序)

### 5.4 回滚后验证

```sql
-- 确认 job_records 表结构已恢复
DESCRIBE job_records;
-- 预期: 不含 job_domain_code 等 17 个分类字段

-- 确认查找表已删除
SHOW TABLES LIKE 'taxonomy_%';
-- 预期: Empty set

-- 确认索引已删除
SHOW INDEX FROM job_records WHERE Key_name LIKE 'idx_job_%'
                                OR Key_name LIKE 'idx_industry_%'
                                OR Key_name LIKE 'idx_education_%'
                                OR Key_name LIKE 'idx_experience_%';
-- 预期: Empty set
```

```cypher
// 确认 Neo4j 新标签节点已删除
MATCH (n:JobDomain) RETURN count(n);  // 预期: 0
MATCH (n:SkillDomain) RETURN count(n); // 预期: 0

// 确认原节点属性已清除
MATCH (t:JobTitle) RETURN t.domain_code LIMIT 1;  // 预期: NULL

// 确认原业务数据完整
MATCH (j:Job) RETURN count(j);   // 应与回滚前一致
MATCH (s:Skill) RETURN count(s); // 应与回滚前一致
```

### 5.5 数据恢复 (极端情况)

如果回滚脚本失败或数据损坏, 从 Step 1 的备份恢复:

```bash
# MySQL 恢复
mysql -u<user> -p<password> <database> < backup_job_records_YYYYMMDD.sql

# Neo4j 恢复
neo4j-admin load --database=neo4j --from=backup_neo4j_YYYYMMDD.dump --force
```

---

## 6. 附录：文件清单

### 本文档相关文件

```
docs/
├── TAXONOMY_DESIGN.md                 # 分类体系设计文档 (前置阅读)
├── TAXONOMY_INTEGRATION.md            # 本文档 (集成指南)
│
├── migrations/
│   ├── taxonomy_mysql.sql             # MySQL 迁移 (1066 行)
│   ├── taxonomy_mysql_rollback.sql    # MySQL 回滚 (61 行)
│   ├── taxonomy_neo4j.cypher          # Neo4j 迁移 (1588 行)
│   └── generate_taxonomy_cypher.py    # Cypher 生成脚本
│
└── data/taxonomy/                     # 分类映射文件 (待创建)
    ├── job_title_mapping.csv          # 383+ 岗位 -> 域/类别
    ├── skill_category_mapping.csv     # 200+ 技能 -> 域/组/类型
    ├── industry_mapping.csv           # 71 行业 -> GB/T 4754
    └── ability_mapping.csv            # 能力初始种子数据

caiji/web/
├── api_skills.py          # P0: 修改 categories/ranking/network/communities
├── api_overview.py        # P0: 修改 overview, 新增 job-distribution
├── api_taxonomy.py        # P0: 新增 (7 个端点)
├── api_salary.py          # P1: 新增 by-domain, 修改 by-title
├── api_distribution.py    # P1: 新增 3 个分布端点, 修改 industries
├── api_reports.py         # P1: 新增 domain-growth, 修改 3 个端点
├── api_job_review.py      # P1: 新增 unclassified, 修改 pending/approve
├── api_matching.py        # P2: 新增 domain 上下文
├── api_evolution.py       # P2: 新增分类维度对比
├── api_skill_manage.py    # P2: 新增分类字段
├── api_graph_admin.py     # P2: Schema 覆盖检查
├── api_updater.py         # P3: 无结构变更
├── api_resume.py          # P3: 可选增强
├── api_rag.py             # P3: 无结构变更
│
└── spa/src/
    ├── services/api.ts              # 新增 taxonomy 接口 + 修改现有接口
    ├── components/common/TaxonomyFilter.tsx     # 新增 (分类级联筛选器)
    ├── components/charts/TaxonomySunburst.tsx   # 新增 (旭日图)
    ├── components/charts/TaxonomySankey.tsx     # 新增 (桑基图)
    │
    ├── pages/b-end/
    │   ├── Dashboard.tsx            # + 分类覆盖率 + 域分布卡片
    │   ├── SkillManage.tsx          # + TaxonomyFilter + 域分组
    │   ├── GraphManage.tsx          # + 新标签 Tab
    │   ├── JobReview.tsx            # + 分类字段列 + 筛选
    │   ├── Reports.tsx              # + 域维度切换
    │   ├── BatchMatch.tsx           # + 目标 domain 展示
    │   └── QuickMatch.tsx           # + 目标 domain 展示
    │
    └── pages/c-end/
        ├── Home.tsx                 # + 域热力分布
        ├── SkillGraphPage.tsx       # + 节点按 domain 着色
        ├── NewJobs.tsx              # + 域标签 Badge
        ├── Profile.tsx              # + 能力维度参考线
        └── ResumeEvaluate.tsx       # + 分类上下文
```

### 关键编码体系速查

| 分类体系 | Layer 1 | Layer 2 | Layer 3 | 参考标准 |
|---------|---------|---------|---------|---------|
| 岗位 | JobDomain (DOM-01~06) | JobCategory (CAT-0101~0604) | JobTitle (现有 383) | GB/T 6565 |
| 技能 | SkillDomain (SKD-01~99) | SkillGroup (GRP-0101~0705) | SkillType (T-xxxxx) | ESCO |
| 行业 | IndustrySector (A~T) | IndustryDivision (01~97) | IndustryGroup (011~979) | GB/T 4754 |
| 能力 | AbilityDimension (ABL-01~05) | CompetencyCluster (CLS-0101~0503) | Competency | O*NET |
| 教育 | -- | Education (ordinal 0~6) | -- | 自定义有序 |
| 经验 | -- | Experience (ordinal 0~6) | -- | 自定义有序 |
