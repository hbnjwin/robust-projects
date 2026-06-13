"""建表脚本：蒙特卡洛模拟交易表"""

import psycopg
import sys, os

sys.path.insert(0, os.path.expanduser("~/quant"))
from config import PG_CONFIG

conn = psycopg.connect(**PG_CONFIG)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS sim_runs (
    sim_id          VARCHAR(32) PRIMARY KEY,
    created_at      TIMESTAMP DEFAULT NOW(),
    start_date      DATE NOT NULL,
    end_date        DATE NOT NULL,
    duration_months INT,
    trading_days    INT,
    initial_capital NUMERIC(14,2) DEFAULT 1000000,
    final_equity    NUMERIC(14,2),
    total_return    NUMERIC(8,4),
    annual_return   NUMERIC(8,4),
    max_drawdown    NUMERIC(8,4),
    sharpe          NUMERIC(8,4),
    trend_return    NUMERIC(8,4),
    trend_dd        NUMERIC(8,4),
    trend_sharpe    NUMERIC(8,4),
    lowvol_return   NUMERIC(8,4),
    lowvol_dd       NUMERIC(8,4),
    lowvol_sharpe   NUMERIC(8,4),
    factor_return   NUMERIC(8,4),
    factor_dd       NUMERIC(8,4),
    factor_sharpe   NUMERIC(8,4),
    bull_days       INT DEFAULT 0,
    crisis_days     INT DEFAULT 0,
    neutral_days    INT DEFAULT 0,
    label           VARCHAR(32) DEFAULT '待分析',
    notes           TEXT DEFAULT ''
);
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS sim_daily (
    sim_id          VARCHAR(32) NOT NULL,
    trade_date      DATE NOT NULL,
    day_num         INT,
    regime          VARCHAR(10),
    total_equity    NUMERIC(14,2),
    daily_return    NUMERIC(8,6),
    drawdown        NUMERIC(8,6),
    trend_equity    NUMERIC(14,2),
    lowvol_equity   NUMERIC(14,2),
    factor_equity   NUMERIC(14,2),
    trend_positions INT DEFAULT 0,
    lowvol_positions INT DEFAULT 0,
    factor_positions INT DEFAULT 0,
    PRIMARY KEY (sim_id, trade_date)
);
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS sim_trades (
    id              SERIAL PRIMARY KEY,
    sim_id          VARCHAR(32) NOT NULL,
    trade_date      DATE NOT NULL,
    strategy        VARCHAR(10) NOT NULL,
    ts_code         VARCHAR(12) NOT NULL,
    action          VARCHAR(4) NOT NULL,
    price           NUMERIC(10,4),
    shares          INT,
    amount          NUMERIC(14,2),
    fee             NUMERIC(10,4),
    reason          VARCHAR(32) DEFAULT ''
);
""")

cur.execute("CREATE INDEX IF NOT EXISTS idx_sim_daily_sim ON sim_daily(sim_id);")
cur.execute("CREATE INDEX IF NOT EXISTS idx_sim_trades_sim ON sim_trades(sim_id);")
cur.execute("CREATE INDEX IF NOT EXISTS idx_sim_trades_date ON sim_trades(sim_id, trade_date);")
cur.execute("CREATE INDEX IF NOT EXISTS idx_sim_runs_dates ON sim_runs(start_date, end_date);")

conn.commit()
conn.close()
print("Tables created: sim_runs, sim_daily, sim_trades")
