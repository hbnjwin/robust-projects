"""
因子驱动选股策略
Phase 7: 仓位自适应（Volatility Scaling）
- 等权模式（默认）：weight = 1/top_n
- 波动率倒数加权：weight ∝ 1/vol，波动率低的股票获得更多仓位
"""

import numpy as np


class FactorStrategy:
    def __init__(self, factor_scores, top_n=20, rebalance_days=30, vol_scaling=True, vol_window=20, vol_floor=0.005):
        """
        factor_scores   : {date: {ts_code: composite_score}}
        top_n           : 选股数量
        rebalance_days  : 调仓周期（交易日）
        vol_scaling     : 是否启用波动率倒数加权（Phase 7）
        vol_window      : 计算波动率的滚动窗口（交易日）
        vol_floor       : 波动率下限，防止除零（默认 0.5%）
        """
        self.factor_scores = factor_scores
        self.top_n = top_n
        self.rebalance_days = rebalance_days
        self.vol_scaling = vol_scaling
        self.vol_window = vol_window
        self.vol_floor = vol_floor

        self.day_count = 0
        self.current_holdings = set()

        # 维护价格历史，用于计算波动率
        self._price_history: dict[str, list[float]] = {}

    def _update_price_history(self, price_dict: dict):
        """每日更新价格历史"""
        for code, data in price_dict.items():
            close = data["close"] if isinstance(data, dict) else float(data)
            hist = self._price_history.setdefault(code, [])
            hist.append(close)
            # 只保留 vol_window + 1 天（计算收益率需要多一天）
            if len(hist) > self.vol_window + 5:
                self._price_history[code] = hist[-(self.vol_window + 5) :]

    def _compute_vol(self, code: str) -> float:
        """计算个股 vol_window 日收益率标准差"""
        hist = self._price_history.get(code, [])
        if len(hist) < self.vol_window + 1:
            return None  # 历史不足，返回 None

        prices = np.array(hist[-(self.vol_window + 1) :])
        rets = np.diff(prices) / np.where(prices[:-1] > 0, prices[:-1], 1)
        vol = float(np.std(rets))
        return max(vol, self.vol_floor)

    def _vol_weights(self, selected: set) -> dict[str, float]:
        """
        波动率倒数加权
        weight_i = (1/vol_i) / sum(1/vol_j)
        历史不足的股票使用全组平均波动率
        """
        inv_vols = {}
        fallback_codes = []

        for code in selected:
            vol = self._compute_vol(code)
            if vol is not None:
                inv_vols[code] = 1.0 / vol
            else:
                fallback_codes.append(code)

        # 历史不足的股票用已有股票的平均 inv_vol 填充
        if inv_vols:
            avg_inv_vol = float(np.mean(list(inv_vols.values())))
        else:
            avg_inv_vol = 1.0 / self.vol_floor  # 全部不足时用 floor

        for code in fallback_codes:
            inv_vols[code] = avg_inv_vol

        total = sum(inv_vols.values())
        return {code: v / total for code, v in inv_vols.items()}

    def generate(self, date: str, price_dict: dict) -> list:
        """
        生成交易信号，兼容 ReplayEngineV3 格式
        返回: list of {action, ts_code, weight}
        """
        # 每日更新价格历史（无论是否调仓日）
        self._update_price_history(price_dict)

        self.day_count += 1

        # 非调仓日不操作
        if self.day_count % self.rebalance_days != 1 and self.day_count != 1:
            return []

        # 获取当日因子得分
        scores = self.factor_scores.get(date, {})
        if not scores:
            return []

        # 只选有行情的股票
        available = {code: score for code, score in scores.items() if code in price_dict}
        if not available:
            return []

        # 排序选 top_n
        ranked = sorted(available.items(), key=lambda x: x[1], reverse=True)
        selected = set(code for code, _ in ranked[: self.top_n])

        # 计算仓位权重
        if self.vol_scaling:
            weights = self._vol_weights(selected)
        else:
            w = 1.0 / len(selected)
            weights = {code: w for code in selected}

        signals = []

        # 卖出：不在新选股列表中的持仓
        for code in self.current_holdings - selected:
            signals.append({"action": "sell", "ts_code": code})

        # 买入：新进入选股列表的
        for code in selected - self.current_holdings:
            signals.append(
                {
                    "action": "buy",
                    "ts_code": code,
                    "weight": weights[code],
                }
            )

        self.current_holdings = selected
        return signals
