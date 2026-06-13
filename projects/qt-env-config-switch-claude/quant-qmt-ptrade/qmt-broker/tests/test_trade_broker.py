import pathlib
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qmt_broker.config import BrokerConfig
from qmt_broker.providers.mock_trade import MockTradeProvider
from qmt_broker.trade_broker import TradeBroker
from qmt_broker.trade_models import TradeStreamFilter


class NotificationCaptureHandler(BaseHTTPRequestHandler):
    events = []

    def do_POST(self) -> None:
        content_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_length) if content_length > 0 else b"{}"
        NotificationCaptureHandler.events.append(body.decode("utf-8"))
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, fmt: str, *args) -> None:  # type: ignore[override]
        return None


class TradeBrokerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.provider = MockTradeProvider()
        self.tempdir = tempfile.TemporaryDirectory()
        self.audit_path = str(pathlib.Path(self.tempdir.name) / "trade-audit.jsonl")
        self.state_path = str(pathlib.Path(self.tempdir.name) / "trade-state.json")
        self.broker = TradeBroker(
            self.provider,
            BrokerConfig(
                stream_queue_size=32,
                trade_audit_log_path=self.audit_path,
                trade_state_store_path=self.state_path,
            ),
        )

    def tearDown(self) -> None:
        self.broker.close()
        self.tempdir.cleanup()

    def test_place_order_updates_state(self) -> None:
        result = self.broker.place_order(
            {
                "account_id": "mock-stock",
                "symbol": "600000.SH",
                "side": "buy",
                "volume": 100,
                "price": 10.5,
            }
        )
        self.assertTrue(result["ok"])
        asset = self.broker.get_asset("mock-stock")
        self.assertIsNotNone(asset)
        positions = self.broker.get_positions("mock-stock")
        self.assertEqual(len(positions), 1)
        self.assertEqual(positions[0]["stock_code"], "600000.SH")

    def test_request_indexes_follow_order_and_trade_events(self) -> None:
        result = self.broker.place_order(
            {
                "account_id": "mock-stock",
                "symbol": "600000.SH",
                "side": "buy",
                "volume": 100,
                "price": 10.5,
            }
        )
        request_id = result["request_id"]
        order_id = str(result["result"]["order_id"])
        request = self.broker.request_by_order_id(order_id)
        self.assertIsNotNone(request)
        self.assertEqual(request["request_id"], request_id)
        order_sysid = request["links"]["order_sysids"][0]
        by_sysid = self.broker.request_by_order_sysid(order_sysid)
        self.assertEqual(by_sysid["request_id"], request_id)
        trade_id = request["links"]["trade_ids"][0]
        by_trade = self.broker.request_by_trade_id(trade_id)
        self.assertEqual(by_trade["request_id"], request_id)

    def test_trade_stream_replay(self) -> None:
        self.broker.place_order(
            {
                "account_id": "mock-stock",
                "symbol": "600000.SH",
                "side": "buy",
                "volume": 100,
                "price": 10.5,
            }
        )
        stream_id, stream_queue = self.broker.open_stream(
            TradeStreamFilter(topics=["order", "trade"], account_id="mock-stock", replay=2)
        )
        try:
            message = stream_queue.get(timeout=1.0)
            self.assertIn(message["type"], {"replay", "event"})
            self.assertIn(message["event"]["topic"], {"order", "trade"})
        finally:
            self.broker.close_stream(stream_id)

    def test_async_order_tracks_seq_and_reaches_executed(self) -> None:
        result = self.broker.place_order(
            {
                "account_id": "mock-stock",
                "symbol": "600000.SH",
                "side": "buy",
                "volume": 100,
                "price": 10.5,
                "async": True,
            }
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "accepted")
        request = self.broker.request_by_seq(str(result["result"]["seq"]))
        self.assertIsNotNone(request)

        import time

        deadline = time.time() + 2.0
        while time.time() < deadline:
            status = self.broker.request_status(result["request_id"])
            if status["status"] == "executed":
                break
            time.sleep(0.05)
        status = self.broker.request_status(result["request_id"])
        self.assertEqual(status["status"], "executed")

    def test_account_statuses_are_exposed(self) -> None:
        self.broker.get_asset("mock-stock")
        statuses = self.broker.account_statuses()
        infos = self.broker.account_infos()
        self.assertTrue(any(item["account_id"] == "mock-stock" for item in statuses))
        self.assertTrue(any(item["account_id"] == "mock-stock" for item in infos))

    def test_policy_blocks_symbol(self) -> None:
        broker = TradeBroker(
            self.provider,
            BrokerConfig(
                stream_queue_size=32,
                trade_audit_log_path=self.audit_path,
                allowed_symbols=("000001.SZ",),
            ),
        )
        try:
            result = broker.place_order(
                {
                    "account_id": "mock-stock",
                    "symbol": "600000.SH",
                    "side": "buy",
                    "volume": 100,
                    "price": 10.5,
                }
            )
            self.assertFalse(result["ok"])
            self.assertEqual(result["error"]["code"], "symbol_not_allowed")
        finally:
            broker.close()

    def test_audit_tail_contains_actions(self) -> None:
        self.broker.place_order(
            {
                "account_id": "mock-stock",
                "symbol": "600000.SH",
                "side": "buy",
                "volume": 100,
                "price": 10.5,
            }
        )
        tail = self.broker.audit_tail(10)
        self.assertTrue(any(item["kind"] == "trade_action" and item["action"] == "place_order" for item in tail))

    def test_credit_queries(self) -> None:
        detail = self.broker.get_credit_detail("mock-credit", "CREDIT")
        self.assertIsNotNone(detail)
        subjects = self.broker.get_credit_subjects("mock-credit", "CREDIT")
        self.assertGreaterEqual(len(subjects), 1)

    def test_pending_approval_flow(self) -> None:
        broker = TradeBroker(
            self.provider,
            BrokerConfig(
                stream_queue_size=32,
                trade_audit_log_path=self.audit_path,
                trade_state_store_path=self.state_path,
                require_order_approval=True,
            ),
        )
        try:
            created = broker.place_order(
                {
                    "account_id": "mock-stock",
                    "symbol": "600000.SH",
                    "side": "buy",
                    "volume": 100,
                    "price": 10.5,
                }
            )
            self.assertTrue(created["pending"])
            request_id = created["request_id"]
            status = broker.request_status(request_id)
            self.assertEqual(status["status"], "pending")
            approved = broker.approve_order(request_id)
            self.assertTrue(approved["ok"])
            status = broker.request_status(request_id)
            self.assertEqual(status["status"], "executed")
        finally:
            broker.close()

    def test_pending_approval_requires_approver_secret(self) -> None:
        broker = TradeBroker(
            self.provider,
            BrokerConfig(
                stream_queue_size=32,
                trade_audit_log_path=self.audit_path,
                trade_state_store_path=self.state_path,
                require_order_approval=True,
                approver_secrets={"alice": "secret-a"},
            ),
        )
        try:
            created = broker.place_order(
                {
                    "account_id": "mock-stock",
                    "symbol": "600000.SH",
                    "side": "buy",
                    "volume": 100,
                    "price": 10.5,
                }
            )
            denied = broker.approve_order_as(created["request_id"], approver_id="alice", approver_secret="wrong")
            self.assertFalse(denied["ok"])
            approved = broker.approve_order_as(created["request_id"], approver_id="alice", approver_secret="secret-a")
            self.assertTrue(approved["ok"])
            self.assertEqual(approved["status"], "executed")
        finally:
            broker.close()

    def test_pending_approval_can_require_two_approvers(self) -> None:
        broker = TradeBroker(
            self.provider,
            BrokerConfig(
                stream_queue_size=32,
                trade_audit_log_path=self.audit_path,
                trade_state_store_path=self.state_path,
                require_order_approval=True,
                approval_min_approvers=2,
                approver_secrets={"alice": "secret-a", "bob": "secret-b"},
            ),
        )
        try:
            created = broker.place_order(
                {
                    "account_id": "mock-stock",
                    "symbol": "600000.SH",
                    "side": "buy",
                    "volume": 100,
                    "price": 10.5,
                }
            )
            first = broker.approve_order_as(created["request_id"], approver_id="alice", approver_secret="secret-a")
            self.assertTrue(first["pending"])
            second = broker.approve_order_as(created["request_id"], approver_id="bob", approver_secret="secret-b")
            self.assertTrue(second["ok"])
            self.assertEqual(second["status"], "executed")
        finally:
            broker.close()

    def test_reject_pending_request(self) -> None:
        broker = TradeBroker(
            self.provider,
            BrokerConfig(
                stream_queue_size=32,
                trade_audit_log_path=self.audit_path,
                trade_state_store_path=self.state_path,
                require_order_approval=True,
            ),
        )
        try:
            created = broker.place_order(
                {
                    "account_id": "mock-stock",
                    "symbol": "600000.SH",
                    "side": "buy",
                    "volume": 100,
                    "price": 10.5,
                }
            )
            rejected = broker.reject_order(created["request_id"], "manual deny")
            self.assertTrue(rejected["ok"])
            self.assertEqual(rejected["status"], "rejected")
        finally:
            broker.close()

    def test_revoke_pending_request(self) -> None:
        broker = TradeBroker(
            self.provider,
            BrokerConfig(
                stream_queue_size=32,
                trade_audit_log_path=self.audit_path,
                trade_state_store_path=self.state_path,
                require_order_approval=True,
            ),
        )
        try:
            created = broker.place_order(
                {
                    "account_id": "mock-stock",
                    "symbol": "600000.SH",
                    "side": "buy",
                    "volume": 100,
                    "price": 10.5,
                }
            )
            revoked = broker.revoke_order(created["request_id"], "user canceled")
            self.assertTrue(revoked["ok"])
            self.assertEqual(revoked["status"], "revoked")
        finally:
            broker.close()

    def test_idempotency_key_reuses_result(self) -> None:
        payload = {
            "account_id": "mock-stock",
            "symbol": "600000.SH",
            "side": "buy",
            "volume": 100,
            "price": 10.5,
            "idempotency_key": "abc-123",
        }
        first = self.broker.place_order(payload)
        second = self.broker.place_order(payload)
        self.assertTrue(first["ok"])
        self.assertTrue(second["ok"])
        self.assertTrue(second["reused"])
        self.assertEqual(first["request_id"], second["request_id"])

    def test_state_persists_across_restart(self) -> None:
        broker1 = TradeBroker(
            self.provider,
            BrokerConfig(
                stream_queue_size=32,
                trade_audit_log_path=self.audit_path,
                trade_state_store_path=self.state_path,
                require_order_approval=True,
            ),
        )
        try:
            created = broker1.place_order(
                {
                    "account_id": "mock-stock",
                    "symbol": "600000.SH",
                    "side": "buy",
                    "volume": 100,
                    "price": 10.5,
                    "idempotency_key": "persist-1",
                }
            )
            request_id = created["request_id"]
        finally:
            broker1.close()
        broker2 = TradeBroker(
            MockTradeProvider(),
            BrokerConfig(
                stream_queue_size=32,
                trade_audit_log_path=self.audit_path,
                trade_state_store_path=self.state_path,
                require_order_approval=True,
            ),
        )
        try:
            status = broker2.request_status(request_id)
            self.assertIsNotNone(status)
            self.assertEqual(status["status"], "pending")
            reused = broker2.place_order(
                {
                    "account_id": "mock-stock",
                    "symbol": "600000.SH",
                    "side": "buy",
                    "volume": 100,
                    "price": 10.5,
                    "idempotency_key": "persist-1",
                }
            )
            self.assertTrue(reused["reused"])
            self.assertEqual(reused["request_id"], request_id)
        finally:
            broker2.close()

    def test_pending_request_expires(self) -> None:
        broker = TradeBroker(
            self.provider,
            BrokerConfig(
                stream_queue_size=32,
                trade_audit_log_path=self.audit_path,
                trade_state_store_path=self.state_path,
                require_order_approval=True,
                approval_pending_ttl_sec=1,
            ),
        )
        try:
            created = broker.place_order(
                {
                    "account_id": "mock-stock",
                    "symbol": "600000.SH",
                    "side": "buy",
                    "volume": 100,
                    "price": 10.5,
                }
            )
            import time

            time.sleep(1.1)
            status = broker.request_status(created["request_id"])
            self.assertEqual(status["status"], "expired")
        finally:
            broker.close()

    def test_pending_request_sends_pending_and_reminder_notifications(self) -> None:
        NotificationCaptureHandler.events = []
        notification_server = ThreadingHTTPServer(("127.0.0.1", 0), NotificationCaptureHandler)
        notification_thread = threading.Thread(target=notification_server.serve_forever, daemon=True)
        notification_thread.start()
        webhook_url = "http://127.0.0.1:%s" % notification_server.server_address[1]
        broker = TradeBroker(
            self.provider,
            BrokerConfig(
                stream_queue_size=32,
                trade_audit_log_path=self.audit_path,
                trade_state_store_path=self.state_path,
                require_order_approval=True,
                approval_pending_ttl_sec=2,
                approval_reminder_before_sec=1,
                approval_webhook_urls=(webhook_url,),
            ),
        )
        try:
            created = broker.place_order(
                {
                    "account_id": "mock-stock",
                    "symbol": "600000.SH",
                    "side": "buy",
                    "volume": 100,
                    "price": 10.5,
                }
            )
            import time

            time.sleep(1.2)
            status = broker.request_status(created["request_id"])
            self.assertGreater(int(status.get("reminder_sent_at_ms", 0)), 0)
            joined = "\n".join(NotificationCaptureHandler.events)
            self.assertIn("approval_pending", joined)
            self.assertIn("approval_reminder", joined)
        finally:
            broker.close()
            notification_server.shutdown()
            notification_server.server_close()
            notification_thread.join(timeout=1.0)


if __name__ == "__main__":
    unittest.main()
