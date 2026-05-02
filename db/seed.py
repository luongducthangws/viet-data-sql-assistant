"""
db/seed.py — Load Northwind vào PostgreSQL và cache schema
Chạy một lần duy nhất: python db/seed.py
"""

import json
import logging
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DB_HOST     = os.getenv("DB_HOST", "localhost")
DB_PORT     = os.getenv("DB_PORT", "5432")
DB_NAME     = os.getenv("DB_NAME", "northwind")
DB_USER     = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")

SQL_FILE    = Path(__file__).parent / "northwind.sql"
SCHEMA_FILE = Path(__file__).parent / "schema_snapshot.json"


def load_sql():
    """Dùng psql CLI để load northwind.sql vào database."""
    if not SQL_FILE.exists():
        logger.error(f"Không tìm thấy {SQL_FILE}")
        logger.error("Chạy lệnh: curl -o db/northwind.sql https://raw.githubusercontent.com/pthom/northwind_psql/master/northwind.sql")
        sys.exit(1)

    logger.info(f"Loading {SQL_FILE} vào {DB_NAME}...")
    env = {**os.environ, "PGPASSWORD": DB_PASSWORD}

    result = subprocess.run(
        [
            "psql",
            "-h", DB_HOST,
            "-p", DB_PORT,
            "-U", DB_USER,
            "-d", DB_NAME,
            "-f", str(SQL_FILE),
            "-q",          # quiet
        ],
        env=env,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        logger.error(f"psql error:\n{result.stderr}")
        sys.exit(1)

    logger.info("Load SQL thành công.")


def snapshot_schema():
    """
    Đọc toàn bộ schema từ PostgreSQL và lưu vào schema_snapshot.json.
    File này được dùng bởi schema_inspector.py để inject vào prompt
    mà không cần query DB mỗi request.
    """
    import psycopg2

    conn = psycopg2.connect(
        host=DB_HOST, port=DB_PORT,
        dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD,
    )
    cur = conn.cursor()

    # Lấy tất cả bảng trong schema public (bỏ qua system tables)
    cur.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_type = 'BASE TABLE'
        ORDER BY table_name;
    """)
    tables = [row[0] for row in cur.fetchall()]

    schema = {}
    for table in tables:
        # Lấy column name + data type + nullable
        cur.execute("""
            SELECT
                column_name,
                data_type,
                is_nullable,
                column_default
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = %s
            ORDER BY ordinal_position;
        """, (table,))
        columns = [
            {
                "name":     row[0],
                "type":     row[1],
                "nullable": row[2] == "YES",
                "default":  row[3],
            }
            for row in cur.fetchall()
        ]

        # Lấy primary keys
        cur.execute("""
            SELECT kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
             AND tc.table_schema    = kcu.table_schema
            WHERE tc.constraint_type = 'PRIMARY KEY'
              AND tc.table_name = %s;
        """, (table,))
        pks = [row[0] for row in cur.fetchall()]

        # Lấy foreign keys
        cur.execute("""
            SELECT
                kcu.column_name,
                ccu.table_name  AS foreign_table,
                ccu.column_name AS foreign_column
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage ccu
              ON ccu.constraint_name = tc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND tc.table_name = %s;
        """, (table,))
        fks = [
            {"column": row[0], "references": f"{row[1]}.{row[2]}"}
            for row in cur.fetchall()
        ]

        # Lấy sample 3 rows để LLM hiểu format dữ liệu
        cur.execute(f'SELECT * FROM "{table}" LIMIT 3;')
        col_names = [desc[0] for desc in cur.description]
        sample_rows = [dict(zip(col_names, row)) for row in cur.fetchall()]
        # Convert non-serializable types to string
        for sr in sample_rows:
            for k, v in sr.items():
                if not isinstance(v, (str, int, float, bool, type(None))):
                    sr[k] = str(v)

        schema[table] = {
            "columns":     columns,
            "primary_keys": pks,
            "foreign_keys": fks,
            "sample_rows": sample_rows,
        }

    cur.close()
    conn.close()

    SCHEMA_FILE.write_text(json.dumps(schema, indent=2, ensure_ascii=False))
    logger.info(f"Schema snapshot lưu vào {SCHEMA_FILE} ({len(tables)} bảng)")
    return schema


if __name__ == "__main__":
    load_sql()
    snapshot_schema()
    logger.info("Setup hoàn tất. Chạy: uvicorn src.api.main:app --reload")