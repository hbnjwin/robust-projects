import pathlib
import sys
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qmt_broker.bar_backfill import BarBackfillOptions, run_bar_backfill
from qmt_broker.config import BrokerConfig


class FakeProvider:
    def __init__(self) -> None:
        self.prefetch_calls = []
        self.prefetch_batch_calls = []
        self.bar_calls = []

    def name(self) -> str:
        return "fake"

    def prefetch_history(self, symbol, period, start_time="", end_time="", wait_timeout_ms=0, poll_interval_ms=250):  # type: ignore[no-untyped-def]
        self.prefetch_calls.append(
            {
                "symbol": symbol,
                "period": period,
                "start_time": start_time,
                "end_time": end_time,
                "wait_timeout_ms": wait_timeout_ms,
                "poll_interval_ms": poll_interval_ms,
            }
        )
        return {"ok": True, "cache_ready": True}

    def prefetch_history_batch(self, symbols, period, start_time="", end_time="", wait_timeout_ms=0, poll_interval_ms=250):  # type: ignore[no-untyped-def]
        self.prefetch_batch_calls.append(
            {
                "symbols": tuple(symbols),
                "period": period,
                "start_time": start_time,
                "end_time": end_time,
                "wait_timeout_ms": wait_timeout_ms,
                "poll_interval_ms": poll_interval_ms,
            }
        )
        return {"ok": True, "ok_count": len(tuple(symbols)), "cache_ready_count": 0}

    def get_bars(self, symbol, period, limit, start_time="", end_time=""):  # type: ignore[no-untyped-def]
        self.bar_calls.append(
            {
                "symbol": symbol,
                "period": period,
                "limit": limit,
                "start_time": start_time,
                "end_time": end_time,
            }
        )
        return [
            {
                "time": "20260319093100",
                "open": 10.1,
                "high": 10.2,
                "low": 10.0,
                "close": 10.15,
                "volume": 1200,
                "amount": 12180.0,
            }
        ]

    def close(self) -> None:
        return None


class FakeBarArchive:
    def __init__(self, dsn, schema="public", table="intraday_bars_1m") -> None:  # type: ignore[no-untyped-def]
        self.dsn = dsn
        self.schema = schema
        self.table = table
        self.calls = []

    def enabled(self):  # type: ignore[no-untyped-def]
        return True

    def upsert_bars(self, symbol, period, rows, *, source="xtquant"):  # type: ignore[no-untyped-def]
        materialized = list(rows)
        self.calls.append(
            {
                "symbol": symbol,
                "period": period,
                "rows": materialized,
                "source": source,
            }
        )
        return len(materialized)


class BarBackfillTest(unittest.TestCase):
    def test_run_bar_backfill_prefetches_and_archives_explicit_symbols(self) -> None:
        provider = FakeProvider()
        config = BrokerConfig(bar_archive_pg_dsn="postgresql://example", watchlist_pg_dsn="")
        archive = FakeBarArchive("postgresql://example")
        options = BarBackfillOptions(
            trade_date="2026-03-19",
            symbols=("000001.SZ", "600000.SH"),
            archive_dsn="postgresql://example",
        )
        with mock.patch("qmt_broker.bar_backfill.PostgresBarArchive", return_value=archive):
            written_rows = run_bar_backfill(provider, config, options)
        self.assertEqual(written_rows, 2)
        self.assertEqual(len(provider.prefetch_batch_calls), 1)
        self.assertEqual(provider.prefetch_batch_calls[0]["symbols"], ("000001.SZ", "600000.SH"))
        self.assertEqual(provider.bar_calls[0]["limit"], -1)
        self.assertEqual(provider.bar_calls[0]["start_time"], "20260319093000")
        self.assertEqual(provider.bar_calls[0]["end_time"], "20260319150000")
        self.assertEqual(len(archive.calls), 2)
        self.assertEqual(archive.calls[0]["symbol"], "000001.SZ")
        self.assertEqual(archive.calls[0]["source"], "fake")

    def test_run_bar_backfill_logs_empty_symbols(self) -> None:
        class EmptyProvider(FakeProvider):
            def get_bars(self, symbol, period, limit, start_time="", end_time=""):  # type: ignore[no-untyped-def]
                self.bar_calls.append(
                    {
                        "symbol": symbol,
                        "period": period,
                        "limit": limit,
                        "start_time": start_time,
                        "end_time": end_time,
                    }
                )
                return []

        provider = EmptyProvider()
        config = BrokerConfig(bar_archive_pg_dsn="postgresql://example", watchlist_pg_dsn="")
        archive = FakeBarArchive("postgresql://example")
        options = BarBackfillOptions(
            trade_date="2026-03-19",
            symbols=("000001.SZ",),
            archive_dsn="postgresql://example",
        )
        with mock.patch("qmt_broker.bar_backfill.PostgresBarArchive", return_value=archive):
            with mock.patch("qmt_broker.bar_backfill._emit_bar_backfill_log") as emit_log:
                written_rows = run_bar_backfill(provider, config, options)
        self.assertEqual(written_rows, 0)
        self.assertEqual(len(archive.calls), 0)
        events = [call.args[0] for call in emit_log.call_args_list]
        self.assertIn("bar_backfill_empty", events)
        self.assertIn("bar_backfill_prefetch_batch", events)

    def test_run_bar_backfill_retries_provider_fetch(self) -> None:
        class RetryProvider(FakeProvider):
            def __init__(self) -> None:
                super().__init__()
                self._attempt = 0

            def get_bars(self, symbol, period, limit, start_time="", end_time=""):  # type: ignore[no-untyped-def]
                self.bar_calls.append(
                    {
                        "symbol": symbol,
                        "period": period,
                        "limit": limit,
                        "start_time": start_time,
                        "end_time": end_time,
                    }
                )
                self._attempt += 1
                if self._attempt == 1:
                    return []
                return [
                    {
                        "time": "20260319093100",
                        "open": 10.1,
                        "high": 10.2,
                        "low": 10.0,
                        "close": 10.15,
                        "volume": 1200,
                        "amount": 12180.0,
                    }
                ]

        provider = RetryProvider()
        config = BrokerConfig(bar_archive_pg_dsn="postgresql://example", watchlist_pg_dsn="")
        archive = FakeBarArchive("postgresql://example")
        options = BarBackfillOptions(
            trade_date="2026-03-19",
            symbols=("000001.SZ",),
            archive_dsn="postgresql://example",
            poll_interval_ms=1,
            fetch_retry_count=2,
            batch_fetch_rounds=0,
        )
        with mock.patch("qmt_broker.bar_backfill.PostgresBarArchive", return_value=archive):
            with mock.patch("qmt_broker.bar_backfill.time.sleep"):
                written_rows = run_bar_backfill(provider, config, options)
        self.assertEqual(written_rows, 1)
        self.assertEqual(len(provider.bar_calls), 2)
        self.assertEqual(len(archive.calls), 1)

    def test_run_bar_backfill_uses_batch_warmup_before_direct_fetch(self) -> None:
        class WarmProvider(FakeProvider):
            def __init__(self) -> None:
                super().__init__()
                self._calls = {}

            def get_bars(self, symbol, period, limit, start_time="", end_time=""):  # type: ignore[no-untyped-def]
                self.bar_calls.append(
                    {
                        "symbol": symbol,
                        "period": period,
                        "limit": limit,
                        "start_time": start_time,
                        "end_time": end_time,
                    }
                )
                count = self._calls.get(symbol, 0) + 1
                self._calls[symbol] = count
                if symbol == "000001.SZ" and count == 1:
                    return []
                return [
                    {
                        "time": "20260319093100",
                        "open": 10.1,
                        "high": 10.2,
                        "low": 10.0,
                        "close": 10.15,
                        "volume": 1200,
                        "amount": 12180.0,
                    }
                ]

        provider = WarmProvider()
        config = BrokerConfig(bar_archive_pg_dsn="postgresql://example", watchlist_pg_dsn="")
        archive = FakeBarArchive("postgresql://example")
        options = BarBackfillOptions(
            trade_date="2026-03-19",
            symbols=("000001.SZ", "600000.SH"),
            archive_dsn="postgresql://example",
            batch_fetch_rounds=2,
            fetch_retry_count=0,
            poll_interval_ms=1,
        )
        with mock.patch("qmt_broker.bar_backfill.PostgresBarArchive", return_value=archive):
            with mock.patch("qmt_broker.bar_backfill.time.sleep"):
                written_rows = run_bar_backfill(provider, config, options)
        self.assertEqual(written_rows, 2)
        self.assertEqual(len(archive.calls), 2)
        self.assertGreaterEqual(len(provider.prefetch_batch_calls), 2)

    def test_run_bar_backfill_skips_prefetch_for_same_day_live_session(self) -> None:
        provider = FakeProvider()
        config = BrokerConfig(bar_archive_pg_dsn="postgresql://example", watchlist_pg_dsn="")
        archive = FakeBarArchive("postgresql://example")
        options = BarBackfillOptions(
            trade_date="2026-03-20",
            symbols=("000001.SZ", "600000.SH"),
            archive_dsn="postgresql://example",
        )
        market_session = {
            "market": "CN-A",
            "timezone": "Asia/Shanghai",
            "now_local": "2026-03-20 10:32:00",
            "status": "trading",
            "is_trading": True,
        }
        with mock.patch("qmt_broker.bar_backfill.PostgresBarArchive", return_value=archive):
            with mock.patch("qmt_broker.bar_backfill._get_market_session_snapshot", return_value=market_session):
                with mock.patch("qmt_broker.bar_backfill._emit_bar_backfill_log") as emit_log:
                    written_rows = run_bar_backfill(provider, config, options)
        self.assertEqual(written_rows, 2)
        self.assertEqual(len(provider.prefetch_batch_calls), 0)
        events = [call.args[0] for call in emit_log.call_args_list]
        self.assertIn("bar_backfill_prefetch_skipped", events)

    def test_run_bar_backfill_uses_single_symbol_prefetch_for_same_day_live_session(self) -> None:
        provider = FakeProvider()
        config = BrokerConfig(bar_archive_pg_dsn="postgresql://example", watchlist_pg_dsn="")
        archive = FakeBarArchive("postgresql://example")
        options = BarBackfillOptions(
            trade_date="2026-03-20",
            symbols=("000001.SZ",),
            archive_dsn="postgresql://example",
        )
        market_session = {
            "market": "CN-A",
            "timezone": "Asia/Shanghai",
            "now_local": "2026-03-20 10:32:00",
            "status": "trading",
            "is_trading": True,
        }
        with mock.patch("qmt_broker.bar_backfill.PostgresBarArchive", return_value=archive):
            with mock.patch("qmt_broker.bar_backfill._get_market_session_snapshot", return_value=market_session):
                with mock.patch("qmt_broker.bar_backfill._emit_bar_backfill_log") as emit_log:
                    written_rows = run_bar_backfill(provider, config, options)
        self.assertEqual(written_rows, 1)
        self.assertEqual(len(provider.prefetch_calls), 1)
        self.assertEqual(len(provider.prefetch_batch_calls), 0)
        events = [call.args[0] for call in emit_log.call_args_list]
        self.assertIn("bar_backfill_prefetch_single_started", events)
        self.assertIn("bar_backfill_prefetch_single", events)

    def test_run_bar_backfill_keeps_prefetch_for_prior_trade_date_during_live_session(self) -> None:
        provider = FakeProvider()
        config = BrokerConfig(bar_archive_pg_dsn="postgresql://example", watchlist_pg_dsn="")
        archive = FakeBarArchive("postgresql://example")
        options = BarBackfillOptions(
            trade_date="2026-03-19",
            symbols=("000001.SZ", "600000.SH"),
            archive_dsn="postgresql://example",
        )
        market_session = {
            "market": "CN-A",
            "timezone": "Asia/Shanghai",
            "now_local": "2026-03-20 10:32:00",
            "status": "trading",
            "is_trading": True,
        }
        with mock.patch("qmt_broker.bar_backfill.PostgresBarArchive", return_value=archive):
            with mock.patch("qmt_broker.bar_backfill._get_market_session_snapshot", return_value=market_session):
                written_rows = run_bar_backfill(provider, config, options)
        self.assertEqual(written_rows, 2)
        self.assertEqual(len(provider.prefetch_batch_calls), 1)


if __name__ == "__main__":
    unittest.main()
