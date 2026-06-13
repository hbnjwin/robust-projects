import json
import pathlib
import queue
import sys
import tempfile
import threading
import unittest
import urllib.request
from types import SimpleNamespace
from datetime import datetime

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qmt_broker.broker import MarketDataBroker
from qmt_broker.config import BrokerConfig
from qmt_broker.http_api import BrokerHttpServer, BrokerRequestHandler
from qmt_broker.providers.mock import MockMarketDataProvider
from qmt_broker.providers.mock_trade import MockTradeProvider
from qmt_broker.trade_broker import TradeBroker


class FakeTickCache:
    def get_recent_ticks(self, symbol, limit):  # type: ignore[no-untyped-def]
        if symbol != "000001.SZ":
            return []
        return [{"time": 1773812943000, "lastPrice": 7.03, "volume": 169340}][:limit]

    def append_event(self, symbol, event):  # type: ignore[no-untyped-def]
        return None

    def status(self):  # type: ignore[no-untyped-def]
        return {
            "enabled": True,
            "backend": "fake",
            "connected": True,
            "cached_symbols": ["000001.SZ"],
            "last_error": "",
            "ttl_sec": 30,
            "max_records": 8,
            "key_prefix": "test",
        }

    def close(self):  # type: ignore[no-untyped-def]
        return None


class HttpApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.provider = MockMarketDataProvider()
        self.trade_provider = MockTradeProvider()
        self.broker = MarketDataBroker(
            self.provider,
            BrokerConfig(
                host="127.0.0.1",
                port=0,
                token="test-token",
                heartbeat_interval_sec=1,
                trade_audit_log_path=str(pathlib.Path(self.tempdir.name) / "trade-audit.jsonl"),
                trade_state_store_path=str(pathlib.Path(self.tempdir.name) / "trade-state.json"),
            ),
        )
        self.trade_broker = TradeBroker(self.trade_provider, self.broker.config)
        self.server = BrokerHttpServer(("127.0.0.1", 0), self.broker, self.trade_broker, self.broker.config)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.base_url = "http://%s:%s" % (host, port)

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=1.0)
        self.broker.close()
        self.trade_broker.close()
        self.tempdir.cleanup()

    def test_quote_endpoint(self) -> None:
        request = urllib.request.Request(self.base_url + "/v1/market/quote?symbol=000001.SZ")
        request.add_header("Authorization", "Bearer test-token")
        with urllib.request.urlopen(request) as response:
            payload = json.loads(response.read().decode("utf-8"))
        self.assertEqual(payload["symbol"], "000001.SZ")
        self.assertIn("result", payload)

    def test_market_prefetch_endpoint(self) -> None:
        request = urllib.request.Request(
            self.base_url + "/v1/market/prefetch",
            data=json.dumps(
                {
                    "symbol": "000001.SZ",
                    "period": "1m",
                    "start_time": "20240101093000",
                    "end_time": "20240101150000",
                    "wait_timeout_ms": 1500,
                    "poll_interval_ms": 200,
                }
            ).encode("utf-8"),
            method="POST",
        )
        request.add_header("Authorization", "Bearer test-token")
        request.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(request) as response:
            payload = json.loads(response.read().decode("utf-8"))
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["period"], "1m")
        self.assertEqual(payload["wait_timeout_ms"], 1500)
        self.assertEqual(payload["poll_interval_ms"], 200)

    def test_market_bars_diagnostics_endpoint(self) -> None:
        request = urllib.request.Request(
            self.base_url
            + "/v1/market/bars/diagnostics?symbol=000001.SZ&period=1m&limit=2&prefetch=1&wait_timeout_ms=500&poll_interval_ms=100"
        )
        request.add_header("Authorization", "Bearer test-token")
        with urllib.request.urlopen(request) as response:
            payload = json.loads(response.read().decode("utf-8"))
        self.assertEqual(payload["symbol"], "000001.SZ")
        self.assertTrue(payload["result"]["ok"])
        self.assertEqual(payload["result"]["run_prefetch"], True)
        self.assertEqual(payload["result"]["wait_timeout_ms"], 500)
        self.assertEqual(payload["result"]["poll_interval_ms"], 100)
        self.assertIn("before", payload["result"])
        self.assertIn("after", payload["result"])

    def test_market_ticks_endpoint_forwards_prefetch_controls(self) -> None:
        captured = {}

        def fake_get_ticks_response(
            symbol, limit, start_time="", end_time="", run_prefetch=False, wait_timeout_ms=0, poll_interval_ms=250
        ):
            captured.update(
                {
                    "symbol": symbol,
                    "limit": limit,
                    "start_time": start_time,
                    "end_time": end_time,
                    "run_prefetch": run_prefetch,
                    "wait_timeout_ms": wait_timeout_ms,
                    "poll_interval_ms": poll_interval_ms,
                }
            )
            return {"result": [], "source": "provider"}

        self.broker.get_ticks_response = fake_get_ticks_response  # type: ignore[method-assign]
        request = urllib.request.Request(
            self.base_url
            + "/v1/market/ticks?symbol=000001.SZ&limit=5&prefetch=1&wait_timeout_ms=1200&poll_interval_ms=75"
        )
        request.add_header("Authorization", "Bearer test-token")
        with urllib.request.urlopen(request) as response:
            payload = json.loads(response.read().decode("utf-8"))
        self.assertEqual(payload["symbol"], "000001.SZ")
        self.assertEqual(payload["result"], [])
        self.assertEqual(payload["market_session"], {})
        self.assertEqual(payload["diagnostics"], {})
        self.assertEqual(
            captured,
            {
                "symbol": "000001.SZ",
                "limit": 5,
                "start_time": "",
                "end_time": "",
                "run_prefetch": True,
                "wait_timeout_ms": 1200,
                "poll_interval_ms": 75,
            },
        )

    def test_market_ticks_endpoint_includes_source(self) -> None:
        provider = MockMarketDataProvider()
        trade_provider = MockTradeProvider()
        broker = MarketDataBroker(
            provider,
            BrokerConfig(
                host="127.0.0.1",
                port=0,
                token="test-token",
                heartbeat_interval_sec=1,
                trade_audit_log_path=str(pathlib.Path(self.tempdir.name) / "trade-audit.jsonl"),
                trade_state_store_path=str(pathlib.Path(self.tempdir.name) / "trade-state.json"),
            ),
            tick_cache=FakeTickCache(),
        )
        trade_broker = TradeBroker(trade_provider, broker.config)
        server = BrokerHttpServer(("127.0.0.1", 0), broker, trade_broker, broker.config)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        host, port = server.server_address
        base_url = "http://%s:%s" % (host, port)
        try:
            request = urllib.request.Request(base_url + "/v1/market/ticks?symbol=000001.SZ&limit=1")
            request.add_header("Authorization", "Bearer test-token")
            with urllib.request.urlopen(request) as response:
                payload = json.loads(response.read().decode("utf-8"))
            self.assertEqual(payload["source"], "redis")
            self.assertEqual(payload["result"][0]["lastPrice"], 7.03)
            self.assertIn("market_session", payload)
            self.assertIn("diagnostics", payload)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=1.0)
            broker.close()
            trade_broker.close()

    def test_market_ticks_keepalive_endpoint_returns_broker_status(self) -> None:
        self.broker.touch_tick_keepalive("000001.SZ")
        request = urllib.request.Request(self.base_url + "/v1/market/ticks/keepalive")
        request.add_header("Authorization", "Bearer test-token")
        with urllib.request.urlopen(request) as response:
            payload = json.loads(response.read().decode("utf-8"))
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["symbols"][0]["symbol"], "000001.SZ")
        self.assertIn("source", payload)
        self.assertIn("cache", payload)

    def test_market_tick_archive_status_endpoint_returns_broker_status(self) -> None:
        request = urllib.request.Request(self.base_url + "/v1/market/ticks/archive/status")
        request.add_header("Authorization", "Bearer test-token")
        with urllib.request.urlopen(request) as response:
            payload = json.loads(response.read().decode("utf-8"))
        self.assertIn("enabled", payload)
        self.assertIn("connected", payload)
        self.assertIn("table", payload)

    def test_market_tick_archive_query_endpoint_returns_rows(self) -> None:
        captured = {}

        def fake_get_tick_archive_records(symbol, trade_date="", limit=500):  # type: ignore[no-untyped-def]
            captured.update({"symbol": symbol, "trade_date": trade_date, "limit": limit})
            return [{"ts_code": symbol, "trade_date": trade_date or "2026-03-18", "tick_time_ms": 1773817200000}]

        self.broker.get_tick_archive_records = fake_get_tick_archive_records  # type: ignore[method-assign]
        request = urllib.request.Request(
            self.base_url + "/v1/market/ticks/archive?symbol=600196.SH&trade_date=2026-03-18&limit=20"
        )
        request.add_header("Authorization", "Bearer test-token")
        with urllib.request.urlopen(request) as response:
            payload = json.loads(response.read().decode("utf-8"))
        self.assertEqual(payload["symbol"], "600196.SH")
        self.assertEqual(payload["trade_date"], "2026-03-18")
        self.assertEqual(payload["result"][0]["ts_code"], "600196.SH")
        self.assertIn("archive", payload)
        self.assertEqual(captured, {"symbol": "600196.SH", "trade_date": "2026-03-18", "limit": 20})

    def test_market_tick_archive_bars_endpoint_returns_rows(self) -> None:
        captured = {}

        def fake_get_tick_archive_bars(symbol, trade_date="", period="1m", limit=240):  # type: ignore[no-untyped-def]
            captured.update({"symbol": symbol, "trade_date": trade_date, "period": period, "limit": limit})
            return [{"time": "20260318145900", "close": 25.76, "volume": 96272}]

        self.broker.get_tick_archive_bars = fake_get_tick_archive_bars  # type: ignore[method-assign]
        request = urllib.request.Request(
            self.base_url + "/v1/market/ticks/archive/bars?symbol=600196.SH&trade_date=2026-03-18&period=5m&limit=48"
        )
        request.add_header("Authorization", "Bearer test-token")
        with urllib.request.urlopen(request) as response:
            payload = json.loads(response.read().decode("utf-8"))
        self.assertEqual(payload["symbol"], "600196.SH")
        self.assertEqual(payload["trade_date"], "2026-03-18")
        self.assertEqual(payload["period"], "5m")
        self.assertEqual(payload["result"][0]["close"], 25.76)
        self.assertIn("archive", payload)
        self.assertEqual(captured, {"symbol": "600196.SH", "trade_date": "2026-03-18", "period": "5m", "limit": 48})

    def test_market_tick_archive_features_endpoint_returns_summary(self) -> None:
        captured = {}

        def fake_get_tick_archive_features(symbol, trade_date=""):  # type: ignore[no-untyped-def]
            captured.update({"symbol": symbol, "trade_date": trade_date})
            return {
                "symbol": symbol,
                "trade_date": trade_date or "2026-03-18",
                "tick_count": 12,
                "day_return_pct": 1.9,
                "bar_count_15m": 1,
            }

        self.broker.get_tick_archive_features = fake_get_tick_archive_features  # type: ignore[method-assign]
        request = urllib.request.Request(
            self.base_url + "/v1/market/ticks/archive/features?symbol=600196.SH&trade_date=2026-03-18"
        )
        request.add_header("Authorization", "Bearer test-token")
        with urllib.request.urlopen(request) as response:
            payload = json.loads(response.read().decode("utf-8"))
        self.assertEqual(payload["symbol"], "600196.SH")
        self.assertEqual(payload["result"]["tick_count"], 12)
        self.assertEqual(payload["result"]["bar_count_15m"], 1)
        self.assertIn("archive", payload)
        self.assertEqual(captured, {"symbol": "600196.SH", "trade_date": "2026-03-18"})

    def test_market_symbols_endpoint_returns_catalog(self) -> None:
        request = urllib.request.Request(self.base_url + "/v1/market/symbols")
        request.add_header("Authorization", "Bearer test-token")
        with urllib.request.urlopen(request) as response:
            payload = json.loads(response.read().decode("utf-8"))
        self.assertTrue(payload["ok"])
        self.assertIn("watchlist", payload)
        self.assertIn("positions", payload)
        self.assertIn("all", payload)
        self.assertEqual(payload["source"]["source"], "disabled")

    def test_stream_endpoint(self) -> None:
        request = urllib.request.Request(self.base_url + "/v1/stream?topics=tick&symbol=000001.SZ")
        request.add_header("Authorization", "Bearer test-token")
        with urllib.request.urlopen(request, timeout=5) as response:
            chunks = []
            for raw_line in response:
                line = raw_line.decode("utf-8").strip()
                if line:
                    chunks.append(line)
                if len(chunks) >= 4:
                    break
        self.assertTrue(any(line.startswith("event: ready") for line in chunks))
        self.assertTrue(any(line.startswith("event: event") for line in chunks))

    def test_do_get_ignores_client_disconnect(self) -> None:
        handler = object.__new__(BrokerRequestHandler)
        sent = {"called": False}

        def fake_handle_get() -> None:
            raise ConnectionAbortedError(10053, "client disconnected")

        def fake_send_json(status, payload) -> None:  # type: ignore[no-untyped-def]
            sent["called"] = True

        handler._handle_get = fake_handle_get  # type: ignore[attr-defined]
        handler._send_json = fake_send_json  # type: ignore[attr-defined]
        handler.do_GET()
        self.assertFalse(sent["called"])

    def test_stream_endpoint_ignores_connection_aborted_error(self) -> None:
        market_broker = SimpleNamespace()
        stream_queue: "queue.Queue[dict[str, object]]" = queue.Queue()
        closed = {"stream_id": ""}

        def open_stream(request) -> tuple[str, "queue.Queue[dict[str, object]]"]:  # type: ignore[no-untyped-def]
            return "stream-1", stream_queue

        def close_stream(stream_id: str) -> None:
            closed["stream_id"] = stream_id

        market_broker.open_stream = open_stream
        market_broker.close_stream = close_stream
        handler = object.__new__(BrokerRequestHandler)
        handler.server = SimpleNamespace(
            market_broker=market_broker,
            config=SimpleNamespace(heartbeat_interval_sec=1),
        )
        handler.send_response = lambda status: None  # type: ignore[attr-defined]
        handler.send_header = lambda name, value: None  # type: ignore[attr-defined]
        handler.end_headers = lambda: None  # type: ignore[attr-defined]
        handler._send_error = lambda status, code: None  # type: ignore[attr-defined]

        def aborting_write_sse(event_name: str, payload: dict[str, object]) -> None:
            raise ConnectionAbortedError(10053, "client disconnected")

        handler._write_sse = aborting_write_sse  # type: ignore[attr-defined]
        handler._handle_stream("topics=tick&symbol=000001.SZ")
        self.assertEqual(closed["stream_id"], "stream-1")

    def test_trade_order_endpoint(self) -> None:
        request = urllib.request.Request(
            self.base_url + "/v1/trade/order",
            data=json.dumps(
                {
                    "account_id": "mock-stock",
                    "symbol": "600000.SH",
                    "side": "buy",
                    "volume": 100,
                    "price": 10.5,
                }
            ).encode("utf-8"),
            method="POST",
        )
        request.add_header("Authorization", "Bearer test-token")
        request.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(request) as response:
            payload = json.loads(response.read().decode("utf-8"))
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["status"], "executed")
        self.assertGreater(payload["result"]["order_id"], 0)

    def test_trade_stream_endpoint(self) -> None:
        trade_request = urllib.request.Request(
            self.base_url + "/v1/trade/order",
            data=json.dumps(
                {
                    "account_id": "mock-stock",
                    "symbol": "600000.SH",
                    "side": "buy",
                    "volume": 100,
                    "price": 10.5,
                }
            ).encode("utf-8"),
            method="POST",
        )
        trade_request.add_header("Authorization", "Bearer test-token")
        trade_request.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(trade_request):
            pass
        request = urllib.request.Request(self.base_url + "/v1/trade/stream?topics=order,trade&account_id=mock-stock&replay=2")
        request.add_header("Authorization", "Bearer test-token")
        with urllib.request.urlopen(request, timeout=5) as response:
            chunks = []
            for raw_line in response:
                line = raw_line.decode("utf-8").strip()
                if line:
                    chunks.append(line)
                if len(chunks) >= 4:
                    break
        self.assertTrue(any(line.startswith("event: ready") for line in chunks))
        self.assertTrue(any(line.startswith("event: replay") or line.startswith("event: event") for line in chunks))

    def test_trade_audit_endpoint(self) -> None:
        trade_request = urllib.request.Request(
            self.base_url + "/v1/trade/order",
            data=json.dumps(
                {
                    "account_id": "mock-stock",
                    "symbol": "600000.SH",
                    "side": "buy",
                    "volume": 100,
                    "price": 10.5,
                }
            ).encode("utf-8"),
            method="POST",
        )
        trade_request.add_header("Authorization", "Bearer test-token")
        trade_request.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(trade_request):
            pass
        request = urllib.request.Request(self.base_url + "/v1/trade/audit?limit=5")
        request.add_header("Authorization", "Bearer test-token")
        with urllib.request.urlopen(request) as response:
            payload = json.loads(response.read().decode("utf-8"))
        self.assertTrue(any(item["action"] == "place_order" for item in payload["result"] if item["kind"] == "trade_action"))

    def test_credit_endpoint(self) -> None:
        request = urllib.request.Request(self.base_url + "/v1/trade/credit/subjects?account_id=mock-credit&account_type=CREDIT")
        request.add_header("Authorization", "Bearer test-token")
        with urllib.request.urlopen(request) as response:
            payload = json.loads(response.read().decode("utf-8"))
        self.assertGreaterEqual(len(payload["result"]), 1)

    def test_account_status_endpoints(self) -> None:
        request = urllib.request.Request(self.base_url + "/v1/trade/account-statuses")
        request.add_header("Authorization", "Bearer test-token")
        with urllib.request.urlopen(request) as response:
            statuses = json.loads(response.read().decode("utf-8"))
        self.assertIsInstance(statuses["result"], list)

        request = urllib.request.Request(self.base_url + "/v1/trade/account-infos")
        request.add_header("Authorization", "Bearer test-token")
        with urllib.request.urlopen(request) as response:
            infos = json.loads(response.read().decode("utf-8"))
        self.assertIsInstance(infos["result"], list)

    def test_json_safe_response_serialization(self) -> None:
        class CustomStatus:
            def __init__(self) -> None:
                self.account_id = "mock-stock"
                self.connected = True
                self.updated_at = datetime(2026, 3, 17, 12, 0, 0)

        class CustomScalar:
            def __init__(self, value) -> None:  # type: ignore[no-untyped-def]
                self.value = value

            def item(self):  # type: ignore[no-untyped-def]
                return self.value

        self.trade_provider.status = lambda: {  # type: ignore[method-assign]
            "provider": "mock",
            "connected": True,
            "accounts": ["mock-stock"],
            "account_statuses": [CustomStatus()],
        }
        self.provider.get_bars = lambda symbol, period, limit, start_time="", end_time="": [  # type: ignore[method-assign]
            {
                "time": CustomScalar(1773730800000),
                "price": CustomScalar(11.03),
                "seen_at": datetime(2026, 3, 17, 15, 0, 0),
            }
        ]

        request = urllib.request.Request(self.base_url + "/v1/trade/status")
        request.add_header("Authorization", "Bearer test-token")
        with urllib.request.urlopen(request) as response:
            status_payload = json.loads(response.read().decode("utf-8"))
        self.assertEqual(status_payload["provider"], "mock")
        self.assertEqual(status_payload["account_statuses"][0]["account_id"], "mock-stock")
        self.assertEqual(status_payload["account_statuses"][0]["updated_at"], "2026-03-17T12:00:00")

        request = urllib.request.Request(self.base_url + "/v1/market/bars?symbol=000001.SZ&period=1m&limit=1")
        request.add_header("Authorization", "Bearer test-token")
        with urllib.request.urlopen(request) as response:
            bars_payload = json.loads(response.read().decode("utf-8"))
        self.assertEqual(bars_payload["result"][0]["time"], 1773730800000)
        self.assertEqual(bars_payload["result"][0]["price"], 11.03)
        self.assertEqual(bars_payload["result"][0]["seen_at"], "2026-03-17T15:00:00")

    def test_pending_request_endpoints(self) -> None:
        self.trade_broker.close()
        self.trade_provider = MockTradeProvider()
        self.trade_broker = TradeBroker(
            self.trade_provider,
            BrokerConfig(
                host="127.0.0.1",
                port=0,
                token="test-token",
                heartbeat_interval_sec=1,
                trade_audit_log_path=str(pathlib.Path(self.tempdir.name) / "trade-audit.jsonl"),
                trade_state_store_path=str(pathlib.Path(self.tempdir.name) / "trade-state.json"),
                require_order_approval=True,
                approver_secrets={"alice": "secret-a"},
            ),
        )
        self.server.trade_broker = self.trade_broker
        trade_request = urllib.request.Request(
            self.base_url + "/v1/trade/order",
            data=json.dumps(
                {
                    "account_id": "mock-stock",
                    "symbol": "600000.SH",
                    "side": "buy",
                    "volume": 100,
                    "price": 10.5,
                    "idempotency_key": "pending-http-1",
                }
            ).encode("utf-8"),
            method="POST",
        )
        trade_request.add_header("Authorization", "Bearer test-token")
        trade_request.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(trade_request) as response:
            created = json.loads(response.read().decode("utf-8"))
        self.assertTrue(created["pending"])
        request_id = created["request_id"]

        request = urllib.request.Request(self.base_url + "/v1/trade/request?request_id=" + request_id)
        request.add_header("Authorization", "Bearer test-token")
        with urllib.request.urlopen(request) as response:
            status_payload = json.loads(response.read().decode("utf-8"))
        self.assertEqual(status_payload["result"]["status"], "pending")

        approve_request = urllib.request.Request(
            self.base_url + "/v1/trade/approve",
            data=json.dumps(
                {"request_id": request_id, "approver_id": "alice", "approver_secret": "secret-a"}
            ).encode("utf-8"),
            method="POST",
        )
        approve_request.add_header("Authorization", "Bearer test-token")
        approve_request.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(approve_request) as response:
            approved = json.loads(response.read().decode("utf-8"))
        self.assertTrue(approved["ok"])

    def test_pending_request_expired_http(self) -> None:
        self.trade_broker.close()
        self.trade_provider = MockTradeProvider()
        self.trade_broker = TradeBroker(
            self.trade_provider,
            BrokerConfig(
                host="127.0.0.1",
                port=0,
                token="test-token",
                heartbeat_interval_sec=1,
                trade_audit_log_path=str(pathlib.Path(self.tempdir.name) / "trade-audit.jsonl"),
                trade_state_store_path=str(pathlib.Path(self.tempdir.name) / "trade-state.json"),
                require_order_approval=True,
                approval_pending_ttl_sec=1,
                approver_secrets={"alice": "secret-a"},
            ),
        )
        self.server.trade_broker = self.trade_broker
        trade_request = urllib.request.Request(
            self.base_url + "/v1/trade/order",
            data=json.dumps(
                {
                    "account_id": "mock-stock",
                    "symbol": "600000.SH",
                    "side": "buy",
                    "volume": 100,
                    "price": 10.5,
                    "idempotency_key": "pending-http-expire-1",
                }
            ).encode("utf-8"),
            method="POST",
        )
        trade_request.add_header("Authorization", "Bearer test-token")
        trade_request.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(trade_request) as response:
            created = json.loads(response.read().decode("utf-8"))
        import time

        time.sleep(1.1)
        request = urllib.request.Request(self.base_url + "/v1/trade/request?request_id=" + created["request_id"])
        request.add_header("Authorization", "Bearer test-token")
        with urllib.request.urlopen(request) as response:
            payload = json.loads(response.read().decode("utf-8"))
        self.assertEqual(payload["result"]["status"], "expired")

    def test_request_index_and_revoke_http(self) -> None:
        trade_request = urllib.request.Request(
            self.base_url + "/v1/trade/order",
            data=json.dumps(
                {
                    "account_id": "mock-stock",
                    "symbol": "600000.SH",
                    "side": "buy",
                    "volume": 100,
                    "price": 10.5,
                }
            ).encode("utf-8"),
            method="POST",
        )
        trade_request.add_header("Authorization", "Bearer test-token")
        trade_request.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(trade_request) as response:
            created = json.loads(response.read().decode("utf-8"))
        request = urllib.request.Request(
            self.base_url + "/v1/trade/request/by-order-id?order_id=%s" % created["result"]["order_id"]
        )
        request.add_header("Authorization", "Bearer test-token")
        with urllib.request.urlopen(request) as response:
            payload = json.loads(response.read().decode("utf-8"))
        self.assertEqual(payload["result"]["request_id"], created["request_id"])
        order_sysid = payload["result"]["links"]["order_sysids"][0]
        request = urllib.request.Request(
            self.base_url + "/v1/trade/request/by-order-sysid?order_sysid=" + order_sysid
        )
        request.add_header("Authorization", "Bearer test-token")
        with urllib.request.urlopen(request) as response:
            by_sysid = json.loads(response.read().decode("utf-8"))
        self.assertEqual(by_sysid["result"]["request_id"], created["request_id"])
        trade_id = payload["result"]["links"]["trade_ids"][0]
        request = urllib.request.Request(
            self.base_url + "/v1/trade/request/by-trade-id?trade_id=" + str(trade_id)
        )
        request.add_header("Authorization", "Bearer test-token")
        with urllib.request.urlopen(request) as response:
            by_trade = json.loads(response.read().decode("utf-8"))
        self.assertEqual(by_trade["result"]["request_id"], created["request_id"])

        self.trade_broker.close()
        self.trade_provider = MockTradeProvider()
        self.trade_broker = TradeBroker(
            self.trade_provider,
            BrokerConfig(
                host="127.0.0.1",
                port=0,
                token="test-token",
                heartbeat_interval_sec=1,
                trade_audit_log_path=str(pathlib.Path(self.tempdir.name) / "trade-audit.jsonl"),
                trade_state_store_path=str(pathlib.Path(self.tempdir.name) / "trade-state.json"),
                require_order_approval=True,
            ),
        )
        self.server.trade_broker = self.trade_broker
        pending_request = urllib.request.Request(
            self.base_url + "/v1/trade/order",
            data=json.dumps(
                {
                    "account_id": "mock-stock",
                    "symbol": "600001.SH",
                    "side": "buy",
                    "volume": 100,
                    "price": 10.5,
                    "idempotency_key": "revoke-http-1",
                }
            ).encode("utf-8"),
            method="POST",
        )
        pending_request.add_header("Authorization", "Bearer test-token")
        pending_request.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(pending_request) as response:
            pending = json.loads(response.read().decode("utf-8"))
        revoke_request = urllib.request.Request(
            self.base_url + "/v1/trade/revoke",
            data=json.dumps({"request_id": pending["request_id"], "reason": "user canceled"}).encode("utf-8"),
            method="POST",
        )
        revoke_request.add_header("Authorization", "Bearer test-token")
        revoke_request.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(revoke_request) as response:
            revoked = json.loads(response.read().decode("utf-8"))
        self.assertEqual(revoked["status"], "revoked")

    def test_notifications_status_http(self) -> None:
        request = urllib.request.Request(self.base_url + "/v1/trade/notifications")
        request.add_header("Authorization", "Bearer test-token")
        with urllib.request.urlopen(request) as response:
            payload = json.loads(response.read().decode("utf-8"))
        self.assertIn("enabled", payload)
        self.assertIn("channels", payload)

    def test_idempotency_http(self) -> None:
        body = {
            "account_id": "mock-stock",
            "symbol": "600000.SH",
            "side": "buy",
            "volume": 100,
            "price": 10.5,
            "idempotency_key": "idem-http-1",
        }
        first_request = urllib.request.Request(
            self.base_url + "/v1/trade/order",
            data=json.dumps(body).encode("utf-8"),
            method="POST",
        )
        first_request.add_header("Authorization", "Bearer test-token")
        first_request.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(first_request) as response:
            first = json.loads(response.read().decode("utf-8"))

        second_request = urllib.request.Request(
            self.base_url + "/v1/trade/order",
            data=json.dumps(body).encode("utf-8"),
            method="POST",
        )
        second_request.add_header("Authorization", "Bearer test-token")
        second_request.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(second_request) as response:
            second = json.loads(response.read().decode("utf-8"))
        self.assertEqual(first["request_id"], second["request_id"])
        self.assertTrue(second["reused"])

    def test_async_request_index_by_seq_http(self) -> None:
        body = {
            "account_id": "mock-stock",
            "symbol": "600000.SH",
            "side": "buy",
            "volume": 100,
            "price": 10.5,
            "async": True,
        }
        order_request = urllib.request.Request(
            self.base_url + "/v1/trade/order",
            data=json.dumps(body).encode("utf-8"),
            method="POST",
        )
        order_request.add_header("Authorization", "Bearer test-token")
        order_request.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(order_request) as response:
            created = json.loads(response.read().decode("utf-8"))

        seq = created["result"]["seq"]
        request = urllib.request.Request(self.base_url + "/v1/trade/request/by-seq?seq=%s" % seq)
        request.add_header("Authorization", "Bearer test-token")
        with urllib.request.urlopen(request) as response:
            payload = json.loads(response.read().decode("utf-8"))
        self.assertEqual(payload["result"]["request_id"], created["request_id"])


if __name__ == "__main__":
    unittest.main()
