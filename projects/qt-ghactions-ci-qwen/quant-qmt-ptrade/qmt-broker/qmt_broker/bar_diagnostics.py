import json
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

from qmt_broker.bar_backfill import _chunked_symbols, _load_symbols, _resolve_window, _trade_date_from_window
from qmt_broker.config import BrokerConfig
from qmt_broker.providers.base import MarketDataProvider


def _emit_bar_diagnostics_log(event: str, **payload: object) -> None:
    message = {"ts_ms": int(time.time() * 1000), "event": event, "component": "bar_diagnostics", **payload}
    print(json.dumps(message, ensure_ascii=False), flush=True)


@dataclass
class BarDiagnosticsOptions:
    period: str = "1m"
    trade_date: str = ""
    start_time: str = ""
    end_time: str = ""
    symbols: Sequence[str] = ()
    prefetch: bool = True
    prefetch_batch_size: int = 16
    limit: int = 10
    wait_timeout_ms: int = 5000
    poll_interval_ms: int = 250
    output_path: str = ""


def run_bar_diagnostics(provider: MarketDataProvider, config: BrokerConfig, options: BarDiagnosticsOptions) -> Dict[str, object]:
    symbols = list(_load_symbols(config, options.symbols))
    if not symbols:
        raise RuntimeError("no symbols available for bar diagnostics")
    start_time, end_time = _resolve_window(options.trade_date, options.start_time, options.end_time)
    _emit_bar_diagnostics_log(
        "bar_diagnostics_started",
        provider=provider.name(),
        period=options.period,
        trade_date=_trade_date_from_window(start_time),
        symbol_count=len(symbols),
        start_time=start_time,
        end_time=end_time,
        prefetch=options.prefetch,
    )
    if options.prefetch:
        _prefetch_diagnostics_batches(
            provider,
            symbols,
            options.period,
            start_time,
            end_time,
            batch_size=max(int(options.prefetch_batch_size), 1),
            wait_timeout_ms=options.wait_timeout_ms,
            poll_interval_ms=options.poll_interval_ms,
        )
    symbol_results: List[Dict[str, object]] = []
    for symbol_index, symbol in enumerate(symbols, start=1):
        result = provider.diagnose_bars(
            symbol,
            options.period,
            max(int(options.limit), 1),
            start_time,
            end_time,
            run_prefetch=False,
            wait_timeout_ms=options.wait_timeout_ms,
            poll_interval_ms=options.poll_interval_ms,
        )
        classification = _classify_symbol_result(result)
        normalized = {
            "symbol": symbol,
            "symbol_index": symbol_index,
            "total_symbols": len(symbols),
            "diagnosis": result.get("diagnosis", ""),
            "classification": classification,
            "before": _compact_snapshots(result.get("before")),
            "after": _compact_snapshots(result.get("after")),
            "prefetch": _compact_prefetch(result.get("prefetch")),
        }
        symbol_results.append(normalized)
        _emit_bar_diagnostics_log(
            "bar_diagnostics_symbol",
            provider=provider.name(),
            symbol=symbol,
            symbol_index=symbol_index,
            total_symbols=len(symbols),
            diagnosis=normalized["diagnosis"],
            classification=classification,
            after=normalized["after"],
        )
    summary = _build_summary(
        provider.name(),
        options.period,
        start_time,
        end_time,
        symbol_results,
    )
    output_path = _resolve_output_path(options.output_path, options.period, _trade_date_from_window(start_time))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    _emit_bar_diagnostics_log(
        "bar_diagnostics_completed",
        provider=provider.name(),
        period=options.period,
        trade_date=_trade_date_from_window(start_time),
        symbol_count=len(symbols),
        readable_count=summary["groups"]["readable"]["count"],
        unreadable_count=summary["groups"]["unreadable"]["count"],
        output_path=str(output_path),
    )
    return summary


def _prefetch_diagnostics_batches(
    provider: MarketDataProvider,
    symbols: Sequence[str],
    period: str,
    start_time: str,
    end_time: str,
    *,
    batch_size: int,
    wait_timeout_ms: int,
    poll_interval_ms: int,
) -> None:
    for batch_index, batch_symbols in enumerate(_chunked_symbols(symbols, batch_size), start=1):
        _emit_bar_diagnostics_log(
            "bar_diagnostics_prefetch_batch_started",
            provider=provider.name(),
            batch_index=batch_index,
            batch_size=len(batch_symbols),
            period=period,
            start_time=start_time,
            end_time=end_time,
        )
        try:
            result = provider.prefetch_history_batch(
                batch_symbols,
                period,
                start_time,
                end_time,
                wait_timeout_ms=wait_timeout_ms,
                poll_interval_ms=poll_interval_ms,
            )
        except Exception as exc:
            _emit_bar_diagnostics_log(
                "bar_diagnostics_prefetch_batch_failed",
                provider=provider.name(),
                batch_index=batch_index,
                batch_size=len(batch_symbols),
                period=period,
                detail=str(exc),
            )
            continue
        _emit_bar_diagnostics_log(
            "bar_diagnostics_prefetch_batch",
            provider=provider.name(),
            batch_index=batch_index,
            batch_size=len(batch_symbols),
            period=period,
            ok=bool(result.get("ok")),
            ok_count=int(result.get("ok_count", 0) or 0),
            cache_ready_count=int(result.get("cache_ready_count", 0) or 0),
        )


def _compact_snapshots(snapshot_group: object) -> Dict[str, Dict[str, object]]:
    if not isinstance(snapshot_group, dict):
        return {}
    compact = {}
    for label in ("market", "market_ex", "local"):
        snapshot = snapshot_group.get(label)
        if not isinstance(snapshot, dict):
            continue
        compact[label] = {
            "ok": bool(snapshot.get("ok")),
            "record_count": int(snapshot.get("record_count", 0) or 0),
            "sample": snapshot.get("sample", []),
            **({"error": snapshot.get("error")} if snapshot.get("error") else {}),
        }
    return compact


def _compact_prefetch(prefetch: object) -> Dict[str, object]:
    if not isinstance(prefetch, dict):
        return {}
    return {
        "ok": bool(prefetch.get("ok")),
        "cache_ready": bool(prefetch.get("cache_ready", False)),
        "wait_timeout_ms": int(prefetch.get("wait_timeout_ms", 0) or 0),
        "poll_interval_ms": int(prefetch.get("poll_interval_ms", 0) or 0),
    }


def _classify_symbol_result(result: Dict[str, object]) -> str:
    after = result.get("after")
    if not isinstance(after, dict):
        return "unreadable"
    market = _snapshot_count(after.get("market"))
    market_ex = _snapshot_count(after.get("market_ex"))
    local = _snapshot_count(after.get("local"))
    if market > 0:
        return "readable_market"
    if market_ex > 0:
        return "readable_market_ex"
    if local > 0:
        return "readable_local"
    return "unreadable"


def _snapshot_count(snapshot: object) -> int:
    if not isinstance(snapshot, dict):
        return 0
    return int(snapshot.get("record_count", 0) or 0)


def _build_summary(
    provider_name: str,
    period: str,
    start_time: str,
    end_time: str,
    symbol_results: Sequence[Dict[str, object]],
) -> Dict[str, object]:
    readable = [item for item in symbol_results if str(item.get("classification", "")).startswith("readable_")]
    unreadable = [item for item in symbol_results if item not in readable]
    groups = {
        "readable": {
            "count": len(readable),
            "symbols": [item["symbol"] for item in readable],
        },
        "unreadable": {
            "count": len(unreadable),
            "symbols": [item["symbol"] for item in unreadable],
        },
        "readable_market": _group_symbols(symbol_results, "readable_market"),
        "readable_market_ex": _group_symbols(symbol_results, "readable_market_ex"),
        "readable_local": _group_symbols(symbol_results, "readable_local"),
    }
    return {
        "ok": True,
        "provider": provider_name,
        "period": period,
        "trade_date": _trade_date_from_window(start_time),
        "start_time": start_time,
        "end_time": end_time,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "groups": groups,
        "symbols": list(symbol_results),
    }


def _group_symbols(symbol_results: Sequence[Dict[str, object]], classification: str) -> Dict[str, object]:
    filtered = [item for item in symbol_results if item.get("classification") == classification]
    return {
        "count": len(filtered),
        "symbols": [item["symbol"] for item in filtered],
    }


def _resolve_output_path(output_path: str, period: str, trade_date: str) -> Path:
    clean = str(output_path or "").strip()
    if clean:
        return Path(clean)
    safe_trade_date = trade_date or "unknown"
    return Path("data") / "runtime" / "bar_diagnostics" / f"{safe_trade_date}_{period}.json"
