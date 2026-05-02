"""
src/database/schema_inspector.py — Đọc schema và format thành context cho LLM

Có 2 mode:
  1. Từ cache file (schema_snapshot.json) — nhanh, dùng trong production
  2. Trực tiếp từ DB — dùng khi schema thay đổi
"""

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

SCHEMA_FILE = Path("db/schema_snapshot.json")

# Các bảng quan trọng nhất trong Northwind — inject đầy đủ
# Bảng ít dùng hơn sẽ được inject dạng rút gọn để tiết kiệm token
PRIORITY_TABLES = {
    "orders", "order_details", "products",
    "customers", "employees", "categories",
    "suppliers", "shippers",
}


def load_schema(from_cache: bool = True) -> dict:
    """
    Load schema từ cache JSON.
    Nếu cache không tồn tại, đọc thẳng từ DB.
    """
    if from_cache and SCHEMA_FILE.exists():
        return json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))

    # Fallback: đọc từ DB
    logger.warning("schema_snapshot.json không tồn tại, đọc từ DB...")
    from db.seed import snapshot_schema
    return snapshot_schema()


def format_schema_for_prompt(
    schema: dict,
    include_samples: bool = True,
    max_tables: Optional[int] = None,
) -> str:
    """
    Chuyển schema dict thành chuỗi text để inject vào LLM prompt.

    Format:
        TABLE: orders
        COLUMNS: order_id (integer, PK), customer_id (character varying), ...
        FK: customer_id → customers.customer_id
        SAMPLE: {"order_id": 10248, "customer_id": "VINET", ...}

    Tại sao cần format này?
    → LLM cần biết tên bảng chính xác (case-sensitive trong SQL)
    → FK relationships giúp LLM biết cần JOIN bảng nào
    → Sample rows giúp LLM biết format giá trị (VD: date là "1996-07-04" không phải integer)
    """
    tables = list(schema.keys())

    # Ưu tiên bảng quan trọng, giới hạn số lượng nếu cần
    priority = [t for t in tables if t in PRIORITY_TABLES]
    rest     = [t for t in tables if t not in PRIORITY_TABLES]
    ordered  = priority + rest

    if max_tables:
        ordered = ordered[:max_tables]

    lines = ["=== DATABASE SCHEMA (PostgreSQL - Northwind) ===\n"]

    for table in ordered:
        info = schema[table]
        lines.append(f"TABLE: {table}")

        # Columns
        col_parts = []
        for col in info["columns"]:
            flags = []
            if col["name"] in info.get("primary_keys", []):
                flags.append("PK")
            if not col["nullable"]:
                flags.append("NOT NULL")
            flag_str = f" [{', '.join(flags)}]" if flags else ""
            col_parts.append(f"{col['name']} ({col['type']}{flag_str})")
        lines.append(f"COLUMNS: {', '.join(col_parts)}")

        # Foreign keys
        if info.get("foreign_keys"):
            for fk in info["foreign_keys"]:
                lines.append(f"FK: {fk['column']} → {fk['references']}")

        # Sample rows (chỉ cho priority tables)
        if include_samples and table in PRIORITY_TABLES and info.get("sample_rows"):
            sample = info["sample_rows"][0]  # chỉ 1 row là đủ
            lines.append(f"SAMPLE: {json.dumps(sample, ensure_ascii=False, default=str)}")

        lines.append("")  # blank line giữa các bảng

    return "\n".join(lines)


def get_table_names(schema: dict) -> list[str]:
    return list(schema.keys())


def get_columns(schema: dict, table: str) -> list[str]:
    if table not in schema:
        return []
    return [col["name"] for col in schema[table]["columns"]]


def find_matching_tables(schema: dict, question: str) -> list[str]:
    normalized = question.strip().lower()
    matches: list[str] = []

    for table in schema.keys():
        if table.lower() in normalized:
            matches.append(table)

    return matches


def find_tables_by_column(schema: dict, column_name: str) -> list[str]:
    normalized = column_name.strip().lower()
    matches: list[str] = []

    for table, info in schema.items():
        for col in info["columns"]:
            if col["name"].lower() == normalized:
                matches.append(table)
                break

    return matches


def format_table_schema_for_chat(schema: dict, table: str) -> str:
    if table not in schema:
        return f"Khong tim thay bang '{table}' trong database."

    info = schema[table]
    lines = [f"Bang `{table}` co {len(info['columns'])} cot:"]

    for col in info["columns"]:
        flags = []
        if col["name"] in info.get("primary_keys", []):
            flags.append("PK")
        if not col["nullable"]:
            flags.append("NOT NULL")
        suffix = f" [{', '.join(flags)}]" if flags else ""
        lines.append(f"- {col['name']}: {col['type']}{suffix}")

    if info.get("foreign_keys"):
        lines.append("")
        lines.append("Quan he khoa ngoai:")
        for fk in info["foreign_keys"]:
            lines.append(f"- {fk['column']} -> {fk['references']}")

    return "\n".join(lines)


def format_schema_overview_for_chat(schema: dict) -> str:
    tables = sorted(schema.keys())
    lines = [f"Database hien co {len(tables)} bang:"]
    lines.extend(f"- {table}" for table in tables)
    return "\n".join(lines)
