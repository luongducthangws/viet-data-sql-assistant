"""
Load Northwind into PostgreSQL and refresh the schema cache.

Run locally with `python db/seed.py`. On Railway this is used as the
pre-deploy command, so it reads DATABASE_URL when that variable is present.
"""

import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "northwind")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")

SQL_FILE = Path(__file__).parent / "northwind.sql"
SCHEMA_FILE = Path(__file__).parent / "schema_snapshot.json"


def _running_on_railway() -> bool:
    return any(
        os.getenv(name)
        for name in ("RAILWAY_ENVIRONMENT", "RAILWAY_PROJECT_ID", "RAILWAY_SERVICE_ID")
    )


def _has_explicit_db_config() -> bool:
    return bool(DATABASE_URL or os.getenv("DB_HOST"))


def _database_target_label() -> str:
    if not DATABASE_URL:
        return f"{DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

    parsed = urlparse(DATABASE_URL)
    host = parsed.hostname or "database"
    port = f":{parsed.port}" if parsed.port else ""
    database = parsed.path.lstrip("/") or "postgres"
    username = parsed.username or "user"
    return f"{username}@{host}{port}/{database}"


def load_sql():
    """Load northwind.sql into PostgreSQL with psql."""
    if not SQL_FILE.exists():
        logger.error("Missing %s", SQL_FILE)
        logger.error(
            "Run: curl -o db/northwind.sql "
            "https://raw.githubusercontent.com/pthom/northwind_psql/master/northwind.sql"
        )
        sys.exit(1)

    logger.info("Loading %s into %s...", SQL_FILE, _database_target_label())
    env = {**os.environ, "PGPASSWORD": DB_PASSWORD}

    cmd = ["psql"]
    if DATABASE_URL:
        cmd.append(DATABASE_URL)
    else:
        cmd.extend(["-h", DB_HOST, "-p", DB_PORT, "-U", DB_USER, "-d", DB_NAME])
    cmd.extend(["-f", str(SQL_FILE), "-q"])

    result = subprocess.run(
        cmd,
        env=env,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        logger.error("psql error:\n%s", result.stderr)
        sys.exit(1)

    logger.info("SQL load completed.")


def snapshot_schema():
    """
    Read PostgreSQL metadata and write db/schema_snapshot.json.
    The runtime uses this snapshot as prompt context instead of querying
    information_schema on every request.
    """
    import psycopg2

    if DATABASE_URL:
        conn = psycopg2.connect(DATABASE_URL)
    else:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
        )
    cur = conn.cursor()

    cur.execute(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_type = 'BASE TABLE'
        ORDER BY table_name;
        """
    )
    tables = [row[0] for row in cur.fetchall()]

    schema = {}
    for table in tables:
        cur.execute(
            """
            SELECT
                column_name,
                data_type,
                is_nullable,
                column_default
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = %s
            ORDER BY ordinal_position;
            """,
            (table,),
        )
        columns = [
            {
                "name": row[0],
                "type": row[1],
                "nullable": row[2] == "YES",
                "default": row[3],
            }
            for row in cur.fetchall()
        ]

        cur.execute(
            """
            SELECT kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
             AND tc.table_schema    = kcu.table_schema
            WHERE tc.constraint_type = 'PRIMARY KEY'
              AND tc.table_name = %s;
            """,
            (table,),
        )
        pks = [row[0] for row in cur.fetchall()]

        cur.execute(
            """
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
            """,
            (table,),
        )
        fks = [
            {"column": row[0], "references": f"{row[1]}.{row[2]}"}
            for row in cur.fetchall()
        ]

        cur.execute(f'SELECT * FROM "{table}" LIMIT 3;')
        col_names = [desc[0] for desc in cur.description]
        sample_rows = [dict(zip(col_names, row)) for row in cur.fetchall()]
        for sample_row in sample_rows:
            for key, value in sample_row.items():
                if not isinstance(value, (str, int, float, bool, type(None))):
                    sample_row[key] = str(value)

        schema[table] = {
            "columns": columns,
            "primary_keys": pks,
            "foreign_keys": fks,
            "sample_rows": sample_rows,
        }

    cur.close()
    conn.close()

    SCHEMA_FILE.write_text(json.dumps(schema, indent=2, ensure_ascii=False))
    logger.info("Schema snapshot saved to %s (%s tables).", SCHEMA_FILE, len(tables))
    return schema


if __name__ == "__main__":
    if _running_on_railway() and not _has_explicit_db_config():
        logger.error("DATABASE_URL is not configured; skipping Railway seed step.")
        sys.exit(0)

    load_sql()
    snapshot_schema()
    logger.info("Setup completed.")
