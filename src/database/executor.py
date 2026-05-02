"""
src/database/executor.py - Thực thi SQL và trả về kết quả có cấu trúc.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy import text

from src.database.connection import get_db

logger = logging.getLogger(__name__)

MAX_ROWS = 100


@dataclass
class QueryResult:
    success: bool
    columns: list[str] = field(default_factory=list)
    rows: list[dict] = field(default_factory=list)
    row_count: int = 0
    error: Optional[str] = None
    truncated: bool = False


def _normalize_postgres_sql(sql: str) -> str:
    """
    Sửa một số mẫu SQL phổ biến mà LLM hay sinh sai cho PostgreSQL.

    PostgreSQL không hỗ trợ ROUND(double precision, integer),
    nên cần ép sang numeric trước khi làm tròn 2 chữ số thập phân.
    """

    def repl(match: re.Match) -> str:
        expr = match.group("expr").strip()
        scale = match.group("scale")

        # Tránh cast lặp nếu biểu thức đã là numeric.
        if "::numeric" in expr.lower():
            return f"ROUND({expr}, {scale})"

        return f"ROUND(({expr})::numeric, {scale})"

    return re.sub(
        r"ROUND\s*\(\s*(?P<expr>.*?)\s*,\s*(?P<scale>\d+)\s*\)",
        repl,
        sql,
        flags=re.IGNORECASE | re.DOTALL,
    )


def execute_query(sql: str) -> QueryResult:
    """
    Chạy câu SQL và trả về QueryResult.
    Tự động thêm LIMIT nếu query chưa có.
    """
    sql = _normalize_postgres_sql(sql)

    sql_normalized = sql.strip().rstrip(";").upper()
    if "LIMIT" not in sql_normalized:
        sql = sql.rstrip().rstrip(";") + f" LIMIT {MAX_ROWS + 1}"

    try:
        with get_db() as db:
            result = db.execute(text(sql))
            columns = list(result.keys())
            all_rows = result.fetchall()

            truncated = len(all_rows) > MAX_ROWS
            rows = all_rows[:MAX_ROWS]

            row_dicts = []
            for row in rows:
                d = {}
                for col, val in zip(columns, row):
                    if hasattr(val, "isoformat"):
                        d[col] = val.isoformat()
                    elif hasattr(val, "__float__"):
                        d[col] = float(val)
                    else:
                        d[col] = val
                row_dicts.append(d)

            return QueryResult(
                success=True,
                columns=columns,
                rows=row_dicts,
                row_count=len(row_dicts),
                truncated=truncated,
            )

    except Exception as e:
        error_msg = str(e).split("\n")[0]
        logger.warning("SQL execution failed: %s", error_msg)
        logger.debug("SQL: %s", sql)
        return QueryResult(success=False, error=error_msg)


def format_result_for_llm(result: QueryResult) -> str:
    """
    Chuyển QueryResult thành text ngắn gọn để LLM tổng hợp.
    """
    if not result.success:
        return f"[LỖI SQL]: {result.error}"

    if result.row_count == 0:
        return "[KẾT QUẢ]: Không có dữ liệu phù hợp."

    lines = [f"[KẾT QUẢ]: {result.row_count} dòng" +
             (" (đã cắt bớt, còn nhiều hơn)" if result.truncated else "")]

    lines.append(" | ".join(result.columns))
    lines.append("-" * (sum(len(c) for c in result.columns) + 3 * len(result.columns)))

    for row in result.rows[:20]:
        lines.append(" | ".join(str(row.get(c, "")) for c in result.columns))

    if result.row_count > 20:
        lines.append(f"... (và {result.row_count - 20} dòng nữa)")

    return "\n".join(lines)
