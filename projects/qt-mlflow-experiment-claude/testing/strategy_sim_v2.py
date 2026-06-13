"""
策略推演引擎 v2
支持指定/随机时间窗口，三策略完整模拟，推演主表+持仓表+交易变化表+每日快照
自动打标签，后台驻留每30分钟运行一次

用法:
    cd /home/tulin/quant
    .venv/bin/python testing/strategy_sim_v2.py              # 单次随机
    .venv/bin/python testing/strategy_sim_v2.py --daemon     # 后台驻留
    .venv/bin/python testing/strategy_sim_v2.py --start 2025-01-06 --months 3
    .venv/bin/python testing/strategy_sim_v2.py --count 5
"""
import sys, os, time, random, argparse, functools
from datetime import datetime, timedelta
from pathlib import Path
import numpy as np
import pandas as pd
import psycopg

print = functools.partial(print, flush=True)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import PG_CONFIG
from live.data_loader_fast import load_market_data_fast
from live.strategy_account import StrategyAccount
from live.execution_engine_v2 import ExecutionEngine
from live.trend_strategy_v2 import TrendStrategyV2
from live.lowvol_strategy_v2 import LowVolStrategy
from live.regime_detector_v2 import RegimeDetectorV2
from strategies.factor_strategy import FactorStrategy

INITIAL_CAPITAL = 1_000_000
TREND_RATIO, LOWVOL_RATIO, FACTOR_RATIO, CASH_RATIO = 0.35, 0.20, 0.25, 0.20
REPORT_DIR = "testing/sim_reports_v2"
os.makedirs(REPORT_DIR, exist_ok=True)

_ml_signals = None

def load_ml_signals():
    global _ml_signals
    if _ml_signals is None:
        p = "data/ml_signals.parquet"
        if not os.path.exists(p):
            print("[sim] WARNING: ml_signals.parquet not found")
            _ml_signals = {}
            return _ml_signals
        df = pd.read_parquet(p)
        _ml_signals = {}
        for d, g in df.groupby("trade_date"):
            _ml_signals[d] = dict(zip(g["ts_code"], g["score"]))
        print(f"[sim] ML signals: {len(_ml_signals)} days")
    return _ml_signals


def random_window():
    s = datetime(2018, 6, 1) + timedelta(
        days=random.randint(0, (datetime(2025, 9, 1) - datetime(2018, 6, 1)).days))
    m = random.choice([1, 2, 3, 6])
    e = s + timedelta(days=m * 30)
    return s.strftime("%Y-%m-%d"), e.strftime("%Y-%m-%d"), m


def gen_sim_id():
    return "SIM-" + datetime.now().strftime("%Y%m%d%H%M%S") + "-" + str(random.randint(100, 999))


def calc_sharpe(eq):
    if len(eq) < 2:
        return 0.0
    r = [(eq[i] - eq[i-1]) / eq[i-1] for i in range(1, len(eq)) if eq[i-1] > 0]
    return float(np.mean(r) / np.std(r) * np.sqrt(240)) if len(r) > 1 and np.std(r) > 0 else 0.0


def calc_mdd(eq):
    peak, mdd = eq[0], 0.0
    for v in eq:
        if v > peak:
            peak = v
        d = (peak - v) / peak if peak > 0 else 0
        if d > mdd:
            mdd = d
    return mdd


def run_single_sim(start_date=None, end_date=None, months=None, notes=""):
    if start_date is None:
        start_date, end_date, months = random_window()
    elif end_date is None:
        months = months or 3
        end_date = (datetime.strptime(start_date, "%Y-%m-%d") + timedelta(days=months * 30)).strftime("%Y-%m-%d")

    sim_id = gen_sim_id()
    ml_signals = load_ml_signals()
    print("\n" + "=" * 60)
    print(f"  {sim_id}")
    print(f"  {start_date} ~ {end_date}  ({months}M)")
    print("=" * 60)

    ws = (datetime.strptime(start_date, "%Y-%m-%d") - timedelta(days=90)).strftime("%Y-%m-%d")
    mkt = load_market_data_fast(ws, end_date)
    if not mkt:
        print("  [SKIP] no data")
        return None

    dates = sorted(mkt.keys())
    sim_dates = [d for d in dates if start_date <= d <= end_date]
    warm_dates = [d for d in dates if d < start_date]
    if len(sim_dates) < 5:
        print(f"  [SKIP] only {len(sim_dates)} days")
        return None
    print(f"  Warmup:{len(warm_dates)}  Sim:{len(sim_dates)}")

    ta = StrategyAccount("Trend",  INITIAL_CAPITAL * TREND_RATIO)
    la = StrategyAccount("LowVol", INITIAL_CAPITAL * LOWVOL_RATIO)
    fa = StrategyAccount("Factor", INITIAL_CAPITAL * FACTOR_RATIO)
    te = ExecutionEngine(ta)
    le = ExecutionEngine(la)
    fe = ExecutionEngine(fa)
    ts = TrendStrategyV2()
    lv = LowVolStrategy()
    det = RegimeDetectorV2()
    fstrat = FactorStrategy(factor_scores=ml_signals, top_n=15, rebalance_days=5)

    for d in warm_dates:
        p = mkt[d]
        cl = [v["close"] for v in p.values() if v.get("close", 0) > 0]
        if cl:
            det.update(np.mean(cl), 0)
        ts.generate(d, p)
        lv.set_regime(det.detect())
        lv.generate(d, p)
        fstrat.generate(d, p)

    daily, trades, positions = [], [], []
    rc = {"BULL": 0, "CRISIS": 0, "NEUTRAL": 0}
    prev = INITIAL_CAPITAL
    curve = [INITIAL_CAPITAL]

    for dn, d in enumerate(sim_dates, 1):
        p = mkt[d]
        cl = [v["close"] for v in p.values() if v.get("close", 0) > 0]
        if cl:
            det.update(np.mean(cl), 0)
        reg = det.detect()
        rc[reg] = rc.get(reg, 0) + 1
        lv.set_regime(reg)

        tsg = ts.generate(d, p)
        lsg = lv.generate(d, p)
        fsg = fstrat.generate(d, p)

        if reg == "CRISIS":
            tsg = [{"action": "sell", "ts_code": c} for c in list(ta.positions.keys())]
            lsg = [{"action": "sell", "ts_code": c} for c in list(la.positions.keys())]
            fsg = [{"action": "sell", "ts_code": c} for c in list(fa.positions.keys())]

        te.queue_orders(tsg)
        le.queue_orders(lsg)
        fe.queue_orders(fsg)
        te.execute(p, date=d)
        le.execute(p, date=d)
        fe.execute(p, date=d)
        ta.mark_to_market(p)
        la.mark_to_market(p)
        fa.mark_to_market(p)

        eq = ta.total_equity + la.total_equity + fa.total_equity + INITIAL_CAPITAL * CASH_RATIO
        dr = (eq - prev) / prev if prev > 0 else 0
        prev = eq
        curve.append(eq)
        pk = max(curve)
        dd = (pk - eq) / pk if pk > 0 else 0

        daily.append({
            "sim_id": sim_id, "trade_date": d, "day_num": dn, "regime": reg,
            "total_equity": round(eq, 2), "daily_return": round(dr, 6), "drawdown": round(dd, 6),
            "trend_equity": round(ta.total_equity, 2),
            "lowvol_equity": round(la.total_equity, 2),
            "factor_equity": round(fa.total_equity, 2),
            "trend_positions": len(ta.positions),
            "lowvol_positions": len(la.positions),
            "factor_positions": len(fa.positions),
        })

        for sn, acc in [("Trend", ta), ("LowVol", la), ("Factor", fa)]:
            for t in acc.trade_log:
                trades.append({
                    "sim_id": sim_id, "trade_date": d, "strategy": sn,
                    "ts_code": t["code"], "action": t["action"],
                    "price": t["price"], "shares": t["shares"],
                    "amount": round(t["price"] * t["shares"], 2),
                    "fee": round(t["fee"], 4), "reason": t.get("reason", ""),
                })
            acc.trade_log.clear()
            for code, pos in acc.positions.items():
                mp = p.get(code, {}).get("close", 0)
                ac = pos.get("avg_cost", 0)
                sh = pos.get("shares", 0)
                mv = round(mp * sh, 2)
                pnl = round((mp / ac - 1) * 100, 4) if ac > 0 else 0
                bd = pos.get("buy_date", d)
                try:
                    hold = (datetime.strptime(d, "%Y-%m-%d") - datetime.strptime(str(bd), "%Y-%m-%d")).days
                except Exception:
                    hold = 0
                positions.append({
                    "sim_id": sim_id, "trade_date": d, "strategy": sn,
                    "ts_code": code, "shares": sh, "avg_cost": round(ac, 4),
                    "market_price": round(mp, 4), "market_value": mv,
                    "pnl_pct": pnl, "hold_days": hold,
                })

    feq = curve[-1]
    tr = (feq / INITIAL_CAPITAL - 1) * 100
    days_n = len(sim_dates)
    ar = tr / days_n * 240 if days_n > 0 else 0
    mdd = calc_mdd(curve)
    sh = calc_sharpe(curve)

    def sr(acc, cap): return round((acc.total_equity / cap - 1) * 100, 4)
    def sd(acc): return round(getattr(acc, "max_drawdown", 0) * 100, 4)
    def ss(acc, cap, key): return round(calc_sharpe([cap] + [r[key] for r in daily]), 4)

    t_r = sr(ta, INITIAL_CAPITAL * TREND_RATIO)
    l_r = sr(la, INITIAL_CAPITAL * LOWVOL_RATIO)
    f_r = sr(fa, INITIAL_CAPITAL * FACTOR_RATIO)
    t_d = sd(ta); l_d = sd(la); f_d = sd(fa)
    t_s = ss(ta, INITIAL_CAPITAL * TREND_RATIO, "trend_equity")
    l_s = ss(la, INITIAL_CAPITAL * LOWVOL_RATIO, "lowvol_equity")
    f_s = ss(fa, INITIAL_CAPITAL * FACTOR_RATIO, "factor_equity")

    tags = []
    notable = False
    if tr > 10:   tags.append("高收益");    notable = True
    if tr < -10:  tags.append("大亏损");    notable = True
    if mdd > 0.15: tags.append("高回撤");   notable = True
    if tr > 5 and mdd < 0.08: tags.append("理想场景"); notable = True
    if rc.get("CRISIS", 0) > days_n * 0.3: tags.append("危机主导"); notable = True
    if rc.get("BULL", 0) > days_n * 0.7:   tags.append("牛市主导")
    if f_r > t_r + 5 and f_r > l_r + 5:   tags.append("Factor领先"); notable = True
    if t_r > f_r + 5 and t_r > l_r + 5:   tags.append("Trend领先")
    if l_r > f_r + 5 and l_r > t_r + 5:   tags.append("LowVol领先")
    if t_r < 0 and l_r < 0 and f_r < 0:   tags.append("全线亏损")
    if t_r > 0 and l_r > 0 and f_r > 0:   tags.append("全线盈利")
    if sh > 1.5:  tags.append("高Sharpe"); notable = True
    if mdd < 0.05 and tr > 0: tags.append("低回撤盈利")

    conn = psycopg.connect(**PG_CONFIG)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO sim_runs(sim_id,start_date,end_date,duration_months,trading_days,"
        "final_equity,total_return,annual_return,max_drawdown,sharpe,"
        "trend_return,trend_dd,trend_sharpe,lowvol_return,lowvol_dd,lowvol_sharpe,"
        "factor_return,factor_dd,factor_sharpe,bull_days,crisis_days,neutral_days,"
        "tags,is_notable,label,notes) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (sim_id, start_date, end_date, months, days_n,
         round(feq, 2), round(tr, 4), round(ar, 4), round(mdd * 100, 4), round(sh, 4),
         t_r, t_d, t_s, l_r, l_d, l_s, f_r, f_d, f_s,
         rc.get("BULL", 0), rc.get("CRISIS", 0), rc.get("NEUTRAL", 0),
         tags, notable, "/".join(tags) if tags else "", notes))

    for r in daily:
        cur.execute(
            "INSERT INTO sim_daily(sim_id,trade_date,day_num,regime,total_equity,daily_return,drawdown,"
            "trend_equity,lowvol_equity,factor_equity,trend_positions,lowvol_positions,factor_positions)"
            " VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (r["sim_id"], r["trade_date"], r["day_num"], r["regime"],
             r["total_equity"], r["daily_return"], r["drawdown"],
             r["trend_equity"], r["lowvol_equity"], r["factor_equity"],
             r["trend_positions"], r["lowvol_positions"], r["factor_positions"]))

    for t in trades:
        cur.execute(
            "INSERT INTO sim_trades(sim_id,trade_date,strategy,ts_code,action,price,shares,amount,fee,reason)"
            " VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (t["sim_id"], t["trade_date"], t["strategy"], t["ts_code"],
             t["action"], t["price"], t["shares"], t["amount"], t["fee"], t["reason"]))

    for pos in positions:
        cur.execute(
            "INSERT INTO sim_positions(sim_id,trade_date,strategy,ts_code,shares,avg_cost,"
            "market_price,market_value,pnl_pct,hold_days)"
            " VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
            " ON CONFLICT(sim_id,trade_date,strategy,ts_code) DO NOTHING",
            (pos["sim_id"], pos["trade_date"], pos["strategy"], pos["ts_code"],
             pos["shares"], pos["avg_cost"], pos["market_price"],
             pos["market_value"], pos["pnl_pct"], pos["hold_days"]))

    conn.commit()
    conn.close()

    # ── Markdown 报告 ──
    tag_str = ", ".join(tags) if tags else "无"
    notable_str = "有代表意义" if notable else "普通"

    last_pos = [p for p in positions if p["trade_date"] == sim_dates[-1]]
    pos_rows = ""
    if last_pos:
        pos_rows = "\n## 最终持仓\n\n| 策略 | 股票 | 股数 | 成本 | 现价 | 市值 | 盈亏% | 持仓天 |\n"
        pos_rows += "|------|------|------|------|------|------|-------|--------|\n"
        for p in sorted(last_pos, key=lambda x: (x["strategy"], -x["market_value"])):
            pos_rows += (f"| {p['strategy']} | {p['ts_code']} | {p['shares']} | "
                         f"{p['avg_cost']:.2f} | {p['market_price']:.2f} | "
                         f"{p['market_value']:,.0f} | {p['pnl_pct']:+.2f}% | {p['hold_days']} |\n")

    eq_rows = ""
    for i, r in enumerate(daily):
        if i % 5 == 0 or i == len(daily) - 1:
            eq_rows += (f"| {r['trade_date']} | {r['regime']} | {r['total_equity']:,.0f} | "
                        f"{r['daily_return']*100:+.2f}% | {r['drawdown']*100:.2f}% | "
                        f"{r['trend_positions']}/{r['lowvol_positions']}/{r['factor_positions']} |\n")

    bc = sum(1 for t in trades if t["action"] == "buy")
    sc = sum(1 for t in trades if t["action"] == "sell")
    tf = sum(t["fee"] for t in trades)
    t_bc = sum(1 for t in trades if t["strategy"] == "Trend"  and t["action"] == "buy")
    t_sc = sum(1 for t in trades if t["strategy"] == "Trend"  and t["action"] == "sell")
    l_bc = sum(1 for t in trades if t["strategy"] == "LowVol" and t["action"] == "buy")
    l_sc = sum(1 for t in trades if t["strategy"] == "LowVol" and t["action"] == "sell")
    f_bc = sum(1 for t in trades if t["strategy"] == "Factor" and t["action"] == "buy")
    f_sc = sum(1 for t in trades if t["strategy"] == "Factor" and t["action"] == "sell")

    lines = [
        f"# 策略推演报告 {sim_id}",
        "",
        "## 基本信息",
        "| 项目 | 值 |",
        "|------|-----|",
        f"| 推演编号 | `{sim_id}` |",
        f"| 时间窗口 | {start_date} ~ {end_date} |",
        f"| 持仓时长 | {months} 个月 ({days_n} 个交易日) |",
        "| 初始资金 | 1,000,000 元 |",
        f"| 最终权益 | {feq:,.2f} 元 |",
        f"| 市场环境 | BULL {rc.get('BULL',0)}天 / NEUTRAL {rc.get('NEUTRAL',0)}天 / CRISIS {rc.get('CRISIS',0)}天 |",
        f"| 标签 | {tag_str} |",
        f"| 代表性 | {notable_str} |",
        f"| 备注 | {notes if notes else '—'} |",
        "",
        "## 策略表现",
        "| 策略 | 占比 | 收益% | 回撤% | Sharpe | 买入 | 卖出 |",
        "|------|------|-------|-------|--------|------|------|",
        f"| Trend  | 35% | {t_r:+.2f} | {t_d:.2f} | {t_s:.2f} | {t_bc} | {t_sc} |",
        f"| LowVol | 20% | {l_r:+.2f} | {l_d:.2f} | {l_s:.2f} | {l_bc} | {l_sc} |",
        f"| Factor | 25% | {f_r:+.2f} | {f_d:.2f} | {f_s:.2f} | {f_bc} | {f_sc} |",
        f"| **组合** | 80% | **{tr:+.2f}** | **{mdd*100:.2f}** | **{sh:.2f}** | {bc} | {sc} |",
        "",
        f"> 现金储备 20% 不参与交易 | 总手续费: {tf:,.2f} 元",
        "",
        "## 权益曲线 (每5日采样)",
        "| 日期 | Regime | 总权益 | 日收益 | 回撤 | 持仓(T/L/F) |",
        "|------|--------|--------|--------|------|------------|",
        eq_rows,
        pos_rows,
        "## 标注区",
        f"- **标签**: {tag_str}",
        f"- **代表性**: {notable_str}",
        "- **策略优劣分析**: _(待填写)_",
        "- **市场环境描述**: _(待填写)_",
        "- **改进建议**: _(待填写)_",
        "- **参数调整方向**: _(待填写)_",
        "",
        "---",
        f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Engine: strategy_sim_v2*",
    ]
    report = "\n".join(lines)
    rp = os.path.join(REPORT_DIR, f"{sim_id}.md")
    with open(rp, "w") as f:
        f.write(report)

    print(f"  ret={tr:+.2f}%  dd={mdd*100:.2f}%  sh={sh:.2f}")
    print(f"  T={t_r:+.2f}%  L={l_r:+.2f}%  F={f_r:+.2f}%")
    print(f"  trades={len(trades)}  fee={tf:.2f}  tags={tag_str}")
    print(f"  report={rp}")
    return sim_id


def main():
    p = argparse.ArgumentParser(description="Strategy Sim v2")
    p.add_argument("--daemon",   action="store_true", help="后台驻留模式")
    p.add_argument("--count",    type=int, default=1,    help="连续运行次数")
    p.add_argument("--interval", type=int, default=1800, help="驻留间隔(秒)")
    p.add_argument("--start",    type=str, default=None, help="起始日期 YYYY-MM-DD")
    p.add_argument("--end",      type=str, default=None, help="结束日期 YYYY-MM-DD")
    p.add_argument("--months",   type=int, default=None, help="持仓时长(月)")
    p.add_argument("--notes",    type=str, default="",   help="备注")
    a = p.parse_args()

    if a.daemon:
        print(f"[sim_v2] daemon  interval={a.interval}s ({a.interval//60}min)")
        n = 0
        while True:
            n += 1
            print(f"\n[sim_v2] Run #{n} @ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            try:
                run_single_sim(a.start, a.end, a.months, a.notes)
            except Exception as e:
                print(f"[sim_v2] Error: {e}")
                import traceback; traceback.print_exc()
            print(f"[sim_v2] sleep {a.interval}s ...")
            time.sleep(a.interval)
    else:
        for i in range(a.count):
            print(f"\n[sim_v2] Run {i+1}/{a.count}")
            try:
                run_single_sim(a.start, a.end, a.months, a.notes)
            except Exception as e:
                print(f"[sim_v2] Error: {e}")
                import traceback; traceback.print_exc()


if __name__ == "__main__":
    main()
