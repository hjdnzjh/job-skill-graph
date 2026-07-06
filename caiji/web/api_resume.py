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

from web._settings import get_settings

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
        # Extract known skills from text via keyword matching
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
