"""
src/chain/sql_chain.py - Orchestrator chính của toàn bộ pipeline.
"""

import logging
import re
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Literal

from src.chain.retry_handler import execute_with_retry
from src.database.executor import QueryResult, format_result_for_llm
from src.database.schema_inspector import (
    find_matching_tables,
    find_tables_by_column,
    format_schema_for_prompt,
    format_schema_overview_for_chat,
    format_table_schema_for_chat,
    load_schema,
)
from src.llm.client import call_llm
from src.llm.prompt_builder import (
    CLARIFICATION_ASSISTANT_SYSTEM,
    GENERAL_ASSISTANT_SYSTEM,
    SQL_GENERATION_SYSTEM,
    SYNTHESIS_SYSTEM,
    build_clarification_prompt,
    build_general_prompt,
    build_sql_prompt,
    build_synthesis_prompt,
)

logger = logging.getLogger(__name__)

IntentLabel = Literal["general_chat", "clarification", "data_query", "unsafe_request", "schema_query"]

GENERAL_CHAT_PATTERNS = (
    r"\b(xin chao|chao|hello|hi)\b",
    r"\b(ban co the|ban giup toi|giup toi voi|ho tro toi)\b",
    r"\b(ban lam duoc gi|ban co the lam gi|kha nang cua ban)\b",
    r"\b(cam on|thanks|thank you)\b",
)

DATA_HINT_PATTERNS = (
    r"\b(doanh thu|san pham|khach hang|nhan vien|don hang|nha cung cap)\b",
    r"\b(top|bao nhieu|danh sach|cao nhat|thap nhat|nhieu nhat|it nhat|trung binh|tong|liet ke)\b",
)

SCHEMA_PATTERNS = (
    r"\b(database|schema|bang|cot|truong|field|column|table)\b",
    r"\b(co nhung gi|gom nhung gi|cau truc|metadata)\b",
)

AGGREGATION_PATTERNS = (
    r"\b(theo ai|theo gi|theo tung|nhom nao|phan loai nao)\b",
    r"\b(xu huong|bien dong|so sanh|xep hang)\b",
)

UNSAFE_PATTERNS = (
    r"\b(xoa|delete|drop|truncate|remove)\b",
    r"\b(cap nhat|update|sua du lieu|chinh sua du lieu)\b",
    r"\b(chen|insert|them moi ban ghi)\b",
    r"\b(alter|grant|revoke)\b",
)

CLARIFICATION_PATTERNS = (
    r"\b(giup toi|ho tro toi|toi muon hoi|toi can biet)\b",
    r"\b(thong tin|du lieu|bao cao|phan tich)\b",
)


@dataclass
class ChatResponse:
    answer: str
    sql: str
    row_count: int
    attempts: int
    success: bool
    debug: dict = field(default_factory=dict)


@dataclass
class IntentDecision:
    label: IntentLabel
    reason: str


@lru_cache(maxsize=1)
def _get_schema_context() -> str:
    schema = load_schema(from_cache=True)
    return format_schema_for_prompt(schema, include_samples=True)


@lru_cache(maxsize=1)
def _get_schema_snapshot() -> dict:
    return load_schema(from_cache=True)


def _build_query_failure_answer() -> str:
    return (
        "Xin lỗi, tôi không thể truy vấn dữ liệu cho câu hỏi này. "
        "Vui lòng thử diễn đạt lại hoặc hỏi bộ phận IT."
    )


def _build_llm_failure_answer(error: Exception) -> str:
    message = str(error).lower()
    if "quota" in message or "resource_exhausted" in message or "429" in message:
        return (
            "Dịch vụ AI hiện đã chạm giới hạn quota nên tôi chưa thể xử lý câu hỏi lúc này. "
            "Vui lòng chờ một lúc rồi thử lại, hoặc đổi sang provider/model khác trong file .env."
        )
    return (
        "Tôi chưa thể sinh câu trả lời do dịch vụ AI đang gặp lỗi tạm thời. "
        "Vui lòng thử lại sau."
    )


def _build_fallback_answer(result: QueryResult, question: str = "") -> str:
    if not result.success:
        return "Xin lỗi, tôi không thể tổng hợp câu trả lời do truy vấn dữ liệu thất bại."

    if result.row_count == 0:
        return "Không có dữ liệu phù hợp với câu hỏi này."

    if question:
        lines = [f"Dựa trên câu hỏi: {question}"]
        lines.append(f"Tôi đã tìm thấy {result.row_count} dòng dữ liệu phù hợp.")
    else:
        lines = [f"Tôi đã tìm thấy {result.row_count} dòng dữ liệu phù hợp."]
    preview_columns = result.columns[:3]

    for idx, row in enumerate(result.rows[:5], start=1):
        values = [f"{col}: {row.get(col, '')}" for col in preview_columns]
        lines.append(f"{idx}. " + " | ".join(values))

    if result.row_count > 5:
        lines.append(f"... và còn {result.row_count - 5} dòng dữ liệu khác.")

    return "\n".join(lines)


def _normalize_question(question: str) -> str:
    normalized = unicodedata.normalize("NFD", question.strip().lower())
    without_accents = "".join(
        ch for ch in normalized
        if unicodedata.category(ch) != "Mn"
    )
    return re.sub(r"\s+", " ", without_accents)


def _classify_intent(question: str) -> IntentDecision:
    normalized = _normalize_question(question)
    if not normalized:
        return IntentDecision("clarification", "empty_question")

    if any(re.search(pattern, normalized) for pattern in UNSAFE_PATTERNS):
        return IntentDecision("unsafe_request", "matched_unsafe_pattern")

    normalized = question.strip().lower()

    has_general_signal = any(re.search(pattern, normalized) for pattern in GENERAL_CHAT_PATTERNS)
    has_data_signal = any(re.search(pattern, normalized) for pattern in DATA_HINT_PATTERNS)
    has_aggregation_signal = any(re.search(pattern, normalized) for pattern in AGGREGATION_PATTERNS)
    has_clarification_signal = any(re.search(pattern, normalized) for pattern in CLARIFICATION_PATTERNS)
    has_schema_signal = any(re.search(pattern, normalized) for pattern in SCHEMA_PATTERNS)

    if has_general_signal and not (has_data_signal or has_aggregation_signal):
        return IntentDecision("general_chat", "matched_general_pattern")

    if has_schema_signal and not has_data_signal:
        return IntentDecision("schema_query", "matched_schema_pattern")

    if has_data_signal or has_aggregation_signal:
        return IntentDecision("data_query", "matched_data_pattern")

    if has_clarification_signal or len(normalized.split()) <= 4:
        return IntentDecision("clarification", "question_too_ambiguous")

    return IntentDecision("data_query", "default_to_data_query")


def _handle_general_chat(question: str) -> str:
    return call_llm(
        user_prompt=build_general_prompt(question),
        system_prompt=GENERAL_ASSISTANT_SYSTEM,
        temperature=0.4,
        max_tokens=220,
    )


def _handle_clarification(question: str) -> str:
    return call_llm(
        user_prompt=build_clarification_prompt(question),
        system_prompt=CLARIFICATION_ASSISTANT_SYSTEM,
        temperature=0.4,
        max_tokens=220,
    )


def _handle_unsafe_request(question: str) -> str:
    return (
        "Xin lỗi, tôi không thể thực hiện yêu cầu thay đổi hoặc xóa dữ liệu. "
        "Hệ thống chỉ hỗ trợ tra cứu và phân tích dữ liệu an toàn. "
        "Bạn có thể hỏi theo hướng xem thông tin, ví dụ: `có bao nhiêu đơn hàng?` "
        "hoặc `đơn hàng nào có giá trị lớn nhất?`"
    )


def _extract_column_name(question: str) -> str:
    normalized = _normalize_question(question)
    match = re.search(r"(cot|truong|field|column)\s+([a-zA-Z_][a-zA-Z0-9_]*)", normalized)
    if match:
        return match.group(2)
    return ""


def _handle_schema_query(question: str) -> str:
    schema = _get_schema_snapshot()
    normalized = _normalize_question(question)

    if any(token in normalized for token in ("tat ca bang", "nhung bang nao", "co nhung bang nao", "database co")):
        return format_schema_overview_for_chat(schema)

    matched_tables = find_matching_tables(schema, normalized)
    if matched_tables:
        return "\n\n".join(format_table_schema_for_chat(schema, table) for table in matched_tables[:3])

    column_name = _extract_column_name(question)
    if column_name:
        tables = find_tables_by_column(schema, column_name)
        if tables:
            joined = ", ".join(f"`{table}`" for table in tables)
            return f"Cot `{column_name}` xuat hien trong cac bang: {joined}."
        return f"Khong tim thay cot `{column_name}` trong schema hien tai."

    return (
        format_schema_overview_for_chat(schema)
        + "\n\nBan co the hoi cu the hon, vi du: `bang orders co nhung cot nao?` "
          "hoac `cot customer_id nam o bang nao?`"
    )


class SQLChain:
    def __init__(self):
        logger.info("Initializing SQLChain - loading schema...")
        self.schema_context = _get_schema_context()
        logger.info("SQLChain ready.")

    def ask(self, question: str, debug: bool = False) -> ChatResponse:
        intent = _classify_intent(question)

        try:
            if intent.label == "general_chat":
                answer = _handle_general_chat(question)
                return ChatResponse(
                    answer=answer,
                    sql="",
                    row_count=0,
                    attempts=1,
                    success=True,
                    debug={"stage": "intent_router", "intent": intent.label, "reason": intent.reason} if debug else {},
                )
            if intent.label == "clarification":
                answer = _handle_clarification(question)
                return ChatResponse(
                    answer=answer,
                    sql="",
                    row_count=0,
                    attempts=1,
                    success=True,
                    debug={"stage": "intent_router", "intent": intent.label, "reason": intent.reason} if debug else {},
                )
            if intent.label == "schema_query":
                answer = _handle_schema_query(question)
                return ChatResponse(
                    answer=answer,
                    sql="",
                    row_count=0,
                    attempts=1,
                    success=True,
                    debug={"stage": "intent_router", "intent": intent.label, "reason": intent.reason} if debug else {},
                )
            if intent.label == "unsafe_request":
                answer = _handle_unsafe_request(question)
                return ChatResponse(
                    answer=answer,
                    sql="",
                    row_count=0,
                    attempts=1,
                    success=False,
                    debug={"stage": "intent_router", "intent": intent.label, "reason": intent.reason} if debug else {},
                )
        except Exception as e:
            logger.warning("Intent router handling failed, fallback to SQL flow: %s", e)

        sql_prompt = build_sql_prompt(
            question=question,
            schema_context=self.schema_context,
        )

        try:
            raw_sql = call_llm(
                user_prompt=sql_prompt,
                system_prompt=SQL_GENERATION_SYSTEM,
                temperature=0.0,
            )
        except Exception as e:
            logger.warning("SQL generation failed: %s", e)
            return ChatResponse(
                answer=_build_llm_failure_answer(e),
                sql="",
                row_count=0,
                attempts=0,
                success=False,
                debug={
                    "error": str(e),
                    "stage": "sql_generation",
                    "intent": intent.label,
                    "intent_reason": intent.reason,
                } if debug else {},
            )

        logger.info("Generated SQL: %s...", raw_sql[:100])

        retry_result = execute_with_retry(
            question=question,
            schema_context=self.schema_context,
            initial_sql=raw_sql,
        )

        if not retry_result.success:
            return ChatResponse(
                answer=_build_query_failure_answer(),
                sql=retry_result.sql,
                row_count=0,
                attempts=retry_result.attempts,
                success=False,
                debug={
                    "error": retry_result.final_error,
                    "stage": "query_execution",
                    "intent": intent.label,
                    "intent_reason": intent.reason,
                } if debug else {},
            )

        result_text = format_result_for_llm(retry_result.result)
        synthesis_prompt = build_synthesis_prompt(
            question=question,
            sql=retry_result.sql,
            result_text=result_text,
        )

        used_fallback = False
        try:
            answer = call_llm(
                user_prompt=synthesis_prompt,
                system_prompt=SYNTHESIS_SYSTEM,
                temperature=0.3,
                max_tokens=512,
            )
        except Exception as e:
            logger.warning("Synthesis step failed, using fallback answer: %s", e)
            answer = _build_fallback_answer(retry_result.result, question=question)
            used_fallback = True

        return ChatResponse(
            answer=answer,
            sql=retry_result.sql,
            row_count=retry_result.result.row_count,
            attempts=retry_result.attempts,
            success=True,
            debug={
                "intent": intent.label,
                "intent_reason": intent.reason,
                "schema_tokens": len(self.schema_context.split()),
                "result_preview": result_text[:200],
                "synthesis_fallback": used_fallback,
            } if debug else {},
        )
