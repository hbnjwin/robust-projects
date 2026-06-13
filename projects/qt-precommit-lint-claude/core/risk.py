"""
core/risk.py — 订单前置风控 + 超时撤单 + 撤单重报 + 订单持久化

Phase 2 新增能力:
  1. RiskGate          — 下单前置检查（资金/持仓/涨跌停/重复下单）
  2. OrderTimeoutManager — 超时自动撤单（实盘用，回测不需要）
  3. CancelAndReplace  — 撤单重报（按新价格重新下单）
  4. OrderPersistence  — 订单持久化（JSON，重启后恢复活跃订单）

设计原则:
  - 不修改 OmsEngine / DailyMatcher / paper_gateway 任何现有接口
  - RiskGate 作为 OmsEngine.submit_order 的前置包装
  - 所有新能力可独立使用，互不依赖
"""
from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from core.contract import contract_manager
from core.oms import OmsEngine, Order, OrderSide, OrderStatus

# ══════════════════════════════════════════════════════════════
# 1. RiskGate — 下单前置风控
# ══════════════════════════════════════════════════════════════

@dataclass
class RiskCheckResult:
    passed: bool
    reason: str = ""

    def __bool__(self):
        return self.passed


class RiskGate:
    """
    下单前置风控门

    用法:
        gate = RiskGate(oms, accounts, prices)
        gate.update_prices(today_prices)   # 每日更新行情
        order = gate.submit_order(...)     # 通过风控才提交

    风控规则:
        - 资金充足（买入）
        - 持仓存在且满足 T+1（卖出）
        - 非涨跌停
        - 同一标的无重复活跃订单
        - 单笔委托不超过账户净值 X%（可配置）
    """

    def __init__(
        self,
        oms: OmsEngine,
        accounts: dict,                  # {strategy: StrategyAccount}
        max_single_pct: float = 0.15,    # 单笔最大占账户净值比例
    ):
        self._oms = oms
        self._accounts = accounts
        self._prices: dict = {}          # {ts_code: {close, prev_close, volume}}
        self.max_single_pct = max_single_pct

        # 风控日志
        self._blocked: list[dict] = []

    def update_prices(self, prices: dict) -> None:
        """每日开盘前更新行情快照"""
        self._prices = prices

    def check(
        self,
        strategy: str,
        ts_code: str,
        side: OrderSide,
        price: float,
        volume: int,
    ) -> RiskCheckResult:
        """执行所有风控检查，返回 RiskCheckResult"""

        account = self._accounts.get(strategy)
        if account is None:
            return RiskCheckResult(False, f"找不到账户: {strategy}")

        # ── 重复活跃订单检查 ─────────────────────────────────
        active = self._oms.get_active_orders(strategy)
        for o in active:
            if o.ts_code == ts_code and o.side == side:
                return RiskCheckResult(False, f"已有活跃订单: {o.order_id}")

        # ── 行情检查 ─────────────────────────────────────────
        data = self._prices.get(ts_code)
        if data:
            prev_close = data.get("prev_close", 0)
            if prev_close > 0:
                limit_range = contract_manager.limit_range(ts_code)
                limit_up   = prev_close * (1 + limit_range)
                limit_down = prev_close * (1 - limit_range)

                if side == OrderSide.BUY and price >= limit_up:
                    return RiskCheckResult(False, "涨停无法买入")
                if side == OrderSide.SELL and price <= limit_down:
                    return RiskCheckResult(False, "跌停无法卖出")

        # ── 买入：资金检查 ────────────────────────────────────
        if side == OrderSide.BUY:
            cfg      = contract_manager.get(ts_code)
            fee_rate = cfg.long_rate
            cost     = volume * price * (1 + fee_rate)

            if cost > account.cash:
                return RiskCheckResult(False, f"资金不足: 需要{cost:.0f} 可用{account.cash:.0f}")

            # 单笔上限
            net_value = account.cash + sum(
                p["shares"] * self._prices.get(p.get("ts_code", ts_code), {}).get("close", price)
                for p in account.positions.values()
                if isinstance(p, dict)
            )
            if net_value > 0 and cost / net_value > self.max_single_pct:
                return RiskCheckResult(
                    False,
                    f"单笔超限: {cost/net_value:.1%} > {self.max_single_pct:.1%}"
                )

        # ── 卖出：持仓检查 ────────────────────────────────────
        if side == OrderSide.SELL:
            pos = account.positions.get(ts_code)
            if not pos:
                return RiskCheckResult(False, "无持仓可卖")
            if pos.get("shares", 0) < volume:
                return RiskCheckResult(False, f"持仓不足: 有{pos['shares']} 卖{volume}")

        return RiskCheckResult(True)

    def submit_order(
        self,
        strategy: str,
        ts_code: str,
        side: OrderSide,
        price: float,
        volume: int,
        date: str = "",
        raw_signal: dict | None = None,
    ) -> Order | None:
        """
        风控通过后提交订单，失败返回 None
        """
        result = self.check(strategy, ts_code, side, price, volume)
        if not result:
            self._blocked.append({
                "time": datetime.now().isoformat(),
                "strategy": strategy,
                "ts_code": ts_code,
                "side": side.value,
                "price": price,
                "volume": volume,
                "reason": result.reason,
            })
            return None

        return self._oms.submit_order(
            strategy=strategy,
            ts_code=ts_code,
            side=side,
            price=price,
            volume=volume,
            date=date,
            raw_signal=raw_signal,
        )

    def get_blocked_log(self) -> list[dict]:
        return list(self._blocked)

    def clear_blocked_log(self) -> None:
        self._blocked.clear()


# ══════════════════════════════════════════════════════════════
# 2. OrderTimeoutManager — 超时自动撤单
# ══════════════════════════════════════════════════════════════

class OrderTimeoutManager:
    """
    订单超时自动撤单（实盘用）

    用法:
        mgr = OrderTimeoutManager(oms, timeout_seconds=30)
        mgr.start()          # 启动后台线程
        mgr.stop()           # 停止

    原理:
        每隔 check_interval 秒扫描活跃订单，
        超过 timeout_seconds 未成交的自动撤单。
    """

    def __init__(
        self,
        oms: OmsEngine,
        timeout_seconds: int = 30,
        check_interval: int = 5,
        on_timeout: Callable[[Order], None] | None = None,
    ):
        self._oms = oms
        self.timeout_seconds = timeout_seconds
        self.check_interval  = check_interval
        self.on_timeout      = on_timeout

        self._running = False
        self._thread: threading.Thread | None = None
        self._submit_times: dict[str, float] = {}  # order_id → submit timestamp

    def register(self, order: Order) -> None:
        """注册订单提交时间（在 submit_order 后调用）"""
        self._submit_times[order.order_id] = time.time()

    def start(self) -> None:
        """启动后台超时检查线程"""
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name="OrderTimeout")
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=self.check_interval + 1)

    def _run(self) -> None:
        while self._running:
            time.sleep(self.check_interval)
            self._check()

    def _check(self) -> None:
        now = time.time()
        for order in list(self._oms.get_active_orders()):
            submit_time = self._submit_times.get(order.order_id)
            if submit_time is None:
                continue
            if now - submit_time > self.timeout_seconds:
                self._oms.cancel_order(order.order_id, reason=f"超时撤单({self.timeout_seconds}s)")
                self._submit_times.pop(order.order_id, None)
                if self.on_timeout:
                    self.on_timeout(order)


# ══════════════════════════════════════════════════════════════
# 3. CancelAndReplace — 撤单重报
# ══════════════════════════════════════════════════════════════

class CancelAndReplace:
    """
    撤单重报

    用法:
        car = CancelAndReplace(oms)
        new_order = car.replace(old_order_id, new_price=10.5)
    """

    def __init__(self, oms: OmsEngine):
        self._oms = oms

    def replace(
        self,
        order_id: str,
        new_price: float,
        new_volume: int | None = None,
        date: str = "",
    ) -> Order | None:
        """
        撤销旧订单，按新价格/数量重新下单

        Returns:
            新 Order 对象，撤单失败返回 None
        """
        old_order = self._oms.get_order(order_id)
        if not old_order:
            return None

        # 撤旧单
        cancelled = self._oms.cancel_order(order_id, reason="撤单重报")
        if not cancelled:
            return None

        # 重新下单（剩余未成交量）
        remaining = old_order.remaining
        volume = new_volume if new_volume is not None else remaining
        if volume <= 0:
            return None

        return self._oms.submit_order(
            strategy=old_order.strategy,
            ts_code=old_order.ts_code,
            side=old_order.side,
            price=new_price,
            volume=volume,
            date=date or old_order.create_time,
            raw_signal={**old_order.raw_signal, "replaced_from": order_id},
        )

    def chase(
        self,
        order_id: str,
        prices: dict,
        slippage: float = 0.002,
        date: str = "",
    ) -> Order | None:
        """
        追价重报：按最新行情价 + slippage 重新下单

        prices: {ts_code: {"close": float, ...}}
        """
        old_order = self._oms.get_order(order_id)
        if not old_order:
            return None

        data = prices.get(old_order.ts_code)
        if not data:
            return None

        close = data["close"]
        if old_order.side == OrderSide.BUY:
            new_price = close * (1 + slippage)
        else:
            new_price = close * (1 - slippage)

        return self.replace(order_id, new_price=new_price, date=date)


# ══════════════════════════════════════════════════════════════
# 4. OrderPersistence — 订单持久化
# ══════════════════════════════════════════════════════════════

class OrderPersistence:
    """
    订单持久化（JSON 文件）

    用法:
        persist = OrderPersistence(oms, path="data/orders.json")
        persist.save()          # 保存当前所有订单
        persist.restore()       # 重启后恢复活跃订单

    存储格式:
        {
          "saved_at": "...",
          "orders": [...],      # 所有订单
          "active_ids": [...]   # 活跃订单 ID
        }
    """

    def __init__(self, oms: OmsEngine, path: str = "data/orders.json"):
        self._oms = oms
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def save(self) -> None:
        """持久化当前所有订单"""
        orders = [o.to_dict() for o in self._oms.get_all_orders()]
        active_ids = [o.order_id for o in self._oms.get_active_orders()]

        data = {
            "saved_at": datetime.now().isoformat(),
            "orders": orders,
            "active_ids": active_ids,
        }
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def restore(self) -> int:
        """
        从文件恢复活跃订单到 OMS

        Returns: 恢复的活跃订单数量
        """
        if not self._path.exists():
            return 0

        with open(self._path, encoding="utf-8") as f:
            data = json.load(f)

        active_ids = set(data.get("active_ids", []))
        restored = 0

        for od in data.get("orders", []):
            if od["order_id"] not in active_ids:
                continue

            # 重建 Order 对象
            order = Order(
                order_id=od["order_id"],
                strategy=od["strategy"],
                ts_code=od["ts_code"],
                side=OrderSide(od["side"]),
                price=od["price"],
                volume=od["volume"],
                traded=od["traded"],
                status=OrderStatus(od["status"]),
                create_time=od["create_time"],
                update_time=od["update_time"],
                reject_reason=od.get("reject_reason", ""),
            )

            # 注入 OMS 内部状态
            self._oms._orders[order.order_id] = order
            if order.is_active:
                self._oms._active[order.order_id] = order
                restored += 1

        return restored

    def load_snapshot(self) -> dict | None:
        """读取快照（不注入 OMS，只返回原始数据）"""
        if not self._path.exists():
            return None
        with open(self._path, encoding="utf-8") as f:
            return json.load(f)
