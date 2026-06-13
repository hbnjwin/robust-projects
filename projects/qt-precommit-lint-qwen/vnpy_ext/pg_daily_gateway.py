"""
PgDailyGateway - 从 PostgreSQL daily_price 表读取日线数据，转换为 vnpy TickData 推送。

用于 T+1 日线级别模拟盘，不提供实时行情。
每次调用 replay_date() 推送指定日期的全市场行情快照。
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import psycopg

from vnpy.event import EventEngine
from vnpy.trader.gateway import BaseGateway
from vnpy.trader.object import (
    TickData,
    BarData,
    ContractData,
    SubscribeRequest,
    OrderRequest,
    CancelRequest,
    HistoryRequest,
    AccountData,
)
from vnpy.trader.constant import Exchange, Product, Direction


# ts_code 后缀 → vnpy Exchange 映射
MARKET_MAP: dict[str, Exchange] = {
    "SH": Exchange.SSE,
    "SZ": Exchange.SZSE,
    "BJ": Exchange.BSE,
}

# vnpy Exchange.value → ts_code 后缀（反向映射）
EXCHANGE_TO_MARKET: dict[str, str] = {
    "SSE": "SH",
    "SZSE": "SZ",
    "BSE": "BJ",
}


def parse_ts_code(ts_code: str) -> tuple[str, Exchange]:
    """将 '000001.SZ' 转换为 ('000001', Exchange.SZSE)"""
    parts = ts_code.split(".")
    symbol = parts[0]
    market = parts[1] if len(parts) > 1 else "SZ"
    exchange = MARKET_MAP.get(market, Exchange.SZSE)
    return symbol, exchange


def to_ts_code(symbol: str, exchange: Exchange) -> str:
    """将 vnpy 格式转回 ts_code，如 ('000001', Exchange.SZSE) → '000001.SZ'"""
    market = EXCHANGE_TO_MARKET.get(exchange.value, exchange.value)
    return f"{symbol}.{market}"


class PgDailyGateway(BaseGateway):
    """从 PostgreSQL daily_price 读取日线数据的 Gateway"""

    default_name: str = "PG_DAILY"
    default_setting: dict = {
        "host": "localhost",
        "port": 5432,
        "user": "postgres",
        "password": "limit123",
        "dbname": "quant",
    }
    exchanges: list[Exchange] = [Exchange.SSE, Exchange.SZSE, Exchange.BSE]

    def __init__(self, event_engine: EventEngine, gateway_name: str = "PG_DAILY") -> None:
        super().__init__(event_engine, gateway_name)
        self.conn: Optional[psycopg.Connection] = None
        self.contracts: dict[str, ContractData] = {}
        self.subscribed: set[str] = set()
        self.account_balance: float = 1_000_000.0

    def connect(self, setting: dict) -> None:
        """连接 PostgreSQL"""
        try:
            self.conn = psycopg.connect(
                host=setting.get("host", "localhost"),
                port=setting.get("port", 5432),
                user=setting.get("user", "postgres"),
                password=setting.get("password", "limit123"),
                dbname=setting.get("dbname", "quant"),
            )
            self.write_log("PostgreSQL 连接成功")
            self._load_contracts()
            self._push_account()
        except Exception as e:
            self.write_log(f"PostgreSQL 连接失败: {e}")

    def _load_contracts(self) -> None:
        """从 daily_price 加载所有股票代码，注册为 ContractData"""
        if not self.conn:
            return

        cur = self.conn.cursor()
        cur.execute("SELECT DISTINCT ts_code FROM daily_price")
        rows = cur.fetchall()

        for (ts_code,) in rows:
            symbol, exchange = parse_ts_code(ts_code)
            contract = ContractData(
                symbol=symbol,
                exchange=exchange,
                name=ts_code,
                product=Product.EQUITY,
                size=100,  # A股 1手 = 100股
                pricetick=0.01,
                min_volume=100,
                net_position=True,  # A股用净持仓模式
                history_data=True,
                gateway_name=self.gateway_name,
            )
            self.contracts[ts_code] = contract
            self.on_contract(contract)

        self.write_log(f"合约加载完成: {len(self.contracts)} 只股票")

    def _push_account(self) -> None:
        """推送账户信息"""
        account = AccountData(
            accountid="paper",
            balance=self.account_balance,
            frozen=0,
            gateway_name=self.gateway_name,
        )
        self.on_account(account)

    def subscribe(self, req: SubscribeRequest) -> None:
        """订阅行情（记录订阅列表，replay_date 时只推送已订阅的）"""
        self.subscribed.add(req.vt_symbol)
        self.write_log(f"订阅行情: {req.vt_symbol}")

    def replay_date(self, trade_date: str, ts_codes: list[str] | None = None) -> dict[str, TickData]:
        """
        推送指定日期的日线行情。

        Args:
            trade_date: 日期字符串 'YYYY-MM-DD'
            ts_codes: 可选，指定股票列表。None 则推送全市场。

        Returns:
            dict[ts_code, TickData]: 推送的行情数据
        """
        if not self.conn:
            self.write_log("未连接 PostgreSQL")
            return {}

        cur = self.conn.cursor()

        if ts_codes:
            placeholders = ",".join(["%s"] * len(ts_codes))
            cur.execute(
                f"SELECT ts_code, open, high, low, close, vol "
                f"FROM daily_price WHERE trade_date = %s AND ts_code IN ({placeholders})",
                [trade_date] + ts_codes,
            )
        else:
            cur.execute(
                "SELECT ts_code, open, high, low, close, vol FROM daily_price WHERE trade_date = %s",
                (trade_date,),
            )

        rows = cur.fetchall()
        ticks: dict[str, TickData] = {}

        dt = datetime.strptime(trade_date, "%Y-%m-%d").replace(hour=15, minute=0, second=0)

        for ts_code, open_p, high_p, low_p, close_p, vol in rows:
            symbol, exchange = parse_ts_code(ts_code)

            # 构造 TickData：用收盘价模拟盘口
            tick = TickData(
                symbol=symbol,
                exchange=exchange,
                datetime=dt,
                name=ts_code,
                volume=vol or 0,
                last_price=close_p or 0,
                open_price=open_p or 0,
                high_price=high_p or 0,
                low_price=low_p or 0,
                pre_close=0,
                # 用收盘价填充买卖盘口（PaperEngine 撮合需要）
                bid_price_1=close_p or 0,
                ask_price_1=close_p or 0,
                bid_volume_1=10000,
                ask_volume_1=10000,
                # 涨跌停价（±10%，简化处理）
                limit_up=round((close_p or 0) * 1.1, 2),
                limit_down=round((close_p or 0) * 0.9, 2),
                gateway_name=self.gateway_name,
            )
            self.on_tick(tick)
            ticks[ts_code] = tick

        self.write_log(f"推送 {trade_date} 行情: {len(ticks)} 只股票")
        return ticks

    def query_history(self, req: HistoryRequest) -> list[BarData]:
        """查询历史 K 线"""
        if not self.conn:
            return []

        cur = self.conn.cursor()
        ts_code = f"{req.symbol}.{req.exchange.value}"

        cur.execute(
            "SELECT trade_date, open, high, low, close, vol "
            "FROM daily_price WHERE ts_code = %s AND trade_date BETWEEN %s AND %s "
            "ORDER BY trade_date",
            (ts_code, req.start.strftime("%Y-%m-%d"), req.end.strftime("%Y-%m-%d") if req.end else "2099-12-31"),
        )

        bars: list[BarData] = []
        for trade_date, open_p, high_p, low_p, close_p, vol in cur.fetchall():
            bar = BarData(
                symbol=req.symbol,
                exchange=req.exchange,
                datetime=datetime.combine(trade_date, datetime.min.time()),
                open_price=open_p or 0,
                high_price=high_p or 0,
                low_price=low_p or 0,
                close_price=close_p or 0,
                volume=vol or 0,
                gateway_name=self.gateway_name,
            )
            bars.append(bar)

        return bars

    def send_order(self, req: OrderRequest) -> str:
        """日线 Gateway 不直接下单，由 PaperEngine 接管"""
        return ""

    def cancel_order(self, req: CancelRequest) -> None:
        pass

    def query_account(self) -> None:
        self._push_account()

    def query_position(self) -> None:
        pass

    def close(self) -> None:
        if self.conn:
            self.conn.close()
            self.conn = None
            self.write_log("PostgreSQL 连接已关闭")
