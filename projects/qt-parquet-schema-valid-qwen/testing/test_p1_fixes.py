"""
测试 P1 修复项：
- P1-5: MATrendRiskStrategy "all" 标记
- P1-6: MACrossStrategy 历史长度限制
- P1-7: LowVolStrategy 已有截断（验证）
- P1-8: 回撤控制扣手续费
- P1-9: ReplayEngineV2 index_is_bull dict 查找
- P1-10: 信号生成器日期校验
"""
import sys
import os
sys.path.insert(0, "/home/tulin/quant")


def test_p1_5_sell_all_marker():
    """P1-5: MATrendRiskStrategy 使用 "all" 而非 999999"""
    print("=== P1-5: sell size 'all' 标记 ===")

    from strategies.ma_trend_risk import MATrendRiskStrategy

    strategy = MATrendRiskStrategy(short=2, long=3, trend=5, stop_loss=0.08)

    # 喂入足够数据让趋势线建立
    prices_up = [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]
    for p in prices_up:
        signal = strategy.on_bar({"close": p})

    # 确认已经进场
    assert strategy.entry_price is not None, "FAIL: 策略未进场"
    print(f"  进场价: {strategy.entry_price}")

    # 触发死叉卖出（价格急跌）
    prices_down = [15, 10, 5]
    sell_signal = None
    for p in prices_down:
        signal = strategy.on_bar({"close": p})
        if signal["action"] == "sell":
            sell_signal = signal
            break

    assert sell_signal is not None, "FAIL: 未触发卖出信号"
    assert sell_signal["size"] == "all", f"FAIL: size={sell_signal['size']}，应为 'all'"
    print(f"  卖出信号 size={sell_signal['size']} OK")

    # 检查源码中没有 999999
    with open("/home/tulin/quant/strategies/ma_trend_risk.py") as f:
        content = f.read()
    assert "999999" not in content, "FAIL: 源码中仍有 999999"
    print("  源码无 999999 OK")
    print("  P1-5 测试通过\n")


def test_p1_5_backtest_handles_all():
    """P1-5: engine/backtest.py 正确处理 "all" 标记"""
    print("=== P1-5: backtest 处理 'all' 标记 ===")

    with open("/home/tulin/quant/engine/backtest.py") as f:
        content = f.read()

    assert '"all"' in content, "FAIL: backtest.py 未处理 'all' 标记"
    print("  backtest.py 包含 'all' 处理逻辑 OK")
    print("  P1-5 backtest 测试通过\n")


def test_p1_6_ma_cross_history_limit():
    """P1-6: MACrossStrategy 限制历史长度"""
    print("=== P1-6: MACrossStrategy 历史长度限制 ===")

    from strategies.ma_cross import MACrossStrategy

    strategy = MACrossStrategy(short=5, long=20)

    # 喂入 1000 个数据点
    for i in range(1000):
        strategy.on_bar({"close": 10 + (i % 10) * 0.1})

    max_expected = max(5, 20) + 10  # 30
    actual_len = len(strategy.prices)
    assert actual_len <= max_expected, f"FAIL: 历史长度 {actual_len} > {max_expected}"
    print(f"  喂入 1000 条后，历史长度={actual_len}，上限={max_expected} OK")
    print("  P1-6 测试通过\n")


def test_p1_7_lowvol_truncation():
    """P1-7: LowVolStrategy 已有截断验证"""
    print("=== P1-7: LowVolStrategy 历史截断 ===")

    from live.lowvol_strategy_v2 import LowVolStrategy

    strategy = LowVolStrategy(lookback=20, top_n=3)

    # 喂入大量数据
    for i in range(500):
        prices = {
            f"stock_{j}": {"close": 10 + j + (i % 5) * 0.1}
            for j in range(10)
        }
        strategy.generate(f"2026-01-{i+1:03d}", prices)

    max_expected = 20 * 3  # lookback * 3
    for code, hist in strategy.history.items():
        assert len(hist) <= max_expected, f"FAIL: {code} 历史长度 {len(hist)} > {max_expected}"

    print(f"  所有股票历史长度 <= {max_expected} OK")
    print("  P1-7 测试通过（已有缓解措施）\n")


def test_p1_8_drawdown_fee():
    """P1-8: 回撤控制扣手续费"""
    print("=== P1-8: 回撤控制扣手续费 ===")

    from live.master_portfolio import MasterPortfolio
    from live.strategy_account import StrategyAccount

    portfolio = MasterPortfolio(total_capital=1_000_000)
    account = StrategyAccount("test", 500_000)

    # 模拟持仓
    account.positions["600000.SH"] = {"shares": 10000, "avg_cost": 10.0, "buy_date": "2026-03-01"}
    account.cash = 400_000

    portfolio.add_strategy("test", account)

    # 模拟大回撤 > 25%
    portfolio.max_equity = 1_000_000
    portfolio.total_equity = 700_000
    portfolio.max_drawdown = 0.30

    prices = {"600000.SH": {"close": 10.0}}

    cash_before = account.cash
    portfolio.apply_drawdown_control(prices)

    # 验证手续费被扣除
    sell_price = 10.0 * 0.999  # 滑点
    revenue = 10000 * sell_price
    fee = revenue * 0.0003
    expected_cash = cash_before + revenue - fee

    assert abs(account.cash - expected_cash) < 0.01, \
        f"FAIL: cash={account.cash}, expected={expected_cash}"
    assert len(account.positions) == 0, "FAIL: 持仓未清空"
    print(f"  强平后 cash={account.cash:.2f}, 预期={expected_cash:.2f} OK")
    print("  P1-8 测试通过\n")


def test_p1_8_drawdown_half_fee():
    """P1-8: 减半回撤控制也扣手续费"""
    print("=== P1-8: 减半回撤控制扣手续费 ===")

    from live.master_portfolio import MasterPortfolio
    from live.strategy_account import StrategyAccount

    portfolio = MasterPortfolio(total_capital=1_000_000)
    account = StrategyAccount("test", 500_000)

    account.positions["600000.SH"] = {"shares": 10000, "avg_cost": 10.0, "buy_date": "2026-03-01"}
    account.cash = 400_000

    portfolio.add_strategy("test", account)

    # 模拟中等回撤 15%-25%
    portfolio.max_equity = 1_000_000
    portfolio.total_equity = 800_000
    portfolio.max_drawdown = 0.20

    prices = {"600000.SH": {"close": 10.0}}

    cash_before = account.cash
    portfolio.apply_drawdown_control(prices)

    sell_shares = 10000 // 2  # 5000
    sell_price = 10.0 * 0.999
    revenue = sell_shares * sell_price
    fee = revenue * 0.0003
    expected_cash = cash_before + revenue - fee

    assert abs(account.cash - expected_cash) < 0.01, \
        f"FAIL: cash={account.cash}, expected={expected_cash}"
    assert account.positions["600000.SH"]["shares"] == 5000, "FAIL: 未减半"
    print(f"  减半后 cash={account.cash:.2f}, 预期={expected_cash:.2f} OK")
    print("  P1-8 减半测试通过\n")


def test_p1_9_index_dict_lookup():
    """P1-9: ReplayEngineV2 使用 dict 查找"""
    print("=== P1-9: index_is_bull dict 查找 ===")

    with open("/home/tulin/quant/live/replay_engine_v2.py") as f:
        content = f.read()

    assert "_index_lookup" in content, "FAIL: 未使用 _index_lookup dict"
    assert '.get(' in content, "FAIL: 未使用 dict.get() 查找"

    # 确认没有 DataFrame 过滤
    # index_is_bull 方法中不应有 self.index_df[self.index_df["date"] == date]
    import re
    old_pattern = re.compile(r'self\.index_df\[self\.index_df\["date"\]\s*==\s*date\]')
    assert not old_pattern.search(content), "FAIL: 仍有 DataFrame 全表扫描"

    print("  使用 _index_lookup dict 查找 OK")
    print("  P1-9 测试通过\n")


def test_p1_10_signal_date_validation():
    """P1-10: 信号生成器日期校验"""
    print("=== P1-10: 信号生成器日期校验 ===")

    with open("/home/tulin/quant/services/signal_generator_v1.py") as f:
        content = f.read()

    assert "days_gap" in content or "days_gap" in content, "FAIL: 未添加日期校验"
    assert "过期" in content or "gap" in content.lower(), "FAIL: 未添加过期警告"
    print("  日期校验逻辑已添加 OK")
    print("  P1-10 测试通过\n")


def test_p2_13_notification_bridge_logging():
    """P2-13: 通知桥使用 logging"""
    print("=== P2-13: 通知桥日志 ===")

    with open("/home/tulin/quant/control/notification_bridge.py") as f:
        content = f.read()

    assert "import logging" in content, "FAIL: 未导入 logging"
    assert "logger" in content, "FAIL: 未使用 logger"
    print("  使用 logging 模块 OK")
    print("  P2-13 测试通过\n")


def test_p2_14_signal_server():
    """P2-14: signal_server 读取最新 JSON"""
    print("=== P2-14: signal_server 读取最新文件 ===")

    with open("/home/tulin/quant/live/signal_server.py") as f:
        content = f.read()

    assert "current_signal.json" not in content, "FAIL: 仍读取旧文件"
    assert "logs/signals" in content, "FAIL: 未读取 logs/signals 目录"
    assert "glob" in content or "os.listdir" in content, "FAIL: 未扫描目录"
    print("  读取 logs/signals/ 最新文件 OK")
    print("  P2-14 测试通过\n")


def test_p2_15_logger():
    """P2-15: 统一日志框架"""
    print("=== P2-15: 统一日志框架 ===")

    assert os.path.exists("/home/tulin/quant/utils/logger.py"), "FAIL: logger.py 不存在"

    from utils.logger import get_logger
    logger = get_logger("test")
    assert logger is not None
    assert len(logger.handlers) >= 2, "FAIL: handler 数量不足"
    print("  utils/logger.py 存在且可用 OK")

    # 检查 scheduler_v2 使用了新 logger
    with open("/home/tulin/quant/control/scheduler_v2.py") as f:
        content = f.read()
    assert "from utils.logger import get_logger" in content, "FAIL: scheduler_v2 未使用新 logger"
    print("  scheduler_v2 已集成 OK")
    print("  P2-15 测试通过\n")


if __name__ == "__main__":
    test_p1_5_sell_all_marker()
    test_p1_5_backtest_handles_all()
    test_p1_6_ma_cross_history_limit()
    test_p1_7_lowvol_truncation()
    test_p1_8_drawdown_fee()
    test_p1_8_drawdown_half_fee()
    test_p1_9_index_dict_lookup()
    test_p1_10_signal_date_validation()
    test_p2_13_notification_bridge_logging()
    test_p2_14_signal_server()
    test_p2_15_logger()
    print("=" * 50)
    print("P1 + P2 全部测试通过 ✅")
