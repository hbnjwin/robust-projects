"""
Phase 5 集成测试
验证: BaseGateway / PaperGateway / LiveEngine
"""
import sys
import numpy as np
import pandas as pd
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def make_prices(n_stocks=10, seed=42):
    np.random.seed(seed)
    codes = [f"{i:06d}.SZ" for i in range(n_stocks)]
    prices = {}
    for code in codes:
        p = 10.0 + np.random.uniform(0, 20)
        prices[code] = {
            "close":      round(p, 2),
            "volume":     int(np.random.uniform(1e6, 5e6)),
            "prev_close": round(p * 0.99, 2),
        }
    return prices


def make_market_data(n_days=60, n_stocks=10):
    from datetime import datetime, timedelta
    np.random.seed(0)
    data = {}
    base = {f"{i:06d}.SZ": 10.0 + i for i in range(n_stocks)}
    dt = datetime(2024, 1, 1)
    for d in range(n_days):
        date = (dt + timedelta(days=d)).strftime("%Y-%m-%d")
        day = {}
        for code, price in base.items():
            prev = price
            close = round(max(prev * (1 + np.random.normal(0, 0.01)), 0.1), 2)
            day[code] = {"close": close, "volume": int(np.random.uniform(1e6, 5e6)), "prev_close": prev}
            base[code] = close
        data[date] = day
    return data


def test_base_gateway_interface():
    print("\n[T1] BaseGateway 接口约定")
    from core.gateway import BaseGateway
    import inspect
    abstract = {
        name for name, method in inspect.getmembers(BaseGateway, predicate=inspect.isfunction)
        if getattr(method, "__isabstractmethod__", False)
    }
    required = {"connect", "disconnect", "subscribe", "send_order", "cancel_order",
                "query_account", "query_positions"}
    assert required.issubset(abstract), f"缺少抽象方法: {required - abstract}"
    print(f"  抽象方法完整: {sorted(abstract)} ✓")
    print("[T1] PASS")


def test_paper_gateway_lifecycle():
    print("\n[T2] PaperGateway 生命周期")
    from live.paper_gateway import PaperGateway

    gw = PaperGateway(initial_cash=500_000, state_path="/tmp/test_paper_state.json")

    # 连接
    assert gw.connect() is True
    assert gw.connected is True
    print("  connect ✓")

    # 订阅
    gw.subscribe(["000001.SZ", "000002.SZ"])
    assert "000001.SZ" in gw._subscribed
    print("  subscribe ✓")

    # 查询账户
    acc = gw.query_account()
    assert acc["available"] == 500_000
    assert acc["balance"] == 500_000
    print(f"  query_account: {acc} ✓")

    # 查询持仓（初始为空）
    pos = gw.query_positions()
    assert isinstance(pos, dict)
    print(f"  query_positions: {len(pos)} 持仓 ✓")

    # 断开
    gw.disconnect()
    assert gw.connected is False
    print("  disconnect ✓")

    print("[T2] PASS")


def test_paper_gateway_order_and_match():
    print("\n[T3] PaperGateway 下单 & 收盘撮合")
    from live.paper_gateway import PaperGateway
    from core.oms import OrderSide, OrderStatus

    gw = PaperGateway(initial_cash=1_000_000, state_path="/tmp/test_paper_state2.json")
    gw.connect()

    prices = make_prices(10)
    date = "2024-01-02"

    # 下买单
    order = gw.place_order(
        strategy="Trend",
        ts_code="000001.SZ",
        side=OrderSide.BUY,
        price=prices["000001.SZ"]["close"],
        volume=1000,
        date=date,
    )
    assert order.status == OrderStatus.NOTTRADED
    print(f"  下单: {order.order_id} status={order.status.value} ✓")

    # 收盘撮合
    summary = gw.on_daily_close(date, prices)
    assert "total_equity" in summary
    assert "000001.SZ" in gw._account.positions
    shares = gw._account.positions["000001.SZ"]["shares"]
    assert shares % 100 == 0
    print(f"  收盘撮合: 持仓 {shares} 股, equity={summary['total_equity']:,.0f} ✓")

    # 撤单测试
    order2 = gw.place_order(
        strategy="Trend",
        ts_code="000002.SZ",
        side=OrderSide.BUY,
        price=prices["000002.SZ"]["close"],
        volume=500,
        date=date,
    )
    result = gw.cancel_order(order2.order_id)
    assert result is True
    assert order2.status == OrderStatus.CANCELLED
    print(f"  撤单: status={order2.status.value} ✓")

    gw.disconnect()
    print("[T3] PASS")


def test_paper_gateway_state_persistence():
    print("\n[T4] PaperGateway 状态持久化")
    import os
    from live.paper_gateway import PaperGateway
    from core.oms import OrderSide

    state_path = "/tmp/test_paper_persist.json"
    if os.path.exists(state_path):
        os.remove(state_path)

    # 第一次：下单撮合
    gw1 = PaperGateway(initial_cash=1_000_000, state_path=state_path)
    gw1.connect()
    prices = make_prices(5)
    gw1.place_order("Trend", "000001.SZ", OrderSide.BUY,
                    prices["000001.SZ"]["close"], 1000, "2024-01-02")
    gw1.on_daily_close("2024-01-02", prices)
    cash_after = gw1._account.cash
    gw1.disconnect()

    # 第二次：加载状态
    gw2 = PaperGateway(initial_cash=1_000_000, state_path=state_path)
    gw2.connect()
    assert abs(gw2._account.cash - cash_after) < 1.0
    assert "000001.SZ" in gw2._account.positions
    print(f"  状态恢复: cash={gw2._account.cash:,.0f} pos={list(gw2._account.positions.keys())} ✓")
    gw2.disconnect()

    print("[T4] PASS")


def test_live_engine_smoke():
    print("\n[T5] LiveEngine smoke test")
    from live.paper_gateway import PaperGateway
    from live.live_engine import LiveEngine

    market_data = make_market_data(n_days=60, n_stocks=10)
    all_dates = sorted(market_data.keys())

    gw = PaperGateway(initial_cash=1_000_000, state_path="/tmp/test_live_engine.json")
    engine = LiveEngine(gateway=gw, initial_capital=1_000_000, ml_signals={})

    # 预热
    warmup_data = {d: market_data[d] for d in all_dates[:40]}
    engine.warmup(warmup_data)
    assert engine._warmup_done is True
    print("  预热完成 ✓")

    # 启动
    engine.start()
    assert engine._started is True
    print("  start ✓")

    # 跑 5 天
    sim_dates = all_dates[40:45]
    for date in sim_dates:
        summary = engine.on_market_close(date, market_data[date])
        assert "total_equity" in summary

    curve = engine.master.equity_curve
    assert len(curve) == 5
    print(f"  5天回放: equity_curve={len(curve)} days, final={curve[-1]['equity']:,.0f} ✓")

    # 信号预览
    signals = engine.get_signals_for_today(all_dates[45], market_data[all_dates[45]])
    assert set(signals.keys()) == {"Trend", "LowVol", "Factor"}
    print(f"  信号预览: {sum(len(v) for v in signals.values())} 条信号 ✓")

    engine.stop()
    print("[T5] PASS")


def test_qmt_gateway_stub():
    print("\n[T6] QmtGateway 存根（接口验证）")
    from core.gateway import BaseGateway

    class QmtGatewayStub(BaseGateway):
        """招商 QMT Gateway 存根，验证接口完整性"""
        def connect(self, setting=None): self._connected = True; return True
        def disconnect(self): self._connected = False
        def subscribe(self, ts_codes): pass
        def send_order(self, order): return order.order_id
        def cancel_order(self, order_id): return True
        def query_account(self): return {"balance": 0, "available": 0, "frozen": 0}
        def query_positions(self): return {}

    gw = QmtGatewayStub("QMT-招商")
    assert gw.connect() is True
    assert gw.connected is True
    gw.disconnect()
    assert gw.connected is False
    print("  QmtGatewayStub 接口完整 ✓")
    print("  切换实盘只需实现 BaseGateway 的 7 个抽象方法 ✓")
    print("[T6] PASS")


if __name__ == "__main__":
    try:
        test_base_gateway_interface()
        test_paper_gateway_lifecycle()
        test_paper_gateway_order_and_match()
        test_paper_gateway_state_persistence()
        test_live_engine_smoke()
        test_qmt_gateway_stub()
        print("\n" + "="*50)
        print("  Phase 5 ALL TESTS PASSED ✓")
        print("="*50)
    except Exception as e:
        import traceback
        print(f"\n[FAIL] {e}")
        traceback.print_exc()
        sys.exit(1)
