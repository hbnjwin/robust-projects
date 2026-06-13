"""
stock_advisor_fetch.py — 个股综合分析脚本
整合：日线技术指标 + 主力资金流向 + 基本面 + 实时行情
被 stock-advisor skill 调用，也可独立运行

用法：
  python scripts/stock_advisor_fetch.py --code 000802.SZ
  python scripts/stock_advisor_fetch.py --code 000802  # 自动补后缀
"""

import sys
import argparse
import time
from pathlib import Path
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import PG_CONFIG

# ── 工具函数 ──────────────────────────────────────────────


def normalize_code(code: str) -> str:
    """000802 → 000802.SZ，600519 → 600519.SH"""
    if "." in code:
        return code.upper()
    c = code.strip()
    if c.startswith("6"):
        return f"{c}.SH"
    elif c.startswith(("0", "3")):
        return f"{c}.SZ"
    elif c.startswith(("4", "8")):
        return f"{c}.BJ"
    return f"{c}.SZ"


def calc_rsi(close: pd.Series, n: int = 14) -> float:
    if len(close) < n + 1:
        return float("nan")
    delta = close.diff().iloc[-(n + 1) :]
    gain = delta.clip(lower=0).mean()
    loss = (-delta.clip(upper=0)).mean()
    if loss == 0:
        return 100.0
    return round(100 - 100 / (1 + gain / loss), 1)


def calc_macd(close: pd.Series):
    if len(close) < 35:
        return float("nan"), float("nan"), float("nan")
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    hist = macd - signal
    return round(macd.iloc[-1], 4), round(signal.iloc[-1], 4), round(hist.iloc[-1], 4)


def calc_boll(close: pd.Series, n: int = 20):
    if len(close) < n:
        return float("nan"), float("nan"), float("nan")
    mid = close.iloc[-n:].mean()
    std = close.iloc[-n:].std()
    return round(mid + 2 * std, 3), round(mid, 3), round(mid - 2 * std, 3)


def vol_ratio(vol: pd.Series, n: int = 20) -> float:
    if len(vol) < n + 1:
        return float("nan")
    avg = vol.iloc[-(n + 1) : -1].mean()
    return round(vol.iloc[-1] / avg, 2) if avg > 0 else float("nan")


def drawdown_from_high(close: pd.Series, n: int) -> float:
    if len(close) < 2:
        return 0.0
    peak = close.iloc[-n:].max()
    return round((close.iloc[-1] - peak) / peak * 100, 2)


# ── 数据加载 ──────────────────────────────────────────────


def load_price(conn, ts_code: str, days: int = 150) -> pd.DataFrame:
    cutoff = (datetime.today() - timedelta(days=days * 2)).strftime("%Y-%m-%d")
    df = pd.read_sql(
        "SELECT trade_date, open, high, low, close, vol FROM daily_price "
        "WHERE ts_code=%s AND trade_date>=%s ORDER BY trade_date",
        conn,
        params=(ts_code, cutoff),
    )
    return df.tail(days)


def _is_trading_day() -> bool:
    """简单判断今天是否是交易日（非周末）"""
    from datetime import date

    return date.today().weekday() < 5  # 0=周一 4=周五


def _fetch_fund_flow_realtime(ts_code: str) -> pd.DataFrame:
    """实时拉取资金流向（fallback 用）"""
    try:
        import akshare as ak
        from datetime import date

        code6 = ts_code.split(".")[0]
        suffix = ts_code.split(".")[1]
        market = {"SH": "sh", "SZ": "sz", "BJ": "bj"}.get(suffix, "sz")
        df = ak.stock_individual_fund_flow(stock=code6, market=market)
        if df is None or df.empty:
            return pd.DataFrame()
        df = df.rename(
            columns={
                "日期": "trade_date",
                "主力净流入-净额": "main_net",
                "主力净流入-净占比": "main_net_pct",
                "超大单净流入-净额": "super_net",
                "大单净流入-净额": "big_net",
            }
        )
        df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
        return df[["trade_date", "main_net", "main_net_pct", "super_net", "big_net"]].tail(20)
    except Exception as e:
        print(f"  [fallback] 实时资金流向拉取失败: {e}", file=__import__("sys").stderr)
        return pd.DataFrame()


def load_fund_flow(conn, ts_code: str, days: int = 20) -> pd.DataFrame:
    from datetime import date, datetime, timedelta

    with conn.cursor() as cur:
        cur.execute(
            "SELECT trade_date, main_net, main_net_pct, super_net, big_net, updated_at "
            "FROM stock_fund_flow WHERE ts_code=%s ORDER BY trade_date DESC LIMIT %s",
            (ts_code, days),
        )
        rows = cur.fetchall()

    if not rows:
        return _fetch_fund_flow_realtime(ts_code)

    df = pd.DataFrame(rows, columns=["trade_date", "main_net", "main_net_pct", "super_net", "big_net", "updated_at"])
    df = df.sort_values("trade_date")

    # 判断今天数据是否需要 fallback（今天缺失 or updated_at 超过 2 小时）
    today = date.today()
    if _is_trading_day():
        latest_date = df["trade_date"].max()
        latest_updated_at = df["updated_at"].max()
        now = datetime.now()

        need_fallback = latest_date < today
        if not need_fallback and latest_updated_at is not None:
            age = now - pd.Timestamp(latest_updated_at).to_pydatetime().replace(tzinfo=None)
            need_fallback = age > timedelta(hours=2)

        if need_fallback:
            rt_df = _fetch_fund_flow_realtime(ts_code)
            if not rt_df.empty:
                hist = df[df["trade_date"] < today][["trade_date", "main_net", "main_net_pct", "super_net", "big_net"]]
                df = pd.concat([hist, rt_df], ignore_index=True).sort_values("trade_date")
                return df  # 实时数据没有 updated_at，直接返回

    # 保留 updated_at 供外部判断新鲜度
    return df


def load_fundamentals(conn, ts_code: str) -> pd.Series:
    df = pd.read_sql(
        "SELECT * FROM stock_fundamentals_unified WHERE ts_code=%s AND roe IS NOT NULL ORDER BY report_date DESC LIMIT 1",
        conn,
        params=(ts_code,),
    )
    return df.iloc[0] if not df.empty else pd.Series()


def load_stock_info(conn, ts_code: str) -> dict:
    with conn.cursor() as cur:
        cur.execute("SELECT name, category, note, in_position FROM watchlist WHERE ts_code=%s", (ts_code,))
        row = cur.fetchone()
    if row:
        return {"name": row[0], "category": row[1], "note": row[2], "in_position": row[3]}
    return {"name": ts_code, "category": "-", "note": "", "in_position": False}


# ── 实时行情（akshare）──────────────────────────────────


def fetch_realtime(ts_code: str) -> dict:
    try:
        import akshare as ak

        code6 = ts_code.split(".")[0]
        df = ak.stock_individual_info_em(symbol=code6)
        info = dict(zip(df["item"], df["value"]))
        return {
            "industry": info.get("行业", "-"),
            "total_mv": info.get("总市值", "-"),
            "circ_mv": info.get("流通市值", "-"),
            "list_date": info.get("上市时间", "-"),
        }
    except Exception:
        return {}


def fetch_news(ts_code: str, limit: int = 5) -> list:
    try:
        import akshare as ak

        code6 = ts_code.split(".")[0]
        df = ak.stock_news_em(symbol=code6)
        if df is None or df.empty:
            return []
        return df[["datetime", "title"]].head(limit).to_dict("records")
    except Exception:
        return []


# ── 综合分析 ──────────────────────────────────────────────


def analyze(ts_code: str) -> dict:
    ts_code = normalize_code(ts_code)
    conn = psycopg.connect(**PG_CONFIG)

    price_df = load_price(conn, ts_code, 150)
    fund_df = load_fund_flow(conn, ts_code, 20)
    fund_row = load_fundamentals(conn, ts_code)
    info = load_stock_info(conn, ts_code)
    conn.close()

    result = {
        "ts_code": ts_code,
        "name": info.get("name", ts_code),
        "category": info.get("category"),
        "note": info.get("note"),
        "in_position": info.get("in_position"),
        "analysis_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }

    # ── 技术面 ──
    if len(price_df) < 10:
        result["error"] = "日线数据不足"
        return result

    close = price_df["close"]
    vol = price_df["vol"]
    cur_price = round(close.iloc[-1], 3)
    prev_price = close.iloc[-2]
    today_ret = round((cur_price - prev_price) / prev_price * 100, 2)

    result["technical"] = {
        "close": cur_price,
        "today_ret": today_ret,
        "ma5": round(close.iloc[-5:].mean(), 3) if len(close) >= 5 else None,
        "ma10": round(close.iloc[-10:].mean(), 3) if len(close) >= 10 else None,
        "ma20": round(close.iloc[-20:].mean(), 3) if len(close) >= 20 else None,
        "ma60": round(close.iloc[-60:].mean(), 3) if len(close) >= 60 else None,
        "ma120": round(close.iloc[-120:].mean(), 3) if len(close) >= 120 else None,
        "rsi14": calc_rsi(close, 14),
        "macd": calc_macd(close),  # (macd, signal, hist)
        "boll": calc_boll(close, 20),  # (upper, mid, lower)
        "vol_ratio": vol_ratio(vol, 20),
        "drawdown_60d": drawdown_from_high(close, 60),
        "drawdown_120d": drawdown_from_high(close, 120),
        "high_20d": round(price_df["high"].iloc[-20:].max(), 3),
        "low_20d": round(price_df["low"].iloc[-20:].min(), 3),
    }

    # 技术信号
    t = result["technical"]
    signals = []
    rsi = t["rsi14"]
    if rsi < 20:
        signals.append("RSI极度超卖(<20)")
    elif rsi < 30:
        signals.append("RSI超卖(<30)")
    elif rsi > 70:
        signals.append("RSI超买(>70)")

    macd_val, sig_val, hist_val = t["macd"]
    if not np.isnan(hist_val):
        if hist_val > 0:
            signals.append("MACD金叉")
        else:
            signals.append("MACD死叉")

    boll_u, boll_m, boll_l = t["boll"]
    if not np.isnan(boll_l) and cur_price < boll_l:
        signals.append("跌破布林下轨")
    if not np.isnan(boll_u) and cur_price > boll_u:
        signals.append("突破布林上轨")

    ma5, ma20 = t.get("ma5"), t.get("ma20")
    if ma5 and ma20:
        signals.append("MA5>MA20(多头)" if ma5 > ma20 else "MA5<MA20(空头)")

    vr = t["vol_ratio"]
    if not np.isnan(vr):
        if vr >= 2.0:
            signals.append(f"放量{vr}x(异常)")
        elif vr >= 1.5:
            signals.append(f"放量{vr}x")
        elif vr < 0.5:
            signals.append(f"缩量{vr}x")

    t["signals"] = signals

    # 择时判断
    timing = "观望"
    timing_reason = []
    if rsi < 30 and not np.isnan(hist_val) and hist_val < 0:
        timing = "关注"
        timing_reason.append("RSI超卖区间，等待企稳")
    if rsi < 30 and not np.isnan(hist_val) and hist_val > 0:
        timing = "可关注建仓"
        timing_reason.append("RSI超卖+MACD金叉，技术反转信号")
    if t["drawdown_60d"] <= -20:
        timing = "深度调整区，可分批建仓"
        timing_reason.append(f"60日回撤{t['drawdown_60d']}%，历史支撑区域")

    result["timing"] = {"signal": timing, "reasons": timing_reason}

    # ── 资金流向 ──
    if not fund_df.empty:
        latest_fund = fund_df.iloc[-1]
        fund_5d = fund_df.tail(5)
        # 数据新鲜度检查：今天有数据但 updated_at 超过 3 小时
        data_stale = False
        stale_note = ""
        if "updated_at" in fund_df.columns:
            from datetime import datetime as _dt, timedelta as _td, date as _date

            latest_updated = fund_df["updated_at"].max()
            latest_fund_date = fund_df["trade_date"].max()
            today = _date.today()
            if latest_updated is not None and not pd.isna(latest_updated):
                age = _dt.now() - pd.Timestamp(latest_updated).to_pydatetime().replace(tzinfo=None)
                if age > _td(hours=3) and today.weekday() < 5:
                    data_stale = True
                    stale_note = f"  ⚠️ 数据同步于{pd.Timestamp(latest_updated).strftime('%H:%M')}，可能不是最新"
        result["fund_flow"] = {
            "latest_date": str(latest_fund_date),
            "main_net_wan": round(latest_fund["main_net"] / 1e4, 1) if latest_fund["main_net"] else None,
            "main_net_pct": latest_fund["main_net_pct"],
            "super_net_wan": round(latest_fund["super_net"] / 1e4, 1) if latest_fund["super_net"] else None,
            "5d_main_net_wan": round(fund_5d["main_net"].sum() / 1e4, 1) if "main_net" in fund_5d else None,
            "5d_trend": "持续流入"
            if (fund_5d["main_net"] > 0).sum() >= 3
            else "持续流出"
            if (fund_5d["main_net"] < 0).sum() >= 3
            else "震荡",
            "stale_note": stale_note,
        }
    else:
        result["fund_flow"] = None

    # ── 基本面 ──
    if not fund_row.empty:
        result["fundamentals"] = {
            "report_date": str(fund_row.get("report_date", "")),
            "announce_date": str(fund_row.get("announce_date", "") or ""),
            "roe": fund_row.get("roe"),
            "roa": fund_row.get("roa"),
            "gross_margin": fund_row.get("gross_margin"),
            "net_margin": fund_row.get("net_margin"),
            "debt_ratio": fund_row.get("debt_ratio"),
            "revenue_growth": fund_row.get("revenue_growth"),
            "profit_growth": fund_row.get("profit_growth"),
            # 统一口径：COALESCE(eps_basic, eps) / COALESCE(bps_official, bps)
            "eps": fund_row.get("eps"),
            "bps": fund_row.get("bps"),
            "eps_diluted": fund_row.get("eps_diluted"),
            "ocfps": fund_row.get("ocfps"),
            "total_capital": fund_row.get("total_capital"),
            "circulating_capital": fund_row.get("circulating_capital"),
        }
    else:
        result["fundamentals"] = None

    return result


# ── 格式化输出 ──────────────────────────────────────────


def format_report(r: dict) -> str:
    lines = []
    lines.append(f"【股票分析】{r['ts_code']} {r['name']}  {r['analysis_date']}")
    if r.get("note"):
        lines.append(f"备注：{r['note']}")
    if r.get("in_position"):
        lines.append("⚡ 当前已持仓")
    lines.append("")

    t = r.get("technical", {})
    if t:
        lines.append("📊 技术面")
        lines.append(f"  当前价：{t['close']}  今日：{t['today_ret']:+.2f}%")
        lines.append(f"  MA5={t.get('ma5')}  MA20={t.get('ma20')}  MA60={t.get('ma60')}  MA120={t.get('ma120')}")
        lines.append(f"  RSI14={t['rsi14']}  量比={t['vol_ratio']}x")
        macd_v, sig_v, hist_v = t.get("macd", (None, None, None))
        lines.append(f"  MACD={macd_v}  Signal={sig_v}  Hist={hist_v}")
        boll_u, boll_m, boll_l = t.get("boll", (None, None, None))
        lines.append(f"  布林：上={boll_u}  中={boll_m}  下={boll_l}")
        lines.append(f"  60日回撤={t['drawdown_60d']}%  120日回撤={t['drawdown_120d']}%")
        lines.append(f"  近20日高={t['high_20d']}  低={t['low_20d']}")
        if t.get("signals"):
            lines.append(f"  信号：{'  '.join(t['signals'])}")

    ff = r.get("fund_flow")
    if ff:
        lines.append("")
        lines.append("💰 主力资金（最新）")
        stale_tag = ff.get("stale_note", "")
        lines.append(
            f"  {ff['latest_date']}  主力净流入={ff['main_net_wan']:+.1f}万  占比={ff['main_net_pct']:+.1f}%{stale_tag}"
        )
        lines.append(
            f"  超大单={ff['super_net_wan']:+.1f}万  近5日合计={ff['5d_main_net_wan']:+.1f}万  趋势={ff['5d_trend']}"
        )

    fund = r.get("fundamentals")
    if fund:

        def fmt(v, suffix="%", decimals=1):
            return (
                f"{v:.{decimals}f}{suffix}" if v is not None and not (isinstance(v, float) and np.isnan(v)) else "N/A"
            )

        def fmt_cap(v):
            """股本转换为亿股"""
            if v is None or (isinstance(v, float) and np.isnan(v)):
                return "N/A"
            return f"{v / 1e8:.2f}亿股"

        ann = f"  公告日：{fund['announce_date']}" if fund.get("announce_date") else ""
        lines.append("")
        lines.append(f"📋 基本面（{fund['report_date']}）{ann}")
        lines.append(f"  ROE={fmt(fund['roe'])}  净利率={fmt(fund['net_margin'])}  毛利率={fmt(fund['gross_margin'])}")
        lines.append(
            f"  负债率={fmt(fund['debt_ratio'])}  营收增速={fmt(fund['revenue_growth'])}  利润增速={fmt(fund['profit_growth'])}"
        )
        lines.append(
            f"  EPS={fmt(fund['eps'], '元', 2)}  EPS摊薄={fmt(fund['eps_diluted'], '元', 2)}  BPS={fmt(fund['bps'], '元', 2)}  每股现金流={fmt(fund['ocfps'], '元', 2)}"
        )
        lines.append(f"  总股本={fmt_cap(fund['total_capital'])}  流通股本={fmt_cap(fund['circulating_capital'])}")

    timing = r.get("timing", {})
    if timing:
        lines.append("")
        lines.append(f"⏰ 择时判断：{timing['signal']}")
        for reason in timing.get("reasons", []):
            lines.append(f"  · {reason}")

    lines.append("")
    lines.append("⚠️ 仅供参考，不构成投资建议。中长线持仓需关注季报/公告节点。")
    return "\n".join(lines)


# ── 主入口 ──────────────────────────────────────────────


def fetch_and_analyze(ts_code: str) -> str:
    result = analyze(ts_code)
    return format_report(result)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--code", required=True, help="股票代码，如 000802 或 000802.SZ")
    args = parser.parse_args()
    print(fetch_and_analyze(args.code))
