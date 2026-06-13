import json
import subprocess
import sys
import threading
import time
from typing import Dict, List, Optional, Sequence, Tuple

from qmt_broker.models import SubscriptionTopic
from qmt_broker.providers.base import MarketDataProvider, ProviderCallback, normalize_limit


def _emit_provider_log(event: str, **payload: object) -> None:
    message = {"ts_ms": int(time.time() * 1000), "event": event, "provider": "xtquant", **payload}
    print(json.dumps(message, ensure_ascii=False), flush=True)


_BACKFILL_WAIT_TIMEOUT_MS = 5000
_BACKFILL_POLL_INTERVAL_MS = 250
_PREFETCH_SUBPROCESS_TIMEOUT_SEC = 12


def _normalize_scalar(value):  # type: ignore[no-untyped-def]
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            return value
    return value


def _normalize_record_dict(record: Dict[str, object]) -> Dict[str, object]:
    return {key: _normalize_scalar(value) for key, value in record.items()}


def _normalize_structured_array(array) -> List[Dict[str, object]]:  # type: ignore[no-untyped-def]
    if array is None:
        return []
    if hasattr(array, "dtype") and getattr(array.dtype, "names", None):
        names = list(array.dtype.names)
        records = []
        for row in array:
            records.append({name: _normalize_scalar(row[name]) for name in names})
        return records
    if isinstance(array, list):
        return [_normalize_record_dict(item) for item in array]
    return []


def _normalize_tabular_records(frame) -> List[Dict[str, object]]:  # type: ignore[no-untyped-def]
    if frame is None:
        return []
    if hasattr(frame, "to_dict"):
        try:
            records = frame.to_dict(orient="records")
        except TypeError:
            records = frame.to_dict("records")
        if not isinstance(records, list):
            return []
        index_values = list(frame.index) if hasattr(frame, "index") else []
        normalized_records: List[Dict[str, object]] = []
        for idx, record in enumerate(records):
            if not isinstance(record, dict):
                continue
            normalized = _normalize_record_dict(record)
            if idx < len(index_values):
                normalized.setdefault("time", _normalize_scalar(index_values[idx]))
            normalized_records.append(normalized)
        return normalized_records
    return _normalize_structured_array(frame)


_TICK_SUBPROCESS_SCRIPT = """
import contextlib
import json
import sys
import warnings

_stdout = sys.stdout

def _stderr_warning(message, category, filename, lineno, file=None, line=None):
    text = warnings.formatwarning(message, category, filename, lineno, line)
    print(text, file=sys.stderr, end="")

warnings.showwarning = _stderr_warning

params = json.loads(sys.argv[1])
with contextlib.redirect_stdout(sys.stderr):
    from xtquant import xtdata

    data = xtdata.get_market_data(
        stock_list=[params["symbol"]],
        period="tick",
        count=int(params["count"]),
        start_time=params.get("start_time", ""),
        end_time=params.get("end_time", ""),
    )
    rows = data.get(params["symbol"]) if isinstance(data, dict) else None
    result = []
    if rows is not None and hasattr(rows, "dtype") and getattr(rows.dtype, "names", None):
        names = list(rows.dtype.names)
        for row in rows:
            record = {}
            for name in names:
                value = row[name]
                if hasattr(value, "item"):
                    try:
                        value = value.item()
                    except Exception:
                        pass
                record[name] = value
            result.append(record)
    elif isinstance(rows, list):
        for row in rows:
            if isinstance(row, dict):
                normalized = {}
                for key, value in row.items():
                    if hasattr(value, "item"):
                        try:
                            value = value.item()
                        except Exception:
                            pass
                    normalized[key] = value
                result.append(normalized)

_stdout.write(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
_stdout.write("\\n")
""".strip()


_PREFETCH_SUBPROCESS_SCRIPT = """
import contextlib
import json
import sys
import warnings

_stdout = sys.stdout

def _stderr_warning(message, category, filename, lineno, file=None, line=None):
    text = warnings.formatwarning(message, category, filename, lineno, line)
    print(text, file=sys.stderr, end="")

warnings.showwarning = _stderr_warning

params = json.loads(sys.argv[1])
symbols = [str(item).strip().upper() for item in params.get("symbols", []) if str(item).strip()]

def _call_first_success(function, call_specs):
    last_error = None
    for args, kwargs in call_specs:
        try:
            function(*args, **kwargs)
            return
        except TypeError as exc:
            last_error = exc
            continue
    if last_error is not None:
        raise last_error
    function()

with contextlib.redirect_stdout(sys.stderr):
    from xtquant import xtdata

    downloader = getattr(xtdata, "download_history_data2", None) or getattr(xtdata, "download_history_data", None)
    if downloader is None:
        result = {"ok": False, "error": "download_history_not_supported"}
    else:
        call_specs = [
            ((symbols, params["period"], params.get("start_time", ""), params.get("end_time", "")), {}),
            (
                (),
                {
                    "stock_list": symbols,
                    "period": params["period"],
                    "start_time": params.get("start_time", ""),
                    "end_time": params.get("end_time", ""),
                },
            ),
        ]
        if len(symbols) == 1:
            call_specs.extend(
                [
                    ((symbols[0], params["period"], params.get("start_time", ""), params.get("end_time", "")), {}),
                    (
                        (),
                        {
                            "stock_code": symbols[0],
                            "period": params["period"],
                            "start_time": params.get("start_time", ""),
                            "end_time": params.get("end_time", ""),
                        },
                    ),
                ]
            )
        _call_first_success(
            downloader,
            call_specs,
        )
        result = {"ok": True, "symbol_count": len(symbols)}

_stdout.write(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
_stdout.write("\\n")
""".strip()


def _call_first_success(function, call_specs):  # type: ignore[no-untyped-def]
    last_error = None
    for args, kwargs in call_specs:
        try:
            return function(*args, **kwargs)
        except TypeError as exc:
            last_error = exc
            continue
    if last_error is not None:
        raise last_error
    return function()


def _normalize_kline(dataset: Dict[str, object], symbol: str) -> List[Dict[str, object]]:
    if not dataset:
        return []
    first_frame = None
    for field_name, frame in dataset.items():
        if field_name == "time":
            continue
        if hasattr(frame, "columns") and hasattr(frame, "index"):
            first_frame = frame
            break
    if first_frame is None:
        time_frame = dataset.get("time")
        if time_frame is not None and hasattr(time_frame, "columns") and hasattr(time_frame, "index"):
            first_frame = time_frame
    if first_frame is None:
        return []
    columns = list(first_frame.columns)
    index = list(first_frame.index)
    if symbol not in index:
        return []
    row_index = index.index(symbol)
    records = []
    for column_index, column_value in enumerate(columns):
        record = {"time": _normalize_scalar(column_value)}
        for field_name, frame in dataset.items():
            if not hasattr(frame, "iloc"):
                continue
            if field_name == "time":
                continue
            record[field_name] = _normalize_scalar(frame.iloc[row_index, column_index])
        records.append(record)
    return records


def _trim_text(value: str, limit: int = 400) -> str:
    text = value.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _extract_last_json_value(stdout: str):  # type: ignore[no-untyped-def]
    text = stdout.strip()
    decoder = json.JSONDecoder()
    for index in range(len(text) - 1, -1, -1):
        if text[index] not in "[{":
            continue
        try:
            payload, end = decoder.raw_decode(text, index)
        except json.JSONDecodeError:
            continue
        if text[end:].strip():
            continue
        return payload
    raise json.JSONDecodeError("no trailing json payload found", stdout, 0)


def _download_timeout_sec(wait_timeout_ms: int) -> int:
    extra_wait = max(int(wait_timeout_ms), 0) / 1000.0
    return max(_PREFETCH_SUBPROCESS_TIMEOUT_SEC, int(extra_wait) + 5)


def _prefetch_history_via_subprocess(
    symbols: Sequence[str],
    period: str,
    start_time: str = "",
    end_time: str = "",
    *,
    timeout_sec: int,
) -> Dict[str, object]:
    clean_symbols = [str(symbol or "").strip().upper() for symbol in symbols if str(symbol or "").strip()]
    if not clean_symbols:
        return {"ok": False, "error": "empty_symbol_batch", "symbols": []}
    params = {
        "symbols": clean_symbols,
        "period": period,
        "start_time": start_time,
        "end_time": end_time,
    }
    try:
        completed = subprocess.run(
            [sys.executable, "-c", _PREFETCH_SUBPROCESS_SCRIPT, json.dumps(params, ensure_ascii=False)],
            capture_output=True,
            text=True,
            timeout=max(int(timeout_sec), 1),
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "error": "download_history_timeout",
            "symbols": clean_symbols,
            "symbol_count": len(clean_symbols),
            "period": period,
            "start_time": start_time,
            "end_time": end_time,
            "timeout_sec": max(int(timeout_sec), 1),
        }
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or f"exit code {completed.returncode}"
        return {
            "ok": False,
            "error": "download_history_failed",
            "detail": _trim_text(detail),
            "symbols": clean_symbols,
            "symbol_count": len(clean_symbols),
            "period": period,
            "start_time": start_time,
            "end_time": end_time,
            "timeout_sec": max(int(timeout_sec), 1),
        }
    if not completed.stdout.strip():
        detail = completed.stderr.strip()
        return {
            "ok": False,
            "error": "download_history_empty_stdout",
            "detail": _trim_text(detail),
            "symbols": clean_symbols,
            "symbol_count": len(clean_symbols),
            "period": period,
            "start_time": start_time,
            "end_time": end_time,
            "timeout_sec": max(int(timeout_sec), 1),
        }
    try:
        payload = _extract_last_json_value(completed.stdout)
    except json.JSONDecodeError as exc:
        detail = _trim_text(completed.stderr)
        preview = _trim_text(completed.stdout)
        message = f"download_history returned invalid json: {exc}"
        if detail:
            message += f"; stderr={detail}"
        if preview:
            message += f"; stdout_tail={preview}"
        return {
            "ok": False,
            "error": "download_history_invalid_json",
            "detail": message,
            "symbols": clean_symbols,
            "symbol_count": len(clean_symbols),
            "period": period,
            "start_time": start_time,
            "end_time": end_time,
            "timeout_sec": max(int(timeout_sec), 1),
        }
    if not isinstance(payload, dict):
        return {
            "ok": False,
            "error": "download_history_non_dict_payload",
            "symbols": clean_symbols,
            "symbol_count": len(clean_symbols),
            "period": period,
            "start_time": start_time,
            "end_time": end_time,
            "timeout_sec": max(int(timeout_sec), 1),
        }
    payload.setdefault("symbols", clean_symbols)
    payload.setdefault("symbol_count", len(clean_symbols))
    payload.setdefault("period", period)
    payload.setdefault("start_time", start_time)
    payload.setdefault("end_time", end_time)
    payload.setdefault("timeout_sec", max(int(timeout_sec), 1))
    return payload


def _record_summary(records: List[Dict[str, object]]) -> Dict[str, object]:
    summary: Dict[str, object] = {"record_count": len(records)}
    if records:
        summary["first_time"] = records[0].get("time")
        summary["last_time"] = records[-1].get("time")
        summary["sample"] = records[-2:]
    else:
        summary["sample"] = []
    return summary


def _capture_records_snapshot(label: str, reader) -> Dict[str, object]:  # type: ignore[no-untyped-def]
    try:
        records = reader()
    except Exception as exc:
        return {
            "source": label,
            "ok": False,
            "error": str(exc),
            "record_count": 0,
            "sample": [],
        }
    snapshot = {"source": label, "ok": True}
    snapshot.update(_record_summary(records))
    return snapshot


def _diagnose_bars_outcome(
    before_market: Dict[str, object],
    before_market_ex: Dict[str, object],
    before_local: Dict[str, object],
    after_market: Dict[str, object],
    after_market_ex: Dict[str, object],
    after_local: Dict[str, object],
    prefetch: Optional[Dict[str, object]],
) -> str:
    if bool(after_market.get("ok")) and int(after_market.get("record_count", 0)) > 0:
        return "market_data_ready"
    if bool(after_market_ex.get("ok")) and int(after_market_ex.get("record_count", 0)) > 0:
        return "market_data_ex_ready"
    if bool(after_local.get("ok")) and int(after_local.get("record_count", 0)) > 0:
        return "local_cache_ready_but_market_data_empty"
    if bool(before_local.get("ok")) and int(before_local.get("record_count", 0)) > 0:
        return "local_cache_preexisting_but_market_data_empty"
    if bool(before_market_ex.get("ok")) and int(before_market_ex.get("record_count", 0)) > 0:
        return "market_data_ex_preexisting"
    if prefetch and not bool(prefetch.get("ok")):
        return "prefetch_failed"
    if prefetch and bool(prefetch.get("ok")) and not bool(prefetch.get("cache_ready", False)):
        return "prefetch_completed_but_cache_still_unreadable"
    return "local_cache_miss"


def _fetch_ticks_via_subprocess(
    symbol: str,
    count: int,
    start_time: str = "",
    end_time: str = "",
) -> List[Dict[str, object]]:
    params = {
        "symbol": symbol,
        "count": count,
        "start_time": start_time,
        "end_time": end_time,
    }
    completed = subprocess.run(
        [sys.executable, "-c", _TICK_SUBPROCESS_SCRIPT, json.dumps(params, ensure_ascii=False)],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or f"exit code {completed.returncode}"
        raise RuntimeError(f"tick subprocess failed: {detail}")
    if not completed.stdout.strip():
        detail = completed.stderr.strip()
        if detail:
            raise RuntimeError(f"tick subprocess returned empty stdout: {detail}")
        raise RuntimeError("tick subprocess returned empty stdout")
    try:
        payload = _extract_last_json_value(completed.stdout)
    except json.JSONDecodeError as exc:
        detail = _trim_text(completed.stderr)
        preview = _trim_text(completed.stdout)
        message = f"tick subprocess returned invalid json: {exc}"
        if detail:
            message += f"; stderr={detail}"
        if preview:
            message += f"; stdout_tail={preview}"
        raise RuntimeError(message) from exc
    if not isinstance(payload, list):
        raise RuntimeError("tick subprocess returned non-list payload")
    return [_normalize_record_dict(item) for item in payload if isinstance(item, dict)]


class XtQuantMarketDataProvider(MarketDataProvider):
    def __init__(self) -> None:
        try:
            from xtquant import xtdata
        except Exception as exc:
            raise RuntimeError(
                "xtquant import failed. Run qmt-broker on the Windows machine that has QMT and xtquant available."
            ) from exc
        self._xtdata = xtdata
        self._lock = threading.RLock()
        self._handles = {}

    def name(self) -> str:
        return "xtquant"

    def capabilities(self) -> Dict[str, object]:
        return {
            "provider": "xtquant",
            "supports": [
                "quote",
                "bar",
                "tick",
                "whole_quote",
                "l2_quote",
                "l2_order",
                "l2_transaction",
                "prefetch_history",
                "bars_diagnostics",
            ],
            "notes": [
                "whole_quote is preferred for large symbol universes",
                "level2 getters depend on QMT cache availability",
            ],
        }

    def get_sector_list(self) -> List[str]:
        reader = getattr(self._xtdata, "get_sector_list", None)
        if reader is None:
            return []
        sectors = reader() or []
        return [str(item).strip() for item in sectors if str(item).strip()]

    def get_stock_list_in_sector(self, sector_name: str) -> List[str]:
        clean_sector = str(sector_name or "").strip()
        if not clean_sector:
            return []
        reader = getattr(self._xtdata, "get_stock_list_in_sector", None)
        if reader is None:
            return []
        symbols = _call_first_success(
            reader,
            [
                ((clean_sector,), {}),
                ((), {"sector_name": clean_sector}),
            ],
        ) or []
        return [str(item).strip().upper() for item in symbols if str(item).strip()]

    def get_instrument_detail(self, symbol: str) -> Dict[str, object]:
        clean_symbol = str(symbol or "").strip().upper()
        if not clean_symbol:
            return {}
        reader = getattr(self._xtdata, "get_instrument_detail", None)
        if reader is None:
            return {}
        detail = _call_first_success(
            reader,
            [
                ((clean_symbol,), {}),
                ((), {"stock_code": clean_symbol}),
            ],
        )
        return _normalize_record_dict(detail) if isinstance(detail, dict) else {}

    def default_security_master_sectors(self) -> List[str]:
        sectors = set(self.get_sector_list())
        preferred = [
            "沪深京A股",
            "沪深A股",
            "沪A",
            "深A",
            "京A",
            "科创板",
            "创业板",
        ]
        selected = [item for item in preferred if item in sectors]
        if selected:
            return selected
        return sorted(
            sector
            for sector in sectors
            if ("A股" in sector or sector in {"沪A", "深A", "京A", "科创板", "创业板"})
        )

    def get_quote(self, symbol: str) -> Dict[str, object]:
        data = self._xtdata.get_full_tick([symbol]) or {}
        return data.get(symbol, {})

    def get_bars(
        self,
        symbol: str,
        period: str,
        limit: int,
        start_time: str = "",
        end_time: str = "",
    ) -> List[Dict[str, object]]:
        return self._read_market_records(symbol, period, normalize_limit(limit, 240), start_time, end_time)

    def get_ticks(
        self,
        symbol: str,
        limit: int,
        start_time: str = "",
        end_time: str = "",
        run_prefetch: bool = False,
        wait_timeout_ms: int = 0,
        poll_interval_ms: int = 250,
    ) -> List[Dict[str, object]]:
        # Tick queries are isolated in a child process because xtdata tick reads can
        # occasionally destabilize the host interpreter on some Windows/QMT builds.
        normalized_limit = normalize_limit(limit, 500)
        records = _fetch_ticks_via_subprocess(
            symbol,
            normalized_limit,
            start_time=start_time,
            end_time=end_time,
        )
        if records or not run_prefetch:
            return records
        return self._prefetch_ticks(
            symbol,
            normalized_limit,
            start_time=start_time,
            end_time=end_time,
            wait_timeout_ms=wait_timeout_ms,
            poll_interval_ms=poll_interval_ms,
        )

    def backfill_ticks(
        self,
        symbol: str,
        start_time: str = "",
        end_time: str = "",
    ) -> List[Dict[str, object]]:
        records = _fetch_ticks_via_subprocess(
            symbol,
            -1,
            start_time=start_time,
            end_time=end_time,
        )
        _emit_provider_log(
            "xtquant_backfill_ticks_first_fetch",
            symbol=symbol,
            start_time=start_time,
            end_time=end_time,
            record_count=len(records),
        )
        if records:
            return records
        prefetch_result = self.prefetch_history(
            symbol,
            "tick",
            start_time,
            end_time,
            wait_timeout_ms=_BACKFILL_WAIT_TIMEOUT_MS,
            poll_interval_ms=_BACKFILL_POLL_INTERVAL_MS,
        )
        local_after_wait = (
            prefetch_result.get("local_after_wait")
            if isinstance(prefetch_result.get("local_after_wait"), dict)
            else {}
        )
        _emit_provider_log(
            "xtquant_backfill_ticks_prefetch",
            symbol=symbol,
            start_time=start_time,
            end_time=end_time,
            ok=bool(prefetch_result.get("ok")),
            cache_ready=bool(prefetch_result.get("cache_ready", False)),
            wait_timeout_ms=_BACKFILL_WAIT_TIMEOUT_MS,
            poll_interval_ms=_BACKFILL_POLL_INTERVAL_MS,
            local_record_count=int(local_after_wait.get("record_count", 0) or 0),
        )
        market_ex_probe = _capture_records_snapshot(
            "get_market_data_ex",
            lambda: self._read_market_records_ex(symbol, "tick", 32, start_time, end_time),
        )
        local_probe = _capture_records_snapshot(
            "get_local_data",
            lambda: self._read_local_records(symbol, "tick", 32, start_time, end_time),
        )
        _emit_provider_log(
            "xtquant_backfill_ticks_cache_probe",
            symbol=symbol,
            start_time=start_time,
            end_time=end_time,
            market_ex=market_ex_probe,
            local=local_probe,
        )
        records = _fetch_ticks_via_subprocess(
            symbol,
            -1,
            start_time=start_time,
            end_time=end_time,
        )
        _emit_provider_log(
            "xtquant_backfill_ticks_second_fetch",
            symbol=symbol,
            start_time=start_time,
            end_time=end_time,
            record_count=len(records),
        )
        if records:
            return records
        market_ex_records = self._read_market_records_ex(symbol, "tick", -1, start_time, end_time)
        _emit_provider_log(
            "xtquant_backfill_ticks_market_ex_fallback",
            symbol=symbol,
            start_time=start_time,
            end_time=end_time,
            record_count=len(market_ex_records),
        )
        if market_ex_records:
            return market_ex_records
        local_records = self._read_local_records(symbol, "tick", -1, start_time, end_time)
        _emit_provider_log(
            "xtquant_backfill_ticks_local_fallback",
            symbol=symbol,
            start_time=start_time,
            end_time=end_time,
            record_count=len(local_records),
        )
        if local_records:
            return local_records
        return records

    def get_l2_quote(
        self,
        symbol: str,
        limit: int,
        start_time: str = "",
        end_time: str = "",
    ) -> List[Dict[str, object]]:
        data = self._xtdata.get_l2_quote(
            stock_code=symbol,
            count=normalize_limit(limit, 200),
            start_time=start_time,
            end_time=end_time,
        )
        return _normalize_structured_array(data)

    def get_l2_order(
        self,
        symbol: str,
        limit: int,
        start_time: str = "",
        end_time: str = "",
    ) -> List[Dict[str, object]]:
        data = self._xtdata.get_l2_order(
            stock_code=symbol,
            count=normalize_limit(limit, 200),
            start_time=start_time,
            end_time=end_time,
        )
        return _normalize_structured_array(data)

    def get_l2_transaction(
        self,
        symbol: str,
        limit: int,
        start_time: str = "",
        end_time: str = "",
    ) -> List[Dict[str, object]]:
        data = self._xtdata.get_l2_transaction(
            stock_code=symbol,
            count=normalize_limit(limit, 200),
            start_time=start_time,
            end_time=end_time,
        )
        return _normalize_structured_array(data)

    def prefetch_history(
        self,
        symbol: str,
        period: str,
        start_time: str = "",
        end_time: str = "",
        wait_timeout_ms: int = 0,
        poll_interval_ms: int = 250,
        ) -> Dict[str, object]:
        result = _prefetch_history_via_subprocess(
            [symbol],
            period,
            start_time,
            end_time,
            timeout_sec=_download_timeout_sec(wait_timeout_ms),
        )
        result.update(
            {
                "provider": "xtquant",
                "symbol": symbol,
                "period": period,
                "start_time": start_time,
                "end_time": end_time,
                "wait_timeout_ms": wait_timeout_ms,
                "poll_interval_ms": poll_interval_ms,
            }
        )
        if not bool(result.get("ok")):
            return result
        if wait_timeout_ms > 0:
            polls, local_after_wait = self._poll_local_cache(
                symbol,
                period,
                start_time,
                end_time,
                wait_timeout_ms,
                poll_interval_ms,
            )
            result["cache_ready"] = bool(local_after_wait.get("record_count"))
            result["polls"] = polls
            result["local_after_wait"] = local_after_wait
        return result

    def prefetch_history_batch(
        self,
        symbols: Sequence[str],
        period: str,
        start_time: str = "",
        end_time: str = "",
        wait_timeout_ms: int = 0,
        poll_interval_ms: int = 250,
    ) -> Dict[str, object]:
        clean_symbols = tuple(str(symbol or "").strip().upper() for symbol in symbols if str(symbol or "").strip())
        if not clean_symbols:
            return {
                "ok": False,
                "error": "empty_symbol_batch",
                "symbols": [],
                "period": period,
                "start_time": start_time,
                "end_time": end_time,
                "wait_timeout_ms": wait_timeout_ms,
                "poll_interval_ms": poll_interval_ms,
            }
        downloader = getattr(self._xtdata, "download_history_data2", None) or getattr(
            self._xtdata, "download_history_data", None
        )
        if downloader is None:
            return {
                "ok": False,
                "error": "download_history_not_supported",
                "symbols": list(clean_symbols),
                "symbol_count": len(clean_symbols),
                "period": period,
                "start_time": start_time,
                "end_time": end_time,
                "wait_timeout_ms": wait_timeout_ms,
                "poll_interval_ms": poll_interval_ms,
            }
        _call_first_success(
            downloader,
            [
                ((list(clean_symbols), period, start_time, end_time), {}),
                (
                    (),
                    {
                        "stock_list": list(clean_symbols),
                        "period": period,
                        "start_time": start_time,
                        "end_time": end_time,
                    },
                ),
            ],
        )
        return {
            "ok": True,
            "provider": "xtquant",
            "symbols": list(clean_symbols),
            "symbol_count": len(clean_symbols),
            "ok_count": len(clean_symbols),
            "cache_ready_count": 0,
            "period": period,
            "start_time": start_time,
            "end_time": end_time,
            "wait_timeout_ms": wait_timeout_ms,
            "poll_interval_ms": poll_interval_ms,
        }

    def diagnose_bars(
        self,
        symbol: str,
        period: str,
        limit: int,
        start_time: str = "",
        end_time: str = "",
        run_prefetch: bool = False,
        wait_timeout_ms: int = 0,
        poll_interval_ms: int = 250,
    ) -> Dict[str, object]:
        normalized_limit = normalize_limit(limit, 240)
        before = self._capture_bars_snapshot(symbol, period, normalized_limit, start_time, end_time)
        prefetch = None
        prefetch_summary = None
        polls: List[Dict[str, object]] = []
        if run_prefetch:
            prefetch = self.prefetch_history(
                symbol,
                period,
                start_time,
                end_time,
                wait_timeout_ms=wait_timeout_ms,
                poll_interval_ms=poll_interval_ms,
            )
            polls = list(prefetch.get("polls", [])) if isinstance(prefetch.get("polls"), list) else []
            prefetch_summary = dict(prefetch)
            prefetch_summary.pop("polls", None)
        elif wait_timeout_ms > 0:
            polls, _ = self._poll_local_cache(
                symbol,
                period,
                start_time,
                end_time,
                wait_timeout_ms,
                poll_interval_ms,
            )
        after = self._capture_bars_snapshot(symbol, period, normalized_limit, start_time, end_time)
        return {
            "ok": True,
            "provider": "xtquant",
            "symbol": symbol,
            "period": period,
            "limit": normalized_limit,
            "start_time": start_time,
            "end_time": end_time,
            "run_prefetch": run_prefetch,
            "wait_timeout_ms": wait_timeout_ms,
            "poll_interval_ms": poll_interval_ms,
            "xtdata_data_dir": getattr(self._xtdata, "data_dir", ""),
            "diagnosis": _diagnose_bars_outcome(
                before.get("market", {"ok": False, "record_count": 0}),
                before.get("market_ex", {"ok": False, "record_count": 0}),
                before.get("local", {"ok": False, "record_count": 0}),
                after.get("market", {"ok": False, "record_count": 0}),
                after.get("market_ex", {"ok": False, "record_count": 0}),
                after.get("local", {"ok": False, "record_count": 0}),
                prefetch,
            ),
            "before": before,
            "prefetch": prefetch_summary,
            "polls": polls,
            "after": after,
        }

    def subscribe(self, topic: SubscriptionTopic, callback: ProviderCallback) -> str:
        if topic.kind == "whole_quote":
            code_list = [topic.market] if topic.market else ["SH", "SZ"]
            seq = self._xtdata.subscribe_whole_quote(
                code_list,
                callback=lambda datas: self._dispatch_whole_quote(topic, datas, callback),
            )
        elif topic.kind in {"quote", "tick", "bar", "l2_quote", "l2_order", "l2_transaction"}:
            period_map = {
                "tick": "tick",
                "bar": topic.period or "1m",
                "quote": topic.period or "1m",
                "l2_quote": "l2quote",
                "l2_order": "l2order",
                "l2_transaction": "l2transaction",
            }
            period = period_map[topic.kind]
            seq = self._xtdata.subscribe_quote(
                topic.symbol,
                period=period,
                count=0,
                callback=lambda datas: self._dispatch_quote(topic, datas, callback),
            )
        else:
            raise ValueError("xtquant provider does not support direct subscribe for topic %s" % topic.kind)
        handle = str(seq)
        with self._lock:
            self._handles[handle] = int(seq)
        return handle

    def unsubscribe(self, handle: str) -> None:
        with self._lock:
            seq = self._handles.pop(handle, None)
        if seq is not None:
            self._xtdata.unsubscribe_quote(seq)

    def close(self) -> None:
        with self._lock:
            handles = list(self._handles.values())
            self._handles.clear()
        for seq in handles:
            try:
                self._xtdata.unsubscribe_quote(seq)
            except Exception:
                continue

    def _prefetch_ticks(
        self,
        symbol: str,
        limit: int,
        start_time: str = "",
        end_time: str = "",
        wait_timeout_ms: int = 0,
        poll_interval_ms: int = 250,
    ) -> List[Dict[str, object]]:
        subscriber = getattr(self._xtdata, "subscribe_quote", None)
        if subscriber is None:
            return []
        seq = _call_first_success(
            subscriber,
            [
                (
                    (symbol,),
                    {
                        "period": "tick",
                        "start_time": start_time,
                        "end_time": end_time,
                        "count": 0,
                        "callback": None,
                    },
                ),
                (
                    (),
                    {
                        "stock_code": symbol,
                        "period": "tick",
                        "start_time": start_time,
                        "end_time": end_time,
                        "count": 0,
                        "callback": None,
                    },
                ),
            ],
        )
        deadline = time.time() + max(wait_timeout_ms, 0) / 1000.0
        interval_sec = max(poll_interval_ms, 50) / 1000.0
        try:
            while True:
                records = _fetch_ticks_via_subprocess(
                    symbol,
                    limit,
                    start_time=start_time,
                    end_time=end_time,
                )
                if records:
                    return records
                if time.time() >= deadline:
                    return records
                time.sleep(interval_sec)
        finally:
            try:
                self._xtdata.unsubscribe_quote(seq)
            except Exception:
                pass

    def _dispatch_quote(
        self,
        topic: SubscriptionTopic,
        datas: Dict[str, object],
        callback: ProviderCallback,
    ) -> None:
        for symbol, payloads in datas.items():
            if isinstance(payloads, list):
                for payload in payloads:
                    if isinstance(payload, dict):
                        callback(topic, symbol, _normalize_record_dict(payload))
                    else:
                        callback(topic, symbol, {"value": _normalize_scalar(payload)})
            elif isinstance(payloads, dict):
                callback(topic, symbol, _normalize_record_dict(payloads))
            else:
                callback(topic, symbol, {"value": _normalize_scalar(payloads)})

    def _dispatch_whole_quote(
        self,
        topic: SubscriptionTopic,
        datas: Dict[str, object],
        callback: ProviderCallback,
    ) -> None:
        for symbol, payload in datas.items():
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except Exception:
                    payload = {"raw": payload}
            if isinstance(payload, dict):
                callback(topic, symbol, _normalize_record_dict(payload))
            else:
                callback(topic, symbol, {"value": _normalize_scalar(payload)})

    def _read_market_records(
        self,
        symbol: str,
        period: str,
        limit: int,
        start_time: str = "",
        end_time: str = "",
    ) -> List[Dict[str, object]]:
        data = self._xtdata.get_market_data(
            stock_list=[symbol],
            period=period,
            count=limit,
            start_time=start_time,
            end_time=end_time,
            fill_data=False,
        )
        if period == "tick":
            rows = data.get(symbol) if isinstance(data, dict) else None
            return _normalize_structured_array(rows)
        return _normalize_kline(data, symbol)

    def _read_market_records_ex(
        self,
        symbol: str,
        period: str,
        limit: int,
        start_time: str = "",
        end_time: str = "",
    ) -> List[Dict[str, object]]:
        market_reader = getattr(self._xtdata, "get_market_data_ex", None)
        if market_reader is None:
            raise RuntimeError("xtdata.get_market_data_ex is unavailable")
        data = _call_first_success(
            market_reader,
            [
                (
                    (),
                    {
                        "field_list": [],
                        "stock_list": [symbol],
                        "period": period,
                        "start_time": start_time,
                        "end_time": end_time,
                        "count": limit,
                        "dividend_type": "none",
                        "fill_data": False,
                        "subscribe": False,
                    },
                ),
                (
                    (),
                    {
                        "field_list": [],
                        "stock_list": [symbol],
                        "period": period,
                        "start_time": start_time,
                        "end_time": end_time,
                        "count": limit,
                        "dividend_type": "none",
                        "fill_data": False,
                    },
                ),
                (
                    (),
                    {
                        "field_list": [],
                        "stock_code": [symbol],
                        "period": period,
                        "start_time": start_time,
                        "end_time": end_time,
                        "count": limit,
                        "dividend_type": "none",
                        "fill_data": False,
                        "subscribe": False,
                    },
                ),
                (
                    (),
                    {
                        "field_list": [],
                        "stock_code": [symbol],
                        "period": period,
                        "start_time": start_time,
                        "end_time": end_time,
                        "count": limit,
                        "dividend_type": "none",
                        "fill_data": False,
                    },
                ),
            ],
        )
        rows = data.get(symbol) if isinstance(data, dict) else None
        return _normalize_tabular_records(rows)

    def _read_local_records(
        self,
        symbol: str,
        period: str,
        limit: int,
        start_time: str = "",
        end_time: str = "",
    ) -> List[Dict[str, object]]:
        local_reader = getattr(self._xtdata, "get_local_data", None)
        if local_reader is None:
            raise RuntimeError("xtdata.get_local_data is unavailable")
        data = _call_first_success(
            local_reader,
            [
                (
                    (),
                    {
                        "field_list": [],
                        "stock_list": [symbol],
                        "period": period,
                        "start_time": start_time,
                        "end_time": end_time,
                        "count": limit,
                        "fill_data": False,
                    },
                ),
                (
                    (),
                    {
                        "field_list": [],
                        "stock_code": [symbol],
                        "period": period,
                        "start_time": start_time,
                        "end_time": end_time,
                        "count": limit,
                        "fill_data": False,
                    },
                ),
            ],
        )
        if period == "tick":
            rows = data.get(symbol) if isinstance(data, dict) else None
            return _normalize_structured_array(rows)
        return _normalize_kline(data, symbol)

    def _capture_bars_snapshot(
        self,
        symbol: str,
        period: str,
        limit: int,
        start_time: str,
        end_time: str,
    ) -> Dict[str, object]:
        return {
            "market": _capture_records_snapshot(
                "get_market_data",
                lambda: self._read_market_records(symbol, period, limit, start_time, end_time),
            ),
            "market_ex": _capture_records_snapshot(
                "get_market_data_ex",
                lambda: self._read_market_records_ex(symbol, period, limit, start_time, end_time),
            ),
            "local": _capture_records_snapshot(
                "get_local_data",
                lambda: self._read_local_records(symbol, period, limit, start_time, end_time),
            ),
        }

    def _poll_local_cache(
        self,
        symbol: str,
        period: str,
        start_time: str,
        end_time: str,
        wait_timeout_ms: int,
        poll_interval_ms: int,
    ) -> Tuple[List[Dict[str, object]], Dict[str, object]]:
        polls: List[Dict[str, object]] = []
        deadline = time.time() + max(wait_timeout_ms, 0) / 1000.0
        interval_sec = max(poll_interval_ms, 50) / 1000.0
        attempt = 0
        last_snapshot: Dict[str, object] = {
            "source": "get_local_data",
            "ok": False,
            "error": "poll_not_started",
            "record_count": 0,
            "sample": [],
        }
        while True:
            attempt += 1
            last_snapshot = _capture_records_snapshot(
                "get_local_data",
                lambda: self._read_local_records(symbol, period, 32, start_time, end_time),
            )
            polls.append(
                {
                    "attempt": attempt,
                    "elapsed_ms": int(max(wait_timeout_ms, 0) - max(deadline - time.time(), 0) * 1000),
                    "local": last_snapshot,
                }
            )
            if int(last_snapshot.get("record_count", 0)) > 0:
                break
            if time.time() >= deadline:
                break
            time.sleep(interval_sec)
        return polls, last_snapshot
