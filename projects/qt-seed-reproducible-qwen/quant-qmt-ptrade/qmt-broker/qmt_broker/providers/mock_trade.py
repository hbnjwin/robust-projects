import threading
import time
from typing import Dict, List, Optional

from qmt_broker.providers.base import TradeProvider, TradeProviderCallback


class MockTradeProvider(TradeProvider):
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._callback: TradeProviderCallback = lambda topic, payload: None
        self._closed = False
        self._threads: List[threading.Thread] = []
        self._next_order_id = 100000
        self._next_seq = 9000
        self._orders: Dict[str, List[Dict[str, object]]] = {}
        self._trades: Dict[str, List[Dict[str, object]]] = {}
        self._positions: Dict[str, List[Dict[str, object]]] = {}
        self._assets: Dict[str, Dict[str, object]] = {}
        self._account_statuses: Dict[str, Dict[str, object]] = {}

    def name(self) -> str:
        return "mock"

    def capabilities(self) -> Dict[str, object]:
        return {
            "provider": "mock",
            "trade_topics": [
                "disconnected",
                "account_status",
                "order",
                "asset",
                "trade",
                "position",
                "order_error",
                "cancel_error",
                "order_async_response",
                "cancel_async_response",
            ],
            "supports": [
                "status",
                "asset",
                "orders",
                "trades",
                "positions",
                "order_place",
                "order_cancel",
            ],
        }

    def status(self) -> Dict[str, object]:
        return {
            "provider": "mock",
            "connected": True,
            "accounts": sorted(self._assets.keys()),
            "account_statuses": self.get_account_statuses(),
        }

    def get_account_infos(self) -> List[Dict[str, object]]:
        with self._lock:
            return [
                {
                    "account_id": account_id,
                    "account_type": str(asset.get("account_type", "STOCK")),
                    "status": "connected",
                }
                for account_id, asset in sorted(self._assets.items())
            ]

    def get_account_statuses(self) -> List[Dict[str, object]]:
        with self._lock:
            return [dict(item) for _, item in sorted(self._account_statuses.items())]

    def set_event_callback(self, callback: TradeProviderCallback) -> None:
        self._callback = callback

    def get_asset(self, account_id: str = "", account_type: str = "") -> Optional[Dict[str, object]]:
        account = self._resolve_account(account_id, account_type)
        return dict(self._assets[account])

    def get_orders(self, account_id: str = "", account_type: str = "") -> List[Dict[str, object]]:
        account = self._resolve_account(account_id, account_type)
        return [dict(item) for item in self._orders[account]]

    def get_order(self, account_id: str, order_id: int, account_type: str = "") -> Optional[Dict[str, object]]:
        account = self._resolve_account(account_id, account_type)
        for order in self._orders[account]:
            if int(order["order_id"]) == int(order_id):
                return dict(order)
        return None

    def get_trades(self, account_id: str = "", account_type: str = "") -> List[Dict[str, object]]:
        account = self._resolve_account(account_id, account_type)
        return [dict(item) for item in self._trades[account]]

    def get_positions(self, account_id: str = "", account_type: str = "") -> List[Dict[str, object]]:
        account = self._resolve_account(account_id, account_type)
        return [dict(item) for item in self._positions[account]]

    def get_position(
        self,
        account_id: str,
        symbol: str,
        account_type: str = "",
    ) -> Optional[Dict[str, object]]:
        account = self._resolve_account(account_id, account_type)
        for position in self._positions[account]:
            if position["stock_code"] == symbol:
                return dict(position)
        return None

    def place_order(self, payload: Dict[str, object]) -> Dict[str, object]:
        account = self._resolve_account(
            str(payload.get("account_id", "")),
            str(payload.get("account_type", "")),
        )
        side = str(payload.get("side", "buy")).lower()
        symbol = str(payload.get("symbol", "000001.SZ"))
        volume = int(payload.get("volume", 100))
        price = float(payload.get("price", 10.5))
        order_type = int(payload.get("order_type", 23 if side == "buy" else 24))
        is_async = bool(payload.get("async", False))
        now_int = int(time.time())
        with self._lock:
            self._next_order_id += 1
            order_id = self._next_order_id
            self._next_seq += 1
            seq = self._next_seq
            order = {
                "account_id": account,
                "stock_code": symbol,
                "order_id": order_id,
                "order_sysid": "SYS%s" % order_id,
                "order_time": now_int,
                "order_type": order_type,
                "order_volume": volume,
                "price_type": int(payload.get("price_type", 11)),
                "price": price,
                "traded_volume": volume,
                "traded_price": price,
                "order_status": 56,
                "status_msg": "mock filled",
                "strategy_name": str(payload.get("strategy_name", "")),
                "order_remark": str(payload.get("order_remark", "")),
            }
            trade = {
                "account_id": account,
                "stock_code": symbol,
                "order_type": order_type,
                "traded_id": order_id + 900000,
                "traded_time": now_int,
                "traded_price": price,
                "traded_volume": volume,
                "traded_amount": round(price * volume, 3),
                "order_id": order_id,
                "order_sysid": order["order_sysid"],
                "strategy_name": order["strategy_name"],
                "order_remark": order["order_remark"],
            }
            self._orders[account].append(order)
            self._trades[account].append(trade)
            self._apply_position(account, symbol, volume if side == "buy" else -volume, price)
            self._update_asset(account, delta_cash=-price * volume if side == "buy" else price * volume)
        if is_async:
            thread = threading.Thread(
                target=self._emit_async_order_callbacks,
                args=(account, symbol, seq, order_id, order, trade),
                daemon=True,
            )
            with self._lock:
                self._threads.append(thread)
            thread.start()
            return {"ok": True, "seq": seq}
        self._callback("order", dict(order))
        self._callback("trade", dict(trade))
        self._callback("position", dict(self.get_position(account, symbol) or {}))
        self._callback("asset", dict(self._assets[account]))
        return {"ok": True, "order_id": order_id, "result": dict(order)}

    def cancel_order(self, payload: Dict[str, object]) -> Dict[str, object]:
        account = self._resolve_account(
            str(payload.get("account_id", "")),
            str(payload.get("account_type", "")),
        )
        order_id = int(payload.get("order_id", 0))
        is_async = bool(payload.get("async", False))
        with self._lock:
            order = self.get_order(account, order_id)
            if order is None:
                error = {
                    "account_id": account,
                    "order_id": order_id,
                    "error_id": -2,
                    "error_msg": "order not found",
                }
                self._callback("cancel_error", error)
                return {"ok": False, "cancel_result": -2, "error": error}
            for item in self._orders[account]:
                if int(item["order_id"]) == order_id:
                    item["order_status"] = 54
                    item["status_msg"] = "mock canceled"
                    order = dict(item)
                    self._next_seq += 1
                    seq = self._next_seq
                    break
        if is_async:
            thread = threading.Thread(
                target=self._emit_async_cancel_callbacks,
                args=(account, order_id, seq, order),
                daemon=True,
            )
            with self._lock:
                self._threads.append(thread)
            thread.start()
            return {"ok": True, "seq": seq}
        self._callback("order", order)
        return {"ok": True, "cancel_result": 0, "result": order}

    def get_credit_detail(self, account_id: str = "", account_type: str = "") -> Optional[Dict[str, object]]:
        account = self._resolve_account(account_id or "mock-credit", account_type or "CREDIT")
        return {
            "account_id": account,
            "account_type": "CREDIT",
            "margin_ratio": 0.45,
            "debt_balance": 120000.0,
            "available_margin": 380000.0,
        }

    def get_credit_compacts(self, account_id: str = "", account_type: str = "") -> List[Dict[str, object]]:
        account = self._resolve_account(account_id or "mock-credit", account_type or "CREDIT")
        return [
            {
                "account_id": account,
                "compact_id": "compact-1",
                "stock_code": "600000.SH",
                "compact_type": "financing",
                "compact_balance": 100000.0,
            }
        ]

    def get_credit_subjects(self, account_id: str = "", account_type: str = "") -> List[Dict[str, object]]:
        account = self._resolve_account(account_id or "mock-credit", account_type or "CREDIT")
        return [{"account_id": account, "stock_code": "600000.SH", "subject_type": "margin"}]

    def get_credit_slo_codes(self, account_id: str = "", account_type: str = "") -> List[Dict[str, object]]:
        account = self._resolve_account(account_id or "mock-credit", account_type or "CREDIT")
        return [{"account_id": account, "stock_code": "600000.SH", "available_volume": 5000}]

    def get_credit_assure(self, account_id: str = "", account_type: str = "") -> List[Dict[str, object]]:
        account = self._resolve_account(account_id or "mock-credit", account_type or "CREDIT")
        return [{"account_id": account, "stock_code": "510300.SH", "discount_rate": 0.7}]

    def close(self) -> None:
        with self._lock:
            self._closed = True
            threads = list(self._threads)
            self._threads.clear()
        for thread in threads:
            thread.join(timeout=0.2)

    def _resolve_account(self, account_id: str, account_type: str) -> str:
        account = account_id or "mock-stock"
        with self._lock:
            if account not in self._assets:
                self._assets[account] = {
                    "account_id": account,
                    "account_type": account_type or "STOCK",
                    "cash": 1000000.0,
                    "frozen_cash": 0.0,
                    "market_value": 0.0,
                    "total_asset": 1000000.0,
                }
                self._orders[account] = []
                self._trades[account] = []
                self._positions[account] = []
                self._account_statuses[account] = {
                    "account_id": account,
                    "account_type": account_type or "STOCK",
                    "status": "connected",
                    "status_msg": "mock connected",
                }
                self._callback("account_status", dict(self._account_statuses[account]))
        return account

    def _apply_position(self, account: str, symbol: str, delta_volume: int, price: float) -> None:
        positions = self._positions[account]
        for item in positions:
            if item["stock_code"] == symbol:
                item["volume"] = int(item["volume"]) + delta_volume
                item["can_use_volume"] = int(item["can_use_volume"]) + delta_volume
                item["market_value"] = round(float(item["volume"]) * price, 3)
                item["open_price"] = price
                return
        positions.append(
            {
                "account_id": account,
                "stock_code": symbol,
                "volume": max(delta_volume, 0),
                "can_use_volume": max(delta_volume, 0),
                "open_price": price,
                "market_value": round(max(delta_volume, 0) * price, 3),
                "frozen_volume": 0,
                "on_road_volume": 0,
                "yesterday_volume": 0,
            }
        )

    def _update_asset(self, account: str, delta_cash: float) -> None:
        asset = self._assets[account]
        asset["cash"] = round(float(asset["cash"]) + delta_cash, 3)
        asset["market_value"] = round(
            sum(float(item["market_value"]) for item in self._positions[account] if float(item["volume"]) > 0),
            3,
        )
        asset["total_asset"] = round(float(asset["cash"]) + float(asset["market_value"]), 3)

    def _emit_async_order_callbacks(
        self,
        account: str,
        symbol: str,
        seq: int,
        order_id: int,
        order: Dict[str, object],
        trade: Dict[str, object],
    ) -> None:
        time.sleep(0.05)
        if self._closed:
            return
        self._callback(
            "order_async_response",
            {
                "account_id": account,
                "seq": seq,
                "order_id": order_id,
                "error_id": 0,
                "error_msg": "",
            },
        )
        self._callback("order", dict(order))
        self._callback("trade", dict(trade))
        self._callback("position", dict(self.get_position(account, symbol) or {}))
        self._callback("asset", dict(self._assets[account]))

    def _emit_async_cancel_callbacks(
        self,
        account: str,
        order_id: int,
        seq: int,
        order: Dict[str, object],
    ) -> None:
        time.sleep(0.05)
        if self._closed:
            return
        self._callback(
            "cancel_async_response",
            {
                "account_id": account,
                "order_id": order_id,
                "seq": seq,
                "cancel_result": 0,
                "error_id": 0,
                "error_msg": "",
            },
        )
        self._callback("order", dict(order))
