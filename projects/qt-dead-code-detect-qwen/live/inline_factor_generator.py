"""
内联因子生成器 v3 - 20 因子模型
在回测过程中实时计算因子（不依赖数据库）

因子体系（20个）：
=== 动量类 ===
1.  MOM_20: 20日动量
2.  MOM_60: 60日动量
3.  MOM_QUALITY: 动量稳定性（上涨天数占比）
4.  MOM_ACCELERATION: 动量加速度（近期动量 vs 远期动量）

=== 波动类 ===
5.  VOL_20: 20日波动率（低波动优先）
6.  VOL_CHANGE: 波动率收缩信号
7.  DOWNSIDE_VOL: 下行波动率（只计算下跌日，低值优先）

=== 反转/均值回归 ===
8.  REVERSAL_5: 5日反转
9.  RSI_14: 14日RSI（超卖优先）
10. BOLLINGER_POS: 布林带位置（低位优先）

=== 趋势类 ===
11. MA_DEVIATION: 价格偏离20日均线
12. TREND_STRENGTH: MA5/MA20/MA60排列一致性
13. ADX_PROXY: 趋势强度代理（方向性运动指标近似）

=== 量价类 ===
14. VOLUME_RATIO: 近5日/近20日成交量比
15. PRICE_VOLUME_CORR: 价量相关性（量价齐升信号）
16. OBV_SLOPE: OBV斜率（资金流向）

=== 价值/位置类 ===
17. PRICE_LEVEL: 60日价格位置（低位优先）
18. DRAWDOWN_RECOVERY: 从近期低点恢复程度
19. HIGH_DISTANCE: 距离60日最高价的距离（近高点=强势）

=== 风险调整类 ===
20. SHARPE_20: 20日滚动Sharpe（风险调整后收益）

输出格式兼容 FactorStrategy 的 factor_scores
"""
import numpy as np


class InlineFactorGenerator:

    def __init__(self, history_len=120):
        self.history_len = history_len
        self.price_history = {}
        self.volume_history = {}

        # 20 因子权重配置（基于 IC 分析 + 类别均衡）
        self.base_weights = {
            # 动量类 (20%)
            "MOM_20": 0.06,
            "MOM_60": 0.06,
            "MOM_QUALITY": 0.05,
            "MOM_ACCELERATION": 0.03,
            # 波动类 (18%)
            "VOL_20": 0.10,
            "VOL_CHANGE": 0.04,
            "DOWNSIDE_VOL": 0.04,
            # 反转/均值回归 (15%)
            "REVERSAL_5": 0.05,
            "RSI_14": 0.05,
            "BOLLINGER_POS": 0.05,
            # 趋势类 (15%)
            "MA_DEVIATION": 0.04,
            "TREND_STRENGTH": 0.05,
            "ADX_PROXY": 0.06,
            # 量价类 (12%)
            "VOLUME_RATIO": 0.04,
            "PRICE_VOLUME_CORR": 0.04,
            "OBV_SLOPE": 0.04,
            # 价值/位置类 (12%)
            "PRICE_LEVEL": 0.04,
            "DRAWDOWN_RECOVERY": 0.04,
            "HIGH_DISTANCE": 0.04,
            # 风险调整类 (8%)
            "SHARPE_20": 0.08,
        }
        self.factor_weights = dict(self.base_weights)
        self.current_regime = "NEUTRAL"

    def update(self, price_dict):
        """每日更新价格和成交量历史"""
        for code, data in price_dict.items():
            self.price_history.setdefault(code, []).append(data["close"])
            if len(self.price_history[code]) > self.history_len:
                self.price_history[code] = self.price_history[code][-self.history_len:]

            vol = data.get("volume", 0)
            self.volume_history.setdefault(code, []).append(vol)
            if len(self.volume_history[code]) > self.history_len:
                self.volume_history[code] = self.volume_history[code][-self.history_len:]

    def set_regime(self, regime):
        """
        根据 Regime 动态调整因子权重
        - BULL: 加大动量+趋势，降低反转+波动
        - CRISIS: 加大低波动+反转+风险调整，降低动量+趋势
        - NEUTRAL: 使用基础权重
        """
        self.current_regime = regime
        w = dict(self.base_weights)

        if regime == "BULL":
            # 进攻：动量+趋势加强
            w["MOM_20"] *= 1.5
            w["MOM_60"] *= 1.3
            w["MOM_ACCELERATION"] *= 1.5
            w["TREND_STRENGTH"] *= 1.3
            w["ADX_PROXY"] *= 1.3
            w["PRICE_VOLUME_CORR"] *= 1.3
            # 降低防御因子
            w["REVERSAL_5"] *= 0.5
            w["RSI_14"] *= 0.5
            w["VOL_20"] *= 0.7
            w["DOWNSIDE_VOL"] *= 0.7
        elif regime == "CRISIS":
            # 防御：低波动+反转+风险调整加强
            w["VOL_20"] *= 1.8
            w["DOWNSIDE_VOL"] *= 1.5
            w["REVERSAL_5"] *= 1.5
            w["RSI_14"] *= 1.5
            w["BOLLINGER_POS"] *= 1.3
            w["SHARPE_20"] *= 1.5
            # 降低进攻因子
            w["MOM_20"] *= 0.5
            w["MOM_60"] *= 0.5
            w["MOM_ACCELERATION"] *= 0.5
            w["TREND_STRENGTH"] *= 0.5

        # 归一化到总和为 1
        total = sum(w.values())
        if total > 0:
            self.factor_weights = {k: v / total for k, v in w.items()}
        else:
            self.factor_weights = dict(self.base_weights)

    def _compute_all_factors(self):
        """计算所有 20 个因子，返回 {factor_name: {code: value}}"""
        factor_names = list(self.base_weights.keys())
        factors = {name: {} for name in factor_names}

        for code, prices in self.price_history.items():
            n = len(prices)
            vols = self.volume_history.get(code, [])

            try:
                self._compute_stock_factors(factors, code, prices, vols, n)
            except (ZeroDivisionError, ValueError, IndexError):
                continue

        return factors

    def _compute_stock_factors(self, factors, code, prices, vols, n):
        """计算单只股票的所有因子（从 _compute_all_factors 提取）"""

        # 1. MOM_20: 20日动量
        if n >= 21:
            factors["MOM_20"][code] = (prices[-1] - prices[-21]) / prices[-21] if prices[-21] != 0 else 0

        # 2. MOM_60: 60日动量
        if n >= 61:
            factors["MOM_60"][code] = (prices[-1] - prices[-61]) / prices[-61] if prices[-61] != 0 else 0

        # 3. MOM_QUALITY: 动量质量（过去20日中上涨天数占比）
        if n >= 21:
            window = prices[-21:]
            up_days = sum(1 for j in range(1, len(window)) if window[j] > window[j - 1])
            factors["MOM_QUALITY"][code] = up_days / 20.0

        # 4. MOM_ACCELERATION: 动量加速度（近10日动量 - 前10日动量）
        if n >= 21:
            mom_recent = (prices[-1] - prices[-11]) / prices[-11] if prices[-11] > 0 else 0
            mom_prior = (prices[-11] - prices[-21]) / prices[-21] if prices[-21] > 0 else 0
            factors["MOM_ACCELERATION"][code] = mom_recent - mom_prior

        # === 波动类 ===

        # 计算日收益率（多个因子共用）
        rets_20 = []
        if n >= 21:
            window = prices[-21:]
            for j in range(1, len(window)):
                if window[j - 1] > 0:
                    rets_20.append((window[j] - window[j - 1]) / window[j - 1])

        # 5. VOL_20: 20日波动率（越低越好）
        if len(rets_20) > 1:
            factors["VOL_20"][code] = np.std(rets_20)

        # 6. VOL_CHANGE: 波动率变化（近10日/近20日，<1=收缩）
        if len(rets_20) >= 20:
            vol10 = np.std(rets_20[-10:])
            vol20 = np.std(rets_20)
            if vol20 > 0:
                factors["VOL_CHANGE"][code] = -(vol10 / vol20)

        # 7. DOWNSIDE_VOL: 下行波动率（只计算下跌日的标准差）
        if len(rets_20) > 1:
            down_rets = [r for r in rets_20 if r < 0]
            if len(down_rets) > 1:
                factors["DOWNSIDE_VOL"][code] = np.std(down_rets)
            else:
                factors["DOWNSIDE_VOL"][code] = 0.0  # 没有下跌日=最好

        # === 反转/均值回归 ===

        # 8. REVERSAL_5: 5日反转
        if n >= 6 and prices[-6] != 0:
            factors["REVERSAL_5"][code] = -(prices[-1] - prices[-6]) / prices[-6]

        # 9. RSI_14: 14日RSI（超卖区域优先）
        if n >= 15:
            window = prices[-15:]
            gains = []
            losses = []
            for j in range(1, len(window)):
                change = window[j] - window[j - 1]
                if change > 0:
                    gains.append(change)
                    losses.append(0)
                else:
                    gains.append(0)
                    losses.append(abs(change))
            avg_gain = np.mean(gains) if gains else 0
            avg_loss = np.mean(losses) if losses else 0
            if avg_loss > 0:
                rs = avg_gain / avg_loss
                rsi = 100 - (100 / (1 + rs))
            else:
                rsi = 100
            # 反转逻辑：RSI 低 = 超卖 = 买入信号，取负值让低RSI排前
            factors["RSI_14"][code] = -rsi

        # 10. BOLLINGER_POS: 布林带位置（低位优先）
        if n >= 20:
            ma20 = np.mean(prices[-20:])
            std20 = np.std(prices[-20:])
            if std20 > 0:
                # (price - lower_band) / (upper_band - lower_band)
                upper = ma20 + 2 * std20
                lower = ma20 - 2 * std20
                band_width = upper - lower
                if band_width > 0:
                    factors["BOLLINGER_POS"][code] = (prices[-1] - lower) / band_width

        # === 趋势类 ===

        # 11. MA_DEVIATION: 价格偏离20日均线
        if n >= 20:
            ma20 = np.mean(prices[-20:])
            if ma20 > 0:
                factors["MA_DEVIATION"][code] = (prices[-1] - ma20) / ma20

        # 12. TREND_STRENGTH: MA5/MA20/MA60排列一致性
        if n >= 60:
            ma5 = np.mean(prices[-5:])
            ma20 = np.mean(prices[-20:])
            ma60 = np.mean(prices[-60:])
            if ma5 > ma20 > ma60:
                factors["TREND_STRENGTH"][code] = 1.0
            elif ma5 > ma20:
                factors["TREND_STRENGTH"][code] = 0.5
            else:
                factors["TREND_STRENGTH"][code] = 0.0

        # 13. ADX_PROXY: 趋势强度代理
        #     用价格在过去20日高低范围中的方向性运动近似
        if n >= 21:
            window = prices[-21:]
            plus_dm = 0
            minus_dm = 0
            tr_sum = 0
            for j in range(1, len(window)):
                high_diff = window[j] - window[j - 1]  # 近似+DM
                low_diff = window[j - 1] - window[j]   # 近似-DM
                tr = abs(window[j] - window[j - 1])     # 近似TR
                tr_sum += tr
                if high_diff > 0 and high_diff > low_diff:
                    plus_dm += high_diff
                if low_diff > 0 and low_diff > high_diff:
                    minus_dm += low_diff
            if tr_sum > 0:
                plus_di = plus_dm / tr_sum
                minus_di = minus_dm / tr_sum
                di_sum = plus_di + minus_di
                if di_sum > 0:
                    # ADX 近似：方向性指标的绝对差/和
                    factors["ADX_PROXY"][code] = abs(plus_di - minus_di) / di_sum
                else:
                    factors["ADX_PROXY"][code] = 0.0

        # === 量价类 ===

        # 14. VOLUME_RATIO: 近5日/近20日成交量
        if len(vols) >= 20:
            avg5 = np.mean(vols[-5:])
            avg20 = np.mean(vols[-20:])
            if avg20 > 0:
                factors["VOLUME_RATIO"][code] = avg5 / avg20

        # 15. PRICE_VOLUME_CORR: 价量相关性（过去20日）
        if n >= 20 and len(vols) >= 20:
            p_window = prices[-20:]
            v_window = vols[-20:]
            p_rets = [(p_window[j] - p_window[j-1]) / p_window[j-1]
                      for j in range(1, len(p_window)) if p_window[j-1] > 0]
            v_rets = [(v_window[j] - v_window[j-1]) / v_window[j-1]
                      for j in range(1, len(v_window)) if v_window[j-1] > 0]
            min_len = min(len(p_rets), len(v_rets))
            if min_len >= 10:
                corr = np.corrcoef(p_rets[:min_len], v_rets[:min_len])[0, 1]
                if not np.isnan(corr):
                    factors["PRICE_VOLUME_CORR"][code] = corr

        # 16. OBV_SLOPE: OBV斜率（资金流向）
        if n >= 20 and len(vols) >= 20:
            obv = 0
            obv_series = [0]
            p_window = prices[-20:]
            v_window = vols[-20:]
            for j in range(1, len(p_window)):
                if p_window[j] > p_window[j - 1]:
                    obv += v_window[j]
                elif p_window[j] < p_window[j - 1]:
                    obv -= v_window[j]
                obv_series.append(obv)
            # OBV 斜率：线性回归斜率归一化
            if len(obv_series) >= 5:
                x = np.arange(len(obv_series))
                slope = np.polyfit(x, obv_series, 1)[0]
                # 归一化：除以平均成交量
                avg_vol = np.mean(v_window) if np.mean(v_window) > 0 else 1
                factors["OBV_SLOPE"][code] = slope / avg_vol

        # === 价值/位置类 ===

        # 17. PRICE_LEVEL: 60日价格位置（低位优先）
        if n >= 60:
            window60 = prices[-60:]
            min60 = min(window60)
            max60 = max(window60)
            rng = max60 - min60
            if rng > 0:
                factors["PRICE_LEVEL"][code] = (prices[-1] - min60) / rng

        # 18. DRAWDOWN_RECOVERY: 从近20日最低点恢复程度
        if n >= 20:
            min20 = min(prices[-20:])
            if min20 > 0:
                factors["DRAWDOWN_RECOVERY"][code] = (prices[-1] - min20) / min20

        # 19. HIGH_DISTANCE: 距离60日最高价的距离（越近=越强势）
        if n >= 60:
            max60 = max(prices[-60:])
            if max60 > 0:
                # 负值：距离高点越远值越小
                factors["HIGH_DISTANCE"][code] = -(max60 - prices[-1]) / max60

        # === 风险调整类 ===

        # 20. SHARPE_20: 20日滚动Sharpe
        if len(rets_20) >= 10:
            mean_ret = np.mean(rets_20)
            std_ret = np.std(rets_20)
            if std_ret > 0:
                factors["SHARPE_20"][code] = mean_ret / std_ret
            else:
                factors["SHARPE_20"][code] = 0.0

        return factors

    def compute_scores(self):
        """
        计算综合因子评分
        返回 {ts_code: score}
        """
        factors = self._compute_all_factors()

        # 收集所有有因子值的股票
        all_codes = set()
        for fname, fdata in factors.items():
            all_codes.update(fdata.keys())

        if not all_codes:
            return {}

        # 对每个因子做排名归一化
        ranked_factors = {}
        for fname, fdata in factors.items():
            if not fdata:
                continue

            # 确定排序方向
            # 低值优先（值小排前）的因子：
            #   VOL_20: 低波动优先
            #   DOWNSIDE_VOL: 低下行波动优先
            #   PRICE_LEVEL: 低位优先
            #   BOLLINGER_POS: 布林带低位优先
            # 其他因子: 值大排前（已在计算时取负值的不需要再反转）
            if fname in ("VOL_20", "DOWNSIDE_VOL", "PRICE_LEVEL", "BOLLINGER_POS"):
                reverse = False
            else:
                reverse = True

            codes = sorted(fdata.keys())
            vals = [(c, fdata[c]) for c in codes if not np.isnan(fdata[c])]
            vals.sort(key=lambda x: x[1], reverse=reverse)
            n = len(vals)

            ranks = {}
            for i, (c, _) in enumerate(vals):
                ranks[c] = i / max(n - 1, 1)

            ranked_factors[fname] = ranks

        # 加权合成
        scores = {}
        for code in all_codes:
            total_weight = 0.0
            total_score = 0.0

            for fname, weight in self.factor_weights.items():
                if fname in ranked_factors and code in ranked_factors[fname]:
                    total_score += weight * ranked_factors[fname][code]
                    total_weight += weight

            if total_weight > 0:
                scores[code] = total_score / total_weight

        return scores

    def get_factor_exposures(self, code):
        """获取单只股票的因子暴露（用于调试）"""
        factors = self._compute_all_factors()
        exposures = {}
        for fname, fdata in factors.items():
            if code in fdata:
                exposures[fname] = fdata[code]
        return exposures
