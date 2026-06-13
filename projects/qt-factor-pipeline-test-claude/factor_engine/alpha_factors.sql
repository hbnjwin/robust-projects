/*
 * Alpha158-style 因子计算 SQL (DuckDB)
 * 输入表: prices (ts_code, trade_date, open, high, low, close, volume)
 * 输出: 30+ 因子列 + meta 列 + label 列
 */

WITH base AS (
    SELECT
        ts_code,
        trade_date,
        open,
        high,
        low,
        close,
        volume,

        -- daily return
        close / NULLIF(LAG(close) OVER w, 0) - 1           AS daily_return,

        -- lagged close for momentum
        LAG(close, 5)  OVER w  AS close_5,
        LAG(close, 10) OVER w  AS close_10,
        LAG(close, 20) OVER w  AS close_20,

        -- future returns (labels)
        LEAD(close, 3)  OVER w / NULLIF(close, 0) - 1  AS label_3d,
        LEAD(close, 5)  OVER w / NULLIF(close, 0) - 1  AS label_5d,
        LEAD(close, 10) OVER w / NULLIF(close, 0) - 1  AS label_10d

    FROM prices
    WINDOW w AS (PARTITION BY ts_code ORDER BY trade_date)
),

rolling AS (
    SELECT
        *,

        -- ── 均线 ──
        AVG(close)  OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 4  PRECEDING AND CURRENT ROW)  AS ma5,
        AVG(close)  OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 9  PRECEDING AND CURRENT ROW)  AS ma10,
        AVG(close)  OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW)  AS ma20,

        -- ── 滚动波动率 ──
        STDDEV_SAMP(daily_return) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 4  PRECEDING AND CURRENT ROW)  AS vol_5d,
        STDDEV_SAMP(daily_return) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 9  PRECEDING AND CURRENT ROW)  AS vol_10d,
        STDDEV_SAMP(daily_return) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW)  AS vol_20d,

        -- ── 滚动成交量均值 ──
        AVG(volume) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 4  PRECEDING AND CURRENT ROW)  AS vol_ma5,
        AVG(volume) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 9  PRECEDING AND CURRENT ROW)  AS vol_ma10,
        AVG(volume) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW)  AS vol_ma20,

        -- ── 滚动极值 ──
        MAX(high) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 4  PRECEDING AND CURRENT ROW)  AS high_max5,
        MIN(low)  OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 4  PRECEDING AND CURRENT ROW)  AS low_min5,
        MAX(high) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW)  AS high_max20,
        MIN(low)  OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW)  AS low_min20,

        -- ── 滚动 return sum (动量) ──
        SUM(daily_return) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 4  PRECEDING AND CURRENT ROW)  AS ret_sum_5,
        SUM(daily_return) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 9  PRECEDING AND CURRENT ROW)  AS ret_sum_10,
        SUM(daily_return) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW)  AS ret_sum_20

    FROM base
)

SELECT
    ts_code,
    trade_date,
    close,
    volume,
    daily_return,

    -- ── 1-4: 动量因子 ──
    close / NULLIF(close_5, 0)  - 1         AS momentum_5d,
    close / NULLIF(close_10, 0) - 1         AS momentum_10d,
    close / NULLIF(close_20, 0) - 1         AS momentum_20d,
    ret_sum_5                               AS cum_ret_5d,

    -- ── 5-7: 均线偏离 (BIAS) ──
    (close - ma5)  / NULLIF(ma5, 0)         AS bias_5,
    (close - ma10) / NULLIF(ma10, 0)        AS bias_10,
    (close - ma20) / NULLIF(ma20, 0)        AS bias_20,

    -- ── 8-10: 均线交叉 ──
    ma5  / NULLIF(ma20, 0)                  AS ma5_ma20_ratio,
    ma5  / NULLIF(ma10, 0)                  AS ma5_ma10_ratio,
    ma10 / NULLIF(ma20, 0)                  AS ma10_ma20_ratio,

    -- ── 11-13: 波动率 ──
    vol_5d                                  AS volatility_5d,
    vol_10d                                 AS volatility_10d,
    vol_20d                                 AS volatility_20d,

    -- ── 14-15: 波动率比 ──
    vol_5d  / NULLIF(vol_20d, 0)            AS vol_ratio_5_20,
    vol_10d / NULLIF(vol_20d, 0)            AS vol_ratio_10_20,

    -- ── 16-18: 量比 ──
    volume / NULLIF(vol_ma5, 0)             AS volume_ratio_5,
    volume / NULLIF(vol_ma10, 0)            AS volume_ratio_10,
    volume / NULLIF(vol_ma20, 0)            AS volume_ratio_20,

    -- ── 19-20: K 线形态 ──
    (high - low)  / NULLIF(close, 0)        AS price_range,
    (close - open) / NULLIF(high - low, 0)  AS candle_body,

    -- ── 21-22: 上下影线 ──
    (high - GREATEST(open, close)) / NULLIF(high - low, 0)   AS upper_shadow,
    (LEAST(open, close) - low)     / NULLIF(high - low, 0)   AS lower_shadow,

    -- ── 23-24: 价格位置 ──
    (close - low_min20)  / NULLIF(high_max20 - low_min20, 0)  AS price_position_20d,
    (close - low_min5)   / NULLIF(high_max5  - low_min5,  0)  AS price_position_5d,

    -- ── 25-26: 极值比 ──
    high / NULLIF(high_max5, 0)             AS high_breakout_5d,
    low  / NULLIF(low_min5, 0)              AS low_breakout_5d,

    -- ── 27-28: 振幅 ──
    (high_max5  - low_min5)  / NULLIF(close, 0)  AS amplitude_5d,
    (high_max20 - low_min20) / NULLIF(close, 0)  AS amplitude_20d,

    -- ── 29: VWAP 偏离 (近似) ──
    close / NULLIF(
        SUM(close * volume) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 4 PRECEDING AND CURRENT ROW)
        / NULLIF(SUM(volume) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 4 PRECEDING AND CURRENT ROW), 0)
    , 0) - 1                                AS vwap_bias_5d,

    -- ── 30: 量价相关性 (5日方向一致性) ──
    ret_sum_5 * (volume / NULLIF(vol_ma5, 0) - 1)  AS price_volume_corr_5d,

    -- ── 31-32: 累计收益动量 ──
    ret_sum_10                              AS cum_ret_10d,
    ret_sum_20                              AS cum_ret_20d,

    -- ── 33: 日内收益率 ──
    close / NULLIF(open, 0) - 1             AS intraday_return,

    -- ── 34: 跳空缺口 ──
    open / NULLIF(LAG(close) OVER (PARTITION BY ts_code ORDER BY trade_date), 0) - 1  AS gap,

    -- ── 35: 成交量变化率 ──
    volume / NULLIF(LAG(volume) OVER (PARTITION BY ts_code ORDER BY trade_date), 0) - 1  AS volume_change,

    -- ── labels ──
    label_3d,
    label_5d,
    label_10d

FROM rolling
ORDER BY ts_code, trade_date
