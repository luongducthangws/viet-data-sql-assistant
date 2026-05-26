"""
src/api/routes.py - Định nghĩa tất cả API endpoints
"""

import logging

from fastapi import APIRouter, Depends, HTTPException

from src.api.schemas import AskRequest, AskResponse, HealthResponse, SchemaResponse
from src.database.connection import check_connection
from src.database.schema_inspector import get_table_names, load_schema

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

    db_ok = check_connection()
    chain_ready = hasattr(app.state, "chain") and app.state.chain is not None
    return HealthResponse(
        status="ok" if db_ok else "degraded",
        db_connected=db_ok,
        chain_ready=chain_ready,
    )


@router.get("/schema", response_model=SchemaResponse, tags=["system"])
async def schema():
    """Trả về danh sách bảng trong database."""
    schema_data = load_schema(from_cache=True)
    tables = get_table_names(schema_data)
    return SchemaResponse(tables=tables, total_tables=len(tables))


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
