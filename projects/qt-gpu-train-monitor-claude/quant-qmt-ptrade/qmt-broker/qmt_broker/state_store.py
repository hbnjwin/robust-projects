import json
import os
import threading
import uuid
from copy import deepcopy
from typing import Dict, List, Optional


class TradeStateStore:
    def __init__(self, path: str) -> None:
        self.path = path
        self._lock = threading.RLock()
        self._state = {
            "requests": {},
            "idempotency": {},
            "indexes": {
                "seq": {},
                "order_id": {},
                "order_sysid": {},
                "trade_id": {},
            },
        }
        self._load()

    def get_request(self, request_id: str) -> Optional[Dict[str, object]]:
        with self._lock:
            request = self._state["requests"].get(request_id)
            return deepcopy(request) if request is not None else None

    def list_requests(self, status: str = "", limit: int = 100) -> List[Dict[str, object]]:
        with self._lock:
            values = list(self._state["requests"].values())
        if status:
            values = [item for item in values if item.get("status") == status]
        values.sort(key=lambda item: int(item.get("updated_at_ms", 0)), reverse=True)
        if limit > 0:
            values = values[:limit]
        return [deepcopy(item) for item in values]

    def find_by_idempotency(self, idempotency_key: str) -> Optional[Dict[str, object]]:
        if not idempotency_key:
            return None
        with self._lock:
            request_id = self._state["idempotency"].get(idempotency_key)
            if not request_id:
                return None
            request = self._state["requests"].get(request_id)
            return deepcopy(request) if request is not None else None

    def find_by_order_id(self, order_id: str) -> Optional[Dict[str, object]]:
        return self._find_by_index("order_id", order_id)

    def find_by_seq(self, seq: str) -> Optional[Dict[str, object]]:
        return self._find_by_index("seq", seq)

    def find_by_order_sysid(self, order_sysid: str) -> Optional[Dict[str, object]]:
        return self._find_by_index("order_sysid", order_sysid)

    def find_by_trade_id(self, trade_id: str) -> Optional[Dict[str, object]]:
        return self._find_by_index("trade_id", trade_id)

    def create_request(
        self,
        payload: Dict[str, object],
        status: str,
        reason: str = "",
        expires_at_ms: int = 0,
    ) -> Dict[str, object]:
        request_id = str(uuid.uuid4())
        now_ms = self._now_ms()
        request = {
            "request_id": request_id,
            "status": status,
            "reason": reason,
            "created_at_ms": now_ms,
            "updated_at_ms": now_ms,
            "expires_at_ms": expires_at_ms,
            "reminder_sent_at_ms": 0,
            "payload": deepcopy(payload),
            "result": None,
            "approvals": [],
            "links": {
                "seqs": [],
                "order_ids": [],
                "order_sysids": [],
                "trade_ids": [],
            },
        }
        idempotency_key = str(payload.get("idempotency_key", ""))
        with self._lock:
            self._state["requests"][request_id] = request
            if idempotency_key:
                self._state["idempotency"][idempotency_key] = request_id
            self._flush()
            return deepcopy(request)

    def update_request(
        self,
        request_id: str,
        *,
        status: Optional[str] = None,
        reason: Optional[str] = None,
        result: Optional[Dict[str, object]] = None,
        expires_at_ms: Optional[int] = None,
        reminder_sent_at_ms: Optional[int] = None,
    ) -> Dict[str, object]:
        with self._lock:
            request = self._state["requests"][request_id]
            if status is not None:
                request["status"] = status
            if reason is not None:
                request["reason"] = reason
            if result is not None:
                request["result"] = deepcopy(result)
            if expires_at_ms is not None:
                request["expires_at_ms"] = expires_at_ms
            if reminder_sent_at_ms is not None:
                request["reminder_sent_at_ms"] = reminder_sent_at_ms
            request["updated_at_ms"] = self._now_ms()
            self._flush()
            return deepcopy(request)

    def append_approval(self, request_id: str, approval: Dict[str, object]) -> Dict[str, object]:
        with self._lock:
            request = self._state["requests"][request_id]
            approvals = request.setdefault("approvals", [])
            approvals.append(deepcopy(approval))
            request["updated_at_ms"] = self._now_ms()
            self._flush()
            return deepcopy(request)

    def bind_identifiers(
        self,
        request_id: str,
        *,
        seq: str = "",
        order_id: str = "",
        order_sysid: str = "",
        trade_id: str = "",
    ) -> Dict[str, object]:
        with self._lock:
            request = self._state["requests"][request_id]
            links = request.setdefault(
                "links",
                {
                    "seqs": [],
                    "order_ids": [],
                    "order_sysids": [],
                    "trade_ids": [],
                },
            )
            self._append_link(links, "seqs", str(seq), "seq", request_id)
            self._append_link(links, "order_ids", str(order_id), "order_id", request_id)
            self._append_link(links, "order_sysids", str(order_sysid), "order_sysid", request_id)
            self._append_link(links, "trade_ids", str(trade_id), "trade_id", request_id)
            request["updated_at_ms"] = self._now_ms()
            self._flush()
            return deepcopy(request)

    def _load(self) -> None:
        with self._lock:
            if not os.path.exists(self.path):
                return
            with open(self.path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                self._state["requests"] = data.get("requests", {})
                self._state["idempotency"] = data.get("idempotency", {})
                indexes = data.get("indexes", {})
                self._state["indexes"]["seq"] = indexes.get("seq", {})
                self._state["indexes"]["order_id"] = indexes.get("order_id", {})
                self._state["indexes"]["order_sysid"] = indexes.get("order_sysid", {})
                self._state["indexes"]["trade_id"] = indexes.get("trade_id", {})
                self._rebuild_indexes_locked()

    def _flush(self) -> None:
        parent = os.path.dirname(self.path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        temp_path = self.path + ".tmp"
        with open(temp_path, "w", encoding="utf-8") as fh:
            json.dump(self._state, fh, ensure_ascii=False, separators=(",", ":"))
        os.replace(temp_path, self.path)

    def _now_ms(self) -> int:
        import time

        return int(time.time() * 1000)

    def _find_by_index(self, index_name: str, value: str) -> Optional[Dict[str, object]]:
        key = str(value).strip()
        if not key:
            return None
        with self._lock:
            request_id = self._state["indexes"].get(index_name, {}).get(key)
            if not request_id:
                return None
            request = self._state["requests"].get(request_id)
            return deepcopy(request) if request is not None else None

    def _append_link(
        self,
        links: Dict[str, object],
        key: str,
        value: str,
        index_name: str,
        request_id: str,
    ) -> None:
        normalized = value.strip()
        if not normalized:
            return
        values = links.setdefault(key, [])
        if normalized not in values:
            values.append(normalized)
        self._state["indexes"][index_name][normalized] = request_id

    def _rebuild_indexes_locked(self) -> None:
        self._state["indexes"] = {
            "seq": {},
            "order_id": {},
            "order_sysid": {},
            "trade_id": {},
        }
        for request_id, request in self._state["requests"].items():
            request.setdefault("reminder_sent_at_ms", 0)
            request.setdefault("approvals", [])
            links = request.setdefault(
                "links",
                {
                    "seqs": [],
                    "order_ids": [],
                    "order_sysids": [],
                    "trade_ids": [],
                },
            )
            for seq in list(links.get("seqs", [])):
                self._append_link(links, "seqs", str(seq), "seq", request_id)
            for order_id in list(links.get("order_ids", [])):
                self._append_link(links, "order_ids", str(order_id), "order_id", request_id)
            for order_sysid in list(links.get("order_sysids", [])):
                self._append_link(links, "order_sysids", str(order_sysid), "order_sysid", request_id)
            for trade_id in list(links.get("trade_ids", [])):
                self._append_link(links, "trade_ids", str(trade_id), "trade_id", request_id)
