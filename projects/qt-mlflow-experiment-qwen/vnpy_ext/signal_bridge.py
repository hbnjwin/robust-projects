"""
SignalBridge - 将 signal_generator_v1 输出的 JSON 信号转换为 vnpy OrderRequest。

信号格式：
  买入: {"action": "buy", "ts_code": "000001.SZ", "weight": 0.0667}
  卖出: {"action": "sell", "ts_code": "000001.SZ"}
  卖出(带原因): {"action": "sell", "ts_code": "000001.SZ", "reason": "adaptive_stop"}
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from datetime import datetime

from vnpy.trader.object import OrderRequest
from vnpy.trader.constant import Direction, OrderType, Offset, Exchange

from .pg_daily_gateway import parse_ts_code


class SignalBridge:
    """将策略信号 JSON 转换为 vnpy OrderRequest 列表"""

    def __init__(self, total_capital: float = 1_000_000.0, lot_size: int = 100):
        """
        Args:
            total_capital: 总资金（用于 weight → volume 计算）
            lot_size: 每手股数（A股 = 100）
        """
        self.total_capital = total_capital
        self.lot_size = lot_size

    def load_signals(self, signal_path: str | Path) -> dict:
        """加载信号 JSON 文件"""
        path = Path(signal_path)
        if not path.exists():
            return {}
        with open(path, "r") as f:
            return json.load(f)

    def convert_signals(
        self,
        signals: dict,
        current_prices: dict[str, float],
        current_positions: dict[str, float] | None = None,
    ) -> list[OrderRequest]:
        """
        将信号转换为 vnpy OrderRequest 列表。

        Args:
            signals: signal_generator_v1 输出的完整 JSON
            current_prices: {ts_code: close_price} 当前价格
            current_positions: {ts_code: volume} 当前持仓（用于卖出计算）

        Returns:
            OrderRequest 列表
        """
        if current_positions is None:
            current_positions = {}

        orders: list[OrderRequest] = []

        # 先处理卖出信号（释放资金）
        all_signals = signals.get("trend_signals", []) + signals.get("lowvol_signals", [])

        sell_signals = [s for s in all_signals if s.get("action") == "sell"]
        buy_signals = [s for s in all_signals if s.get("action") == "buy"]

        for sig in sell_signals:
            ts_code = sig["ts_code"]
            symbol, exchange = parse_ts_code(ts_code)
            price = current_prices.get(ts_code, 0)

            if price <= 0:
                continue

            # 查持仓量
            pos_volume = current_positions.get(ts_code, 0)
            if pos_volume <= 0:
                continue

            order = OrderRequest(
                symbol=symbol,
                exchange=exchange,
                direction=Direction.SHORT,
                type=OrderType.LIMIT,
                volume=pos_volume,
                price=price,
                offset=Offset.CLOSE,
                reference=f"sell:{sig.get('reason', 'signal')}",
            )
            orders.append(order)

        for sig in buy_signals:
            ts_code = sig["ts_code"]
            symbol, exchange = parse_ts_code(ts_code)
            price = current_prices.get(ts_code, 0)

            if price <= 0:
                continue

            # 已持仓则跳过
            if current_positions.get(ts_code, 0) > 0:
                continue

            # weight → volume 计算
            weight = sig.get("weight", 1.0 / 15)  # 默认等权 15 只
            alloc_amount = self.total_capital * weight
            raw_shares = alloc_amount / price
            # 向下取整到整手
            volume = math.floor(raw_shares / self.lot_size) * self.lot_size

            if volume < self.lot_size:
                continue

            order = OrderRequest(
                symbol=symbol,
                exchange=exchange,
                direction=Direction.LONG,
                type=OrderType.LIMIT,
                volume=float(volume),
                price=price,
                offset=Offset.OPEN,
                reference=f"buy:weight={weight:.4f}",
            )
            orders.append(order)

        return orders

    def load_and_convert(
        self,
        signal_date: str,
        signal_dir: str = "logs/signals",
        current_prices: dict[str, float] | None = None,
        current_positions: dict[str, float] | None = None,
    ) -> list[OrderRequest]:
        """
 ：加载指定日期信号并转换。

        Args:
            signal_date: 'YYYY-MM-DD'
            signal_dir: 信号文件目录
            current_prices: 当前价格
            current_positions: 当前持仓
        """
        signal_path = Path(signal_dir) / f"{signal_date}.json"
        signals = self.load_signals(signal_path)

        if not signals:
            return []

        return self.convert_signals(
            signals,
            current_prices or {},
            current_positions,
        )
