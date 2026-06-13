import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings  # type: ignore
from app.models import CancelOrderRequest, ProcessOrdersRequest, SubmitOrderRequest, TerminalSessionControlRequest  # type: ignore
from app.services import BrokerDaemonService, QmtTerminalAdapter, TerminalAdapterError  # type: ignore


class BrokerDaemonRegressionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.old_state_path = settings.state_path
        self.old_live_routing = settings.live_routing_enabled
        self.old_terminal_adapter = settings.terminal_adapter
        self.old_simulated_fill_mode = settings.simulated_fill_mode
        self.old_qmt_terminal_path = settings.qmt_terminal_path
        self.old_qmt_account_alias = settings.qmt_account_alias
        self.old_qmt_credential_profile = settings.qmt_credential_profile
        self.old_qmt_process_name = settings.qmt_process_name
        self.old_qmt_pid_file_path = settings.qmt_pid_file_path
        self.old_qmt_session_file_path = settings.qmt_session_file_path
        self.old_qmt_lock_file_path = settings.qmt_lock_file_path
        self.old_qmt_singleton_required = settings.qmt_singleton_required
        self.old_qmt_start_command = settings.qmt_start_command
        self.old_qmt_working_directory = settings.qmt_working_directory
        settings.state_path = f"{self.tmp.name}/brokerd-state.json"
        settings.live_routing_enabled = False
        settings.terminal_adapter = "simulated"
        settings.simulated_fill_mode = "immediate"
        settings.qmt_terminal_path = None
        settings.qmt_account_alias = None
        settings.qmt_credential_profile = None
        settings.qmt_process_name = None
        settings.qmt_pid_file_path = None
        settings.qmt_session_file_path = None
        settings.qmt_lock_file_path = None
        settings.qmt_singleton_required = True
        settings.qmt_start_command = None
        settings.qmt_working_directory = None
        self.service = BrokerDaemonService(settings.state_path)

    def tearDown(self):
        settings.state_path = self.old_state_path
        settings.live_routing_enabled = self.old_live_routing
        settings.terminal_adapter = self.old_terminal_adapter
        settings.simulated_fill_mode = self.old_simulated_fill_mode
        settings.qmt_terminal_path = self.old_qmt_terminal_path
        settings.qmt_account_alias = self.old_qmt_account_alias
        settings.qmt_credential_profile = self.old_qmt_credential_profile
        settings.qmt_process_name = self.old_qmt_process_name
        settings.qmt_pid_file_path = self.old_qmt_pid_file_path
        settings.qmt_session_file_path = self.old_qmt_session_file_path
        settings.qmt_lock_file_path = self.old_qmt_lock_file_path
        settings.qmt_singleton_required = self.old_qmt_singleton_required
        settings.qmt_start_command = self.old_qmt_start_command
        settings.qmt_working_directory = self.old_qmt_working_directory
        self.tmp.cleanup()

    def test_submit_cancel_and_query(self):
        connected = self.service.connect_session(
            TerminalSessionControlRequest(
                reason="unit_test_connect",
                terminal_path="C:/QMT/QMT.exe",
                account_alias="招商QMT",
            )
        )
        logged_in = self.service.login_session(TerminalSessionControlRequest(credential_profile="unit_test_profile"))
        submitted = self.service.submit_order(
            SubmitOrderRequest(
                account_id="acct-1",
                symbol="600519.SH",
                side="buy",
                order_type="limit",
                price=10.0,
                quantity=100,
                adapter="qmt",
            )
        )
        orders = self.service.orders("acct-1")
        account = self.service.account("acct-1")
        session = self.service.session_health_check()
        canceled = self.service.cancel_order(
            CancelOrderRequest(
                account_id="acct-1",
                broker_order_id=submitted.broker_order_id,
                reason="unit_test_cancel",
                adapter="qmt",
            )
        )
        orders_after = self.service.orders("acct-1")

        self.assertEqual(connected.session.account_alias, "招商QMT")
        self.assertEqual(logged_in.session.credential_profile, "unit_test_profile")
        self.assertEqual(submitted.status, "accepted")
        self.assertEqual(submitted.detail, "simulated_fill_complete")
        self.assertEqual(submitted.fill_quantity, 100)
        self.assertEqual(len(orders.orders), 1)
        self.assertEqual(orders.orders[0].status, "filled")
        self.assertEqual(account.cash, settings.default_account_cash - round(submitted.fill_price * 100, 2))
        self.assertEqual(session.session_state, "ready")
        self.assertEqual(session.health_state, "ok")
        self.assertEqual(canceled.status, "rejected")
        self.assertEqual(canceled.detail, "already_filled_or_partially_filled")
        self.assertEqual(orders_after.orders[0].status, "filled")

    def test_queued_processing_and_rejection(self):
        settings.simulated_fill_mode = "queued"
        self.service = BrokerDaemonService(settings.state_path)
        queued_buy = self.service.submit_order(
            SubmitOrderRequest(
                account_id="acct-2",
                symbol="600519.SH",
                side="buy",
                order_type="limit",
                price=settings.default_account_cash * 2,
                quantity=100,
                adapter="qmt",
            )
        )
        queued_sell = self.service.submit_order(
            SubmitOrderRequest(
                account_id="acct-2",
                symbol="600519.SH",
                side="sell",
                order_type="limit",
                price=10.0,
                quantity=100,
                adapter="qmt",
            )
        )
        process = self.service.process_orders(ProcessOrdersRequest(account_id="acct-2", limit=10))
        orders = self.service.orders("acct-2")
        self.assertEqual(queued_buy.detail, "queued_for_processing")
        self.assertEqual(queued_sell.detail, "queued_for_processing")
        self.assertEqual(process.rejected_count, 2)
        self.assertEqual(process.remaining_queued_count, 0)
        self.assertEqual([order.status for order in orders.orders], ["rejected", "rejected"])

    def test_qmt_terminal_placeholder_raises(self):
        adapter = QmtTerminalAdapter(self.service.state_store)
        with self.assertRaises(TerminalAdapterError):
            adapter.account("acct-1")
        self.assertEqual(adapter.session_status().detail, "qmt_terminal_not_implemented")
        connect = adapter.connect_session(TerminalSessionControlRequest(reason="placeholder"))
        self.assertEqual(connect.detail, "placeholder_only")
        health = adapter.session_health_check()
        self.assertEqual(health.health_state, "unavailable")
        self.assertEqual(health.detail, "qmt_terminal_path_missing")
        preflight = adapter.preflight()
        self.assertEqual(preflight.status, "error")

    def test_qmt_health_checks_host_prerequisites(self):
        terminal_path = Path(self.tmp.name) / "QMT.exe"
        terminal_path.write_text("placeholder", encoding="utf-8")
        settings.qmt_terminal_path = str(terminal_path)
        settings.qmt_account_alias = "招商QMT"
        settings.qmt_credential_profile = "招商凭据"
        settings.qmt_lock_file_path = str(Path(self.tmp.name) / "qmt.lock")
        settings.qmt_start_command = "start-qmt.cmd"
        adapter = QmtTerminalAdapter(self.service.state_store)

        adapter.connect_session(TerminalSessionControlRequest(reason="host_check"))
        adapter.login_session(TerminalSessionControlRequest(reason="host_login"))
        logged_in = adapter.session_health_check()
        self.assertEqual(logged_in.health_state, "degraded")
        self.assertEqual(logged_in.detail, "qmt_terminal_placeholder_logged_in")
        self.assertIsNotNone(logged_in.host_state)
        assert logged_in.host_state is not None
        self.assertTrue(logged_in.host_state.terminal_path_exists)
        self.assertEqual(logged_in.host_state.lock.lock_file_path, settings.qmt_lock_file_path)
        preflight = adapter.preflight()
        self.assertEqual(preflight.status, "warn")

        Path(settings.qmt_lock_file_path).unlink()
        degraded = adapter.session_health_check()
        self.assertEqual(degraded.health_state, "degraded")
        self.assertEqual(degraded.detail, "qmt_singleton_not_detected")

    def test_qmt_health_reads_pid_and_session_markers(self):
        terminal_path = Path(self.tmp.name) / "QMT.exe"
        terminal_path.write_text("placeholder", encoding="utf-8")
        session_file = Path(self.tmp.name) / "qmt.session"
        session_file.write_text("ready", encoding="utf-8")
        pid_file = Path(self.tmp.name) / "qmt.pid"
        pid_file.write_text(str(os.getpid()), encoding="utf-8")
        settings.qmt_terminal_path = str(terminal_path)
        settings.qmt_account_alias = "招商QMT"
        settings.qmt_credential_profile = "招商凭据"
        settings.qmt_process_name = "python"
        settings.qmt_pid_file_path = str(pid_file)
        settings.qmt_session_file_path = str(session_file)
        settings.qmt_singleton_required = True
        settings.qmt_start_command = "start-qmt.cmd"
        adapter = QmtTerminalAdapter(self.service.state_store)

        adapter.connect_session(TerminalSessionControlRequest(reason="host_check"))
        health = adapter.session_health_check()
        self.assertTrue(health.process_detected)
        self.assertTrue(health.pid_file_present)
        self.assertTrue(health.session_file_present)
        self.assertTrue(health.singleton_ok)
        self.assertEqual(health.detail, "qmt_terminal_placeholder_connected")
        self.assertEqual(adapter.preflight().status, "warn")

    def test_qmt_start_command_and_lock_management(self):
        terminal_path = Path(self.tmp.name) / "QMT.exe"
        terminal_path.write_text("placeholder", encoding="utf-8")
        working_directory = Path(self.tmp.name) / "qmt-home"
        working_directory.mkdir()
        lock_file = Path(self.tmp.name) / "qmt.lock"
        settings.qmt_terminal_path = str(terminal_path)
        settings.qmt_account_alias = "招商QMT"
        settings.qmt_credential_profile = "招商凭据"
        settings.qmt_lock_file_path = str(lock_file)
        settings.qmt_start_command = "start-qmt.cmd"
        settings.qmt_working_directory = str(working_directory)
        adapter = QmtTerminalAdapter(self.service.state_store)

        connected = adapter.connect_session(TerminalSessionControlRequest(operator_id="unit", reason="connect"))
        self.assertEqual(connected.status, "accepted")
        self.assertTrue(lock_file.exists())
        self.assertTrue(connected.session.lock_owned)

        conflict = adapter.connect_session(TerminalSessionControlRequest(operator_id="unit2", reason="connect2"))
        self.assertEqual(conflict.status, "rejected")
        self.assertEqual(conflict.detail, "qmt_singleton_lock_conflict")

        disconnected = adapter.disconnect_session(TerminalSessionControlRequest(operator_id="unit", reason="done"))
        self.assertEqual(disconnected.status, "accepted")
        self.assertFalse(lock_file.exists())

    def test_qmt_start_dry_run_preflight(self):
        terminal_path = Path(self.tmp.name) / "QMT.exe"
        terminal_path.write_text("placeholder", encoding="utf-8")
        working_directory = Path(self.tmp.name) / "qmt-home"
        working_directory.mkdir()
        lock_file = Path(self.tmp.name) / "qmt.lock"
        settings.qmt_terminal_path = str(terminal_path)
        settings.qmt_account_alias = "招商QMT"
        settings.qmt_credential_profile = "招商凭据"
        settings.qmt_lock_file_path = str(lock_file)
        settings.qmt_start_command = "start-qmt.cmd"
        settings.qmt_working_directory = str(working_directory)
        adapter = QmtTerminalAdapter(self.service.state_store)

        start = adapter.start_terminal(TerminalSessionControlRequest(operator_id="starter", reason="manual_start"))
        self.assertEqual(start.status, "accepted")
        self.assertEqual(start.detail, "qmt_start_plan_ready")
        self.assertEqual(start.session.session_state, "start_plan_ready")
        self.assertIsNotNone(start.launch_plan)
        assert start.launch_plan is not None
        self.assertTrue(start.launch_plan.runnable)
        self.assertEqual(start.launch_plan.status, "ready")
        self.assertEqual(start.launch_plan.command, "start-qmt.cmd")
        self.assertEqual(start.launch_plan.working_directory, str(working_directory))
        self.assertIn("launch_terminal_command", start.launch_plan.steps)
        self.assertIn("run_start_command_on_broker_host", start.launch_plan.next_actions)
        self.assertIsNotNone(start.session.host_state)
        assert start.session.host_state is not None
        self.assertEqual(start.session.host_state.lock.lock_file_path, str(lock_file))
        self.assertFalse(start.session.host_state.lock.lock_present)
        self.assertFalse(start.session.host_state.lock.lock_owned)


if __name__ == "__main__":
    unittest.main()
