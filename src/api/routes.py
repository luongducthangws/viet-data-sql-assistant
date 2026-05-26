"""
src/api/routes.py - Định nghĩa tất cả API endpoints
"""

import logging

from fastapi import APIRouter, Depends, HTTPException

from src.api.schemas import (
    AskRequest,
    AskResponse,
    HealthResponse,
    LLMTestResponse,
    SchemaResponse,
)
from src.database.connection import check_connection_detail
from src.database.schema_inspector import get_table_names, load_schema
from src.llm.client import call_llm, get_llm_status

logger = logging.getLogger(__name__)
router = APIRouter()


def get_chain():
    """Dependency injection - lấy SQLChain singleton từ app state."""
    from src.api.main import app

    if not hasattr(app.state, "chain") or app.state.chain is None:
        raise HTTPException(status_code=503, detail="Chain chưa sẵn sàng")
    return app.state.chain


@router.get("/health", response_model=HealthResponse, tags=["system"])
async def health():
    """Health check - Railway chỉ cần 200, chi tiết DB/chain là bonus."""
    from src.api.main import app

    db_ok, db_error = check_connection_detail()
    chain_ready = hasattr(app.state, "chain") and app.state.chain is not None
    llm_status = get_llm_status()
    return HealthResponse(
        status="ok" if db_ok and llm_status["configured"] else "degraded",
        db_connected=db_ok,
        chain_ready=chain_ready,
        db_error=db_error,
        llm_provider=llm_status["provider"],
        llm_configured=llm_status["configured"],
        llm_error=llm_status["error"],
    )


@router.get("/schema", response_model=SchemaResponse, tags=["system"])
async def schema():
    """Trả về danh sách bảng trong database."""
    schema_data = load_schema(from_cache=True)
    tables = get_table_names(schema_data)
    return SchemaResponse(tables=tables, total_tables=len(tables))


@router.get("/llm-test", response_model=LLMTestResponse, tags=["system"])
async def llm_test():
    """One-shot provider check for deployment diagnostics."""
    llm_status = get_llm_status()
    if not llm_status["configured"]:
        return LLMTestResponse(
            provider=llm_status["provider"],
            configured=False,
            ok=False,
            error=llm_status["error"],
        )

    try:
        response = call_llm(
            user_prompt="Tra loi dung mot tu: OK",
            system_prompt="You are a concise assistant.",
            temperature=0.0,
            max_tokens=8,
        )
        return LLMTestResponse(
            provider=llm_status["provider"],
            configured=True,
            ok=True,
            response=response,
        )
    except Exception as exc:
        return LLMTestResponse(
            provider=llm_status["provider"],
            configured=True,
            ok=False,
            error_type=type(exc).__name__,
            error=str(exc).splitlines()[0][:300],
        )


@router.post("/ask", response_model=AskResponse, tags=["chat"])
async def ask(req: AskRequest, chain=Depends(get_chain)):
    """
    Endpoint chính - nhận câu hỏi tiếng Việt, trả về câu trả lời + SQL đã dùng.
    """
    try:
        result = chain.ask(question=req.question, debug=req.debug)
        return AskResponse(
            question=req.question,
            answer=result.answer,
            sql=result.sql,
            row_count=result.row_count,
            attempts=result.attempts,
            success=result.success,
            debug=result.debug if req.debug else None,
        )
    except Exception as e:
        logger.error("Chain error: %s", e, exc_info=True)
        detail = f"Lỗi xử lý câu hỏi: {e}"
        if req.debug:
            detail = f"{detail} ({type(e).__name__})"
        raise HTTPException(status_code=500, detail=detail)
