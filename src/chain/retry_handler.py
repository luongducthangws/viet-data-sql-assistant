"""
src/chain/retry_handler.py - Xử lý retry khi SQL bị lỗi.
"""

import logging
from dataclasses import dataclass
from typing import Optional

from src.database.executor import QueryResult, execute_query
from src.llm.client import call_llm
from src.llm.prompt_builder import SQL_GENERATION_SYSTEM, build_sql_prompt
from src.llm.sql_validator import validate_sql

logger = logging.getLogger(__name__)

MAX_RETRIES = 2


@dataclass
class RetryResult:
    success: bool
    sql: str
    result: Optional[QueryResult] = None
    attempts: int = 1
    final_error: Optional[str] = None


def execute_with_retry(
    question: str,
    schema_context: str,
    initial_sql: str,
) -> RetryResult:
    """
    Thực thi SQL, nếu fail thì cho LLM tự sửa và thử lại.
    """
    current_sql = initial_sql
    error_context = None

    for attempt in range(1, MAX_RETRIES + 2):
        logger.info("Attempt %s: executing SQL", attempt)

        validation = validate_sql(current_sql)
        if not validation.valid:
            error_context = f"SQL validation failed: {validation.error}"
            logger.warning("Attempt %s validation failed: %s", attempt, validation.error)
        else:
            result = execute_query(validation.sql)
            if result.success:
                return RetryResult(
                    success=True,
                    sql=validation.sql,
                    result=result,
                    attempts=attempt,
                )

            error_context = f"PostgreSQL error: {result.error}"
            logger.warning("Attempt %s execution failed: %s", attempt, result.error)

        if attempt <= MAX_RETRIES:
            logger.info("Retrying with error context: %s", error_context)
            retry_prompt = build_sql_prompt(
                question=question,
                schema_context=schema_context,
                error_context=error_context,
            )
            try:
                current_sql = call_llm(
                    user_prompt=retry_prompt,
                    system_prompt=SQL_GENERATION_SYSTEM,
                    temperature=0.0,
                )
            except Exception as e:
                final_error = f"{error_context}; LLM retry failed: {e}"
                logger.warning("Retry generation failed at attempt %s: %s", attempt, e)
                return RetryResult(
                    success=False,
                    sql=current_sql,
                    attempts=attempt,
                    final_error=final_error,
                )

    return RetryResult(
        success=False,
        sql=current_sql,
        attempts=MAX_RETRIES + 1,
        final_error=error_context,
    )
