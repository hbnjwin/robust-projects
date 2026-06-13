from __future__ import annotations

from collections.abc import Mapping, Sequence
import json
from dataclasses import asdict
from datetime import datetime
from typing import Any

from .config import PostgresConfig, normalize_symbol
from .models import PositionSnapshot, QuoteSnapshot, SignalDecision

try:
    import psycopg2
    from psycopg2.extras import Json
except Exception:  # pragma: no cover - optional dependency in runtime
    psycopg2 = None
    Json = None


def _top_of_book(levels: list[Any]) -> tuple[float | None, float | None]:
    if not levels:
        return None, None
    first = levels[0]
    price = getattr(first, "price", None)
    volume = getattr(first, "volume", None)
    return price, volume


def _json_ready(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_json_ready(item) for item in value]
    if hasattr(value, "to_dict") and callable(value.to_dict):
        try:
            return _json_ready(value.to_dict(orient="records"))
        except TypeError:
            return _json_ready(value.to_dict())
        except Exception:
            pass
    if hasattr(value, "tolist") and callable(value.tolist):
        try:
            return _json_ready(value.tolist())
        except Exception:
            pass
    return str(value)


def _payload_count(payload: Any, symbol: str | None = None) -> int:
    resolved = payload
    if symbol and isinstance(payload, Mapping) and symbol in payload:
        resolved = payload[symbol]
    if resolved is None:
        return 0
    if isinstance(resolved, Sequence) and not isinstance(resolved, (str, bytes, bytearray)):
        return len(resolved)
    if hasattr(resolved, "__len__"):
        try:
            return len(resolved)
        except Exception:
            return 1
    return 1


class PostgresRuntimeStore:
    def __init__(self, config: PostgresConfig):
        if psycopg2 is None or Json is None:
            raise RuntimeError("psycopg2 is not available")
        self.config = config
        self.connection = psycopg2.connect(
            host=config.host,
            port=config.port,
            dbname=config.database,
            user=config.user,
            password=config.password,
            connect_timeout=config.connect_timeout_seconds,
        )
        self.connection.autocommit = True
        self._resolved_watchlist_table: str | None = None

    @property
    def is_enabled(self) -> bool:
        return self.config.enabled

    def close(self) -> None:
        self.connection.close()

    def _table_exists(self, table_name: str) -> bool:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                select exists (
                    select 1
                    from information_schema.tables
                    where table_schema = 'public' and table_name = %s
                )
                """,
                (table_name,),
            )
            row = cursor.fetchone()
        return bool(row and row[0])

    def resolve_watchlist_table(self) -> str | None:
        if self._resolved_watchlist_table is not None:
            return self._resolved_watchlist_table
        for table_name in self.config.watchlist_table_priority or []:
            if self._table_exists(table_name):
                self._resolved_watchlist_table = table_name
                return table_name
        return None

    def load_watchlist(self) -> tuple[str | None, list[str]]:
        table_name = self.resolve_watchlist_table()
        if table_name is None:
            return None, []

        with self.connection.cursor() as cursor:
            cursor.execute(f"select ts_code from public.{table_name} where ts_code is not null order by ts_code")
            rows = cursor.fetchall()
        watchlist = sorted({normalize_symbol(row[0]) for row in rows if row and row[0]})
        return table_name, watchlist

    def upsert_positions(self, strategy_name: str, positions: dict[str, PositionSnapshot]) -> None:
        if not self.config.write_positions or not positions:
            return

        sql = f"""
            insert into public.{self.config.positions_table} (
                account_id,
                strategy_name,
                symbol,
                quantity,
                available_quantity,
                cost_basis,
                last_price,
                source_update_time,
                raw_json,
                updated_at
            ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, now())
            on conflict (account_id, strategy_name, symbol) do update set
                quantity = excluded.quantity,
                available_quantity = excluded.available_quantity,
                cost_basis = excluded.cost_basis,
                last_price = excluded.last_price,
                source_update_time = excluded.source_update_time,
                raw_json = excluded.raw_json,
                updated_at = now()
        """
        with self.connection.cursor() as cursor:
            for symbol, position in positions.items():
                payload = Json(asdict(position))
                cursor.execute(
                    sql,
                    (
                        self.config.account_id,
                        strategy_name,
                        normalize_symbol(symbol),
                        position.quantity,
                        position.available_quantity,
                        position.cost_basis,
                        position.last_price,
                        position.update_time,
                        payload,
                    ),
                )

    def insert_tick_raw(
        self,
        strategy_name: str,
        quote: QuoteSnapshot,
        decision: SignalDecision,
        capture: dict[str, Any] | None = None,
    ) -> None:
        if not self.config.write_ticks:
            return

        capture = capture or {}
        bid1_price, bid1_volume = _top_of_book(quote.bid)
        ask1_price, ask1_volume = _top_of_book(quote.ask)
        metrics = decision.metrics
        sql = f"""
            insert into public.{self.config.tick_table} (
                account_id,
                strategy_name,
                source,
                trade_date,
                symbol,
                quote_time_text,
                last_price,
                open_price,
                high_price,
                low_price,
                pre_close,
                volume,
                turnover,
                bid1_price,
                bid1_volume,
                ask1_price,
                ask1_volume,
                quote_source,
                has_l2,
                bid_level_count,
                ask_level_count,
                spread_bps,
                imbalance,
                momentum,
                entrust_count,
                transaction_count,
                action,
                score,
                tick_payload_json,
                entrust_payload_json,
                transaction_payload_json,
                raw_json,
                created_at
            ) values (
                %s,
                %s,
                %s,
                current_date,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                now()
            )
        """
        tick_payload = _json_ready(capture.get("tick_payload", quote.raw))
        entrust_payload = _json_ready(capture.get("entrust_payload"))
        transaction_payload = _json_ready(capture.get("transaction_payload"))
        quote_source = str(capture.get("quote_source", "tick_data"))
        has_l2 = bool(quote.bid or quote.ask)
        with self.connection.cursor() as cursor:
            cursor.execute(
                sql,
                (
                    self.config.account_id,
                    strategy_name,
                    self.config.source,
                    normalize_symbol(quote.symbol),
                    quote.timestamp,
                    quote.last_price,
                    quote.open_price,
                    quote.high_price,
                    quote.low_price,
                    quote.pre_close,
                    quote.volume,
                    quote.turnover,
                    bid1_price,
                    bid1_volume,
                    ask1_price,
                    ask1_volume,
                    quote_source,
                    has_l2,
                    len(quote.bid),
                    len(quote.ask),
                    metrics.spread_bps,
                    metrics.imbalance,
                    metrics.momentum,
                    _payload_count(entrust_payload, quote.symbol),
                    _payload_count(transaction_payload, quote.symbol),
                    decision.action,
                    decision.score,
                    Json(tick_payload),
                    Json(entrust_payload),
                    Json(transaction_payload),
                    Json(
                        {
                            "quote": asdict(quote),
                            "decision": asdict(decision),
                            "quote_source": quote_source,
                            "has_l2": has_l2,
                            "captured_at": datetime.now().isoformat(),
                        }
                    ),
                ),
            )
