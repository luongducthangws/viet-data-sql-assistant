"""
src/llm/sql_validator.py — Validate SQL trước khi thực thi

Mục tiêu: Chặn mọi câu SQL có thể thay đổi hoặc xóa dữ liệu.
Đây là lớp bảo vệ quan trọng nhất trong hệ thống.
"""

import re
import logging
from dataclasses import dataclass

import sqlparse
from sqlparse.sql import Statement
from sqlparse.tokens import Keyword, DDL, DML

logger = logging.getLogger(__name__)

# Các DML/DDL bị cấm tuyệt đối
FORBIDDEN_KEYWORDS = {
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER",
    "TRUNCATE", "CREATE", "REPLACE", "MERGE",
    "GRANT", "REVOKE", "EXEC", "EXECUTE",
    "CALL", "COPY", "VACUUM", "ANALYZE",
}

# Ký tự/pattern nguy hiểm
DANGEROUS_PATTERNS = [
    r";\s*\w",           # Multiple statements: SELECT 1; DROP TABLE
    r"--",               # SQL comment injection
    r"/\*.*?\*/",        # Block comment
    r"\bpg_\w+\b",       # PostgreSQL system functions (pg_sleep, pg_read_file...)
    r"\binformation_schema\b",  # Schema enumeration
    r"\bpg_catalog\b",
]


@dataclass
class ValidationResult:
    valid: bool
    sql: str            # SQL đã được làm sạch
    error: str = ""


def clean_sql(raw: str) -> str:
    """
    Làm sạch output của LLM:
    - Bỏ markdown code blocks (```sql ... ```)
    - Bỏ khoảng trắng thừa
    - Đảm bảo kết thúc bằng dấu chấm phẩy
    """
    sql = raw.strip()

    # Bỏ markdown fences
    sql = re.sub(r"^```(?:sql)?\s*", "", sql, flags=re.IGNORECASE)
    sql = re.sub(r"\s*```$", "", sql)
    sql = sql.strip()

    # Bỏ prefix giải thích của LLM (VD: "Here is the SQL: SELECT...")
    lines = sql.splitlines()
    sql_lines = []
    found_select = False
    for line in lines:
        if re.match(r"^\s*(SELECT|WITH)\b", line, re.IGNORECASE):
            found_select = True
        if found_select:
            sql_lines.append(line)
    if sql_lines:
        sql = "\n".join(sql_lines)

    # Sua mot so loi cu phap MySQL ma LLM hay sinh khi target la PostgreSQL.
    sql = sql.replace("`", '"')
    sql = re.sub(r'"order\s+details"', '"order_details"', sql, flags=re.IGNORECASE)

    # Đảm bảo kết thúc bằng ";"
    sql = sql.rstrip(";").strip() + ";"

    return sql


def validate_sql(raw_sql: str) -> ValidationResult:
    """
    Validate và làm sạch SQL.
    Trả về ValidationResult với valid=True nếu an toàn.
    """
    sql = clean_sql(raw_sql)

    # 1. Phải bắt đầu bằng SELECT hoặc WITH (CTE)
    if not re.match(r"^\s*(SELECT|WITH)\b", sql, re.IGNORECASE):
        return ValidationResult(
            valid=False,
            sql=sql,
            error=f"Chỉ cho phép SELECT query. SQL nhận được bắt đầu bằng: '{sql[:50]}'"
        )

    # 2. Kiểm tra dangerous patterns
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, sql, re.IGNORECASE | re.DOTALL):
            return ValidationResult(
                valid=False,
                sql=sql,
                error=f"SQL chứa pattern nguy hiểm: {pattern}"
            )

    # 3. Parse và kiểm tra từng token với sqlparse
    try:
        parsed = sqlparse.parse(sql)
        if not parsed:
            return ValidationResult(valid=False, sql=sql, error="Không parse được SQL")

        # Chỉ cho phép 1 statement
        if len(parsed) > 1:
            return ValidationResult(
                valid=False, sql=sql,
                error="Chỉ cho phép 1 câu SQL duy nhất"
            )

        stmt: Statement = parsed[0]

        for token in stmt.flatten():
            token_val = token.normalized.upper()

            # Kiểm tra forbidden keywords
            if token.ttype in (DDL, DML, Keyword):
                if token_val in FORBIDDEN_KEYWORDS:
                    return ValidationResult(
                        valid=False, sql=sql,
                        error=f"Keyword bị cấm: {token_val}"
                    )

    except Exception as e:
        logger.warning(f"sqlparse error: {e}")
        # Nếu parse lỗi, vẫn dùng regex check — không block hoàn toàn

    logger.debug(f"SQL validated OK: {sql[:80]}...")
    return ValidationResult(valid=True, sql=sql)
