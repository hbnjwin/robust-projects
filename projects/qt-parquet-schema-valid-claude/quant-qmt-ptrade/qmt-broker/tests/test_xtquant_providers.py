import json
import pathlib
import subprocess
import sys
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qmt_broker.providers.xtquant_runtime import (
    XtQuantMarketDataProvider,
    _diagnose_bars_outcome,
    _fetch_ticks_via_subprocess,
    _normalize_kline,
    _prefetch_history_via_subprocess,
)
from qmt_broker.providers.xtquant_trader_runtime import XtQuantTradeProvider, _normalize_object


class XtQuantProviderHelpersTest(unittest.TestCase):
    class FakeFrame:
        def __init__(self, index, columns, rows) -> None:
            self.index = index
            self.columns = columns
            self._rows = rows
            self.iloc = self

        def __getitem__(self, key):
            row_index, column_index = key
            return self._rows[row_index][column_index]

    def test_trader_object_normalization_expands_public_and_alias_fields(self) -> None:
        class FakeXtOrder:
            __slots__ = (
                "m_nAccountType",
                "m_strAccountID",
                "m_strStockCode",
                "m_nOrderID",
                "m_strOrderSysID",
                "m_nOrderVolume",
                "m_dPrice",
                "m_nOrderStatus",
            )

            def __init__(self) -> None:
                self.m_nAccountType = 2
                self.m_strAccountID = "39134967"
                self.m_strStockCode = "600000.SH"
                self.m_nOrderID = 12345
                self.m_strOrderSysID = "A0001"
                self.m_nOrderVolume = 100
                self.m_dPrice = 10.5
                self.m_nOrderStatus = 50

        normalized = _normalize_object(FakeXtOrder())
        self.assertEqual(normalized["account_type"], 2)
        self.assertEqual(normalized["account_id"], "39134967")
        self.assertEqual(normalized["stock_code"], "600000.SH")
        self.assertEqual(normalized["order_id"], 12345)
        self.assertEqual(normalized["order_sysid"], "A0001")
        self.assertEqual(normalized["order_volume"], 100)
        self.assertEqual(normalized["price"], 10.5)
        self.assertEqual(normalized["order_status"], 50)

    def test_tick_fetch_uses_subprocess_json_payload(self) -> None:
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(
                [
                    {
                        "time": 1773730800000,
                        "lastPrice": 11.03,
                        "volume": 1076657,
                    }
                ]
            ),
            stderr="",
        )
        with patch("qmt_broker.providers.xtquant_runtime.subprocess.run", return_value=completed) as run_mock:
            result = _fetch_ticks_via_subprocess("000001.SZ", 3, "", "")
        self.assertEqual(result[0]["time"], 1773730800000)
        self.assertEqual(result[0]["lastPrice"], 11.03)
        self.assertEqual(result[0]["volume"], 1076657)
        run_mock.assert_called_once()

    def test_tick_fetch_extracts_trailing_json_from_noisy_stdout(self) -> None:
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout='xtquant warning on stdout\n[{"time":1773730800000,"lastPrice":11.03}]\n',
            stderr="warning redirected to stderr",
        )
        with patch("qmt_broker.providers.xtquant_runtime.subprocess.run", return_value=completed):
            result = _fetch_ticks_via_subprocess("000001.SZ", 3, "", "")
        self.assertEqual(result, [{"time": 1773730800000, "lastPrice": 11.03}])

    def test_tick_fetch_surfaces_subprocess_failure(self) -> None:
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=1,
            stdout="",
            stderr="simulated tick crash",
        )
        with patch("qmt_broker.providers.xtquant_runtime.subprocess.run", return_value=completed):
            with self.assertRaisesRegex(RuntimeError, "simulated tick crash"):
                _fetch_ticks_via_subprocess("000001.SZ", 3, "", "")

    def test_tick_fetch_reports_empty_stdout_with_stderr_detail(self) -> None:
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="",
            stderr="xtquant emitted no payload",
        )
        with patch("qmt_broker.providers.xtquant_runtime.subprocess.run", return_value=completed):
            with self.assertRaisesRegex(RuntimeError, "empty stdout: xtquant emitted no payload"):
                _fetch_ticks_via_subprocess("000001.SZ", 3, "", "")

    def test_kline_normalization_uses_dataframe_columns_when_time_field_missing(self) -> None:
        dataset = {
            "open": self.FakeFrame(
                ["000001.SZ"],
                [1773700200000, 1773700260000],
                [[10.1, 10.2]],
            ),
            "close": self.FakeFrame(
                ["000001.SZ"],
                [1773700200000, 1773700260000],
                [[10.3, 10.4]],
            ),
            "volume": self.FakeFrame(
                ["000001.SZ"],
                [1773700200000, 1773700260000],
                [[1000, 1200]],
            ),
        }

        result = _normalize_kline(dataset, "000001.SZ")
        self.assertEqual(
            result,
            [
                {"time": 1773700200000, "open": 10.1, "close": 10.3, "volume": 1000},
                {"time": 1773700260000, "open": 10.2, "close": 10.4, "volume": 1200},
            ],
        )

    def test_bars_diagnosis_flags_local_cache_ready_but_market_empty(self) -> None:
        diagnosis = _diagnose_bars_outcome(
            before_market={"ok": True, "record_count": 0},
            before_market_ex={"ok": True, "record_count": 0},
            before_local={"ok": True, "record_count": 0},
            after_market={"ok": True, "record_count": 0},
            after_market_ex={"ok": True, "record_count": 0},
            after_local={"ok": True, "record_count": 5},
            prefetch={"ok": True, "cache_ready": True},
        )
        self.assertEqual(diagnosis, "local_cache_ready_but_market_data_empty")

    def test_bars_diagnosis_flags_market_ex_ready_when_primary_market_empty(self) -> None:
        diagnosis = _diagnose_bars_outcome(
            before_market={"ok": True, "record_count": 0},
            before_market_ex={"ok": True, "record_count": 0},
            before_local={"ok": True, "record_count": 0},
            after_market={"ok": True, "record_count": 0},
            after_market_ex={"ok": True, "record_count": 5},
            after_local={"ok": True, "record_count": 0},
            prefetch={"ok": True, "cache_ready": False},
        )
        self.assertEqual(diagnosis, "market_data_ex_ready")

    def test_local_record_reader_supports_stock_list_signature(self) -> None:
        dataset = {
            "open": self.FakeFrame(
                ["000001.SZ"],
                [1773700200000, 1773700260000],
                [[10.1, 10.2]],
            ),
            "close": self.FakeFrame(
                ["000001.SZ"],
                [1773700200000, 1773700260000],
                [[10.3, 10.4]],
            ),
        }

        class FakeXtData:
            def get_local_data(self, field_list=None, stock_list=None, period="1d", start_time="", end_time="", count=-1, fill_data=True):
                return dataset

        provider = object.__new__(XtQuantMarketDataProvider)
        provider._xtdata = FakeXtData()

        result = provider._read_local_records("000001.SZ", "1m", 2)
        self.assertEqual(
            result,
            [
                {"time": 1773700200000, "open": 10.1, "close": 10.3},
                {"time": 1773700260000, "open": 10.2, "close": 10.4},
            ],
        )

    def test_market_record_reader_ex_supports_stock_list_signature(self) -> None:
        class FakeTickFrame:
            def __init__(self) -> None:
                self.index = [1773730800000, 1773730803000]

            def to_dict(self, orient="records"):
                assert orient == "records"
                return [
                    {"lastPrice": 11.03, "volume": 1000},
                    {"lastPrice": 11.05, "volume": 1200},
                ]

        class FakeXtData:
            def get_market_data_ex(
                self,
                field_list=None,
                stock_list=None,
                period="1d",
                start_time="",
                end_time="",
                count=-1,
                dividend_type="none",
                fill_data=True,
                subscribe=False,
            ):
                return {"000001.SZ": FakeTickFrame()}

        provider = object.__new__(XtQuantMarketDataProvider)
        provider._xtdata = FakeXtData()

        result = provider._read_market_records_ex("000001.SZ", "tick", 2)
        self.assertEqual(
            result,
            [
                {"time": 1773730800000, "lastPrice": 11.03, "volume": 1000},
                {"time": 1773730803000, "lastPrice": 11.05, "volume": 1200},
            ],
        )

    def test_prefetch_history_batch_uses_stock_list_signature(self) -> None:
        class FakeXtData:
            def __init__(self) -> None:
                self.calls = []

            def download_history_data(self, stock_list, period="1d", start_time="", end_time=""):
                self.calls.append(
                    {
                        "stock_list": list(stock_list),
                        "period": period,
                        "start_time": start_time,
                        "end_time": end_time,
                    }
                )

        provider = object.__new__(XtQuantMarketDataProvider)
        provider._xtdata = FakeXtData()
        provider._lock = threading.RLock()
        provider._handles = {}

        result = provider.prefetch_history_batch(
            ["000001.SZ", "600000.SH"],
            "1m",
            start_time="20260319093000",
            end_time="20260319150000",
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["symbol_count"], 2)
        self.assertEqual(
            provider._xtdata.calls,
            [
                {
                    "stock_list": ["000001.SZ", "600000.SH"],
                    "period": "1m",
                    "start_time": "20260319093000",
                    "end_time": "20260319150000",
                }
            ],
        )

    def test_prefetch_history_uses_subprocess_payload(self) -> None:
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps({"ok": True, "symbol_count": 1}),
            stderr="",
        )
        with patch("qmt_broker.providers.xtquant_runtime.subprocess.run", return_value=completed) as run_mock:
            result = _prefetch_history_via_subprocess(
                ["000001.SZ"],
                "1m",
                start_time="20260320093000",
                end_time="20260320150000",
                timeout_sec=9,
            )
        self.assertTrue(result["ok"])
        self.assertEqual(result["symbol_count"], 1)
        run_mock.assert_called_once()

    def test_prefetch_history_reports_subprocess_timeout(self) -> None:
        with patch(
            "qmt_broker.providers.xtquant_runtime.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd=["python"], timeout=9),
        ):
            result = _prefetch_history_via_subprocess(
                ["000001.SZ"],
                "1m",
                start_time="20260320093000",
                end_time="20260320150000",
                timeout_sec=9,
            )
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "download_history_timeout")

    def test_trade_status_reports_connected_after_lazy_status_query(self) -> None:
        class FakeTrader:
            def query_account_status(self):
                return [{"account_id": "61002000", "account_type": 2, "status": 0}]

        provider = object.__new__(XtQuantTradeProvider)
        provider._config = SimpleNamespace(trader_path="e:\\QMT\\userdata_mini", trader_session_id=10001)
        provider._connected = False
        provider._subscribed_accounts = {}
        provider._account_statuses = {}

        def ensure_trader():
            provider._connected = True
            return FakeTrader()

        provider._ensure_trader = ensure_trader

        status = provider.status()
        self.assertTrue(status["connected"])
        self.assertEqual(status["account_statuses"][0]["account_id"], "61002000")

    def test_tick_prefetch_subscribes_then_retries_when_initial_read_is_empty(self) -> None:
        class FakeXtData:
            def __init__(self) -> None:
                self.subscribe_calls = []
                self.unsubscribe_calls = []

            def subscribe_quote(self, stock_code, period="1d", start_time="", end_time="", count=0, callback=None):
                self.subscribe_calls.append(
                    {
                        "stock_code": stock_code,
                        "period": period,
                        "start_time": start_time,
                        "end_time": end_time,
                        "count": count,
                        "callback": callback,
                    }
                )
                return 77

            def unsubscribe_quote(self, seq):
                self.unsubscribe_calls.append(seq)

        provider = object.__new__(XtQuantMarketDataProvider)
        provider._xtdata = FakeXtData()
        provider._lock = threading.RLock()
        provider._handles = {}
        responses = [
            [],
            [{"time": 1773730800000, "lastPrice": 11.03}],
        ]

        def fake_fetch(symbol, count, start_time="", end_time=""):
            self.assertEqual(symbol, "000001.SZ")
            self.assertEqual(count, 5)
            return responses.pop(0)

        with patch("qmt_broker.providers.xtquant_runtime._fetch_ticks_via_subprocess", side_effect=fake_fetch):
            result = provider.get_ticks(
                "000001.SZ",
                5,
                run_prefetch=True,
                wait_timeout_ms=200,
                poll_interval_ms=50,
            )

        self.assertEqual(result, [{"time": 1773730800000, "lastPrice": 11.03}])
        self.assertEqual(provider._xtdata.subscribe_calls[0]["period"], "tick")
        self.assertEqual(provider._xtdata.unsubscribe_calls, [77])

    def test_bars_diagnostics_hoists_prefetch_polls_to_top_level(self) -> None:
        provider = object.__new__(XtQuantMarketDataProvider)
        provider._xtdata = SimpleNamespace(data_dir="")

        def capture_bars_snapshot(symbol, period, limit, start_time, end_time):
            return {
                "market": {"source": "get_market_data", "ok": True, "record_count": 1, "sample": [{"time": "20260318101700"}]},
                "local": {"source": "get_local_data", "ok": True, "record_count": 1, "sample": [{"time": "20260318101700"}]},
            }

        provider._capture_bars_snapshot = capture_bars_snapshot
        provider.prefetch_history = lambda *args, **kwargs: {
            "ok": True,
            "provider": "xtquant",
            "cache_ready": True,
            "local_after_wait": {"record_count": 1},
            "polls": [{"attempt": 1, "elapsed_ms": 0}],
        }

        result = provider.diagnose_bars("000001.SZ", "1m", 5, run_prefetch=True, wait_timeout_ms=3000)
        self.assertEqual(result["polls"], [{"attempt": 1, "elapsed_ms": 0}])
        self.assertNotIn("polls", result["prefetch"])

    def test_backfill_ticks_waits_for_prefetch_cache_before_second_fetch(self) -> None:
        provider = object.__new__(XtQuantMarketDataProvider)
        provider._xtdata = SimpleNamespace()
        provider._lock = threading.RLock()
        provider._handles = {}
        fetch_calls = []

        def fake_fetch(symbol, count, start_time="", end_time=""):
            fetch_calls.append(
                {
                    "symbol": symbol,
                    "count": count,
                    "start_time": start_time,
                    "end_time": end_time,
                }
            )
            if len(fetch_calls) == 1:
                return []
            return [{"time": 1773730800000, "lastPrice": 11.03}]

        prefetch_calls = []

        def fake_prefetch(symbol, period, start_time="", end_time="", wait_timeout_ms=0, poll_interval_ms=250):
            prefetch_calls.append(
                {
                    "symbol": symbol,
                    "period": period,
                    "start_time": start_time,
                    "end_time": end_time,
                    "wait_timeout_ms": wait_timeout_ms,
                    "poll_interval_ms": poll_interval_ms,
                }
            )
            return {
                "ok": True,
                "cache_ready": True,
                "local_after_wait": {"record_count": 12},
            }

        provider.prefetch_history = fake_prefetch

        with patch("qmt_broker.providers.xtquant_runtime._fetch_ticks_via_subprocess", side_effect=fake_fetch):
            result = provider.backfill_ticks("000001.SZ", "20260319093000", "20260319150000")

        self.assertEqual(result, [{"time": 1773730800000, "lastPrice": 11.03}])
        self.assertEqual(prefetch_calls[0]["wait_timeout_ms"], 5000)
        self.assertEqual(prefetch_calls[0]["poll_interval_ms"], 250)
        self.assertEqual(fetch_calls[0]["count"], -1)
        self.assertEqual(fetch_calls[1]["count"], -1)

    def test_backfill_ticks_uses_market_data_ex_fallback_after_empty_second_fetch(self) -> None:
        class FakeTickFrame:
            def __init__(self) -> None:
                self.index = [1773730800000, 1773730803000]

            def to_dict(self, orient="records"):
                assert orient == "records"
                return [
                    {"lastPrice": 11.03, "volume": 1000},
                    {"lastPrice": 11.05, "volume": 1200},
                ]

        class FakeXtData:
            def get_market_data_ex(self, **kwargs):
                return {"000001.SZ": FakeTickFrame()}

            def get_local_data(self, **kwargs):
                return {"000001.SZ": []}

        provider = object.__new__(XtQuantMarketDataProvider)
        provider._xtdata = FakeXtData()
        provider._lock = threading.RLock()
        provider._handles = {}
        provider.prefetch_history = lambda *args, **kwargs: {
            "ok": True,
            "cache_ready": False,
            "local_after_wait": {"record_count": 0},
        }

        with patch("qmt_broker.providers.xtquant_runtime._fetch_ticks_via_subprocess", return_value=[]):
            result = provider.backfill_ticks("000001.SZ", "20260319093000", "20260319150000")

        self.assertEqual(
            result,
            [
                {"time": 1773730800000, "lastPrice": 11.03, "volume": 1000},
                {"time": 1773730803000, "lastPrice": 11.05, "volume": 1200},
            ],
        )


if __name__ == "__main__":
    unittest.main()
