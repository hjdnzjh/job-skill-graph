-- ============================================================================
-- 岗位能力分类体系 — MySQL 回滚脚本
-- ============================================================================
-- 版本：v1.1
-- 日期：2026-07-15
-- 用途：撤销 taxonomy_mysql.sql 所做的一切变更
--
-- 执行方式：
--   mysql -u<user> -p --default-character-set=utf8mb4 <database> < taxonomy_mysql_rollback.sql
--
-- 兼容性：
--   - DROP COLUMN IF EXISTS / DROP INDEX IF EXISTS 需要 MySQL 8.0.29+
--   - 若使用 MySQL 8.0.28，可改用下方注释的逐列 ALTER TABLE 语句
--   - 若已处于部分回滚状态，某些语句会报错（列/表不存在），可忽略继续执行
-- ============================================================================

SET FOREIGN_KEY_CHECKS = 0;

-- ---------------------------------------------------------------------------
-- 1. 删除分类索引（先删索引再删列，避免依赖问题）
-- ---------------------------------------------------------------------------
-- MySQL 8.0.29+ 语法：
DROP INDEX IF EXISTS idx_job_domain     ON job_records;
DROP INDEX IF EXISTS idx_job_category   ON job_records;
DROP INDEX IF EXISTS idx_industry_sector ON job_records;
DROP INDEX IF EXISTS idx_education_ord  ON job_records;
DROP INDEX IF EXISTS idx_experience_ord ON job_records;

-- MySQL 8.0.28 备用语法（取消注释以下行，注释上面 DROP INDEX IF EXISTS）：
-- ALTER TABLE job_records DROP INDEX idx_job_domain;
-- ALTER TABLE job_records DROP INDEX idx_job_category;
-- ALTER TABLE job_records DROP INDEX idx_industry_sector;
-- ALTER TABLE job_records DROP INDEX idx_education_ord;
-- ALTER TABLE job_records DROP INDEX idx_experience_ord;

-- ---------------------------------------------------------------------------
-- 2. 删除 job_records 新增的分类字段
--    注意：job_canonical_title 和 industry_code 为项目已有列，不在删除范围
-- ---------------------------------------------------------------------------
-- MySQL 8.0.29+ 语法（一条语句，任意列不存在则整条失败）：
-- ALTER TABLE job_records
--     DROP COLUMN IF EXISTS job_domain_code,
--     DROP COLUMN IF EXISTS job_domain_name,
--     DROP COLUMN IF EXISTS job_category_code,
--     DROP COLUMN IF EXISTS job_category_name,
--     DROP COLUMN IF EXISTS industry_sector_code,
--     DROP COLUMN IF EXISTS industry_sector_name,
--     DROP COLUMN IF EXISTS industry_division_code,
--     DROP COLUMN IF EXISTS industry_division_name,
--     DROP COLUMN IF EXISTS industry_group_code,
--     DROP COLUMN IF EXISTS industry_group_name,
--     DROP COLUMN IF EXISTS education_ordinal,
--     DROP COLUMN IF EXISTS experience_ordinal,
--     DROP COLUMN IF EXISTS experience_min_years,
--     DROP COLUMN IF EXISTS experience_max_years;

-- MySQL 8.0.28 兼容语法（逐列删除，已不存在的列会报错可忽略）：
ALTER TABLE job_records DROP COLUMN job_domain_code;
ALTER TABLE job_records DROP COLUMN job_domain_name;
ALTER TABLE job_records DROP COLUMN job_category_code;
ALTER TABLE job_records DROP COLUMN job_category_name;
ALTER TABLE job_records DROP COLUMN industry_sector_code;
ALTER TABLE job_records DROP COLUMN industry_sector_name;
ALTER TABLE job_records DROP COLUMN industry_division_code;
ALTER TABLE job_records DROP COLUMN industry_division_name;
ALTER TABLE job_records DROP COLUMN industry_group_code;
ALTER TABLE job_records DROP COLUMN industry_group_name;
ALTER TABLE job_records DROP COLUMN education_ordinal;
ALTER TABLE job_records DROP COLUMN experience_ordinal;
ALTER TABLE job_records DROP COLUMN experience_min_years;
ALTER TABLE job_records DROP COLUMN experience_max_years;

-- ---------------------------------------------------------------------------
-- 3. 删除分类查找表（按外键依赖顺序，先子后父）
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS taxonomy_competencies;
DROP TABLE IF EXISTS taxonomy_competency_clusters;
DROP TABLE IF EXISTS taxonomy_ability_dimensions;
DROP TABLE IF EXISTS taxonomy_skill_types;
DROP TABLE IF EXISTS taxonomy_skill_groups;
DROP TABLE IF EXISTS taxonomy_skill_domains;
DROP TABLE IF EXISTS taxonomy_industry_groups;
DROP TABLE IF EXISTS taxonomy_industry_divisions;
DROP TABLE IF EXISTS taxonomy_industry_sectors;
DROP TABLE IF EXISTS taxonomy_job_categories;
DROP TABLE IF EXISTS taxonomy_job_domains;

SET FOREIGN_KEY_CHECKS = 1;
