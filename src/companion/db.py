"""DuckDB helpers: open the database, create the tables, insert rows.

This is the storage layer. It knows nothing about football or APIs — it just
takes rows (lists of dicts) and stores them. Keeping it separate means we can
test it with fake data and never touch the network.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import duckdb

# The DuckDB file lives in data/. We compute the path relative to THIS file so it
# works no matter what folder you run the command from.
#   db.py is at src/companion/db.py  ->  parents[2] is the repo root.
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = REPO_ROOT / "data" / "companion.duckdb"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def now_utc() -> dt.datetime:
    """The current UTC time, without a timezone attached.

    We store everything in UTC (a single, unambiguous clock) and keep it
    "naive" (no tzinfo) because our DuckDB TIMESTAMP columns are tz-naive. Using
    one consistent rule avoids subtle off-by-an-hour bugs.
    """
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


def connect(db_path: Path | str = DEFAULT_DB_PATH) -> duckdb.DuckDBPyConnection:
    """Open (or create) the DuckDB database file and return a connection."""
    db_path = Path(db_path)
    if db_path != Path(":memory:"):
        db_path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(db_path))


def _split_statements(sql: str) -> list[str]:
    """Split a .sql script into individual statements.

    DuckDB's execute() runs one statement at a time, so we split on ';'. We first
    drop full-line '--' comments (including the trailing note in schema.sql) so we
    don't try to execute a comment-only chunk. Inline '-- ...' comments after code
    are left in place; DuckDB handles those fine.
    """
    lines = [ln for ln in sql.splitlines() if not ln.strip().startswith("--")]
    cleaned = "\n".join(lines)
    return [s.strip() for s in cleaned.split(";") if s.strip()]


def init_schema(con: duckdb.DuckDBPyConnection, schema_path: Path = SCHEMA_PATH) -> None:
    """Create all tables (CREATE TABLE IF NOT EXISTS — safe to run every time)."""
    for statement in _split_statements(schema_path.read_text(encoding="utf-8")):
        con.execute(statement)


def insert_rows(con: duckdb.DuckDBPyConnection, table: str, rows: list[dict]) -> int:
    """Insert a batch of rows (list of dicts) into `table`. Returns the count.

    All rows must share the same keys (our parse functions guarantee this). We use
    a parameterized query (the '?' placeholders) so values are safely escaped —
    never string-formatted into SQL, which would be an injection risk.
    """
    if not rows:
        return 0
    columns = list(rows[0].keys())
    placeholders = ", ".join(["?"] * len(columns))
    column_list = ", ".join(columns)
    params = [[row[col] for col in columns] for row in rows]
    con.executemany(
        f"INSERT INTO {table} ({column_list}) VALUES ({placeholders})", params
    )
    return len(rows)


def replace_rows(con: duckdb.DuckDBPyConnection, table: str, rows: list[dict]) -> int:
    """Refresh a whole table in place (DELETE all, then INSERT).

    Used for the `teams` reference table, which we keep current rather than
    snapshotting (team names/ids barely change).
    """
    con.execute(f"DELETE FROM {table}")
    return insert_rows(con, table, rows)
