"""
因子策略 - 基于综合因子评分选股
使用 InlineFactorGenerator 实时计算因子，选择评分最高的股票
"""


class FactorStrategy:
    def __init__(self, top_n=8, rebalance_interval=10):
        self.top_n = top_n
        self.rebalance_interval = rebalance_interval
        self.in_position = {}
        self.days_since_rebalance = 0

    def generate(self, date, price_dict, factor_scores=None):
        """
        生成交易信号
        factor_scores: {ts_code: score} 字典，由外部因子生成器提供
        """
        orders = []

        if not factor_scores:
            return orders

        self.days_since_rebalance += 1

        # 只在调仓日调仓
        if self.days_since_rebalance < self.rebalance_interval:
            return orders

        self.days_since_rebalance = 0

        # 按因子评分降序排列，选 top_n
        ranked = sorted(factor_scores.items(), key=lambda x: x[1], reverse=True)
        # 只选在当日有价格数据的
        selected = set()
        for code, score in ranked:
            if code in price_dict and len(selected) < self.top_n:
                selected.add(code)

        # 卖出不在选中列表的持仓
        for code in list(self.in_position.keys()):
            if code not in selected:
                orders.append({"action": "sell", "ts_code": code})
                del self.in_position[code]

        # 买入新选中的
        for code in selected:
            if code not in self.in_position:
                weight = 1.0 / self.top_n
                orders.append({"action": "buy", "ts_code": code, "weight": weight})
                self.in_position[code] = True

        return orders
