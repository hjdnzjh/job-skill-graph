"""Resume parser: extract structured info from PDF/Word resumes via LLM."""

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

from openai import OpenAI

logger = logging.getLogger(__name__)

EXTRACT_PROMPT = """你是一个简历解析专家。从以下简历文本中提取结构化信息。

## 输出格式
返回纯 JSON，不要 markdown 代码块，不要其他文字：
{
  "name": "姓名",
  "skills": ["技能1", "技能2", ...],
  "years_of_experience": 工作年数(数字),
  "education": "最高学历",
  "current_title": "当前/最近职位",
  "target_titles": ["意向岗位1", ...] 或空数组
}

## 规则
- 技能名使用标准通用名称（如 "Python" 而非 "python编程"，"Java" 而非 "java开发"）
- 如果简历中未提及某项，填 null 或空数组
- 只提取明确列出的技能，不要推测"""


class ResumeParser:
    """Parse PDF/Word resumes and extract structured skill profiles."""

    def __init__(self, settings):
        self.settings = settings
        self._neo4j = None
        self._llm_client = None

    @property
    def neo4j(self):
        if self._neo4j is None:
            from kg.neo4j_client import Neo4jClient
            self._neo4j = Neo4jClient(self.settings)
        return self._neo4j

    @property
    def llm(self):
        if self._llm_client is None:
            self._llm_client = OpenAI(
                api_key=self.settings.llm_api_key,
                base_url=self.settings.llm_base_url,
            )
        return self._llm_client

    def close(self):
        if self._neo4j:
            self._neo4j.close()

    # ------------------------------------------------------------------
    # File reading
    # ------------------------------------------------------------------

    @staticmethod
    def read_file(filepath: str) -> str:
        """Extract plain text from PDF, DOCX, or TXT file.

        Returns the full text content.
        """
        ext = os.path.splitext(filepath)[1].lower()

        if ext == ".pdf":
            import fitz
            doc = fitz.open(filepath)
            pages = [page.get_text() for page in doc]
            doc.close()
            return "\n".join(pages)

        elif ext in (".docx", ".doc"):
            from docx import Document
            doc = Document(filepath)
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            return "\n".join(paragraphs)

        elif ext == ".txt":
            with open(filepath, "r", encoding="utf-8") as f:
                return f.read()

        else:
            raise ValueError(f"Unsupported file format: {ext}")

    # ------------------------------------------------------------------
    # LLM extraction
    # ------------------------------------------------------------------

    def extract(self, text: str) -> dict:
        """Use LLM to extract structured resume info from text.

        Returns dict with keys: name, skills, years_of_experience, education,
        current_title, target_titles, raw_text.
        """
        # Truncate long text to avoid token limits
        truncated = text[:4000] if len(text) > 4000 else text

        messages = [
            {"role": "system", "content": EXTRACT_PROMPT},
            {"role": "user", "content": truncated},
        ]

        response = self.llm.chat.completions.create(
            model=self.settings.llm_model,
            messages=messages,
            temperature=0.0,
        )

        content = response.choices[0].message.content.strip()
        content = re.sub(r'^```(?:json)?\s*\n?', '', content)
        content = re.sub(r'\n?```\s*$', '', content)

        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            logger.warning("Failed to parse LLM resume output, using raw extraction")
            result = {"name": "", "skills": [], "education": ""}

        result["raw_text"] = text
        # Ensure skills is a list
        if not isinstance(result.get("skills"), list):
            result["skills"] = []
        return result

    # ------------------------------------------------------------------
    # Fallback parsing (no LLM)
    # ------------------------------------------------------------------

    def has_llm(self) -> bool:
        """Check whether LLM API key is configured."""
        return bool(self.settings.llm_api_key)

    def parse_with_fallback(self, text: str,
                            skills_from_text: list = None) -> dict:
        """Parse resume with LLM if available, otherwise use keyword fallback.

        Args:
            text: Raw text from resume file.
            skills_from_text: Pre-extracted skills from keyword scanning.

        Returns:
            Dict with keys: name, skills, years_of_experience, education,
            current_title, target_titles, method.
        """
        if self.has_llm():
            try:
                result = self.extract(text)
                result["method"] = "llm"
                return result
            except Exception as exc:
                logger.warning(f"LLM extraction failed, falling back: {exc}")

        # Keyword fallback
        result = {
            "name": "",
            "skills": skills_from_text or [],
            "years_of_experience": None,
            "education": "",
            "current_title": "",
            "target_titles": [],
            "raw_text": text[:500],
            "method": "keyword_fallback",
        }
        # Try to extract years with simple regex
        import re
        exp_match = re.search(r'(\d+)\s*[年岁]', text)
        if exp_match:
            result["years_of_experience"] = int(exp_match.group(1))

        return result

    # ------------------------------------------------------------------
    # Skill alignment to knowledge graph
    # ------------------------------------------------------------------

    def align_skills(self, skills: List[str]) -> List[str]:
        """Align extracted skill names to Neo4j Skill nodes via fuzzy match.

        For each skill, try exact match first, then fuzzy match against
        all Skill nodes in the graph. Returns list of canonical skill names.
        """
        # Get all known skills from Neo4j
        rows = self.neo4j.run_query("MATCH (s:Skill) RETURN s.name AS name")
        known_skills = [r["name"] for r in rows]

        if not known_skills:
            return skills  # No graph to align against, return as-is

        aligned = []
        for skill in skills:
            # Try case-insensitive exact match
            matches = [k for k in known_skills if k.lower() == skill.lower()]
            if matches:
                aligned.append(matches[0])
                continue

            # Try substring match
            matches = [k for k in known_skills
                       if skill.lower() in k.lower() or k.lower() in skill.lower()]
            if matches:
                aligned.append(matches[0])
                continue

            # Fuzzy match via SequenceMatcher
            from difflib import SequenceMatcher
            best = max(known_skills,
                       key=lambda k: SequenceMatcher(None, skill.lower(), k.lower()).ratio())
            score = SequenceMatcher(None, skill.lower(), best.lower()).ratio()
            if score >= 0.75:
                aligned.append(best)
            else:
                # Keep original — may be a skill not yet in the graph
                aligned.append(skill)

        return aligned
