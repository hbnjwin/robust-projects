"""
自适应配置管理器
根据 Regime 动态调整策略参数，融合各版本最优配置
"""


class AdaptiveConfig:
    """
    根据市场状态自动选择最优参数组合

    BULL: 进攻模式（v4风格）
    - 因子权重：等权（v4的多因子等权在牛市收益最高）
    - LowVol止损：收紧（保护利润）
    - Trend max_positions: 15（扩大进攻面）
    - Factor top_n: 15（更多持仓）

    CRISIS: 防御模式（v3风格）
    - 因子权重：IC加权 + 低波动加强（v5的Regime感知）
    - LowVol止损：放宽（避免恐慌卖出）
    - Trend max_positions: 5（收缩持仓）
    - Factor top_n: 5（集中防御）

    NEUTRAL: 均衡模式（v5风格）
    - 因子权重：IC加权
    - LowVol止损：基础参数
    - Trend max_positions: 10
    - Factor top_n: 10
    """

    # 各 Regime 下的因子权重（20 因子）
    BULL_WEIGHTS = {
        "MOM_20": 0.09,
        "MOM_60": 0.08,
        "MOM_QUALITY": 0.06,
        "MOM_ACCELERATION": 0.05,
        "VOL_20": 0.04,
        "VOL_CHANGE": 0.02,
        "DOWNSIDE_VOL": 0.02,
        "REVERSAL_5": 0.02,
        "RSI_14": 0.02,
        "BOLLINGER_POS": 0.02,
        "MA_DEVIATION": 0.06,
        "TREND_STRENGTH": 0.08,
        "ADX_PROXY": 0.08,
        "VOLUME_RATIO": 0.06,
        "PRICE_VOLUME_CORR": 0.06,
        "OBV_SLOPE": 0.05,
        "PRICE_LEVEL": 0.03,
        "DRAWDOWN_RECOVERY": 0.04,
        "HIGH_DISTANCE": 0.04,
        "SHARPE_20": 0.08,
    }

    CRISIS_WEIGHTS = {
        "MOM_20": 0.02,
        "MOM_60": 0.02,
        "MOM_QUALITY": 0.03,
        "MOM_ACCELERATION": 0.01,
        "VOL_20": 0.15,
        "VOL_CHANGE": 0.06,
        "DOWNSIDE_VOL": 0.08,
        "REVERSAL_5": 0.08,
        "RSI_14": 0.08,
        "BOLLINGER_POS": 0.06,
        "MA_DEVIATION": 0.02,
        "TREND_STRENGTH": 0.02,
        "ADX_PROXY": 0.03,
        "VOLUME_RATIO": 0.02,
        "PRICE_VOLUME_CORR": 0.02,
        "OBV_SLOPE": 0.03,
        "PRICE_LEVEL": 0.06,
        "DRAWDOWN_RECOVERY": 0.05,
        "HIGH_DISTANCE": 0.04,
        "SHARPE_20": 0.12,
    }

    NEUTRAL_WEIGHTS = {
        "MOM_20": 0.06,
        "MOM_60": 0.06,
        "MOM_QUALITY": 0.05,
        "MOM_ACCELERATION": 0.03,
        "VOL_20": 0.10,
        "VOL_CHANGE": 0.04,
        "DOWNSIDE_VOL": 0.04,
        "REVERSAL_5": 0.05,
        "RSI_14": 0.05,
        "BOLLINGER_POS": 0.05,
        "MA_DEVIATION": 0.04,
        "TREND_STRENGTH": 0.05,
        "ADX_PROXY": 0.06,
        "VOLUME_RATIO": 0.04,
        "PRICE_VOLUME_CORR": 0.04,
        "OBV_SLOPE": 0.04,
        "PRICE_LEVEL": 0.04,
        "DRAWDOWN_RECOVERY": 0.04,
        "HIGH_DISTANCE": 0.04,
        "SHARPE_20": 0.08,
    }

    @classmethod
    def get_config(cls, regime):
        if regime == "BULL":
            return {
                "factor_weights": cls.BULL_WEIGHTS,
                "trend_max_positions": 15,
                "factor_top_n": 15,
                "lowvol_base_stop_loss": 0.08,
                "lowvol_base_cooldown": 3,
                "lowvol_strategy_dd_limit": 0.18,
            }
        elif regime == "CRISIS":
            return {
                "factor_weights": cls.CRISIS_WEIGHTS,
                "trend_max_positions": 5,
                "factor_top_n": 5,
                "lowvol_base_stop_loss": 0.08,
                "lowvol_base_cooldown": 3,
                "lowvol_strategy_dd_limit": 0.12,
            }
        else:  # NEUTRAL
            return {
                "factor_weights": cls.NEUTRAL_WEIGHTS,
                "trend_max_positions": 10,
                "factor_top_n": 10,
                "lowvol_base_stop_loss": 0.12,
                "lowvol_base_cooldown": 5,
                "lowvol_strategy_dd_limit": 0.15,
            }
