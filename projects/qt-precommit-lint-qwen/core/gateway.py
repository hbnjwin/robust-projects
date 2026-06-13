"""
core/gateway.py — BaseGateway 抽象层

所有实盘/模拟盘 Gateway 继承此类。
参考 vnpy BaseGateway 设计，简化为 A 股日频场景。

子类必须实现:
  connect()      — 建立连接
  disconnect()   — 断开连接
  subscribe(codes) — 订阅行情
  send_order(order) → str  — 发送订单，返回 order_id
  cancel_order(order_id)   — 撤单
  query_account() → dict   — 查询账户资金
  query_positions() → dict — 查询持仓

回调（由子类在数据到达时调用）:
  on_tick(ts_code, data)   — 行情推送
  on_order(order_id, status, traded, price) — 订单回报
  on_trade(trade)          — 成交回报
  on_account(data)         — 账户资金更新
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable


class BaseGateway(ABC):
    def __init__(self, name: str):
        self.name = name
        self._connected = False

        # 回调注册（由 LiveEngine 注入）
        self.on_tick: Callable | None = None
        self.on_order: Callable | None = None
        self.on_trade: Callable | None = None
        self.on_account: Callable | None = None

    @property
    def connected(self) -> bool:
        return self._connected

    @abstractmethod
    def connect(self, setting: dict | None = None) -> bool:
        """建立连接，返回是否成功"""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        pass

    @abstractmethod
    def subscribe(self, ts_codes: list[str]) -> None:
        """订阅行情"""
        pass

    @abstractmethod
    def send_order(self, order) -> str:
        """
        发送订单
        order: core.oms.Order 对象
        返回 gateway 侧的 order_id
        """
        pass

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        pass

    @abstractmethod
    def query_account(self) -> dict:
        """返回 {balance, available, frozen}"""
        pass

    @abstractmethod
    def query_positions(self) -> dict:
        """返回 {ts_code: {shares, avg_cost, market_value}}"""
        pass

    def write_log(self, msg: str) -> None:
        print(f"[{self.name}] {msg}")

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name}, connected={self._connected})"
