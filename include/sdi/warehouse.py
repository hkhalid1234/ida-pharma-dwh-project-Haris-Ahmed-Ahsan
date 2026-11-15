"""Warehouse adapters. DuckDB is the production OLAP engine; SQLite is only used by unit tests
(same DDL and the same portable SQL)."""
import re
import sqlite3
from pathlib import Path

import pandas as pd

SCHEMA_SQL = Path(__file__).parent / "sql" / "star_schema.sql"


def _statements(sql: str):
    sql = re.sub(r"--.*", "", sql)
    return [s.strip() for s in sql.split(";") if s.strip()]


class BaseWarehouse:
    def ensure_schema(self):
        for stmt in _statements(SCHEMA_SQL.read_text()):
            self.execute(stmt)

    def table_exists_nonempty(self, table: str) -> bool:
        return int(self.query(f"SELECT COUNT(*) AS n FROM {table}")["n"][0]) > 0

    def append(self, table: str, df: pd.DataFrame):
        raise NotImplementedError

    def replace(self, table: str, df: pd.DataFrame):
        self.execute(f"DELETE FROM {table}")
        self.append(table, df)


class DuckWarehouse(BaseWarehouse):
    def __init__(self, path: str):
        import duckdb
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.con = duckdb.connect(path)

    def execute(self, sql, params=None):
        return self.con.execute(sql, params) if params else self.con.execute(sql)

    def query(self, sql, params=None) -> pd.DataFrame:
        return self.execute(sql, params).df()

    def append(self, table, df):
        if df.empty:
            return
        cols = ", ".join(df.columns)
        self.con.register("_incoming", df)
        try:
            self.con.execute(f"INSERT INTO {table} ({cols}) SELECT {cols} FROM _incoming")
        finally:
            self.con.unregister("_incoming")

    def drop_indexes(self):
        for (name,) in self.con.execute("SELECT index_name FROM duckdb_indexes()").fetchall():
            self.con.execute(f"DROP INDEX IF EXISTS {name}")

    def close(self):
        self.con.close()


class SqliteWarehouse(BaseWarehouse):
    def __init__(self, path: str = ":memory:"):
        self.con = sqlite3.connect(path)

    def execute(self, sql, params=()):
        cur = self.con.cursor(); cur.execute(sql, params or []); self.con.commit(); return cur

    def query(self, sql, params=()) -> pd.DataFrame:
        cur = self.con.cursor(); cur.execute(sql, params or [])
        return pd.DataFrame(cur.fetchall(), columns=[c[0] for c in cur.description])

    def append(self, table, df):
        if not df.empty:
            df.to_sql(table, self.con, if_exists="append", index=False)

    def drop_indexes(self):
        for (n,) in self.con.execute("SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'").fetchall():
            self.con.execute(f"DROP INDEX IF EXISTS {n}")

    def close(self):
        self.con.close()
