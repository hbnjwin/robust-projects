"""
watchlist_monitor.py — 监控池每日技术分析 + 大盘择时
每天 15:30 运行，输出飞书推送报告

功能：
1. 大盘状态判断（沪深300 跌幅/回撤/成交量）
2. watchlist 标的技术分析（MA/MACD/RSI/布林带/量能）
3. 超跌候选筛选（全市场 RSI<35 + 放量）
4. 推送飞书报告
"""
import sys
import sqlite3
import json
from pathlib import Path
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from data.db import get_conn

# ── 技术指标计算 ──────────────────────────────────────────

def calc_ma(close: pd.Series, n: int) -> float:
    if len(close) < n:
        return float("nan")
    return round(close.iloc[-n:].mean(), 3)


def calc_rsi(close: pd.Series, n: int = 14) -> float:
    if len(close) < n + 1:
        return float("nan")
    delta = close.diff().iloc[-(n + 1):]
    gain = delta.clip(lower=0).mean()
    loss = (-delta.clip(upper=0)).mean()
    if loss == 0:
        return 100.0
    rs = gain / loss
    return round(100 - 100 / (1 + rs), 1)


def calc_macd(close: pd.Series):
    """返回 (macd_line, signal_line, histogram) 最新值"""
    if len(close) < 35:
        return float("nan"), float("nan"), float("nan")
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    hist = macd - signal
    return round(macd.iloc[-1], 4), round(signal.iloc[-1], 4), round(hist.iloc[-1], 4)


def calc_boll(close: pd.Series, n: int = 20):
    """返回 (upper, mid, lower) 最新值"""
    if len(close) < n:
        return float("nan"), float("nan"), float("nan")
    mid = close.iloc[-n:].mean()
    std = close.iloc[-n:].std()
    return round(mid + 2 * std, 3), round(mid, 3), round(mid - 2 * std, 3)


def calc_drawdown_from_high(close: pd.Series, lookback: int = 120) -> float:
    """从近 lookback 日高点的回撤"""
    if len(close) < 2:
        return 0.0
    window = close.iloc[-lookback:]
    peak = window.max()
    current = close.iloc[-1]
    return round((current - peak) / peak * 100, 2)


def vol_ratio(vol: pd.Series, n: int = 20) -> float:
    """当日成交量 / 近 n 日均量"""
    if len(vol) < n + 1:
        return float("nan")
    avg = vol.iloc[-(n + 1):-1].mean()
    if avg == 0:
        return float("nan")
    return round(vol.iloc[-1] / avg, 2)


# ── 数据加载 ──────────────────────────────────────────────

def _is_trading_day_and_closed() -> bool:
    """判断今天是否是交易日且已收盘（15:00后）"""
    now = datetime.now()
    if now.weekday() >= 5:  # 周末
        return False
    return now.hour >= 15


def _fetch_realtime_today(ts_code: str) -> pd.Series | None:
    """用腾讯财经拉今日收盘行情，返回一行 Series 或 None"""
    try:
        import requests, json as _json
        today_str = datetime.today().strftime("%Y-%m-%d")
        symbol = ts_code.split(".")[0]
        exch = "sh" if ts_code.endswith(".SH") else "sz"
        tx_code = f"{exch}{symbol}"

        url = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
        params = {
            "_var": "kline_dayqfq",
            "param": f"{tx_code},day,{today_str},{today_str},1,qfq"
        }
        r = requests.get(url, params=params, timeout=8,
                         headers={"User-Agent": "Mozilla/5.0"})
        text = r.text
        d = _json.loads(text[text.index("=") + 1:])
        day_data = d.get("data", {}).get(tx_code, {}).get("day", [])
        if not day_data:
            # 尝试 qfq 字段（复权）
            day_data = d.get("data", {}).get(tx_code, {}).get("qfqday", [])
        if not day_data:
            return None

        row = day_data[-1]  # [date, open, close, high, low, vol]
        return pd.Series({
            "trade_date": row[0],
            "open":  float(row[1]),
            "close": float(row[2]),
            "high":  float(row[3]),
            "low":   float(row[4]),
            "vol":   float(row[5]) if len(row) > 5 else 0.0,
        })
    except Exception:
        return None


def load_price(conn: sqlite3.Connection, ts_code: str, days: int = 150) -> pd.DataFrame:
    cutoff = (datetime.today() - timedelta(days=days * 2)).strftime("%Y%m%d")
    df = pd.read_sql(
        "SELECT trade_date, open, high, low, close, vol FROM daily_price "
        "WHERE ts_code=? AND trade_date>=? ORDER BY trade_date",
        conn, params=(ts_code, cutoff)
    )
    df = df.tail(days)

    # 如果今天是交易日且已收盘，检查 DB 是否缺今日数据
    if _is_trading_day_and_closed():
        today_str = datetime.today().strftime("%Y-%m-%d")
        if df.empty:
            # DB 完全没有该股票数据，直接拉实时
            today_row = _fetch_realtime_today(ts_code)
            if today_row is not None:
                df = today_row.to_frame().T.reset_index(drop=True)
        else:
            # DB 有历史数据，检查是否缺今日
            raw_latest = str(df.iloc[-1]["trade_date"])
            db_latest = raw_latest[:4] + "-" + raw_latest[4:6] + "-" + raw_latest[6:] \
                if len(raw_latest) == 8 else raw_latest[:10]
            if db_latest < today_str:
                today_row = _fetch_realtime_today(ts_code)
                if today_row is not None:
                    df = pd.concat([df, today_row.to_frame().T], ignore_index=True)

    return df


def load_watchlist(conn: sqlite3.Connection):
    return pd.read_sql("SELECT ts_code, name, category, note FROM watchlist", conn)


# ── 大盘分析 ──────────────────────────────────────────────

def analyze_market(conn: sqlite3.Connection) -> dict:
    hs300 = load_price(conn, "000300.SH", 150)
    if hs300.empty:
        return {"status": "数据不足", "signal": "UNKNOWN"}

    close = hs300["close"]
    vol = hs300["vol"]
    today_ret = round((close.iloc[-1] - close.iloc[-2]) / close.iloc[-2] * 100, 2)
    drawdown = calc_drawdown_from_high(close, 60)
    vr = vol_ratio(vol, 20)
    rsi = calc_rsi(close, 14)
    ma5 = calc_ma(close, 5)
    ma20 = calc_ma(close, 20)
    ma60 = calc_ma(close, 60)

    # 择时信号
    signal = "NEUTRAL"
    alerts = []

    if today_ret <= -5:
        alerts.append(f"⚠️ 单日暴跌 {today_ret}%")
        signal = "CRASH"
    elif today_ret <= -3:
        alerts.append(f"🔴 单日大跌 {today_ret}%")
        signal = "WEAK"
    elif today_ret <= -2:
        alerts.append(f"🟠 单日下跌 {today_ret}%")
        if signal == "NEUTRAL":
            signal = "WEAK"

    if drawdown <= -20:
        alerts.append(f"⚠️ 从高点回撤 {drawdown}%（深度调整）")
        signal = "BUY_ZONE"
    elif drawdown <= -15:
        alerts.append(f"🟡 从高点回撤 {drawdown}%（关注进仓机会）")
        if signal not in ("CRASH",):
            signal = "WATCH"
    elif drawdown <= -10:
        alerts.append(f"从高点回撤 {drawdown}%")

    if isinstance(vr, float) and vr >= 2.0:
        alerts.append(f"📊 成交量放大 {vr}x（恐慌性抛售信号）")

    if rsi < 30:
        alerts.append(f"RSI={rsi}（超卖）")

    return {
        "ts_code": "000300.SH",
        "name": "沪深300",
        "close": round(close.iloc[-1], 2),
        "today_ret": today_ret,
        "drawdown_60d": drawdown,
        "rsi14": rsi,
        "ma5": ma5, "ma20": ma20, "ma60": ma60,
        "vol_ratio": vr,
        "signal": signal,
        "alerts": alerts,
    }


# ── 个股技术分析 ──────────────────────────────────────────

def analyze_stock(conn: sqlite3.Connection, ts_code: str, name: str) -> dict:
    df = load_price(conn, ts_code, 150)
    if len(df) < 30:
        return {"ts_code": ts_code, "name": name, "error": "数据不足"}

    close = df["close"]
    vol = df["vol"]
    today_ret = round((close.iloc[-1] - close.iloc[-2]) / close.iloc[-2] * 100, 2)
    rsi = calc_rsi(close, 14)
    macd, signal_line, hist = calc_macd(close)
    boll_u, boll_m, boll_l = calc_boll(close, 20)
    ma5 = calc_ma(close, 5)
    ma20 = calc_ma(close, 20)
    ma60 = calc_ma(close, 60)
    drawdown = calc_drawdown_from_high(close, 60)
    vr = vol_ratio(vol, 20)
    cur = round(close.iloc[-1], 3)

    # 技术信号
    signals = []
    if rsi < 30:
        signals.append("RSI超卖")
    if rsi > 70:
        signals.append("RSI超买")
    if hist > 0 and macd > signal_line:
        signals.append("MACD金叉")
    elif hist < 0 and macd < signal_line:
        signals.append("MACD死叉")
    if not np.isnan(boll_l) and cur < boll_l:
        signals.append("跌破布林下轨")
    if not np.isnan(boll_u) and cur > boll_u:
        signals.append("突破布林上轨")
    if not np.isnan(ma5) and not np.isnan(ma20):
        if ma5 > ma20:
            signals.append("MA5>MA20")
        else:
            signals.append("MA5<MA20")
    if isinstance(vr, float) and vr >= 1.5:
        signals.append(f"放量{vr}x")

    return {
        "ts_code": ts_code,
        "name": name,
        "close": cur,
        "today_ret": today_ret,
        "rsi14": rsi,
        "macd_hist": hist,
        "boll": f"{boll_l}~{boll_u}",
        "ma5": ma5, "ma20": ma20, "ma60": ma60,
        "drawdown_60d": drawdown,
        "vol_ratio": vr,
        "signals": signals,
    }


# ── 超跌候选筛选 ──────────────────────────────────────────

def scan_oversold(conn: sqlite3.Connection, top_n: int = 10) -> list:
    """全市场扫描 RSI<35 + 放量的标的"""
    codes_df = pd.read_sql(
        "SELECT DISTINCT ts_code FROM daily_price "
        "WHERE ts_code NOT LIKE '0003%' AND ts_code NOT LIKE '3990%' "
        "AND ts_code NOT LIKE '5%' AND ts_code NOT LIKE '1599%'",
        conn
    )
    candidates = []
    for ts_code in codes_df["ts_code"].tolist():
        try:
            df = load_price(conn, ts_code, 60)
            if len(df) < 20:
                continue
            close = df["close"]
            vol = df["vol"]
            rsi = calc_rsi(close, 14)
            vr = vol_ratio(vol, 20)
            drawdown = calc_drawdown_from_high(close, 60)
            if rsi < 35 and isinstance(vr, float) and vr >= 1.3 and drawdown <= -10:
                candidates.append({
                    "ts_code": ts_code,
                    "rsi": rsi,
                    "vol_ratio": vr,
                    "drawdown": drawdown,
                    "close": round(close.iloc[-1], 3),
                })
        except Exception:
            continue
    candidates.sort(key=lambda x: x["rsi"])
    return candidates[:top_n]


# ── 报告生成 ──────────────────────────────────────────────

def build_report(market: dict, watchlist_results: list, oversold: list) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    lines = [f"📊 量化监控日报 {today}\n"]

    # 大盘
    lines.append("━━━ 大盘状态 ━━━")
    sig_emoji = {"CRASH": "🔴", "WEAK": "🟠", "WATCH": "🟡",
                 "BUY_ZONE": "🟢", "NEUTRAL": "⚪"}.get(market.get("signal", ""), "⚪")
    lines.append(f"{sig_emoji} 沪深300: {market.get('close')}  今日 {market.get('today_ret')}%")
    lines.append(f"   60日回撤: {market.get('drawdown_60d')}%  RSI: {market.get('rsi14')}")
    lines.append(f"   MA5/20/60: {market.get('ma5')}/{market.get('ma20')}/{market.get('ma60')}")
    for alert in market.get("alerts", []):
        lines.append(f"   {alert}")

    # 择时建议
    signal = market.get("signal", "NEUTRAL")
    if signal == "BUY_ZONE":
        lines.append("\n💡 择时建议：市场深度调整，可考虑分批建仓")
    elif signal == "WATCH":
        lines.append("\n💡 择时建议：回撤达到关注区间，持续观察")
    elif signal == "CRASH":
        lines.append("\n💡 择时建议：市场恐慌，等待企稳信号再进仓")
    else:
        lines.append("\n💡 择时建议：市场平稳，继续观望")

    # Watchlist
    if watchlist_results:
        lines.append("\n━━━ 监控池 ━━━")
        for r in watchlist_results:
            if "error" in r:
                lines.append(f"  {r['name']}({r['ts_code']}): {r['error']}")
                continue
            sig_str = " | ".join(r.get("signals", [])) or "无明显信号"
            lines.append(
                f"  {r['name']}({r['ts_code']}): {r['close']} "
                f"今日{r['today_ret']}%  RSI:{r['rsi14']}  {sig_str}"
            )

    # 超跌候选
    if oversold:
        lines.append("\n━━━ 超跌候选（RSI<35+放量）━━━")
        for c in oversold[:5]:
            lines.append(
                f"  {c['ts_code']}: RSI={c['rsi']}  量比={c['vol_ratio']}x  "
                f"60日回撤={c['drawdown']}%  现价={c['close']}"
            )

    lines.append("\n数据来源：akshare | 仅供参考，不构成投资建议")
    return "\n".join(lines)


# ── 主流程 ──────────────────────────────────────────────

def run():
    conn = get_conn()

    print("分析大盘...")
    market = analyze_market(conn)

    print("分析监控池...")
    wl = load_watchlist(conn)
    watchlist_results = []
    for _, row in wl.iterrows():
        r = analyze_stock(conn, row["ts_code"], row.get("name") or row["ts_code"])
        watchlist_results.append(r)
        print(f"  {row['ts_code']} done")

    print("扫描超跌候选...")
    oversold = scan_oversold(conn, top_n=10)

    report = build_report(market, watchlist_results, oversold)
    print("\n" + report)

    # 保存报告
    report_dir = Path("/home/tulin/quant/reports")
    report_dir.mkdir(exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    report_path = report_dir / f"watchlist_{today}.txt"
    report_path.write_text(report, encoding="utf-8")
    print(f"\n报告已保存: {report_path}")

    conn.close()

    # 飞书推送
    import subprocess, json as _json, datetime as _dt
    feishu_target = "ou_e0fc34f4bfdadf27c59dc8e830ea32ce"
    try:
        result = subprocess.run(
            ["openclaw", "message", "send",
             "-t", feishu_target,
             "--channel", "feishu",
             "-m", report],
            capture_output=True, text=True, timeout=15
        )
        push_ok = result.returncode == 0
        print(f"飞书推送: {'✅ 成功' if push_ok else '❌ 失败 ' + result.stderr[:80]}")
    except Exception as e:
        push_ok = False
        print(f"飞书推送异常: {e}")

    # 写入 task_state
    from pathlib import Path as _Path
    tz = _dt.timezone(_dt.timedelta(hours=8))
    state = {
        "last_run": _dt.datetime.now(tz).isoformat(),
        "status": "success",
        "error": "",
        "report_file": str(report_path),
        "feishu_push": "success" if push_ok else "failed",
        "note": f"watchlist {len(watchlist_results)} 只，超跌候选 {len(oversold)} 只"
    }
    _Path("/home/tulin/quant/control/task_state/watchlist_monitor.json").write_text(
        _json.dumps(state, ensure_ascii=False, indent=2)
    )

    return report


if __name__ == "__main__":
    run()
