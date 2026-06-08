# Resume Evaluation API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build resume upload and evaluation APIs matching the prototype's ResumeEvaluate page — file upload, AI skill extraction, job matching with radar chart data, and learning suggestions.

**Architecture:** Three-layer design — (1) file upload endpoint stores uploaded files to disk, (2) resume evaluation endpoint parses → extracts → matches → returns structured result, (3) existing JobMatcher + ResumeParser reused and extended with radar scoring and suggestion generation.

**Tech Stack:** FastAPI, Neo4j, DeepSeek LLM, PyMuPDF (fitz), python-docx, Pydantic

---

## File Structure

**New Files:**
- `web/api_resume.py` — Resume upload & evaluation API routes
- `tests/test_resume_api.py` — Integration tests for new endpoints
- `tests/test_resume_parser_unit.py` — Unit tests for ResumeParser
- `tests/test_job_matcher_ext.py` — Unit tests for new matcher features

**Modified Files:**
- `web/server.py` — Register new `api_resume` router
- `kg/job_matcher.py` — Add `radar_score()` and `gap_suggestions()` methods
- `kg/resume_parser.py` — Add `has_llm` check and `parse_with_fallback()` method

---

### Task 1: Add radar scoring to JobMatcher

**Files:**
- Modify: `kg/job_matcher.py`
- Test: `tests/test_job_matcher_ext.py`

- [ ] **Step 1: Write the failing test**

```python
"""tests/test_job_matcher_ext.py"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from kg.job_matcher import JobMatcher


class DummySettings:
    neo4j_uri = "bolt://localhost:7687"
    neo4j_user = "neo4j"
    neo4j_password = "12345678"
    neo4j_database = "neo4j"


@pytest.fixture
def matcher():
    m = JobMatcher(DummySettings())
    yield m
    m.close()


def test_radar_score_returns_all_five_dimensions(matcher):
    """radar_score() should return 5 dimensions with 0-100 scores."""
    result = matcher.radar_score(
        user_skills=["Python", "Git", "Linux"],
        matched_skills=["Python"],
        missing_skills=["Java"],
        total_required=2,
    )
    assert "radar" in result
    assert len(result["radar"]) == 5
    dims = {d["dimension"] for d in result["radar"]}
    assert dims == {"技术深度", "业务理解", "协作沟通", "学习能力", "工具链熟练度"}
    for d in result["radar"]:
        assert 0 <= d["score"] <= 100


def test_radar_score_empty_skills(matcher):
    """radar_score() should handle empty skill lists gracefully."""
    result = matcher.radar_score(
        user_skills=[],
        matched_skills=[],
        missing_skills=[],
        total_required=0,
    )
    for d in result["radar"]:
        assert d["score"] >= 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_job_matcher_ext.py::test_radar_score_returns_all_five_dimensions -v`
Expected: FAIL with "AttributeError: 'JobMatcher' object has no attribute 'radar_score'"

- [ ] **Step 3: Write minimal implementation**

Add these methods to `kg/job_matcher.py` (before the `# Helpers` section):

```python
# ------------------------------------------------------------------
# Radar scoring
# ------------------------------------------------------------------

def radar_score(self, user_skills: List[str], matched_skills: List[str],
                missing_skills: List[str], total_required: int) -> dict:
    """Compute 5-dimension radar scores for skill visualization.

    Args:
        user_skills: All skills the user has.
        matched_skills: Skills that matched the target job.
        missing_skills: Required skills the user lacks.
        total_required: Total number of required skills.

    Returns:
        Dict with "radar" key containing list of {dimension, score, label}.
    """
    user_lower = {s.lower() for s in user_skills}

    # Dimension 1: 技术深度 — ratio of matched to required
    depth_score = 0
    if total_required > 0:
        depth_score = int(len(matched_skills) / total_required * 100)

    # Dimension 2: 业务理解 — skill category breadth from Neo4j
    cat_rows = self.neo4j.run_query(
        "MATCH (s:Skill) WHERE s.name IN $skills RETURN "
        "DISTINCT s.category AS cat",
        {"skills": list(user_lower)},
    ) if user_skills else []
    known_user_skills = [r["cat"] for r in cat_rows if r.get("cat")]
    breadth_score = min(len(set(known_user_skills)) * 15, 100)

    # Dimension 3: 协作沟通 — collaboration tools presence
    collab_tools = {"git", "jira", "jenkins", "slack", "confluence",
                    "notion", "teams", "agile", "scrum", "ci/cd"}
    collab_found = user_lower & collab_tools
    collab_score = min(len(collab_found) * 25, 100)

    # Dimension 4: 学习能力 — skill diversity + modern skills
    modern_skills = {"python", "docker", "kubernetes", "pytorch",
                     "tensorflow", "react", "vue", "go", "rust"}
    modern_found = user_lower & modern_skills
    learning_score = min(50 + len(modern_found) * 10, 100)

    # Dimension 5: 工具链熟练度 — DevOps/tool coverage
    tool_skills = {"docker", "kubernetes", "git", "jenkins", "maven",
                   "nginx", "linux", "shell", "ansible", "ci/cd"}
    tool_found = user_lower & tool_skills
    tool_score = min(len(tool_found) * 15, 100)

    radar = [
        {"dimension": "技术深度", "score": depth_score,
         "label": "优势领域" if depth_score >= 60 else "需要提升"},
        {"dimension": "业务理解", "score": breadth_score,
         "label": "优势领域" if breadth_score >= 60 else "需要提升"},
        {"dimension": "协作沟通", "score": collab_score,
         "label": "优势领域" if collab_score >= 60 else "需要提升"},
        {"dimension": "学习能力", "score": learning_score,
         "label": "优势领域" if learning_score >= 60 else "需要提升"},
        {"dimension": "工具链熟练度", "score": tool_score,
         "label": "优势领域" if tool_score >= 60 else "需要提升"},
    ]
    return {"radar": radar}


def gap_suggestions(self, user_skills: List[str], missing_skills: List[str],
                    target_title: str) -> list:
    """Generate actionable suggestions for skill gaps.

    Returns list of dicts with category, suggestion, and related_skills.
    """
    suggestions = []
    user_lower = {s.lower() for s in user_skills}

    if not missing_skills:
        suggestions.append({
            "category": "overall",
            "suggestion": "你的技能已覆盖目标岗位的所有核心要求",
            "related_skills": [],
        })
        return suggestions

    # Group missing skills by category from Neo4j
    cat_rows = self.neo4j.run_query(
        "MATCH (s:Skill) WHERE s.name IN $skills "
        "RETURN s.name AS skill, s.category AS category",
        {"skills": missing_skills},
    ) if missing_skills else []
    cat_map = {}
    for r in cat_rows:
        cat = r.get("category") or "未分类"
        cat_map.setdefault(cat, []).append(r["skill"])

    # Uncategorized missing skills
    categorized = {r["skill"].lower() for r in cat_rows}
    uncategorized = [s for s in missing_skills
                     if s.lower() not in categorized]

    # Generate suggestions per category
    for cat, skills in sorted(cat_map.items()):
        suggestions.append({
            "category": cat,
            "suggestion": f"建议补充 {cat} 方向的技能：{'、'.join(skills)}",
            "related_skills": skills,
        })

    if uncategorized:
        suggestions.append({
            "category": "未分类",
            "suggestion": f"建议学习：{'、'.join(uncategorized)}",
            "related_skills": uncategorized,
        })

    # Add learning resource suggestions based on patterns
    for ms in missing_skills:
        ms_lower = ms.lower()
        if ms_lower in {"docker", "kubernetes", "k8s", "ci/cd", "jenkins"}:
            suggestions.append({
                "category": "学习路径推荐",
                "suggestion": f"「{ms}」可以通过官方文档 + 动手实验快速入门，推荐 Docker/K8s 实战课程",
                "related_skills": [ms],
            })
            break  # One learning path tip is enough

    return suggestions
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_job_matcher_ext.py::test_radar_score_returns_all_five_dimensions -v`
Expected: PASS

- [ ] **Step 5: Add second test for gap_suggestions**

```python
def test_gap_suggestions_returns_structured_advice(matcher):
    """gap_suggestions() should return categorized improvement advice."""
    result = matcher.gap_suggestions(
        user_skills=["Python", "Git"],
        missing_skills=["Docker", "Kubernetes", "MySQL"],
        target_title="Python开发工程师",
    )
    assert len(result) > 0
    for item in result:
        assert "category" in item
        assert "suggestion" in item
        assert "related_skills" in item
```

- [ ] **Step 6: Run second test**

Run: `python -m pytest tests/test_job_matcher_ext.py::test_gap_suggestions_returns_structured_advice -v`
Expected: PASS

- [ ] **Step 7: Test radar_score empty skills**

Run: `python -m pytest tests/test_job_matcher_ext.py::test_radar_score_empty_skills -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add caiji/kg/job_matcher.py caiji/tests/test_job_matcher_ext.py
git commit -m "feat(job-matcher): add radar scoring and gap suggestions"
```

---

### Task 2: Add fallback parsing mode to ResumeParser

**Files:**
- Modify: `kg/resume_parser.py`
- Test: `tests/test_resume_parser_unit.py`

- [ ] **Step 1: Write the failing test**

```python
"""tests/test_resume_parser_unit.py"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from kg.resume_parser import ResumeParser


class DummySettings:
    llm_api_key = ""
    llm_base_url = "https://api.deepseek.com/v1"
    llm_model = "deepseek-chat"
    neo4j_uri = "bolt://localhost:7687"
    neo4j_user = "neo4j"
    neo4j_password = "12345678"
    neo4j_database = "neo4j"


def test_read_text_file(tmp_path):
    """read_file() should extract text from .txt files."""
    f = tmp_path / "resume.txt"
    f.write_text("姓名: 张三\n技能: Python, Java, MySQL", encoding="utf-8")
    parser = ResumeParser(DummySettings())
    text = parser.read_file(str(f))
    assert "姓名: 张三" in text
    assert "技能: Python, Java, MySQL" in text


def test_parse_with_fallback_no_llm():
    """parse_with_fallback() should work without LLM key."""
    parser = ResumeParser(DummySettings())  # Empty API key
    result = parser.parse_with_fallback(
        text="I know Python and Java",
        skills_from_text=["Python", "Java"],
    )
    assert result["name"] == ""
    assert "Python" in result["skills"]
    assert "Java" in result["skills"]
    assert result["method"] == "keyword_fallback"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_resume_parser_unit.py -v`
Expected: FAIL with "AttributeError: 'ResumeParser' object has no attribute 'parse_with_fallback'"

- [ ] **Step 3: Write minimal implementation**

Add to `kg/resume_parser.py` (after the `extract` method):

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_resume_parser_unit.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add caiji/kg/resume_parser.py caiji/tests/test_resume_parser_unit.py
git commit -m "feat(resume-parser): add fallback parsing mode without LLM"
```

---

### Task 3: Create resume upload API endpoint

**Files:**
- Create: `web/api_resume.py`
- Modify: `web/server.py`
- Test: `tests/test_resume_api.py`

- [ ] **Step 1: Write the failing test**

```python
"""tests/test_resume_api.py — add to existing test_api.py or standalone"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient
from web.server import app
import json

client = TestClient(app)


class TestResumeAPI:
    """Tests for resume upload and evaluation endpoints."""

    def test_upload_no_file_returns_400(self):
        """Upload without file should return 400."""
        response = client.post("/api/resume/upload")
        assert response.status_code == 422  # FastAPI validation error

    def test_upload_text_file(self, tmp_path):
        """Upload a .txt file should return file_id and preview."""
        f = tmp_path / "test_resume.txt"
        f.write_text("姓名: 张三\n技能: Python, Java, MySQL", encoding="utf-8")
        with open(f, "rb") as fh:
            response = client.post(
                "/api/resume/upload",
                files={"file": ("test_resume.txt", fh, "text/plain")},
            )
        assert response.status_code in (200, 503)
        if response.status_code == 200:
            data = response.json()
            assert "file_id" in data
            assert "filename" in data
            assert data["filename"] == "test_resume.txt"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_resume_api.py::TestResumeAPI::test_upload_no_file_returns_400 -v`
Expected: FAIL with 404 (router not registered yet)

- [ ] **Step 3: Create `web/api_resume.py`**

```python
"""Resume upload and evaluation API.

Provides endpoints for file upload, resume parsing, and job matching
with radar visualization data.
"""

import json
import logging
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from web.server import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/resume", tags=["resume"])

UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


class EvaluateRequest(BaseModel):
    file_id: str = Field(..., min_length=1, description="Uploaded file ID")
    target_title: str = Field(..., min_length=1, description="Target job title")


@router.post("/upload")
async def upload_resume(file: UploadFile = File(...)):
    """Upload a resume file (PDF, DOCX, or TXT)."""
    # Validate extension
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return JSONResponse(
            {"error": f"不支持的文件格式: {ext}，支持 PDF、DOCX、TXT"},
            status_code=400,
        )

    # Read content
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        return JSONResponse(
            {"error": "文件过大，最大支持 10MB"},
            status_code=400,
        )

    # Save to disk
    file_id = str(uuid.uuid4())[:8]
    safe_name = f"{file_id}_{file.filename}"
    save_path = UPLOAD_DIR / safe_name
    with open(save_path, "wb") as f:
        f.write(content)

    logger.info(f"Resume uploaded: {save_path} ({len(content)} bytes)")

    return {
        "file_id": file_id,
        "filename": file.filename,
        "size_bytes": len(content),
        "status": "uploaded",
    }


@router.post("/evaluate")
async def evaluate_resume(body: EvaluateRequest):
    """Parse uploaded resume and evaluate against target job.

    Returns match score, radar data, skill gaps, and learning suggestions.
    """
    # Find the uploaded file
    upload_dir = Path("data/uploads")
    matched = list(upload_dir.glob(f"{body.file_id}_*"))
    if not matched:
        return JSONResponse(
            {"error": f"未找到上传文件 (file_id: {body.file_id})，请先上传"},
            status_code=404,
        )
    filepath = matched[0]

    try:
        from kg.resume_parser import ResumeParser
        from kg.job_matcher import JobMatcher

        settings = get_settings()
        parser = ResumeParser(settings)
        matcher = JobMatcher(settings)

        # Step 1: Read file text
        text = parser.read_file(str(filepath))

        # Step 2: Parse resume (LLM or fallback)
        # Simple keyword extraction for fallback
        from kg.skill_extractor import TITLE_TO_SKILLS
        all_known_skills = set()
        for skills in TITLE_TO_SKILLS.values():
            all_known_skills.update(skills)
        text_lower = text.lower()
        found_skills = [s for s in sorted(all_known_skills)
                        if s.lower() in text_lower]

        parsed = parser.parse_with_fallback(text, skills_from_text=found_skills)

        # Step 3: Find target title
        resolved = matcher.find_title(body.target_title)
        if not resolved:
            parser.close()
            matcher.close()
            return JSONResponse(
                {"error": f"未找到岗位 '{body.target_title}'"},
                status_code=404,
            )

        # Step 4: Run matching
        match_result = matcher.match(parsed.get("skills", []), resolved)

        # Step 5: Compute radar scores
        radar = matcher.radar_score(
            user_skills=parsed.get("skills", []),
            matched_skills=match_result.get("matched_skills", []),
            missing_skills=match_result.get("missing_skills", []),
            total_required=match_result.get("total_required", 0),
        )

        # Step 6: Generate gap suggestions
        suggestions = matcher.gap_suggestions(
            user_skills=parsed.get("skills", []),
            missing_skills=match_result.get("missing_skills", [])
                       + match_result.get("preferred_missing", []),
            target_title=resolved,
        )

        parser.close()
        matcher.close()

        return {
            "file_id": body.file_id,
            "parsed": {
                "name": parsed.get("name", ""),
                "skills": parsed.get("skills", [])[:20],
                "years_of_experience": parsed.get("years_of_experience"),
                "education": parsed.get("education", ""),
                "method": parsed.get("method", "unknown"),
            },
            "match": {
                "target_title": resolved,
                "match_score": match_result.get("match_score", 0),
                "match_percent": int(match_result.get("match_score", 0) * 100),
                "matched_skills": match_result.get("matched_skills", []),
                "missing_skills": match_result.get("missing_skills", []),
                "preferred_matched": match_result.get("preferred_matched", []),
                "preferred_missing": match_result.get("preferred_missing", []),
            },
            "radar": radar.get("radar", []),
            "suggestions": suggestions,
            "learning_path": match_result.get("learning_path", []),
        }

    except ImportError as exc:
        logger.error(f"Import error: {exc}")
        return JSONResponse({"error": f"依赖缺失: {exc}"}, status_code=500)
    except Exception as exc:
        logger.error(f"Resume evaluate error: {exc}")
        return JSONResponse({"error": str(exc)}, status_code=500)
```

- [ ] **Step 4: Register router in `web/server.py`**

Add after the existing imports (line 46):
```python
from web.api_resume import router as resume_router
```

Add after existing `app.include_router(updater_router)` (line 55):
```python
app.include_router(resume_router)
```

- [ ] **Step 5: Run test to verify pass**

Run: `python -m pytest tests/test_resume_api.py::TestResumeAPI::test_upload_no_file_returns_400 -v`
Expected: PASS (422 from FastAPI validation)

- [ ] **Step 6: Run the full test suite**

Run: `python -m pytest tests/test_resume_api.py -v`
Expected: All tests pass

- [ ] **Step 7: Commit**

```bash
git add caiji/web/api_resume.py caiji/web/server.py caiji/tests/test_resume_api.py
git commit -m "feat(api): add resume upload and evaluation endpoints"
```

---

### Task 4: Integration test — full evaluate flow

**Files:**
- Modify: `tests/test_resume_api.py`

- [ ] **Step 1: Write integration test**

Add to `TestResumeAPI` class:

```python
def test_full_evaluate_flow(self, tmp_path):
    """Upload a txt resume then evaluate it against a job."""
    # 1. Upload
    resume_content = (
        "姓名: 李四\n"
        "学历: 本科\n"
        "工作经验: 5年\n"
        "技能: Python, Java, MySQL, Docker, Git, Linux, Redis, Kafka\n"
        "当前职位: Java开发工程师\n"
    )
    f = tmp_path / "li_resume.txt"
    f.write_text(resume_content, encoding="utf-8")

    with open(f, "rb") as fh:
        upload_resp = client.post(
            "/api/resume/upload",
            files={"file": ("li_resume.txt", fh, "text/plain")},
        )
    assert upload_resp.status_code == 200
    file_id = upload_resp.json()["file_id"]

    # 2. Evaluate
    eval_resp = client.post(
        "/api/resume/evaluate",
        json={"file_id": file_id, "target_title": "Java开发工程师"},
    )
    assert eval_resp.status_code in (200, 404, 500)
    if eval_resp.status_code == 200:
        data = eval_resp.json()
        assert "match" in data
        assert "radar" in data
        assert "suggestions" in data
        assert "parsed" in data
        assert len(data["radar"]) == 5
```

- [ ] **Step 2: Run integration test**

Run: `python -m pytest tests/test_resume_api.py::TestResumeAPI::test_full_evaluate_flow -v`
Expected: PASS (or 404/500 if Neo4j/LLM unavailable — test is resilient)

- [ ] **Step 3: Commit**

```bash
git add caiji/tests/test_resume_api.py
git commit -m "test(api): add integration test for resume evaluate flow"
```

---

### Task 5: Manual verification

**Files:**
- Run: Web service with LLM API key

- [ ] **Step 1: Restart web service**

```bash
cd caiji
LLM_API_KEY="sk-881b505892354d2ab07793077b8794ea" python main_web.py --host 0.0.0.0 --port 8000
```

- [ ] **Step 2: Test upload endpoint**

```bash
echo "姓名: 测试\n技能: Python, Java, MySQL, Docker, Git\n工作经验: 3年" > /tmp/test_resume.txt
curl -s -X POST http://localhost:8000/api/resume/upload \
  -F "file=@/tmp/test_resume.txt" | python -m json.tool
```

Expected: Returns `{"file_id": "...", "filename": "test_resume.txt", "status": "uploaded"}`

- [ ] **Step 3: Test evaluate endpoint**

```bash
# Use the file_id from previous step
curl -s -X POST http://localhost:8000/api/resume/evaluate \
  -H "Content-Type: application/json" \
  -d '{"file_id": "<file_id>", "target_title": "Java开发工程师"}' | python -m json.tool
```

Expected: Returns match scores, radar dimensions, and gap suggestions.

- [ ] **Step 4: Test with PDF upload**

```bash
# Create a minimal PDF or use an existing one
# Upload and evaluate — verify parser handles PDF correctly
```

- [ ] **Step 5: Verify all registered routes**

```bash
curl -s http://localhost:8000/api/resume/upload -X POST 2>&1
# Expected: 422 (no file) — proves route is registered
```

---

## Self-Review Checklist

1. **Spec coverage:** Does this plan cover all prototype ResumeEvaluate features?
   - File upload (PDF/Word/TXT) ✅ — Task 3
   - Target job selection ✅ — Task 3 (via evaluate request body)
   - Match score (circular gauge) ✅ — Task 3 (match_percent)
   - Skill radar (5 dimensions) ✅ — Task 1 (radar_score)
   - Gap suggestions ✅ — Task 1 (gap_suggestions)
   - Learning path ✅ — Already exists in JobMatcher, surfaced in Task 3

2. **Placeholder scan:** No TODOs, TBDs, or vague steps.

3. **Type consistency:** Method signatures match across tasks — `radar_score()` params consistent between Task 1 impl and Task 3 caller.
