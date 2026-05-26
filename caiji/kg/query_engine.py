"""Text-to-Cypher query engine for natural language graph queries.

Converts Chinese questions into Cypher queries via LLM, executes against
Neo4j, and formats results as natural language answers.
"""

import logging
import re
from typing import Any, Dict, List

from openai import OpenAI

from kg.neo4j_client import Neo4jClient
from kg.prompts import build_messages

logger = logging.getLogger(__name__)

# Destructive Cypher keywords to block
_FORBIDDEN_KEYWORDS = re.compile(
    r'\b(CREATE|DELETE|DETACH|SET|REMOVE|MERGE|DROP|CALL|LOAD)\b',
    re.IGNORECASE,
)

# Chinese column label lookup for _format_answer
_COLUMN_LABELS = {
    "company": "公司", "skill": "技能", "demand": "需求量",
    "job_count": "职位数", "job_title": "职位名称", "city": "城市",
    "industry": "行业", "avg_min": "平均最低薪资", "avg_max": "平均最高薪资",
    "name": "名称", "count": "数量", "category": "类别",
    "province": "省份", "weight": "权重", "salary_min": "最低薪资",
    "salary_max": "最高薪资", "quality_score": "质量评分",
    "source_name": "来源", "education": "学历要求",
}


class TextToCypherEngine:
    """Natural language → Cypher → Neo4j → formatted answer pipeline."""

    def __init__(self, settings):
        self.settings = settings
        self._neo4j = None
        self._llm_client = None

    def query(self, question: str) -> Dict[str, Any]:
        """Run the full NL-to-answer pipeline.

        Returns a dict with keys: question, cypher, data, answer, error.
        """
        result = {"question": question}

        try:
            cypher = self._generate_cypher(question)
            result["cypher"] = cypher

            if not self._validate_cypher(cypher):
                result["error"] = "生成的 Cypher 包含危险操作，已拦截"
                return result

            data = self._execute_cypher(cypher)
            result["data"] = data
            result["answer"] = self._format_answer(data)
            result["error"] = None

        except Exception as exc:
            logger.error(f"Query failed: {exc}")
            result["error"] = str(exc)
            result.setdefault("cypher", "")
            result.setdefault("data", [])
            result.setdefault("answer", "")

        return result

    # ------------------------------------------------------------------
    # Private methods
    # ------------------------------------------------------------------

    def _generate_cypher(self, question: str) -> str:
        """Call LLM to translate question into Cypher."""
        if self._llm_client is None:
            self._llm_client = OpenAI(
                api_key=self.settings.llm_api_key,
                base_url=self.settings.llm_base_url,
            )

        messages = build_messages(question)

        response = self._llm_client.chat.completions.create(
            model=self.settings.llm_model,
            messages=messages,
            temperature=self.settings.llm_temperature,
        )

        content = response.choices[0].message.content.strip()

        # Strip markdown code fences if present
        content = re.sub(r'^```(?:cypher|sql)?\s*\n?', '', content)
        content = re.sub(r'\n?```\s*$', '', content)
        content = content.strip()

        if content.upper() == "UNSUPPORTED":
            raise ValueError("无法将这个问题转换为 Cypher 查询")

        logger.debug(f"Generated Cypher: {content}")
        return content

    @staticmethod
    def _validate_cypher(cypher: str) -> bool:
        """Reject queries containing destructive operations."""
        if _FORBIDDEN_KEYWORDS.search(cypher):
            logger.warning(f"Blocked destructive Cypher: {cypher}")
            return False
        # Must start with MATCH (whitespace-tolerant)
        if not re.match(r'^\s*MATCH\b', cypher, re.IGNORECASE):
            logger.warning(f"Blocked non-MATCH Cypher: {cypher}")
            return False
        return True

    def _execute_cypher(self, cypher: str) -> list:
        """Execute validated Cypher against Neo4j."""
        if self._neo4j is None:
            self._neo4j = Neo4jClient(self.settings)

        rows = self._neo4j.run_query(cypher)
        return rows[:100] if len(rows) > 100 else rows

    @staticmethod
    def _format_answer(data: list) -> str:
        """Format result rows into a natural Chinese answer."""
        if not data:
            return "未找到相关结果。"

        if len(data) == 1:
            row = data[0]
            keys = list(row.keys())
            if len(keys) == 1:
                val = row[keys[0]]
                label = _COLUMN_LABELS.get(keys[0], keys[0])
                return f"{label}：{val}"
            else:
                parts = []
                for k in keys:
                    label = _COLUMN_LABELS.get(k, k)
                    val = row[k]
                    if isinstance(val, float):
                        val = f"{val:,.0f}"
                    parts.append(f"{label}：{val}")
                return "，".join(parts)

        # Multiple rows: numbered list
        lines = []
        for i, row in enumerate(data, 1):
            keys = list(row.keys())
            if len(keys) == 1:
                val = row[keys[0]]
                label = _COLUMN_LABELS.get(keys[0], keys[0])
                lines.append(f"{i}. {label}：{val}")
            elif len(keys) == 2:
                a, b = keys
                la = _COLUMN_LABELS.get(a, a)
                lb = _COLUMN_LABELS.get(b, b)
                lines.append(f"{i}. {la}：{row[a]}，{lb}：{row[b]}")
            else:
                parts = []
                for k in keys:
                    lk = _COLUMN_LABELS.get(k, k)
                    v = row[k]
                    if isinstance(v, float):
                        v = f"{v:,.0f}"
                    parts.append(f"{lk}：{v}")
                lines.append(f"{i}. " + "，".join(parts))

        return "\n".join(lines)

    def close(self):
        """Close Neo4j driver connection."""
        if self._neo4j:
            self._neo4j.close()
            self._neo4j = None
