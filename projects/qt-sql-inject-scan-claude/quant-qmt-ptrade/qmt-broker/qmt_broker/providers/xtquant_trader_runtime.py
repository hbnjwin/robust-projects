import threading
from typing import Dict, List, Optional

from qmt_broker.config import BrokerConfig
from qmt_broker.providers.base import TradeProvider, TradeProviderCallback


def _normalize_scalar(value):  # type: ignore[no-untyped-def]
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            return value
    return value


_XT_TRADER_FIELD_ALIASES = {
    "m_strAccountID": "account_id",
    "m_nAccountType": "account_type",
    "m_nStatus": "status",
    "m_strStatusMsg": "status_msg",
    "m_nOrderID": "order_id",
    "m_strOrderSysID": "order_sysid",
    "m_strStockCode": "stock_code",
    "m_nOrderType": "order_type",
    "m_nOrderVolume": "order_volume",
    "m_nPriceType": "price_type",
    "m_dPrice": "price",
    "m_nTradedVolume": "traded_volume",
    "m_dTradedPrice": "traded_price",
    "m_nOrderStatus": "order_status",
    "m_strStatusMsg": "status_msg",
    "m_strStrategyName": "strategy_name",
    "m_strOrderRemark": "order_remark",
    "m_dCash": "cash",
    "m_dFrozenCash": "frozen_cash",
    "m_dMarketValue": "market_value",
    "m_dTotalAsset": "total_asset",
    "m_dTotalAssset": "total_asset",
    "m_nVolume": "volume",
    "m_nCanUseVolume": "can_use_volume",
    "m_dOpenPrice": "open_price",
    "m_nOrderTime": "order_time",
    "m_strTradedID": "traded_id",
    "m_nTradedTime": "traded_time",
    "m_dTradedAmount": "traded_amount",
    "m_nErrorID": "error_id",
    "m_strErrorMsg": "error_msg",
    "m_nCancelResult": "cancel_result",
    "m_nSeq": "seq",
    "m_nMarket": "market",
}

_XT_TRADER_CLASS_FIELDS = {
    "XtAsset": ["account_type", "account_id", "cash", "frozen_cash", "market_value", "total_asset"],
    "XtOrder": [
        "account_type",
        "account_id",
        "stock_code",
        "order_id",
        "order_sysid",
        "order_time",
        "order_type",
        "order_volume",
        "price_type",
        "price",
        "traded_volume",
        "traded_price",
        "order_status",
        "status_msg",
        "strategy_name",
        "order_remark",
    ],
    "XtTrade": [
        "account_type",
        "account_id",
        "stock_code",
        "order_type",
        "traded_id",
        "traded_time",
        "traded_price",
        "traded_volume",
        "traded_amount",
        "order_id",
        "order_sysid",
        "strategy_name",
        "order_remark",
    ],
    "XtPosition": [
        "account_type",
        "account_id",
        "stock_code",
        "volume",
        "can_use_volume",
        "open_price",
        "market_value",
        "frozen_volume",
        "on_road_volume",
        "yesterday_volume",
    ],
    "XtOrderError": [
        "account_type",
        "account_id",
        "order_id",
        "error_id",
        "error_msg",
        "strategy_name",
        "order_remark",
    ],
    "XtCancelError": [
        "account_type",
        "account_id",
        "order_id",
        "market",
        "order_sysid",
        "error_id",
        "error_msg",
    ],
    "XtOrderResponse": [
        "account_type",
        "account_id",
        "order_id",
        "strategy_name",
        "order_remark",
        "seq",
    ],
    "XtCancelOrderResponse": [
        "account_type",
        "account_id",
        "cancel_result",
        "order_id",
        "order_sysid",
        "seq",
    ],
}


def _safe_getattr(obj, name):  # type: ignore[no-untyped-def]
    try:
        return getattr(obj, name)
    except Exception:
        return None


def _iter_object_attributes(obj):  # type: ignore[no-untyped-def]
    values = {}
    if hasattr(obj, "__dict__"):
        for key, value in vars(obj).items():
            values[key] = value
    for name in dir(obj):
        if name.startswith("__"):
            continue
        if name in values:
            continue
        value = _safe_getattr(obj, name)
        if callable(value):
            continue
        values[name] = value
    return values


def _normalize_object(obj) -> Dict[str, object]:  # type: ignore[no-untyped-def]
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return {key: _normalize_scalar(value) for key, value in obj.items()}
    normalized = {}
    raw_values = _iter_object_attributes(obj)
    class_name = obj.__class__.__name__
    preferred_fields = _XT_TRADER_CLASS_FIELDS.get(class_name, [])
    for raw_name, raw_value in raw_values.items():
        value = _normalize_scalar(raw_value)
        canonical_name = _XT_TRADER_FIELD_ALIASES.get(raw_name, raw_name)
        if canonical_name not in normalized:
            normalized[canonical_name] = value
        if raw_name == canonical_name and raw_name in preferred_fields:
            normalized[raw_name] = value
    if preferred_fields:
        ordered = {}
        for field_name in preferred_fields:
            if field_name in normalized:
                ordered[field_name] = normalized[field_name]
        for field_name, value in normalized.items():
            if field_name not in ordered:
                ordered[field_name] = value
        normalized = ordered
    if normalized:
        return normalized
    return {"value": _normalize_scalar(obj)}


class _TraderCallbackBridge:  # type: ignore[no-untyped-def]
    def __init__(self, emit):
        self.emit = emit

    def on_disconnected(self):
        self.emit("disconnected", {"connected": False})

    def on_account_status(self, status):
        self.emit("account_status", _normalize_object(status))

    def on_stock_order(self, order):
        self.emit("order", _normalize_object(order))

    def on_stock_asset(self, asset):
        self.emit("asset", _normalize_object(asset))

    def on_stock_trade(self, trade):
        self.emit("trade", _normalize_object(trade))

    def on_stock_position(self, position):
        self.emit("position", _normalize_object(position))

    def on_order_error(self, order_error):
        self.emit("order_error", _normalize_object(order_error))

    def on_cancel_error(self, cancel_error):
        self.emit("cancel_error", _normalize_object(cancel_error))

    def on_order_stock_async_response(self, response):
        self.emit("order_async_response", _normalize_object(response))

    def on_cancel_order_stock_async_response(self, response):
        self.emit("cancel_async_response", _normalize_object(response))


class XtQuantTradeProvider(TradeProvider):
    def __init__(self, config: BrokerConfig) -> None:
        if not config.trader_path:
            raise RuntimeError("QMT_TRADER_PATH is required for xtquant trade provider")
        try:
            from xtquant import xtconstant, xttrader, xttype
        except Exception as exc:
            raise RuntimeError(
                "xtquant trade import failed. Run qmt-broker on the Windows machine that has QMT and xtquant."
            ) from exc
        self._config = config
        self._xtconstant = xtconstant
        self._xttrader = xttrader
        self._xttype = xttype
        self._lock = threading.RLock()
        self._callback: TradeProviderCallback = lambda topic, payload: None
        self._bridge = _TraderCallbackBridge(self._emit)
        self._trader = None
        self._connected = False
        self._subscribed_accounts = {}
        self._account_statuses: Dict[str, Dict[str, object]] = {}

    def name(self) -> str:
        return "xtquant"

    def capabilities(self) -> Dict[str, object]:
        return {
            "provider": "xtquant",
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
                "account_infos",
                "account_statuses",
                "asset",
                "orders",
                "order",
                "trades",
                "positions",
                "position",
                "order_place",
                "order_cancel",
                "credit_detail",
                "credit_compacts",
                "credit_subjects",
                "credit_slo_codes",
                "credit_assure",
            ],
            "notes": [
                "trader requires miniQMT userdata path",
                "subscribe(account) is performed lazily per account",
            ],
        }

    def status(self) -> Dict[str, object]:
        account_statuses = self.get_account_statuses()
        return {
            "provider": "xtquant",
            "connected": self._connected,
            "trader_path": self._config.trader_path,
            "session_id": self._config.trader_session_id,
            "accounts": sorted(self._subscribed_accounts.keys()),
            "account_statuses": account_statuses,
        }

    def get_account_infos(self) -> List[Dict[str, object]]:
        trader = self._ensure_trader()
        query = getattr(trader, "query_account_infos", None)
        if not callable(query):
            return []
        result = query() or []
        return [_normalize_object(item) for item in result]

    def get_account_statuses(self) -> List[Dict[str, object]]:
        if self._account_statuses:
            return [dict(item) for item in self._account_statuses.values()]
        trader = self._ensure_trader()
        query = getattr(trader, "query_account_status", None)
        if not callable(query):
            return []
        result = query() or []
        normalized = [_normalize_object(item) for item in result]
        for item in normalized:
            key = self._account_status_key(item)
            if key:
                self._account_statuses[key] = dict(item)
        return normalized

    def set_event_callback(self, callback: TradeProviderCallback) -> None:
        self._callback = callback

    def get_asset(self, account_id: str = "", account_type: str = "") -> Optional[Dict[str, object]]:
        account = self._ensure_account(account_id, account_type)
        asset = self._ensure_trader().query_stock_asset(account)
        return _normalize_object(asset) if asset is not None else None

    def get_orders(self, account_id: str = "", account_type: str = "") -> List[Dict[str, object]]:
        account = self._ensure_account(account_id, account_type)
        return [_normalize_object(item) for item in self._ensure_trader().query_stock_orders(account)]

    def get_order(self, account_id: str, order_id: int, account_type: str = "") -> Optional[Dict[str, object]]:
        account = self._ensure_account(account_id, account_type)
        order = self._ensure_trader().query_stock_order(account, int(order_id))
        return _normalize_object(order) if order is not None else None

    def get_trades(self, account_id: str = "", account_type: str = "") -> List[Dict[str, object]]:
        account = self._ensure_account(account_id, account_type)
        return [_normalize_object(item) for item in self._ensure_trader().query_stock_trades(account)]

    def get_positions(self, account_id: str = "", account_type: str = "") -> List[Dict[str, object]]:
        account = self._ensure_account(account_id, account_type)
        return [_normalize_object(item) for item in self._ensure_trader().query_stock_positions(account)]

    def get_position(
        self,
        account_id: str,
        symbol: str,
        account_type: str = "",
    ) -> Optional[Dict[str, object]]:
        account = self._ensure_account(account_id, account_type)
        position = self._ensure_trader().query_stock_position(account, symbol)
        return _normalize_object(position) if position is not None else None

    def place_order(self, payload: Dict[str, object]) -> Dict[str, object]:
        account = self._ensure_account(
            str(payload.get("account_id", "")),
            str(payload.get("account_type", "")),
        )
        side = str(payload.get("side", "")).lower()
        order_type = payload.get("order_type")
        if order_type is None:
            order_type = self._xtconstant.STOCK_BUY if side == "buy" else self._xtconstant.STOCK_SELL
        price_type = self._resolve_price_type(payload.get("price_type", "fix"))
        symbol = str(payload.get("symbol", ""))
        volume = int(payload.get("volume", 0))
        price = float(payload.get("price", 0))
        strategy_name = str(payload.get("strategy_name", ""))
        order_remark = str(payload.get("order_remark", ""))
        is_async = bool(payload.get("async", False))
        trader = self._ensure_trader()
        if is_async:
            seq = trader.order_stock_async(
                account,
                symbol,
                int(order_type),
                volume,
                price_type,
                price,
                strategy_name,
                order_remark,
            )
            return {"ok": seq > 0, "seq": seq}
        order_id = trader.order_stock(
            account,
            symbol,
            int(order_type),
            volume,
            price_type,
            price,
            strategy_name,
            order_remark,
        )
        return {"ok": order_id > 0, "order_id": order_id}

    def cancel_order(self, payload: Dict[str, object]) -> Dict[str, object]:
        account = self._ensure_account(
            str(payload.get("account_id", "")),
            str(payload.get("account_type", "")),
        )
        trader = self._ensure_trader()
        is_async = bool(payload.get("async", False))
        if payload.get("order_sysid"):
            market = self._resolve_market(payload.get("market", ""))
            order_sysid = str(payload.get("order_sysid", ""))
            if is_async:
                seq = trader.cancel_order_stock_sysid_async(account, market, order_sysid)
                return {"ok": seq > 0, "seq": seq}
            result = trader.cancel_order_stock_sysid(account, market, order_sysid)
            return {"ok": result == 0, "cancel_result": result}
        order_id = int(payload.get("order_id", 0))
        if is_async:
            seq = trader.cancel_order_stock_async(account, order_id)
            return {"ok": seq > 0, "seq": seq}
        result = trader.cancel_order_stock(account, order_id)
        return {"ok": result == 0, "cancel_result": result}

    def get_credit_detail(self, account_id: str = "", account_type: str = "") -> Optional[Dict[str, object]]:
        account = self._ensure_account(account_id, account_type or "CREDIT")
        detail = self._ensure_trader().query_credit_detail(account)
        return _normalize_object(detail) if detail is not None else None

    def get_credit_compacts(self, account_id: str = "", account_type: str = "") -> List[Dict[str, object]]:
        account = self._ensure_account(account_id, account_type or "CREDIT")
        result = self._ensure_trader().query_stk_compacts(account) or []
        return [_normalize_object(item) for item in result]

    def get_credit_subjects(self, account_id: str = "", account_type: str = "") -> List[Dict[str, object]]:
        account = self._ensure_account(account_id, account_type or "CREDIT")
        result = self._ensure_trader().query_credit_subjects(account) or []
        return [_normalize_object(item) for item in result]

    def get_credit_slo_codes(self, account_id: str = "", account_type: str = "") -> List[Dict[str, object]]:
        account = self._ensure_account(account_id, account_type or "CREDIT")
        result = self._ensure_trader().query_credit_slo_code(account) or []
        return [_normalize_object(item) for item in result]

    def get_credit_assure(self, account_id: str = "", account_type: str = "") -> List[Dict[str, object]]:
        account = self._ensure_account(account_id, account_type or "CREDIT")
        result = self._ensure_trader().query_credit_assure(account) or []
        return [_normalize_object(item) for item in result]

    def close(self) -> None:
        if self._trader is not None:
            try:
                self._trader.stop()
            except Exception:
                return

    def _emit(self, topic: str, payload: Dict[str, object]) -> None:
        if topic == "account_status":
            key = self._account_status_key(payload)
            if key:
                self._account_statuses[key] = dict(payload)
        elif topic == "disconnected":
            self._connected = False
        self._callback(topic, payload)

    def _ensure_trader(self):  # type: ignore[no-untyped-def]
        with self._lock:
            if self._trader is not None:
                return self._trader
            trader = self._xttrader.XtQuantTrader(
                self._config.trader_path,
                self._config.trader_session_id,
                callback=self._bridge,
            )
            trader.register_callback(self._bridge)
            relaxed = getattr(trader, "set_relaxed_response_order_enabled", None)
            if callable(relaxed):
                try:
                    relaxed(True)
                except Exception:
                    pass
            trader.start()
            result = trader.connect()
            if result != 0:
                raise RuntimeError("xttrader connect failed with code %s" % result)
            self._connected = True
            self._trader = trader
            return self._trader

    def _ensure_account(self, account_id: str, account_type: str):  # type: ignore[no-untyped-def]
        resolved_account_id = account_id or self._config.trader_account_id
        resolved_account_type = (account_type or self._config.trader_account_type or "STOCK").upper()
        if not resolved_account_id:
            raise RuntimeError("account_id is required")
        with self._lock:
            key = "%s:%s" % (resolved_account_type, resolved_account_id)
            account = self._subscribed_accounts.get(key)
            if account is None:
                account = self._xttype.StockAccount(resolved_account_id, resolved_account_type)
                result = self._ensure_trader().subscribe(account)
                if result != 0:
                    raise RuntimeError("xttrader subscribe failed with code %s" % result)
                self._subscribed_accounts[key] = account
            return account

    def _resolve_price_type(self, raw_value) -> int:  # type: ignore[no-untyped-def]
        if isinstance(raw_value, int):
            return raw_value
        mapping = {
            "latest": self._xtconstant.LATEST_PRICE,
            "fix": self._xtconstant.FIX_PRICE,
            "limit": self._xtconstant.FIX_PRICE,
            "sh_5_cancel": self._xtconstant.MARKET_SH_CONVERT_5_CANCEL,
            "sh_5_limit": self._xtconstant.MARKET_SH_CONVERT_5_LIMIT,
            "sz_peer_first": self._xtconstant.MARKET_PEER_PRICE_FIRST,
            "sz_mine_first": self._xtconstant.MARKET_MINE_PRICE_FIRST,
            "sz_inst_rest_cancel": self._xtconstant.MARKET_SZ_INSTBUSI_RESTCANCEL,
            "sz_5_cancel": self._xtconstant.MARKET_SZ_CONVERT_5_CANCEL,
            "sz_full_or_cancel": self._xtconstant.MARKET_SZ_FULL_OR_CANCEL,
        }
        return mapping.get(str(raw_value).lower(), self._xtconstant.FIX_PRICE)

    def _resolve_market(self, raw_value) -> int:  # type: ignore[no-untyped-def]
        if isinstance(raw_value, int):
            return raw_value
        mapping = {
            "sh": self._xtconstant.SH_MARKET,
            "sz": self._xtconstant.SZ_MARKET,
            "0": self._xtconstant.SH_MARKET,
            "1": self._xtconstant.SZ_MARKET,
        }
        value = mapping.get(str(raw_value).lower())
        if value is None:
            raise RuntimeError("market is required when canceling by order_sysid")
        return value

    def _account_status_key(self, payload: Dict[str, object]) -> str:
        account_id = str(payload.get("account_id") or payload.get("accountid") or "").strip()
        account_type = str(payload.get("account_type") or payload.get("accounttype") or "").strip().upper()
        if not account_id:
            return ""
        return "%s:%s" % (account_type or "UNKNOWN", account_id)
