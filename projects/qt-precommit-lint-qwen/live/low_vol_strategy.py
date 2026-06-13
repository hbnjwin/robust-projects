# DEPRECATED: 此模块已废弃，请使用 live/ 目录下的对应模块
# =============================================================================
# DEPRECATED — 此模块已废弃
# 此 LowVolStrategy 占位实现已被 lowvol_strategy_v2.py (LowVolStrategy) 取代。
# =============================================================================


class LowVolStrategy:
    def generate(self, date, price_dict):
        if not price_dict:
            return []
        # 简单模拟：选择第二只股票（用于区分策略）
        codes = list(price_dict.keys())
        if len(codes) < 2:
            return []
        return [{"action": "buy", "ts_code": codes[1]}]
