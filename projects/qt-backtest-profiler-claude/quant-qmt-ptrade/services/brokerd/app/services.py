from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import shlex
import subprocess
from threading import Lock
from uuid import uuid4

from .config import settings
from .models import (
    BrokerAccountSummary,
    BrokerCancelResponse,
    BrokerOrderRecord,
    BrokerOrderResponse,
    BrokerOrdersResponse,
    BrokerPosition,
    BrokerPositionsResponse,
    CancelOrderRequest,
    DaemonStatusResponse,
    ProcessOrdersRequest,
    ProcessOrdersResponse,
    SubmitOrderRequest,
    TerminalHostState,
    TerminalLaunchPlan,
    TerminalLockState,
    TerminalPreflightCheck,
    TerminalPreflightResponse,
    TerminalProcessState,
    TerminalSessionArtifactState,
    TerminalSessionControlRequest,
    TerminalSessionControlResponse,
    TerminalSessionStatus,
)


def _now() -> datetime:
    return datetime.now(UTC)


class BrokerStateStore:
    def __init__(self, state_path: str | None = None) -> None:
        self._state_path = Path(state_path or settings.state_path).expanduser()
        self._lock = Lock()

    def load(self) -> dict:
        with self._lock:
            return self._load_locked()

    def update(self, updater) -> dict:
        with self._lock:
            state = self._load_locked()
            updated = updater(state)
            self._persist_locked(updated)
            return updated

    def ensure_account(self, state: dict, account_id: str) -> None:
        if account_id not in state["accounts"]:
            state["accounts"][account_id] = {
                "cash": settings.default_account_cash,
                "available_cash": settings.default_account_cash,
            }
        if account_id not in state["positions"]:
            state["positions"][account_id] = {}

    def ensure_session(self, state: dict, session: dict | None = None) -> None:
        if "session" not in state:
            state["session"] = session or {}

    def _load_locked(self) -> dict:
        if not self._state_path.exists():
            return {"accounts": {}, "orders": [], "positions": {}, "session": {}}
        try:
            return json.loads(self._state_path.read_text(encoding="utf-8"))
        except Exception:
            return {"accounts": {}, "orders": [], "positions": {}, "session": {}}

    def _persist_locked(self, payload: dict) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class TerminalAdapterError(RuntimeError):
    pass


class TerminalAdapter(ABC):
    def __init__(self, state_store: BrokerStateStore) -> None:
        self.state_store = state_store
        self._last_heartbeat_at: datetime | None = None

    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    def _heartbeat(self) -> datetime:
        self._last_heartbeat_at = _now()
        return self._last_heartbeat_at

    @abstractmethod
    def session_status(self) -> TerminalSessionStatus:
        raise NotImplementedError

    def session_health_check(self) -> TerminalSessionStatus:
        return self.session_status()

    @abstractmethod
    def preflight(self) -> TerminalPreflightResponse:
        raise NotImplementedError

    @abstractmethod
    def connect_session(self, request: TerminalSessionControlRequest) -> TerminalSessionControlResponse:
        raise NotImplementedError

    @abstractmethod
    def login_session(self, request: TerminalSessionControlRequest) -> TerminalSessionControlResponse:
        raise NotImplementedError

    @abstractmethod
    def disconnect_session(self, request: TerminalSessionControlRequest) -> TerminalSessionControlResponse:
        raise NotImplementedError

    @abstractmethod
    def start_terminal(self, request: TerminalSessionControlRequest) -> TerminalSessionControlResponse:
        raise NotImplementedError

    @abstractmethod
    def process_orders(self, request: ProcessOrdersRequest) -> ProcessOrdersResponse:
        raise NotImplementedError

    @abstractmethod
    def submit_order(self, request: SubmitOrderRequest) -> BrokerOrderResponse:
        raise NotImplementedError

    @abstractmethod
    def cancel_order(self, request: CancelOrderRequest) -> BrokerCancelResponse:
        raise NotImplementedError

    @abstractmethod
    def orders(self, account_id: str) -> BrokerOrdersResponse:
        raise NotImplementedError

    @abstractmethod
    def positions(self, account_id: str) -> BrokerPositionsResponse:
        raise NotImplementedError

    @abstractmethod
    def account(self, account_id: str) -> BrokerAccountSummary:
        raise NotImplementedError


class SimulatedTerminalAdapter(TerminalAdapter):
    @property
    def name(self) -> str:
        return "simulated"

    def session_status(self) -> TerminalSessionStatus:
        state = self.state_store.load()
        session = state.get("session") or {}
        if session:
            return TerminalSessionStatus.model_validate(session)
        return TerminalSessionStatus(
            adapter=self.name,
            session_state="ready",
            health_state="ok",
            connected=True,
            logged_in=True,
            last_heartbeat_at=self._last_heartbeat_at,
            detail="simulated_terminal_ready",
        )

    def preflight(self) -> TerminalPreflightResponse:
        session = self.session_status()
        return TerminalPreflightResponse(
            adapter=self.name,
            status="ok",
            checks=[
                TerminalPreflightCheck(name="adapter_mode", status="ok", detail="simulated"),
                TerminalPreflightCheck(name="fill_mode", status="ok", detail=settings.simulated_fill_mode),
            ],
            session=session,
        )

    def connect_session(self, request: TerminalSessionControlRequest) -> TerminalSessionControlResponse:
        self._heartbeat()
        session = TerminalSessionStatus(
            adapter=self.name,
            session_state="connected",
            health_state="ok",
            connected=True,
            logged_in=False,
            terminal_path=request.terminal_path,
            account_alias=request.account_alias,
            credential_profile=request.credential_profile,
            last_heartbeat_at=self._last_heartbeat_at,
            detail=request.reason or "simulated_connected",
        )
        self.state_store.update(lambda state: self._write_session(state, session))
        return TerminalSessionControlResponse(action="connect", status="accepted", session=session)

    def login_session(self, request: TerminalSessionControlRequest) -> TerminalSessionControlResponse:
        self._heartbeat()
        session = TerminalSessionStatus(
            adapter=self.name,
            session_state="ready",
            health_state="ok",
            connected=True,
            logged_in=True,
            terminal_path=request.terminal_path,
            account_alias=request.account_alias,
            credential_profile=request.credential_profile,
            last_heartbeat_at=self._last_heartbeat_at,
            detail=request.credential_profile or "simulated_logged_in",
        )
        self.state_store.update(lambda state: self._write_session(state, session))
        return TerminalSessionControlResponse(action="login", status="accepted", session=session)

    def disconnect_session(self, request: TerminalSessionControlRequest) -> TerminalSessionControlResponse:
        self._heartbeat()
        session = TerminalSessionStatus(
            adapter=self.name,
            session_state="disconnected",
            health_state="idle",
            connected=False,
            logged_in=False,
            terminal_path=request.terminal_path,
            account_alias=request.account_alias,
            credential_profile=request.credential_profile,
            last_heartbeat_at=self._last_heartbeat_at,
            detail=request.reason or "simulated_disconnected",
        )
        self.state_store.update(lambda state: self._write_session(state, session))
        return TerminalSessionControlResponse(action="disconnect", status="accepted", session=session)

    def start_terminal(self, request: TerminalSessionControlRequest) -> TerminalSessionControlResponse:
        self._heartbeat()
        session = self.session_status()
        session.detail = request.reason or "simulated_start_noop"
        session.last_heartbeat_at = self._last_heartbeat_at
        self.state_store.update(lambda state: self._write_session(state, session))
        return TerminalSessionControlResponse(action="start", status="accepted", detail="simulated_start_noop", session=session)

    def submit_order(self, request: SubmitOrderRequest) -> BrokerOrderResponse:
        self._heartbeat()
        submitted_at = _now()
        broker_order_id = f"daemon_ord_{uuid4().hex[:10]}"
        routed_order_id = f"{settings.adapter_name}_route_{uuid4().hex[:8]}"
        order = {
            "broker_order_id": broker_order_id,
            "account_id": request.account_id,
            "symbol": request.symbol,
            "side": request.side,
            "order_type": request.order_type,
            "price": request.price,
            "quantity": request.quantity,
            "status": "queued",
            "submitted_at": submitted_at.isoformat(),
            "routed_order_id": routed_order_id,
            "fill_price": 0.0,
            "fill_quantity": 0,
            "detail": "queued_for_processing",
        }

        def updater(state: dict) -> dict:
            self.state_store.ensure_account(state, request.account_id)
            state["orders"].append(order)
            if settings.simulated_fill_mode == "immediate":
                self._execute_order_locked(state, order)
            return state

        self.state_store.update(updater)
        return BrokerOrderResponse(
            broker_order_id=broker_order_id,
            adapter_mode="qmt_bridge",
            dry_run=False,
            status="accepted",
            submitted_at=submitted_at,
            approval_required=False,
            risk_status="approved",
            routed_order_id=routed_order_id,
            fill_price=float(order["fill_price"]),
            fill_quantity=int(order["fill_quantity"]),
            detail=str(order["detail"]),
        )

    def process_orders(self, request: ProcessOrdersRequest) -> ProcessOrdersResponse:
        self._heartbeat()
        processed_count = 0
        filled_count = 0
        rejected_count = 0
        updated_order_ids: list[str] = []

        def updater(state: dict) -> dict:
            nonlocal processed_count, filled_count, rejected_count
            for order in state["orders"]:
                if request.account_id and order.get("account_id") != request.account_id:
                    continue
                if str(order.get("status")) != "queued":
                    continue
                self._execute_order_locked(state, order)
                processed_count += 1
                updated_order_ids.append(str(order["broker_order_id"]))
                if str(order["status"]) in {"filled", "partially_filled"}:
                    filled_count += 1
                elif str(order["status"]) == "rejected":
                    rejected_count += 1
                if processed_count >= request.limit:
                    break
            return state

        updated = self.state_store.update(updater)
        remaining_queued = sum(
            1
            for order in updated["orders"]
            if (not request.account_id or order.get("account_id") == request.account_id) and str(order.get("status")) == "queued"
        )
        return ProcessOrdersResponse(
            status="ok",
            processed_count=processed_count,
            filled_count=filled_count,
            rejected_count=rejected_count,
            remaining_queued_count=remaining_queued,
            updated_order_ids=updated_order_ids,
        )

    def session_health_check(self) -> TerminalSessionStatus:
        self._heartbeat()
        state = self.state_store.load()
        session = state.get("session") or {}
        if session:
            parsed = TerminalSessionStatus.model_validate(session)
            parsed.health_state = "ok" if parsed.connected else "idle"
            parsed.last_heartbeat_at = self._last_heartbeat_at
            self.state_store.update(lambda current: self._write_session(current, parsed))
            return parsed
        status = self.session_status()
        self.state_store.update(lambda current: self._write_session(current, status))
        return status

    def cancel_order(self, request: CancelOrderRequest) -> BrokerCancelResponse:
        self._heartbeat()
        response: BrokerCancelResponse | None = None

        def updater(state: dict) -> dict:
            nonlocal response
            for order in reversed(state["orders"]):
                if order.get("account_id") != request.account_id:
                    continue
                if order.get("broker_order_id") != request.broker_order_id:
                    continue
                if str(order.get("status")) in {"filled", "partially_filled"}:
                    response = BrokerCancelResponse(
                        broker_order_id=request.broker_order_id,
                        adapter_mode="qmt_bridge",
                        dry_run=False,
                        status="rejected",
                        canceled_at=_now(),
                        approval_required=False,
                        routed_order_id=str(order.get("routed_order_id") or ""),
                        detail="already_filled_or_partially_filled",
                    )
                    break
                order["status"] = "canceled"
                order["detail"] = request.reason or "operator_canceled"
                response = BrokerCancelResponse(
                    broker_order_id=request.broker_order_id,
                    adapter_mode="qmt_bridge",
                    dry_run=False,
                    status="accepted",
                    canceled_at=_now(),
                    approval_required=False,
                    routed_order_id=str(order.get("routed_order_id") or ""),
                    detail=str(order.get("detail")),
                )
                break
            return state

        self.state_store.update(updater)
        if response is None:
            return BrokerCancelResponse(
                broker_order_id=request.broker_order_id,
                adapter_mode="qmt_bridge",
                dry_run=False,
                status="rejected",
                canceled_at=_now(),
                approval_required=False,
                detail="order_not_found",
            )
        return response

    def orders(self, account_id: str) -> BrokerOrdersResponse:
        self._heartbeat()
        state = self.state_store.load()
        orders = [
            BrokerOrderRecord(
                broker_order_id=str(order["broker_order_id"]),
                account_id=str(order["account_id"]),
                symbol=str(order["symbol"]),
                side=str(order["side"]),
                order_type=str(order["order_type"]),
                price=float(order["price"]),
                quantity=int(order["quantity"]),
                status=str(order["status"]),
                submitted_at=datetime.fromisoformat(str(order["submitted_at"])),
                routed_order_id=str(order.get("routed_order_id") or "") or None,
                fill_price=float(order.get("fill_price", 0.0)),
                fill_quantity=int(order.get("fill_quantity", 0)),
                detail=str(order.get("detail")) if order.get("detail") is not None else None,
            )
            for order in state["orders"]
            if order.get("account_id") == account_id
        ]
        orders.sort(key=lambda item: item.submitted_at, reverse=True)
        return BrokerOrdersResponse(account_id=account_id, adapter_mode="qmt_bridge", status="ok", orders=orders)

    def positions(self, account_id: str) -> BrokerPositionsResponse:
        self._heartbeat()
        state = self.state_store.load()
        self.state_store.ensure_account(state, account_id)
        positions: list[BrokerPosition] = []
        for symbol, payload in sorted(state["positions"].get(account_id, {}).items()):
            quantity = int(payload.get("quantity", 0))
            if quantity <= 0:
                continue
            avg_cost = float(payload.get("avg_cost", 0.0))
            last_price = float(payload.get("last_price", avg_cost))
            market_value = round(last_price * quantity, 2)
            unrealized_pnl = round((last_price - avg_cost) * quantity, 2)
            positions.append(
                BrokerPosition(
                    account_id=account_id,
                    symbol=symbol,
                    quantity=quantity,
                    avg_cost=avg_cost,
                    last_price=last_price,
                    market_value=market_value,
                    unrealized_pnl=unrealized_pnl,
                    unrealized_pnl_pct=round(((last_price / avg_cost) - 1) * 100, 3) if avg_cost else 0.0,
                    updated_at=_now(),
                )
            )
        return BrokerPositionsResponse(account_id=account_id, adapter_mode="qmt_bridge", status="ok", positions=positions)

    def account(self, account_id: str) -> BrokerAccountSummary:
        self._heartbeat()
        state = self.state_store.load()
        self.state_store.ensure_account(state, account_id)
        account = state["accounts"][account_id]
        positions = self.positions(account_id)
        market_value = round(sum(item.market_value for item in positions.positions), 2)
        equity = round(float(account["cash"]) + market_value, 2)
        return BrokerAccountSummary(
            account_id=account_id,
            adapter_mode="qmt_bridge",
            status="ok",
            cash=round(float(account["cash"]), 2),
            available_cash=round(float(account["available_cash"]), 2),
            market_value=market_value,
            equity=equity,
            positions_count=len(positions.positions),
            updated_at=_now(),
        )

    def _write_session(self, state: dict, session: TerminalSessionStatus) -> dict:
        self.state_store.ensure_session(state)
        state["session"] = session.model_dump(mode="json")
        return state

    def _execute_order_locked(self, state: dict, order: dict) -> None:
        self.state_store.ensure_account(state, str(order["account_id"]))
        account = state["accounts"][str(order["account_id"])]
        positions = state["positions"][str(order["account_id"])]
        fill_price = round(float(order["price"]) * (1 + settings.simulated_last_price_markup_bps / 10000), 4)
        requested_quantity = int(order["quantity"])
        max_fill_shares = max(settings.simulated_fill_shares, 0)
        fill_quantity = min(requested_quantity, max_fill_shares)
        if str(order["side"]) == "buy":
            affordable_quantity = int(float(account["available_cash"]) // fill_price) if fill_price > 0 else 0
            fill_quantity = min(fill_quantity, affordable_quantity)
            if fill_quantity <= 0:
                order["status"] = "rejected"
                order["detail"] = "insufficient_cash"
                order["fill_price"] = 0.0
                order["fill_quantity"] = 0
                return
            total_cost = fill_price * fill_quantity
            account["cash"] = round(float(account["cash"]) - total_cost, 2)
            account["available_cash"] = round(float(account["available_cash"]) - total_cost, 2)
            position = positions.setdefault(
                str(order["symbol"]),
                {"quantity": 0, "avg_cost": 0.0, "last_price": fill_price},
            )
            existing_qty = int(position.get("quantity", 0))
            existing_avg = float(position.get("avg_cost", 0.0))
            new_total_cost = existing_avg * existing_qty + total_cost
            new_qty = existing_qty + fill_quantity
            position["quantity"] = new_qty
            position["avg_cost"] = round(new_total_cost / new_qty, 4) if new_qty else 0.0
            position["last_price"] = fill_price
        else:
            position = positions.setdefault(
                str(order["symbol"]),
                {"quantity": 0, "avg_cost": 0.0, "last_price": fill_price},
            )
            available_quantity = int(position.get("quantity", 0))
            fill_quantity = min(fill_quantity, available_quantity)
            if fill_quantity <= 0:
                order["status"] = "rejected"
                order["detail"] = "insufficient_position"
                order["fill_price"] = 0.0
                order["fill_quantity"] = 0
                return
            proceeds = fill_price * fill_quantity
            account["cash"] = round(float(account["cash"]) + proceeds, 2)
            account["available_cash"] = round(float(account["available_cash"]) + proceeds, 2)
            position["quantity"] = available_quantity - fill_quantity
            position["last_price"] = fill_price
        order["fill_price"] = fill_price
        order["fill_quantity"] = fill_quantity
        order["status"] = "filled" if fill_quantity >= requested_quantity else "partially_filled"
        order["detail"] = "simulated_fill_complete" if order["status"] == "filled" else "simulated_fill_partial"


class QmtTerminalAdapter(TerminalAdapter):
    @property
    def name(self) -> str:
        return "qmt"

    def session_status(self) -> TerminalSessionStatus:
        state = self.state_store.load()
        session = state.get("session") or {}
        if session:
            parsed = TerminalSessionStatus.model_validate(session)
            return self._apply_host_state(parsed, self._host_state(parsed))
        status = TerminalSessionStatus(
            adapter=self.name,
            session_state="not_implemented",
            health_state="unavailable",
            connected=False,
            logged_in=False,
            terminal_path=settings.qmt_terminal_path,
            account_alias=settings.qmt_account_alias,
            credential_profile=settings.qmt_credential_profile,
            process_name=settings.qmt_process_name,
            pid_file_path=settings.qmt_pid_file_path,
            session_file_path=settings.qmt_session_file_path,
            lock_file_path=settings.qmt_lock_file_path,
            start_command=settings.qmt_start_command,
            working_directory=settings.qmt_working_directory,
            last_heartbeat_at=self._last_heartbeat_at,
            detail="qmt_terminal_not_implemented",
        )
        return self._apply_host_state(status, self._host_state(status))

    def preflight(self) -> TerminalPreflightResponse:
        session = self.session_health_check()
        host_state = session.host_state or self._host_state(session)
        checks: list[TerminalPreflightCheck] = []
        checks.append(
            TerminalPreflightCheck(
                name="terminal_path",
                status="ok" if host_state.terminal_path_exists else "error",
                detail=host_state.terminal_path,
            )
        )
        checks.append(
            TerminalPreflightCheck(
                name="account_alias",
                status="ok" if host_state.account_alias else "error",
                detail=host_state.account_alias,
            )
        )
        checks.append(
            TerminalPreflightCheck(
                name="credential_profile",
                status="ok" if host_state.credential_profile else "error",
                detail=host_state.credential_profile,
            )
        )
        checks.append(
            TerminalPreflightCheck(
                name="start_command",
                status="ok" if host_state.start_command_configured else "warn",
                detail=host_state.start_command,
            )
        )
        checks.append(
            TerminalPreflightCheck(
                name="working_directory",
                status="ok" if (not host_state.working_directory or host_state.working_directory_exists) else "warn",
                detail=host_state.working_directory,
            )
        )
        checks.append(
            TerminalPreflightCheck(
                name="singleton",
                status="ok" if host_state.lock.singleton_ok else "warn",
                detail="lock/process signal present" if host_state.lock.singleton_ok else "singleton signal missing",
            )
        )
        checks.append(
            TerminalPreflightCheck(
                name="session_marker",
                status="ok" if host_state.session_artifact.session_file_present or not host_state.session_artifact.session_file_path else "warn",
                detail=host_state.session_artifact.session_file_path,
            )
        )
        overall = "ok"
        if any(check.status == "error" for check in checks):
            overall = "error"
        elif session.health_state != "ok" or any(check.status == "warn" for check in checks):
            overall = "warn"
        return TerminalPreflightResponse(adapter=self.name, status=overall, checks=checks, session=session)

    def _resolve_terminal_path(self, request: TerminalSessionControlRequest | None = None) -> str | None:
        return (request.terminal_path if request and request.terminal_path else settings.qmt_terminal_path) or None

    def _resolve_account_alias(self, request: TerminalSessionControlRequest | None = None) -> str | None:
        return (request.account_alias if request and request.account_alias else settings.qmt_account_alias) or None

    def _resolve_credential_profile(self, request: TerminalSessionControlRequest | None = None) -> str | None:
        return (request.credential_profile if request and request.credential_profile else settings.qmt_credential_profile) or None

    def _resolve_start_command(self) -> str | None:
        return settings.qmt_start_command or None

    def _resolve_working_directory(self) -> str | None:
        return settings.qmt_working_directory or None

    def _path_exists(self, value: str | None) -> bool:
        return bool(value and Path(value).expanduser().exists())

    def _parse_command_argv(self, command: str | None) -> list[str]:
        if not command:
            return []
        try:
            return shlex.split(command)
        except ValueError:
            return [command]

    def _pid_file_present(self) -> bool:
        if not settings.qmt_pid_file_path:
            return False
        return Path(settings.qmt_pid_file_path).expanduser().exists()

    def _session_file_present(self) -> bool:
        if not settings.qmt_session_file_path:
            return False
        return Path(settings.qmt_session_file_path).expanduser().exists()

    def _lock_file_present(self) -> bool:
        if not settings.qmt_lock_file_path:
            return False
        return Path(settings.qmt_lock_file_path).expanduser().exists()

    def _read_pid(self) -> int | None:
        if not settings.qmt_pid_file_path:
            return None
        path = Path(settings.qmt_pid_file_path).expanduser()
        if not path.exists():
            return None
        try:
            return int(path.read_text(encoding="utf-8").strip())
        except Exception:
            return None

    def _pid_alive(self, pid: int | None) -> bool:
        if pid is None:
            return False
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    def _process_name_detected(self) -> bool:
        if not settings.qmt_process_name:
            return False
        try:
            result = subprocess.run(
                ["ps", "-ax", "-o", "command="],
                capture_output=True,
                text=True,
                check=False,
            )
        except Exception:
            return False
        needle = settings.qmt_process_name.casefold()
        return any(needle in line.casefold() for line in result.stdout.splitlines())

    def _read_lock_metadata(self) -> dict | None:
        if not settings.qmt_lock_file_path:
            return None
        path = Path(settings.qmt_lock_file_path).expanduser()
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {"invalid": True}

    def _write_lock_metadata(self, session: TerminalSessionStatus, operator_id: str | None) -> None:
        if not settings.qmt_lock_file_path:
            return
        path = Path(settings.qmt_lock_file_path).expanduser()
        payload = {
            "operator_id": operator_id,
            "account_alias": session.account_alias,
            "credential_profile": session.credential_profile,
            "updated_at": _now().isoformat(),
            "adapter": self.name,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _release_lock(self) -> None:
        if not settings.qmt_lock_file_path:
            return
        path = Path(settings.qmt_lock_file_path).expanduser()
        if path.exists():
            path.unlink()

    def _parse_datetime(self, value: object) -> datetime | None:
        if not isinstance(value, str):
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None

    def _host_state(self, status: TerminalSessionStatus | None = None) -> TerminalHostState:
        current = status or self.session_status()
        terminal_path = current.terminal_path or settings.qmt_terminal_path
        account_alias = current.account_alias or settings.qmt_account_alias
        credential_profile = current.credential_profile or settings.qmt_credential_profile
        start_command = current.start_command or settings.qmt_start_command
        working_directory = current.working_directory or settings.qmt_working_directory
        pid = self._read_pid()
        process_detected = self._pid_alive(pid) or self._process_name_detected()
        lock_metadata = self._read_lock_metadata() or {}
        lock_present = self._lock_file_present()
        lock_state = TerminalLockState(
            lock_file_path=current.lock_file_path or settings.qmt_lock_file_path,
            lock_present=lock_present,
            lock_owned=bool(lock_present and lock_metadata.get("adapter") == self.name),
            singleton_ok=(not settings.qmt_singleton_required) or lock_present or process_detected,
            operator_id=str(lock_metadata.get("operator_id")) if lock_metadata.get("operator_id") else None,
            adapter=str(lock_metadata.get("adapter")) if lock_metadata.get("adapter") else None,
            updated_at=self._parse_datetime(lock_metadata.get("updated_at")),
        )
        return TerminalHostState(
            adapter=self.name,
            terminal_path=terminal_path,
            terminal_path_exists=self._path_exists(terminal_path),
            account_alias=account_alias,
            credential_profile=credential_profile,
            start_command=start_command,
            command_argv=self._parse_command_argv(start_command),
            start_command_configured=bool(start_command),
            working_directory=working_directory,
            working_directory_exists=self._path_exists(working_directory) if working_directory else False,
            process=TerminalProcessState(
                process_name=current.process_name or settings.qmt_process_name,
                pid_file_path=current.pid_file_path or settings.qmt_pid_file_path,
                pid=pid,
                process_detected=process_detected,
                pid_file_present=self._pid_file_present(),
            ),
            session_artifact=TerminalSessionArtifactState(
                session_file_path=current.session_file_path or settings.qmt_session_file_path,
                session_file_present=self._session_file_present(),
                session_state=current.session_state,
                connected=current.connected,
                logged_in=current.logged_in,
                last_heartbeat_at=current.last_heartbeat_at,
            ),
            lock=lock_state,
        )

    def _apply_host_state(self, session: TerminalSessionStatus, host_state: TerminalHostState) -> TerminalSessionStatus:
        session.terminal_path = host_state.terminal_path
        session.account_alias = host_state.account_alias
        session.credential_profile = host_state.credential_profile
        session.process_name = host_state.process.process_name
        session.pid_file_path = host_state.process.pid_file_path
        session.session_file_path = host_state.session_artifact.session_file_path
        session.lock_file_path = host_state.lock.lock_file_path
        session.start_command = host_state.start_command
        session.working_directory = host_state.working_directory
        session.pid = host_state.process.pid
        session.process_detected = host_state.process.process_detected
        session.pid_file_present = host_state.process.pid_file_present
        session.session_file_present = host_state.session_artifact.session_file_present
        session.lock_present = host_state.lock.lock_present
        session.singleton_ok = host_state.lock.singleton_ok
        session.lock_owned = host_state.lock.lock_owned
        session.start_command_configured = host_state.start_command_configured
        session.host_state = host_state
        return session

    def _build_launch_plan(self, host_state: TerminalHostState) -> TerminalLaunchPlan:
        blocked_reasons: list[str] = []
        if not host_state.terminal_path:
            blocked_reasons.append("qmt_terminal_path_missing")
        elif not host_state.terminal_path_exists:
            blocked_reasons.append("qmt_terminal_path_not_found")
        if not host_state.account_alias:
            blocked_reasons.append("qmt_account_alias_missing")
        if not host_state.credential_profile:
            blocked_reasons.append("qmt_credential_profile_missing")
        if not host_state.start_command_configured:
            blocked_reasons.append("qmt_start_command_missing")
        if host_state.working_directory and not host_state.working_directory_exists:
            blocked_reasons.append("qmt_working_directory_not_found")
        if settings.qmt_singleton_required and host_state.lock.lock_present and not host_state.lock.lock_owned:
            blocked_reasons.append("qmt_singleton_lock_conflict")

        runnable = not blocked_reasons
        status = "ready" if runnable else "blocked"
        detail = "qmt_start_plan_ready" if runnable else blocked_reasons[0]
        steps = [
            "verify_preflight",
            "verify_singleton",
            "launch_terminal_command",
            "wait_for_pid_signal",
            "wait_for_session_signal",
            "operator_login_bridge",
        ]
        next_actions = (
            [
                "run_start_command_on_broker_host",
                "wait_for_pid_or_process_signal",
                "wait_for_session_marker",
                "complete_terminal_login",
            ]
            if runnable
            else [reason for reason in blocked_reasons]
        )
        return TerminalLaunchPlan(
            adapter=self.name,
            status=status,
            detail=detail,
            dry_run=True,
            runnable=runnable,
            requires_operator_action=True,
            command=host_state.start_command,
            command_argv=host_state.command_argv,
            terminal_path=host_state.terminal_path,
            working_directory=host_state.working_directory,
            account_alias=host_state.account_alias,
            credential_profile=host_state.credential_profile,
            pid_file_path=host_state.process.pid_file_path,
            session_file_path=host_state.session_artifact.session_file_path,
            lock_file_path=host_state.lock.lock_file_path,
            singleton_required=settings.qmt_singleton_required,
            blocked_reasons=blocked_reasons,
            steps=steps,
            next_actions=next_actions,
        )

    def connect_session(self, request: TerminalSessionControlRequest) -> TerminalSessionControlResponse:
        self._heartbeat()
        existing_lock = self._read_lock_metadata()
        if settings.qmt_singleton_required and settings.qmt_lock_file_path and existing_lock:
            session = self.session_status()
            session.health_state = "degraded"
            session.lock_present = True
            session.singleton_ok = False
            session.lock_owned = False
            session.detail = "qmt_singleton_lock_conflict"
            if session.host_state:
                session.host_state.lock.lock_present = True
                session.host_state.lock.singleton_ok = False
                session.host_state.lock.lock_owned = False
            return TerminalSessionControlResponse(
                action="connect",
                status="rejected",
                detail="qmt_singleton_lock_conflict",
                session=session,
            )
        session = TerminalSessionStatus(
            adapter=self.name,
            session_state="terminal_connected_placeholder",
            health_state="degraded",
            connected=True,
            logged_in=False,
            terminal_path=self._resolve_terminal_path(request),
            account_alias=self._resolve_account_alias(request),
            credential_profile=self._resolve_credential_profile(request),
            process_name=settings.qmt_process_name,
            pid_file_path=settings.qmt_pid_file_path,
            session_file_path=settings.qmt_session_file_path,
            lock_file_path=settings.qmt_lock_file_path,
            start_command=self._resolve_start_command(),
            working_directory=self._resolve_working_directory(),
            lock_owned=bool(settings.qmt_lock_file_path and settings.qmt_singleton_required),
            start_command_configured=bool(self._resolve_start_command()),
            last_heartbeat_at=self._last_heartbeat_at,
            detail=request.terminal_path or "qmt_connect_placeholder",
        )
        if session.lock_owned:
            self._write_lock_metadata(session, request.operator_id)
        session = self._apply_host_state(session, self._host_state(session))
        self.state_store.update(lambda state: self._write_session(state, session))
        return TerminalSessionControlResponse(action="connect", status="accepted", detail="placeholder_only", session=session)

    def login_session(self, request: TerminalSessionControlRequest) -> TerminalSessionControlResponse:
        self._heartbeat()
        session = TerminalSessionStatus(
            adapter=self.name,
            session_state="login_placeholder",
            health_state="degraded",
            connected=True,
            logged_in=True,
            terminal_path=self._resolve_terminal_path(request),
            account_alias=self._resolve_account_alias(request),
            credential_profile=self._resolve_credential_profile(request),
            process_name=settings.qmt_process_name,
            pid_file_path=settings.qmt_pid_file_path,
            session_file_path=settings.qmt_session_file_path,
            lock_file_path=settings.qmt_lock_file_path,
            start_command=self._resolve_start_command(),
            working_directory=self._resolve_working_directory(),
            lock_owned=bool(settings.qmt_lock_file_path and settings.qmt_singleton_required),
            start_command_configured=bool(self._resolve_start_command()),
            last_heartbeat_at=self._last_heartbeat_at,
            detail=request.credential_profile or "qmt_login_placeholder",
        )
        if session.lock_owned:
            self._write_lock_metadata(session, request.operator_id)
        session = self._apply_host_state(session, self._host_state(session))
        self.state_store.update(lambda state: self._write_session(state, session))
        return TerminalSessionControlResponse(action="login", status="accepted", detail="placeholder_only", session=session)

    def disconnect_session(self, request: TerminalSessionControlRequest) -> TerminalSessionControlResponse:
        self._heartbeat()
        session = TerminalSessionStatus(
            adapter=self.name,
            session_state="disconnected",
            health_state="idle",
            connected=False,
            logged_in=False,
            terminal_path=self._resolve_terminal_path(request),
            account_alias=self._resolve_account_alias(request),
            credential_profile=self._resolve_credential_profile(request),
            process_name=settings.qmt_process_name,
            pid_file_path=settings.qmt_pid_file_path,
            session_file_path=settings.qmt_session_file_path,
            lock_file_path=settings.qmt_lock_file_path,
            start_command=self._resolve_start_command(),
            working_directory=self._resolve_working_directory(),
            lock_owned=False,
            start_command_configured=bool(self._resolve_start_command()),
            last_heartbeat_at=self._last_heartbeat_at,
            detail=request.reason or "qmt_disconnect_placeholder",
        )
        self._release_lock()
        session = self._apply_host_state(session, self._host_state(session))
        self.state_store.update(lambda state: self._write_session(state, session))
        return TerminalSessionControlResponse(action="disconnect", status="accepted", detail="placeholder_only", session=session)

    def start_terminal(self, request: TerminalSessionControlRequest) -> TerminalSessionControlResponse:
        self._heartbeat()
        session = self.session_status()
        host_state = self._host_state(session)
        launch_plan = self._build_launch_plan(host_state)
        session = self._apply_host_state(session, host_state)
        session.last_heartbeat_at = self._last_heartbeat_at
        if launch_plan.runnable:
            session.session_state = "start_plan_ready"
            session.health_state = "degraded"
            session.connected = True
            session.detail = "qmt_start_plan_generated"
        else:
            session.session_state = "start_plan_blocked"
            session.detail = launch_plan.detail
        self.state_store.update(lambda state: self._write_session(state, session))
        return TerminalSessionControlResponse(
            action="start",
            status="accepted" if launch_plan.runnable else "rejected",
            detail=launch_plan.detail,
            session=session,
            launch_plan=launch_plan,
        )

    def process_orders(self, request: ProcessOrdersRequest) -> ProcessOrdersResponse:
        self._heartbeat()
        raise TerminalAdapterError("qmt_terminal_not_implemented")

    def session_health_check(self) -> TerminalSessionStatus:
        self._heartbeat()
        status = self.session_status()
        host_state = self._host_state(status)
        status = self._apply_host_state(status, host_state)
        terminal_path = host_state.terminal_path
        if not terminal_path:
            status.health_state = "unavailable"
            status.detail = "qmt_terminal_path_missing"
        elif not host_state.terminal_path_exists:
            status.health_state = "unavailable"
            status.detail = "qmt_terminal_path_not_found"
        elif not host_state.account_alias:
            status.health_state = "unavailable"
            status.detail = "qmt_account_alias_missing"
        elif not host_state.credential_profile:
            status.health_state = "unavailable"
            status.detail = "qmt_credential_profile_missing"
        elif not host_state.start_command_configured:
            status.health_state = "degraded"
            status.detail = "qmt_start_command_missing"
        elif host_state.working_directory and not host_state.working_directory_exists:
            status.health_state = "degraded"
            status.detail = "qmt_working_directory_not_found"
        elif settings.qmt_singleton_required and not host_state.lock.singleton_ok:
            status.health_state = "degraded"
            status.detail = "qmt_singleton_not_detected"
        elif host_state.session_artifact.session_file_path and not host_state.session_artifact.session_file_present:
            status.health_state = "degraded"
            status.detail = "qmt_session_file_not_detected"
        elif status.connected and status.logged_in:
            status.health_state = "degraded"
            status.detail = "qmt_terminal_placeholder_logged_in"
        elif status.connected:
            status.health_state = "degraded"
            status.detail = "qmt_terminal_placeholder_connected"
        else:
            status.health_state = "unavailable"
            status.detail = "qmt_terminal_not_connected"
        self.state_store.update(lambda state: self._write_session(state, status))
        return status

    def submit_order(self, request: SubmitOrderRequest) -> BrokerOrderResponse:
        self._heartbeat()
        raise TerminalAdapterError("qmt_terminal_not_implemented")

    def cancel_order(self, request: CancelOrderRequest) -> BrokerCancelResponse:
        self._heartbeat()
        raise TerminalAdapterError("qmt_terminal_not_implemented")

    def orders(self, account_id: str) -> BrokerOrdersResponse:
        self._heartbeat()
        raise TerminalAdapterError("qmt_terminal_not_implemented")

    def positions(self, account_id: str) -> BrokerPositionsResponse:
        self._heartbeat()
        raise TerminalAdapterError("qmt_terminal_not_implemented")

    def account(self, account_id: str) -> BrokerAccountSummary:
        self._heartbeat()
        raise TerminalAdapterError("qmt_terminal_not_implemented")

    def _write_session(self, state: dict, session: TerminalSessionStatus) -> dict:
        self.state_store.ensure_session(state)
        state["session"] = session.model_dump(mode="json")
        return state


class BrokerDaemonService:
    def __init__(self, state_path: str | None = None, terminal_adapter: TerminalAdapter | None = None) -> None:
        self.state_store = BrokerStateStore(state_path)
        self.adapter = terminal_adapter or self._build_adapter()
        self._last_error: str | None = None
        self._background_task: asyncio.Task | None = None
        self._stopping = False

    def status(self) -> DaemonStatusResponse:
        state = self.state_store.load()
        position_count = sum(
            1
            for account_positions in state["positions"].values()
            for payload in account_positions.values()
            if int(payload.get("quantity", 0)) > 0
        )
        return DaemonStatusResponse(
            service=settings.app_name,
            status="ok",
            adapter=settings.adapter_name,
            terminal_adapter=self.adapter.name,
            live_routing_enabled=settings.live_routing_enabled,
            order_count=len(state["orders"]),
            position_count=position_count,
            last_error=self._last_error,
            session=self.adapter.session_status(),
        )

    def session_status(self) -> TerminalSessionStatus:
        return self.adapter.session_status()

    def session_health_check(self) -> TerminalSessionStatus:
        return self._run_adapter(lambda: self.adapter.session_health_check())

    def preflight(self) -> TerminalPreflightResponse:
        return self._run_adapter(lambda: self.adapter.preflight())

    def submit_order(self, request: SubmitOrderRequest) -> BrokerOrderResponse:
        return self._run_adapter(lambda: self.adapter.submit_order(request))

    def connect_session(self, request: TerminalSessionControlRequest) -> TerminalSessionControlResponse:
        return self._run_adapter(lambda: self.adapter.connect_session(request))

    def login_session(self, request: TerminalSessionControlRequest) -> TerminalSessionControlResponse:
        return self._run_adapter(lambda: self.adapter.login_session(request))

    def disconnect_session(self, request: TerminalSessionControlRequest) -> TerminalSessionControlResponse:
        return self._run_adapter(lambda: self.adapter.disconnect_session(request))

    def start_terminal(self, request: TerminalSessionControlRequest) -> TerminalSessionControlResponse:
        return self._run_adapter(lambda: self.adapter.start_terminal(request))

    def cancel_order(self, request: CancelOrderRequest) -> BrokerCancelResponse:
        return self._run_adapter(lambda: self.adapter.cancel_order(request))

    def process_orders(self, request: ProcessOrdersRequest) -> ProcessOrdersResponse:
        return self._run_adapter(lambda: self.adapter.process_orders(request))

    async def start(self) -> None:
        if not settings.background_process_enabled or self._background_task is not None:
            return
        self._stopping = False
        self._background_task = asyncio.create_task(self._background_loop())

    async def stop(self) -> None:
        self._stopping = True
        if self._background_task is None:
            return
        self._background_task.cancel()
        try:
            await self._background_task
        except asyncio.CancelledError:
            pass
        self._background_task = None

    def orders(self, account_id: str) -> BrokerOrdersResponse:
        return self._run_adapter(lambda: self.adapter.orders(account_id))

    def positions(self, account_id: str) -> BrokerPositionsResponse:
        return self._run_adapter(lambda: self.adapter.positions(account_id))

    def account(self, account_id: str) -> BrokerAccountSummary:
        return self._run_adapter(lambda: self.adapter.account(account_id))

    def _run_adapter(self, fn):
        try:
            result = fn()
        except TerminalAdapterError as exc:
            self._last_error = str(exc)
            raise
        self._last_error = None
        return result

    def _build_adapter(self) -> TerminalAdapter:
        if settings.terminal_adapter == "simulated":
            return SimulatedTerminalAdapter(self.state_store)
        if settings.terminal_adapter == "qmt":
            return QmtTerminalAdapter(self.state_store)
        raise TerminalAdapterError(f"unsupported_terminal_adapter:{settings.terminal_adapter}")

    async def _background_loop(self) -> None:
        while not self._stopping:
            try:
                self.session_health_check()
                if settings.simulated_fill_mode == "queued":
                    self.process_orders(ProcessOrdersRequest(limit=50))
            except TerminalAdapterError as exc:
                self._last_error = str(exc)
            await asyncio.sleep(max(settings.background_process_interval_seconds, 1))
