# DEPRECATED: 此模块已废弃，请使用 live/ 目录下的对应模块
# =============================================================================
# DEPRECATED — 此模块已废弃
# SimpleTrendStrategy 已被 trend_strategy_v2.py (TrendStrategyV2) 取代。
# =============================================================================

class SimpleTrendStrategy:
    def generate(self, date, price_dict):
        if not price_dict:
            return []
        first_code = list(price_dict.keys())[0]
        return [{"action": "buy", "ts_code": first_code}]
