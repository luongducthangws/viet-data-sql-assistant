"""
src/api/schemas.py — Pydantic models cho request / response
"""

from typing import Optional
from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=3,
        max_length=500,
        description="Câu hỏi bằng tiếng Việt",
        examples=["Top 5 sản phẩm bán chạy nhất?", "Doanh thu tháng 7 năm 1996?"],
    )
    debug: bool = Field(False, description="Trả về thêm thông tin debug")


class AskResponse(BaseModel):
    question: str
    answer: str
    sql: str
    row_count: int
    attempts: int
    success: bool
    debug: Optional[dict] = None


class HealthResponse(BaseModel):
    status: str
    db_connected: bool
    chain_ready: bool


class SchemaResponse(BaseModel):
    tables: list[str]
    total_tables: int