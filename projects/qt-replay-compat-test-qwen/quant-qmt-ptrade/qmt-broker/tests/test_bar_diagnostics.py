import json
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qmt_broker.bar_diagnostics import BarDiagnosticsOptions, run_bar_diagnostics
from qmt_broker.config import BrokerConfig


class FakeProvider:
    def __init__(self) -> None:
        self.prefetch_batch_calls = []

    def name(self) -> str:
        return "fake"

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

    def diagnose_bars(self, symbol, period, limit, start_time="", end_time="", run_prefetch=False, wait_timeout_ms=0, poll_interval_ms=250):  # type: ignore[no-untyped-def]
        if symbol == "000001.SZ":
            return {
                "diagnosis": "market_data_ready",
                "before": {"market": {"ok": True, "record_count": 0}, "market_ex": {"ok": True, "record_count": 0}, "local": {"ok": True, "record_count": 0}},
                "after": {"market": {"ok": True, "record_count": 10}, "market_ex": {"ok": True, "record_count": 0}, "local": {"ok": True, "record_count": 0}},
                "prefetch": {"ok": True, "cache_ready": False},
            }
        if symbol == "000002.SZ":
            return {
                "diagnosis": "market_data_ex_ready",
                "before": {"market": {"ok": True, "record_count": 0}, "market_ex": {"ok": True, "record_count": 0}, "local": {"ok": True, "record_count": 0}},
                "after": {"market": {"ok": True, "record_count": 0}, "market_ex": {"ok": True, "record_count": 8}, "local": {"ok": True, "record_count": 0}},
                "prefetch": {"ok": True, "cache_ready": False},
            }
        return {
            "diagnosis": "prefetch_completed_but_cache_still_unreadable",
            "before": {"market": {"ok": True, "record_count": 0}, "market_ex": {"ok": True, "record_count": 0}, "local": {"ok": True, "record_count": 0}},
            "after": {"market": {"ok": True, "record_count": 0}, "market_ex": {"ok": True, "record_count": 0}, "local": {"ok": True, "record_count": 0}},
            "prefetch": {"ok": True, "cache_ready": False},
        }

    def close(self) -> None:
        return None


class BarDiagnosticsTest(unittest.TestCase):
    def test_run_bar_diagnostics_groups_symbols_and_writes_output(self) -> None:
        provider = FakeProvider()
        config = BrokerConfig(watchlist_pg_dsn="")
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = pathlib.Path(tmpdir) / "diag.json"
            options = BarDiagnosticsOptions(
                trade_date="2026-03-19",
                symbols=("000001.SZ", "000002.SZ", "000003.SZ"),
                output_path=str(output_path),
            )
            result = run_bar_diagnostics(provider, config, options)
            self.assertEqual(result["groups"]["readable"]["count"], 2)
            self.assertEqual(result["groups"]["unreadable"]["count"], 1)
            self.assertEqual(result["groups"]["readable_market"]["symbols"], ["000001.SZ"])
            self.assertEqual(result["groups"]["readable_market_ex"]["symbols"], ["000002.SZ"])
            self.assertEqual(result["groups"]["unreadable"]["symbols"], ["000003.SZ"])
            self.assertTrue(output_path.exists())
            written = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(written["groups"]["readable"]["count"], 2)
            self.assertEqual(len(provider.prefetch_batch_calls), 1)


if __name__ == "__main__":
    unittest.main()
