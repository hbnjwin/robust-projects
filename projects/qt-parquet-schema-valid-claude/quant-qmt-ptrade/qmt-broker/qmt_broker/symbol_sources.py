from dataclasses import dataclass, field
from typing import Dict, List, Tuple


def _normalize_symbol(raw: object) -> str:
    text = str(raw or "").strip().upper()
    return text


@dataclass
class SymbolSourceSnapshot:
    symbols: Tuple[str, ...]
    metadata: Dict[str, object]
    watchlist_symbols: Tuple[str, ...] = ()
    position_symbols: Tuple[str, ...] = ()
    symbol_names: Dict[str, str] = field(default_factory=dict)


class PostgresSymbolSource:
    def __init__(
        self,
        dsn: str,
        schema: str = "public",
        watchlist_table: str = "watchlist",
        positions_table: str = "paper_positions",
        security_master_dsn: str = "",
        security_master_schema: str = "public",
        security_master_table: str = "security_master_cn",
    ) -> None:
        self._dsn = dsn
        self._schema = schema
        self._watchlist_table = watchlist_table
        self._positions_table = positions_table
        self._security_master_dsn = str(security_master_dsn or dsn or "").strip()
        self._security_master_schema = str(security_master_schema or "public").strip() or "public"
        self._security_master_table = str(security_master_table or "security_master_cn").strip() or "security_master_cn"

    def load(self) -> SymbolSourceSnapshot:
        try:
            import psycopg
            from psycopg import sql
        except Exception as exc:
            raise RuntimeError("psycopg is required for PostgreSQL watchlist bootstrap") from exc

        watchlist_symbols: List[str] = []
        position_symbols: List[str] = []
        watchlist_names: Dict[str, str] = {}
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                watchlist_query = sql.SQL("SELECT ts_code, COALESCE(name, '') FROM {}.{} WHERE ts_code IS NOT NULL").format(
                    sql.Identifier(self._schema),
                    sql.Identifier(self._watchlist_table),
                )
                cur.execute(watchlist_query)
                for raw_symbol, raw_name in cur.fetchall():
                    symbol = _normalize_symbol(raw_symbol)
                    if not symbol:
                        continue
                    watchlist_symbols.append(symbol)
                    name = str(raw_name or "").strip()
                    if name:
                        watchlist_names[symbol] = name

                positions_query = sql.SQL(
                    """
                    SELECT ts_code
                    FROM {}.{}
                    WHERE ts_code IS NOT NULL
                      AND COALESCE(shares, 0) > 0
                      AND trade_date = (SELECT MAX(trade_date) FROM {}.{})
                    """
                ).format(
                    sql.Identifier(self._schema),
                    sql.Identifier(self._positions_table),
                    sql.Identifier(self._schema),
                    sql.Identifier(self._positions_table),
                )
                cur.execute(positions_query)
                position_symbols = [_normalize_symbol(row[0]) for row in cur.fetchall() if _normalize_symbol(row[0])]

        merged = tuple(sorted(set(watchlist_symbols) | set(position_symbols)))
        symbol_names = dict(watchlist_names)
        for symbol, name in self._load_security_master_names(merged).items():
            if symbol not in symbol_names and name:
                symbol_names[symbol] = name
        return SymbolSourceSnapshot(
            symbols=merged,
            metadata={
                "source": "postgres",
                "schema": self._schema,
                "watchlist_table": self._watchlist_table,
                "positions_table": self._positions_table,
                "watchlist_count": len(set(watchlist_symbols)),
                "positions_count": len(set(position_symbols)),
                "symbol_count": len(merged),
                "named_count": len(symbol_names),
            },
            watchlist_symbols=tuple(sorted(set(watchlist_symbols))),
            position_symbols=tuple(sorted(set(position_symbols))),
            symbol_names=symbol_names,
        )

    def _load_security_master_names(self, symbols: Tuple[str, ...]) -> Dict[str, str]:
        if not symbols or not self._security_master_dsn:
            return {}
        try:
            import psycopg
            from psycopg import sql
        except Exception:
            return {}

        try:
            with psycopg.connect(self._security_master_dsn) as conn:
                with conn.cursor() as cur:
                    query = sql.SQL(
                        """
                        SELECT ts_code, COALESCE(name, '')
                        FROM {}.{}
                        WHERE ts_code = ANY(%s)
                        """
                    ).format(
                        sql.Identifier(self._security_master_schema),
                        sql.Identifier(self._security_master_table),
                    )
                    cur.execute(query, (list(symbols),))
                    rows = cur.fetchall()
        except Exception:
            return {}

        result: Dict[str, str] = {}
        for raw_symbol, raw_name in rows:
            symbol = _normalize_symbol(raw_symbol)
            name = str(raw_name or "").strip()
            if symbol and name:
                result[symbol] = name
        return result
