import json
import queue
import time
from datetime import date, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, List, Optional
from urllib.parse import parse_qs, urlparse

from qmt_broker.broker import MarketDataBroker
from qmt_broker.config import BrokerConfig
from qmt_broker.models import StreamRequest, parse_topics, topic_descriptor
from qmt_broker.trade_broker import TradeBroker
from qmt_broker.trade_models import TradeStreamFilter, parse_trade_topics

CLIENT_DISCONNECT_ERRORS = (BrokenPipeError, ConnectionResetError, ConnectionAbortedError)


def _json_safe(value):  # type: ignore[no-untyped-def]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "item"):
        try:
            return _json_safe(value.item())
        except Exception:
            pass
    if hasattr(value, "to_dict"):
        try:
            return _json_safe(value.to_dict())
        except Exception:
            pass
    if hasattr(value, "__dict__"):
        try:
            return _json_safe(vars(value))
        except Exception:
            pass
    return str(value)


def json_bytes(payload) -> bytes:  # type: ignore[no-untyped-def]
    return json.dumps(_json_safe(payload), ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _parse_bool_flag(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


class BrokerRequestHandler(BaseHTTPRequestHandler):
    server_version = "QmtBroker/0.1"
    protocol_version = "HTTP/1.1"

    def handle(self) -> None:
        try:
            super().handle()
        except CLIENT_DISCONNECT_ERRORS:
            return

    def do_GET(self) -> None:
        handler = getattr(self, "_handle_get", None)
        if handler is None:
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "method_not_allowed")
            return
        try:
            handler()
        except CLIENT_DISCONNECT_ERRORS:
            return
        except Exception as exc:
            self._send_json(HTTPStatus.BAD_GATEWAY, {"error": "provider_failure", "detail": str(exc)})

    def do_POST(self) -> None:
        if self.path.rstrip("/") == "/v1/market/prefetch":
            if not self._authorize():
                return
            body = self._read_json()
            if body is None:
                return
            try:
                result = self.server.market_broker.prefetch_history(
                    str(body.get("symbol", "")),
                    str(body.get("period", "1m")),
                    str(body.get("start_time", "")),
                    str(body.get("end_time", "")),
                    wait_timeout_ms=int(body.get("wait_timeout_ms", 0)),
                    poll_interval_ms=int(body.get("poll_interval_ms", 250)),
                )
            except Exception as exc:
                self._send_json(HTTPStatus.BAD_GATEWAY, {"error": "provider_failure", "detail": str(exc)})
                return
            self._send_json(HTTPStatus.OK, result)
            return
        if self.path.rstrip("/") == "/v1/trade/order":
            if not self._authorize():
                return
            body = self._read_json()
            if body is None:
                return
            try:
                result = self.server.trade_broker.place_order(body)
            except Exception as exc:
                self._send_json(HTTPStatus.BAD_GATEWAY, {"error": "provider_failure", "detail": str(exc)})
                return
            self._send_json(HTTPStatus.OK, result)
            return
        if self.path.rstrip("/") == "/v1/trade/approve":
            if not self._authorize():
                return
            body = self._read_json()
            if body is None:
                return
            try:
                result = self.server.trade_broker.approve_order_as(
                    str(body.get("request_id", "")),
                    approver_id=str(body.get("approver_id", "")),
                    approver_secret=str(body.get("approver_secret", "")),
                )
            except Exception as exc:
                self._send_json(HTTPStatus.BAD_GATEWAY, {"error": "provider_failure", "detail": str(exc)})
                return
            self._send_json(HTTPStatus.OK, result)
            return
        if self.path.rstrip("/") == "/v1/trade/reject":
            if not self._authorize():
                return
            body = self._read_json()
            if body is None:
                return
            try:
                result = self.server.trade_broker.reject_order_as(
                    str(body.get("request_id", "")),
                    str(body.get("reason", "")),
                    approver_id=str(body.get("approver_id", "")),
                    approver_secret=str(body.get("approver_secret", "")),
                )
            except Exception as exc:
                self._send_json(HTTPStatus.BAD_GATEWAY, {"error": "provider_failure", "detail": str(exc)})
                return
            self._send_json(HTTPStatus.OK, result)
            return
        if self.path.rstrip("/") == "/v1/trade/revoke":
            if not self._authorize():
                return
            body = self._read_json()
            if body is None:
                return
            try:
                result = self.server.trade_broker.revoke_order(
                    str(body.get("request_id", "")),
                    str(body.get("reason", "")),
                )
            except Exception as exc:
                self._send_json(HTTPStatus.BAD_GATEWAY, {"error": "provider_failure", "detail": str(exc)})
                return
            self._send_json(HTTPStatus.OK, result)
            return
        if self.path.rstrip("/") == "/v1/trade/cancel":
            if not self._authorize():
                return
            body = self._read_json()
            if body is None:
                return
            try:
                result = self.server.trade_broker.cancel_order(body)
            except Exception as exc:
                self._send_json(HTTPStatus.BAD_GATEWAY, {"error": "provider_failure", "detail": str(exc)})
                return
            self._send_json(HTTPStatus.OK, result)
            return
        if self.path.rstrip("/") != "/v1/query":
            self._send_error(HTTPStatus.NOT_FOUND, "not_found")
            return
        if not self._authorize():
            return
        body = self._read_json()
        if body is None:
            return
        kind = str(body.get("kind", ""))
        symbol = str(body.get("symbol", ""))
        limit = int(body.get("limit", 200))
        start_time = str(body.get("start_time", ""))
        end_time = str(body.get("end_time", ""))
        period = str(body.get("period", "1m"))
        run_prefetch = _parse_bool_flag(body.get("prefetch", False))
        wait_timeout_ms = int(body.get("wait_timeout_ms", 0))
        poll_interval_ms = int(body.get("poll_interval_ms", 250))
        try:
            if kind == "quote":
                result = self.server.market_broker.get_quote(symbol)
            elif kind == "bars":
                result = self.server.market_broker.get_bars(symbol, period, limit, start_time, end_time)
            elif kind == "ticks":
                tick_response = self.server.market_broker.get_ticks_response(
                    symbol,
                    limit,
                    start_time,
                    end_time,
                    run_prefetch=run_prefetch,
                    wait_timeout_ms=wait_timeout_ms,
                    poll_interval_ms=poll_interval_ms,
                )
                result = tick_response["result"]
            elif kind == "l2_quote":
                result = self.server.market_broker.get_l2_quote(symbol, limit, start_time, end_time)
            elif kind == "l2_order":
                result = self.server.market_broker.get_l2_order(symbol, limit, start_time, end_time)
            elif kind == "l2_transaction":
                result = self.server.market_broker.get_l2_transaction(symbol, limit, start_time, end_time)
            else:
                self._send_error(HTTPStatus.BAD_REQUEST, "unsupported_kind")
                return
        except Exception as exc:
            self._send_json(HTTPStatus.BAD_GATEWAY, {"error": "provider_failure", "detail": str(exc)})
            return
        payload = {"kind": kind, "symbol": symbol, "result": result}
        if kind == "ticks":
            payload["source"] = tick_response.get("source", "provider")
            payload["market_session"] = tick_response.get("market_session", {})
            payload["diagnostics"] = tick_response.get("diagnostics", {})
        self._send_json(HTTPStatus.OK, payload)

    def _handle_get(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self._send_json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "market_provider": self.server.market_broker.provider.name(),
                    "trade_provider": self.server.trade_broker.provider.name(),
                },
            )
            return
        if parsed.path == "/v1/capabilities":
            if not self._authorize():
                return
            self._send_json(
                HTTPStatus.OK,
                {
                    "market": self.server.market_broker.capabilities(),
                    "trade": self.server.trade_broker.capabilities(),
                },
            )
            return
        if parsed.path == "/v1/market/quote":
            if not self._authorize():
                return
            params = parse_qs(parsed.query)
            symbol = params.get("symbol", [""])[0]
            self._send_json(HTTPStatus.OK, {"symbol": symbol, "result": self.server.market_broker.get_quote(symbol)})
            return
        if parsed.path == "/v1/market/bars":
            if not self._authorize():
                return
            params = parse_qs(parsed.query)
            symbol = params.get("symbol", [""])[0]
            period = params.get("period", ["1m"])[0]
            limit = int(params.get("limit", ["240"])[0])
            start_time = params.get("start_time", [""])[0]
            end_time = params.get("end_time", [""])[0]
            result = self.server.market_broker.get_bars(symbol, period, limit, start_time, end_time)
            self._send_json(HTTPStatus.OK, {"symbol": symbol, "period": period, "result": result})
            return
        if parsed.path == "/v1/market/bars/diagnostics":
            if not self._authorize():
                return
            params = parse_qs(parsed.query)
            symbol = params.get("symbol", [""])[0]
            period = params.get("period", ["1m"])[0]
            limit = int(params.get("limit", ["240"])[0])
            start_time = params.get("start_time", [""])[0]
            end_time = params.get("end_time", [""])[0]
            run_prefetch = _parse_bool_flag(params.get("prefetch", ["0"])[0])
            wait_timeout_ms = int(params.get("wait_timeout_ms", ["0"])[0])
            poll_interval_ms = int(params.get("poll_interval_ms", ["250"])[0])
            result = self.server.market_broker.diagnose_bars(
                symbol,
                period,
                limit,
                start_time,
                end_time,
                run_prefetch=run_prefetch,
                wait_timeout_ms=wait_timeout_ms,
                poll_interval_ms=poll_interval_ms,
            )
            self._send_json(HTTPStatus.OK, {"symbol": symbol, "period": period, "result": result})
            return
        if parsed.path == "/v1/market/ticks":
            if not self._authorize():
                return
            params = parse_qs(parsed.query)
            symbol = params.get("symbol", [""])[0]
            limit = int(params.get("limit", ["200"])[0])
            start_time = params.get("start_time", [""])[0]
            end_time = params.get("end_time", [""])[0]
            run_prefetch = _parse_bool_flag(params.get("prefetch", ["0"])[0])
            wait_timeout_ms = int(params.get("wait_timeout_ms", ["0"])[0])
            poll_interval_ms = int(params.get("poll_interval_ms", ["250"])[0])
            tick_response = self.server.market_broker.get_ticks_response(
                symbol,
                limit,
                start_time,
                end_time,
                run_prefetch=run_prefetch,
                wait_timeout_ms=wait_timeout_ms,
                poll_interval_ms=poll_interval_ms,
            )
            self._send_json(
                HTTPStatus.OK,
                {
                    "symbol": symbol,
                    "source": tick_response.get("source", "provider"),
                    "market_session": tick_response.get("market_session", {}),
                    "diagnostics": tick_response.get("diagnostics", {}),
                    "result": tick_response["result"],
                },
            )
            return
        if parsed.path == "/v1/market/ticks/keepalive":
            if not self._authorize():
                return
            self._send_json(HTTPStatus.OK, self.server.market_broker.get_tick_keepalive_status())
            return
        if parsed.path == "/v1/market/ticks/archive/status":
            if not self._authorize():
                return
            self._send_json(HTTPStatus.OK, self.server.market_broker.get_tick_archive_status())
            return
        if parsed.path == "/v1/market/ticks/archive":
            if not self._authorize():
                return
            params = parse_qs(parsed.query)
            symbol = params.get("symbol", [""])[0]
            if not symbol:
                self._send_error(HTTPStatus.BAD_REQUEST, "missing_symbol")
                return
            trade_date = params.get("trade_date", [""])[0]
            limit = int(params.get("limit", ["500"])[0])
            result = self.server.market_broker.get_tick_archive_records(symbol, trade_date, limit)
            self._send_json(
                HTTPStatus.OK,
                {
                    "symbol": symbol,
                    "trade_date": trade_date,
                    "archive": self.server.market_broker.get_tick_archive_status(),
                    "result": result,
                },
            )
            return
        if parsed.path == "/v1/market/ticks/archive/bars":
            if not self._authorize():
                return
            params = parse_qs(parsed.query)
            symbol = params.get("symbol", [""])[0]
            if not symbol:
                self._send_error(HTTPStatus.BAD_REQUEST, "missing_symbol")
                return
            trade_date = params.get("trade_date", [""])[0]
            period = params.get("period", ["1m"])[0]
            limit = int(params.get("limit", ["240"])[0])
            result = self.server.market_broker.get_tick_archive_bars(symbol, trade_date, period, limit)
            self._send_json(
                HTTPStatus.OK,
                {
                    "symbol": symbol,
                    "trade_date": trade_date,
                    "period": period,
                    "archive": self.server.market_broker.get_tick_archive_status(),
                    "result": result,
                },
            )
            return
        if parsed.path == "/v1/market/ticks/archive/features":
            if not self._authorize():
                return
            params = parse_qs(parsed.query)
            symbol = params.get("symbol", [""])[0]
            if not symbol:
                self._send_error(HTTPStatus.BAD_REQUEST, "missing_symbol")
                return
            trade_date = params.get("trade_date", [""])[0]
            result = self.server.market_broker.get_tick_archive_features(symbol, trade_date)
            self._send_json(
                HTTPStatus.OK,
                {
                    "symbol": symbol,
                    "trade_date": trade_date,
                    "archive": self.server.market_broker.get_tick_archive_status(),
                    "result": result,
                },
            )
            return
        if parsed.path == "/v1/market/symbols":
            if not self._authorize():
                return
            self._send_json(HTTPStatus.OK, self.server.market_broker.get_symbol_catalog())
            return
        if parsed.path == "/v1/market/l2/quote":
            if not self._authorize():
                return
            params = parse_qs(parsed.query)
            symbol = params.get("symbol", [""])[0]
            limit = int(params.get("limit", ["200"])[0])
            start_time = params.get("start_time", [""])[0]
            end_time = params.get("end_time", [""])[0]
            result = self.server.market_broker.get_l2_quote(symbol, limit, start_time, end_time)
            self._send_json(HTTPStatus.OK, {"symbol": symbol, "result": result})
            return
        if parsed.path == "/v1/market/l2/orders":
            if not self._authorize():
                return
            params = parse_qs(parsed.query)
            symbol = params.get("symbol", [""])[0]
            limit = int(params.get("limit", ["200"])[0])
            start_time = params.get("start_time", [""])[0]
            end_time = params.get("end_time", [""])[0]
            result = self.server.market_broker.get_l2_order(symbol, limit, start_time, end_time)
            self._send_json(HTTPStatus.OK, {"symbol": symbol, "result": result})
            return
        if parsed.path == "/v1/market/l2/transactions":
            if not self._authorize():
                return
            params = parse_qs(parsed.query)
            symbol = params.get("symbol", [""])[0]
            limit = int(params.get("limit", ["200"])[0])
            start_time = params.get("start_time", [""])[0]
            end_time = params.get("end_time", [""])[0]
            result = self.server.market_broker.get_l2_transaction(symbol, limit, start_time, end_time)
            self._send_json(HTTPStatus.OK, {"symbol": symbol, "result": result})
            return
        if parsed.path == "/v1/stream":
            if not self._authorize():
                return
            self._handle_stream(parsed.query)
            return
        if parsed.path == "/v1/trade/status":
            if not self._authorize():
                return
            self._send_json(HTTPStatus.OK, self.server.trade_broker.status())
            return
        if parsed.path == "/v1/trade/account-infos":
            if not self._authorize():
                return
            self._send_json(HTTPStatus.OK, {"result": self.server.trade_broker.account_infos()})
            return
        if parsed.path == "/v1/trade/account-statuses":
            if not self._authorize():
                return
            self._send_json(HTTPStatus.OK, {"result": self.server.trade_broker.account_statuses()})
            return
        if parsed.path == "/v1/trade/policy":
            if not self._authorize():
                return
            self._send_json(HTTPStatus.OK, self.server.trade_broker.policy_status())
            return
        if parsed.path == "/v1/trade/notifications":
            if not self._authorize():
                return
            self._send_json(HTTPStatus.OK, self.server.trade_broker.notification_status())
            return
        if parsed.path == "/v1/trade/requests":
            if not self._authorize():
                return
            params = parse_qs(parsed.query)
            status = params.get("status", [""])[0]
            limit = int(params.get("limit", ["100"])[0])
            self._send_json(HTTPStatus.OK, {"result": self.server.trade_broker.request_list(status=status, limit=limit)})
            return
        if parsed.path == "/v1/trade/request":
            if not self._authorize():
                return
            params = parse_qs(parsed.query)
            request_id = params.get("request_id", [""])[0]
            self._send_json(HTTPStatus.OK, {"result": self.server.trade_broker.request_status(request_id)})
            return
        if parsed.path == "/v1/trade/request/by-order-id":
            if not self._authorize():
                return
            params = parse_qs(parsed.query)
            order_id = params.get("order_id", [""])[0]
            self._send_json(HTTPStatus.OK, {"result": self.server.trade_broker.request_by_order_id(order_id)})
            return
        if parsed.path == "/v1/trade/request/by-seq":
            if not self._authorize():
                return
            params = parse_qs(parsed.query)
            seq = params.get("seq", [""])[0]
            self._send_json(HTTPStatus.OK, {"result": self.server.trade_broker.request_by_seq(seq)})
            return
        if parsed.path == "/v1/trade/request/by-order-sysid":
            if not self._authorize():
                return
            params = parse_qs(parsed.query)
            order_sysid = params.get("order_sysid", [""])[0]
            self._send_json(HTTPStatus.OK, {"result": self.server.trade_broker.request_by_order_sysid(order_sysid)})
            return
        if parsed.path == "/v1/trade/request/by-trade-id":
            if not self._authorize():
                return
            params = parse_qs(parsed.query)
            trade_id = params.get("trade_id", [""])[0]
            self._send_json(HTTPStatus.OK, {"result": self.server.trade_broker.request_by_trade_id(trade_id)})
            return
        if parsed.path == "/v1/trade/audit":
            if not self._authorize():
                return
            params = parse_qs(parsed.query)
            limit = int(params.get("limit", ["50"])[0])
            self._send_json(HTTPStatus.OK, {"result": self.server.trade_broker.audit_tail(limit)})
            return
        if parsed.path == "/v1/trade/asset":
            if not self._authorize():
                return
            params = parse_qs(parsed.query)
            self._send_trade_result(
                lambda: self.server.trade_broker.get_asset(
                    account_id=params.get("account_id", [""])[0],
                    account_type=params.get("account_type", [""])[0],
                )
            )
            return
        if parsed.path == "/v1/trade/credit/detail":
            if not self._authorize():
                return
            params = parse_qs(parsed.query)
            self._send_trade_result(
                lambda: self.server.trade_broker.get_credit_detail(
                    account_id=params.get("account_id", [""])[0],
                    account_type=params.get("account_type", ["CREDIT"])[0],
                )
            )
            return
        if parsed.path == "/v1/trade/credit/compacts":
            if not self._authorize():
                return
            params = parse_qs(parsed.query)
            self._send_trade_result(
                lambda: self.server.trade_broker.get_credit_compacts(
                    account_id=params.get("account_id", [""])[0],
                    account_type=params.get("account_type", ["CREDIT"])[0],
                )
            )
            return
        if parsed.path == "/v1/trade/credit/subjects":
            if not self._authorize():
                return
            params = parse_qs(parsed.query)
            self._send_trade_result(
                lambda: self.server.trade_broker.get_credit_subjects(
                    account_id=params.get("account_id", [""])[0],
                    account_type=params.get("account_type", ["CREDIT"])[0],
                )
            )
            return
        if parsed.path == "/v1/trade/credit/slo-codes":
            if not self._authorize():
                return
            params = parse_qs(parsed.query)
            self._send_trade_result(
                lambda: self.server.trade_broker.get_credit_slo_codes(
                    account_id=params.get("account_id", [""])[0],
                    account_type=params.get("account_type", ["CREDIT"])[0],
                )
            )
            return
        if parsed.path == "/v1/trade/credit/assure":
            if not self._authorize():
                return
            params = parse_qs(parsed.query)
            self._send_trade_result(
                lambda: self.server.trade_broker.get_credit_assure(
                    account_id=params.get("account_id", [""])[0],
                    account_type=params.get("account_type", ["CREDIT"])[0],
                )
            )
            return
        if parsed.path == "/v1/trade/orders":
            if not self._authorize():
                return
            params = parse_qs(parsed.query)
            self._send_trade_result(
                lambda: self.server.trade_broker.get_orders(
                    account_id=params.get("account_id", [""])[0],
                    account_type=params.get("account_type", [""])[0],
                )
            )
            return
        if parsed.path == "/v1/trade/order":
            if not self._authorize():
                return
            params = parse_qs(parsed.query)
            account_id = params.get("account_id", [""])[0]
            account_type = params.get("account_type", [""])[0]
            order_id = int(params.get("order_id", ["0"])[0])
            self._send_trade_result(
                lambda: self.server.trade_broker.get_order(
                    account_id=account_id,
                    order_id=order_id,
                    account_type=account_type,
                )
            )
            return
        if parsed.path == "/v1/trade/trades":
            if not self._authorize():
                return
            params = parse_qs(parsed.query)
            self._send_trade_result(
                lambda: self.server.trade_broker.get_trades(
                    account_id=params.get("account_id", [""])[0],
                    account_type=params.get("account_type", [""])[0],
                )
            )
            return
        if parsed.path == "/v1/trade/positions":
            if not self._authorize():
                return
            params = parse_qs(parsed.query)
            self._send_trade_result(
                lambda: self.server.trade_broker.get_positions(
                    account_id=params.get("account_id", [""])[0],
                    account_type=params.get("account_type", [""])[0],
                )
            )
            return
        if parsed.path == "/v1/trade/position":
            if not self._authorize():
                return
            params = parse_qs(parsed.query)
            self._send_trade_result(
                lambda: self.server.trade_broker.get_position(
                    account_id=params.get("account_id", [""])[0],
                    symbol=params.get("symbol", [""])[0],
                    account_type=params.get("account_type", [""])[0],
                )
            )
            return
        if parsed.path == "/v1/trade/stream":
            if not self._authorize():
                return
            self._handle_trade_stream(parsed.query)
            return
        self._send_error(HTTPStatus.NOT_FOUND, "not_found")

    def _handle_stream(self, raw_query: str) -> None:
        params = parse_qs(raw_query)
        topics_raw = params.get("topics", ["quote"])[0]
        symbol = params.get("symbol", [""])[0]
        period = params.get("period", ["1m"])[0]
        market = params.get("market", [""])[0]
        replay = int(params.get("replay", ["0"])[0])
        topics = parse_topics(topics_raw, symbol=symbol, period=period, market=market)
        if not topics:
            self._send_error(HTTPStatus.BAD_REQUEST, "missing_topics")
            return
        stream_id, stream_queue = self.server.market_broker.open_stream(StreamRequest(topics=topics, replay=replay))
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        try:
            self._write_sse(
                "ready",
                {
                    "stream_id": stream_id,
                    "topics": [topic_descriptor(topic) for topic in topics],
                },
            )
            while True:
                try:
                    message = stream_queue.get(timeout=self.server.config.heartbeat_interval_sec)
                except queue.Empty:
                    self._write_sse("heartbeat", {"ts_ms": int(time.time() * 1000)})
                    continue
                self._write_sse(message["type"], message["event"])
        except CLIENT_DISCONNECT_ERRORS:
            return
        finally:
            self.server.market_broker.close_stream(stream_id)

    def _handle_trade_stream(self, raw_query: str) -> None:
        params = parse_qs(raw_query)
        topics = parse_trade_topics(params.get("topics", ["order,trade"])[0])
        if not topics:
            self._send_error(HTTPStatus.BAD_REQUEST, "missing_topics")
            return
        filter_spec = TradeStreamFilter(
            topics=topics,
            account_id=params.get("account_id", [""])[0],
            replay=int(params.get("replay", ["0"])[0]),
        )
        stream_id, stream_queue = self.server.trade_broker.open_stream(filter_spec)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        try:
            self._write_sse(
                "ready",
                {
                    "stream_id": stream_id,
                    "topics": topics,
                    "account_id": filter_spec.account_id,
                },
            )
            while True:
                try:
                    message = stream_queue.get(timeout=self.server.config.heartbeat_interval_sec)
                except queue.Empty:
                    self._write_sse("heartbeat", {"ts_ms": int(time.time() * 1000)})
                    continue
                self._write_sse(message["type"], message["event"])
        except CLIENT_DISCONNECT_ERRORS:
            return
        finally:
            self.server.trade_broker.close_stream(stream_id)

    def _write_sse(self, event_name: str, payload: Dict[str, object]) -> None:
        data = json.dumps(payload, ensure_ascii=False)
        blob = "event: %s\ndata: %s\n\n" % (event_name, data)
        self.wfile.write(blob.encode("utf-8"))
        self.wfile.flush()

    def _authorize(self) -> bool:
        token = self.server.config.token
        if not token:
            return True
        header = self.headers.get("Authorization", "")
        if header == "Bearer %s" % token:
            return True
        self._send_json(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
        return False

    def _read_json(self) -> Optional[Dict[str, object]]:
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_error(HTTPStatus.BAD_REQUEST, "invalid_content_length")
            return None
        raw = self.rfile.read(content_length) if content_length > 0 else b"{}"
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            self._send_error(HTTPStatus.BAD_REQUEST, "invalid_json")
            return None

    def _send_json(self, status: HTTPStatus, payload) -> None:  # type: ignore[no-untyped-def]
        data = json_bytes(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_trade_result(self, producer) -> None:  # type: ignore[no-untyped-def]
        try:
            result = producer()
        except Exception as exc:
            self._send_json(HTTPStatus.BAD_GATEWAY, {"error": "trade_failure", "detail": str(exc)})
            return
        self._send_json(HTTPStatus.OK, {"result": result})

    def _send_error(self, status: HTTPStatus, code: str) -> None:
        self._send_json(status, {"error": code})

    def log_message(self, fmt: str, *args) -> None:  # type: ignore[override]
        return None


class BrokerHttpServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(
        self,
        server_address,
        market_broker: MarketDataBroker,
        trade_broker: TradeBroker,
        config: BrokerConfig,
    ):
        self.market_broker = market_broker
        self.trade_broker = trade_broker
        self.config = config
        super().__init__(server_address, BrokerRequestHandler)


def create_http_server(
    market_broker: MarketDataBroker,
    trade_broker: TradeBroker,
    config: BrokerConfig,
) -> BrokerHttpServer:
    return BrokerHttpServer((config.host, config.port), market_broker, trade_broker, config)


def serve_http(market_broker: MarketDataBroker, trade_broker: TradeBroker, config: BrokerConfig) -> None:
    server = create_http_server(market_broker, trade_broker, config)
    try:
        server.serve_forever()
    finally:
        server.server_close()
