"""
core/oms.py — 订单管理系统 (OMS)

功能:
  - 订单生命周期管理: SUBMITTING → NOTTRADED → PARTTRADED → ALLTRADED/CANCELLED/REJECTED
  - 撤单能力
  - 持仓聚合视图（跨策略账户）
  - 成交回报分发
  - 与 EventEngine 集成，推送 EVENT_ORDER / EVENT_TRADE

A 股简化设计（相比 vnpy OmsEngine）:
  - 仅多头，无今昨仓转换
  - 订单 ID 自增，格式: {strategy}.{date}.{seq}
  - 回测模式: 日线收盘价撮合，当日提交当日成交或拒单
  - 实盘模式: 预留 gateway 回调接口
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable


# ── 订单状态枚举 ─────────────────────────────────────────────
class OrderStatus(Enum):
    SUBMITTING  = "提交中"
    NOTTRADED   = "未成交"
    PARTTRADED  = "部分成交"
    ALLTRADED   = "全部成交"
    CANCELLED   = "已撤销"
    REJECTED    = "拒单"


ACTIVE_STATUSES = {OrderStatus.SUBMITTING, OrderStatus.NOTTRADED, OrderStatus.PARTTRADED}


class OrderSide(Enum):
    BUY  = "买入"
    SELL = "卖出"


# ── 数据对象 ──────────────────────────────────────────────────
@dataclass
class Order:
    """订单对象"""
    order_id:    str
    strategy:    str
    ts_code:     str
    side:        OrderSide
    price:       float
    volume:      int           # 委托股数
    traded:      int = 0       # 已成交股数
    status:      OrderStatus = OrderStatus.SUBMITTING
    create_time: str = ""
    update_time: str = ""
    reject_reason: str = ""
    # 原始信号（透传，方便调试）
    raw_signal:  dict = field(default_factory=dict)

    @property
    def is_active(self) -> bool:
        return self.status in ACTIVE_STATUSES

    @property
    def remaining(self) -> int:
        return self.volume - self.traded

    def to_dict(self) -> dict:
        return {
            "order_id":     self.order_id,
            "strategy":     self.strategy,
            "ts_code":      self.ts_code,
            "side":         self.side.value,
            "price":        self.price,
            "volume":       self.volume,
            "traded":       self.traded,
            "status":       self.status.value,
            "create_time":  self.create_time,
            "update_time":  self.update_time,
            "reject_reason": self.reject_reason,
        }


@dataclass
class Trade:
    """成交回报"""
    trade_id:   str
    order_id:   str
    strategy:   str
    ts_code:    str
    side:       OrderSide
    price:      float
    volume:     int
    fee:        float
    trade_time: str

    def to_dict(self) -> dict:
        return {
            "trade_id":   self.trade_id,
            "order_id":   self.order_id,
            "strategy":   self.strategy,
            "ts_code":    self.ts_code,
            "side":       self.side.value,
            "price":      self.price,
            "volume":     self.volume,
            "fee":        self.fee,
            "trade_time": self.trade_time,
        }


# ── OMS 核心 ──────────────────────────────────────────────────
class OmsEngine:
    """
    订单管理引擎

    回调注册:
        oms.on_order_update = my_handler   # 订单状态变更
        oms.on_trade        = my_handler   # 成交回报

    与 EventEngine 集成（可选）:
        oms = OmsEngine(event_engine=engine)
        # 自动推送 EVENT_ORDER / EVENT_TRADE
    """

    def __init__(self, event_engine=None):
        self._event_engine = event_engine
        self._seq: int = 0

        # 全量订单表
        self._orders:  dict[str, Order] = {}
        # 活跃订单（未完结）
        self._active:  dict[str, Order] = {}
        # 成交记录
        self._trades:  dict[str, Trade] = {}

        # 外部回调（可选）
        self.on_order_update: Callable[[Order], None] | None = None
        self.on_trade:        Callable[[Trade], None] | None = None

    # ── 订单提交 ─────────────────────────────────────────────
    def submit_order(
        self,
        strategy: str,
        ts_code: str,
        side: OrderSide,
        price: float,
        volume: int,
        date: str = "",
        raw_signal: dict | None = None,
    ) -> Order:
        """
        提交新订单，返回 Order 对象
        状态初始为 SUBMITTING
        """
        self._seq += 1
        order_id = f"{strategy}.{date}.{self._seq:06d}"

        order = Order(
            order_id=order_id,
            strategy=strategy,
            ts_code=ts_code,
            side=side,
            price=price,
            volume=volume,
            status=OrderStatus.SUBMITTING,
            create_time=date,
            update_time=date,
            raw_signal=raw_signal or {},
        )

        self._orders[order_id] = order
        self._active[order_id] = order
        self._notify_order(order)
        return order

    # ── 撤单 ─────────────────────────────────────────────────
    def cancel_order(self, order_id: str, reason: str = "手动撤单") -> bool:
        """
        撤销活跃订单
        返回 True 表示撤单成功，False 表示订单不存在或已完结
        """
        order = self._active.get(order_id)
        if not order:
            return False

        if order.traded > 0:
            # 部分成交 → 撤剩余
            order.status = OrderStatus.CANCELLED
        else:
            # 未成交 → 全撤
            order.status = OrderStatus.CANCELLED

        order.reject_reason = reason
        order.update_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._active.pop(order_id, None)
        self._notify_order(order)
        return True

    def cancel_all(self, strategy: str | None = None) -> int:
        """
        批量撤单
        strategy=None 撤全部，否则只撤指定策略的订单
        返回撤单数量
        """
        targets = [
            oid for oid, o in list(self._active.items())
            if strategy is None or o.strategy == strategy
        ]
        for oid in targets:
            self.cancel_order(oid, reason="批量撤单")
        return len(targets)

    # ── 成交回报（回测撮合 / 实盘 gateway 回调）────────────────
    def fill_order(
        self,
        order_id: str,
        fill_price: float,
        fill_volume: int,
        fee: float,
        trade_time: str = "",
    ) -> Trade | None:
        """
        订单成交回报
        支持部分成交（多次调用）
        """
        order = self._orders.get(order_id)
        if not order or not order.is_active:
            return None

        order.traded += fill_volume
        order.update_time = trade_time

        if order.traded >= order.volume:
            order.status = OrderStatus.ALLTRADED
            self._active.pop(order_id, None)
        else:
            order.status = OrderStatus.PARTTRADED

        self._notify_order(order)

        # 生成成交记录
        trade = Trade(
            trade_id=str(uuid.uuid4())[:8],
            order_id=order_id,
            strategy=order.strategy,
            ts_code=order.ts_code,
            side=order.side,
            price=fill_price,
            volume=fill_volume,
            fee=fee,
            trade_time=trade_time,
        )
        self._trades[trade.trade_id] = trade
        self._notify_trade(trade)
        return trade

    def reject_order(self, order_id: str, reason: str = "") -> bool:
        """拒单"""
        order = self._active.get(order_id)
        if not order:
            return False
        order.status = OrderStatus.REJECTED
        order.reject_reason = reason
        order.update_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._active.pop(order_id, None)
        self._notify_order(order)
        return True

    # ── 查询接口 ─────────────────────────────────────────────
    def get_order(self, order_id: str) -> Order | None:
        return self._orders.get(order_id)

    def get_active_orders(self, strategy: str | None = None) -> list[Order]:
        if strategy is None:
            return list(self._active.values())
        return [o for o in self._active.values() if o.strategy == strategy]

    def get_all_orders(self, strategy: str | None = None) -> list[Order]:
        if strategy is None:
            return list(self._orders.values())
        return [o for o in self._orders.values() if o.strategy == strategy]

    def get_trades(self, strategy: str | None = None) -> list[Trade]:
        if strategy is None:
            return list(self._trades.values())
        return [t for t in self._trades.values() if t.strategy == strategy]

    def get_stats(self) -> dict:
        """统计摘要"""
        total = len(self._orders)
        active = len(self._active)
        filled = sum(1 for o in self._orders.values() if o.status == OrderStatus.ALLTRADED)
        cancelled = sum(1 for o in self._orders.values() if o.status == OrderStatus.CANCELLED)
        rejected = sum(1 for o in self._orders.values() if o.status == OrderStatus.REJECTED)
        return {
            "total_orders": total,
            "active_orders": active,
            "filled_orders": filled,
            "cancelled_orders": cancelled,
            "rejected_orders": rejected,
            "total_trades": len(self._trades),
        }

    # ── 内部通知 ─────────────────────────────────────────────
    def _notify_order(self, order: Order) -> None:
        if self.on_order_update:
            self.on_order_update(order)
        if self._event_engine:
            from core.event import Event, EVENT_ORDER
            self._event_engine.put(Event(EVENT_ORDER, order.to_dict()))

    def _notify_trade(self, trade: Trade) -> None:
        if self.on_trade:
            self.on_trade(trade)
        if self._event_engine:
            from core.event import Event, EVENT_TRADE
            self._event_engine.put(Event(EVENT_TRADE, trade.to_dict()))
