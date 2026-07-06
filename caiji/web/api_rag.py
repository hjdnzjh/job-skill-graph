"""RAG QA API endpoint."""

import logging
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from web._settings import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/rag", tags=["rag"])

_rag_engine = None


def _get_engine():
    global _rag_engine
    if _rag_engine is None:
        from kg.rag_engine import RAGEngine
        _rag_engine = RAGEngine(get_settings())
    return _rag_engine


@router.post("/query")
async def rag_query(body: dict):
    """RAG-enhanced question answering.

    Request: {"question": "Python工程师需要什么技能？", "top_k": 5}
    """
    question = body.get("question", "")
    if not question:
        return JSONResponse({"error": "question is required"}, status_code=400)

    top_k = body.get("top_k", 5)
    try:
        engine = _get_engine()
        result = engine.query(question, top_k=top_k)
        return result
    except Exception as exc:
        logger.error(f"RAG query error: {exc}")
        return JSONResponse({"error": str(exc)}, status_code=500)


@router.post("/index")
async def build_rag_index(body: dict = None):
    """Build/rebuild the RAG vector index.

    Request: {"force": false}
    """
    force = body.get("force", False) if body else False
    try:
        engine = _get_engine()
        count = engine.build_index(force=force)
        return {"status": "ok", "document_count": count}
    except Exception as exc:
        logger.error(f"RAG index error: {exc}")
        return JSONResponse({"error": str(exc)}, status_code=500)
