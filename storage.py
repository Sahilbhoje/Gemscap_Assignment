from pathlib import Path
from typing import Dict

import pandas as pd
import sqlite3


class Storage:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as con:
            cur = con.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS ticks (
                    symbol TEXT NOT NULL,
                    ts TEXT NOT NULL,
                    price REAL NOT NULL,
                    size REAL NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS ohlcv (
                    symbol TEXT NOT NULL,
                    bucket TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    open REAL, high REAL, low REAL, close REAL, volume REAL,
                    PRIMARY KEY(symbol, bucket, timeframe)
                )
                """
            )
            con.commit()

    def append_ticks(self, df: pd.DataFrame, symbol: str):
        if df.empty:
            return
        out = df.reset_index()[["ts", "price", "size"]].copy()
        out["symbol"] = symbol
        out = out[["symbol", "ts", "price", "size"]]
        with sqlite3.connect(self.db_path) as con:
            out.to_sql("ticks", con, if_exists="append", index=False)

    def upsert_ohlcv(self, df: pd.DataFrame, symbol: str, timeframe: str):
        if df.empty:
            return
        out = df.reset_index().copy()
        # Ensure a 'bucket' column exists representing the resample timestamp bucket
        if "bucket" not in out.columns:
            if "index" in out.columns:
                out = out.rename(columns={"index": "bucket"})
            else:
                # If the index had a name, rename that column; otherwise create from first column
                idx_name = df.index.name
                if idx_name and idx_name in out.columns:
                    out = out.rename(columns={idx_name: "bucket"})
                else:
                    # As a fallback, construct bucket from the original index values
                    out["bucket"] = df.index.to_series().values
        out["symbol"] = symbol
        out["timeframe"] = timeframe
        # Convert bucket to ISO8601 string for SQLite compatibility
        # Normalize bucket to ISO8601 string for SQLite
        try:
            # Ensure timezone-aware UTC and format
            dt = pd.to_datetime(out["bucket"], utc=True, errors="coerce")
            # If conversion failed for some rows, fill using astype(str)
            if dt.isna().any():
                out["bucket"] = out["bucket"].astype(str)
            else:
                out["bucket"] = dt.dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        except Exception:
            out["bucket"] = out["bucket"].astype(str)
        cols = ["symbol", "bucket", "timeframe", "open", "high", "low", "close", "volume"]
        out = out[cols]
        with sqlite3.connect(self.db_path) as con:
            cur = con.cursor()
            cur.executemany(
                """
                INSERT INTO ohlcv(symbol, bucket, timeframe, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol, bucket, timeframe) DO UPDATE SET
                    open=excluded.open,
                    high=excluded.high,
                    low=excluded.low,
                    close=excluded.close,
                    volume=excluded.volume
                """,
                [tuple(r) for r in out.to_records(index=False)],
            )
            con.commit()
