"""
paper_trading_run.py — Paper Trading 每日运行脚本

用法:
    cd /home/tulin/quant
    source .venv/bin/activate

    # 每日收盘后（15:30 之后）运行:
    python paper_trading_run.py

    # 手动指定日期（补跑历史）:
    python paper_trading_run.py --date 2026-03-15

    # 不推送飞书:
    python paper_trading_run.py --no-notify
"""
import sys
import argparse
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from live.paper_gateway import PaperGateway
from live.live_engine import LiveEngine
from live.data_loader_fast import load_market_data_fast
from services.realtime_quotes import get_realtime_quotes

# ── 配置 ─────────────────────────────────────────────────────
INITIAL_CAPITAL  = 1_000_000
WARMUP_DAYS      = 90
STATE_PATH       = "data/paper_state.json"
FEISHU_NOTIFY    = True


def get_today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def load_ml_signals() -> dict:
    try:
        sig_df = pd.read_parquet("data/ml_signals.parquet")
        signals = {}
        for d, g in sig_df.groupby("trade_date"):
            date_str = str(d)[:10]
            signals[date_str] = dict(zip(g["ts_code"], g["score"]))
        print(f"[paper] ML 信号加载: {len(signals)} 天")
        return signals
    except Exception as e:
        print(f"[paper] ML 信号加载失败，使用空信号: {e}")
        return {}


def get_today_prices(ts_codes: list) -> dict:
    print(f"[paper] 拉取实时行情: {len(ts_codes)} 只...")
    raw = get_realtime_quotes(ts_codes)
    prices = {}
    for ts_code, q in raw.items():
        price     = q.get("price", 0)
        pre_close = q.get("pre_close", 0)
        volume    = q.get("volume", 0)
        if price > 0 and pre_close > 0:
            prices[ts_code] = {
                "close":      price,
                "volume":     volume * 100,
                "prev_close": pre_close,
            }
    print(f"[paper] 有效行情: {len(prices)} 只")
    return prices


def warmup_engine(engine: LiveEngine, today: str) -> None:
    warmup_end   = (datetime.strptime(today, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
    warmup_start = (datetime.strptime(today, "%Y-%m-%d") - timedelta(days=WARMUP_DAYS + 30)).strftime("%Y-%m-%d")
    print(f"[paper] 预热: {warmup_start} ~ {warmup_end}")
    market_data = load_market_data_fast(warmup_start, warmup_end)
    if market_data:
        engine.warmup(market_data)
    else:
        print("[paper] 警告: 预热数据为空")


def format_signals(signals: dict) -> str:
    lines = []
    for strat, sigs in signals.items():
        buys  = [s["ts_code"] for s in sigs if s["action"] == "buy"]
        sells = [s["ts_code"] for s in sigs if s["action"] == "sell"]
        if buys:
            preview = ", ".join(buys[:5]) + ("..." if len(buys) > 5 else "")
            lines.append(f"  {strat} 买入({len(buys)}): {preview}")
        if sells:
            preview = ", ".join(sells[:5]) + ("..." if len(sells) > 5 else "")
            lines.append(f"  {strat} 卖出({len(sells)}): {preview}")
    return "\n".join(lines) if lines else "  无信号"


def format_positions(pos: dict) -> str:
    if not pos:
        return "  无持仓"
    lines = []
    for code, p in sorted(pos.items(), key=lambda x: -x[1]["market_value"])[:15]:
        avg_cost = p["avg_cost"]
        shares   = p["shares"]
        mkt_val  = p["market_value"]
        pnl      = (mkt_val / (avg_cost * shares) - 1) * 100 if avg_cost > 0 and shares > 0 else 0
        lines.append(f"  {code}: {shares}股 成本{avg_cost:.2f} 市值{mkt_val:,.0f} {pnl:+.1f}%")
    if len(pos) > 15:
        lines.append(f"  ... 共 {len(pos)} 只")
    return "\n".join(lines)


def build_report(date: str, summary: dict, signals: dict, gw: PaperGateway) -> str:
    acc = gw.query_account()
    pos = gw.query_positions()
    total_signals = sum(len(v) for v in signals.values())

    report = f"""📊 Paper Trading 日报 {date}

💰 账户状态
  总权益:   {acc['balance']:>12,.0f}
  可用现金: {acc['available']:>12,.0f}
  持仓数:   {len(pos)}
  最大回撤: {summary.get('max_drawdown', 0):.2%}

📈 今日信号 ({total_signals} 条)
{format_signals(signals)}

📋 当前持仓 ({len(pos)} 只)
{format_positions(pos)}"""
    return report


def main():
    parser = argparse.ArgumentParser(description="Paper Trading 每日运行")
    parser.add_argument("--date", type=str, default=None)
    parser.add_argument("--no-notify", action="store_true")
    args = parser.parse_args()

    today  = args.date or get_today()
    notify = FEISHU_NOTIFY and not args.no_notify

    print(f"\n{'='*60}")
    print(f"  Paper Trading — {today}")
    print(f"{'='*60}")

    # 1. 加载 ML 信号
    ml_signals = load_ml_signals()

    # 2. 构建引擎
    gw = PaperGateway(initial_cash=INITIAL_CAPITAL, state_path=STATE_PATH)
    engine = LiveEngine(gateway=gw, initial_capital=INITIAL_CAPITAL, ml_signals=ml_signals)

    # 3. 预热
    warmup_engine(engine, today)

    # 4. 启动
    engine.start()

    # 5. 获取全市场股票列表（从近期历史数据）
    sample = load_market_data_fast(
        (datetime.strptime(today, "%Y-%m-%d") - timedelta(days=5)).strftime("%Y-%m-%d"),
        today,
    )
    all_codes = list({code for prices in sample.values() for code in prices})
    print(f"[paper] 股票池: {len(all_codes)} 只")

    # 6. 拉取今日行情
    today_prices = get_today_prices(all_codes)
    if not today_prices:
        print("[paper] 今日行情为空，可能是非交易日或接口异常，退出")
        engine.stop()
        return

    # 7. 预览信号
    signals = engine.get_signals_for_today(today, today_prices)
    total = sum(len(v) for v in signals.values())
    print(f"\n[paper] 今日信号: {total} 条")
    print(format_signals(signals))

    # 8. 收盘撮合
    summary = engine.on_market_close(today, today_prices)

    # 9. 生成报告
    report = build_report(today, summary, signals, gw)
    print(f"\n{report}")

    # 10. 推送飞书
    if notify:
        try:
            from control.notification_bridge import send_feishu_message
            send_feishu_message(report)
            print("\n[paper] 飞书通知已发送")
        except Exception as e:
            print(f"\n[paper] 飞书通知失败: {e}")

    engine.stop()
    print(f"\n[paper] 完成，状态已保存: {STATE_PATH}")


if __name__ == "__main__":
    main()
