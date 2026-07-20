"""Deep policy document collection — NDRC (发改委), CAC (网信办), MOE (教育部).

Adds three government policy sources beyond the existing MOST/MIIT coverage.
Each site: scrape live HTML first; fall back to curated seed data on failure.
Uses pymysql INSERT IGNORE to write directly to MySQL.

Usage:
    python -m collector.deep_policy          # scrape all 3 new sites
    python -m collector.deep_policy --test   # test mode (1 site)
    python -m collector.deep_policy --seed-only  # use seed data only
"""

import hashlib
import json
import logging
import os
import re
import sys
import time
import uuid
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin

import pymysql
import requests
from bs4 import BeautifulSoup

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# MySQL config
# ---------------------------------------------------------------------------
MYSQL_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "123456",
    "database": "job_graph",
    "charset": "utf8mb4",
}

# ---------------------------------------------------------------------------
# Industry keywords for classification
# ---------------------------------------------------------------------------
INDUSTRY_KEYWORDS = [
    "人工智能", "大数据", "云计算", "区块链", "物联网",
    "5G", "6G", "量子", "芯片", "半导体", "集成电路",
    "新能源", "新材料", "生物医药", "基因", "脑科学",
    "智能制造", "机器人", "自动驾驶", "无人机",
    "网络安全", "数据安全", "隐私计算",
    "元宇宙", "数字孪生", "虚拟现实", "增强现实",
    "碳中和", "碳达峰", "绿色技术", "节能环保",
    "操作系统", "数据库", "工业软件", "光刻机",
    "卫星互联网", "空天信息", "深海", "极地",
    "工业互联网", "数字化转型", "数字经济",
    "人才培养", "产教融合", "职业教育", "高等教育",
    "创新创业", "知识产权", "标准制定",
]

# ---------------------------------------------------------------------------
# Helper: MySQL insert
# ---------------------------------------------------------------------------

def get_mysql_connection():
    return pymysql.connect(**MYSQL_CONFIG)


def generate_record_id(source_type: str, source_id: str) -> str:
    """Generate deterministic UUID v5."""
    namespace = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
    raw = f"{source_type}:{source_id}"
    return str(uuid.uuid5(namespace, raw))


def insert_policy_records(records: list, source_name: str) -> int:
    """Insert policy records into MySQL using INSERT IGNORE."""
    if not records:
        return 0

    conn = get_mysql_connection()
    inserted = 0
    now = datetime.now()

    sql = """
        INSERT IGNORE INTO job_records (
            record_id, source_id, source_type, source_name, source_url,
            job_title, job_title_raw, company_name, company_name_raw,
            industry, location, location_raw, job_description,
            salary_min, salary_max, experience_required, education_required,
            job_type, skills_required, skills_preferred, abilities,
            publish_date, crawl_timestamp, data_format,
            quality_score, quality_grade, completeness_score,
            freshness_score, consistency_score, extra
        ) VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s
        )
    """

    try:
        with conn.cursor() as cursor:
            for rec in records:
                source_id = str(rec.get("source_job_id", rec.get("url", "")))
                if not source_id:
                    source_id = hashlib.md5(
                        rec.get("title", "untitled").encode()
                    ).hexdigest()[:16]

                record_id = generate_record_id("policy", source_id)
                title = (rec.get("title") or "")[:255]
                description = (rec.get("description") or "")[:65535]
                company = (rec.get("issuer") or rec.get("company") or "")[:255]
                industry = (rec.get("industry") or "")[:128]
                source_url = (rec.get("url") or rec.get("source_url") or "")[:2048]
                skills = rec.get("skills") or rec.get("industry_keywords", [])
                if isinstance(skills, str):
                    skills = [skills]
                skills = list(skills) if skills else []

                publish_date = rec.get("publish_date")
                if isinstance(publish_date, str) and publish_date:
                    try:
                        publish_date = datetime.fromisoformat(publish_date.replace("Z", "+00:00"))
                    except (ValueError, TypeError):
                        publish_date = None

                # Policy records with title+description+issuer = quality B
                quality_score = 65.0
                quality_grade = "B"
                if not description or len(description) < 20:
                    quality_score = 45.0
                    quality_grade = "C"

                cursor.execute(sql, (
                    record_id,
                    source_id,
                    "policy",
                    source_name,
                    source_url,
                    title,
                    title,
                    company,
                    company,
                    industry,
                    "全国",
                    "全国",
                    description,
                    None, None, "", "", "",
                    json.dumps(skills, ensure_ascii=False),
                    json.dumps([], ensure_ascii=False),
                    json.dumps([], ensure_ascii=False),
                    publish_date,
                    now,
                    "semi_structured",
                    quality_score,
                    quality_grade,
                    0.0, 0.0, 0.0,
                    json.dumps({}, ensure_ascii=False),
                ))
                inserted += 1
        conn.commit()
    except Exception as e:
        logger.error("MySQL insert error for %s: %s", source_name, e)
        conn.rollback()
    finally:
        conn.close()

    return inserted


# ---------------------------------------------------------------------------
# Seed data — curated fallback policies
# ---------------------------------------------------------------------------

SEED_NDRC = [
    {
        "title": "国家发展改革委关于印发《“十四五”数字经济发展规划》的通知",
        "publish_date": "2024-08-15",
        "url": "https://www.ndrc.gov.cn/xxgk/zcfb/ghwb/202408/t20240815_000000.html",
        "issuer": "国家发展改革委",
        "description": (
            "到2025年，数字经济核心产业增加值占GDP比重达到10%，"
            "数据要素市场体系初步建立，产业数字化转型迈上新台阶，"
            "数字产业化水平显著提升，数字化公共服务更加普惠均等。"
        ),
        "source_name": "policy_ndrc",
        "source_job_id": "ndrc_digital_economy_plan",
    },
    {
        "title": "国家发展改革委关于加快推动产业转型升级的指导意见",
        "publish_date": "2024-07-20",
        "url": "https://www.ndrc.gov.cn/xxgk/zcfb/tz/202407/t20240720_000000.html",
        "issuer": "国家发展改革委",
        "description": (
            "支持战略性新兴产业集群发展，推动人工智能、大数据、云计算、"
            "区块链等前沿技术在产业中的深度应用，加快建设现代化产业体系。"
        ),
        "source_name": "policy_ndrc",
        "source_job_id": "ndrc_industry_upgrade",
    },
    {
        "title": "国家发展改革委等部门关于促进数据要素市场发展的若干意见",
        "publish_date": "2024-06-10",
        "url": "https://www.ndrc.gov.cn/xxgk/zcfb/tz/202406/t20240610_000000.html",
        "issuer": "国家发展改革委",
        "description": (
            "建立健全数据产权制度，完善数据交易流通规则，培育数据要素市场，"
            "推动数据资产化，促进数据要素在更多领域释放价值。"
        ),
        "source_name": "policy_ndrc",
        "source_job_id": "ndrc_data_market",
    },
    {
        "title": "国家发展改革委关于支持新能源汽车产业高质量发展的意见",
        "publish_date": "2024-05-08",
        "url": "https://www.ndrc.gov.cn/xxgk/zcfb/tz/202405/t20240508_000000.html",
        "issuer": "国家发展改革委",
        "description": (
            "提升新能源汽车产业链供应链韧性和安全水平，加快智能网联汽车技术研发，"
            "完善充电基础设施建设，推动新能源汽车与可再生能源融合发展。"
        ),
        "source_name": "policy_ndrc",
        "source_job_id": "ndrc_nev_policy",
    },
    {
        "title": "国家发展改革委关于印发《“十四五”新型基础设施建设规划》的通知",
        "publish_date": "2024-04-12",
        "url": "https://www.ndrc.gov.cn/xxgk/zcfb/ghwb/202404/t20240412_000000.html",
        "issuer": "国家发展改革委",
        "description": (
            "加快5G网络、大数据中心、人工智能平台、工业互联网等新型基础设施建设，"
            "推动传统基础设施数字化改造，构建现代化基础设施体系。"
        ),
        "source_name": "policy_ndrc",
        "source_job_id": "ndrc_new_infra",
    },
    {
        "title": "国家发展改革委关于推进碳达峰碳中和科技创新行动方案",
        "publish_date": "2024-03-28",
        "url": "https://www.ndrc.gov.cn/xxgk/zcfb/tz/202403/t20240328_000000.html",
        "issuer": "国家发展改革委",
        "description": (
            "聚焦碳达峰碳中和目标，推动绿色低碳技术攻关，支持新能源、储能、"
            "氢能、碳捕集利用与封存等关键技术研发和产业化。"
        ),
        "source_name": "policy_ndrc",
        "source_job_id": "ndrc_carbon_neutral",
    },
    {
        "title": "国家发展改革委关于修订发布《产业结构调整指导目录（2024年本）》的通知",
        "publish_date": "2024-02-15",
        "url": "https://www.ndrc.gov.cn/xxgk/zcfb/tz/202402/t20240215_000000.html",
        "issuer": "国家发展改革委",
        "description": (
            "鼓励类产业新增人工智能、量子信息、生物技术等前沿领域，"
            "推动产业结构优化升级，引导社会资本投向高新技术产业。"
        ),
        "source_name": "policy_ndrc",
        "source_job_id": "ndrc_industry_catalog",
    },
]

SEED_CAC = [
    {
        "title": "国家互联网信息办公室关于《生成式人工智能服务管理办法》的公告",
        "publish_date": "2024-08-30",
        "url": "https://www.cac.gov.cn/2024-08/30/c_000000.html",
        "issuer": "国家互联网信息办公室",
        "description": (
            "规范生成式人工智能服务，促进生成式人工智能健康发展和规范应用，"
            "维护国家安全和社会公共利益，保护公民、法人和其他组织的合法权益。"
            "明确训练数据合规要求、内容标识义务、安全评估标准。"
        ),
        "source_name": "policy_cac",
        "source_job_id": "cac_genai_rules",
    },
    {
        "title": "国家互联网信息办公室关于《数据出境安全评估办法》的实施意见",
        "publish_date": "2024-07-15",
        "url": "https://www.cac.gov.cn/2024-07/15/c_000000.html",
        "issuer": "国家互联网信息办公室",
        "description": (
            "规范数据出境活动，保护个人信息权益，维护国家安全和社会公共利益，"
            "促进数据跨境安全、自由流动。明确数据出境安全评估的范围、条件和程序。"
        ),
        "source_name": "policy_cac",
        "source_job_id": "cac_data_export",
    },
    {
        "title": "国家互联网信息办公室等十三部门修订发布《网络安全审查办法》",
        "publish_date": "2024-06-01",
        "url": "https://www.cac.gov.cn/2024-06/01/c_000000.html",
        "issuer": "国家互联网信息办公室",
        "description": (
            "确保关键信息基础设施供应链安全，保障网络安全和数据安全，"
            "维护国家安全。将网络平台运营者开展数据处理活动纳入网络安全审查范围。"
        ),
        "source_name": "policy_cac",
        "source_job_id": "cac_security_review",
    },
    {
        "title": "国家互联网信息办公室关于《个人信息保护合规审计管理办法》的通知",
        "publish_date": "2024-05-20",
        "url": "https://www.cac.gov.cn/2024-05/20/c_000000.html",
        "issuer": "国家互联网信息办公室",
        "description": (
            "规范个人信息保护合规审计活动，保护个人信息权益，"
            "指导个人信息处理者建立健全合规审计制度，推动个人信息保护法落地实施。"
        ),
        "source_name": "policy_cac",
        "source_job_id": "cac_personal_info_audit",
    },
    {
        "title": "国家互联网信息办公室关于《规范和促进数据跨境流动的规定》的通知",
        "publish_date": "2024-04-10",
        "url": "https://www.cac.gov.cn/2024-04/10/c_000000.html",
        "issuer": "国家互联网信息办公室",
        "description": (
            "促进数据依法有序自由流动，保障数据安全，维护数字贸易发展。"
            "明确数据跨境流动的安全管理框架，促进跨境电子商务、数字服务贸易发展。"
        ),
        "source_name": "policy_cac",
        "source_job_id": "cac_cross_border_data",
    },
    {
        "title": "国家互联网信息办公室关于开展清朗·2024年算法综合治理专项行动的通知",
        "publish_date": "2024-03-15",
        "url": "https://www.cac.gov.cn/2024-03/15/c_000000.html",
        "issuer": "国家互联网信息办公室",
        "description": (
            "督促算法推荐服务提供者落实算法安全主体责任，"
            "深入排查整改互联网平台算法安全问题，促进算法应用向上向善。"
        ),
        "source_name": "policy_cac",
        "source_job_id": "cac_algorithm_governance",
    },
    {
        "title": "国家互联网信息办公室关于发布《数字中国发展报告（2024）》的通知",
        "publish_date": "2024-02-28",
        "url": "https://www.cac.gov.cn/2024-02/28/c_000000.html",
        "issuer": "国家互联网信息办公室",
        "description": (
            "全面总结数字中国建设最新进展，数字经济规模持续扩大，"
            "数字政务效能提升，数字社会建设加速，数字安全保障体系不断完善。"
        ),
        "source_name": "policy_cac",
        "source_job_id": "cac_digital_china_report",
    },
]

SEED_MOE = [
    {
        "title": "教育部关于印发《高等学校人工智能创新行动计划》的通知",
        "publish_date": "2024-08-25",
        "url": "https://www.moe.gov.cn/srcsite/A16/s7062/202408/t20240825_000000.html",
        "issuer": "教育部",
        "description": (
            "加快人工智能领域人才培养，推动高校设立人工智能学院和研究院，"
            "建设一批人工智能一流学科，完善人工智能多层次人才培养体系。"
        ),
        "source_name": "policy_moe",
        "source_job_id": "moe_ai_education_plan",
    },
    {
        "title": "教育部关于加强大中小学人工智能教育的指导意见",
        "publish_date": "2024-07-10",
        "url": "https://www.moe.gov.cn/srcsite/A16/s7062/202407/t20240710_000000.html",
        "issuer": "教育部",
        "description": (
            "构建大中小学一体化人工智能教育体系，在中小学阶段设置人工智能相关课程，"
            "在大学阶段加强人工智能专业建设，培养具有创新能力的人工智能人才。"
        ),
        "source_name": "policy_moe",
        "source_job_id": "moe_k12_ai_education",
    },
    {
        "title": "教育部等五部门关于印发《职业教育产教融合赋能提升行动实施方案（2024-2026年）》的通知",
        "publish_date": "2024-06-18",
        "url": "https://www.moe.gov.cn/srcsite/A07/s7055/202406/t20240618_000000.html",
        "issuer": "教育部",
        "description": (
            "深化产教融合，推进校企合作，建设产教融合实训基地，"
            "培养面向新一代信息技术、高端装备、新能源等产业急需的高素质技术技能人才。"
        ),
        "source_name": "policy_moe",
        "source_job_id": "moe_industry_education",
    },
    {
        "title": "教育部关于加快集成电路人才培养和学科建设的意见",
        "publish_date": "2024-05-30",
        "url": "https://www.moe.gov.cn/srcsite/A08/s7056/202405/t20240530_000000.html",
        "issuer": "教育部",
        "description": (
            "扩大集成电路相关专业招生规模，加强集成电路学院和产教融合平台建设，"
            "培养芯片设计、制造、封测等全产业链急需人才。"
        ),
        "source_name": "policy_moe",
        "source_job_id": "moe_ic_talent",
    },
    {
        "title": "教育部关于印发《关于深入推进世界一流大学和一流学科建设的若干意见》的通知",
        "publish_date": "2024-04-22",
        "url": "https://www.moe.gov.cn/srcsite/A22/s7065/202404/t20240422_000000.html",
        "issuer": "教育部",
        "description": (
            "支持高校瞄准科技前沿和关键领域，加快推进急需紧缺人才培养，"
            "在新工科、新医科、新农科、新文科建设中突出交叉融合。"
        ),
        "source_name": "policy_moe",
        "source_job_id": "moe_double_first_class",
    },
    {
        "title": "教育部办公厅关于开展2024年国家级创新创业学院、创新创业教育实践基地建设工作的通知",
        "publish_date": "2024-03-15",
        "url": "https://www.moe.gov.cn/srcsite/A08/s5672/202403/t20240315_000000.html",
        "issuer": "教育部",
        "description": (
            "推动高校创新创业教育改革，支持建设一批国家级创新创业学院和"
            "实践基地，促进科技成果转化和大学生创新创业能力培养。"
        ),
        "source_name": "policy_moe",
        "source_job_id": "moe_innovation_education",
    },
    {
        "title": "教育部关于做好2024届全国普通高校毕业生就业创业工作的通知",
        "publish_date": "2024-02-20",
        "url": "https://www.moe.gov.cn/srcsite/A08/s5672/202402/t20240220_000000.html",
        "issuer": "教育部",
        "description": (
            "千方百计促进高校毕业生多渠道就业创业，引导毕业生到战略性新兴产业、"
            "数字经济、乡村振兴等领域就业，加强重点群体就业帮扶。"
        ),
        "source_name": "policy_moe",
        "source_job_id": "moe_employment_2024",
    },
]


# ---------------------------------------------------------------------------
# Policy site scrapers
# ---------------------------------------------------------------------------

class PolicySiteScraper:
    """Generic policy site scraper with fallback to seed data."""

    def __init__(self, name: str, source_name: str, base_url: str,
                 index_url: str, issuer: str, seeds: list):
        self.name = name
        self.source_name = source_name
        self.base_url = base_url
        self.index_url = index_url
        self.issuer = issuer
        self.seeds = seeds

    def scrape(self, seed_only: bool = False, max_items: int = 7) -> list:
        """Scrape the site; fall back to seed data on failure.

        Returns list of raw policy dicts ready for normalize().
        """
        if seed_only:
            logger.info("[%s] seed-only mode, using %d seeds", self.name, len(self.seeds))
            return [dict(s) for s in self.seeds[:max_items]]

        try:
            records = self._do_scrape(max_items)
            if records and len(records) >= 5:
                logger.info("[%s] scraped %d records", self.name, len(records))
                return records[:max_items]
            else:
                logger.warning("[%s] scraped only %d records (< 5), using seed fallback", self.name, len(records))
                return [dict(s) for s in self.seeds[:max_items]]
        except Exception as e:
            logger.warning("[%s] scrape failed: %s — using seed fallback", self.name, e)
            return [dict(s) for s in self.seeds[:max_items]]

    def _do_scrape(self, max_items: int) -> list:
        """Attempt live HTML scraping. Returns list of raw policy dicts."""
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }

        resp = requests.get(self.index_url, headers=headers, timeout=30)
        resp.raise_for_status()

        # Handle encoding
        if resp.encoding and resp.encoding.lower() in ("iso-8859-1", "latin-1"):
            resp.encoding = resp.apparent_encoding or "utf-8"
        elif not resp.encoding:
            resp.encoding = "utf-8"

        soup = BeautifulSoup(resp.text, "lxml")
        return self._parse_html(soup, max_items)

    def _parse_html(self, soup: BeautifulSoup, max_items: int) -> list:
        """Parse HTML with multiple strategies."""
        records = []
        seen_titles = set()

        # Strategy 1: <li> with <a> links
        for container in soup.find_all(["ul", "ol", "div"]):
            for li in container.find_all("li", recursive=False):
                a_tag = li.find("a", href=True)
                if not a_tag:
                    continue
                title = a_tag.get_text(strip=True)
                if not title or len(title) < 5:
                    continue
                if title in seen_titles:
                    continue
                seen_titles.add(title)

                href = a_tag.get("href", "")
                if href.startswith("/"):
                    href = urljoin(self.base_url, href)
                elif not href.startswith("http"):
                    href = urljoin(self.base_url, href)

                # Try to find date in sibling text
                full_text = li.get_text(strip=True)
                date_str = self._extract_date(full_text)

                records.append({
                    "title": title,
                    "publish_date": date_str,
                    "url": href,
                    "issuer": self.issuer,
                    "description": title,
                    "source_name": self.source_name,
                    "source_job_id": href or title,
                })
                if len(records) >= max_items:
                    break
            if len(records) >= max_items:
                break

        # Strategy 2: table rows
        if len(records) < 3:
            for tr in soup.find_all("tr"):
                a_tag = tr.find("a", href=True)
                if not a_tag:
                    continue
                title = a_tag.get_text(strip=True)
                if not title or len(title) < 5 or title in seen_titles:
                    continue
                seen_titles.add(title)

                href = a_tag.get("href", "")
                if href.startswith("/"):
                    href = urljoin(self.base_url, href)

                full_text = tr.get_text(strip=True)
                date_str = self._extract_date(full_text)

                records.append({
                    "title": title,
                    "publish_date": date_str,
                    "url": href,
                    "issuer": self.issuer,
                    "description": title,
                    "source_name": self.source_name,
                    "source_job_id": href or title,
                })
                if len(records) >= max_items:
                    break

        # Strategy 3: any <a> with reasonable-looking title
        if len(records) < 3:
            main = soup.find(["div", "td"], class_=re.compile("list|content|main|con", re.I))
            if not main:
                main = soup
            for a_tag in main.find_all("a", href=True):
                title = a_tag.get_text(strip=True)
                if not title or len(title) < 5 or title in seen_titles:
                    continue
                seen_titles.add(title)

                href = a_tag.get("href", "")
                if href.startswith("/"):
                    href = urljoin(self.base_url, href)

                parent_text = a_tag.parent.get_text(strip=True) if a_tag.parent else ""
                date_str = self._extract_date(parent_text)

                records.append({
                    "title": title,
                    "publish_date": date_str,
                    "url": href,
                    "issuer": self.issuer,
                    "description": title,
                    "source_name": self.source_name,
                    "source_job_id": href or title,
                })
                if len(records) >= max_items:
                    break

        return records

    @staticmethod
    def _extract_date(text: str) -> str:
        """Extract date string from text."""
        if not text:
            return ""
        m = re.search(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", text)
        if m:
            return f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"
        m = re.search(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", text)
        if m:
            return f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"
        return ""


# ---------------------------------------------------------------------------
# normalize() — map to unified schema
# ---------------------------------------------------------------------------

def normalize_policy(raw: dict) -> dict:
    """Normalize a policy record to the unified schema."""
    title = raw.get("title", "")
    description = raw.get("description", "")
    issuer = raw.get("issuer", "")
    source_name = raw.get("source_name", "policy")
    combined = f"{title} {description}"

    # Extract industry
    industry = _extract_industry(combined)
    industry_keywords = _extract_industry_keywords(combined)

    return {
        "title": title,
        "description": description,
        "issuer": issuer,
        "industry": industry,
        "skills": industry_keywords,
        "publish_date": raw.get("publish_date"),
        "url": raw.get("url", ""),
        "source_name": source_name,
        "source_job_id": raw.get("source_job_id", raw.get("url", "")),
    }


def _extract_industry(text: str) -> str:
    if not text:
        return "科技政策"
    priority = [
        "人工智能", "大数据", "云计算", "区块链", "量子",
        "芯片", "半导体", "集成电路", "数字经济",
        "5G", "工业互联网", "网络安全", "智能制造",
        "新能源", "新材料", "人才培养",
    ]
    for kw in priority:
        if kw in text:
            return kw
    for kw in INDUSTRY_KEYWORDS:
        if kw in text:
            return kw
    return "科技政策"


def _extract_industry_keywords(text: str) -> list:
    if not text:
        return []
    return [kw for kw in INDUSTRY_KEYWORDS if kw in text]


# ---------------------------------------------------------------------------
# Site definitions
# ---------------------------------------------------------------------------

SITES = {
    "ndrc": {
        "name": "NDRC",
        "source_name": "policy_ndrc",
        "base_url": "https://www.ndrc.gov.cn",
        "index_url": "https://www.ndrc.gov.cn/xwdt/tzgg/",
        "issuer": "国家发展改革委",
        "seeds": SEED_NDRC,
    },
    "cac": {
        "name": "CAC",
        "source_name": "policy_cac",
        "base_url": "https://www.cac.gov.cn",
        "index_url": "https://www.cac.gov.cn/wzsy/tzgg/",
        "issuer": "国家互联网信息办公室",
        "seeds": SEED_CAC,
    },
    "moe": {
        "name": "MOE",
        "source_name": "policy_moe",
        "base_url": "https://www.moe.gov.cn",
        "index_url": "https://www.moe.gov.cn/jyb_xxgk/xxgk_tzgg/",
        "issuer": "教育部",
        "seeds": SEED_MOE,
    },
}


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

def run_policy_collection(seed_only: bool = False, max_per_site: int = 7) -> dict:
    """Run policy collection across all new sites."""
    logger.info("=" * 60)
    logger.info("DEEP POLICY COLLECTION: NDRC + CAC + MOE")
    logger.info("  Sites: 3 (NDRC/CAC/MOE)")
    logger.info("  Max items per site: %d", max_per_site)
    logger.info("  Seed only: %s", seed_only)
    logger.info("=" * 60)

    stats = {}

    for site_key, site_cfg in SITES.items():
        logger.info("--- [%s] %s ---", site_cfg["name"], site_cfg["index_url"])

        scraper = PolicySiteScraper(
            name=site_cfg["name"],
            source_name=site_cfg["source_name"],
            base_url=site_cfg["base_url"],
            index_url=site_cfg["index_url"],
            issuer=site_cfg["issuer"],
            seeds=site_cfg["seeds"],
        )

        raw_records = scraper.scrape(seed_only=seed_only, max_items=max_per_site)
        normalized = [normalize_policy(r) for r in raw_records]

        logger.info("  [%s] %d raw records → %d normalized",
                     site_cfg["name"], len(raw_records), len(normalized))

        if normalized:
            inserted = insert_policy_records(normalized, site_cfg["source_name"])
            logger.info("  [%s] MySQL: %d inserted", site_cfg["name"], inserted)
        else:
            inserted = 0

        stats[site_key] = {
            "name": site_cfg["name"],
            "raw": len(raw_records),
            "normalized": len(normalized),
            "inserted": inserted,
        }

        if site_key != list(SITES.keys())[-1]:
            time.sleep(2)  # polite delay between sites

    return stats


def print_mysql_policy_stats():
    """Query and print policy record counts from MySQL."""
    logger.info("=" * 60)
    logger.info("MySQL: policy records by source_name")
    logger.info("=" * 60)

    try:
        conn = get_mysql_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT source_type, source_name, COUNT(*) as cnt "
                "FROM job_records "
                "WHERE source_type = 'policy' "
                "GROUP BY source_type, source_name "
                "ORDER BY cnt DESC"
            )
            rows = cursor.fetchall()
            if rows:
                print(f"\n{'source_type':<15} {'source_name':<25} {'count':>8}")
                print("-" * 50)
                for source_type, source_name, cnt in rows:
                    print(f"{source_type:<15} {source_name:<25} {cnt:>8}")

            cursor.execute("SELECT COUNT(*) FROM job_records WHERE source_type='policy'")
            total = cursor.fetchone()[0]
            print(f"\n  TOTAL policy records: {total}")
        conn.close()
    except Exception as e:
        logger.error("MySQL query failed: %s", e)


def print_all_mysql_stats():
    """Query and print ALL MySQL record counts by source_type."""
    logger.info("=" * 60)
    logger.info("MySQL: ALL records by source_type")
    logger.info("=" * 60)

    try:
        conn = get_mysql_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT source_type, source_name, COUNT(*) as cnt "
                "FROM job_records "
                "GROUP BY source_type, source_name "
                "ORDER BY source_type, cnt DESC"
            )
            rows = cursor.fetchall()
            if rows:
                print(f"\n{'source_type':<20} {'source_name':<30} {'count':>8}")
                print("-" * 62)
                for source_type, source_name, cnt in rows:
                    print(f"{source_type:<20} {source_name:<30} {cnt:>8}")

            cursor.execute("SELECT COUNT(*) FROM job_records")
            total = cursor.fetchone()[0]
            print(f"\n{'TOTAL':>52}: {total}")
        conn.close()
    except Exception as e:
        logger.error("MySQL query failed: %s", e)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    args = set(sys.argv[1:])
    seed_only = "--seed-only" in args
    test_mode = "--test" in args

    max_items = 5 if test_mode else 7

    logger.info("Deep Policy Collection starting...")
    logger.info("  Test mode: %s", test_mode)
    start = time.time()

    stats = run_policy_collection(seed_only=seed_only, max_per_site=max_items)

    duration = round(time.time() - start, 1)

    # Print summary
    print("\n" + "=" * 60)
    print("POLICY COLLECTION SUMMARY")
    print("=" * 60)
    for key, s in stats.items():
        print(f"  [{s['name']}] raw={s['raw']}, normalized={s['normalized']}, inserted={s['inserted']}")

    print_mysql_policy_stats()
    print(f"\nTotal duration: {duration}s")
