from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .models import PositionSnapshot, QuoteSnapshot, SignalDecision


class SQLiteJournal:
    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self._init_schema()

    def _init_schema(self) -> None:
        cursor = self.connection.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS tick_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT,
                symbol TEXT NOT NULL,
                last_price REAL NOT NULL,
                spread_bps REAL,
                imbalance REAL,
                momentum REAL,
                raw_json TEXT
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS signal_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT,
                symbol TEXT NOT NULL,
                action TEXT NOT NULL,
                score REAL NOT NULL,
                reason TEXT NOT NULL,
                pnl_pct REAL,
                drawdown_pct REAL,
                position_qty INTEGER,
                suggested_shares INTEGER
            )
            """
        )
        self.connection.commit()

    def record_tick(self, quote: QuoteSnapshot, decision: SignalDecision) -> None:
        metrics = decision.metrics
        self.connection.execute(
            """
            INSERT INTO tick_snapshots (
                ts, symbol, last_price, spread_bps, imbalance, momentum, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                quote.timestamp,
                quote.symbol,
                quote.last_price,
                metrics.spread_bps,
                metrics.imbalance,
                metrics.momentum,
                json.dumps(quote.raw, ensure_ascii=False, default=str),
            ),
        )
        self.connection.commit()

    def record_signal(
        self,
        quote: QuoteSnapshot,
        decision: SignalDecision,
        position: PositionSnapshot | None,
    ) -> None:
        metrics = decision.metrics
        self.connection.execute(
            """
            INSERT INTO signal_events (
                ts, symbol, action, score, reason, pnl_pct, drawdown_pct, position_qty, suggested_shares
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                quote.timestamp,
                quote.symbol,
                decision.action,
                decision.score,
                decision.reason,
                metrics.pnl_pct,
                metrics.drawdown_pct,
                position.quantity if position else 0,
                decision.suggested_shares,
            ),
        )
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()
