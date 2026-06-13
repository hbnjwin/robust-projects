"""
TxRealtimeGateway - 腾讯实时行情 Gateway

通过腾讯 HTTP 行情接口 (qt.gtimg.cn) 获取 A 股实时行情，转换为 vnpy TickData。
免费、无需 API Key、支持批量查询、含五档盘口和涨跌停价。

用于盘中实时模拟盘，配合 PaperEngine 使用。
"""

from __future__ import annotations

import threading
import time
import urllib.request
from datetime import datetime
from typing import Optional

from vnpy.event import EventEngine
from vnpy.trader.gateway import BaseGateway
from vnpy.trader.object import (
    TickData,
    ContractData,
    SubscribeRequest,
    OrderRequest,
    CancelRequest,
    HistoryRequest,
    BarData,
    AccountData,
)
from vnpy.trader.constant import Exchange, Product

from .pg_daily_gateway import MARKET_MAP, EXCHANGE_TO_MARKET, parse_ts_code, to_ts_code


# vnpy Exchange → 腾讯行情前缀
EXCHANGE_TO_TX_PREFIX: dict[Exchange, str] = {
    Exchange.SSE: "sh",
    Exchange.SZSE: "sz",
    Exchange.BSE: "bj",
}

# 腾讯行情前缀 → vnpy Exchange
TX_PREFIX_TO_EXCHANGE: dict[str, Exchange] = {
    "sh": Exchange.SSE,
    "sz": Exchange.SZSE,
    "bj": Exchange.BSE,
}

# 腾讯行情字段索引（88 字段格式）
TX_FIELD = {
    "name": 1,
    "code": 2,
    "last_price": 3,
    "pre_close": 4,
    "open": 5,
    "volume": 6,  # 成交量（手）
    "bid_price_1": 9,
    "bid_volume_1": 10,
    "bid_price_2": 11,
    "bid_volume_2": 12,
    "bid_price_3": 13,
    "bid_volume_3": 14,
    "bid_price_4": 15,
    "bid_volume_4": 16,
    "bid_price_5": 17,
    "bid_volume_5": 18,
    "ask_price_1": 19,
    "ask_volume_1": 20,
    "ask_price_2": 21,
    "ask_volume_2": 22,
    "ask_price_3": 23,
    "ask_volume_3": 24,
    "ask_price_4": 25,
    "ask_volume_4": 26,
    "ask_price_5": 27,
    "ask_volume_5": 28,
    "datetime": 30,  # 20260313161442
    "high": 33,
    "low": 34,
    "turnover": 37,  # 成交额（万元）
    "limit_up": 47,
    "limit_down": 48,
}

# 每次批量请求的最大股票数
BATCH_SIZE = 80
# 默认轮询间隔（秒）
DEFAULT_POLL_INTERVAL = 3.0

TX_API_URL = "https://qt.gtimg.cn/q="
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"


def _safe_float(val: str, default: float = 0.0) -> float:
    """安全转换浮点数"""
    try:
        return float(val) if val.strip() else default
    except (ValueError, TypeError):
        return default


def _safe_int(val: str, default: int = 0) -> int:
    """安全转换整数"""
    try:
        return int(float(val)) if val.strip() else default
    except (ValueError, TypeError):
        return default


class TxRealtimeGateway(BaseGateway):
    """腾讯实时行情 Gateway"""

    default_name: str = "TX_REALTIME"
    default_setting: dict = {
        "poll_interval": DEFAULT_POLL_INTERVAL,
    }
    exchanges: list[Exchange] = [Exchange.SSE, Exchange.SZSE, Exchange.BSE]

    def __init__(self, event_engine: EventEngine, gateway_name: str = "TX_REALTIME") -> None:
        super().__init__(event_engine, gateway_name)

        self.subscribed_symbols: dict[str, SubscribeRequest] = {}  # vt_symbol → req
        self.poll_interval: float = DEFAULT_POLL_INTERVAL
        self.poll_thread: Optional[threading.Thread] = None
        self.poll_active: bool = False
        self.contracts: dict[str, ContractData] = {}

    def connect(self, setting: dict) -> None:
        """启动 Gateway"""
        self.poll_interval = setting.get("poll_interval", DEFAULT_POLL_INTERVAL)
        self.write_log(f"腾讯实时行情 Gateway 启动，轮询间隔 {self.poll_interval}s")

    def subscribe(self, req: SubscribeRequest) -> None:
        """订阅行情"""
        self.subscribed_symbols[req.vt_symbol] = req

        # 注册合约（如果还没注册）
        if req.vt_symbol not in self.contracts:
            contract = ContractData(
                symbol=req.symbol,
                exchange=req.exchange,
                name=req.vt_symbol,
                product=Product.EQUITY,
                size=100,
                pricetick=0.01,
                min_volume=100,
                net_position=True,
                history_data=False,
                gateway_name=self.gateway_name,
            )
            self.contracts[req.vt_symbol] = contract
            self.on_contract(contract)

        self.write_log(f"订阅行情: {req.vt_symbol}")

    def subscribe_batch(self, ts_codes: list[str]) -> None:
        """批量订阅（ts_code 格式如 '000001.SZ'）"""
        for ts_code in ts_codes:
            symbol, exchange = parse_ts_code(ts_code)
            req = SubscribeRequest(symbol=symbol, exchange=exchange)
            self.subscribe(req)

    def start_polling(self) -> None:
        """启动轮询线程"""
        if self.poll_active:
            return

        self.poll_active = True
        self.poll_thread = threading.Thread(target=self._poll_loop, name="tx-realtime-poll", daemon=True)
        self.poll_thread.start()
        self.write_log("行情轮询已启动")

    def stop_polling(self) -> None:
        """停止轮询"""
        self.poll_active = False
        if self.poll_thread:
            self.poll_thread.join(timeout=10)
            self.poll_thread = None
        self.write_log("行情轮询已停止")

    def _poll_loop(self) -> None:
        """轮询主循环"""
        while self.poll_active:
            try:
                self.fetch_and_push()
            except Exception as e:
                self.write_log(f"行情轮询异常: {e}")
            time.sleep(self.poll_interval)

    def fetch_and_push(self) -> dict[str, TickData]:
        """
        一次性获取所有已订阅股票的实时行情并推送。

        Returns:
            {ts_code: TickData}
        """
        if not self.subscribed_symbols:
            return {}

        # 构建腾讯行情查询代码列表
        tx_codes: list[str] = []
        vt_to_tx: dict[str, str] = {}

        for vt_symbol, req in self.subscribed_symbols.items():
            prefix = EXCHANGE_TO_TX_PREFIX.get(req.exchange)
            if prefix:
                tx_code = f"{prefix}{req.symbol}"
                tx_codes.append(tx_code)
                vt_to_tx[tx_code] = vt_symbol

        if not tx_codes:
            return {}

        # 分批请求
        all_ticks: dict[str, TickData] = {}

        for i in range(0, len(tx_codes), BATCH_SIZE):
            batch = tx_codes[i : i + BATCH_SIZE]
            batch_ticks = self._fetch_batch(batch, vt_to_tx)
            all_ticks.update(batch_ticks)

            # 批次间短暂延迟避免限频
            if i + BATCH_SIZE < len(tx_codes):
                time.sleep(0.2)

        return all_ticks

    def _fetch_batch(self, tx_codes: list[str], vt_to_tx: dict[str, str]) -> dict[str, TickData]:
        """获取一批股票的实时行情"""
        url = TX_API_URL + ",".join(tx_codes)
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

        try:
            resp = urllib.request.urlopen(req, timeout=10)
            data = resp.read().decode("gbk")
        except Exception as e:
            self.write_log(f"HTTP 请求失败: {e}")
            return {}

        ticks: dict[str, TickData] = {}

        for line in data.strip().split("\n"):
            line = line.strip()
            if not line or "=" not in line:
                continue

            parts = line.split("=", 1)
            key = parts[0].strip()  # v_sz000001
            val = parts[1].strip().strip(";").strip('"')
            fields = val.split("~")

            if len(fields) < 50:
                continue

            # 提取腾讯代码
            tx_code = key.replace("v_", "")
            vt_symbol = vt_to_tx.get(tx_code)
            if not vt_symbol:
                continue

            # 解析 vt_symbol
            sub_req = self.subscribed_symbols.get(vt_symbol)
            if not sub_req:
                continue

            # 解析时间
            dt_str = fields[TX_FIELD["datetime"]]
            try:
                dt = datetime.strptime(dt_str, "%Y%m%d%H%M%S")
            except (ValueError, IndexError):
                dt = datetime.now()

            tick = TickData(
                symbol=sub_req.symbol,
                exchange=sub_req.exchange,
                datetime=dt,
                name=fields[TX_FIELD["name"]],
                volume=_safe_float(fields[TX_FIELD["volume"]]),
                turnover=_safe_float(fields[TX_FIELD["turnover"]]) * 10000,  # 万元→元
                last_price=_safe_float(fields[TX_FIELD["last_price"]]),
                open_price=_safe_float(fields[TX_FIELD["open"]]),
                high_price=_safe_float(fields[TX_FIELD["high"]]),
                low_price=_safe_float(fields[TX_FIELD["low"]]),
                pre_close=_safe_float(fields[TX_FIELD["pre_close"]]),
                bid_price_1=_safe_float(fields[TX_FIELD["bid_price_1"]]),
                bid_price_2=_safe_float(fields[TX_FIELD["bid_price_2"]]),
                bid_price_3=_safe_float(fields[TX_FIELD["bid_price_3"]]),
                bid_price_4=_safe_float(fields[TX_FIELD["bid_price_4"]]),
                bid_price_5=_safe_float(fields[TX_FIELD["bid_price_5"]]),
                ask_price_1=_safe_float(fields[TX_FIELD["ask_price_1"]]),
                ask_price_2=_safe_float(fields[TX_FIELD["ask_price_2"]]),
                ask_price_3=_safe_float(fields[TX_FIELD["ask_price_3"]]),
                ask_price_4=_safe_float(fields[TX_FIELD["ask_price_4"]]),
                ask_price_5=_safe_float(fields[TX_FIELD["ask_price_5"]]),
                bid_volume_1=_safe_float(fields[TX_FIELD["bid_volume_1"]]),
                bid_volume_2=_safe_float(fields[TX_FIELD["bid_volume_2"]]),
                bid_volume_3=_safe_float(fields[TX_FIELD["bid_volume_3"]]),
                bid_volume_4=_safe_float(fields[TX_FIELD["bid_volume_4"]]),
                bid_volume_5=_safe_float(fields[TX_FIELD["bid_volume_5"]]),
                ask_volume_1=_safe_float(fields[TX_FIELD["ask_volume_1"]]),
                ask_volume_2=_safe_float(fields[TX_FIELD["ask_volume_2"]]),
                ask_volume_3=_safe_float(fields[TX_FIELD["ask_volume_3"]]),
                ask_volume_4=_safe_float(fields[TX_FIELD["ask_volume_4"]]),
                ask_volume_5=_safe_float(fields[TX_FIELD["ask_volume_5"]]),
                limit_up=_safe_float(fields[TX_FIELD["limit_up"]]),
                limit_down=_safe_float(fields[TX_FIELD["limit_down"]]),
                gateway_name=self.gateway_name,
            )

            self.on_tick(tick)
            ts_code = to_ts_code(sub_req.symbol, sub_req.exchange)
            ticks[ts_code] = tick

        return ticks

    def send_order(self, req: OrderRequest) -> str:
        """实时 Gateway 不直接下单，由 PaperEngine 接管"""
        return ""

    def cancel_order(self, req: CancelRequest) -> None:
        pass

    def query_account(self) -> None:
        pass

    def query_position(self) -> None:
        pass

    def query_history(self, req: HistoryRequest) -> list[BarData]:
        return []

    def close(self) -> None:
        self.stop_polling()
        self.write_log("腾讯实时行情 Gateway 已关闭")
