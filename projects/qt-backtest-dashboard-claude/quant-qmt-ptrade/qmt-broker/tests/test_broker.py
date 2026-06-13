import pathlib
import sys
import json
import unittest
from unittest import mock
from datetime import date, datetime, timezone, timedelta

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qmt_broker.broker import MarketDataBroker
from qmt_broker.config import BrokerConfig
from qmt_broker.models import StreamRequest, SubscriptionTopic
from qmt_broker.providers.mock import MockMarketDataProvider


class FakeTickCache:
    def __init__(self, recent=None):
        self.recent = recent or {}
        self.appended = []
        self.closed = False

    def get_recent_ticks(self, symbol, limit):  # type: ignore[no-untyped-def]
        records = list(self.recent.get(symbol, []))
        return records[-limit:]

    def append_event(self, symbol, event):  # type: ignore[no-untyped-def]
        self.appended.append((symbol, event))

    def status(self):  # type: ignore[no-untyped-def]
        return {
            "enabled": True,
            "backend": "fake",
            "connected": True,
            "cached_symbols": sorted(self.recent.keys()),
            "last_error": "",
            "ttl_sec": 30,
            "max_records": 8,
            "key_prefix": "test",
        }

    def close(self):  # type: ignore[no-untyped-def]
        self.closed = True


class FakeTickArchive:
    def __init__(self):
        self.appended = []
        self.closed = False
        self.ping_calls = 0
        self.query_calls = []
        self.feature_calls = []
        self.count_calls = []
        self.counts = {}

    def enabled(self):  # type: ignore[no-untyped-def]
        return True

    def ping(self):  # type: ignore[no-untyped-def]
        self.ping_calls += 1
        return True

    def append_event(self, symbol, event):  # type: ignore[no-untyped-def]
        self.appended.append((symbol, event))

    def query_ticks(self, symbol, trade_date="", limit=500):  # type: ignore[no-untyped-def]
        self.query_calls.append((symbol, trade_date, limit))
        return [
            {
                "trade_date": trade_date or "2026-03-18",
                "ts_code": symbol,
                "tick_time_ms": 1773817200000,
                "last_price": 25.76,
                "volume": 96272,
            }
        ]

    def count_ticks(self, symbol, trade_date=""):  # type: ignore[no-untyped-def]
        self.count_calls.append((symbol, trade_date))
        return int(self.counts.get((symbol, trade_date), 0))

    def query_bars(self, symbol, trade_date="", period="1m", limit=240):  # type: ignore[no-untyped-def]
        return [
            {
                "time": "20260318145900",
                "open": 25.71,
                "high": 25.80,
                "low": 25.70,
                "close": 25.76,
                "volume": 96272,
                "amount": 247000000.0,
                "tick_count": 8,
            }
        ][:limit]

    def query_feature_summary(self, symbol, trade_date=""):  # type: ignore[no-untyped-def]
        self.feature_calls.append((symbol, trade_date))
        return {
            "symbol": symbol,
            "trade_date": trade_date or "2026-03-18",
            "tick_count": 12,
            "day_return_pct": 1.9,
            "bar_count_1m": 6,
            "bar_count_5m": 3,
            "bar_count_15m": 1,
        }

    def status(self):  # type: ignore[no-untyped-def]
        return {
            "enabled": True,
            "backend": "fake-postgres",
            "connected": True,
            "schema": "public",
            "table": "intraday_ticks",
            "pending_count": 0,
            "dropped_count": 0,
            "written_count": len(self.appended),
            "last_error": "",
            "batch_size": 200,
            "flush_interval_sec": 1,
        }

    def close(self):  # type: ignore[no-untyped-def]
        self.closed = True


class FakeBarArchive:
    def __init__(self, enabled=True):
        self._enabled = enabled
        self.calls = []
        self.rows = {}

    def enabled(self):  # type: ignore[no-untyped-def]
        return self._enabled

    def upsert_bars(self, symbol, period, rows, *, source="xtquant"):  # type: ignore[no-untyped-def]
        normalized_rows = list(rows)
        self.calls.append(
            {
                "symbol": symbol,
                "period": period,
                "rows": normalized_rows,
                "source": source,
            }
        )
        bucket = self.rows.setdefault((symbol, period), {})
        for row in normalized_rows:
            bar_time = self._parse_time(row.get("time"))
            if bar_time is None:
                continue
            bucket[bar_time.isoformat()] = dict(row)
        return len(self.calls[-1]["rows"])

    def describe_bars(self, symbol, trade_date, period="1m"):  # type: ignore[no-untyped-def]
        start = datetime.strptime(f"{trade_date} 00:00:00+0800", "%Y-%m-%d %H:%M:%S%z")
        end = start + timedelta(days=1)
        return self.describe_bars_window(symbol, period, window_start=start, window_end=end)

    def describe_bars_window(self, symbol, period="1m", *, window_start=None, window_end=None):  # type: ignore[no-untyped-def]
        if window_start is None or window_end is None:
            return {"count": 0, "first_bar_time": None, "last_bar_time": None}
        rows = []
        for row in self.rows.get((symbol, period), {}).values():
            bar_time = self._parse_time(row.get("time"))
            if bar_time is None:
                continue
            if window_start <= bar_time < window_end:
                rows.append(bar_time)
        rows.sort()
        return {
            "count": len(rows),
            "first_bar_time": rows[0] if rows else None,
            "last_bar_time": rows[-1] if rows else None,
        }

    def _parse_time(self, value):  # type: ignore[no-untyped-def]
        if value is None:
            return None
        text = str(value)
        if text.isdigit() and len(text) == 14:
            return datetime.strptime(text, "%Y%m%d%H%M%S").replace(tzinfo=timezone(timedelta(hours=8)))
        if isinstance(value, datetime):
            return value
        return None


class FakeBarBackfillState:
    def __init__(self):
        self.jobs = []
        self.coverage = []

    def enabled(self):  # type: ignore[no-untyped-def]
        return True

    def upsert_job(self, **payload):  # type: ignore[no-untyped-def]
        self.jobs.append(dict(payload))

    def upsert_coverage(self, **payload):  # type: ignore[no-untyped-def]
        self.coverage.append(dict(payload))

    def load_coverage_rows(
        self,
        *,
        symbols,
        trade_date_from,
        trade_date_to,
        period="1m",
        stages=(),
    ):  # type: ignore[no-untyped-def]
        allowed_symbols = {str(symbol or "").strip().upper() for symbol in symbols}
        allowed_stages = {str(stage or "").strip().lower() for stage in stages}
        results = []
        for row in self.coverage:
            row_symbol = str(row.get("symbol") or row.get("ts_code") or "").strip().upper()
            row_stage = str(row.get("stage") or "").strip().lower()
            row_trade_date = row.get("trade_date")
            if isinstance(row_trade_date, str):
                row_trade_date = date.fromisoformat(row_trade_date)
            if row_symbol not in allowed_symbols:
                continue
            if allowed_stages and row_stage not in allowed_stages:
                continue
            if row_trade_date is None or row_trade_date < trade_date_from or row_trade_date > trade_date_to:
                continue
            results.append(
                {
                    "trade_date": row_trade_date,
                    "ts_code": row_symbol,
                    "period": period,
                    "stage": row_stage,
                    "expected_bars": int(row.get("expected_bars", 0)),
                    "actual_bars": int(row.get("actual_bars", 0)),
                    "status": str(row.get("status") or ""),
                }
            )
        return results


def build_minute_rows(trade_date_compact, start_hour, start_minute, count, *, open_price=7.0):  # type: ignore[no-untyped-def]
    rows = []
    minute_cursor = start_hour * 60 + start_minute
    for idx in range(count):
        hour = minute_cursor // 60
        minute = minute_cursor % 60
        rows.append(
            {
                "time": f"{trade_date_compact}{hour:02d}{minute:02d}00",
                "open": open_price,
                "high": open_price + 0.1,
                "low": open_price - 0.1,
                "close": open_price + 0.05,
                "volume": 1000 + idx,
                "amount": 7000.0 + idx,
            }
        )
        minute_cursor += 1
    return rows


class BrokerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.provider = MockMarketDataProvider()
        self.broker = MarketDataBroker(self.provider, BrokerConfig(stream_queue_size=32, heartbeat_interval_sec=1))

    def tearDown(self) -> None:
        self.broker.close()

    def test_quote_snapshot(self) -> None:
        quote = self.broker.get_quote("000001.SZ")
        self.assertEqual(quote["symbol"], "000001.SZ")
        self.assertIn("lastPrice", quote)

    def test_stream_receives_tick_event(self) -> None:
        stream_id, stream_queue = self.broker.open_stream(
            StreamRequest(topics=[SubscriptionTopic(kind="tick", symbol="000001.SZ")], replay=0)
        )
        try:
            message = stream_queue.get(timeout=2.0)
            self.assertEqual(message["type"], "event")
            self.assertEqual(message["event"]["topic"], "tick")
            self.assertEqual(message["event"]["symbol"], "000001.SZ")
        finally:
            self.broker.close_stream(stream_id)

    def test_l2_poll_emits_events(self) -> None:
        stream_id, stream_queue = self.broker.open_stream(
            StreamRequest(topics=[SubscriptionTopic(kind="l2_quote", symbol="000001.SZ")], replay=0)
        )
        try:
            message = stream_queue.get(timeout=2.0)
            self.assertEqual(message["event"]["topic"], "l2_quote")
        finally:
            self.broker.close_stream(stream_id)

    def test_tick_keepalive_status_tracks_manual_symbols(self) -> None:
        self.broker.touch_tick_keepalive("000001.SZ")

        status = self.broker.get_tick_keepalive_status()
        self.assertTrue(status["ok"])
        self.assertEqual(status["symbols"][0]["symbol"], "000001.SZ")
        self.assertTrue(status["symbols"][0]["active"])
        self.assertFalse(status["symbols"][0]["pinned"])

        capabilities = self.broker.capabilities()
        self.assertIn("tick_keepalive", capabilities)
        self.assertIn("tick_archive", capabilities)

    def test_tick_keepalive_logs_successful_subscription(self) -> None:
        with mock.patch("builtins.print") as print_mock:
            self.broker.touch_tick_keepalive("000001.SZ")

        payloads = []
        for args, kwargs in print_mock.call_args_list:
            if not args:
                continue
            payloads.append((json.loads(args[0]), kwargs))

        subscribed = [payload for payload, _kwargs in payloads if payload.get("event") == "tick_keepalive_subscribed"]
        self.assertEqual(len(subscribed), 1)
        self.assertEqual(subscribed[0]["symbol"], "000001.SZ")
        self.assertEqual(subscribed[0]["provider"], "mock")

    def test_tick_prefetch_reuses_stream_history_before_provider_pull(self) -> None:
        payload = {
            "time": 1773812943000,
            "lastPrice": 7.03,
            "volume": 169340,
        }

        def fail_get_ticks(*args, **kwargs):  # type: ignore[no-untyped-def]
            raise AssertionError("provider fallback should not run when tick history is already buffered")

        self.provider.get_ticks = fail_get_ticks  # type: ignore[method-assign]
        self.broker._on_provider_event(SubscriptionTopic(kind="tick", symbol="000001.SZ"), "000001.SZ", payload)

        result = self.broker.get_ticks("000001.SZ", 1, run_prefetch=True, wait_timeout_ms=50, poll_interval_ms=25)
        self.assertEqual(result, [payload])

    def test_tick_response_prefers_cache_before_provider_pull(self) -> None:
        provider = MockMarketDataProvider()
        cache = FakeTickCache(
            recent={
                "000001.SZ": [
                    {
                        "time": 1773812943000,
                        "lastPrice": 7.03,
                        "volume": 169340,
                    }
                ]
            }
        )
        broker = MarketDataBroker(provider, BrokerConfig(stream_queue_size=32, heartbeat_interval_sec=1), tick_cache=cache)
        try:
            def fail_get_ticks(*args, **kwargs):  # type: ignore[no-untyped-def]
                raise AssertionError("provider fallback should not run when cache is warm")

            provider.get_ticks = fail_get_ticks  # type: ignore[method-assign]
            result = broker.get_ticks_response("000001.SZ", 1)
            self.assertEqual(result["source"], "redis")
            self.assertEqual(result["result"][0]["lastPrice"], 7.03)
            self.assertEqual(result["diagnostics"]["source"], "redis")
            self.assertEqual(broker.get_tick_cache_status()["backend"], "fake")
        finally:
            broker.close()

    def test_tick_response_reports_market_closed_empty_reason(self) -> None:
        self.provider.get_ticks = lambda *args, **kwargs: []  # type: ignore[method-assign]
        self.broker._get_market_session_snapshot = lambda: {  # type: ignore[method-assign]
            "market": "CN-A",
            "timezone": "Asia/Shanghai",
            "now_local": "2026-03-18 15:30:00",
            "status": "closed",
            "is_trading": False,
        }
        result = self.broker.get_ticks_response("600196.SH", 20, run_prefetch=True, wait_timeout_ms=50, poll_interval_ms=25)
        self.assertEqual(result["source"], "provider")
        self.assertEqual(result["diagnostics"]["empty_reason"], "market_closed_no_recent_ticks")
        self.assertEqual(result["market_session"]["status"], "closed")

    def test_tick_events_are_written_to_cache(self) -> None:
        provider = MockMarketDataProvider()
        cache = FakeTickCache()
        broker = MarketDataBroker(provider, BrokerConfig(stream_queue_size=32, heartbeat_interval_sec=1), tick_cache=cache)
        try:
            payload = {"time": 1773812943000, "lastPrice": 7.03, "volume": 169340}
            broker._on_provider_event(SubscriptionTopic(kind="tick", symbol="000001.SZ"), "000001.SZ", payload)
            self.assertEqual(cache.appended[0][0], "000001.SZ")
            self.assertEqual(cache.appended[0][1]["payload"]["lastPrice"], 7.03)
        finally:
            broker.close()

    def test_tick_events_are_archived_only_for_source_symbols(self) -> None:
        provider = MockMarketDataProvider()
        cache = FakeTickCache()
        archive = FakeTickArchive()
        broker = MarketDataBroker(
            provider,
            BrokerConfig(stream_queue_size=32, heartbeat_interval_sec=1, tick_archive_backfill_enabled=False),
            tick_cache=cache,
            tick_archive=archive,
        )
        try:
            broker._tick_source_snapshot = broker._tick_source_snapshot.__class__(
                symbols=("000001.SZ",),
                metadata={"source": "postgres"},
                watchlist_symbols=("000001.SZ",),
                position_symbols=(),
            )
            payload = {"time": 1773812943000, "lastPrice": 7.03, "volume": 169340}
            broker._on_provider_event(SubscriptionTopic(kind="tick", symbol="000001.SZ"), "000001.SZ", payload)
            broker._on_provider_event(SubscriptionTopic(kind="tick", symbol="600196.SH"), "600196.SH", payload)
            self.assertEqual(len(archive.appended), 1)
            self.assertEqual(archive.appended[0][0], "000001.SZ")
        finally:
            broker.close()

    def test_bar_events_are_archived_only_for_source_symbols(self) -> None:
        provider = MockMarketDataProvider()
        archive = FakeBarArchive()
        broker = MarketDataBroker(
            provider,
            BrokerConfig(stream_queue_size=32, heartbeat_interval_sec=1, tick_archive_backfill_enabled=False),
            bar_archive=archive,
        )
        try:
            broker._tick_source_snapshot = broker._tick_source_snapshot.__class__(
                symbols=("000001.SZ",),
                metadata={"source": "postgres"},
                watchlist_symbols=("000001.SZ",),
                position_symbols=(),
            )
            broker._on_provider_event(
                SubscriptionTopic(kind="bar", symbol="000001.SZ", period="1m"),
                "000001.SZ",
                {
                    "time": 1773817140000,
                    "open": 7.0,
                    "high": 7.1,
                    "low": 6.9,
                    "close": 7.05,
                    "volume": 1000,
                    "amount": 7000.0,
                },
            )
            broker._on_provider_event(
                SubscriptionTopic(kind="bar", symbol="600196.SH", period="1m"),
                "600196.SH",
                {
                    "time": 1773817140000,
                    "open": 25.7,
                    "high": 25.8,
                    "low": 25.6,
                    "close": 25.76,
                    "volume": 96272,
                    "amount": 247000000.0,
                },
            )
            self.assertEqual(len(archive.calls), 1)
            self.assertEqual(archive.calls[0]["symbol"], "000001.SZ")
            self.assertEqual(archive.calls[0]["period"], "1m")
        finally:
            broker.close()

    def test_bar_keepalive_subscribes_for_source_symbols_when_archive_enabled(self) -> None:
        provider = MockMarketDataProvider()
        archive = FakeBarArchive()
        broker = MarketDataBroker(
            provider,
            BrokerConfig(stream_queue_size=32, heartbeat_interval_sec=1, tick_archive_backfill_enabled=False),
            bar_archive=archive,
        )
        try:
            broker._tick_source_snapshot = broker._tick_source_snapshot.__class__(
                symbols=("000001.SZ",),
                metadata={"source": "postgres"},
                watchlist_symbols=("000001.SZ",),
                position_symbols=(),
            )
            with broker._lock:
                broker._sync_bar_keepalives_locked()
                self.assertIn("000001.SZ", broker._bar_keepalives)
                self.assertTrue(broker._bar_keepalives["000001.SZ"].handle)
        finally:
            broker.close()

    def test_bar_backfill_scheduler_runs_lunch_repair_and_records_state(self) -> None:
        provider = MockMarketDataProvider()
        archive = FakeBarArchive()
        broker = MarketDataBroker(
            provider,
            BrokerConfig(
                stream_queue_size=32,
                heartbeat_interval_sec=1,
                tick_archive_backfill_enabled=False,
                bar_backfill_enabled=False,
                bar_backfill_symbol_timeout_sec=0,
                bar_backfill_symbol_workers=2,
                bar_backfill_provider_max_concurrency=2,
            ),
            bar_archive=archive,
        )
        try:
            broker.config.bar_backfill_enabled = True
            broker._bar_backfill_state = FakeBarBackfillState()
            broker._tick_source_snapshot = broker._tick_source_snapshot.__class__(
                symbols=("000001.SZ",),
                metadata={"source": "postgres"},
                watchlist_symbols=("000001.SZ",),
                position_symbols=(),
            )
            broker._get_market_session_snapshot = lambda: {  # type: ignore[method-assign]
                "market": "CN-A",
                "timezone": "Asia/Shanghai",
                "now_local": "2026-03-20 11:40:00",
                "status": "lunch_break",
                "is_trading": False,
            }
            broker._trade_date_text = lambda: "2026-03-20"  # type: ignore[method-assign]
            fixed_now = datetime(2026, 3, 20, 11, 40, tzinfo=timezone(timedelta(hours=8)))
            rows = build_minute_rows("20260320", 9, 30, 120) + build_minute_rows("20260320", 13, 0, 120, open_price=7.1)

            def fake_backfill(_provider, _config, options):  # type: ignore[no-untyped-def]
                archive.upsert_bars(options.symbols[0], options.period, rows, source="mock")
                return len(rows)

            with mock.patch("qmt_broker.broker.run_bar_backfill", side_effect=fake_backfill):
                with mock.patch("qmt_broker.broker.datetime") as datetime_mock:
                    datetime_mock.now.return_value = fixed_now
                    datetime_mock.strptime.side_effect = datetime.strptime
                    broker._run_bar_backfill_cycle(1773949200000)

            self.assertEqual(broker.get_bar_backfill_status()["symbols"]["000001.SZ"]["status"], "complete")
            self.assertEqual(broker._bar_backfill_state.coverage[-1]["stage"], "lunch_repair")
            self.assertEqual(broker._bar_backfill_state.coverage[-1]["expected_bars"], 120)
            self.assertEqual(broker._bar_backfill_state.coverage[-1]["actual_bars"], 120)
            self.assertEqual(broker._bar_backfill_state.jobs[-1]["status"], "complete")
        finally:
            broker.close()

    def test_bar_backfill_scheduler_runs_nightly_recent_days_for_missing_trade_dates_only(self) -> None:
        provider = MockMarketDataProvider()
        archive = FakeBarArchive()
        broker = MarketDataBroker(
            provider,
            BrokerConfig(
                stream_queue_size=32,
                heartbeat_interval_sec=1,
                tick_archive_backfill_enabled=False,
                bar_backfill_enabled=False,
                bar_backfill_recent_days=3,
                bar_backfill_symbol_timeout_sec=0,
            ),
            bar_archive=archive,
        )
        try:
            broker.config.bar_backfill_enabled = True
            broker._bar_backfill_state = FakeBarBackfillState()
            broker._tick_source_snapshot = broker._tick_source_snapshot.__class__(
                symbols=("000001.SZ",),
                metadata={"source": "postgres"},
                watchlist_symbols=("000001.SZ",),
                position_symbols=(),
            )
            broker._get_market_session_snapshot = lambda: {  # type: ignore[method-assign]
                "market": "CN-A",
                "timezone": "Asia/Shanghai",
                "now_local": "2026-03-20 20:00:00",
                "status": "closed",
                "is_trading": False,
            }
            broker._trade_date_text = lambda: "2026-03-20"  # type: ignore[method-assign]
            broker._bar_backfill_state.coverage.append(
                {
                    "trade_date": date(2026, 3, 20),
                    "symbol": "000001.SZ",
                    "stage": "close_finalize",
                    "status": "complete",
                    "expected_bars": 240,
                    "actual_bars": 240,
                }
            )
            archive.upsert_bars(
                "000001.SZ",
                "1m",
                build_minute_rows("20260319", 9, 30, 120) + build_minute_rows("20260319", 13, 0, 120),
            )
            calls = []

            def fake_backfill(_provider, _config, options):  # type: ignore[no-untyped-def]
                calls.append((options.start_time, options.end_time, options.symbols))
                archive.upsert_bars(
                    "000001.SZ",
                    "1m",
                    build_minute_rows("20260318", 9, 30, 120) + build_minute_rows("20260318", 13, 0, 120),
                )
                return 240

            fixed_now = datetime(2026, 3, 20, 20, 0, tzinfo=timezone(timedelta(hours=8)))
            with mock.patch("qmt_broker.broker.run_bar_backfill", side_effect=fake_backfill):
                with mock.patch("qmt_broker.broker.datetime") as datetime_mock:
                    datetime_mock.now.return_value = fixed_now
                    datetime_mock.strptime.side_effect = datetime.strptime
                    broker._run_bar_backfill_cycle(1774008000000)

            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0][0], "20260318093000")
            self.assertEqual(calls[0][1], "20260318150000")
            self.assertEqual(broker.get_bar_backfill_status()["symbols"]["2026-03-18:000001.SZ"]["status"], "complete")
            self.assertEqual(broker.get_bar_backfill_status()["symbols"]["2026-03-19:000001.SZ"]["written_rows"], 0)
        finally:
            broker.close()

    def test_bar_backfill_scheduler_runs_weekend_gap_scan_for_incomplete_coverage_only(self) -> None:
        provider = MockMarketDataProvider()
        archive = FakeBarArchive()
        broker = MarketDataBroker(
            provider,
            BrokerConfig(
                stream_queue_size=32,
                heartbeat_interval_sec=1,
                tick_archive_backfill_enabled=False,
                bar_backfill_enabled=False,
                bar_backfill_weekend_lookback_days=10,
                bar_backfill_weekend_max_trade_days=2,
                bar_backfill_symbol_timeout_sec=0,
            ),
            bar_archive=archive,
        )
        try:
            broker.config.bar_backfill_enabled = True
            broker._bar_backfill_state = FakeBarBackfillState()
            broker._tick_source_snapshot = broker._tick_source_snapshot.__class__(
                symbols=("000001.SZ",),
                metadata={"source": "postgres"},
                watchlist_symbols=("000001.SZ",),
                position_symbols=(),
            )
            broker._get_market_session_snapshot = lambda: {  # type: ignore[method-assign]
                "market": "CN-A",
                "timezone": "Asia/Shanghai",
                "now_local": "2026-03-21 10:00:00",
                "status": "weekend",
                "is_trading": False,
            }
            broker._trade_date_text = lambda: "2026-03-21"  # type: ignore[method-assign]
            broker._bar_backfill_state.coverage.extend(
                [
                    {
                        "trade_date": date(2026, 3, 20),
                        "symbol": "000001.SZ",
                        "stage": "close_finalize",
                        "status": "complete",
                        "expected_bars": 240,
                        "actual_bars": 240,
                    },
                    {
                        "trade_date": date(2026, 3, 19),
                        "symbol": "000001.SZ",
                        "stage": "nightly_recent_days",
                        "status": "partial",
                        "expected_bars": 240,
                        "actual_bars": 80,
                    },
                ]
            )
            calls = []

            def fake_backfill(_provider, _config, options):  # type: ignore[no-untyped-def]
                calls.append(options.start_time[:8])
                return 0

            fixed_now = datetime(2026, 3, 21, 10, 0, tzinfo=timezone(timedelta(hours=8)))
            with mock.patch("qmt_broker.broker.run_bar_backfill", side_effect=fake_backfill):
                with mock.patch("qmt_broker.broker.datetime") as datetime_mock:
                    datetime_mock.now.return_value = fixed_now
                    datetime_mock.strptime.side_effect = datetime.strptime
                    broker._run_bar_backfill_cycle(1774068000000)

            self.assertEqual(calls, ["20260319", "20260318"])
            self.assertEqual(
                broker.get_bar_backfill_status()["symbols"]["2026-03-19:000001.SZ"]["status"],
                "empty",
            )
        finally:
            broker.close()

    def test_run_bar_backfill_plan_once_supports_dry_run(self) -> None:
        provider = MockMarketDataProvider()
        archive = FakeBarArchive()
        broker = MarketDataBroker(
            provider,
            BrokerConfig(
                stream_queue_size=32,
                heartbeat_interval_sec=1,
                tick_archive_backfill_enabled=False,
                bar_backfill_enabled=False,
                bar_backfill_weekend_lookback_days=5,
                bar_backfill_weekend_max_trade_days=2,
            ),
            bar_archive=archive,
        )
        try:
            broker.config.bar_backfill_enabled = True
            broker._bar_backfill_state = FakeBarBackfillState()
            broker._tick_source_snapshot = broker._tick_source_snapshot.__class__(
                symbols=("000001.SZ",),
                metadata={"source": "postgres"},
                watchlist_symbols=("000001.SZ",),
                position_symbols=(),
            )
            result = broker.run_bar_backfill_plan_once(
                "weekend_gap_scan",
                trade_date_text="2026-03-21",
                dry_run=True,
            )
            self.assertTrue(result["dry_run"])
            self.assertEqual(result["stage"], "weekend_gap_scan")
            self.assertGreaterEqual(result["task_count"], 1)
            self.assertEqual(result["tasks"][0]["symbols"], ["000001.SZ"])
            self.assertEqual(len(broker._bar_backfill_state.jobs), 0)
        finally:
            broker.close()

    def test_bar_backfill_scheduler_logs_symbol_progress(self) -> None:
        provider = MockMarketDataProvider()
        archive = FakeBarArchive()
        broker = MarketDataBroker(
            provider,
            BrokerConfig(
                stream_queue_size=32,
                heartbeat_interval_sec=1,
                tick_archive_backfill_enabled=False,
                bar_backfill_enabled=False,
                bar_backfill_symbol_timeout_sec=0,
            ),
            bar_archive=archive,
        )
        try:
            broker.config.bar_backfill_enabled = True
            broker._bar_backfill_state = FakeBarBackfillState()
            broker._tick_source_snapshot = broker._tick_source_snapshot.__class__(
                symbols=("000001.SZ", "000002.SZ"),
                metadata={"source": "postgres"},
                watchlist_symbols=("000001.SZ", "000002.SZ"),
                position_symbols=(),
            )
            fixed_now = datetime(2026, 3, 20, 15, 20, tzinfo=timezone(timedelta(hours=8)))
            rows = build_minute_rows("20260320", 9, 30, 120) + build_minute_rows("20260320", 13, 0, 120, open_price=7.1)

            def fake_backfill(_provider, _config, options):  # type: ignore[no-untyped-def]
                archive.upsert_bars(options.symbols[0], options.period, rows, source="mock")
                return len(rows)

            with mock.patch("qmt_broker.broker.run_bar_backfill", side_effect=fake_backfill):
                with mock.patch("qmt_broker.broker.datetime") as datetime_mock:
                    with mock.patch("builtins.print") as print_mock:
                        datetime_mock.now.return_value = fixed_now
                        datetime_mock.strptime.side_effect = datetime.strptime
                        broker.run_bar_backfill_plan_once(
                            "close_finalize",
                            trade_date_text="2026-03-20",
                            now_ms=1773991200000,
                            dry_run=False,
                        )

            payloads = []
            for args, _kwargs in print_mock.call_args_list:
                if not args:
                    continue
                payloads.append(json.loads(args[0]))
            completed = [
                payload for payload in payloads if payload.get("event") == "bar_backfill_scheduler_symbol_completed"
            ]
            self.assertEqual(len(completed), 2)
            final_progress = next(payload for payload in completed if payload.get("overall_symbol_index") == 2)
            self.assertEqual(final_progress["overall_symbol_count"], 2)
            self.assertEqual(final_progress["overall_progress_pct"], 100.0)
            self.assertIn(final_progress["task_progress_pct"], {50.0, 100.0})
            self.assertIn("overall 2/2", final_progress["progress"])
        finally:
            broker.close()

    def test_tick_archive_is_pinged_on_startup_and_queryable(self) -> None:
        provider = MockMarketDataProvider()
        archive = FakeTickArchive()
        broker = MarketDataBroker(
            provider,
            BrokerConfig(stream_queue_size=32, heartbeat_interval_sec=1, tick_archive_backfill_enabled=False),
            tick_archive=archive,
        )
        try:
            self.assertEqual(archive.ping_calls, 1)
            rows = broker.get_tick_archive_records("600196.SH", "2026-03-18", 20)
            self.assertEqual(rows[0]["ts_code"], "600196.SH")
            self.assertEqual(archive.query_calls[0], ("600196.SH", "2026-03-18", 20))
            bars = broker.get_tick_archive_bars("600196.SH", "2026-03-18", "1m", 20)
            self.assertEqual(bars[0]["close"], 25.76)
            features = broker.get_tick_archive_features("600196.SH", "2026-03-18")
            self.assertEqual(features["tick_count"], 12)
            self.assertEqual(archive.feature_calls[0], ("600196.SH", "2026-03-18"))
        finally:
            broker.close()

    def test_tick_archive_backfill_enqueues_missing_symbols_after_close(self) -> None:
        provider = MockMarketDataProvider()
        archive = FakeTickArchive()
        broker = MarketDataBroker(
            provider,
            BrokerConfig(
                stream_queue_size=32,
                heartbeat_interval_sec=1,
                tick_archive_backfill_enabled=False,
                tick_archive_backfill_poll_sec=60,
                tick_archive_backfill_retry_sec=300,
            ),
            tick_archive=archive,
        )
        try:
            broker.config.tick_archive_backfill_enabled = True
            broker._tick_source_snapshot = broker._tick_source_snapshot.__class__(
                symbols=("600196.SH",),
                metadata={"source": "postgres"},
                watchlist_symbols=("600196.SH",),
                position_symbols=(),
            )
            broker._get_market_session_snapshot = lambda: {  # type: ignore[method-assign]
                "market": "CN-A",
                "timezone": "Asia/Shanghai",
                "now_local": "2026-03-18 15:10:00",
                "status": "closed",
                "is_trading": False,
            }
            broker._trade_date_text = lambda: "2026-03-18"  # type: ignore[method-assign]
            provider.backfill_ticks = lambda symbol, start_time="", end_time="": [  # type: ignore[method-assign]
                {
                    "time": 1773817140000,
                    "lastPrice": 25.76,
                    "volume": 96272,
                    "amount": 247000000.0,
                }
            ]
            broker._run_tick_archive_backfill_cycle(1773825000000)
            self.assertEqual(archive.count_calls[0], ("600196.SH", "2026-03-18"))
            self.assertEqual(len(archive.appended), 1)
            self.assertEqual(archive.appended[0][0], "600196.SH")
            self.assertEqual(broker.get_tick_archive_status()["backfill"]["symbols"]["600196.SH"]["status"], "replayed")
        finally:
            broker.close()

    def test_tick_archive_backfill_replays_full_day_when_rows_already_exist(self) -> None:
        provider = MockMarketDataProvider()
        archive = FakeTickArchive()
        archive.counts[("600196.SH", "2026-03-18")] = 18
        broker = MarketDataBroker(
            provider,
            BrokerConfig(stream_queue_size=32, heartbeat_interval_sec=1, tick_archive_backfill_enabled=False),
            tick_archive=archive,
        )
        try:
            broker.config.tick_archive_backfill_enabled = True
            broker._tick_source_snapshot = broker._tick_source_snapshot.__class__(
                symbols=("600196.SH",),
                metadata={"source": "postgres"},
                watchlist_symbols=("600196.SH",),
                position_symbols=(),
            )
            broker._get_market_session_snapshot = lambda: {  # type: ignore[method-assign]
                "market": "CN-A",
                "timezone": "Asia/Shanghai",
                "now_local": "2026-03-18 15:10:00",
                "status": "closed",
                "is_trading": False,
            }
            broker._trade_date_text = lambda: "2026-03-18"  # type: ignore[method-assign]
            provider.backfill_ticks = lambda symbol, start_time="", end_time="": [  # type: ignore[method-assign]
                {
                    "time": 1773817140000,
                    "lastPrice": 25.76,
                    "volume": 96272,
                    "amount": 247000000.0,
                }
            ]
            broker._run_tick_archive_backfill_cycle(1773825000000)
            self.assertEqual(archive.count_calls[0], ("600196.SH", "2026-03-18"))
            self.assertEqual(len(archive.appended), 1)
            self.assertEqual(
                broker.get_tick_archive_status()["backfill"]["symbols"]["600196.SH"]["status"],
                "replayed",
            )
            self.assertEqual(
                broker.get_tick_archive_status()["backfill"]["symbols"]["600196.SH"]["existing_count"],
                18,
            )
        finally:
            broker.close()

    def test_tick_archive_backfill_skips_second_replay_after_success_in_same_process(self) -> None:
        provider = MockMarketDataProvider()
        archive = FakeTickArchive()
        broker = MarketDataBroker(
            provider,
            BrokerConfig(stream_queue_size=32, heartbeat_interval_sec=1, tick_archive_backfill_enabled=False),
            tick_archive=archive,
        )
        try:
            broker.config.tick_archive_backfill_enabled = True
            broker._tick_source_snapshot = broker._tick_source_snapshot.__class__(
                symbols=("600196.SH",),
                metadata={"source": "postgres"},
                watchlist_symbols=("600196.SH",),
                position_symbols=(),
            )
            broker._get_market_session_snapshot = lambda: {  # type: ignore[method-assign]
                "market": "CN-A",
                "timezone": "Asia/Shanghai",
                "now_local": "2026-03-18 15:10:00",
                "status": "closed",
                "is_trading": False,
            }
            broker._trade_date_text = lambda: "2026-03-18"  # type: ignore[method-assign]
            call_count = {"value": 0}

            def backfill_once(symbol, start_time="", end_time=""):  # type: ignore[no-untyped-def]
                call_count["value"] += 1
                return [
                    {
                        "time": 1773817140000,
                        "lastPrice": 25.76,
                        "volume": 96272,
                        "amount": 247000000.0,
                    }
                ]

            provider.backfill_ticks = backfill_once  # type: ignore[method-assign]
            broker._run_tick_archive_backfill_cycle(1773825000000)
            broker._run_tick_archive_backfill_cycle(1773825060000)
            self.assertEqual(call_count["value"], 1)
            self.assertEqual(
                broker.get_tick_archive_status()["backfill"]["symbols"]["600196.SH"]["status"],
                "already_replayed",
            )
        finally:
            broker.close()

    def test_tick_keepalive_subscription_is_paused_during_backfill(self) -> None:
        provider = MockMarketDataProvider()
        broker = MarketDataBroker(
            provider,
            BrokerConfig(stream_queue_size=32, heartbeat_interval_sec=1, tick_archive_backfill_enabled=False),
        )
        try:
            from qmt_broker.broker import TickKeepaliveState

            with broker._lock:
                broker._tick_keepalives = {
                    "000001.SZ": TickKeepaliveState(symbol="000001.SZ", pinned=True),
                }
                broker._tick_keepalive_pause_reason = "tick_archive_backfill"
                broker._sync_tick_keepalives_locked(1773825000000)
                self.assertEqual(broker._tick_keepalives["000001.SZ"].handle, "")
                broker._tick_keepalive_pause_reason = ""
                broker._sync_tick_keepalives_locked(1773825000000)
                self.assertTrue(broker._tick_keepalives["000001.SZ"].handle)
        finally:
            broker.close()


if __name__ == "__main__":
    unittest.main()
