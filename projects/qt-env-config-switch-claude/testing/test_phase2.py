"""
Phase 2 集成测试
验证 OMS 订单状态机 + 撤单能力 + DailyMatcher 撮合
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_order_lifecycle():
    print("\n[T1] 订单生命周期")
    from core.oms import OmsEngine, OrderSide, OrderStatus

    oms = OmsEngine()

    # 提交订单
    order = oms.submit_order("Trend", "000001.SZ", OrderSide.BUY,
                              price=10.0, volume=1000, date="2024-01-02")
    assert order.status == OrderStatus.SUBMITTING
    assert order.is_active
    print(f"  提交: {order.order_id} status={order.status.value} ✓")

    # 部分成交
    trade = oms.fill_order(order.order_id, fill_price=10.01, fill_volume=500,
                           fee=1.5, trade_time="2024-01-02")
    assert order.status == OrderStatus.PARTTRADED
    assert order.traded == 500
    assert order.remaining == 500
    print(f"  部分成交: traded={order.traded} remaining={order.remaining} ✓")

    # 全部成交
    oms.fill_order(order.order_id, fill_price=10.01, fill_volume=500,
                   fee=1.5, trade_time="2024-01-02")
    assert order.status == OrderStatus.ALLTRADED
    assert not order.is_active
    assert order.order_id not in [o.order_id for o in oms.get_active_orders()]
    print(f"  全部成交: status={order.status.value} active={order.is_active} ✓")

    print("[T1] PASS")


def test_cancel_order():
    print("\n[T2] 撤单能力")
    from core.oms import OmsEngine, OrderSide, OrderStatus

    oms = OmsEngine()

    # 未成交撤单
    o1 = oms.submit_order("LowVol", "000002.SZ", OrderSide.BUY,
                           price=20.0, volume=500, date="2024-01-02")
    result = oms.cancel_order(o1.order_id, reason="手动撤单")
    assert result is True
    assert o1.status == OrderStatus.CANCELLED
    assert not o1.is_active
    print(f"  未成交撤单: status={o1.status.value} ✓")

    # 部分成交后撤剩余
    o2 = oms.submit_order("Trend", "000003.SZ", OrderSide.BUY,
                           price=15.0, volume=1000, date="2024-01-02")
    oms.fill_order(o2.order_id, 15.01, 300, 1.0, "2024-01-02")
    assert o2.status == OrderStatus.PARTTRADED
    oms.cancel_order(o2.order_id, reason="部分撤单")
    assert o2.status == OrderStatus.CANCELLED
    print(f"  部分成交后撤单: traded={o2.traded} status={o2.status.value} ✓")

    # 批量撤单
    for i in range(3):
        oms.submit_order("Factor", f"00000{i}.SZ", OrderSide.SELL,
                         price=10.0, volume=100, date="2024-01-02")
    n = oms.cancel_all(strategy="Factor")
    assert n == 3
    assert len(oms.get_active_orders("Factor")) == 0
    print(f"  批量撤单: {n} 笔 ✓")

    # 撤已完结订单 → 返回 False
    result2 = oms.cancel_order(o1.order_id)
    assert result2 is False
    print("  撤已完结订单返回 False ✓")

    print("[T2] PASS")


def test_reject_order():
    print("\n[T3] 拒单")
    from core.oms import OmsEngine, OrderSide, OrderStatus

    oms = OmsEngine()
    o = oms.submit_order("Trend", "000001.SZ", OrderSide.BUY,
                          price=10.0, volume=100, date="2024-01-02")
    oms.reject_order(o.order_id, reason="涨停无法买入")
    assert o.status == OrderStatus.REJECTED
    assert o.reject_reason == "涨停无法买入"
    assert not o.is_active
    print(f"  拒单: status={o.status.value} reason={o.reject_reason} ✓")
    print("[T3] PASS")


def test_daily_matcher():
    print("\n[T4] DailyMatcher 撮合")
    from core.oms import OmsEngine, OrderSide, OrderStatus
    from core.matcher import DailyMatcher
    from live.strategy_account import StrategyAccount

    oms = OmsEngine()
    matcher = DailyMatcher(oms, slippage=0.001)

    acc = StrategyAccount("Trend", 1_000_000)
    accounts = {"Trend": acc}

    prices = {
        "000001.SZ": {"close": 10.0, "volume": 5_000_000, "prev_close": 9.5},
        "000002.SZ": {"close": 20.0, "volume": 5_000_000, "prev_close": 19.0},
        # 涨停股
        "000003.SZ": {"close": 11.0, "volume": 1_000_000, "prev_close": 10.0},
    }

    # 正常买入
    o1 = oms.submit_order("Trend", "000001.SZ", OrderSide.BUY,
                           price=10.0, volume=1000, date="2024-01-02",
                           raw_signal={"reason": "trend_signal"})
    # 涨停买入（应被拒）
    o2 = oms.submit_order("Trend", "000003.SZ", OrderSide.BUY,
                           price=11.0, volume=500, date="2024-01-02")

    matcher.match("2024-01-02", prices, accounts)

    assert o1.status == OrderStatus.ALLTRADED
    assert "000001.SZ" in acc.positions
    print(f"  正常买入成交: shares={acc.positions['000001.SZ']['shares']} ✓")

    assert o2.status == OrderStatus.REJECTED
    assert "000003.SZ" not in acc.positions
    print(f"  涨停拒单: status={o2.status.value} reason={o2.reject_reason} ✓")

    # T+1 卖出（当天买当天卖 → 拒）
    o3 = oms.submit_order("Trend", "000001.SZ", OrderSide.SELL,
                           price=10.0, volume=1000, date="2024-01-02")
    matcher.match("2024-01-02", prices, accounts)
    assert o3.status == OrderStatus.REJECTED
    assert o3.reject_reason == "T+1限制"
    print(f"  T+1拒单: status={o3.status.value} ✓")

    # 次日卖出（正常）
    o4 = oms.submit_order("Trend", "000001.SZ", OrderSide.SELL,
                           price=10.0, volume=1000, date="2024-01-03")
    matcher.match("2024-01-03", prices, accounts)
    assert o4.status == OrderStatus.ALLTRADED
    assert "000001.SZ" not in acc.positions
    print(f"  次日卖出成交: status={o4.status.value} ✓")

    # OMS 统计
    stats = oms.get_stats()
    print(f"  OMS stats: {stats}")
    assert stats["total_orders"] == 4
    assert stats["filled_orders"] == 2
    assert stats["rejected_orders"] == 2
    print("[T4] PASS")


def test_oms_callbacks():
    print("\n[T5] OMS 回调 & 事件推送")
    from core.oms import OmsEngine, OrderSide
    from core.event import EventEngine, EVENT_ORDER, EVENT_TRADE

    order_events = []
    trade_events = []

    # 测试回调
    oms = OmsEngine()
    oms.on_order_update = lambda o: order_events.append(o.status.value)
    oms.on_trade = lambda t: trade_events.append(t.trade_id)

    o = oms.submit_order("Trend", "000001.SZ", OrderSide.BUY,
                          price=10.0, volume=100, date="2024-01-02")
    oms.fill_order(o.order_id, 10.01, 100, 0.3, "2024-01-02")

    assert "提交中" in order_events
    assert "全部成交" in order_events
    assert len(trade_events) == 1
    print(f"  回调触发: order_events={order_events} trade_events={len(trade_events)} ✓")

    # 测试 EventEngine 集成
    engine = EventEngine()
    ev_orders = []
    ev_trades = []
    engine.register(EVENT_ORDER, lambda e: ev_orders.append(e.data["status"]))
    engine.register(EVENT_TRADE, lambda e: ev_trades.append(e.data["trade_id"]))

    oms2 = OmsEngine(event_engine=engine)
    o2 = oms2.submit_order("LowVol", "000002.SZ", OrderSide.BUY,
                            price=20.0, volume=200, date="2024-01-02")
    oms2.fill_order(o2.order_id, 20.02, 200, 0.6, "2024-01-02")

    # 手动 drain 事件队列
    q = engine._queue
    while not q.empty():
        ev = q.get_nowait()
        engine._process(ev)

    assert len(ev_orders) >= 2
    assert len(ev_trades) == 1
    print(f"  EventEngine 推送: orders={len(ev_orders)} trades={len(ev_trades)} ✓")
    print("[T5] PASS")


if __name__ == "__main__":
    try:
        test_order_lifecycle()
        test_cancel_order()
        test_reject_order()
        test_daily_matcher()
        test_oms_callbacks()
        print("\n" + "="*50)
        print("  Phase 2 ALL TESTS PASSED ✓")
        print("="*50)
    except Exception as e:
        import traceback
        print(f"\n[FAIL] {e}")
        traceback.print_exc()
        import sys; sys.exit(1)
