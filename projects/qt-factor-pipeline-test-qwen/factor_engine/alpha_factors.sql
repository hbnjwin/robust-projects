-- Alpha158-style factor computation SQL
-- Reads from `prices` table (ts_code, trade_date, open, high, low, close, volume)
-- Produces `raw_factors` table with 37 factor columns + meta + labels

WITH base AS (
    SELECT *,
        LAG(close) OVER w AS prev_close,
        close / NULLIF(LAG(close) OVER w, 0) - 1 AS daily_return
    FROM prices
    WINDOW w AS (PARTITION BY ts_code ORDER BY trade_date)
)
SELECT
    ts_code,
    trade_date,
    close,
    volume,
    daily_return,

    -- ===== K-line pattern factors (9) =====
    (close - open) / NULLIF(open, 0) AS kmid,
    (high - low) / NULLIF(open, 0) AS klen,
    (close - open) / NULLIF(high - low + 1e-12, 0) AS kmid2,
    (high - GREATEST(open, close)) / NULLIF(open, 0) AS kup,
    (high - GREATEST(open, close)) / NULLIF(high - low + 1e-12, 0) AS kup2,
    (LEAST(open, close) - low) / NULLIF(open, 0) AS klow,
    (LEAST(open, close) - low) / NULLIF(high - low + 1e-12, 0) AS klow2,
    (close * 2 - high - low) / NULLIF(open, 0) AS ksft,
    (close * 2 - high - low) / NULLIF(high - low + 1e-12, 0) AS ksft2,

    -- ===== Price ratio factors (3) =====
    open / NULLIF(close, 0) AS open_ratio,
    high / NULLIF(close, 0) AS high_ratio,
    low / NULLIF(close, 0) AS low_ratio,

    -- ===== Momentum / ROC (5) =====
    close / NULLIF(LAG(close, 5) OVER w, 0) - 1 AS roc_5,
    close / NULLIF(LAG(close, 10) OVER w, 0) - 1 AS roc_10,
    close / NULLIF(LAG(close, 20) OVER w, 0) - 1 AS roc_20,
    close / NULLIF(LAG(close, 30) OVER w, 0) - 1 AS roc_30,
    close / NULLIF(LAG(close, 60) OVER w, 0) - 1 AS roc_60,

    -- ===== MA deviation (5) =====
    AVG(close) OVER w5 / NULLIF(close, 0) AS ma_5,
    AVG(close) OVER w10 / NULLIF(close, 0) AS ma_10,
    AVG(close) OVER w20 / NULLIF(close, 0) AS ma_20,
    AVG(close) OVER w30 / NULLIF(close, 0) AS ma_30,
    AVG(close) OVER w60 / NULLIF(close, 0) AS ma_60,

    -- ===== Volatility (5) =====
    STDDEV(daily_return) OVER w5 AS std_5,
    STDDEV(daily_return) OVER w10 AS std_10,
    STDDEV(daily_return) OVER w20 AS std_20,
    STDDEV(daily_return) OVER w30 AS std_30,
    STDDEV(daily_return) OVER w60 AS std_60,

    -- ===== High/Low range (4) =====
    MAX(high) OVER w20 / NULLIF(close, 0) AS max_20,
    MAX(high) OVER w60 / NULLIF(close, 0) AS max_60,
    MIN(low) OVER w20 / NULLIF(close, 0) AS min_20,
    MIN(low) OVER w60 / NULLIF(close, 0) AS min_60,

    -- ===== RSV (2) =====
    (close - MIN(low) OVER w20)
        / NULLIF(MAX(high) OVER w20 - MIN(low) OVER w20 + 1e-12, 0) AS rsv_20,
    (close - MIN(low) OVER w60)
        / NULLIF(MAX(high) OVER w60 - MIN(low) OVER w60 + 1e-12, 0) AS rsv_60,

    -- ===== Volume-price factors (4) =====
    AVG(volume) OVER w5 / NULLIF(volume + 1e-12, 0) AS vma_5,
    AVG(volume) OVER w20 / NULLIF(volume + 1e-12, 0) AS vma_20,
    STDDEV(volume) OVER w20 / NULLIF(volume + 1e-12, 0) AS vstd_20,
    AVG(volume) OVER w5 / NULLIF(AVG(volume) OVER w20 + 1e-12, 0) AS vol_ratio,

    -- ===== Labels (forward returns) =====
    LEAD(close, 3) OVER w / NULLIF(close, 0) - 1 AS label_3d,
    LEAD(close, 5) OVER w / NULLIF(close, 0) - 1 AS label_5d,
    LEAD(close, 10) OVER w / NULLIF(close, 0) - 1 AS label_10d

FROM base
WINDOW
    w   AS (PARTITION BY ts_code ORDER BY trade_date),
    w5  AS (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 4 PRECEDING AND CURRENT ROW),
    w10 AS (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 9 PRECEDING AND CURRENT ROW),
    w20 AS (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW),
    w30 AS (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 29 PRECEDING AND CURRENT ROW),
    w60 AS (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 59 PRECEDING AND CURRENT ROW)
ORDER BY ts_code, trade_date
