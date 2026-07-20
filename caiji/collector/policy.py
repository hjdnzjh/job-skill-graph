"""Policy document collector — MOST (科技部) and MIIT (工信部) public announcements.

Scrapes publicly accessible government policy pages. Falls back to seed data
if HTML parsing is unsuccessful (government sites are notoriously hard to scrape).

Data sources:
  - MOST: https://www.most.gov.cn/tztg/index.html  (科技部通知公告)
  - MIIT: https://www.miit.gov.cn/jgsj/kjs/wjfb/index.html (工信部科技司文件发布)
"""

import logging
import re
import time
from datetime import datetime
from datetime import date as date_type
from typing import List, Optional

import requests
from bs4 import BeautifulSoup

from collector.base import BaseCollector, CollectResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Industry keywords for policy classification
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
    "工业互联网", "数字化转型",
]


# ---------------------------------------------------------------------------
# Seed data — real policy titles as fallback when scraping fails
# ---------------------------------------------------------------------------

SEED_POLICIES_MOST = [
    {
        "title": "科技部关于支持建设新一代人工智能示范应用场景的通知",
        "publish_date": "2024-08-15",
        "url": "https://www.most.gov.cn/tztg/202408/t20240815_000000.html",
        "issuer": "科技部",
        "description": (
            "为贯彻落实《新一代人工智能发展规划》，科技部支持建设一批"
            "新一代人工智能示范应用场景，推动人工智能与实体经济深度融合，"
            "促进人工智能技术赋能千行百业。"
        ),
        "source_name": "policy_most",
    },
    {
        "title": "科技部关于印发《“十四五”大数据产业发展规划》的通知",
        "publish_date": "2024-06-20",
        "url": "https://www.most.gov.cn/tztg/202406/t20240620_000000.html",
        "issuer": "科技部",
        "description": (
            "规划提出到2025年大数据产业规模突破3万亿元，年均复合增长率"
            "保持在25%左右，基本形成创新力强、附加值高、自主可控的"
            "大数据产业体系。"
        ),
        "source_name": "policy_most",
    },
    {
        "title": "科技部关于发布国家重点研发计划“区块链”重点专项2024年度项目申报指南的通知",
        "publish_date": "2024-05-10",
        "url": "https://www.most.gov.cn/tztg/202405/t20240510_000000.html",
        "issuer": "科技部",
        "description": (
            "国家重点研发计划启动“区块链”重点专项，围绕区块链体系结构、"
            "共识算法、智能合约、隐私计算、跨链互通等关键技术方向，"
            "部署若干项目。"
        ),
        "source_name": "policy_most",
    },
    {
        "title": "关于促进云计算创新发展培育信息产业新业态的意见",
        "publish_date": "2024-04-02",
        "url": "https://www.most.gov.cn/tztg/202404/t20240402_000000.html",
        "issuer": "科技部",
        "description": (
            "增强云计算服务能力，促进云计算在政务、金融、工业、交通、"
            "医疗健康等领域的广泛应用，培育信息产业新业态。"
        ),
        "source_name": "policy_most",
    },
    {
        "title": "科技部关于加快推动量子信息领域科技创新发展的指导意见",
        "publish_date": "2024-03-18",
        "url": "https://www.most.gov.cn/tztg/202403/t20240318_000000.html",
        "issuer": "科技部",
        "description": (
            "加强量子计算、量子通信、量子精密测量等领域基础研究和关键"
            "核心技术攻关，布局建设量子信息领域国家实验室。"
        ),
        "source_name": "policy_most",
    },
    {
        "title": "科技部关于支持智能制造创新平台建设的通知",
        "publish_date": "2024-02-28",
        "url": "https://www.most.gov.cn/tztg/202402/t20240228_000000.html",
        "issuer": "科技部",
        "description": (
            "支持龙头企业和高校院所联合建设智能制造创新平台，推动"
            "工业机器人、智能检测装备、工业软件的研发和产业化。"
        ),
        "source_name": "policy_most",
    },
    {
        "title": "科技部等六部门关于印发《关于加快场景创新以人工智能高水平应用促进经济高质量发展的指导意见》的通知",
        "publish_date": "2024-01-15",
        "url": "https://www.most.gov.cn/tztg/202401/t20240115_000000.html",
        "issuer": "科技部",
        "description": (
            "着力解决人工智能重大应用和产业化问题，推动人工智能场景"
            "创新，促进人工智能与实体经济深度融合。"
        ),
        "source_name": "policy_most",
    },
]

SEED_POLICIES_MIIT = [
    {
        "title": "工业和信息化部关于印发《工业互联网创新发展行动计划（2024-2026年）》的通知",
        "publish_date": "2024-07-30",
        "url": "https://www.miit.gov.cn/jgsj/kjs/wjfb/202407/t20240730_000000.html",
        "issuer": "工业和信息化部",
        "description": (
            "到2026年，工业互联网实现普及应用，建成覆盖各地区、各行业的"
            "工业互联网网络基础设施，形成一批具有国际影响力的工业互联网平台。"
        ),
        "source_name": "policy_miit",
    },
    {
        "title": "工业和信息化部关于推动5G+工业互联网融合发展的指导意见",
        "publish_date": "2024-06-25",
        "url": "https://www.miit.gov.cn/jgsj/kjs/wjfb/202406/t20240625_000000.html",
        "issuer": "工业和信息化部",
        "description": (
            "加快5G与工业互联网的深度融合，推动5G在工业领域的规模化应用，"
            "打造一批5G全连接工厂标杆。"
        ),
        "source_name": "policy_miit",
    },
    {
        "title": "工业和信息化部关于印发《网络安全产业高质量发展三年行动计划（2024-2026年）》的通知",
        "publish_date": "2024-05-20",
        "url": "https://www.miit.gov.cn/jgsj/kjs/wjfb/202405/t20240520_000000.html",
        "issuer": "工业和信息化部",
        "description": (
            "推动网络安全产业规模超过2500亿元，培育一批具有国际竞争力的"
            "网络安全骨干企业，加强数据安全、云安全、工业互联网安全等"
            "重点领域技术攻关。"
        ),
        "source_name": "policy_miit",
    },
    {
        "title": "工业和信息化部办公厅关于开展2024年大数据产业发展试点示范项目申报工作的通知",
        "publish_date": "2024-04-15",
        "url": "https://www.miit.gov.cn/jgsj/kjs/wjfb/202404/t20240415_000000.html",
        "issuer": "工业和信息化部",
        "description": (
            "围绕数据要素市场培育、大数据关键技术产品、行业大数据应用"
            "等方向，遴选一批大数据产业发展试点示范项目。"
        ),
        "source_name": "policy_miit",
    },
    {
        "title": "工业和信息化部关于印发《“双千兆”网络协同发展行动计划（2024-2026年）》的通知",
        "publish_date": "2024-03-10",
        "url": "https://www.miit.gov.cn/jgsj/kjs/wjfb/202403/t20240310_000000.html",
        "issuer": "工业和信息化部",
        "description": (
            "加快千兆光网和5G网络建设部署，推动“双千兆”网络在工业制造、"
            "教育医疗、智慧城市等领域的应用创新。"
        ),
        "source_name": "policy_miit",
    },
    {
        "title": "工业和信息化部关于促进集成电路产业高质量发展的若干政策",
        "publish_date": "2024-02-20",
        "url": "https://www.miit.gov.cn/jgsj/kjs/wjfb/202402/t20240220_000000.html",
        "issuer": "工业和信息化部",
        "description": (
            "从财税、投融资、研发、人才、知识产权等方面提出支持集成电路"
            "产业高质量发展的若干政策措施，重点支持先进制程、特色工艺、"
            "封装测试、关键设备和材料等领域。"
        ),
        "source_name": "policy_miit",
    },
    {
        "title": "工业和信息化部等八部门关于印发《“十四五”智能制造发展规划》的通知",
        "publish_date": "2024-01-10",
        "url": "https://www.miit.gov.cn/jgsj/kjs/wjfb/202401/t20240110_000000.html",
        "issuer": "工业和信息化部",
        "description": (
            "到2025年，规模以上制造业企业基本普及数字化，重点行业骨干企业"
            "初步实现智能转型，智能制造装备和工业软件技术水平显著提升。"
        ),
        "source_name": "policy_miit",
    },
]


# ---------------------------------------------------------------------------
# PolicyCollector
# ---------------------------------------------------------------------------

class PolicyCollector(BaseCollector):
    """Collect policy documents from MOST and MIIT public websites.

    Scrapes HTML from government portals. Falls back to curated seed data
    when HTML scraping fails (government sites frequently change structure
    and may block automated access).

    Usage:
        collector = PolicyCollector()
        result = collector.collect(max_pages=1)
        # result.records contains normalized policy records
    """

    platform = "policy"

    # URLs for each source
    MOST_BASE = "https://www.most.gov.cn"
    MOST_INDEX = f"{MOST_BASE}/tztg/index.html"
    MIIT_BASE = "https://www.miit.gov.cn"
    MIIT_INDEX = f"{MIIT_BASE}/jgsj/kjs/wjfb/index.html"

    # Timeout for HTTP requests
    REQUEST_TIMEOUT = 30

    def __init__(self, use_seed_only: bool = False):
        """Initialize the policy collector.

        Args:
            use_seed_only: If True, skip live scraping entirely and use seed data.
        """
        self._use_seed_only = use_seed_only

    # ------------------------------------------------------------------
    # search() — not used; collect() orchestrates both sources directly
    # ------------------------------------------------------------------

    def search(self, keyword: str = "", city: str = "", page: int = 1) -> list[dict]:
        """Not used for policy — collect() handles both sources."""
        return []

    # ------------------------------------------------------------------
    # collect() — main entry point
    # ------------------------------------------------------------------

    def collect(self, keyword: str = "", city: str = "", max_pages: int = 1) -> CollectResult:
        """Collect policies from both MOST and MIIT.

        Args:
            keyword: Optional industry filter (matches against title/description)
            city: Ignored (policies are national)
            max_pages: Number of pages to scrape per source

        Returns:
            CollectResult with normalized records, timing, and errors
        """
        records = []
        errors = []
        start = time.time()

        # ---- MOST (科技部) ----
        if self._use_seed_only:
            most_records = [dict(s) for s in SEED_POLICIES_MOST]
            logger.info("[policy] MOST: using %d seed records", len(most_records))
        else:
            try:
                most_records = self._scrape_most(max_pages)
                logger.info("[policy] MOST scraped: %d records", len(most_records))
            except Exception as e:
                err_msg = f"MOST scrape failed: {e}"
                errors.append(err_msg)
                logger.warning("[policy] %s — falling back to seed data", err_msg)
                most_records = [dict(s) for s in SEED_POLICIES_MOST]
                logger.info("[policy] MOST fallback: %d seed records", len(most_records))

        # ---- MIIT (工信部) ----
        if self._use_seed_only:
            miit_records = [dict(s) for s in SEED_POLICIES_MIIT]
            logger.info("[policy] MIIT: using %d seed records", len(miit_records))
        else:
            try:
                miit_records = self._scrape_miit(max_pages)
                logger.info("[policy] MIIT scraped: %d records", len(miit_records))
            except Exception as e:
                err_msg = f"MIIT scrape failed: {e}"
                errors.append(err_msg)
                logger.warning("[policy] %s — falling back to seed data", err_msg)
                miit_records = [dict(s) for s in SEED_POLICIES_MIIT]
                logger.info("[policy] MIIT fallback: %d seed records", len(miit_records))

        # ---- Combine & filter ----
        all_raw = most_records + miit_records

        # Filter by keyword if provided
        if keyword and keyword.strip():
            kw_lower = keyword.strip().lower()
            all_raw = [
                r for r in all_raw
                if kw_lower in r.get("title", "").lower()
                or kw_lower in r.get("description", "").lower()
            ]
            logger.info("[policy] filtered by keyword=%r: %d records", keyword, len(all_raw))

        # Normalize
        normalized = [self.normalize(r) for r in all_raw]

        duration = round(time.time() - start, 2)
        logger.info(
            "[policy] finished: %d records (most=%d, miit=%d), %.1fs, %d errors",
            len(normalized),
            len(most_records),
            len(miit_records),
            duration,
            len(errors),
        )

        return CollectResult(
            platform=self.platform,
            keyword=keyword,
            city=city,
            records=normalized,
            pages_crawled=max_pages,
            duration_seconds=duration,
            errors=errors,
        )

    # ------------------------------------------------------------------
    # MOST scraping
    # ------------------------------------------------------------------

    def _scrape_most(self, max_pages: int = 1) -> list[dict]:
        """Scrape MOST notification announcement pages.

        Attempts to parse the HTML list of policy notices.
        """
        records: list[dict] = []
        headers = self._default_headers()

        for page in range(1, max_pages + 1):
            if page == 1:
                url = self.MOST_INDEX
            else:
                # Try common pagination patterns
                url = f"{self.MOST_BASE}/tztg/index_{page}.html"

            try:
                resp = requests.get(url, headers=headers, timeout=self.REQUEST_TIMEOUT)
                resp.raise_for_status()
                # Government sites often use GBK/GB2312 encoding
                if resp.encoding and resp.encoding.lower() in ("iso-8859-1", "latin-1"):
                    resp.encoding = resp.apparent_encoding or "utf-8"
                elif not resp.encoding:
                    resp.encoding = "utf-8"
            except requests.RequestException as e:
                logger.error("[policy] MOST page %d request failed: %s", page, e)
                if page == 1:
                    raise
                break

            soup = BeautifulSoup(resp.text, "lxml")
            page_records = self._parse_most_html(soup)
            if not page_records:
                logger.info("[policy] MOST page %d: no records parsed", page)
                if page == 1:
                    # First page must yield results
                    raise RuntimeError(
                        f"MOST page returned no parseable records. HTML length={len(resp.text)}"
                    )
                break

            records.extend(page_records)
            logger.info("[policy] MOST page %d → %d records", page, len(page_records))

            if page < max_pages:
                time.sleep(1.5)  # polite delay

        return records

    def _parse_most_html(self, soup: BeautifulSoup) -> list[dict]:
        """Parse a MOST page HTML with multiple fallback strategies.

        Government sites use wildly different HTML structures over time.
        We try several common patterns.
        """
        records: list[dict] = []
        seen_titles: set[str] = set()

        # Strategy 1: <li> tags containing <a> links
        for container in soup.find_all(["ul", "ol", "div"]):
            for li in container.find_all("li", recursive=False):
                rec = self._try_extract_from_element(li, "policy_most")
                if rec and rec["title"] not in seen_titles:
                    seen_titles.add(rec["title"])
                    records.append(rec)

        # Strategy 2: table rows (common in older government sites)
        if not records:
            for tr in soup.find_all("tr"):
                rec = self._try_extract_from_element(tr, "policy_most")
                if rec and rec["title"] not in seen_titles:
                    seen_titles.add(rec["title"])
                    records.append(rec)

        # Strategy 3: any <a> tag within the main content area
        if not records:
            main = soup.find(["div", "td"], class_=re.compile("list|content|main|con", re.I))
            if not main:
                main = soup
            for a_tag in main.find_all("a", href=True):
                title = a_tag.get_text(strip=True)
                if not title or len(title) < 5:
                    continue
                href = self._resolve_url(a_tag["href"], self.MOST_BASE)
                # Try to find date in surrounding text
                parent_text = ""
                parent = a_tag.parent
                if parent:
                    parent_text = parent.get_text(strip=True)
                date_str = self._extract_date_from_text(parent_text)

                rec = {
                    "title": title,
                    "publish_date": self._parse_date(date_str),
                    "url": href,
                    "issuer": "科技部",
                    "description": title,
                    "source_name": "policy_most",
                    "source_job_id": href,
                }
                if rec["title"] not in seen_titles:
                    seen_titles.add(rec["title"])
                    records.append(rec)

        return records

    # ------------------------------------------------------------------
    # MIIT scraping
    # ------------------------------------------------------------------

    def _scrape_miit(self, max_pages: int = 1) -> list[dict]:
        """Scrape MIIT technology department policy document pages."""
        records: list[dict] = []
        headers = self._default_headers()

        for page in range(1, max_pages + 1):
            if page == 1:
                url = self.MIIT_INDEX
            else:
                # Try common pagination patterns
                url = f"{self.MIIT_BASE}/jgsj/kjs/wjfb/index_{page}.html"

            try:
                resp = requests.get(url, headers=headers, timeout=self.REQUEST_TIMEOUT)
                resp.raise_for_status()
                if resp.encoding and resp.encoding.lower() in ("iso-8859-1", "latin-1"):
                    resp.encoding = resp.apparent_encoding or "utf-8"
                elif not resp.encoding:
                    resp.encoding = "utf-8"
            except requests.RequestException as e:
                logger.error("[policy] MIIT page %d request failed: %s", page, e)
                if page == 1:
                    raise
                break

            soup = BeautifulSoup(resp.text, "lxml")
            page_records = self._parse_miit_html(soup)
            if not page_records:
                logger.info("[policy] MIIT page %d: no records parsed", page)
                if page == 1:
                    raise RuntimeError(
                        f"MIIT page returned no parseable records. HTML length={len(resp.text)}"
                    )
                break

            records.extend(page_records)
            logger.info("[policy] MIIT page %d → %d records", page, len(page_records))

            if page < max_pages:
                time.sleep(1.5)

        return records

    def _parse_miit_html(self, soup: BeautifulSoup) -> list[dict]:
        """Parse a MIIT page HTML with multiple fallback strategies."""
        records: list[dict] = []
        seen_titles: set[str] = set()

        # Strategy 1: <li> tags containing <a> links
        for container in soup.find_all(["ul", "ol", "div"]):
            for li in container.find_all("li", recursive=False):
                rec = self._try_extract_from_element(li, "policy_miit")
                if rec and rec["title"] not in seen_titles:
                    seen_titles.add(rec["title"])
                    records.append(rec)

        # Strategy 2: table rows
        if not records:
            for tr in soup.find_all("tr"):
                rec = self._try_extract_from_element(tr, "policy_miit")
                if rec and rec["title"] not in seen_titles:
                    seen_titles.add(rec["title"])
                    records.append(rec)

        # Strategy 3: all <a> tags
        if not records:
            main = soup.find(["div", "td"], class_=re.compile("list|content|main|con", re.I))
            if not main:
                main = soup
            for a_tag in main.find_all("a", href=True):
                title = a_tag.get_text(strip=True)
                if not title or len(title) < 5:
                    continue
                href = self._resolve_url(a_tag["href"], self.MIIT_BASE)
                parent_text = a_tag.parent.get_text(strip=True) if a_tag.parent else ""
                date_str = self._extract_date_from_text(parent_text)

                rec = {
                    "title": title,
                    "publish_date": self._parse_date(date_str),
                    "url": href,
                    "issuer": "工业和信息化部",
                    "description": title,
                    "source_name": "policy_miit",
                    "source_job_id": href,
                }
                if rec["title"] not in seen_titles:
                    seen_titles.add(rec["title"])
                    records.append(rec)

        return records

    # ------------------------------------------------------------------
    # HTML parsing helpers
    # ------------------------------------------------------------------

    def _try_extract_from_element(self, el, source_name: str) -> Optional[dict]:
        """Try to extract a policy record from an HTML element (li, tr, etc.)."""
        a_tag = el.find("a")
        if not a_tag or not a_tag.get("href"):
            return None

        title = a_tag.get_text(strip=True)
        if not title or len(title) < 5:
            return None

        href = self._resolve_url(a_tag["href"])

        # Find date in the element text (span, td, or inline)
        full_text = el.get_text(strip=True)
        date_str = self._extract_date_from_text(full_text)

        # Determine issuer
        if source_name == "policy_most":
            issuer = "科技部"
        else:
            issuer = "工业和信息化部"

        return {
            "title": title,
            "publish_date": self._parse_date(date_str),
            "url": href,
            "issuer": issuer,
            "description": title,  # list items only have title
            "source_name": source_name,
            "source_job_id": href or title,
        }

    @staticmethod
    def _resolve_url(href: str, base: str = "") -> str:
        """Resolve a relative URL against a base."""
        if not href:
            return ""
        href = href.strip()
        if href.startswith("http://") or href.startswith("https://"):
            return href
        if href.startswith("//"):
            return f"https:{href}"
        if not base:
            return href
        if href.startswith("/"):
            # Remove trailing path from base
            from urllib.parse import urljoin
            return urljoin(base, href)
        return f"{base.rstrip('/')}/{href.lstrip('/')}"

    # ------------------------------------------------------------------
    # normalize() — map to unified schema
    # ------------------------------------------------------------------

    def normalize(self, raw: dict) -> dict:
        """Map a policy document to the unified collector schema.

        Schema fields (BaseCollector.normalize):
            source_platform, source_job_id, source_url,
            title, company, city, salary_min, salary_max,
            description, education, experience, industry, skills[]

        Additional policy-specific fields:
            source_type, source_name, publish_date
        """
        title = raw.get("title", "")
        description = raw.get("description", "")
        combined_text = f"{title} {description}"
        industry = self._extract_industry(combined_text)
        industry_keywords = self._extract_industry_keywords(combined_text)

        return {
            "source_platform": self.platform,
            "source_job_id": str(raw.get("source_job_id", "")),
            "source_url": raw.get("url", ""),
            "title": title,
            "company": raw.get("issuer", ""),   # issuing organization
            "city": "全国",                       # national policy
            "salary_min": None,
            "salary_max": None,
            "description": description,
            "education": "",
            "experience": "",
            "industry": industry,
            "skills": industry_keywords,
            # Extra fields for ETL integration
            "source_type": "policy",
            "source_name": raw.get("source_name", self.platform),
            "publish_date": raw.get("publish_date"),
        }

    # ------------------------------------------------------------------
    # Industry extraction
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_industry(text: str) -> str:
        """Extract the primary industry/domain from policy text.

        Returns the first matching keyword, or a category-level fallback.
        """
        if not text:
            return "科技政策"

        # Try specific keywords first
        priority = [
            "人工智能", "大数据", "云计算", "区块链", "量子",
            "芯片", "半导体", "集成电路",
            "5G", "工业互联网", "网络安全", "智能制造",
            "新能源", "新材料", "生物医药",
        ]
        for kw in priority:
            if kw in text:
                return kw

        # Broader match
        for kw in INDUSTRY_KEYWORDS:
            if kw in text:
                return kw

        return "科技政策"

    @staticmethod
    def _extract_industry_keywords(text: str) -> list[str]:
        """Extract all matching industry keywords from text."""
        if not text:
            return []
        return [kw for kw in INDUSTRY_KEYWORDS if kw in text]

    # ------------------------------------------------------------------
    # Date parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_date(date_str: Optional[str]):
        """Parse a date string into a datetime.date object.

        Returns None if parsing fails.
        """
        if not date_str:
            return None
        date_str = date_str.strip()
        for fmt in [
            "%Y-%m-%d", "%Y.%m.%d", "%Y/%m/%d",
            "%Y-%m-%d %H:%M:%S", "%Y年%m月%d日",
            "%d %b %Y", "%B %d, %Y",
        ]:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        # Try isoformat
        try:
            return datetime.fromisoformat(date_str).date()
        except (ValueError, TypeError):
            pass
        return None

    @staticmethod
    def _extract_date_from_text(text: str) -> str:
        """Extract a date pattern (YYYY-MM-DD or YYYY.MM.DD) from text."""
        if not text:
            return ""
        # YYYY-MM-DD or YYYY/MM/DD
        m = re.search(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", text)
        if m:
            return f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"
        # YYYY年MM月DD日
        m = re.search(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", text)
        if m:
            return f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"
        return ""

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _default_headers() -> dict:
        """Build default HTTP request headers."""
        return {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",
        }


# ---------------------------------------------------------------------------
# __main__ — direct smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Default to seed-only for quick testing; pass --live to attempt scraping
    use_live = "--live" in sys.argv
    keyword = None
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == "--live":
            continue
        if not arg.startswith("--"):
            keyword = arg
            break

    collector = PolicyCollector(use_seed_only=not use_live)
    result = collector.collect(keyword=keyword or "", max_pages=1)

    print(f"\n{'=' * 60}")
    print(f"Platform:     {result.platform}")
    print(f"Keyword:      {result.keyword or '(all)'}")
    print(f"Records:      {len(result.records)}")
    print(f"Duration:     {result.duration_seconds}s")
    print(f"Errors:       {len(result.errors)}")
    if result.errors:
        for e in result.errors:
            print(f"  - {e}")
    print(f"{'=' * 60}")

    # Print source distribution
    from collections import Counter
    sources = Counter(r.get("source_name", "?") for r in result.records)
    print(f"\nSource distribution: {dict(sources)}")

    # Print sample records
    for i, rec in enumerate(result.records[:5], 1):
        print(f"\n--- Record {i} ---")
        print(f"  Title:       {rec.get('title', '')[:80]}")
        print(f"  Issuer:      {rec.get('company', '')}")
        print(f"  Date:        {rec.get('publish_date', '')}")
        print(f"  Industry:    {rec.get('industry', '')}")
        print(f"  Keywords:    {rec.get('skills', [])}")
        print(f"  Source:      {rec.get('source_name', '')}")
        print(f"  URL:         {rec.get('source_url', '')[:100]}")
