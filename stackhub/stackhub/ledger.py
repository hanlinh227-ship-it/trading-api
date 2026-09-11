from __future__ import annotations

import sqlite3
from pathlib import Path


class Ledger:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS earnings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    amount_usd REAL NOT NULL,
                    asset TEXT NOT NULL,
                    amount_asset REAL NOT NULL,
                    timestamp TEXT NOT NULL
                )
                """
            )

    def record(
        self,
        source: str,
        amount_usd: float,
        asset: str,
        amount_asset: float,
        timestamp: str,
    ) -> None:
        if amount_usd < 0 or amount_asset < 0:
            raise ValueError("Earning amounts must be non-negative")
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO earnings(source, amount_usd, asset, amount_asset, timestamp) VALUES (?, ?, ?, ?, ?)",
                (source, float(amount_usd), asset.upper(), float(amount_asset), timestamp),
            )

    def summary(self) -> dict:
        with self._connect() as conn:
            total_usd, entries = conn.execute(
                "SELECT COALESCE(SUM(amount_usd), 0), COUNT(*) FROM earnings"
            ).fetchone()
            rows = conn.execute(
                "SELECT asset, COALESCE(SUM(amount_asset), 0) FROM earnings GROUP BY asset ORDER BY asset"
            ).fetchall()
        return {
            "total_usd": float(total_usd),
            "entries": int(entries),
            "assets": {asset: float(total) for asset, total in rows},
        }
