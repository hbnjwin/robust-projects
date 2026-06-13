"""
合约配置体系
管理每只股票/品种的交易规则参数，供 ExecutionEngine 使用。

配置文件: config/contract_settings.json
字段说明:
  pricetick   最小价格变动单位（A股通常 0.01）
  size        每手股数（A股通常 100）
  long_rate   买入手续费率（含印花税方向）
  short_rate  卖出手续费率（含印花税）
  min_volume  最小下单量（手）
"""

import json
from dataclasses import dataclass
from pathlib import Path

_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "contract_settings.json"


@dataclass
class ContractConfig:
    symbol: str
    pricetick: float = 0.01
    size: int = 100  # 每手股数
    long_rate: float = 0.0003  # 买入费率（万3）
    short_rate: float = 0.0013  # 卖出费率（万3 + 千1印花税）
    min_volume: int = 1  # 最小下单手数


# A股默认配置（无个股配置时使用）
_A_SHARE_DEFAULT = ContractConfig(symbol="DEFAULT")

# 科创板/创业板注册制涨跌幅 20%（symbol 前缀匹配）
_STAR_PREFIXES = ("688", "689")
_GEM_PREFIXES = ("300", "301")


class ContractManager:
    """
    合约配置管理器（单例）
    优先从 JSON 文件加载，缺失时使用 A 股默认值。
    """

    def __init__(self, config_path: str | None = None):
        self._configs: dict[str, ContractConfig] = {}
        path = Path(config_path) if config_path else _DEFAULT_CONFIG_PATH
        if path.exists():
            self._load(path)

    def _load(self, path: Path) -> None:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for symbol, cfg in data.items():
            # 跳过注释键（以 _ 开头）和非 dict 值
            if symbol.startswith("_") or not isinstance(cfg, dict):
                continue
            self._configs[symbol] = ContractConfig(symbol=symbol, **cfg)

    def get(self, symbol: str) -> ContractConfig:
        """获取合约配置，优先个股 > 市场默认 > 全局默认"""
        if symbol in self._configs:
            return self._configs[symbol]
        # 按市场前缀匹配默认配置
        prefix = symbol[:3]
        market_key = f"_market_{prefix}"
        if market_key in self._configs:
            return self._configs[market_key]
        return _A_SHARE_DEFAULT

    def limit_range(self, symbol: str) -> float:
        """返回涨跌幅限制比例（科创板/创业板 0.20，其余 0.10）"""
        prefix = symbol[:3]
        if prefix in _STAR_PREFIXES or prefix in _GEM_PREFIXES:
            return 0.20
        return 0.10

    def reload(self, config_path: str | None = None) -> None:
        path = Path(config_path) if config_path else _DEFAULT_CONFIG_PATH
        self._configs.clear()
        if path.exists():
            self._load(path)


# 全局单例
contract_manager = ContractManager()
