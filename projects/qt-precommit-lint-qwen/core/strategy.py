"""
core/strategy.py — 统一策略基类
所有策略继承 BaseStrategy，约定统一接口。
向后兼容：旧策略的 generate(date, prices) 接口仍可用，
通过 LegacyStrategyAdapter 包装后接入事件引擎。
"""

from abc import ABC, abstractmethod
from typing import Any


class BaseStrategy(ABC):
    """
    策略基类

    子类必须实现:
      on_init()          — 初始化（预热期结束后调用一次）
      on_bars(date, prices) — 每日 Bar 回调，返回信号列表
      on_trade(trade)    — 成交回报回调

    信号格式（与 v2 兼容）:
      {"action": "buy"|"sell", "ts_code": str, "weight": float, ...}
    """

    def __init__(self, name: str):
        self.name = name
        self._initialized = False

    def on_init(self) -> None:
        """初始化回调，子类可覆盖"""
        pass

    @abstractmethod
    def on_bars(self, date: str, prices: dict) -> list[dict]:
        """
        每日 Bar 回调
        返回信号列表，空列表表示无操作
        """
        pass

    def on_trade(self, trade: dict) -> None:
        """成交回报回调，子类可覆盖"""
        pass

    def warmup(self, date: str, prices: dict) -> None:
        """
        预热期回调（不产生信号，仅更新内部状态）
        默认调用 on_bars 但丢弃结果，子类可覆盖以优化性能
        """
        self.on_bars(date, prices)

    def initialize(self) -> None:
        """标记初始化完成"""
        self._initialized = True
        self.on_init()


class LegacyStrategyAdapter(BaseStrategy):
    """
    旧策略适配器
    将实现了 generate(date, prices) 接口的旧策略包装为 BaseStrategy。
    用于 TrendStrategyV2 / LowVolStrategy / FactorStrategy 的无缝接入。
    """

    def __init__(self, name: str, legacy_strategy: Any):
        super().__init__(name)
        self._strategy = legacy_strategy

    def on_bars(self, date: str, prices: dict) -> list[dict]:
        return self._strategy.generate(date, prices)

    def warmup(self, date: str, prices: dict) -> None:
        """旧策略预热：调用 generate 但丢弃结果"""
        self._strategy.generate(date, prices)

    def set_regime(self, regime: str) -> None:
        """透传 regime 设置（LowVolStrategy 需要）"""
        if hasattr(self._strategy, "set_regime"):
            self._strategy.set_regime(regime)

    def __getattr__(self, name: str) -> Any:
        """透传属性访问到底层策略"""
        return getattr(self._strategy, name)
