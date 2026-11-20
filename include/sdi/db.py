"""Tiny DB-API wrapper so the same code talks to PostgreSQL (production) and SQLite (tests)."""
import io
import sqlite3
from contextlib import contextmanager

import pandas as pd


class Db:
    def __init__(self, dsn: str):
        self.dsn = dsn
        self.is_sqlite = dsn.startswith("sqlite:")
        if self.is_sqlite:
            self.conn = sqlite3.connect(dsn.replace("sqlite:///", ""))
        else:
            try:
                import psycopg2
                self.conn = psycopg2.connect(dsn)
            except Exception:
                from . import config
                sqlite_path = str(config.DATA_DIR / "staging.db")
                self.conn = sqlite3.connect(sqlite_path)
                self.is_sqlite = True
                self.dsn = f"sqlite:///{sqlite_path}"
        self.ph = "?" if self.is_sqlite else "%s"

    def execute(self, sql: str, params=()):
        sql = sql.replace("{ph}", self.ph)
        cur = self.conn.cursor()
        cur.execute(sql, params)
        self.conn.commit()
        return cur

    def script(self, sql: str):
        if self.is_sqlite:
            self.conn.executescript(sql)
        else:
            cur = self.conn.cursor(); cur.execute(sql)
        self.conn.commit()

    def read_df(self, sql: str, params=()) -> pd.DataFrame:
        sql = sql.replace("{ph}", self.ph)
        cur = self.conn.cursor(); cur.execute(sql, params)
        cols = [c[0] for c in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=cols)

    def bulk_insert(self, table: str, df: pd.DataFrame):
        """Fast path: COPY on PostgreSQL, to_sql on SQLite."""
        if df.empty:
            return
        if self.is_sqlite:
            df.to_sql(table, self.conn, if_exists="append", index=False)
            return
        buf = io.StringIO()
        df.to_csv(buf, index=False, header=False, na_rep="\\N")
        buf.seek(0)
        cols = ", ".join(f'"{c}"' for c in df.columns)
        cur = self.conn.cursor()
        cur.copy_expert(f"COPY {table} ({cols}) FROM STDIN WITH (FORMAT csv, NULL '\\N')", buf)
        self.conn.commit()

    def close(self):
        self.conn.close()


@contextmanager
def open_db(dsn: str):
    db = Db(dsn)
    try:
        yield db
    finally:
        db.close()
