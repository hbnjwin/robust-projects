import queue
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Deque, Dict, List, Optional, Tuple

from qmt_broker.audit import TradeAuditLogger
from qmt_broker.config import BrokerConfig
from qmt_broker.notifications import ApprovalNotifier
from qmt_broker.state_store import TradeStateStore
from qmt_broker.trade_policy import TradePolicy
from qmt_broker.trade_models import TradeEvent, TradeStreamFilter


@dataclass
class QueueRegistration:
    queue_obj: "queue.Queue[Dict[str, object]]"
    filter_spec: TradeStreamFilter


class TradeBroker:
    def __init__(self, provider, config: BrokerConfig) -> None:  # type: ignore[no-untyped-def]
        self.provider = provider
        self.config = config
        self.policy = TradePolicy(config)
        self.audit = TradeAuditLogger(config.trade_audit_log_path)
        self.state = TradeStateStore(config.trade_state_store_path)
        self.notifier = ApprovalNotifier(config)
        self._lock = threading.RLock()
        self._queues: Dict[str, QueueRegistration] = {}
        self._histories: Dict[str, Deque[Dict[str, object]]] = defaultdict(
            lambda: deque(maxlen=self.config.history_limit)
        )
        self._stop_event = threading.Event()
        self.provider.set_event_callback(self._on_provider_event)
        self._maintenance_thread = threading.Thread(target=self._maintenance_loop, daemon=True)
        self._maintenance_thread.start()

    def close(self) -> None:
        self._stop_event.set()
        self._maintenance_thread.join(timeout=1.0)
        with self._lock:
            self._queues.clear()
        self.provider.close()

    def capabilities(self) -> Dict[str, object]:
        self._scan_pending_requests()
        result = dict(self.provider.capabilities())
        result["policy"] = self.policy.describe()
        result["audit_log_path"] = self.config.trade_audit_log_path
        result["trade_state_store_path"] = self.config.trade_state_store_path
        result["notifications"] = self.notifier.status()
        return result

    def status(self) -> Dict[str, object]:
        self._scan_pending_requests()
        return self.provider.status()

    def account_infos(self) -> List[Dict[str, object]]:
        return self.provider.get_account_infos()

    def account_statuses(self) -> List[Dict[str, object]]:
        return self.provider.get_account_statuses()

    def policy_status(self) -> Dict[str, object]:
        return self.policy.describe()

    def notification_status(self) -> Dict[str, object]:
        return self.notifier.status()

    def audit_tail(self, limit: int = 50) -> List[Dict[str, object]]:
        return self.audit.tail(limit)

    def request_status(self, request_id: str) -> Optional[Dict[str, object]]:
        self._scan_pending_requests()
        return self.state.get_request(request_id)

    def request_list(self, status: str = "", limit: int = 100) -> List[Dict[str, object]]:
        self._scan_pending_requests()
        return self.state.list_requests(status=status, limit=limit)

    def request_by_order_id(self, order_id: str) -> Optional[Dict[str, object]]:
        self._scan_pending_requests()
        return self.state.find_by_order_id(order_id)

    def request_by_seq(self, seq: str) -> Optional[Dict[str, object]]:
        self._scan_pending_requests()
        return self.state.find_by_seq(seq)

    def request_by_order_sysid(self, order_sysid: str) -> Optional[Dict[str, object]]:
        self._scan_pending_requests()
        return self.state.find_by_order_sysid(order_sysid)

    def request_by_trade_id(self, trade_id: str) -> Optional[Dict[str, object]]:
        self._scan_pending_requests()
        return self.state.find_by_trade_id(trade_id)

    def get_asset(self, account_id: str = "", account_type: str = "") -> Optional[Dict[str, object]]:
        result = self.provider.get_asset(account_id=account_id, account_type=account_type)
        self._log_action("get_asset", {"account_id": account_id, "account_type": account_type}, {"ok": True})
        return result

    def get_orders(self, account_id: str = "", account_type: str = "") -> List[Dict[str, object]]:
        result = self.provider.get_orders(account_id=account_id, account_type=account_type)
        self._log_action("get_orders", {"account_id": account_id, "account_type": account_type}, {"ok": True, "count": len(result)})
        return result

    def get_order(self, account_id: str, order_id: int, account_type: str = "") -> Optional[Dict[str, object]]:
        result = self.provider.get_order(account_id=account_id, order_id=order_id, account_type=account_type)
        self._log_action("get_order", {"account_id": account_id, "account_type": account_type, "order_id": order_id}, {"ok": True, "found": result is not None})
        return result

    def get_trades(self, account_id: str = "", account_type: str = "") -> List[Dict[str, object]]:
        result = self.provider.get_trades(account_id=account_id, account_type=account_type)
        self._log_action("get_trades", {"account_id": account_id, "account_type": account_type}, {"ok": True, "count": len(result)})
        return result

    def get_positions(self, account_id: str = "", account_type: str = "") -> List[Dict[str, object]]:
        result = self.provider.get_positions(account_id=account_id, account_type=account_type)
        self._log_action("get_positions", {"account_id": account_id, "account_type": account_type}, {"ok": True, "count": len(result)})
        return result

    def get_position(
        self,
        account_id: str,
        symbol: str,
        account_type: str = "",
    ) -> Optional[Dict[str, object]]:
        result = self.provider.get_position(account_id=account_id, symbol=symbol, account_type=account_type)
        self._log_action("get_position", {"account_id": account_id, "account_type": account_type, "symbol": symbol}, {"ok": True, "found": result is not None})
        return result

    def get_credit_detail(self, account_id: str = "", account_type: str = "") -> Optional[Dict[str, object]]:
        self._ensure_credit_query_allowed(account_type or "CREDIT")
        result = self.provider.get_credit_detail(account_id=account_id, account_type=account_type or "CREDIT")
        self._log_action("get_credit_detail", {"account_id": account_id, "account_type": account_type or "CREDIT"}, {"ok": True})
        return result

    def get_credit_compacts(self, account_id: str = "", account_type: str = "") -> List[Dict[str, object]]:
        self._ensure_credit_query_allowed(account_type or "CREDIT")
        result = self.provider.get_credit_compacts(account_id=account_id, account_type=account_type or "CREDIT")
        self._log_action("get_credit_compacts", {"account_id": account_id, "account_type": account_type or "CREDIT"}, {"ok": True, "count": len(result)})
        return result

    def get_credit_subjects(self, account_id: str = "", account_type: str = "") -> List[Dict[str, object]]:
        self._ensure_credit_query_allowed(account_type or "CREDIT")
        result = self.provider.get_credit_subjects(account_id=account_id, account_type=account_type or "CREDIT")
        self._log_action("get_credit_subjects", {"account_id": account_id, "account_type": account_type or "CREDIT"}, {"ok": True, "count": len(result)})
        return result

    def get_credit_slo_codes(self, account_id: str = "", account_type: str = "") -> List[Dict[str, object]]:
        self._ensure_credit_query_allowed(account_type or "CREDIT")
        result = self.provider.get_credit_slo_codes(account_id=account_id, account_type=account_type or "CREDIT")
        self._log_action("get_credit_slo_codes", {"account_id": account_id, "account_type": account_type or "CREDIT"}, {"ok": True, "count": len(result)})
        return result

    def get_credit_assure(self, account_id: str = "", account_type: str = "") -> List[Dict[str, object]]:
        self._ensure_credit_query_allowed(account_type or "CREDIT")
        result = self.provider.get_credit_assure(account_id=account_id, account_type=account_type or "CREDIT")
        self._log_action("get_credit_assure", {"account_id": account_id, "account_type": account_type or "CREDIT"}, {"ok": True, "count": len(result)})
        return result

    def place_order(self, payload: Dict[str, object]) -> Dict[str, object]:
        self._scan_pending_requests()
        idempotency_key = str(payload.get("idempotency_key", ""))
        if idempotency_key:
            existing = self.state.find_by_idempotency(idempotency_key)
            if existing is not None:
                result = {
                    "ok": True,
                    "reused": True,
                    "request_id": existing["request_id"],
                    "status": existing["status"],
                    "reason": existing.get("reason", ""),
                    "result": existing.get("result"),
                    "links": existing.get("links", {}),
                }
                self._log_action("place_order", payload, result)
                return result
        policy = self.policy.validate_order(payload)
        if not policy.ok:
            result = {"ok": False, "error": policy.to_dict()}
            self._log_action("place_order", payload, result)
            return result
        approval_reason = self.policy.approval_reason(payload)
        if approval_reason:
            expires_at_ms = 0
            if self.config.approval_pending_ttl_sec > 0:
                expires_at_ms = int(time.time() * 1000) + self.config.approval_pending_ttl_sec * 1000
            request = self.state.create_request(
                payload,
                status="pending",
                reason=approval_reason,
                expires_at_ms=expires_at_ms,
            )
            result = {
                "ok": True,
                "pending": True,
                "request_id": request["request_id"],
                "status": request["status"],
                "reason": approval_reason,
                "expires_at_ms": request.get("expires_at_ms", 0),
                "approvals_required": self.config.approval_min_approvers,
            }
            self._notify_request("approval_pending", request)
            self._log_action("place_order", payload, result)
            return result
        request = self.state.create_request(payload, status="executing", reason="")
        execution = self.provider.place_order(payload)
        stored = self._store_execution_result(str(request["request_id"]), execution, reason="")
        result = {
            "ok": bool(execution.get("ok")),
            "request_id": stored["request_id"],
            "status": stored["status"],
            "result": execution,
            "links": stored.get("links", {}),
        }
        self._log_action("place_order", payload, result)
        return result

    def cancel_order(self, payload: Dict[str, object]) -> Dict[str, object]:
        result = self.provider.cancel_order(payload)
        self._log_action("cancel_order", payload, result)
        return result

    def approve_order(self, request_id: str) -> Dict[str, object]:
        return self.approve_order_as(request_id, approver_id="", approver_secret="")

    def approve_order_as(self, request_id: str, approver_id: str, approver_secret: str) -> Dict[str, object]:
        self._scan_pending_requests()
        request = self.state.get_request(request_id)
        if request is None:
            result = {"ok": False, "error": {"code": "request_not_found", "detail": "request_id not found"}}
            self._log_action("approve_order", {"request_id": request_id, "approver_id": approver_id}, result)
            return result
        if request["status"] != "pending":
            result = {
                "ok": False,
                "error": {"code": "request_not_pending", "detail": "request is not pending approval"},
                "request": request,
            }
            self._log_action("approve_order", {"request_id": request_id, "approver_id": approver_id}, result)
            return result
        approver_check = self.policy.validate_approver(approver_id, approver_secret)
        if not approver_check.ok:
            result = {"ok": False, "error": approver_check.to_dict()}
            self._log_action("approve_order", {"request_id": request_id, "approver_id": approver_id}, result)
            return result
        for approval in request.get("approvals", []):
            if approval.get("approver_id") == approver_id and approver_id:
                result = {
                    "ok": False,
                    "error": {"code": "approver_duplicate", "detail": "approver has already approved this request"},
                }
                self._log_action("approve_order", {"request_id": request_id, "approver_id": approver_id}, result)
                return result
        approval_entry = {"approver_id": approver_id or "implicit", "approved_at_ms": int(time.time() * 1000)}
        stored = self.state.append_approval(request_id, approval_entry)
        approvals = stored.get("approvals", [])
        if len(approvals) < self.config.approval_min_approvers:
            result = {
                "ok": True,
                "pending": True,
                "request_id": request_id,
                "status": "pending",
                "approvals": approvals,
                "approvals_required": self.config.approval_min_approvers,
            }
            self._notify_request("approval_progress", stored)
            self._log_action("approve_order", {"request_id": request_id, "approver_id": approver_id}, result)
            return result
        payload = dict(stored["payload"])
        execution = self.provider.place_order(payload)
        stored = self._store_execution_result(request_id, execution, reason="approved")
        result = {
            "ok": bool(execution.get("ok")),
            "request_id": request_id,
            "status": stored["status"],
            "approvals": stored.get("approvals", []),
            "result": execution,
            "links": stored.get("links", {}),
        }
        self._notify_request("approval_approved", stored)
        self._log_action("approve_order", {"request_id": request_id, "approver_id": approver_id}, result)
        return result

    def reject_order(self, request_id: str, reason: str = "") -> Dict[str, object]:
        return self.reject_order_as(request_id, reason=reason, approver_id="", approver_secret="")

    def reject_order_as(
        self,
        request_id: str,
        reason: str = "",
        approver_id: str = "",
        approver_secret: str = "",
    ) -> Dict[str, object]:
        self._scan_pending_requests()
        request = self.state.get_request(request_id)
        if request is None:
            result = {"ok": False, "error": {"code": "request_not_found", "detail": "request_id not found"}}
            self._log_action("reject_order", {"request_id": request_id, "reason": reason, "approver_id": approver_id}, result)
            return result
        if request["status"] != "pending":
            result = {
                "ok": False,
                "error": {"code": "request_not_pending", "detail": "request is not pending approval"},
                "request": request,
            }
            self._log_action("reject_order", {"request_id": request_id, "reason": reason, "approver_id": approver_id}, result)
            return result
        approver_check = self.policy.validate_approver(approver_id, approver_secret)
        if not approver_check.ok:
            result = {"ok": False, "error": approver_check.to_dict()}
            self._log_action("reject_order", {"request_id": request_id, "reason": reason, "approver_id": approver_id}, result)
            return result
        stored = self.state.update_request(request_id, status="rejected", reason=reason or "rejected")
        result = {"ok": True, "request_id": request_id, "status": stored["status"], "reason": stored["reason"]}
        self._notify_request("approval_rejected", stored)
        self._log_action("reject_order", {"request_id": request_id, "reason": reason, "approver_id": approver_id}, result)
        return result

    def revoke_order(self, request_id: str, reason: str = "") -> Dict[str, object]:
        self._scan_pending_requests()
        request = self.state.get_request(request_id)
        if request is None:
            result = {"ok": False, "error": {"code": "request_not_found", "detail": "request_id not found"}}
            self._log_action("revoke_order", {"request_id": request_id, "reason": reason}, result)
            return result
        if request["status"] != "pending":
            result = {
                "ok": False,
                "error": {"code": "request_not_pending", "detail": "request is not pending approval"},
                "request": request,
            }
            self._log_action("revoke_order", {"request_id": request_id, "reason": reason}, result)
            return result
        stored = self.state.update_request(request_id, status="revoked", reason=reason or "revoked")
        result = {"ok": True, "request_id": request_id, "status": stored["status"], "reason": stored["reason"]}
        self._notify_request("approval_revoked", stored)
        self._log_action("revoke_order", {"request_id": request_id, "reason": reason}, result)
        return result

    def open_stream(self, filter_spec: TradeStreamFilter) -> Tuple[str, "queue.Queue[Dict[str, object]]"]:
        stream_queue = queue.Queue(self.config.stream_queue_size)
        stream_id = "trade-stream-%d" % len(self._queues)
        with self._lock:
            self._queues[stream_id] = QueueRegistration(queue_obj=stream_queue, filter_spec=filter_spec)
            if filter_spec.replay > 0:
                for topic in filter_spec.topics:
                    for payload in list(self._histories[topic])[-filter_spec.replay :]:
                        stream_queue.put_nowait({"type": "replay", "event": payload})
        return stream_id, stream_queue

    def close_stream(self, stream_id: str) -> None:
        with self._lock:
            self._queues.pop(stream_id, None)

    def _on_provider_event(self, topic: str, payload: Dict[str, object]) -> None:
        if topic in {"order", "trade"}:
            self._bind_request_from_event(topic, payload)
        elif topic in {"order_async_response", "cancel_async_response"}:
            self._bind_request_from_async_response(topic, payload)
        elif topic == "order_error":
            self._bind_request_error(payload)
        event = TradeEvent(topic=topic, payload=payload).to_dict()
        account_id = str(payload.get("account_id", ""))
        self.audit.log({"kind": "trade_event", "topic": topic, "account_id": account_id, "payload": payload})
        with self._lock:
            self._histories[topic].append(event)
            targets = list(self._queues.values())
        for registration in targets:
            if topic not in registration.filter_spec.topics:
                continue
            if registration.filter_spec.account_id and registration.filter_spec.account_id != account_id:
                continue
            try:
                registration.queue_obj.put_nowait({"type": "event", "event": event})
            except queue.Full:
                try:
                    registration.queue_obj.get_nowait()
                except queue.Empty:
                    pass
                try:
                    registration.queue_obj.put_nowait({"type": "event", "event": event})
                except queue.Full:
                    continue

    def _ensure_credit_query_allowed(self, account_type: str) -> None:
        policy = self.policy.validate_credit_query(account_type)
        if not policy.ok:
            raise RuntimeError(policy.detail)

    def _log_action(self, action: str, request: Dict[str, object], result: Dict[str, object]) -> None:
        self.audit.log({"kind": "trade_action", "action": action, "request": request, "result": result})

    def _scan_pending_requests(self) -> None:
        pending = self.state.list_requests(status="pending", limit=100000)
        if not pending:
            return
        now_ms = int(time.time() * 1000)
        for request in pending:
            expires_at_ms = int(request.get("expires_at_ms", 0) or 0)
            if expires_at_ms > 0 and expires_at_ms <= now_ms:
                updated = self.state.update_request(
                    str(request["request_id"]),
                    status="expired",
                    reason="approval_timeout",
                )
                self.audit.log(
                    {
                        "kind": "trade_action",
                        "action": "expire_request",
                        "request": {"request_id": request["request_id"]},
                        "result": {"ok": True, "status": updated["status"]},
                    }
                )
                self._notify_request("approval_expired", updated)
                continue
            reminder_window_ms = self.config.approval_reminder_before_sec * 1000
            reminder_sent_at_ms = int(request.get("reminder_sent_at_ms", 0) or 0)
            if (
                expires_at_ms > 0
                and reminder_window_ms > 0
                and reminder_sent_at_ms <= 0
                and expires_at_ms - now_ms <= reminder_window_ms
            ):
                updated = self.state.update_request(
                    str(request["request_id"]),
                    reminder_sent_at_ms=now_ms,
                )
                self.audit.log(
                    {
                        "kind": "trade_action",
                        "action": "remind_request",
                        "request": {"request_id": request["request_id"]},
                        "result": {"ok": True, "status": updated["status"]},
                    }
                )
                self._notify_request("approval_reminder", updated)

    def _store_execution_result(self, request_id: str, execution: Dict[str, object], reason: str) -> Dict[str, object]:
        status = self._derive_request_status(execution)
        current = self.state.get_request(request_id)
        current_status = str(current.get("status", "")) if current else ""
        if execution.get("ok") and current_status not in {"", "executing"}:
            stored = self._promote_request_status(request_id, status)
            stored = self.state.update_request(request_id, result=execution, reason=reason)
        else:
            stored = self.state.update_request(
                request_id,
                status=status,
                result=execution,
                reason=reason,
            )
        stored = self._bind_request_identifiers(
            request_id,
            seq=self._extract_identifier(execution, "seq"),
            order_id=self._extract_identifier(execution, "order_id"),
            order_sysid=self._extract_identifier(execution, "order_sysid"),
            trade_id=self._extract_identifier(execution, "trade_id", "traded_id"),
        )
        stored = self._backfill_trade_identifier(stored)
        links = stored.get("links", {})
        if execution.get("ok") and isinstance(links, dict) and links.get("trade_ids"):
            stored = self._promote_request_status(request_id, "executed")
        final_status = str(stored.get("status", status))
        self._notify_request(
            "order_executed" if final_status == "executed" else "order_failed" if not execution.get("ok") else "order_submitted",
            stored,
        )
        return stored

    def _bind_request_from_event(self, topic: str, payload: Dict[str, object]) -> None:
        seq = self._extract_identifier(payload, "seq")
        order_id = self._extract_identifier(payload, "order_id")
        order_sysid = self._extract_identifier(payload, "order_sysid")
        trade_id = self._extract_identifier(payload, "trade_id", "traded_id")
        request = None
        if seq:
            request = self.state.find_by_seq(seq)
        if request is None and order_id:
            request = self.state.find_by_order_id(order_id)
        if request is None and order_sysid:
            request = self.state.find_by_order_sysid(order_sysid)
        if request is None and trade_id:
            request = self.state.find_by_trade_id(trade_id)
        if request is None:
            return
        updated = self._bind_request_identifiers(
            str(request["request_id"]),
            seq=seq,
            order_id=order_id,
            order_sysid=order_sysid,
            trade_id=trade_id if topic == "trade" else "",
        )
        if topic == "trade":
            updated = self.state.update_request(
                str(request["request_id"]),
                status="executed",
                reason=str(updated.get("reason", "")),
            )
        elif topic == "order":
            updated = self._promote_request_status(str(request["request_id"]), "reported")
        self.audit.log(
            {
                "kind": "trade_action",
                "action": "bind_request_index",
                "request": {"request_id": updated["request_id"]},
                "result": {
                    "ok": True,
                    "topic": topic,
                    "links": updated.get("links", {}),
                },
            }
        )

    def _bind_request_identifiers(
        self,
        request_id: str,
        *,
        seq: str = "",
        order_id: str = "",
        order_sysid: str = "",
        trade_id: str = "",
    ) -> Dict[str, object]:
        return self.state.bind_identifiers(
            request_id,
            seq=seq,
            order_id=order_id,
            order_sysid=order_sysid,
            trade_id=trade_id,
        )

    def _extract_identifier(self, payload: Dict[str, object], *keys: str) -> str:
        for container in [payload, payload.get("result", {})]:
            if not isinstance(container, dict):
                continue
            for key in keys:
                value = container.get(key)
                if value is None:
                    continue
                normalized = str(value).strip()
                if normalized and normalized != "0":
                    return normalized
        return ""

    def _notify_request(self, event_name: str, request: Dict[str, object]) -> None:
        results = self.notifier.notify(event_name, request)
        if not results:
            return
        self.audit.log(
            {
                "kind": "notification",
                "event": event_name,
                "request_id": request.get("request_id", ""),
                "result": results,
            }
        )

    def _backfill_trade_identifier(self, request: Dict[str, object]) -> Dict[str, object]:
        links = request.get("links", {})
        if not isinstance(links, dict):
            return request
        if links.get("trade_ids"):
            return request
        payload = request.get("payload", {})
        if not isinstance(payload, dict):
            return request
        account_id = str(payload.get("account_id", ""))
        account_type = str(payload.get("account_type", ""))
        if not account_id:
            return request
        try:
            trades = self.provider.get_trades(account_id=account_id, account_type=account_type)
        except Exception:
            return request
        order_ids = {str(item) for item in links.get("order_ids", [])}
        order_sysids = {str(item) for item in links.get("order_sysids", [])}
        for trade in reversed(trades):
            trade_order_id = self._extract_identifier(trade, "order_id")
            trade_order_sysid = self._extract_identifier(trade, "order_sysid")
            if trade_order_id not in order_ids and trade_order_sysid not in order_sysids:
                continue
            trade_id = self._extract_identifier(trade, "trade_id", "traded_id")
            if not trade_id:
                continue
            return self._bind_request_identifiers(str(request["request_id"]), trade_id=trade_id)
        return request

    def _derive_request_status(self, execution: Dict[str, object]) -> str:
        if not execution.get("ok"):
            return "failed"
        if self._extract_identifier(execution, "trade_id", "traded_id"):
            return "executed"
        if self._extract_identifier(execution, "order_id"):
            return "submitted"
        if self._extract_identifier(execution, "seq"):
            return "accepted"
        return "accepted"

    def _promote_request_status(self, request_id: str, candidate: str) -> Dict[str, object]:
        request = self.state.get_request(request_id)
        if request is None:
            raise KeyError(request_id)
        current = str(request.get("status", ""))
        ranks = {
            "pending": 0,
            "accepted": 1,
            "acknowledged": 2,
            "submitted": 3,
            "reported": 4,
            "executed": 5,
            "revoked": 90,
            "rejected": 90,
            "expired": 90,
            "failed": 90,
        }
        if current in {"revoked", "rejected", "expired"}:
            return request
        if ranks.get(candidate, 0) <= ranks.get(current, 0) and current not in {"failed"}:
            return request
        return self.state.update_request(request_id, status=candidate)

    def _bind_request_from_async_response(self, topic: str, payload: Dict[str, object]) -> None:
        seq = self._extract_identifier(payload, "seq")
        if not seq:
            return
        request = self.state.find_by_seq(seq)
        if request is None:
            return
        request_id = str(request["request_id"])
        order_id = self._extract_identifier(payload, "order_id")
        order_sysid = self._extract_identifier(payload, "order_sysid")
        updated = self._bind_request_identifiers(request_id, seq=seq, order_id=order_id, order_sysid=order_sysid)
        is_ok = str(payload.get("error_id", payload.get("cancel_result", "0"))) in {"0", ""}
        if topic == "order_async_response":
            if is_ok:
                if order_id:
                    updated = self._promote_request_status(request_id, "submitted")
                else:
                    updated = self._promote_request_status(request_id, "acknowledged")
            else:
                updated = self.state.update_request(request_id, status="failed", result=payload)
        self.audit.log(
            {
                "kind": "trade_action",
                "action": "bind_request_async_response",
                "request": {"request_id": updated["request_id"]},
                "result": {"ok": is_ok, "topic": topic, "seq": seq, "links": updated.get("links", {})},
            }
        )

    def _bind_request_error(self, payload: Dict[str, object]) -> None:
        seq = self._extract_identifier(payload, "seq")
        order_id = self._extract_identifier(payload, "order_id")
        request = None
        if seq:
            request = self.state.find_by_seq(seq)
        if request is None and order_id:
            request = self.state.find_by_order_id(order_id)
        if request is None:
            return
        self.state.update_request(str(request["request_id"]), status="failed", result=payload)

    def _maintenance_loop(self) -> None:
        while not self._stop_event.wait(1.0):
            try:
                self._scan_pending_requests()
            except Exception:
                continue
