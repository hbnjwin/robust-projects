import asyncio
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from html import unescape
import json
from pathlib import Path
import re
from threading import Lock
from typing import Any, Callable
from urllib.parse import urljoin
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4
from zoneinfo import ZoneInfo

from .config import settings
from .models import (
    AdviceAction,
    AdviceRequest,
    AdviceResponse,
    Bar,
    BacktestEquityPoint,
    BacktestBlockedEntry,
    BacktestExecutionConfig,
    BacktestGateEventRef,
    BacktestRunRequest,
    BacktestRunResponse,
    BacktestSummary,
    BacktestSymbolContribution,
    BacktestTrade,
    BrokerAccountSummary,
    BrokerCancelRequest,
    BrokerCancelResponse,
    BrokerKillSwitchRequest,
    BrokerKillSwitchState,
    BrokerOrderRecord,
    BrokerOrderRequest,
    BrokerOrderResponse,
    BrokerOrdersResponse,
    BrokerPosition,
    BrokerPositionsResponse,
    BrokerStatusResponse,
    BarsResponse,
    Catalyst,
    Confidence,
    ImpactDirection,
    Indicators,
    IntelEventsResponse,
    IntelIngestRequest,
    IntelIngestResponse,
    IntelReport,
    IntelSectorContext,
    IntelSchedulerRunResult,
    IntelSchedulerStatus,
    IntelSchedulerTarget,
    IntelSchedulerTargetRequest,
    IntelStoredEvent,
    IntelSummary,
    LimitStatus,
    Magnitude,
    NewsItem,
    PaperAccountSummary,
    PaperOrderRecord,
    PaperOrderResponse,
    PaperOrdersResponse,
    PaperPerformancePoint,
    PaperPerformanceResponse,
    PaperPerformanceSummary,
    PaperPosition,
    PaperPositionsResponse,
    MarketProviderStatus,
    MarketDecisionStatus,
    PortfolioPosition,
    ProviderCandidateScore,
    ProviderDecision,
    ProviderSourceAudit,
    ProviderCheck,
    PortfolioRiskConfig,
    Quote,
    RiskCheckRequest,
    RiskCheckResponse,
    RiskRuleResult,
    SourceTier,
    StrategyMeta,
    TradePlan,
    TradingStatus,
    WatchlistAlert,
    WatchlistAlertsResponse,
    WatchlistItem,
    WatchlistItemRequest,
    WatchlistResponse,
    WatchlistScanResult,
    WatchlistStatus,
)

_LOCAL_TZ = ZoneInfo(settings.timezone)
_INTEL_GATE_FORMULA_VERSION = "intel_gate_v2"
_EXECUTION_RULE_VERSION = "execution_v3"
_INTEL_LIVE_VERSION = "intel_live_v1"
_DEFAULT_EVENT_KEYWORD_WEIGHT = 100.0
_DEFAULT_EVENT_SOURCE_WEIGHT = 10.0
_DEFAULT_EVENT_RECENCY_WINDOW_HOURS = 72.0
_EVENT_POSITIVE_TERMS = ["合作", "快报", "增长", "创新", "升级", "意见", "实施", "推进", "批复", "签署"]
_EVENT_NEGATIVE_TERMS = ["风险", "问询", "减持", "诉讼", "处罚", "质押", "延期", "下滑", "亏损", "监管"]


class ProviderError(RuntimeError):
    pass


@dataclass
class CacheEntry:
    expires_at: datetime
    value: Any = None
    error: ProviderError | None = None


@dataclass
class ProviderAuditState:
    consecutive_failures: int = 0
    last_success_at: datetime | None = None
    last_error_at: datetime | None = None
    last_error_code: str | None = None


def _now() -> datetime:
    return datetime.now(UTC)


def _parse_trade_time(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if value is None:
        return _now()
    text = str(value).strip()
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y%m%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%d",
        "%Y%m%d",
    ):
        try:
            parsed = datetime.strptime(text, fmt)
            return parsed.replace(tzinfo=_LOCAL_TZ)
        except ValueError:
            continue
    return _now()


def _event_keyword_score(event: NewsItem) -> int:
    text = f"{event.title} {event.summary}"
    score = 0
    if any(term in text for term in _EVENT_POSITIVE_TERMS):
        score += 1
    if any(term in text for term in _EVENT_NEGATIVE_TERMS):
        score -= 1
    return score


def _float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _provider_error_code(detail: str) -> str:
    text = detail.casefold()
    if "package is not installed" in text:
        return "dependency_missing"
    if (
        "proxyerror" in text
        or "empty reply from server" in text
        or "remotedisconnected" in text
        or "remote end closed connection without response" in text
        or "connection reset by peer" in text
        or "connection refused" in text
        or "no route to host" in text
        or "network is unreachable" in text
        or "name or service not known" in text
        or "nodename nor servname provided" in text
    ):
        return "network_path_unavailable"
    if "provider unavailable" in text or "token missing" in text or "unavailable" in text:
        return "provider_unavailable"
    if "permission denied" in text or "没有接口访问权限" in detail:
        return "permission_denied"
    if "rate limited" in text or "每小时最多访问" in detail or "每分钟最多访问" in detail:
        return "rate_limited"
    if "timeout" in text:
        return "upstream_timeout"
    if "unsupported intraday interval" in text:
        return "unsupported_interval"
    if "could not find symbol" in text:
        return "symbol_not_found"
    if "no " in text and "rows returned" in text:
        return "empty_result"
    if "failed" in text:
        return "upstream_failed"
    return "unknown_error"


def _ashare_symbol_code(symbol: str) -> str:
    return symbol.split(".", 1)[0].strip().upper()


def _expanded_path(path_value: str) -> Path:
    return Path(path_value).expanduser()


def _row_get(row: Any, *names: str) -> Any:
    for name in names:
        if hasattr(row, "get"):
            value = row.get(name)
            if value is not None:
                return value
        try:
            value = row[name]
        except Exception:
            continue
        if value is not None:
            return value
    return None


def _resolve_execution_values(
    execution: BacktestExecutionConfig | None,
    symbol_count: int,
    legacy_constraints: dict[str, float | bool | int | str] | None = None,
) -> tuple[float, float, float, float, int, int, int, float, float, float, str | None]:
    default_max_open_positions = min(5, symbol_count)
    if execution is not None:
        return (
            float(execution.max_position_pct),
            float(execution.stop_loss_pct),
            float(execution.take_profit_pct),
            float(execution.commission_bps),
            int(execution.lot_size),
            int(execution.min_hold_days),
            int(execution.max_open_positions) if execution.max_open_positions is not None else default_max_open_positions,
            float(execution.fee_drag_warn_ratio),
            float(execution.reward_risk_tight_ratio),
            float(execution.reward_risk_thin_ratio),
            "execution",
        )
    constraints = legacy_constraints or {}
    execution_keys = {
        "max_position_pct",
        "stop_loss_pct",
        "take_profit_pct",
        "commission_bps",
        "lot_size",
        "min_hold_days",
        "max_open_positions",
        "fee_drag_warn_ratio",
        "reward_risk_tight_ratio",
        "reward_risk_thin_ratio",
    }
    config_source = "constraints" if any(key in constraints for key in execution_keys) else None
    return (
        float(constraints.get("max_position_pct", 0.2)),
        float(constraints.get("stop_loss_pct", 0.06)),
        float(constraints.get("take_profit_pct", 0.12)),
        float(constraints.get("commission_bps", 3.0)),
        int(constraints.get("lot_size", 100)),
        int(constraints.get("min_hold_days", 5)),
        int(constraints.get("max_open_positions", default_max_open_positions)),
        float(constraints.get("fee_drag_warn_ratio", 0.25)),
        float(constraints.get("reward_risk_tight_ratio", 1.2)),
        float(constraints.get("reward_risk_thin_ratio", 0.9)),
        config_source,
    )


def _execution_params_map(
    max_position_pct: float,
    stop_loss_pct: float,
    take_profit_pct: float,
    commission_bps: float,
    lot_size: int,
    min_hold_days: int,
    max_open_positions: int,
    fee_drag_warn_ratio: float,
    reward_risk_tight_ratio: float,
    reward_risk_thin_ratio: float,
) -> dict[str, float | int]:
    return {
        "max_position_pct": round(max_position_pct, 4),
        "stop_loss_pct": round(stop_loss_pct, 4),
        "take_profit_pct": round(take_profit_pct, 4),
        "commission_bps": round(commission_bps, 4),
        "lot_size": lot_size,
        "min_hold_days": min_hold_days,
        "max_open_positions": max_open_positions,
        "fee_drag_warn_ratio": round(fee_drag_warn_ratio, 4),
        "reward_risk_tight_ratio": round(reward_risk_tight_ratio, 4),
        "reward_risk_thin_ratio": round(reward_risk_thin_ratio, 4),
    }


def _resolve_portfolio_risk_values(
    portfolio_risk: PortfolioRiskConfig | None,
    legacy_constraints: dict[str, float | bool | int | str] | None = None,
) -> tuple[float, float, int, str | None]:
    if portfolio_risk is not None:
        return (
            float(portfolio_risk.max_sector_pct),
            float(portfolio_risk.max_total_exposure_pct),
            int(portfolio_risk.max_daily_orders),
            "portfolio_risk",
        )
    constraints = legacy_constraints or {}
    portfolio_keys = {"max_sector_pct", "max_total_exposure_pct", "max_daily_orders"}
    config_source = "constraints" if any(key in constraints for key in portfolio_keys) else None
    return (
        float(constraints.get("max_sector_pct", 0.35)),
        float(constraints.get("max_total_exposure_pct", 0.9)),
        int(constraints.get("max_daily_orders", 12)),
        config_source,
    )


def _portfolio_risk_params_map(
    max_sector_pct: float,
    max_total_exposure_pct: float,
    max_daily_orders: int,
) -> dict[str, float | int]:
    return {
        "max_sector_pct": round(max_sector_pct, 4),
        "max_total_exposure_pct": round(max_total_exposure_pct, 4),
        "max_daily_orders": max_daily_orders,
    }


def _strategy_version(
    strategy_id: str,
    execution_rule_version: str,
    intel_version: str | None = None,
) -> str:
    parts = [strategy_id, execution_rule_version]
    if intel_version:
        parts.append(intel_version)
    return "@".join(parts)


def _strategy_meta(
    strategy_id: str,
    execution_rule_version: str,
    execution_config_source: str | None,
    intel_version: str | None = None,
    intel_config_source: str | None = None,
) -> StrategyMeta:
    return StrategyMeta(
        strategy_id=strategy_id,
        strategy_version=_strategy_version(strategy_id, execution_rule_version, intel_version),
        execution_rule_version=execution_rule_version,
        intel_version=intel_version,
        execution_config_source=execution_config_source,
        intel_config_source=intel_config_source,
    )


def _clean_html_text(value: str) -> str:
    text = re.sub(r"<[^>]+>", "", value)
    text = unescape(text)
    return " ".join(text.split())


def _event_store_key(item: NewsItem) -> str:
    return item.id


def _sector_aliases(sector_alias_key: str | None = None, original: str = "") -> list[str]:
    aliases = {
        "ai": ["ai", "人工智能", "大模型", "算力", "新质生产力", "科技创新"],
        "机器人": ["机器人", "具身智能", "智能机器人", "新质生产力", "科技创新"],
        "robotics": ["机器人", "具身智能", "智能机器人", "新质生产力", "科技创新"],
        "半导体": ["半导体", "芯片", "集成电路", "科技创新", "高新技术", "现代化产业体系"],
        "semiconductor": ["半导体", "芯片", "集成电路", "科技创新", "高新技术", "现代化产业体系"],
        "新能源": ["新能源", "光伏", "储能", "锂电", "电力市场", "绿色低碳"],
        "new_energy": ["新能源", "光伏", "储能", "锂电", "电力市场", "绿色低碳"],
        "汽车": ["汽车", "智驾", "智能驾驶", "新能源车", "新质生产力"],
        "auto": ["汽车", "智驾", "智能驾驶", "新能源车", "新质生产力"],
    }
    key = (sector_alias_key or original).casefold()
    return aliases.get(key, [original] if original else [])


def _theme_aliases(theme: str) -> list[str]:
    return _sector_aliases(original=theme)


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _stddev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    avg = _mean(values)
    variance = sum((value - avg) ** 2 for value in values) / len(values)
    return variance**0.5


def _sma(values: list[float], period: int) -> float:
    if len(values) < period or period <= 0:
        return 0.0
    return _mean(values[-period:])


def _ema_series(values: list[float], period: int) -> list[float]:
    if not values or period <= 0:
        return []
    multiplier = 2 / (period + 1)
    ema_values = [values[0]]
    for value in values[1:]:
        ema_values.append((value - ema_values[-1]) * multiplier + ema_values[-1])
    return ema_values


def _rsi(values: list[float], period: int = 14) -> float:
    if len(values) <= period:
        return 50.0
    gains: list[float] = []
    losses: list[float] = []
    for previous, current in zip(values[:-1], values[1:]):
        delta = current - previous
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))
    avg_gain = _mean(gains[-period:])
    avg_loss = _mean(losses[-period:])
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _atr_percent(bars: list[Bar], period: int = 14) -> float:
    if len(bars) < 2:
        return 0.02
    true_ranges: list[float] = []
    for previous, current in zip(bars[:-1], bars[1:]):
        tr = max(
            current.high - current.low,
            abs(current.high - previous.close),
            abs(current.low - previous.close),
        )
        true_ranges.append(tr)
    atr = _mean(true_ranges[-period:]) if true_ranges else 0.0
    latest_close = bars[-1].close or 1.0
    return atr / latest_close if latest_close else 0.02


class MarketService:
    """Local deterministic fallback when no market-data provider is configured."""

    def get_quote(self, symbol: str) -> Quote:
        market_time = _now().replace(second=0, microsecond=0)
        last = 1688.0
        prev_close = 1662.31
        change = round(last - prev_close, 2)
        return Quote(
            symbol=symbol,
            name="样例股票",
            last=last,
            open=1675.5,
            high=1692.4,
            low=1668.88,
            prev_close=prev_close,
            change=change,
            change_pct=round(change / prev_close * 100, 3),
            volume=3521980,
            amount=5932104432.0,
            turnover_ratio=0.29,
            amplitude_pct=1.42,
            limit_status=LimitStatus.NORMAL,
            trading_status=TradingStatus.TRADING,
            market_time=market_time,
            source="mock",
            received_at=_now(),
        )

    def get_bars(self, symbol: str, interval: str, limit: int) -> BarsResponse:
        end = _now().replace(second=0, microsecond=0)
        bars: list[Bar] = []
        price = 1660.0
        minutes = {
            "1m": 1,
            "5m": 5,
            "15m": 15,
            "30m": 30,
            "60m": 60,
            "1d": 60 * 24,
            "1w": 60 * 24 * 7,
        }.get(interval, 60 * 24)
        step = timedelta(minutes=minutes)
        for idx in range(limit):
            ts = end - step * (limit - idx)
            close = round(price + idx * 0.8, 2)
            bars.append(
                Bar(
                    ts=ts,
                    open=round(close - 1.2, 2),
                    high=round(close + 1.5, 2),
                    low=round(close - 1.8, 2),
                    close=close,
                    volume=100000 + idx * 1200,
                    amount=(100000 + idx * 1200) * close,
                )
            )
        return BarsResponse(symbol=symbol, interval=interval, bars=bars, source="mock")


class TushareMarketService:
    """Official-market-data adapter built on top of the Tushare SDK.

    Current implementation uses:
    - `rt_k` for quote snapshots
    - `rt_min` for same-day intraday bars
    - `daily` for daily bars
    """

    def __init__(self, token: str) -> None:
        try:
            import tushare as ts
        except ImportError as exc:
            raise ProviderError("tushare package is not installed") from exc
        ts.set_token(token)
        self._ts = ts
        self._pro = ts.pro_api(token)
        self._quote_cache: dict[str, CacheEntry] = {}
        self._bars_cache: dict[str, CacheEntry] = {}

    def get_quote(self, symbol: str) -> Quote:
        cache_key = symbol.upper()

        def fetch() -> Quote:
            try:
                return self._fetch_crawler_quote(symbol)
            except ProviderError:
                pass
            try:
                return self._fetch_rt_quote(symbol)
            except ProviderError:
                return self._get_daily_snapshot_quote(symbol)

        return self._remember(
            self._quote_cache,
            cache_key,
            timedelta(seconds=settings.tushare_quote_ttl_seconds),
            fetch,
        )

    def _fetch_crawler_quote(self, symbol: str) -> Quote:
        try:
            frame = self._ts.realtime_quote(ts_code=symbol)
        except Exception as exc:
            raise ProviderError(f"tushare realtime_quote failed: {exc}") from exc
        if frame is None or frame.empty:
            raise ProviderError(f"no Tushare crawler quote rows returned for {symbol}")

        row = frame.iloc[0]
        prev_close = _float(row.get("PRE_CLOSE"))
        last = _float(row.get("PRICE"))
        change = last - prev_close
        amplitude_base = prev_close if prev_close else last
        amplitude_pct = (
            ((_float(row.get("HIGH")) - _float(row.get("LOW"))) / amplitude_base) * 100
            if amplitude_base
            else 0.0
        )
        trade_time = f"{row.get('DATE', '')} {row.get('TIME', '')}".strip()

        return Quote(
            symbol=str(row.get("TS_CODE") or symbol),
            name=str(row.get("NAME") or symbol),
            last=last,
            open=_float(row.get("OPEN")),
            high=_float(row.get("HIGH")),
            low=_float(row.get("LOW")),
            prev_close=prev_close,
            change=round(change, 2),
            change_pct=round((change / prev_close) * 100, 3) if prev_close else 0.0,
            volume=_int(row.get("VOLUME")),
            amount=_float(row.get("AMOUNT")),
            turnover_ratio=0.0,
            amplitude_pct=round(amplitude_pct, 3),
            limit_status=LimitStatus.NORMAL,
            trading_status=TradingStatus.TRADING,
            market_time=_parse_trade_time(trade_time),
            source="tushare_crawler_quote",
            received_at=_now(),
        )

    def _fetch_rt_quote(self, symbol: str) -> Quote:
        try:
            frame = self._pro.rt_k(ts_code=symbol)
        except Exception as exc:
            raise ProviderError(f"tushare rt_k failed: {exc}") from exc
        if frame is None or frame.empty:
            raise ProviderError(f"no Tushare quote rows returned for {symbol}")

        row = frame.iloc[0]
        prev_close = _float(row.get("pre_close"))
        close = _float(row.get("close"))
        change = close - prev_close
        amplitude_base = prev_close if prev_close else close
        amplitude_pct = (
            ((_float(row.get("high")) - _float(row.get("low"))) / amplitude_base) * 100
            if amplitude_base
            else 0.0
        )
        trade_time = row.get("trade_time")
        if trade_time is None:
            trade_time = datetime.combine(date.today(), time(15, 0)).strftime("%Y-%m-%d %H:%M:%S")

        return Quote(
            symbol=str(row.get("ts_code") or symbol),
            name=str(row.get("name") or symbol),
            last=close,
            open=_float(row.get("open")),
            high=_float(row.get("high")),
            low=_float(row.get("low")),
            prev_close=prev_close,
            change=round(change, 2),
            change_pct=round((change / prev_close) * 100, 3) if prev_close else 0.0,
            volume=_int(row.get("vol")),
            amount=_float(row.get("amount")),
            turnover_ratio=0.0,
            amplitude_pct=round(amplitude_pct, 3),
            limit_status=LimitStatus.NORMAL,
            trading_status=TradingStatus.TRADING,
            market_time=_parse_trade_time(trade_time),
            source="tushare",
            received_at=_now(),
        )

    def _get_daily_snapshot_quote(self, symbol: str) -> Quote:
        bars = self._get_daily_bars(symbol, 2)
        if not bars.bars:
            raise ProviderError(f"no Tushare daily snapshot rows returned for {symbol}")

        latest = bars.bars[-1]
        prev_close = bars.bars[-2].close if len(bars.bars) > 1 else latest.close
        change = latest.close - prev_close
        amplitude_base = prev_close if prev_close else latest.close
        amplitude_pct = (
            ((latest.high - latest.low) / amplitude_base) * 100 if amplitude_base else 0.0
        )
        market_day = latest.ts.astimezone(_LOCAL_TZ).date()
        market_time = datetime.combine(market_day, time(15, 0), tzinfo=_LOCAL_TZ)

        return Quote(
            symbol=symbol,
            name=symbol,
            last=latest.close,
            open=latest.open,
            high=latest.high,
            low=latest.low,
            prev_close=prev_close,
            change=round(change, 2),
            change_pct=round((change / prev_close) * 100, 3) if prev_close else 0.0,
            volume=latest.volume,
            amount=latest.amount,
            turnover_ratio=0.0,
            amplitude_pct=round(amplitude_pct, 3),
            limit_status=LimitStatus.NORMAL,
            trading_status=TradingStatus.CLOSED,
            market_time=market_time,
            source="tushare_daily_snapshot",
            received_at=_now(),
        )

    def get_bars(self, symbol: str, interval: str, limit: int) -> BarsResponse:
        if interval == "1d":
            return self._get_daily_bars(symbol, limit)
        return self._get_intraday_bars(symbol, interval, limit)

    def _get_intraday_bars(self, symbol: str, interval: str, limit: int) -> BarsResponse:
        freq = {
            "1m": "1MIN",
            "5m": "5MIN",
            "15m": "15MIN",
            "30m": "30MIN",
            "60m": "60MIN",
        }.get(interval)
        if not freq:
            raise ProviderError(f"unsupported intraday interval for tushare: {interval}")
        cache_key = f"{symbol.upper()}:{interval}:{limit}"

        def fetch() -> BarsResponse:
            try:
                frame = self._pro.rt_min(ts_code=symbol, freq=freq)
            except Exception as exc:
                raise ProviderError(f"tushare rt_min failed: {exc}") from exc
            if frame is None or frame.empty:
                raise ProviderError(f"no Tushare intraday rows returned for {symbol}")

            frame = frame.tail(limit)
            bars = [
                Bar(
                    ts=_parse_trade_time(row.get("time")),
                    open=_float(row.get("open")),
                    high=_float(row.get("high")),
                    low=_float(row.get("low")),
                    close=_float(row.get("close")),
                    volume=_int(row.get("vol")),
                    amount=_float(row.get("amount")),
                )
                for _, row in frame.iterrows()
            ]
            return BarsResponse(symbol=symbol, interval=interval, bars=bars, source="tushare")

        return self._remember(
            self._bars_cache,
            cache_key,
            timedelta(seconds=settings.tushare_bars_ttl_seconds),
            fetch,
        )

    def _get_daily_bars(self, symbol: str, limit: int) -> BarsResponse:
        end_date = date.today().strftime("%Y%m%d")
        start_date = (date.today() - timedelta(days=max(limit * 3, 30))).strftime("%Y%m%d")
        cache_key = f"{symbol.upper()}:1d:{limit}"

        def fetch() -> BarsResponse:
            try:
                frame = self._pro.daily(ts_code=symbol, start_date=start_date, end_date=end_date)
            except Exception as exc:
                raise ProviderError(f"tushare daily failed: {exc}") from exc
            if frame is None or frame.empty:
                raise ProviderError(f"no Tushare daily rows returned for {symbol}")

            frame = frame.sort_values("trade_date").tail(limit)
            bars = [
                Bar(
                    ts=_parse_trade_time(row.get("trade_date")),
                    open=_float(row.get("open")),
                    high=_float(row.get("high")),
                    low=_float(row.get("low")),
                    close=_float(row.get("close")),
                    volume=_int(row.get("vol")),
                    amount=_float(row.get("amount")),
                )
                for _, row in frame.iterrows()
            ]
            return BarsResponse(symbol=symbol, interval="1d", bars=bars, source="tushare")

        return self._remember(
            self._bars_cache,
            cache_key,
            timedelta(seconds=settings.tushare_bars_ttl_seconds),
            fetch,
        )

    def _remember(
        self,
        cache: dict[str, CacheEntry],
        key: str,
        success_ttl: timedelta,
        fetch: Callable[[], Any],
    ) -> Any:
        now = _now()
        entry = cache.get(key)
        if entry and entry.expires_at > now:
            if entry.error:
                raise entry.error
            return entry.value

        try:
            value = fetch()
        except ProviderError as exc:
            cache[key] = CacheEntry(
                expires_at=now + timedelta(seconds=settings.tushare_error_ttl_seconds),
                error=exc,
            )
            raise

        cache[key] = CacheEntry(expires_at=now + success_ttl, value=value)
        return value


class AkshareMarketService:
    """Secondary A-share market-data adapter based on AKShare Eastmoney endpoints."""

    def __init__(self) -> None:
        try:
            import akshare as ak
        except ImportError as exc:
            raise ProviderError("akshare package is not installed") from exc
        self._ak = ak
        self._quote_cache: dict[str, CacheEntry] = {}
        self._bars_cache: dict[str, CacheEntry] = {}

    def get_quote(self, symbol: str) -> Quote:
        cache_key = symbol.upper()
        return self._remember(
            self._quote_cache,
            cache_key,
            timedelta(seconds=settings.akshare_quote_ttl_seconds),
            lambda: self._fetch_spot_quote(symbol),
        )

    def _fetch_spot_quote(self, symbol: str) -> Quote:
        code = _ashare_symbol_code(symbol)
        try:
            frame = self._ak.stock_zh_a_spot_em()
        except Exception as exc:
            raise ProviderError(f"akshare spot quote failed: {exc}") from exc
        if frame is None or frame.empty:
            raise ProviderError("akshare spot quote returned no rows")
        match = frame[frame["代码"].astype(str).str.upper() == code]
        if match.empty:
            raise ProviderError(f"akshare spot quote could not find symbol {symbol}")
        row = match.iloc[0]
        prev_close = _float(_row_get(row, "昨收", "昨收盘", "昨收价"))
        last = _float(_row_get(row, "最新价", "最新"))
        change = _float(_row_get(row, "涨跌额"))
        if not change and prev_close and last:
            change = last - prev_close
        high = _float(_row_get(row, "最高"))
        low = _float(_row_get(row, "最低"))
        amplitude_base = prev_close if prev_close else last
        amplitude_pct = (((high - low) / amplitude_base) * 100) if amplitude_base else 0.0
        market_time = _now().astimezone(_LOCAL_TZ).replace(second=0, microsecond=0)
        return Quote(
            symbol=symbol,
            name=str(_row_get(row, "名称") or symbol),
            last=last,
            open=_float(_row_get(row, "今开", "开盘")),
            high=high,
            low=low,
            prev_close=prev_close,
            change=round(change, 2),
            change_pct=round(_float(_row_get(row, "涨跌幅")), 3),
            volume=_int(_row_get(row, "成交量")),
            amount=_float(_row_get(row, "成交额")),
            turnover_ratio=round(_float(_row_get(row, "换手率")), 3),
            amplitude_pct=round(amplitude_pct, 3),
            limit_status=LimitStatus.NORMAL,
            trading_status=TradingStatus.TRADING,
            market_time=market_time,
            source="akshare_spot_em",
            received_at=_now(),
        )

    def get_bars(self, symbol: str, interval: str, limit: int) -> BarsResponse:
        if interval == "1d":
            return self._get_daily_bars(symbol, limit)
        return self._get_intraday_bars(symbol, interval, limit)

    def _get_intraday_bars(self, symbol: str, interval: str, limit: int) -> BarsResponse:
        period = {
            "1m": "1",
            "5m": "5",
            "15m": "15",
            "30m": "30",
            "60m": "60",
        }.get(interval)
        if not period:
            raise ProviderError(f"unsupported intraday interval for akshare: {interval}")
        code = _ashare_symbol_code(symbol)
        cache_key = f"{symbol.upper()}:{interval}:{limit}"

        def fetch() -> BarsResponse:
            try:
                frame = self._ak.stock_zh_a_hist_min_em(symbol=code, period=period, adjust="")
            except Exception as exc:
                raise ProviderError(f"akshare minute bars failed: {exc}") from exc
            if frame is None or frame.empty:
                raise ProviderError(f"no akshare intraday rows returned for {symbol}")
            frame = frame.tail(limit)
            bars = [
                Bar(
                    ts=_parse_trade_time(_row_get(row, "时间", "日期时间", "日期")),
                    open=_float(_row_get(row, "开盘")),
                    high=_float(_row_get(row, "最高")),
                    low=_float(_row_get(row, "最低")),
                    close=_float(_row_get(row, "收盘", "最新价")),
                    volume=_int(_row_get(row, "成交量")),
                    amount=_float(_row_get(row, "成交额")),
                )
                for _, row in frame.iterrows()
            ]
            return BarsResponse(symbol=symbol, interval=interval, bars=bars, source="akshare")

        return self._remember(
            self._bars_cache,
            cache_key,
            timedelta(seconds=settings.akshare_bars_ttl_seconds),
            fetch,
        )

    def _get_daily_bars(self, symbol: str, limit: int) -> BarsResponse:
        code = _ashare_symbol_code(symbol)
        cache_key = f"{symbol.upper()}:1d:{limit}"
        end_date = date.today().strftime("%Y%m%d")
        start_date = (date.today() - timedelta(days=max(limit * 3, 30))).strftime("%Y%m%d")

        def fetch() -> BarsResponse:
            try:
                frame = self._ak.stock_zh_a_hist(
                    symbol=code,
                    period="daily",
                    start_date=start_date,
                    end_date=end_date,
                    adjust="",
                )
            except Exception as exc:
                raise ProviderError(f"akshare daily bars failed: {exc}") from exc
            if frame is None or frame.empty:
                raise ProviderError(f"no akshare daily rows returned for {symbol}")
            frame = frame.tail(limit)
            bars = [
                Bar(
                    ts=_parse_trade_time(_row_get(row, "日期")),
                    open=_float(_row_get(row, "开盘")),
                    high=_float(_row_get(row, "最高")),
                    low=_float(_row_get(row, "最低")),
                    close=_float(_row_get(row, "收盘")),
                    volume=_int(_row_get(row, "成交量")),
                    amount=_float(_row_get(row, "成交额")),
                )
                for _, row in frame.iterrows()
            ]
            return BarsResponse(symbol=symbol, interval="1d", bars=bars, source="akshare")

        return self._remember(
            self._bars_cache,
            cache_key,
            timedelta(seconds=settings.akshare_bars_ttl_seconds),
            fetch,
        )

    def _remember(
        self,
        cache: dict[str, CacheEntry],
        key: str,
        success_ttl: timedelta,
        fetch: Callable[[], Any],
    ) -> Any:
        now = _now()
        entry = cache.get(key)
        if entry and entry.expires_at > now:
            if entry.error:
                raise entry.error
            return entry.value

        try:
            value = fetch()
        except ProviderError as exc:
            cache[key] = CacheEntry(
                expires_at=now + timedelta(seconds=settings.akshare_error_ttl_seconds),
                error=exc,
            )
            raise

        cache[key] = CacheEntry(expires_at=now + success_ttl, value=value)
        return value


class MarketProviderFacade:
    def __init__(self) -> None:
        self.mode = settings.market_data_provider
        self._mock = MarketService()
        self._tushare: TushareMarketService | None = None
        self._akshare: AkshareMarketService | None = None
        self._audit_window_seconds = 300
        self._decision_history: dict[str, list[tuple[datetime, str]]] = {"quote": [], "bars": []}
        self._provider_audit: dict[str, dict[str, ProviderAuditState]] = {"quote": {}, "bars": {}}
        if settings.tushare_token:
            try:
                self._tushare = TushareMarketService(settings.tushare_token)
            except ProviderError:
                self._tushare = None
        try:
            self._akshare = AkshareMarketService()
        except ProviderError:
            self._akshare = None

    @property
    def effective_provider(self) -> str:
        if self.mode == "mock":
            return "mock"
        if self.mode == "akshare":
            return "akshare" if self._akshare else "akshare_unavailable"
        if self.mode == "tushare":
            return "tushare" if self._tushare else "tushare_unavailable"
        if self.mode == "auto":
            if self._tushare and self._akshare:
                return "tushare_primary+akshare_fallback"
            if self._tushare:
                return "tushare"
            if self._akshare:
                return "akshare"
            return "unavailable"
        return self.mode

    def _all_candidates_failed_message(self, kind: str, symbol: str, candidate_scores: list[ProviderCandidateScore]) -> str:
        errors = [
            f"{item.source}:{item.error_code or 'unknown_error'}"
            for item in candidate_scores
            if item.status != "ok"
        ]
        if errors:
            return f"provider unavailable for {kind} {symbol}; {'; '.join(errors)}"
        return f"provider unavailable for {kind} {symbol}; no live providers configured"

    def _record_provider_result(self, kind: str, source: str, ok: bool, error_code: str | None = None) -> None:
        bucket = self._provider_audit.setdefault(kind, {})
        state = bucket.setdefault(source, ProviderAuditState())
        now = _now()
        if ok:
            state.consecutive_failures = 0
            state.last_success_at = now
            return
        state.consecutive_failures += 1
        state.last_error_at = now
        state.last_error_code = error_code

    def _record_decision(self, kind: str, source: str) -> None:
        now = _now()
        history = self._decision_history.setdefault(kind, [])
        history.append((now, source))
        cutoff = now - timedelta(seconds=self._audit_window_seconds)
        self._decision_history[kind] = [(ts, name) for ts, name in history if ts >= cutoff]

    def _recent_switch_count(self, kind: str) -> int:
        history = self._decision_history.get(kind, [])
        switches = 0
        previous: str | None = None
        for _, source in history:
            if previous is not None and source != previous:
                switches += 1
            previous = source
        return switches

    def _selected_source_streak(self, kind: str, source: str) -> int:
        history = self._decision_history.get(kind, [])
        streak = 0
        for _, item_source in reversed(history):
            if item_source != source:
                break
            streak += 1
        return streak

    def _source_audit_snapshot(self, kind: str) -> list[ProviderSourceAudit]:
        bucket = self._provider_audit.get(kind, {})
        items = [
            ProviderSourceAudit(
                source=source,
                consecutive_failures=state.consecutive_failures,
                last_success_at=state.last_success_at,
                last_error_at=state.last_error_at,
                last_error_code=state.last_error_code,
            )
            for source, state in sorted(bucket.items())
        ]
        return items

    def decision_status(self) -> MarketDecisionStatus:
        quote_history = self._decision_history.get("quote", [])
        bars_history = self._decision_history.get("bars", [])
        quote_selected_source = quote_history[-1][1] if quote_history else None
        bars_selected_source = bars_history[-1][1] if bars_history else None
        return MarketDecisionStatus(
            provider_mode=self.mode,
            effective_provider=self.effective_provider,
            audit_window_seconds=self._audit_window_seconds,
            quote_recent_switch_count=self._recent_switch_count("quote"),
            bars_recent_switch_count=self._recent_switch_count("bars"),
            quote_selected_source=quote_selected_source,
            bars_selected_source=bars_selected_source,
            quote_selected_source_streak=self._selected_source_streak("quote", quote_selected_source) if quote_selected_source else 0,
            bars_selected_source_streak=self._selected_source_streak("bars", bars_selected_source) if bars_selected_source else 0,
            quote_source_audit=self._source_audit_snapshot("quote"),
            bars_source_audit=self._source_audit_snapshot("bars"),
        )

    def _quote_priority(self, source: str) -> int:
        priorities = {
            "tushare_crawler_quote": 40,
            "akshare_spot_em": 30,
            "tushare": 25,
            "akshare": 20,
            "tushare_daily_snapshot": 10,
            "mock": 0,
        }
        return priorities.get(source, 0)

    def _quote_score(self, quote: Quote) -> tuple[int, int, int, int]:
        freshness_seconds = max(
            0,
            int((_now().astimezone(_LOCAL_TZ) - quote.market_time.astimezone(_LOCAL_TZ)).total_seconds()),
        )
        freshness_bucket = 0
        if freshness_seconds <= 120:
            freshness_bucket = 4
        elif freshness_seconds <= 900:
            freshness_bucket = 3
        elif freshness_seconds <= 3600:
            freshness_bucket = 2
        elif freshness_seconds <= 86400:
            freshness_bucket = 1
        completeness = sum(
            1
            for value in [
                quote.open,
                quote.high,
                quote.low,
                quote.prev_close,
                quote.volume,
                quote.amount,
                quote.turnover_ratio,
            ]
            if value and value > 0
        )
        trading_bonus = 1 if quote.trading_status == TradingStatus.TRADING else 0
        return (
            freshness_bucket,
            completeness,
            trading_bonus,
            self._quote_priority(quote.source),
        )

    def _quote_candidate_score(self, quote: Quote) -> ProviderCandidateScore:
        freshness_bucket, completeness, trading_bonus, source_priority = self._quote_score(quote)
        return ProviderCandidateScore(
            source=quote.source,
            status="ok",
            error_code=None,
            freshness_bucket=freshness_bucket,
            completeness=completeness,
            trading_bonus=trading_bonus,
            source_priority=source_priority,
            score_vector=[freshness_bucket, completeness, trading_bonus, source_priority],
        )

    def _error_candidate_score(self, source: str, detail: str) -> ProviderCandidateScore:
        return ProviderCandidateScore(
            source=source,
            status="error",
            error_code=_provider_error_code(detail),
            detail=detail,
            freshness_bucket=0,
            completeness=0,
            trading_bonus=0,
            coverage=0,
            source_priority=0,
            score_vector=[0, 0, 0, 0],
        )

    def _bars_priority(self, source: str) -> int:
        priorities = {
            "tushare": 30,
            "akshare": 25,
            "mock": 0,
        }
        return priorities.get(source, 0)

    def _bars_score(self, bars: BarsResponse, requested_limit: int, interval: str) -> tuple[int, int, int]:
        if not bars.bars:
            return (0, 0, self._bars_priority(bars.source))
        latest_ts = bars.bars[-1].ts.astimezone(_LOCAL_TZ)
        freshness_seconds = max(0, int((_now().astimezone(_LOCAL_TZ) - latest_ts).total_seconds()))
        interval_windows = {
            "1m": 180,
            "5m": 900,
            "15m": 2700,
            "30m": 5400,
            "60m": 10800,
            "1d": 172800,
            "1w": 1209600,
        }
        freshness_bucket = 0
        threshold = interval_windows.get(interval, 172800)
        if freshness_seconds <= threshold:
            freshness_bucket = 3
        elif freshness_seconds <= threshold * 3:
            freshness_bucket = 2
        elif freshness_seconds <= threshold * 7:
            freshness_bucket = 1
        coverage = min(len(bars.bars), requested_limit)
        return (
            freshness_bucket,
            coverage,
            self._bars_priority(bars.source),
        )

    def _bars_candidate_score(self, bars: BarsResponse, requested_limit: int, interval: str) -> ProviderCandidateScore:
        freshness_bucket, coverage, source_priority = self._bars_score(bars, requested_limit, interval)
        return ProviderCandidateScore(
            source=bars.source,
            status="ok",
            error_code=None,
            freshness_bucket=freshness_bucket,
            completeness=0,
            coverage=coverage,
            source_priority=source_priority,
            score_vector=[freshness_bucket, coverage, source_priority],
        )

    def _best_quote(self, symbol: str) -> Quote:
        candidates: list[Quote] = []
        candidate_scores: list[ProviderCandidateScore] = []
        if self._tushare:
            try:
                quote = self._tushare.get_quote(symbol)
                candidates.append(quote)
                candidate_scores.append(self._quote_candidate_score(quote))
                self._record_provider_result("quote", "tushare", True)
            except ProviderError as exc:
                detail = str(exc)
                error_code = _provider_error_code(detail)
                candidate_scores.append(self._error_candidate_score("tushare", detail))
                self._record_provider_result("quote", "tushare", False, error_code)
        if self._akshare:
            try:
                quote = self._akshare.get_quote(symbol)
                candidates.append(quote)
                candidate_scores.append(self._quote_candidate_score(quote))
                self._record_provider_result("quote", "akshare", True)
            except ProviderError as exc:
                detail = str(exc)
                error_code = _provider_error_code(detail)
                candidate_scores.append(self._error_candidate_score("akshare", detail))
                self._record_provider_result("quote", "akshare", False, error_code)
        if not candidates:
            raise ProviderError(self._all_candidates_failed_message("quote", symbol, candidate_scores))
        selected = max(candidates, key=self._quote_score)
        self._record_decision("quote", selected.source)
        selected.provider_decision = ProviderDecision(
            mode="auto",
            selected_source=selected.source,
            reason="freshness_then_completeness_then_priority",
            audit_window_seconds=self._audit_window_seconds,
            recent_switch_count=self._recent_switch_count("quote"),
            selected_source_streak=self._selected_source_streak("quote", selected.source),
            candidates=sorted(candidate_scores, key=lambda item: (item.status == "ok", item.score_vector), reverse=True),
            source_audit=self._source_audit_snapshot("quote"),
        )
        return selected

    def _best_bars(self, symbol: str, interval: str, limit: int) -> BarsResponse:
        candidates: list[BarsResponse] = []
        candidate_scores: list[ProviderCandidateScore] = []
        if self._tushare:
            try:
                bars = self._tushare.get_bars(symbol, interval, limit)
                candidates.append(bars)
                candidate_scores.append(self._bars_candidate_score(bars, limit, interval))
                self._record_provider_result("bars", "tushare", True)
            except ProviderError as exc:
                detail = str(exc)
                error_code = _provider_error_code(detail)
                candidate_scores.append(self._error_candidate_score("tushare", detail))
                self._record_provider_result("bars", "tushare", False, error_code)
        if self._akshare:
            try:
                bars = self._akshare.get_bars(symbol, interval, limit)
                candidates.append(bars)
                candidate_scores.append(self._bars_candidate_score(bars, limit, interval))
                self._record_provider_result("bars", "akshare", True)
            except ProviderError as exc:
                detail = str(exc)
                error_code = _provider_error_code(detail)
                candidate_scores.append(self._error_candidate_score("akshare", detail))
                self._record_provider_result("bars", "akshare", False, error_code)
        if not candidates:
            raise ProviderError(self._all_candidates_failed_message("bars", f"{symbol} {interval}", candidate_scores))
        selected = max(candidates, key=lambda item: self._bars_score(item, limit, interval))
        self._record_decision("bars", selected.source)
        selected.provider_decision = ProviderDecision(
            mode="auto",
            selected_source=selected.source,
            reason="freshness_then_coverage_then_priority",
            audit_window_seconds=self._audit_window_seconds,
            recent_switch_count=self._recent_switch_count("bars"),
            selected_source_streak=self._selected_source_streak("bars", selected.source),
            candidates=sorted(candidate_scores, key=lambda item: (item.status == "ok", item.score_vector), reverse=True),
            source_audit=self._source_audit_snapshot("bars"),
        )
        return selected

    def get_quote(self, symbol: str) -> Quote:
        if self.mode == "mock":
            return self._mock.get_quote(symbol)
        if self.mode == "akshare":
            if not self._akshare:
                raise ProviderError("akshare provider requested but unavailable; install dependencies")
            return self._akshare.get_quote(symbol)
        if self.mode == "tushare":
            if not self._tushare:
                raise ProviderError("tushare provider requested but unavailable; set TS_TOKEN and install dependencies")
            return self._tushare.get_quote(symbol)
        if self.mode == "auto":
            return self._best_quote(symbol)
        raise ProviderError(f"unknown market_data_provider mode: {self.mode}")

    def get_bars(self, symbol: str, interval: str, limit: int) -> BarsResponse:
        if self.mode == "mock":
            return self._mock.get_bars(symbol, interval, limit)
        if self.mode == "akshare":
            if not self._akshare:
                raise ProviderError("akshare provider requested but unavailable; install dependencies")
            return self._akshare.get_bars(symbol, interval, limit)
        if self.mode == "tushare":
            if not self._tushare:
                raise ProviderError("tushare provider requested but unavailable; set TS_TOKEN and install dependencies")
            return self._tushare.get_bars(symbol, interval, limit)
        if self.mode == "auto":
            return self._best_bars(symbol, interval, limit)
        raise ProviderError(f"unknown market_data_provider mode: {self.mode}")

    def _check_block_reason(
        self,
        checks: list[ProviderCheck],
        probe_names: tuple[str, ...],
    ) -> str | None:
        matching = [check for check in checks if check.name in probe_names]
        if any(check.status == "ok" for check in matching):
            return None
        if matching:
            for preferred_code in (
                "permission_denied",
                "network_path_unavailable",
                "provider_unavailable",
                "rate_limited",
                "dependency_missing",
                "upstream_timeout",
                "upstream_failed",
                "unknown_error",
            ):
                if any(check.error_code == preferred_code for check in matching):
                    return preferred_code
            unavailable = next((check for check in matching if check.status == "unavailable"), None)
            if unavailable:
                return unavailable.error_code or "provider_unavailable"
            errored = next((check for check in matching if check.status == "error"), None)
            if errored:
                return errored.error_code or "unknown_error"
        return "provider_unavailable"

    def _provider_status_response(self, symbol: str, checks: list[ProviderCheck]) -> MarketProviderStatus:
        quote_probe_names = ("quote", "quote_crawler", "quote_rt_k", "quote_akshare")
        intraday_probe_names = ("bars_1m", "bars_1m_tushare", "bars_1m_akshare")
        daily_probe_names = ("bars_1d", "bars_1d_tushare", "bars_1d_akshare")
        quote_ready = any(check.name in quote_probe_names and check.status == "ok" for check in checks)
        intraday_ready = any(check.name in intraday_probe_names and check.status == "ok" for check in checks)
        daily_ready = any(check.name in daily_probe_names and check.status == "ok" for check in checks)
        return MarketProviderStatus(
            provider_mode=self.mode,
            effective_provider=self.effective_provider,
            token_configured=bool(settings.tushare_token),
            probe_symbol=symbol,
            quote_ready=quote_ready,
            quote_block_reason=None if quote_ready else self._check_block_reason(checks, quote_probe_names),
            intraday_ready=intraday_ready,
            intraday_block_reason=None if intraday_ready else self._check_block_reason(checks, intraday_probe_names),
            daily_ready=daily_ready,
            daily_block_reason=None if daily_ready else self._check_block_reason(checks, daily_probe_names),
            checks=checks,
        )

    def provider_status(self, symbol: str) -> MarketProviderStatus:
        checks: list[ProviderCheck] = []
        if self.mode == "mock":
            checks.extend(
                [
                    ProviderCheck(name="quote", status="ok", detail="mock provider"),
                    ProviderCheck(name="bars_1m", status="ok", detail="mock provider"),
                    ProviderCheck(name="bars_1d", status="ok", detail="mock provider"),
                ]
            )
            return self._provider_status_response(symbol, checks)

        if self.mode == "akshare":
            if not self._akshare:
                checks.append(
                    ProviderCheck(
                        name="bootstrap_akshare",
                        status="unavailable",
                        error_code="provider_unavailable",
                        detail="AKShare provider unavailable",
                    )
                )
            else:
                probes = [
                    ("quote_akshare", lambda: self._akshare.get_quote(symbol)),
                    ("bars_1m_akshare", lambda: self._akshare.get_bars(symbol, "1m", 1)),
                    ("bars_1d_akshare", lambda: self._akshare.get_bars(symbol, "1d", 1)),
                ]
                for name, fn in probes:
                    try:
                        fn()
                        checks.append(ProviderCheck(name=name, status="ok"))
                    except Exception as exc:
                        detail = str(exc)
                        checks.append(
                            ProviderCheck(name=name, status="error", error_code=_provider_error_code(detail), detail=detail)
                        )
            return self._provider_status_response(symbol, checks)

        if not self._tushare and not self._akshare:
            checks.append(
                ProviderCheck(
                    name="bootstrap",
                    status="unavailable",
                    error_code="provider_unavailable",
                    detail="No market provider available; install AKShare or configure Tushare",
                )
            )
            return self._provider_status_response(symbol, checks)

        if self._tushare:
            probes = [
                ("quote_crawler", lambda: self._tushare._fetch_crawler_quote(symbol)),
                ("quote_rt_k", lambda: self._tushare._fetch_rt_quote(symbol)),
                ("bars_1m_tushare", lambda: self._tushare.get_bars(symbol, "1m", 1)),
                ("bars_1d_tushare", lambda: self._tushare.get_bars(symbol, "1d", 1)),
            ]
            for name, fn in probes:
                try:
                    fn()
                    checks.append(ProviderCheck(name=name, status="ok"))
                except Exception as exc:
                    detail = str(exc)
                    checks.append(
                        ProviderCheck(name=name, status="error", error_code=_provider_error_code(detail), detail=detail)
                    )
        else:
            checks.append(
                ProviderCheck(name="bootstrap_tushare", status="unavailable", error_code="provider_unavailable", detail="Tushare unavailable")
            )

        if self._akshare:
            probes = [
                ("quote_akshare", lambda: self._akshare.get_quote(symbol)),
                ("bars_1m_akshare", lambda: self._akshare.get_bars(symbol, "1m", 1)),
                ("bars_1d_akshare", lambda: self._akshare.get_bars(symbol, "1d", 1)),
            ]
            for name, fn in probes:
                try:
                    fn()
                    checks.append(ProviderCheck(name=name, status="ok"))
                except Exception as exc:
                    detail = str(exc)
                    checks.append(
                        ProviderCheck(name=name, status="error", error_code=_provider_error_code(detail), detail=detail)
                    )
        else:
            checks.append(
                ProviderCheck(name="bootstrap_akshare", status="unavailable", error_code="provider_unavailable", detail="AKShare unavailable")
            )

        return self._provider_status_response(symbol, checks)


class TushareIntelService:
    _NEWS_SOURCES = ("cls", "yicai", "eastmoney", "sina")
    _NEWS_SOURCE_META = {
        "cls": ("财联社", "https://www.cls.cn/"),
        "yicai": ("第一财经", "https://www.yicai.com/"),
        "eastmoney": ("东方财富", "https://www.eastmoney.com/"),
        "sina": ("新浪财经", "https://finance.sina.com.cn/"),
    }

    def __init__(self, token: str) -> None:
        try:
            import tushare as ts
        except ImportError as exc:
            raise ProviderError("tushare package is not installed") from exc
        ts.set_token(token)
        self._pro = ts.pro_api(token)
        self._report_cache: dict[str, CacheEntry] = {}
        self._news_cache: dict[str, CacheEntry] = {}
        self._profile_cache: dict[str, CacheEntry] = {}

    def get_report(self, symbol: str | None, sector: str | None, lookback_hours: int) -> IntelReport:
        cache_key = f"{symbol or '*'}:{sector or '*'}:{lookback_hours}"
        return self._remember(
            self._report_cache,
            cache_key,
            timedelta(seconds=settings.tushare_intel_ttl_seconds),
            lambda: self._fetch_report(symbol, sector, lookback_hours),
        )

    def get_news(self, symbol: str | None, sector: str | None, lookback_hours: int) -> list[NewsItem]:
        cache_key = f"{symbol or '*'}:{sector or '*'}:{lookback_hours}"
        return self._remember(
            self._news_cache,
            cache_key,
            timedelta(seconds=settings.tushare_intel_ttl_seconds),
            lambda: self._fetch_news(symbol, sector, lookback_hours),
        )

    def _remember(self, cache: dict[str, CacheEntry], key: str, success_ttl: timedelta, fetch: Callable[[], Any]) -> Any:
        now = _now()
        entry = cache.get(key)
        if entry and entry.expires_at > now:
            if entry.error:
                raise entry.error
            return entry.value

        try:
            value = fetch()
        except ProviderError as exc:
            cache[key] = CacheEntry(
                expires_at=now + timedelta(seconds=settings.tushare_error_ttl_seconds),
                error=exc,
            )
            raise

        cache[key] = CacheEntry(expires_at=now + success_ttl, value=value)
        return value

    def _fetch_news(self, symbol: str | None, sector: str | None, lookback_hours: int) -> list[NewsItem]:
        now_local = _now().astimezone(_LOCAL_TZ)
        start_local = now_local - timedelta(hours=lookback_hours)
        if symbol:
            try:
                symbol_profile = self._get_symbol_profile(symbol)
            except ProviderError:
                # `stock_basic` is rate-limited on some free Tushare accounts.
                # Fall back to code-only matching so media news does not hard-fail.
                symbol_profile = {"ts_code": symbol, "name": "", "industry": ""}
        else:
            symbol_profile = None
        events: list[NewsItem] = []
        for src in self._NEWS_SOURCES:
            try:
                frame = self._pro.news(
                    src=src,
                    start_date=start_local.strftime("%Y-%m-%d %H:%M:%S"),
                    end_date=now_local.strftime("%Y-%m-%d %H:%M:%S"),
                    fields="datetime,title,content,channels",
                )
            except Exception as exc:
                raise ProviderError(f"tushare news fetch failed: {exc}") from exc
            if frame is None or frame.empty:
                continue
            for _, row in frame.head(400).iterrows():
                title = str(row.get("title") or "").strip()
                content = str(row.get("content") or "").strip()
                channels = str(row.get("channels") or "").strip()
                if not self._news_matches_scope(symbol, sector, symbol_profile, title, content, channels):
                    continue
                source_name, source_url = self._NEWS_SOURCE_META.get(src, (src, "https://tushare.pro/"))
                published_at = _parse_trade_time(row.get("datetime"))
                events.append(
                    NewsItem(
                        id=f"tushare_news:{src}:{published_at.isoformat()}:{title[:40]}",
                        title=title[:120] or "新闻快讯",
                        summary=(content or title)[:280],
                        source_name=source_name,
                        source_url=source_url,
                        source_tier=SourceTier.COMMERCIAL_MEDIA,
                        published_at=published_at,
                        symbols=[symbol] if symbol else [],
                        sectors=[sector] if sector else ([symbol_profile["industry"]] if symbol_profile and symbol_profile.get("industry") else []),
                        themes=[],
                        event_type="market_news",
                        sentiment="neutral",
                        impact_direction=ImpactDirection.MIXED,
                        impact_magnitude=Magnitude.MEDIUM,
                        confidence=Confidence.MEDIUM,
                    )
                )
        events.sort(key=lambda item: item.published_at, reverse=True)
        return events[:20]

    def _get_symbol_profile(self, symbol: str) -> dict[str, str]:
        cache_key = symbol.upper()
        return self._remember(
            self._profile_cache,
            cache_key,
            timedelta(hours=12),
            lambda: self._fetch_symbol_profile(symbol),
        )

    def _fetch_symbol_profile(self, symbol: str) -> dict[str, str]:
        try:
            frame = self._pro.stock_basic(ts_code=symbol, fields="ts_code,name,industry")
        except Exception as exc:
            raise ProviderError(f"tushare stock_basic failed: {exc}") from exc
        if frame is None or frame.empty:
            return {"ts_code": symbol, "name": _ashare_symbol_code(symbol), "industry": ""}
        row = frame.iloc[0]
        return {
            "ts_code": str(row.get("ts_code") or symbol),
            "name": str(row.get("name") or _ashare_symbol_code(symbol)).strip(),
            "industry": str(row.get("industry") or "").strip(),
        }

    def _news_matches_scope(
        self,
        symbol: str | None,
        sector: str | None,
        symbol_profile: dict[str, str] | None,
        title: str,
        content: str,
        channels: str,
    ) -> bool:
        haystack = " ".join([title, content, channels]).casefold()
        compact_haystack = "".join(haystack.split())
        if symbol:
            candidates = {
                _ashare_symbol_code(symbol),
            }
            if symbol_profile:
                candidates.add(symbol_profile.get("name", "").strip())
            candidates = {candidate for candidate in candidates if candidate}
            for candidate in candidates:
                if candidate.casefold() in haystack or "".join(candidate.casefold().split()) in compact_haystack:
                    return True
        if sector:
            aliases = _sector_aliases(original=sector)
            if any(alias.casefold() in haystack for alias in aliases):
                return True
        if symbol_profile and symbol_profile.get("industry"):
            industry = symbol_profile["industry"].strip()
            if industry and industry.casefold() in haystack:
                return True
        return False

    def _fetch_report(self, symbol: str | None, sector: str | None, lookback_hours: int) -> IntelReport:
        if symbol:
            qa_events = self._fetch_irm_events(symbol, lookback_hours)
        elif sector:
            qa_events = self._fetch_sector_irm_events(sector, lookback_hours)
        else:
            raise ProviderError("symbol or sector is required for Tushare intel provider")

        if not qa_events:
            target = symbol or sector or "market"
            raise ProviderError(f"no Tushare IRM rows returned for {target}")

        summary = IntelSummary(
            top_catalysts=[event.title for event in qa_events[:3]],
            top_risks=["互动问答属于公司口径信息，需与公告和财报交叉验证。"],
        )
        return IntelReport(
            scope={"symbol": symbol, "sector": sector},
            as_of=_now(),
            headline_events=qa_events[:5],
            policy_events=[],
            disclosure_events=qa_events[:5],
            sector_context=IntelSectorContext(
                net_direction=ImpactDirection.NEUTRAL,
                confidence=Confidence.MEDIUM,
            ),
            summary=summary,
        )

    def _fetch_irm_events(self, symbol: str, lookback_hours: int) -> list[NewsItem]:
        now_local = _now().astimezone(_LOCAL_TZ)
        start_local = now_local - timedelta(hours=lookback_hours)
        params = {
            "ts_code": symbol,
            "start_date": start_local.strftime("%Y%m%d"),
            "end_date": now_local.strftime("%Y%m%d"),
        }
        fetcher = self._select_irm_fetcher(symbol)
        try:
            frame = fetcher(**params)
        except Exception as exc:
            raise ProviderError(f"tushare irm fetch failed: {exc}") from exc
        if frame is None or frame.empty:
            return []

        events: list[NewsItem] = []
        for _, row in frame.head(20).iterrows():
            question = str(row.get("q") or "").strip()
            answer = str(row.get("a") or "").strip()
            title = self._build_event_title(question)
            published_at = _parse_trade_time(row.get("pub_time") or row.get("trade_date"))
            events.append(
                NewsItem(
                    id=f"irm:{symbol}:{published_at.isoformat()}",
                    title=title,
                    summary=(answer or question)[:280],
                    source_name="SSE e互动" if symbol.upper().endswith(".SH") else "SZSE 互动易",
                    source_url="https://sns.sseinfo.com/" if symbol.upper().endswith(".SH") else "https://irm.cninfo.com.cn/",
                    source_tier=SourceTier.OFFICIAL,
                    published_at=published_at,
                    symbols=[symbol],
                    sectors=[str(row.get("industry")).strip()] if row.get("industry") else [],
                    themes=self._extract_themes(question, answer),
                    event_type="investor_relations_qa",
                    sentiment="neutral",
                    impact_direction=ImpactDirection.NEUTRAL,
                    impact_magnitude=Magnitude.LOW,
                    confidence=Confidence.MEDIUM,
                )
            )
        return events

    def _fetch_sector_irm_events(self, sector: str, lookback_hours: int) -> list[NewsItem]:
        normalized_sector = sector.strip()
        if not normalized_sector:
            return []

        all_events = [
            *self._fetch_market_irm_events(self._pro.irm_qa_sh, ".SH", lookback_hours),
            *self._fetch_market_irm_events(self._pro.irm_qa_sz, ".SZ", lookback_hours),
        ]
        matches = [event for event in all_events if self._event_matches_sector(event, normalized_sector)]
        matches.sort(key=lambda event: event.published_at, reverse=True)
        return matches[:10]

    def _fetch_market_irm_events(
        self,
        fetcher: Callable[..., Any],
        exchange_suffix: str,
        lookback_hours: int,
    ) -> list[NewsItem]:
        now_local = _now().astimezone(_LOCAL_TZ)
        start_local = now_local - timedelta(hours=lookback_hours)
        try:
            frame = fetcher(
                start_date=start_local.strftime("%Y%m%d"),
                end_date=now_local.strftime("%Y%m%d"),
            )
        except Exception as exc:
            raise ProviderError(f"tushare sector irm fetch failed: {exc}") from exc
        if frame is None or frame.empty:
            return []

        events: list[NewsItem] = []
        for _, row in frame.head(500).iterrows():
            symbol = str(row.get("ts_code") or "").strip()
            if symbol and "." not in symbol:
                symbol = f"{symbol}{exchange_suffix}"
            question = str(row.get("q") or "").strip()
            answer = str(row.get("a") or "").strip()
            published_at = _parse_trade_time(row.get("pub_time") or row.get("trade_date"))
            events.append(
                NewsItem(
                    id=f"irm:{symbol}:{published_at.isoformat()}",
                    title=self._build_event_title(question),
                    summary=(answer or question)[:280],
                    source_name="SSE e互动" if exchange_suffix == ".SH" else "SZSE 互动易",
                    source_url="https://sns.sseinfo.com/" if exchange_suffix == ".SH" else "https://irm.cninfo.com.cn/",
                    source_tier=SourceTier.OFFICIAL,
                    published_at=published_at,
                    symbols=[symbol] if symbol else [],
                    sectors=[str(row.get("industry")).strip()] if row.get("industry") else [],
                    themes=self._extract_themes(question, answer),
                    event_type="investor_relations_qa",
                    sentiment="neutral",
                    impact_direction=ImpactDirection.NEUTRAL,
                    impact_magnitude=Magnitude.LOW,
                    confidence=Confidence.MEDIUM,
                )
            )
        return events

    def _select_irm_fetcher(self, symbol: str) -> Callable[..., Any]:
        normalized = symbol.upper()
        if normalized.endswith(".SH"):
            return self._pro.irm_qa_sh
        if normalized.endswith(".SZ"):
            return self._pro.irm_qa_sz
        raise ProviderError(f"unsupported symbol for Tushare IRM fetch: {symbol}")

    def _build_event_title(self, question: str) -> str:
        compact = " ".join(question.split())
        if not compact:
            return "投资者互动问答"
        return compact[:60]

    def _extract_themes(self, question: str, answer: str) -> list[str]:
        text = f"{question} {answer}".lower()
        mapping = {
            "ai": ["deepseek", "人工智能", "大模型", "ai"],
            "semiconductor": ["芯片", "半导体"],
            "robotics": ["机器人"],
            "data_center": ["数据中心"],
            "new_energy": ["光伏", "储能", "锂电", "新能源"],
        }
        themes = [theme for theme, keywords in mapping.items() if any(keyword.lower() in text for keyword in keywords)]
        return themes

    def _event_matches_sector(self, event: NewsItem, sector: str) -> bool:
        needle = sector.casefold()
        aliases = _sector_aliases(sector_alias_key=needle, original=sector)
        haystacks = [
            event.title,
            event.summary,
            " ".join(event.sectors),
            " ".join(event.themes),
        ]
        haystack = " ".join(haystacks).casefold()
        return any(alias.casefold() in haystack for alias in aliases)


class GovCnPolicyService:
    _INDEX_URL = "https://www.gov.cn/zhengce/index.htm"

    def __init__(self) -> None:
        self._cache: dict[str, CacheEntry] = {}

    def get_policy_events(self, scope_keywords: list[str], lookback_hours: int) -> list[NewsItem]:
        keywords = [keyword.strip() for keyword in scope_keywords if keyword.strip()]
        if not keywords:
            return []

        cache_key = "|".join(sorted({keyword.casefold() for keyword in keywords}))
        now = _now()
        entry = self._cache.get(cache_key)
        if entry and entry.expires_at > now:
            if entry.error:
                raise entry.error
            return entry.value

        try:
            value = self._fetch_policy_events(keywords, lookback_hours)
        except ProviderError as exc:
            self._cache[cache_key] = CacheEntry(
                expires_at=now + timedelta(seconds=settings.tushare_error_ttl_seconds),
                error=exc,
            )
            raise

        self._cache[cache_key] = CacheEntry(
            expires_at=now + timedelta(seconds=settings.gov_policy_ttl_seconds),
            value=value,
        )
        return value

    def _fetch_policy_events(self, scope_keywords: list[str], lookback_hours: int) -> list[NewsItem]:
        try:
            html = urlopen(self._INDEX_URL, timeout=20).read().decode("utf-8", "ignore")
        except Exception as exc:
            raise ProviderError(f"gov.cn policy fetch failed: {exc}") from exc

        latest_section = self._extract_section(html, "最新政策-->", "<!--end 最新政策-->")
        interpretation_section = self._extract_section(html, "<!--政策解读-->", "<!--end 政策解读-->")
        records = [
            *self._parse_policy_list_items(latest_section, "gov_policy_release", with_summary=False),
            *self._parse_policy_list_items(interpretation_section, "gov_policy_interpretation", with_summary=True),
        ]

        cutoff = _now().astimezone(_LOCAL_TZ) - timedelta(hours=lookback_hours)
        keywords = {keyword.casefold() for keyword in scope_keywords}
        events: list[NewsItem] = []
        for record in records:
            published_at = _parse_trade_time(record["date"])
            if published_at < cutoff:
                continue
            haystack = f"{record['title']} {record.get('summary', '')}".casefold()
            if not any(keyword in haystack for keyword in keywords):
                continue
            events.append(
                NewsItem(
                    id=f"govcn:{record['event_type']}:{published_at.isoformat()}:{record['title'][:24]}",
                    title=record["title"],
                    summary=record.get("summary", "")[:280],
                    source_name="中国政府网",
                    source_url=record["url"],
                    source_tier=SourceTier.OFFICIAL,
                    published_at=published_at,
                    symbols=[],
                    sectors=[],
                    themes=[],
                    event_type=record["event_type"],
                    sentiment="neutral",
                    impact_direction=ImpactDirection.MIXED,
                    impact_magnitude=Magnitude.MEDIUM,
                    confidence=Confidence.MEDIUM,
                )
            )
        return events[:6]

    def _extract_section(self, html: str, start_marker: str, end_marker: str) -> str:
        start = html.find(start_marker)
        if start == -1:
            return ""
        end = html.find(end_marker, start)
        if end == -1:
            return html[start:]
        return html[start:end]

    def _parse_policy_list_items(self, html: str, event_type: str, with_summary: bool) -> list[dict[str, str]]:
        records: list[dict[str, str]] = []
        if with_summary:
            pattern = re.compile(
                r'<li>\s*<h5>\s*<a href="(?P<href>[^"]+)"[^>]*>\s*(?P<title>.*?)\s*</a>\s*</h5>\s*'
                r'<p>\s*<a href="[^"]+"[^>]*>\s*(?P<summary>.*?)\s*</a>\s*</p>\s*'
                r'<span>\s*(?P<date>\d{4}-\d{2}-\d{2})\s*</span>',
                re.S,
            )
        else:
            pattern = re.compile(
                r'<li>\s*<a href="(?P<href>[^"]+)"[^>]*>\s*(?P<title>.*?)\s*</a>\s*'
                r'<span>\s*(?P<date>\d{4}-\d{2}-\d{2})\s*</span>\s*</li>',
                re.S,
            )
        for match in pattern.finditer(html):
            data = match.groupdict()
            records.append(
                {
                    "url": urljoin(self._INDEX_URL, data["href"].strip()),
                    "title": _clean_html_text(data["title"]),
                    "summary": _clean_html_text(data.get("summary", "")),
                    "date": data["date"].strip(),
                    "event_type": event_type,
                }
            )
        return records


class CninfoDisclosureService:
    _QUERY_URL = "https://www.cninfo.com.cn/new/hisAnnouncement/query"
    _SEARCH_REFERER = "https://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search"

    def __init__(self) -> None:
        self._cache: dict[str, CacheEntry] = {}

    def get_disclosures(self, symbol: str, lookback_hours: int) -> list[NewsItem]:
        cache_key = f"{symbol}:{lookback_hours}"
        now = _now()
        entry = self._cache.get(cache_key)
        if entry and entry.expires_at > now:
            if entry.error:
                raise entry.error
            return entry.value

        try:
            value = self._fetch_disclosures(symbol, lookback_hours)
        except ProviderError as exc:
            self._cache[cache_key] = CacheEntry(
                expires_at=now + timedelta(seconds=settings.tushare_error_ttl_seconds),
                error=exc,
            )
            raise

        self._cache[cache_key] = CacheEntry(
            expires_at=now + timedelta(seconds=settings.cninfo_disclosure_ttl_seconds),
            value=value,
        )
        return value

    def _fetch_disclosures(self, symbol: str, lookback_hours: int) -> list[NewsItem]:
        code, _exchange = symbol.upper().split(".", 1)
        now_local = _now().astimezone(_LOCAL_TZ)
        start_local = now_local - timedelta(hours=lookback_hours)
        payload = {
            "pageNum": 1,
            "pageSize": 10,
            "column": "sse" if symbol.upper().endswith(".SH") else "szse",
            "tabName": "fulltext",
            "plate": "sh" if symbol.upper().endswith(".SH") else "sz",
            "stock": "",
            "searchkey": code,
            "secid": "",
            "category": "",
            "trade": "",
            "seDate": f"{start_local.strftime('%Y-%m-%d')}~{now_local.strftime('%Y-%m-%d')}",
        }
        request = Request(
            self._QUERY_URL,
            data=urlencode(payload).encode(),
            headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": self._SEARCH_REFERER,
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            },
        )
        try:
            raw = urlopen(request, timeout=20).read().decode("utf-8", "ignore")
        except Exception as exc:
            raise ProviderError(f"cninfo disclosure fetch failed: {exc}") from exc

        try:
            payload = json.loads(raw)
        except Exception as exc:
            raise ProviderError(f"cninfo disclosure parse failed: {exc}") from exc
        rows = payload.get("announcements") or []
        events: list[NewsItem] = []
        for row in rows:
            if str(row.get("secCode") or "") != code:
                continue
            title = _clean_html_text(str(row.get("announcementTitle") or ""))
            if "H股公告" in title:
                continue
            published_at = datetime.fromtimestamp((_float(row.get("announcementTime")) / 1000), tz=_LOCAL_TZ)
            pdf_url = urljoin("https://static.cninfo.com.cn/", str(row.get("adjunctUrl") or "").lstrip("/"))
            events.append(
                NewsItem(
                    id=f"cninfo:{row.get('announcementId')}",
                    title=title,
                    summary=title[:280],
                    source_name="巨潮资讯",
                    source_url=pdf_url,
                    source_tier=SourceTier.OFFICIAL,
                    published_at=published_at,
                    symbols=[symbol],
                    sectors=[],
                    themes=[],
                    event_type="company_disclosure",
                    sentiment="neutral",
                    impact_direction=ImpactDirection.MIXED,
                    impact_magnitude=Magnitude.MEDIUM,
                    confidence=Confidence.HIGH,
                )
            )
        return events[:5]


class SseExchangeDisclosureService:
    _QUERY_URL = "https://query.sse.com.cn/commonSoaQuery.do"
    _REFERER = "https://www.sse.com.cn/disclosure/listedinfo/announcement/"
    _CHANNEL_IDS = "8319,11796,8320,11794,12008,12468"

    def __init__(self) -> None:
        self._cache: dict[str, CacheEntry] = {}

    def get_disclosures(self, symbol: str, lookback_hours: int) -> list[NewsItem]:
        cache_key = f"{symbol}:{lookback_hours}"
        now = _now()
        entry = self._cache.get(cache_key)
        if entry and entry.expires_at > now:
            if entry.error:
                raise entry.error
            return entry.value

        try:
            value = self._fetch_disclosures(symbol, lookback_hours)
        except ProviderError as exc:
            self._cache[cache_key] = CacheEntry(
                expires_at=now + timedelta(seconds=settings.tushare_error_ttl_seconds),
                error=exc,
            )
            raise

        self._cache[cache_key] = CacheEntry(
            expires_at=now + timedelta(seconds=settings.cninfo_disclosure_ttl_seconds),
            value=value,
        )
        return value

    def _fetch_disclosures(self, symbol: str, lookback_hours: int) -> list[NewsItem]:
        target_code = _ashare_symbol_code(symbol)
        cutoff = _now().astimezone(_LOCAL_TZ) - timedelta(hours=lookback_hours)
        events: list[NewsItem] = []
        for page_no in range(1, 4):
            callback = f"jsonpCallback{int(_now().timestamp() * 1000)}{page_no}"
            params = {
                "sqlId": "BS_KCB_GGLL_NEW",
                "siteId": "28",
                "channelId": self._CHANNEL_IDS,
                "createTime": "",
                "createTimeEnd": "",
                "extWTFL": "",
                "extTeacher": "",
                "type": "1",
                "isPagination": "true",
                "pageHelp.pageSize": "100",
                "pageHelp.beginPage": str(page_no),
                "pageHelp.pageCount": "50",
                "pageHelp.pageNo": str(page_no),
                "pageHelp.cacheSize": "1",
                "pageHelp.endPage": "5",
                "jsonCallBack": callback,
            }
            request = Request(
                f"{self._QUERY_URL}?{urlencode(params)}",
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Referer": self._REFERER,
                    "Accept": "*/*",
                },
            )
            try:
                raw = urlopen(request, timeout=20).read().decode("utf-8", "ignore")
            except Exception as exc:
                raise ProviderError(f"sse disclosure fetch failed: {exc}") from exc
            payload = self._parse_jsonp(raw)
            rows = (((payload.get("pageHelp") or {}).get("data")) or [])
            if not rows:
                break
            page_oldest: datetime | None = None
            for row in rows:
                row_code = str(
                    row.get("extZQDM")
                    or row.get("stockcode")
                    or row.get("extSECURITY_CODE")
                    or row.get("extGPDM")
                    or ""
                ).strip()
                if row_code != target_code:
                    continue
                published_at = _parse_trade_time(row.get("createTime") or row.get("cmsOpDate"))
                page_oldest = published_at if page_oldest is None else min(page_oldest, published_at)
                if published_at < cutoff:
                    continue
                doc_url = str(row.get("docURL") or "").strip()
                if doc_url and not doc_url.startswith(("http://", "https://")):
                    doc_url = f"https://{doc_url.lstrip('/')}"
                events.append(
                    NewsItem(
                        id=f"sse:{row.get('docId') or row_code}:{published_at.isoformat()}",
                        title=_clean_html_text(str(row.get("docTitle") or "")),
                        summary=_clean_html_text(str(row.get("extINTRODUCTION") or row.get("docTitle") or ""))[:280],
                        source_name="上海证券交易所",
                        source_url=doc_url or self._REFERER,
                        source_tier=SourceTier.OFFICIAL,
                        published_at=published_at,
                        symbols=[symbol],
                        sectors=[],
                        themes=[],
                        event_type="exchange_disclosure_notice",
                        sentiment="neutral",
                        impact_direction=ImpactDirection.MIXED,
                        impact_magnitude=Magnitude.MEDIUM,
                        confidence=Confidence.HIGH,
                    )
                )
            if page_oldest and page_oldest < cutoff:
                break
        return events[:5]

    def _parse_jsonp(self, raw: str) -> dict[str, Any]:
        match = re.match(r"^[^(]+\((.*)\)\s*$", raw, re.S)
        if not match:
            raise ProviderError("sse disclosure parse failed: unexpected jsonp payload")
        try:
            return json.loads(match.group(1))
        except Exception as exc:
            raise ProviderError(f"sse disclosure parse failed: {exc}") from exc


class SzseExchangeDisclosureService:
    _QUERY_URL = "http://www.szse.cn/api/disc/announcement/detailinfo"
    _REFERER = "http://www.szse.cn/disclosure/listed/notice/index.html"
    _PDF_BASE_URL = "https://disc.static.szse.cn/"

    def __init__(self) -> None:
        self._cache: dict[str, CacheEntry] = {}

    def get_disclosures(self, symbol: str, lookback_hours: int) -> list[NewsItem]:
        cache_key = f"{symbol}:{lookback_hours}"
        now = _now()
        entry = self._cache.get(cache_key)
        if entry and entry.expires_at > now:
            if entry.error:
                raise entry.error
            return entry.value

        try:
            value = self._fetch_disclosures(symbol, lookback_hours)
        except ProviderError as exc:
            self._cache[cache_key] = CacheEntry(
                expires_at=now + timedelta(seconds=settings.tushare_error_ttl_seconds),
                error=exc,
            )
            raise

        self._cache[cache_key] = CacheEntry(
            expires_at=now + timedelta(seconds=settings.cninfo_disclosure_ttl_seconds),
            value=value,
        )
        return value

    def _fetch_disclosures(self, symbol: str, lookback_hours: int) -> list[NewsItem]:
        target_code = _ashare_symbol_code(symbol)
        cutoff = _now().astimezone(_LOCAL_TZ) - timedelta(hours=lookback_hours)
        request = Request(
            f"{self._QUERY_URL}?{urlencode({'plateCode': 'szse', 'pageSize': '100', 'pageNum': '1'})}",
            headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": self._REFERER,
                "Accept": "application/json, text/plain, */*",
            },
        )
        try:
            raw = urlopen(request, timeout=20).read().decode("utf-8", "ignore")
        except Exception as exc:
            raise ProviderError(f"szse disclosure fetch failed: {exc}") from exc
        try:
            payload = json.loads(raw)
        except Exception as exc:
            raise ProviderError(f"szse disclosure parse failed: {exc}") from exc
        rows = payload.get("data") or []
        events: list[NewsItem] = []
        for row in rows:
            if str(row.get("secCode") or "").strip() != target_code:
                continue
            sec_name = str(row.get("secName") or symbol).strip()
            for notice in row.get("announList") or []:
                published_at = _parse_trade_time(notice.get("publishTime"))
                if published_at < cutoff:
                    continue
                pdf_url = urljoin(self._PDF_BASE_URL, str(notice.get("attachPath") or "").lstrip("/"))
                events.append(
                    NewsItem(
                        id=f"szse:{notice.get('annId') or notice.get('id')}",
                        title=_clean_html_text(str(notice.get("title") or "")),
                        summary=_clean_html_text(str(notice.get("title") or ""))[:280],
                        source_name="深圳证券交易所",
                        source_url=pdf_url or self._REFERER,
                        source_tier=SourceTier.OFFICIAL,
                        published_at=published_at,
                        symbols=[symbol],
                        sectors=[],
                        themes=[],
                        event_type="exchange_disclosure_notice",
                        sentiment="neutral",
                        impact_direction=ImpactDirection.MIXED,
                        impact_magnitude=Magnitude.MEDIUM,
                        confidence=Confidence.HIGH,
                    )
                )
        return events[:5]


class IntelService:
    def __init__(self) -> None:
        self._tushare: TushareIntelService | None = None
        self._gov_policy = GovCnPolicyService()
        self._cninfo: CninfoDisclosureService | None = None
        self._sse_disclosure = SseExchangeDisclosureService()
        self._szse_disclosure = SzseExchangeDisclosureService()
        if settings.tushare_token:
            try:
                self._tushare = TushareIntelService(settings.tushare_token)
            except ProviderError:
                self._tushare = None
        self._cninfo = CninfoDisclosureService()

    @property
    def effective_provider(self) -> str:
        if self._tushare and self._cninfo:
            return "tushare_irm+cninfo+gov_cn_policy"
        if self._tushare:
            return "tushare_irm+gov_cn_policy"
        if self._cninfo:
            return "cninfo+gov_cn_policy"
        return "gov_cn_policy"

    def get_news(
        self,
        symbol: str | None,
        sector: str | None,
        lookback_hours: int,
        source_name: str | None = None,
        event_type: str | None = None,
    ) -> list[NewsItem]:
        events: list[NewsItem] = []
        policy_seed_events: list[NewsItem] = []
        if self._tushare and (symbol or sector):
            try:
                report = self._tushare.get_report(symbol, sector, lookback_hours)
            except ProviderError:
                report = None
            if report:
                events.extend(report.headline_events)
                policy_seed_events.extend(report.headline_events)
            try:
                tushare_news = self._tushare.get_news(symbol, sector, lookback_hours)
            except ProviderError:
                tushare_news = []
            if tushare_news:
                events.extend(tushare_news)
        if symbol:
            disclosures = self.get_disclosures(symbol, lookback_hours)
            if disclosures:
                events.extend(disclosures)
                policy_seed_events.extend(disclosures)
        try:
            policy_events = self._gov_policy.get_policy_events(
                self._policy_keywords(symbol, sector, policy_seed_events),
                lookback_hours,
            )
        except ProviderError:
            policy_events = []
        if policy_events:
            events.extend(policy_events)
        deduped = self._dedupe_items(events)
        deduped.sort(key=lambda item: item.published_at, reverse=True)
        return self._filter_news_items(deduped, source_name=source_name, event_type=event_type)

    def get_policy(self, symbol: str | None, sector: str | None, lookback_hours: int) -> list[NewsItem]:
        return self._gov_policy.get_policy_events(
            self._policy_keywords(symbol, sector, []),
            lookback_hours,
        )

    def get_disclosures(self, symbol: str, lookback_hours: int) -> list[NewsItem]:
        events: list[NewsItem] = []
        if self._cninfo:
            try:
                events.extend(self._cninfo.get_disclosures(symbol, lookback_hours))
            except ProviderError:
                pass
        try:
            if symbol.upper().endswith(".SH"):
                events.extend(self._sse_disclosure.get_disclosures(symbol, lookback_hours))
            elif symbol.upper().endswith(".SZ"):
                events.extend(self._szse_disclosure.get_disclosures(symbol, lookback_hours))
        except ProviderError:
            pass
        deduped = self._dedupe_items(events)
        deduped.sort(key=lambda item: item.published_at, reverse=True)
        return deduped[:5]

    def _commercial_media_events(
        self,
        symbol: str | None,
        sector: str | None,
        lookback_hours: int,
    ) -> list[NewsItem]:
        if not self._tushare or not (symbol or sector):
            return []
        try:
            return self._tushare.get_news(symbol, sector, lookback_hours)
        except ProviderError:
            return []

    def _headline_events_with_media(
        self,
        primary_events: list[NewsItem],
        media_events: list[NewsItem],
        limit: int = 5,
    ) -> list[NewsItem]:
        deduped = self._dedupe_items([*primary_events, *media_events])
        ranked = sorted(
            deduped,
            key=lambda event: (
                0 if event.source_tier == SourceTier.OFFICIAL else 1,
                -event.published_at.timestamp(),
            ),
        )
        return ranked[:limit]

    def get_report(self, symbol: str | None, sector: str | None, lookback_hours: int) -> IntelReport:
        if self._tushare and (symbol or sector):
            try:
                report = self._tushare.get_report(symbol, sector, lookback_hours)
                media_events = self._commercial_media_events(symbol, sector, lookback_hours)
                try:
                    policy_events = self._gov_policy.get_policy_events(
                        self._policy_keywords(symbol, sector, report.headline_events),
                        lookback_hours,
                    )
                except ProviderError:
                    policy_events = []
                if policy_events:
                    report.policy_events = policy_events
                    report.summary.top_catalysts = [
                        *report.summary.top_catalysts,
                        *[event.title for event in policy_events[:2]],
                    ][:5]
                if symbol:
                    disclosures = self.get_disclosures(symbol, lookback_hours)
                    if disclosures:
                        report.disclosure_events = disclosures
                if media_events:
                    report.headline_events = self._headline_events_with_media(report.headline_events, media_events)
                return report
            except ProviderError:
                pass
        if sector:
            gov_only = self._gov_only_report(symbol, sector, lookback_hours)
            if gov_only:
                return gov_only
        if symbol:
            official_symbol = self._official_symbol_report(symbol, sector, lookback_hours)
            if official_symbol:
                return official_symbol
        raise ProviderError(
            f"no intelligence data available for symbol={symbol or '-'} sector={sector or '-'}"
        )
        event_time = _now() - timedelta(hours=min(lookback_hours, 4))
        event = NewsItem(
            id="intel_mock_01",
            title="样例政策/公告事件",
            summary="这是 sidecar 骨架返回的示例 intelligence 事件，用于联调 skill。",
            source_name="CSRC",
            source_url="https://www.csrc.gov.cn/",
            source_tier=SourceTier.OFFICIAL,
            published_at=event_time,
            symbols=[symbol] if symbol else [],
            sectors=[sector] if sector else ["broad_market"],
            themes=["capital_market_reform"],
            event_type="policy_release",
            sentiment="positive",
            impact_direction=ImpactDirection.MIXED,
            impact_magnitude=Magnitude.MEDIUM,
            confidence=Confidence.MEDIUM,
        )
        return IntelReport(
            scope={"symbol": symbol, "sector": sector},
            as_of=_now(),
            headline_events=[event],
            policy_events=[event],
            disclosure_events=[],
            sector_context=IntelSectorContext(
                net_direction=ImpactDirection.MIXED,
                confidence=Confidence.MEDIUM,
            ),
            summary=IntelSummary(
                top_catalysts=["政策预期提升", "市场风险偏好回暖"],
                top_risks=["事件仍在发酵", "盘中波动可能放大"],
            ),
        )

    def _gov_only_report(
        self,
        symbol: str | None,
        sector: str | None,
        lookback_hours: int,
    ) -> IntelReport | None:
        try:
            policy_events = self._gov_policy.get_policy_events(
                self._policy_keywords(symbol, sector, []),
                lookback_hours,
            )
        except ProviderError:
            return None
        if not policy_events:
            return None
        media_events = self._commercial_media_events(symbol, sector, lookback_hours)
        headline_events = self._headline_events_with_media(policy_events[:5], media_events)
        top_catalysts = [event.title for event in policy_events[:3]]
        for event in media_events[:2]:
            if len(top_catalysts) >= 5:
                break
            if event.title not in top_catalysts:
                top_catalysts.append(event.title)
        return IntelReport(
            scope={"symbol": symbol, "sector": sector},
            as_of=_now(),
            headline_events=headline_events,
            policy_events=policy_events[:5],
            disclosure_events=[],
            sector_context=IntelSectorContext(
                net_direction=ImpactDirection.MIXED,
                confidence=Confidence.MEDIUM,
            ),
            summary=IntelSummary(
                top_catalysts=top_catalysts,
                top_risks=["当前主要基于官方政策口径，缺少公司公告与互动问答交叉验证。"],
            ),
        )

    def _official_symbol_report(
        self,
        symbol: str,
        sector: str | None,
        lookback_hours: int,
    ) -> IntelReport | None:
        disclosures: list[NewsItem] = []
        disclosures = self.get_disclosures(symbol, lookback_hours)
        policy_events: list[NewsItem] = []
        try:
            policy_events = self._gov_policy.get_policy_events(
                self._policy_keywords(symbol, sector, disclosures),
                lookback_hours,
            )
        except ProviderError:
            policy_events = []
        if not disclosures and not policy_events:
            return None
        lead_events = disclosures or policy_events
        media_events = self._commercial_media_events(symbol, sector, lookback_hours)
        headline_events = self._headline_events_with_media(lead_events[:5], media_events)
        top_catalysts = [event.title for event in [*disclosures[:2], *policy_events[:2]][:4]]
        for event in media_events[:2]:
            if len(top_catalysts) >= 5:
                break
            if event.title not in top_catalysts:
                top_catalysts.append(event.title)
        return IntelReport(
            scope={"symbol": symbol, "sector": sector},
            as_of=_now(),
            headline_events=headline_events,
            policy_events=policy_events[:5],
            disclosure_events=disclosures[:5],
            sector_context=IntelSectorContext(
                net_direction=ImpactDirection.MIXED,
                confidence=Confidence.MEDIUM,
            ),
            summary=IntelSummary(
                top_catalysts=top_catalysts,
                top_risks=["当前缺少互动问答实时口径，主要依赖公告和官方政策。"],
            ),
        )

    def _policy_keywords(
        self,
        symbol: str | None,
        sector: str | None,
        headline_events: list[NewsItem],
    ) -> list[str]:
        keywords: list[str] = []
        if sector:
            keywords.extend(_sector_aliases(original=sector))
        for event in headline_events[:5]:
            for theme in event.themes:
                keywords.extend(_theme_aliases(theme))
        if symbol and not keywords:
            keywords.extend(["科技创新", "新质生产力"])

        seen: set[str] = set()
        deduped: list[str] = []
        for keyword in keywords:
            normalized = keyword.casefold()
            if normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(keyword)
        return deduped

    def _dedupe_items(self, items: list[NewsItem]) -> list[NewsItem]:
        deduped: dict[str, NewsItem] = {}
        for item in sorted(items, key=lambda event: event.published_at, reverse=True):
            deduped.setdefault(item.id, item)
        return list(deduped.values())

    def _filter_news_items(
        self,
        items: list[NewsItem],
        *,
        source_name: str | None,
        event_type: str | None,
    ) -> list[NewsItem]:
        source_name_fold = source_name.casefold() if source_name else None
        event_type_fold = event_type.casefold() if event_type else None
        filtered: list[NewsItem] = []
        for item in items:
            if source_name_fold and item.source_name.casefold() != source_name_fold:
                continue
            if event_type_fold and item.event_type.casefold() != event_type_fold:
                continue
            filtered.append(item)
        return filtered


class IntelEventStore:
    def __init__(self, path_value: str | None = None) -> None:
        self._path = _expanded_path(path_value or settings.intel_event_store_path)
        self._lock = Lock()
        self._events_by_id: dict[str, IntelStoredEvent] = {}
        self._load()

    @property
    def total_events(self) -> int:
        return len(self._events_by_id)

    def ingest_report(
        self,
        report: IntelReport,
        triggered_by: str,
    ) -> tuple[int, int, int, dict[str, int]]:
        now = _now()
        grouped: dict[str, tuple[NewsItem, set[str]]] = {}
        category_counts: dict[str, int] = {}
        for category, items in (
            ("headline", report.headline_events),
            ("policy", report.policy_events),
            ("disclosure", report.disclosure_events),
        ):
            for item in items:
                category_counts[category] = category_counts.get(category, 0) + 1
                key = _event_store_key(item)
                if key not in grouped:
                    grouped[key] = (item, set())
                grouped[key][1].add(category)

        added_count = 0
        updated_count = 0
        with self._lock:
            for key, (item, categories) in grouped.items():
                existing = self._events_by_id.get(key)
                if existing is None:
                    self._events_by_id[key] = IntelStoredEvent(
                        item=item,
                        categories=sorted(categories),
                        stored_at=now,
                        report_as_of=report.as_of,
                        triggered_by=triggered_by,
                    )
                    added_count += 1
                    continue

                merged_categories = sorted({*existing.categories, *categories})
                item_changed = item.model_dump(mode="json") != existing.item.model_dump(mode="json")
                categories_changed = merged_categories != existing.categories
                if item_changed or categories_changed or report.as_of > existing.report_as_of:
                    existing.item = item
                    existing.categories = merged_categories
                    existing.report_as_of = max(existing.report_as_of, report.as_of)
                    existing.stored_at = now
                    existing.triggered_by = triggered_by
                    updated_count += 1
            self._persist_locked()

        return added_count, updated_count, len(grouped), category_counts

    def query(
        self,
        symbol: str | None,
        sector: str | None,
        event_type: str | None,
        source_name: str | None,
        category: str | None,
        lookback_hours: int,
        limit: int,
    ) -> IntelEventsResponse:
        with self._lock:
            events = sorted(
                self._events_by_id.values(),
                key=lambda entry: (entry.item.published_at, entry.stored_at),
                reverse=True,
            )
        cutoff = _now().astimezone(_LOCAL_TZ) - timedelta(hours=lookback_hours)
        filtered: list[IntelStoredEvent] = []
        symbol_upper = symbol.upper() if symbol else None
        sector_fold = sector.casefold() if sector else None
        category_fold = category.casefold() if category else None
        event_type_fold = event_type.casefold() if event_type else None
        source_name_fold = source_name.casefold() if source_name else None

        for entry in events:
            item = entry.item
            if item.published_at < cutoff:
                continue
            if symbol_upper and symbol_upper not in {value.upper() for value in item.symbols}:
                continue
            if sector_fold and sector_fold not in {value.casefold() for value in item.sectors}:
                continue
            if event_type_fold and item.event_type.casefold() != event_type_fold:
                continue
            if source_name_fold and item.source_name.casefold() != source_name_fold:
                continue
            if category_fold and category_fold not in {value.casefold() for value in entry.categories}:
                continue
            filtered.append(entry)

        return IntelEventsResponse(
            scope={"symbol": symbol, "sector": sector},
            filters={
                "event_type": event_type,
                "source_name": source_name,
                "category": category,
                "lookback_hours": lookback_hours,
                "limit": limit,
            },
            total_events=len(events),
            filtered_events=len(filtered),
            events=filtered[:limit],
        )

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            return
        if not isinstance(payload, list):
            return
        for row in payload:
            try:
                record = IntelStoredEvent.model_validate(row)
            except Exception:
                continue
            self._events_by_id[_event_store_key(record.item)] = record

    def _persist_locked(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        serialized = [
            record.model_dump(mode="json")
            for record in sorted(
                self._events_by_id.values(),
                key=lambda entry: (entry.item.published_at, entry.stored_at),
                reverse=True,
            )
        ]
        self._path.write_text(json.dumps(serialized, ensure_ascii=False, indent=2), encoding="utf-8")


class IntelHistoryService:
    def __init__(self, intel: IntelService, store: IntelEventStore | None = None) -> None:
        self.intel = intel
        self.store = store or IntelEventStore()

    def ingest(self, request: IntelIngestRequest) -> IntelIngestResponse:
        if not request.symbol and not request.sector:
            raise ValueError("symbol or sector is required")
        report = self.intel.get_report(request.symbol, request.sector, request.lookback_hours)
        added_count, updated_count, total_events, category_counts = self.store.ingest_report(report, request.triggered_by)
        return IntelIngestResponse(
            ingest_id=f"ingest-{uuid4().hex[:10]}",
            scope={"symbol": request.symbol, "sector": request.sector},
            lookback_hours=request.lookback_hours,
            as_of=report.as_of,
            added_count=added_count,
            updated_count=updated_count,
            total_events=total_events,
            category_counts=category_counts,
        )

    def events(
        self,
        symbol: str | None,
        sector: str | None,
        event_type: str | None,
        source_name: str | None,
        category: str | None,
        lookback_hours: int,
        limit: int,
    ) -> IntelEventsResponse:
        return self.store.query(symbol, sector, event_type, source_name, category, lookback_hours, limit)


class IntelSchedulerService:
    def __init__(self, history: IntelHistoryService) -> None:
        self.history = history
        self._targets_path = _expanded_path(settings.intel_scheduler_targets_path)
        self._enabled = settings.intel_scheduler_enabled
        self._interval_seconds = settings.intel_scheduler_interval_seconds
        self._targets: list[IntelSchedulerTarget] = self._load_targets()
        self._last_run_started_at: datetime | None = None
        self._last_run_finished_at: datetime | None = None
        self._last_error: str | None = None
        self._last_results: list[IntelSchedulerRunResult] = []
        self._task: asyncio.Task[None] | None = None
        self._running = False
        self._lock = Lock()

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def running(self) -> bool:
        return self._running

    def status(self) -> IntelSchedulerStatus:
        with self._lock:
            targets = list(self._targets)
            results = list(self._last_results)
            last_run_started_at = self._last_run_started_at
            last_run_finished_at = self._last_run_finished_at
            last_error = self._last_error
        return IntelSchedulerStatus(
            enabled=self._enabled,
            running=self._running,
            interval_seconds=self._interval_seconds,
            target_count=len(targets),
            total_events=self.history.store.total_events,
            last_run_started_at=last_run_started_at,
            last_run_finished_at=last_run_finished_at,
            last_error=last_error,
            targets=targets,
            last_results=results,
        )

    def upsert_target(self, request: IntelSchedulerTargetRequest) -> IntelSchedulerStatus:
        if not request.symbol and not request.sector:
            raise ValueError("symbol or sector is required")
        target = IntelSchedulerTarget(
            symbol=request.symbol.upper() if request.symbol else None,
            sector=request.sector,
            lookback_hours=request.lookback_hours,
            enabled=request.enabled,
        )
        with self._lock:
            updated = False
            for idx, existing in enumerate(self._targets):
                if existing.symbol == target.symbol and existing.sector == target.sector:
                    self._targets[idx] = target
                    updated = True
                    break
            if not updated:
                self._targets.append(target)
            self._persist_targets_locked()
        return self.status()

    def remove_target(self, symbol: str | None, sector: str | None) -> IntelSchedulerStatus:
        if not symbol and not sector:
            raise ValueError("symbol or sector is required")
        symbol_upper = symbol.upper() if symbol else None
        sector_fold = sector.casefold() if sector else None
        with self._lock:
            self._targets = [
                target
                for target in self._targets
                if not (
                    (symbol_upper and target.symbol == symbol_upper)
                    or (sector_fold and target.sector and target.sector.casefold() == sector_fold)
                )
            ]
            self._persist_targets_locked()
        return self.status()

    def run_once(self) -> IntelSchedulerStatus:
        with self._lock:
            targets = [target for target in self._targets if target.enabled]
            self._last_run_started_at = _now()
            self._last_error = None
        results: list[IntelSchedulerRunResult] = []
        for target in targets:
            try:
                response = self.history.ingest(
                    IntelIngestRequest(
                        symbol=target.symbol,
                        sector=target.sector,
                        lookback_hours=target.lookback_hours,
                        triggered_by="scheduler",
                    )
                )
                results.append(
                    IntelSchedulerRunResult(
                        target=target,
                        added_count=response.added_count,
                        updated_count=response.updated_count,
                        total_events=response.total_events,
                        status="ok",
                    )
                )
            except Exception as exc:
                results.append(
                    IntelSchedulerRunResult(
                        target=target,
                        added_count=0,
                        updated_count=0,
                        total_events=0,
                        status="error",
                        detail=str(exc),
                    )
                )

        with self._lock:
            self._last_run_finished_at = _now()
            self._last_results = results
            failures = [result.detail for result in results if result.status != "ok" and result.detail]
            self._last_error = failures[0] if failures else None
        return self.status()

    async def start(self) -> None:
        if not self._enabled or self._task is not None:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop(), name="ashare-quantd-intel-scheduler")

    async def stop(self) -> None:
        self._running = False
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    async def _run_loop(self) -> None:
        while self._running:
            await asyncio.to_thread(self.run_once)
            await asyncio.sleep(self._interval_seconds)

    def _load_targets(self) -> list[IntelSchedulerTarget]:
        if not self._targets_path.exists():
            return []
        try:
            payload = json.loads(self._targets_path.read_text(encoding="utf-8"))
        except Exception:
            return []
        if not isinstance(payload, list):
            return []
        targets: list[IntelSchedulerTarget] = []
        for row in payload:
            try:
                targets.append(IntelSchedulerTarget.model_validate(row))
            except Exception:
                continue
        return targets

    def _persist_targets_locked(self) -> None:
        self._targets_path.parent.mkdir(parents=True, exist_ok=True)
        payload = [target.model_dump(mode="json") for target in self._targets]
        self._targets_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class WatchlistService:
    def __init__(self, market: MarketProviderFacade, intel: IntelService, indicators: "IndicatorService") -> None:
        self.market = market
        self.intel = intel
        self.indicators = indicators
        self._watchlist_path = _expanded_path(settings.watchlist_path)
        self._alerts_path = _expanded_path(settings.watchlist_alerts_path)
        self._enabled = settings.watchlist_scheduler_enabled
        self._interval_seconds = settings.watchlist_scheduler_interval_seconds
        self._items: list[WatchlistItem] = self._load_items()
        self._alerts: list[WatchlistAlert] = self._load_alerts()
        self._last_results: list[WatchlistScanResult] = []
        self._last_scan_started_at: datetime | None = None
        self._last_scan_finished_at: datetime | None = None
        self._last_error: str | None = None
        self._task: asyncio.Task[None] | None = None
        self._running = False
        self._lock = Lock()

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def running(self) -> bool:
        return self._running

    def watchlist(self) -> WatchlistResponse:
        with self._lock:
            return WatchlistResponse(items=list(self._items))

    def upsert_item(self, request: WatchlistItemRequest) -> WatchlistResponse:
        item = WatchlistItem(
            symbol=request.symbol.upper(),
            sector=request.sector,
            notes=request.notes,
            enabled=request.enabled,
            added_at=_now(),
        )
        with self._lock:
            replaced = False
            for idx, existing in enumerate(self._items):
                if existing.symbol == item.symbol:
                    item.added_at = existing.added_at
                    self._items[idx] = item
                    replaced = True
                    break
            if not replaced:
                self._items.append(item)
            self._persist_items_locked()
            return WatchlistResponse(items=list(self._items))

    def remove_item(self, symbol: str) -> WatchlistResponse:
        symbol_upper = symbol.upper()
        with self._lock:
            self._items = [item for item in self._items if item.symbol != symbol_upper]
            self._persist_items_locked()
            return WatchlistResponse(items=list(self._items))

    def alerts(self, symbol: str | None, status: str | None, limit: int) -> WatchlistAlertsResponse:
        with self._lock:
            alerts = list(self._alerts)
        symbol_upper = symbol.upper() if symbol else None
        status_fold = status.casefold() if status else None
        filtered = [
            alert
            for alert in sorted(alerts, key=lambda item: item.triggered_at, reverse=True)
            if (not symbol_upper or alert.symbol == symbol_upper) and (not status_fold or alert.status.casefold() == status_fold)
        ]
        return WatchlistAlertsResponse(total_alerts=len(filtered), alerts=filtered[:limit])

    def status(self) -> WatchlistStatus:
        with self._lock:
            return WatchlistStatus(
                enabled=self._enabled,
                running=self._running,
                interval_seconds=self._interval_seconds,
                item_count=len(self._items),
                alert_count=len(self._alerts),
                last_scan_started_at=self._last_scan_started_at,
                last_scan_finished_at=self._last_scan_finished_at,
                last_error=self._last_error,
                last_results=list(self._last_results),
            )

    def run_once(self) -> WatchlistStatus:
        with self._lock:
            items = [item for item in self._items if item.enabled]
            self._last_scan_started_at = _now()
            self._last_error = None
        results: list[WatchlistScanResult] = []
        new_alerts: list[WatchlistAlert] = []
        for item in items:
            try:
                generated = self._scan_item(item)
                new_alerts.extend(generated)
                results.append(
                    WatchlistScanResult(
                        symbol=item.symbol,
                        generated_alerts=len(generated),
                        skipped=False,
                    )
                )
            except Exception as exc:
                results.append(
                    WatchlistScanResult(
                        symbol=item.symbol,
                        generated_alerts=0,
                        skipped=True,
                        detail=str(exc),
                    )
                )
        with self._lock:
            for alert in new_alerts:
                if not self._is_duplicate_alert_locked(alert):
                    self._alerts.append(alert)
            self._persist_alerts_locked()
            self._last_results = results
            self._last_scan_finished_at = _now()
            failures = [result.detail for result in results if result.detail]
            self._last_error = failures[0] if failures else None
        return self.status()

    async def start(self) -> None:
        if not self._enabled or self._task is not None:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop(), name="ashare-quantd-watchlist-scheduler")

    async def stop(self) -> None:
        self._running = False
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    async def _run_loop(self) -> None:
        while self._running:
            await asyncio.to_thread(self.run_once)
            await asyncio.sleep(self._interval_seconds)

    def _scan_item(self, item: WatchlistItem) -> list[WatchlistAlert]:
        quote = self.market.get_quote(item.symbol)
        intel = self.intel.get_report(item.symbol, item.sector, 72)
        indicators = self.indicators.get_indicators(item.symbol, "1d", "ma,macd,rsi,boll")
        alerts: list[WatchlistAlert] = []
        latest = indicators.latest

        recent_official_events = [
            event
            for event in [*intel.policy_events, *intel.disclosure_events]
            if (_now() - event.published_at.astimezone(UTC)) <= timedelta(hours=24)
        ]
        negative_events = [event for event in recent_official_events if self._event_keyword_score(event) < 0]
        if negative_events:
            event = negative_events[0]
            alerts.append(
                WatchlistAlert(
                    alert_id=f"alert-{uuid4().hex[:10]}",
                    symbol=item.symbol,
                    sector=item.sector,
                    kind="negative_official_event",
                    severity="high",
                    title=f"{item.symbol} 命中负面官方事件",
                    detail=event.title,
                    source=event.source_name,
                    triggered_at=_now(),
                )
            )

        if abs(quote.change_pct) >= 8.0:
            alerts.append(
                WatchlistAlert(
                    alert_id=f"alert-{uuid4().hex[:10]}",
                    symbol=item.symbol,
                    sector=item.sector,
                    kind="near_limit_move",
                    severity="high",
                    title=f"{item.symbol} 接近涨跌停波动",
                    detail=f"最新涨跌幅 {quote.change_pct:.2f}%",
                    source=quote.source,
                    triggered_at=_now(),
                )
            )

        if quote.last > latest.get("ma20", 0.0) > 0 and latest.get("macd_hist", 0.0) > 0:
            alerts.append(
                WatchlistAlert(
                    alert_id=f"alert-{uuid4().hex[:10]}",
                    symbol=item.symbol,
                    sector=item.sector,
                    kind="bullish_breakout_watch",
                    severity="medium",
                    title=f"{item.symbol} 站上 MA20 且 MACD 转正",
                    detail=(
                        f"last={quote.last:.2f}, ma20={latest.get('ma20', 0.0):.2f}, "
                        f"macd_hist={latest.get('macd_hist', 0.0):.3f}"
                    ),
                    source="market+indicators",
                    triggered_at=_now(),
                )
            )

        if latest.get("rsi14", 50.0) <= 22.0:
            alerts.append(
                WatchlistAlert(
                    alert_id=f"alert-{uuid4().hex[:10]}",
                    symbol=item.symbol,
                    sector=item.sector,
                    kind="oversold_rebound_watch",
                    severity="medium",
                    title=f"{item.symbol} 进入超卖观察区",
                    detail=f"rsi14={latest.get('rsi14', 0.0):.2f}",
                    source="indicators",
                    triggered_at=_now(),
                )
            )

        return alerts

    def _event_keyword_score(self, event: NewsItem) -> int:
        positive_terms = ["合作", "快报", "增长", "创新", "升级", "意见", "实施", "推进", "批复", "签署"]
        negative_terms = ["风险", "问询", "减持", "诉讼", "处罚", "质押", "延期", "下滑", "亏损", "监管"]
        text = f"{event.title} {event.summary}"
        score = 0
        if any(term in text for term in positive_terms):
            score += 1
        if any(term in text for term in negative_terms):
            score -= 1
        return score

    def _is_duplicate_alert_locked(self, alert: WatchlistAlert) -> bool:
        cutoff = alert.triggered_at - timedelta(hours=6)
        for existing in self._alerts:
            if (
                existing.symbol == alert.symbol
                and existing.kind == alert.kind
                and existing.detail == alert.detail
                and existing.triggered_at >= cutoff
            ):
                return True
        return False

    def _load_items(self) -> list[WatchlistItem]:
        if not self._watchlist_path.exists():
            return []
        try:
            payload = json.loads(self._watchlist_path.read_text(encoding="utf-8"))
        except Exception:
            return []
        if not isinstance(payload, list):
            return []
        items: list[WatchlistItem] = []
        for row in payload:
            try:
                items.append(WatchlistItem.model_validate(row))
            except Exception:
                continue
        return items

    def _load_alerts(self) -> list[WatchlistAlert]:
        if not self._alerts_path.exists():
            return []
        try:
            payload = json.loads(self._alerts_path.read_text(encoding="utf-8"))
        except Exception:
            return []
        if not isinstance(payload, list):
            return []
        alerts: list[WatchlistAlert] = []
        for row in payload:
            try:
                alerts.append(WatchlistAlert.model_validate(row))
            except Exception:
                continue
        return alerts

    def _persist_items_locked(self) -> None:
        self._watchlist_path.parent.mkdir(parents=True, exist_ok=True)
        payload = [item.model_dump(mode="json") for item in self._items]
        self._watchlist_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _persist_alerts_locked(self) -> None:
        self._alerts_path.parent.mkdir(parents=True, exist_ok=True)
        payload = [alert.model_dump(mode="json") for alert in sorted(self._alerts, key=lambda item: item.triggered_at, reverse=True)]
        self._alerts_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class BrokerDaemonClient:
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout_seconds: int | None = None,
        adapter_name: str | None = None,
    ) -> None:
        self.base_url = (base_url or settings.broker_daemon_base_url or "").rstrip("/")
        self.api_key = api_key or settings.broker_daemon_api_key
        self.timeout_seconds = timeout_seconds or settings.broker_daemon_timeout_seconds
        self.adapter_name = adapter_name or settings.broker_daemon_adapter

    @property
    def configured(self) -> bool:
        return bool(self.base_url)

    def status(self) -> dict[str, Any]:
        return self._request("GET", "/status")

    def submit_order(self, request: BrokerOrderRequest) -> BrokerOrderResponse:
        payload = request.model_dump(mode="json")
        payload["adapter"] = self.adapter_name
        response = self._request("POST", "/orders", payload)
        return BrokerOrderResponse.model_validate(response)

    def cancel_order(self, request: BrokerCancelRequest) -> BrokerCancelResponse:
        payload = request.model_dump(mode="json")
        payload["adapter"] = self.adapter_name
        response = self._request("POST", "/orders/cancel", payload)
        return BrokerCancelResponse.model_validate(response)

    def orders(self, account_id: str) -> BrokerOrdersResponse:
        response = self._request("GET", "/orders", {"account_id": account_id, "adapter": self.adapter_name})
        return BrokerOrdersResponse.model_validate(response)

    def positions(self, account_id: str) -> BrokerPositionsResponse:
        response = self._request("GET", "/positions", {"account_id": account_id, "adapter": self.adapter_name})
        return BrokerPositionsResponse.model_validate(response)

    def account(self, account_id: str) -> BrokerAccountSummary:
        response = self._request("GET", "/account", {"account_id": account_id, "adapter": self.adapter_name})
        return BrokerAccountSummary.model_validate(response)

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.configured:
            raise ProviderError("broker daemon not configured")
        headers = {
            "Accept": "application/json",
            "User-Agent": "ashare-quantd/0.1",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if method == "GET":
            url = f"{self.base_url}{path}"
            if payload:
                url = f"{url}?{urlencode(payload)}"
            request = Request(url, headers=headers, method="GET")
        else:
            headers["Content-Type"] = "application/json"
            body = json.dumps(payload or {}, ensure_ascii=False).encode("utf-8")
            request = Request(f"{self.base_url}{path}", data=body, headers=headers, method=method)
        try:
            raw = urlopen(request, timeout=self.timeout_seconds).read().decode("utf-8", "ignore")
        except Exception as exc:
            raise ProviderError(f"broker daemon request failed: {exc}") from exc
        try:
            return json.loads(raw)
        except Exception as exc:
            raise ProviderError(f"broker daemon returned invalid json: {exc}") from exc


class BrokerAdapterService:
    def __init__(
        self,
        market: MarketProviderFacade,
        risk: "RiskService",
        paper: "PaperTradingService",
        daemon: BrokerDaemonClient | None = None,
    ) -> None:
        self.market = market
        self.risk = risk
        self.paper = paper
        self.daemon = daemon or BrokerDaemonClient()
        self._state_path = _expanded_path(settings.broker_state_path)
        self._lock = Lock()
        self._last_submission_at: datetime | None = None
        self._last_error: str | None = None
        self._kill_switch = self._load_state()

    def status(self) -> BrokerStatusResponse:
        daemon_status: str | None = None
        if self.daemon.configured:
            try:
                daemon_payload = self.daemon.status()
                daemon_status = str(daemon_payload.get("status") or "ok")
            except ProviderError as exc:
                daemon_status = f"error:{exc}"
        return BrokerStatusResponse(
            adapter_mode=settings.broker_adapter,
            live_enabled=settings.broker_live_enabled,
            dry_run_only=(settings.broker_adapter == "dry_run"),
            daemon_configured=self.daemon.configured,
            daemon_base_url=self.daemon.base_url or None,
            daemon_adapter=self.daemon.adapter_name,
            daemon_status=daemon_status,
            kill_switch=self._kill_switch,
            capabilities=self._capabilities(),
            last_submission_at=self._last_submission_at,
            last_error=self._last_error,
        )

    def set_kill_switch(self, request: BrokerKillSwitchRequest) -> BrokerStatusResponse:
        with self._lock:
            self._kill_switch = BrokerKillSwitchState(
                active=request.active,
                reason=request.reason or ("manually_enabled" if request.active else "manually_disabled"),
                updated_at=_now(),
            )
            self._persist_state_locked()
        return self.status()

    def submit_order(self, request: BrokerOrderRequest) -> BrokerOrderResponse:
        submitted_at = _now()
        broker_order_id = f"broker_ord_{uuid4().hex[:10]}"
        if self._kill_switch.active:
            self._last_error = "broker_kill_switch_active"
            return BrokerOrderResponse(
                broker_order_id=broker_order_id,
                adapter_mode=settings.broker_adapter,
                dry_run=(settings.broker_adapter == "dry_run"),
                status="rejected",
                submitted_at=submitted_at,
                approval_required=True,
                risk_status="skipped",
                detail="broker_kill_switch_active",
            )

        if settings.broker_adapter == "disabled":
            self._last_error = "broker_adapter_disabled"
            return BrokerOrderResponse(
                broker_order_id=broker_order_id,
                adapter_mode=settings.broker_adapter,
                dry_run=False,
                status="rejected",
                submitted_at=submitted_at,
                approval_required=True,
                risk_status="skipped",
                detail="broker_adapter_disabled",
            )
        if settings.broker_adapter == "qmt_bridge" and not settings.broker_live_enabled:
            self._last_error = "broker_live_disabled"
            return BrokerOrderResponse(
                broker_order_id=broker_order_id,
                adapter_mode=settings.broker_adapter,
                dry_run=False,
                status="rejected",
                submitted_at=submitted_at,
                approval_required=True,
                risk_status="skipped",
                detail="broker_live_disabled",
            )

        risk_result = self.risk.check(request)
        if risk_result.approval_required and not (request.approval_token or "").strip():
            self._last_error = "approval_token_required"
            return BrokerOrderResponse(
                broker_order_id=broker_order_id,
                adapter_mode=settings.broker_adapter,
                dry_run=(settings.broker_adapter == "dry_run"),
                status="rejected",
                submitted_at=submitted_at,
                approval_required=True,
                risk_status=risk_result.status,
                detail="approval_token_required",
            )

        quote = self.market.get_quote(request.symbol)
        if quote.trading_status != TradingStatus.TRADING and settings.broker_adapter == "paper_bridge":
            self._last_error = "market_not_trading"
            return BrokerOrderResponse(
                broker_order_id=broker_order_id,
                adapter_mode=settings.broker_adapter,
                dry_run=False,
                status="rejected",
                submitted_at=submitted_at,
                approval_required=risk_result.approval_required,
                risk_status=risk_result.status,
                detail="market_not_trading",
            )

        self._last_submission_at = submitted_at
        self._last_error = None
        if settings.broker_adapter == "dry_run":
            return BrokerOrderResponse(
                broker_order_id=broker_order_id,
                adapter_mode="dry_run",
                dry_run=True,
                status="accepted_dry_run",
                submitted_at=submitted_at,
                approval_required=risk_result.approval_required,
                risk_status=risk_result.status,
                detail="broker_dry_run_only",
            )
        if settings.broker_adapter == "qmt_bridge":
            try:
                daemon_response = self.daemon.submit_order(request)
            except ProviderError as exc:
                self._last_error = str(exc)
                return BrokerOrderResponse(
                    broker_order_id=broker_order_id,
                    adapter_mode="qmt_bridge",
                    dry_run=False,
                    status="rejected",
                    submitted_at=submitted_at,
                    approval_required=risk_result.approval_required,
                    risk_status=risk_result.status,
                    detail=str(exc),
                )
            self._last_error = None
            if not daemon_response.broker_order_id:
                daemon_response.broker_order_id = broker_order_id
            return daemon_response

        paper_result = self.paper.submit_order(request)
        return BrokerOrderResponse(
            broker_order_id=broker_order_id,
            adapter_mode="paper_bridge",
            dry_run=False,
            status="accepted" if not paper_result.status.startswith("rejected") else "rejected",
            submitted_at=submitted_at,
            approval_required=risk_result.approval_required,
            risk_status=risk_result.status,
            routed_order_id=paper_result.order_id,
            fill_price=paper_result.fill_price,
            fill_quantity=paper_result.fill_quantity,
            detail=paper_result.detail or paper_result.status,
        )

    def cancel_order(self, request: BrokerCancelRequest) -> BrokerCancelResponse:
        canceled_at = _now()
        if self._kill_switch.active:
            self._last_error = "broker_kill_switch_active"
            return BrokerCancelResponse(
                broker_order_id=request.broker_order_id,
                adapter_mode=settings.broker_adapter,
                dry_run=(settings.broker_adapter == "dry_run"),
                status="rejected",
                canceled_at=canceled_at,
                approval_required=True,
                detail="broker_kill_switch_active",
            )
        if settings.broker_adapter in {"disabled", "paper_bridge"}:
            detail = "cancel_not_supported_for_adapter"
            self._last_error = detail
            return BrokerCancelResponse(
                broker_order_id=request.broker_order_id,
                adapter_mode=settings.broker_adapter,
                dry_run=False,
                status="rejected",
                canceled_at=canceled_at,
                approval_required=False,
                detail=detail,
            )
        if settings.broker_adapter == "dry_run":
            self._last_error = None
            return BrokerCancelResponse(
                broker_order_id=request.broker_order_id,
                adapter_mode="dry_run",
                dry_run=True,
                status="accepted_dry_run",
                canceled_at=canceled_at,
                approval_required=False,
                detail="broker_dry_run_only",
            )
        if not settings.broker_live_enabled:
            self._last_error = "broker_live_disabled"
            return BrokerCancelResponse(
                broker_order_id=request.broker_order_id,
                adapter_mode=settings.broker_adapter,
                dry_run=False,
                status="rejected",
                canceled_at=canceled_at,
                approval_required=True,
                detail="broker_live_disabled",
            )
        try:
            response = self.daemon.cancel_order(request)
        except ProviderError as exc:
            self._last_error = str(exc)
            return BrokerCancelResponse(
                broker_order_id=request.broker_order_id,
                adapter_mode=settings.broker_adapter,
                dry_run=False,
                status="rejected",
                canceled_at=canceled_at,
                approval_required=False,
                detail=str(exc),
            )
        self._last_error = None
        return response

    def orders(self, account_id: str) -> BrokerOrdersResponse:
        if settings.broker_adapter == "paper_bridge":
            paper_orders = self.paper.orders(account_id)
            orders = [
                BrokerOrderRecord(
                    broker_order_id=order.order_id,
                    account_id=order.account_id,
                    symbol=order.symbol,
                    side=order.side,
                    order_type=order.order_type,
                    price=order.price,
                    quantity=order.quantity,
                    status=order.status,
                    submitted_at=order.submitted_at,
                    routed_order_id=order.order_id,
                    fill_price=order.fill_price,
                    fill_quantity=order.fill_quantity,
                    detail=order.detail,
                )
                for order in paper_orders.orders
            ]
            return BrokerOrdersResponse(account_id=account_id, adapter_mode="paper_bridge", status="ok", orders=orders)
        if settings.broker_adapter == "dry_run":
            return BrokerOrdersResponse(
                account_id=account_id,
                adapter_mode="dry_run",
                status="ok",
                detail="dry_run_has_no_live_order_book",
                orders=[],
            )
        if settings.broker_adapter == "disabled":
            return BrokerOrdersResponse(
                account_id=account_id,
                adapter_mode="disabled",
                status="disabled",
                detail="broker_adapter_disabled",
                orders=[],
            )
        try:
            return self.daemon.orders(account_id)
        except ProviderError as exc:
            self._last_error = str(exc)
            return BrokerOrdersResponse(
                account_id=account_id,
                adapter_mode=settings.broker_adapter,
                status="error",
                detail=str(exc),
                orders=[],
            )

    def positions(self, account_id: str) -> BrokerPositionsResponse:
        if settings.broker_adapter == "paper_bridge":
            paper_positions = self.paper.positions(account_id)
            positions = [
                BrokerPosition(
                    account_id=position.account_id,
                    symbol=position.symbol,
                    quantity=position.quantity,
                    avg_cost=position.avg_cost,
                    last_price=position.last_price,
                    market_value=position.market_value,
                    unrealized_pnl=position.unrealized_pnl,
                    unrealized_pnl_pct=position.unrealized_pnl_pct,
                    updated_at=position.updated_at,
                )
                for position in paper_positions.positions
            ]
            return BrokerPositionsResponse(account_id=account_id, adapter_mode="paper_bridge", status="ok", positions=positions)
        if settings.broker_adapter == "dry_run":
            return BrokerPositionsResponse(
                account_id=account_id,
                adapter_mode="dry_run",
                status="ok",
                detail="dry_run_has_no_live_positions",
                positions=[],
            )
        if settings.broker_adapter == "disabled":
            return BrokerPositionsResponse(
                account_id=account_id,
                adapter_mode="disabled",
                status="disabled",
                detail="broker_adapter_disabled",
                positions=[],
            )
        try:
            return self.daemon.positions(account_id)
        except ProviderError as exc:
            self._last_error = str(exc)
            return BrokerPositionsResponse(
                account_id=account_id,
                adapter_mode=settings.broker_adapter,
                status="error",
                detail=str(exc),
                positions=[],
            )

    def account(self, account_id: str) -> BrokerAccountSummary:
        if settings.broker_adapter == "paper_bridge":
            paper_account = self.paper.account_summary(account_id)
            return BrokerAccountSummary(
                account_id=account_id,
                adapter_mode="paper_bridge",
                status="ok",
                cash=paper_account.cash,
                available_cash=paper_account.cash,
                market_value=paper_account.market_value,
                equity=paper_account.equity,
                positions_count=paper_account.positions_count,
                updated_at=paper_account.updated_at,
            )
        if settings.broker_adapter == "dry_run":
            now = _now()
            return BrokerAccountSummary(
                account_id=account_id,
                adapter_mode="dry_run",
                status="ok",
                cash=0.0,
                available_cash=0.0,
                market_value=0.0,
                equity=0.0,
                positions_count=0,
                updated_at=now,
                detail="dry_run_has_no_live_account",
            )
        if settings.broker_adapter == "disabled":
            now = _now()
            return BrokerAccountSummary(
                account_id=account_id,
                adapter_mode="disabled",
                status="disabled",
                cash=0.0,
                available_cash=0.0,
                market_value=0.0,
                equity=0.0,
                positions_count=0,
                updated_at=now,
                detail="broker_adapter_disabled",
            )
        try:
            return self.daemon.account(account_id)
        except ProviderError as exc:
            self._last_error = str(exc)
            now = _now()
            return BrokerAccountSummary(
                account_id=account_id,
                adapter_mode=settings.broker_adapter,
                status="error",
                cash=0.0,
                available_cash=0.0,
                market_value=0.0,
                equity=0.0,
                positions_count=0,
                updated_at=now,
                detail=str(exc),
            )

    def _capabilities(self) -> list[str]:
        if settings.broker_adapter == "disabled":
            return ["status", "kill_switch"]
        if settings.broker_adapter == "dry_run":
            return ["status", "kill_switch", "dry_run_submit", "cancel", "orders", "positions", "account", "risk_gate"]
        if settings.broker_adapter == "paper_bridge":
            return ["status", "kill_switch", "paper_bridge_submit", "orders", "positions", "account", "risk_gate"]
        if settings.broker_adapter == "qmt_bridge":
            return ["status", "kill_switch", "daemon_submit", "cancel", "orders", "positions", "account", "risk_gate"]
        return ["status", "kill_switch"]

    def _load_state(self) -> BrokerKillSwitchState:
        if not self._state_path.exists():
            return BrokerKillSwitchState(active=True, reason="default_safe_mode", updated_at=_now())
        try:
            payload = json.loads(self._state_path.read_text(encoding="utf-8"))
            return BrokerKillSwitchState.model_validate(payload)
        except Exception:
            return BrokerKillSwitchState(active=True, reason="state_read_failed", updated_at=_now())

    def _persist_state_locked(self) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state_path.write_text(
            json.dumps(self._kill_switch.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


class IndicatorService:
    def __init__(self, market: MarketProviderFacade) -> None:
        self.market = market

    def get_indicators(self, symbol: str, interval: str, sets: str) -> Indicators:
        bars = self.market.get_bars(symbol, interval, 120).bars
        closes = [bar.close for bar in bars]
        volumes = [float(bar.volume) for bar in bars]
        ema12 = _ema_series(closes, 12)
        ema26 = _ema_series(closes, 26)
        macd_line = (ema12[-1] - ema26[-1]) if ema12 and ema26 else 0.0
        macd_series = [fast - slow for fast, slow in zip(ema12[-len(ema26):], ema26)] if ema26 else []
        macd_signal_series = _ema_series(macd_series, 9)
        macd_signal = macd_signal_series[-1] if macd_signal_series else 0.0
        std20 = _stddev(closes[-20:]) if len(closes) >= 20 else 0.0
        latest = {
            "close": closes[-1] if closes else 0.0,
            "ma5": _sma(closes, 5),
            "ma10": _sma(closes, 10),
            "ma20": _sma(closes, 20),
            "ma60": _sma(closes, 60),
            "vol_ma5": _sma(volumes, 5),
            "vol_ma20": _sma(volumes, 20),
            "macd": macd_line,
            "macd_signal": macd_signal,
            "macd_hist": macd_line - macd_signal,
            "rsi14": _rsi(closes, 14),
            "boll_upper": _sma(closes, 20) + 2 * std20 if len(closes) >= 20 else 0.0,
            "boll_mid": _sma(closes, 20),
            "boll_lower": _sma(closes, 20) - 2 * std20 if len(closes) >= 20 else 0.0,
            "atr_pct": _atr_percent(bars, 14),
        }
        return Indicators(symbol=symbol, interval=interval, latest=latest)


class AdviceService:
    def __init__(self, market: MarketProviderFacade, intel: IntelService, indicators: IndicatorService) -> None:
        self.market = market
        self.intel = intel
        self.indicators = indicators

    def generate(self, request: AdviceRequest) -> AdviceResponse:
        quote = self.market.get_quote(request.symbol)
        bars_response = self.market.get_bars(request.symbol, "1d", 120)
        indicators = self.indicators.get_indicators(request.symbol, "1d", "ma,macd,rsi,boll")
        intel = self.intel.get_report(request.symbol, None, 72)
        (
            _max_position_pct,
            stop_loss_pct,
            take_profit_pct,
            commission_bps,
            lot_size,
            min_hold_days,
            max_open_positions,
            fee_drag_warn_ratio,
            reward_risk_tight_ratio,
            reward_risk_thin_ratio,
            execution_config_source,
        ) = _resolve_execution_values(request.execution, 1)
        catalyst_events = self._catalyst_events(intel)
        catalysts = [
            Catalyst(
                title=item.title,
                source_tier=item.source_tier,
                published_at=item.published_at,
            )
            for item in catalyst_events[:2]
        ]
        latest = indicators.latest
        closes = [bar.close for bar in bars_response.bars]
        returns = [
            ((current / previous) - 1) if previous else 0.0
            for previous, current in zip(closes[:-1], closes[1:])
        ]
        volatility_pct = _stddev(returns[-20:]) * 100 if returns else 0.0
        latest_volume = float(bars_response.bars[-1].volume) if bars_response.bars else 0.0
        vol_ma20 = latest.get("vol_ma20", 0.0)

        trend_state = self._trend_state(latest)
        volume_state = self._volume_state(latest_volume, vol_ma20)
        volatility_state = self._volatility_state(volatility_pct)
        intel_bias, intel_flags = self._intel_bias(intel)
        action, confidence, thesis = self._decide_action(
            trend_state,
            latest,
            intel_bias,
            request.time_horizon,
        )
        risk_flags = self._risk_flags(quote, latest, intel, volatility_pct)
        risk_flags.extend(intel_flags)
        risk_flags = list(dict.fromkeys(risk_flags))

        atr_pct = latest.get("atr_pct", 0.02) or 0.02
        entry_low = round(quote.last * (1 - min(atr_pct * 0.5, 0.03)), 2)
        entry_high = round(quote.last * (1 + min(atr_pct * 0.2, 0.015)), 2)
        effective_stop_loss_pct = max(stop_loss_pct, max(atr_pct * 1.2, 0.03))
        effective_take_profit_pct = max(take_profit_pct, max(atr_pct * 2.0, 0.05))
        stop_loss = round(quote.last * (1 - effective_stop_loss_pct), 2)
        target_low = round(quote.last * (1 + max(effective_take_profit_pct * 0.6, 0.03)), 2)
        target_high = round(quote.last * (1 + effective_take_profit_pct), 2)
        suggested_position_value, suggested_quantity, estimated_entry_fee = self._execution_trade_plan(
            quote.last,
            request.account_equity,
            request.available_cash,
            _max_position_pct,
            commission_bps,
            lot_size,
        )
        if request.account_equity and suggested_quantity == 0:
            risk_flags.append("insufficient_budget_for_board_lot")
            risk_flags = list(dict.fromkeys(risk_flags))
        action, confidence, thesis, execution_flags = self._apply_execution_constraints(
            action=action,
            confidence=confidence,
            thesis=thesis,
            price=quote.last,
            stop_loss=stop_loss,
            target_low=target_low,
            suggested_position_value=suggested_position_value,
            suggested_quantity=suggested_quantity,
            commission_bps=commission_bps,
            lot_size=lot_size,
            account_equity=request.account_equity,
            fee_drag_warn_ratio=fee_drag_warn_ratio,
            reward_risk_tight_ratio=reward_risk_tight_ratio,
            reward_risk_thin_ratio=reward_risk_thin_ratio,
        )
        risk_flags.extend(execution_flags)
        risk_flags = list(dict.fromkeys(risk_flags))
        actionability = self._actionability(action, risk_flags, confidence)

        return AdviceResponse(
            symbol=request.symbol,
            action=action,
            confidence=confidence,
            thesis=thesis,
            market_state={
                "trend": trend_state,
                "volume_state": volume_state,
                "volatility_state": volatility_state,
                "quote_source": quote.source,
                "intel_provider": self.intel.effective_provider,
                "market_time": quote.market_time.isoformat(),
            },
            catalysts=catalysts,
            trade_plan=TradePlan(
                entry_zone=[entry_low, entry_high],
                stop_loss=stop_loss,
                target_zone=[target_low, target_high],
                time_horizon=request.time_horizon,
                suggested_position_value=suggested_position_value,
                suggested_quantity=suggested_quantity,
                estimated_entry_fee=estimated_entry_fee,
            ),
            risk_flags=risk_flags,
            actionability=actionability,
            strategy_meta=_strategy_meta(
                request.strategy_id,
                _EXECUTION_RULE_VERSION,
                execution_config_source,
                _INTEL_LIVE_VERSION,
                self.intel.effective_provider,
            ),
            strategy_version=_strategy_version(request.strategy_id, _EXECUTION_RULE_VERSION, _INTEL_LIVE_VERSION),
            execution_rule_version=_EXECUTION_RULE_VERSION,
            execution_config_source=execution_config_source,
            execution_params=_execution_params_map(
                _max_position_pct,
                stop_loss_pct,
                take_profit_pct,
                commission_bps,
                lot_size,
                min_hold_days,
                max_open_positions,
                fee_drag_warn_ratio,
                reward_risk_tight_ratio,
                reward_risk_thin_ratio,
            ),
        )

    def _trend_state(self, latest: dict[str, float]) -> str:
        close = latest.get("close", 0.0)
        ma5 = latest.get("ma5", 0.0)
        ma10 = latest.get("ma10", 0.0)
        ma20 = latest.get("ma20", 0.0)
        if close > ma20 and ma5 >= ma10 >= ma20:
            return "up"
        if close < ma20 and ma5 <= ma10 <= ma20:
            return "down"
        return "sideways"

    def _volume_state(self, latest_volume: float, vol_ma20: float) -> str:
        if not vol_ma20:
            return "normal"
        ratio = latest_volume / vol_ma20
        if ratio >= 1.5:
            return "expanding"
        if ratio <= 0.7:
            return "light"
        return "normal"

    def _volatility_state(self, volatility_pct: float) -> str:
        if volatility_pct >= 3.0:
            return "high"
        if volatility_pct >= 1.5:
            return "medium"
        return "low"

    def _catalyst_events(self, intel: IntelReport) -> list[NewsItem]:
        events: list[NewsItem] = []
        seen: set[str] = set()
        for group in (
            intel.policy_events,
            intel.disclosure_events,
            [event for event in intel.headline_events if event.source_tier == SourceTier.OFFICIAL],
            [event for event in intel.headline_events if event.source_tier == SourceTier.COMMERCIAL_MEDIA],
        ):
            for event in group:
                if event.id in seen:
                    continue
                seen.add(event.id)
                events.append(event)
                if len(events) >= 2:
                    return events
        return events

    def _unique_events(self, intel: IntelReport) -> list[NewsItem]:
        deduped: dict[str, NewsItem] = {}
        for event in [*intel.policy_events, *intel.disclosure_events, *intel.headline_events]:
            deduped.setdefault(event.id, event)
        return list(deduped.values())

    def _intel_bias(self, intel: IntelReport) -> tuple[float, list[str]]:
        score = 0.0
        media_score = 0.0
        flags: list[str] = []
        events = self._unique_events(intel)
        for event in events[:8]:
            event_score = _event_keyword_score(event)
            if event.source_tier == SourceTier.COMMERCIAL_MEDIA:
                media_score += event_score * 0.35
                if event_score > 0:
                    flags.append("media_headline_support")
                elif event_score < 0:
                    flags.append("negative_media_flow")
                continue
            score += event_score
            if event.source_name == "中国政府网":
                flags.append("official_policy_driver")
            if event.source_name == "巨潮资讯":
                flags.append("recent_disclosure")
        score += max(-1.0, min(1.0, media_score))
        return score, flags

    def _decide_action(
        self,
        trend_state: str,
        latest: dict[str, float],
        intel_bias: float,
        time_horizon: str,
    ) -> tuple[AdviceAction, float, str]:
        rsi14 = latest.get("rsi14", 50.0)
        macd_hist = latest.get("macd_hist", 0.0)
        close = latest.get("close", 0.0)
        ma20 = latest.get("ma20", close)
        score = 0
        if trend_state == "up":
            score += 2
        elif trend_state == "down":
            score -= 2
        if macd_hist > 0:
            score += 1
        else:
            score -= 1
        if 45 <= rsi14 <= 68:
            score += 1
        elif rsi14 >= 75:
            score -= 1
        if close > ma20:
            score += 1
        else:
            score -= 1
        score += max(-2.0, min(2.0, intel_bias))

        if score >= 4:
            action = AdviceAction.BUY_CANDIDATE
        elif score >= 2:
            action = AdviceAction.BUY_WATCH
        elif score <= -4:
            action = AdviceAction.AVOID
        elif score <= -2:
            action = AdviceAction.SELL_WATCH
        else:
            action = AdviceAction.HOLD

        # Oversold names with positive official/disclosure catalysts are more often "wait for confirmation"
        # than immediate sell candidates in A-share swing workflows.
        if trend_state == "down" and rsi14 <= 20 and intel_bias >= 1 and action == AdviceAction.SELL_WATCH:
            action = AdviceAction.HOLD

        confidence = max(0.35, min(0.84, 0.5 + score * 0.06))
        thesis = (
            f"{time_horizon} 视角下，趋势={trend_state}、MACD柱={'正' if macd_hist > 0 else '负'}、"
            f"RSI14={rsi14:.1f}、情报偏置={intel_bias:+.1f}，因此给出 `{action.value}`。"
        )
        return action, round(confidence, 2), thesis

    def _risk_flags(
        self,
        quote: Quote,
        latest: dict[str, float],
        intel: IntelReport,
        volatility_pct: float,
    ) -> list[str]:
        flags: list[str] = []
        if quote.source == "tushare_daily_snapshot":
            flags.append("quote_not_live")
        if quote.limit_status != LimitStatus.NORMAL:
            flags.append("limit_status_abnormal")
        if volatility_pct >= 3.0:
            flags.append("high_volatility")
        if latest.get("rsi14", 50.0) >= 75:
            flags.append("overbought")
        if latest.get("rsi14", 50.0) <= 20:
            flags.append("oversold_reversal_risk")
        if any(event.source_name == "巨潮资讯" for event in intel.disclosure_events):
            flags.append("recent_disclosure_review")
        if any(event.source_name == "中国政府网" for event in intel.policy_events):
            flags.append("policy_interpretation_required")
        if any(event.source_tier == SourceTier.COMMERCIAL_MEDIA for event in intel.headline_events):
            flags.append("media_headline_unconfirmed")
        return flags

    def _actionability(self, action: AdviceAction, risk_flags: list[str], confidence: float) -> str:
        blocking_flags = {
            "limit_status_abnormal",
            "policy_interpretation_required",
            "execution_budget_constrained",
            "execution_reward_risk_thin",
            "insufficient_budget_for_board_lot",
        }
        if action in {AdviceAction.AVOID, AdviceAction.SELL_WATCH}:
            return "research_only"
        if any(flag in blocking_flags for flag in risk_flags):
            return "approval_required"
        if confidence >= 0.6:
            return "paper_trade_ready"
        return "research_only"

    def _apply_execution_constraints(
        self,
        action: AdviceAction,
        confidence: float,
        thesis: str,
        price: float,
        stop_loss: float,
        target_low: float,
        suggested_position_value: float | None,
        suggested_quantity: int | None,
        commission_bps: float,
        lot_size: int,
        account_equity: float | None,
        fee_drag_warn_ratio: float,
        reward_risk_tight_ratio: float,
        reward_risk_thin_ratio: float,
    ) -> tuple[AdviceAction, float, str, list[str]]:
        adjusted_action = action
        adjusted_confidence = confidence
        flags: list[str] = []
        thesis_notes: list[str] = []

        if account_equity is not None and account_equity > 0 and suggested_quantity == 0:
            flags.append("execution_budget_constrained")
            thesis_notes.append(f"预算不足 {lot_size} 股整手")
            adjusted_confidence -= 0.18
            if adjusted_action in {AdviceAction.BUY_CANDIDATE, AdviceAction.BUY_WATCH}:
                adjusted_action = AdviceAction.HOLD

        if price > 0 and stop_loss > 0 and target_low > 0:
            downside_pct = max(0.0, 1 - (stop_loss / price))
            gross_upside_pct = max(0.0, (target_low / price) - 1)
            round_trip_fee_pct = (commission_bps * 2) / 10000
            net_upside_pct = max(0.0, gross_upside_pct - round_trip_fee_pct)

            if gross_upside_pct > 0 and round_trip_fee_pct >= gross_upside_pct * fee_drag_warn_ratio:
                flags.append("execution_fee_drag_high")
                thesis_notes.append("手续费拖累偏高")
                adjusted_confidence -= 0.06
                if adjusted_action == AdviceAction.BUY_CANDIDATE:
                    adjusted_action = AdviceAction.BUY_WATCH

            if downside_pct > 0 and net_upside_pct <= downside_pct * reward_risk_thin_ratio:
                flags.append("execution_reward_risk_thin")
                thesis_notes.append("止盈止损空间偏薄")
                adjusted_confidence -= 0.1
                if adjusted_action == AdviceAction.BUY_CANDIDATE:
                    adjusted_action = AdviceAction.BUY_WATCH
                elif adjusted_action == AdviceAction.BUY_WATCH:
                    adjusted_action = AdviceAction.HOLD
            elif downside_pct > 0 and net_upside_pct <= downside_pct * reward_risk_tight_ratio:
                flags.append("execution_reward_risk_tight")
                thesis_notes.append("盈亏比偏紧")
                adjusted_confidence -= 0.05

        adjusted_confidence = round(max(0.25, min(0.84, adjusted_confidence)), 2)
        if thesis_notes:
            thesis = f"{thesis} 执行侧补充：{'，'.join(dict.fromkeys(thesis_notes))}。"
        return adjusted_action, adjusted_confidence, thesis, list(dict.fromkeys(flags))

    def _execution_trade_plan(
        self,
        price: float,
        account_equity: float | None,
        available_cash: float | None,
        max_position_pct: float,
        commission_bps: float,
        lot_size: int,
    ) -> tuple[float | None, int | None, float | None]:
        if price <= 0:
            return None, None, None
        budget_candidates = [value for value in [available_cash] if value is not None and value > 0]
        if account_equity is not None and account_equity > 0:
            budget_candidates.append(account_equity * max_position_pct)
        if not budget_candidates:
            return None, None, None
        position_budget = min(budget_candidates)
        fee_factor = 1 + (commission_bps / 10000)
        raw_quantity = int(position_budget // (price * fee_factor * lot_size)) * lot_size
        if raw_quantity <= 0:
            return round(position_budget, 2), 0, 0.0
        estimated_fee = round((price * raw_quantity) * commission_bps / 10000, 2)
        suggested_position_value = round(price * raw_quantity, 2)
        return round(position_budget, 2), raw_quantity, estimated_fee


class RiskService:
    def __init__(self, market: MarketProviderFacade, intel: IntelService, indicators: IndicatorService) -> None:
        self.market = market
        self.intel = intel
        self.indicators = indicators

    def check(self, request: RiskCheckRequest) -> RiskCheckResponse:
        checks: list[RiskRuleResult] = []
        (
            max_position_pct,
            stop_loss_pct,
            take_profit_pct,
            commission_bps,
            lot_size,
            min_hold_days,
            max_open_positions,
            fee_drag_warn_ratio,
            reward_risk_tight_ratio,
            reward_risk_thin_ratio,
            execution_config_source,
        ) = _resolve_execution_values(request.execution, 1)
        (
            max_sector_pct,
            max_total_exposure_pct,
            max_daily_orders,
            portfolio_risk_config_source,
        ) = _resolve_portfolio_risk_values(request.portfolio_risk)
        if request.quantity <= 0 or request.price <= 0:
            checks.append(
                RiskRuleResult(
                    rule="order_sanity",
                    status="block",
                    message="价格和数量必须为正数。",
                )
            )
            return RiskCheckResponse(
                status="blocked",
                checks=checks,
                approval_required=True,
                strategy_meta=_strategy_meta(
                    request.strategy_id or "risk_guard_v1",
                    _EXECUTION_RULE_VERSION,
                    execution_config_source,
                ),
                strategy_version=_strategy_version(request.strategy_id or "risk_guard_v1", _EXECUTION_RULE_VERSION),
                execution_rule_version=_EXECUTION_RULE_VERSION,
                execution_config_source=execution_config_source,
                execution_params=_execution_params_map(
                    max_position_pct,
                    stop_loss_pct,
                    take_profit_pct,
                    commission_bps,
                    lot_size,
                    min_hold_days,
                    max_open_positions,
                    fee_drag_warn_ratio,
                    reward_risk_tight_ratio,
                    reward_risk_thin_ratio,
                ),
                portfolio_risk_config_source=portfolio_risk_config_source,
                portfolio_risk_params=_portfolio_risk_params_map(
                    max_sector_pct,
                    max_total_exposure_pct,
                    max_daily_orders,
                ),
            )

        quote = self.market.get_quote(request.symbol)
        indicators = self.indicators.get_indicators(request.symbol, "1d", "ma,macd,rsi,boll")
        intel = self.intel.get_report(request.symbol, None, 72)
        latest = indicators.latest

        checks.append(self._lot_rule(request, lot_size))
        checks.append(self._max_position_rule(request, max_position_pct))
        checks.append(self._total_exposure_rule(request, max_total_exposure_pct))
        checks.append(self._sector_concentration_rule(request, max_sector_pct))
        checks.append(self._daily_order_limit_rule(request, max_daily_orders))
        checks.append(self._price_deviation_rule(request, quote))
        checks.append(self._limit_rule(request, quote))
        checks.append(self._snapshot_freshness_rule(quote))
        checks.append(self._volatility_rule(latest))
        checks.append(self._event_window_rule(intel))
        checks.append(self._side_momentum_rule(request, latest))

        has_block = any(check.status == "block" for check in checks)
        has_warn = any(check.status == "warn" for check in checks)
        return RiskCheckResponse(
            status="blocked" if has_block else ("approved_with_warnings" if has_warn else "approved"),
            checks=checks,
            approval_required=has_block or has_warn,
            strategy_meta=_strategy_meta(
                request.strategy_id or "risk_guard_v1",
                _EXECUTION_RULE_VERSION,
                execution_config_source,
            ),
            strategy_version=_strategy_version(request.strategy_id or "risk_guard_v1", _EXECUTION_RULE_VERSION),
            execution_rule_version=_EXECUTION_RULE_VERSION,
            execution_config_source=execution_config_source,
            execution_params=_execution_params_map(
                max_position_pct,
                stop_loss_pct,
                take_profit_pct,
                commission_bps,
                lot_size,
                min_hold_days,
                max_open_positions,
                fee_drag_warn_ratio,
                reward_risk_tight_ratio,
                reward_risk_thin_ratio,
            ),
            portfolio_risk_config_source=portfolio_risk_config_source,
            portfolio_risk_params=_portfolio_risk_params_map(
                max_sector_pct,
                max_total_exposure_pct,
                max_daily_orders,
            ),
        )

    def _lot_rule(self, request: RiskCheckRequest, lot_size: int) -> RiskRuleResult:
        if request.side.lower() == "buy" and request.quantity % lot_size != 0:
            return RiskRuleResult(
                rule="board_lot",
                status="block",
                message=f"A股买入通常应按 {lot_size} 股整手下单。",
            )
        return RiskRuleResult(rule="board_lot", status="pass")

    def _max_position_rule(self, request: RiskCheckRequest, max_position_pct: float) -> RiskRuleResult:
        if request.account_equity is None or request.account_equity <= 0:
            return RiskRuleResult(
                rule="max_position_pct",
                status="warn",
                message="缺少账户权益，无法校验单标的仓位上限。",
            )
        current_position_value = max(request.current_position_value or 0.0, 0.0)
        order_notional = request.price * request.quantity
        projected_position_value = (
            current_position_value + order_notional
            if request.side.lower() == "buy"
            else max(0.0, current_position_value - order_notional)
        )
        projected_ratio = projected_position_value / request.account_equity
        if projected_ratio > max_position_pct:
            return RiskRuleResult(
                rule="max_position_pct",
                status="block",
                message=(
                    f"预计单标的仓位占比 {projected_ratio * 100:.2f}% ，"
                    f"超过配置上限 {max_position_pct * 100:.2f}% 。"
                ),
            )
        if projected_ratio > max_position_pct * 0.9:
            return RiskRuleResult(
                rule="max_position_pct",
                status="warn",
                message=(
                    f"预计单标的仓位占比 {projected_ratio * 100:.2f}% ，"
                    f"接近配置上限 {max_position_pct * 100:.2f}% 。"
                ),
            )
        return RiskRuleResult(rule="max_position_pct", status="pass")

    def _total_exposure_rule(
        self,
        request: RiskCheckRequest,
        max_total_exposure_pct: float,
    ) -> RiskRuleResult:
        if request.account_equity is None or request.account_equity <= 0:
            return RiskRuleResult(
                rule="portfolio_exposure",
                status="warn",
                message="缺少账户权益，无法校验组合总暴露。",
            )
        existing_value = sum(max(position.market_value, 0.0) for position in request.portfolio_positions)
        pending_value = max(request.pending_order_value or 0.0, 0.0)
        order_notional = request.price * request.quantity
        projected_value = existing_value + pending_value
        if request.side.lower() == "buy":
            projected_value += order_notional
        else:
            projected_value = max(0.0, projected_value - min(order_notional, max(request.current_position_value or 0.0, 0.0)))
        projected_ratio = projected_value / request.account_equity
        if projected_ratio > max_total_exposure_pct:
            return RiskRuleResult(
                rule="portfolio_exposure",
                status="block",
                message=(
                    f"预计组合总暴露 {projected_ratio * 100:.2f}% ，"
                    f"超过配置上限 {max_total_exposure_pct * 100:.2f}% 。"
                ),
            )
        if projected_ratio > max_total_exposure_pct * 0.9:
            return RiskRuleResult(
                rule="portfolio_exposure",
                status="warn",
                message=(
                    f"预计组合总暴露 {projected_ratio * 100:.2f}% ，"
                    f"接近配置上限 {max_total_exposure_pct * 100:.2f}% 。"
                ),
            )
        return RiskRuleResult(rule="portfolio_exposure", status="pass")

    def _sector_concentration_rule(
        self,
        request: RiskCheckRequest,
        max_sector_pct: float,
    ) -> RiskRuleResult:
        if not request.sector:
            return RiskRuleResult(
                rule="sector_concentration",
                status="warn",
                message="缺少行业标签，无法校验行业集中度。",
            )
        if request.account_equity is None or request.account_equity <= 0:
            return RiskRuleResult(
                rule="sector_concentration",
                status="warn",
                message="缺少账户权益，无法校验行业集中度。",
            )
        sector_fold = request.sector.casefold()
        sector_value = sum(
            max(position.market_value, 0.0)
            for position in request.portfolio_positions
            if position.sector and position.sector.casefold() == sector_fold
        )
        if request.side.lower() == "buy":
            sector_value += request.price * request.quantity
        sector_ratio = sector_value / request.account_equity
        if sector_ratio > max_sector_pct:
            return RiskRuleResult(
                rule="sector_concentration",
                status="block",
                message=(
                    f"预计行业仓位占比 {sector_ratio * 100:.2f}% ，"
                    f"超过配置上限 {max_sector_pct * 100:.2f}% 。"
                ),
            )
        if sector_ratio > max_sector_pct * 0.9:
            return RiskRuleResult(
                rule="sector_concentration",
                status="warn",
                message=(
                    f"预计行业仓位占比 {sector_ratio * 100:.2f}% ，"
                    f"接近配置上限 {max_sector_pct * 100:.2f}% 。"
                ),
            )
        return RiskRuleResult(rule="sector_concentration", status="pass")

    def _daily_order_limit_rule(self, request: RiskCheckRequest, max_daily_orders: int) -> RiskRuleResult:
        if request.daily_order_count is None:
            return RiskRuleResult(
                rule="daily_order_limit",
                status="warn",
                message="缺少当日订单计数，无法校验组合交易频率。",
            )
        projected_count = request.daily_order_count + 1
        if projected_count > max_daily_orders:
            return RiskRuleResult(
                rule="daily_order_limit",
                status="block",
                message=f"预计当日订单数 {projected_count} ，超过配置上限 {max_daily_orders} 。",
            )
        if projected_count >= max(1, int(max_daily_orders * 0.9)):
            return RiskRuleResult(
                rule="daily_order_limit",
                status="warn",
                message=f"预计当日订单数 {projected_count} ，接近配置上限 {max_daily_orders} 。",
            )
        return RiskRuleResult(rule="daily_order_limit", status="pass")

    def _price_deviation_rule(self, request: RiskCheckRequest, quote: Quote) -> RiskRuleResult:
        reference = quote.last or quote.prev_close
        if not reference:
            return RiskRuleResult(rule="price_deviation", status="warn", message="缺少参考价格，需人工确认。")
        deviation_pct = abs(request.price - reference) / reference * 100
        if deviation_pct >= 5:
            return RiskRuleResult(
                rule="price_deviation",
                status="block",
                message=f"委托价偏离最新参考价 {deviation_pct:.2f}% ，超出阈值。",
            )
        if deviation_pct >= 2:
            return RiskRuleResult(
                rule="price_deviation",
                status="warn",
                message=f"委托价偏离最新参考价 {deviation_pct:.2f}% ，建议人工复核。",
            )
        return RiskRuleResult(rule="price_deviation", status="pass")

    def _limit_rule(self, request: RiskCheckRequest, quote: Quote) -> RiskRuleResult:
        if quote.limit_status != LimitStatus.NORMAL:
            return RiskRuleResult(
                rule="limit_status",
                status="block",
                message="标的处于涨跌停异常状态，不建议直接执行。",
            )
        near_limit = abs(quote.change_pct) >= 9.2
        if near_limit:
            return RiskRuleResult(
                rule="limit_status",
                status="warn",
                message="标的接近涨跌停，成交和撤单风险上升。",
            )
        return RiskRuleResult(rule="limit_status", status="pass")

    def _snapshot_freshness_rule(self, quote: Quote) -> RiskRuleResult:
        if quote.source == "tushare_daily_snapshot":
            return RiskRuleResult(
                rule="quote_freshness",
                status="warn",
                message="当前报价来自日线快照，不是盘中实时行情。",
            )
        return RiskRuleResult(rule="quote_freshness", status="pass")

    def _volatility_rule(self, latest: dict[str, float]) -> RiskRuleResult:
        atr_pct = latest.get("atr_pct", 0.0) * 100
        if atr_pct >= 4:
            return RiskRuleResult(
                rule="volatility_guard",
                status="warn",
                message=f"ATR波动率约 {atr_pct:.2f}% ，波动较高。",
            )
        return RiskRuleResult(rule="volatility_guard", status="pass")

    def _event_window_rule(self, intel: IntelReport) -> RiskRuleResult:
        recent_official_events = [
            event
            for event in [*intel.policy_events, *intel.disclosure_events]
            if (_now() - event.published_at.astimezone(UTC)) <= timedelta(hours=72)
        ]
        if recent_official_events:
            return RiskRuleResult(
                rule="event_window",
                status="warn",
                message="最近72小时内存在官方政策或公告事件，建议人工复核。",
            )
        recent_negative_media_events = [
            event
            for event in intel.headline_events
            if event.source_tier == SourceTier.COMMERCIAL_MEDIA
            and (_now() - event.published_at.astimezone(UTC)) <= timedelta(hours=72)
            and _event_keyword_score(event) < 0
        ]
        if recent_negative_media_events:
            return RiskRuleResult(
                rule="event_window",
                status="warn",
                message="最近72小时内存在负面媒体 headline，尚未见官方公告或政策确认，建议人工复核。",
            )
        return RiskRuleResult(rule="event_window", status="pass")

    def _side_momentum_rule(self, request: RiskCheckRequest, latest: dict[str, float]) -> RiskRuleResult:
        rsi14 = latest.get("rsi14", 50.0)
        macd_hist = latest.get("macd_hist", 0.0)
        side = request.side.lower()
        if side == "buy" and rsi14 >= 78:
            return RiskRuleResult(
                rule="momentum_extreme",
                status="warn",
                message="买入时标的已接近超买区，追高风险较大。",
            )
        if side == "sell" and rsi14 <= 22 and macd_hist < 0:
            return RiskRuleResult(
                rule="momentum_extreme",
                status="warn",
                message="卖出时标的已处于超卖区，需警惕反抽风险。",
            )
        return RiskRuleResult(rule="momentum_extreme", status="pass")


class BacktestService:
    def __init__(self, market: MarketProviderFacade, intel: IntelService) -> None:
        self.market = market
        self.intel = intel

    def run(self, request: BacktestRunRequest) -> BacktestRunResponse:
        symbols = self._normalize_symbols(request)
        data: dict[str, list[Bar]] = {}
        (
            enable_intel_gate,
            intel_lookback_hours,
            require_positive_official_event,
            block_negative_official_event,
            event_keyword_weight,
            event_source_weight,
            event_recency_window_hours,
            intel_gate_config_source,
        ) = self._resolve_intel_gate_config(request)
        (
            max_position_pct,
            stop_loss_pct,
            take_profit_pct,
            commission_bps,
            lot_size,
            min_hold_days,
            max_open_positions,
            fee_drag_warn_ratio,
            reward_risk_tight_ratio,
            reward_risk_thin_ratio,
            execution_config_source,
        ) = self._resolve_execution_config(request, max(1, len(symbols)))
        official_events: dict[str, list[NewsItem]] = {}
        for symbol in symbols:
            bars = self.market.get_bars(symbol, "1d", 500).bars
            filtered = self._filter_bars(bars, request.start, request.end)
            if len(filtered) >= 60:
                data[symbol] = filtered
                if enable_intel_gate:
                    official_events[symbol] = self._official_backtest_events(symbol, intel_lookback_hours)

        if not data:
            now = _now()
            summary = BacktestSummary(
                run_id=f"bt_{uuid4().hex[:10]}",
                strategy_id=request.strategy_id,
                strategy_meta=_strategy_meta(
                    request.strategy_id,
                    _EXECUTION_RULE_VERSION,
                    execution_config_source,
                    _INTEL_GATE_FORMULA_VERSION if enable_intel_gate else None,
                    intel_gate_config_source,
                ),
                strategy_version=_strategy_version(
                    request.strategy_id,
                    _EXECUTION_RULE_VERSION,
                    _INTEL_GATE_FORMULA_VERSION if enable_intel_gate else None,
                ),
                symbol=request.symbol,
                symbols=symbols,
                scope="portfolio" if len(symbols) > 1 else "single_symbol",
                start=request.start,
                end=request.end,
                initial_capital=request.capital,
                ending_cash=request.capital,
                ending_market_value=0.0,
                ending_equity=request.capital,
                total_return_pct=0.0,
                max_drawdown_pct=0.0,
                total_trades=0,
                closed_trade_count=0,
                winning_trade_count=0,
                losing_trade_count=0,
                win_rate=0.0,
                gate_blocked_entry_count=0,
                execution_rule_version=_EXECUTION_RULE_VERSION,
                execution_config_source=execution_config_source,
                execution_params=self._execution_params(
                    max_position_pct,
                    stop_loss_pct,
                    take_profit_pct,
                    commission_bps,
                    lot_size,
                    min_hold_days,
                    max_open_positions,
                    fee_drag_warn_ratio,
                    reward_risk_tight_ratio,
                    reward_risk_thin_ratio,
                ),
                intel_gate_formula_version=_INTEL_GATE_FORMULA_VERSION if enable_intel_gate else None,
                intel_gate_config_source=intel_gate_config_source,
                intel_gate_scoring_params=self._intel_gate_scoring_params(
                    enable_intel_gate,
                    event_keyword_weight,
                    event_source_weight,
                    event_recency_window_hours,
                ),
                updated_at=now,
            )
            return BacktestRunResponse(
                summary=summary,
                trades=[],
                equity_curve=[],
                symbol_contributions=[],
                blocked_entries=[],
            )

        cash = request.capital
        positions: dict[str, dict[str, float | int | None]] = {
            symbol: {"quantity": 0, "avg_cost": 0.0, "entry_index": None}
            for symbol in data
        }
        symbol_stats: dict[str, dict[str, float | int]] = {
            symbol: {"realized_pnl": 0.0, "total_trades": 0, "closed_trade_count": 0, "blocked_entry_count": 0}
            for symbol in data
        }
        last_prices: dict[str, float] = {}
        trades: list[BacktestTrade] = []
        equity_curve: list[BacktestEquityPoint] = []
        blocked_entries: list[BacktestBlockedEntry] = []
        run_id = f"bt_{uuid4().hex[:10]}"
        gate_blocked_entry_count = 0

        by_date: dict[date, list[tuple[str, int, Bar]]] = {}
        for symbol, bars in data.items():
            for idx in range(59, len(bars)):
                bar = bars[idx]
                trade_day = bar.ts.astimezone(_LOCAL_TZ).date()
                by_date.setdefault(trade_day, []).append((symbol, idx, bar))

        for trade_day in sorted(by_date):
            day_events = sorted(by_date[trade_day], key=lambda item: item[0])
            for symbol, idx, bar in day_events:
                last_prices[symbol] = bar.close
                window = data[symbol][: idx + 1]
                snapshot = self._indicator_snapshot(window)
                state = positions[symbol]
                quantity = int(state["quantity"])
                avg_cost = float(state["avg_cost"])
                entry_index = state["entry_index"]
                reason: str | None = None

                if quantity > 0:
                    if bar.close <= avg_cost * (1 - stop_loss_pct):
                        reason = "stop_loss"
                    elif (
                        isinstance(entry_index, int)
                        and idx - entry_index >= min_hold_days
                        and bar.close >= avg_cost * (1 + take_profit_pct)
                    ):
                        reason = "take_profit"
                    elif (
                        isinstance(entry_index, int)
                        and idx - entry_index >= min_hold_days
                        and self._should_exit(bar.close, snapshot)
                    ):
                        reason = "trend_exit"

                    if reason:
                        holding_days = idx - entry_index if isinstance(entry_index, int) else 0
                        fees = (bar.close * quantity) * commission_bps / 10000
                        pnl = (bar.close - avg_cost) * quantity - fees
                        cash += bar.close * quantity - fees
                        trades.append(
                            BacktestTrade(
                                ts=bar.ts,
                                symbol=symbol,
                                side="sell",
                                price=round(bar.close, 4),
                                quantity=quantity,
                                fees=round(fees, 2),
                                pnl=round(pnl, 2),
                                reason=reason,
                                indicator_snapshot={
                                    "ma5": round(snapshot["ma5"], 4),
                                    "ma20": round(snapshot["ma20"], 4),
                                    "macd_hist": round(snapshot["macd_hist"], 6),
                                    "rsi14": round(snapshot["rsi14"], 4),
                                },
                                holding_days=holding_days,
                                exit_rule=reason,
                                exit_rule_inputs={
                                    "entry_price": round(avg_cost, 4),
                                    "stop_loss_price": round(avg_cost * (1 - stop_loss_pct), 4),
                                    "take_profit_price": round(avg_cost * (1 + take_profit_pct), 4),
                                    "close": round(bar.close, 4),
                                    "ma20": round(snapshot["ma20"], 4),
                                    "macd_hist": round(snapshot["macd_hist"], 6),
                                    "rsi14": round(snapshot["rsi14"], 4),
                                },
                            )
                        )
                        symbol_stats[symbol]["realized_pnl"] += pnl
                        symbol_stats[symbol]["total_trades"] += 1
                        symbol_stats[symbol]["closed_trade_count"] += 1
                        state["quantity"] = 0
                        state["avg_cost"] = 0.0
                        state["entry_index"] = None
                        quantity = 0

                open_positions = sum(1 for payload in positions.values() if int(payload["quantity"]) > 0)
                current_equity = cash + self._market_value(positions, last_prices)
                allow_entry = True
                gate_event_titles: list[str] = []
                gate_block_reason: str | None = None
                gate_rule_inputs: dict[str, float] = {}
                gate_event_refs: list[BacktestGateEventRef] = []
                if enable_intel_gate:
                    allow_entry, gate_event_titles, gate_block_reason, gate_rule_inputs, gate_event_refs = self._intel_entry_allowed(
                        official_events.get(symbol, []),
                        bar.ts,
                        intel_lookback_hours,
                        require_positive_official_event,
                        block_negative_official_event,
                        event_keyword_weight,
                        event_source_weight,
                        event_recency_window_hours,
                    )
                has_entry_signal = quantity <= 0 and open_positions < max_open_positions and self._should_enter(bar.close, snapshot)
                if has_entry_signal and enable_intel_gate and not allow_entry:
                    gate_blocked_entry_count += 1
                    symbol_stats[symbol]["blocked_entry_count"] += 1
                    blocked_entries.append(
                        BacktestBlockedEntry(
                            ts=bar.ts,
                            symbol=symbol,
                            price=round(bar.close, 4),
                            reason=gate_block_reason or "intel_gate_blocked",
                            blocked_rule=gate_block_reason or "intel_gate_blocked",
                            blocked_rule_inputs={
                                "close": round(bar.close, 4),
                                "ma5": round(snapshot["ma5"], 4),
                                "ma20": round(snapshot["ma20"], 4),
                                "macd_hist": round(snapshot["macd_hist"], 6),
                                "rsi14": round(snapshot["rsi14"], 4),
                                **gate_rule_inputs,
                            },
                            gate_event_titles=gate_event_titles,
                            gate_events=gate_event_refs,
                            indicator_snapshot={
                                "ma5": round(snapshot["ma5"], 4),
                                "ma20": round(snapshot["ma20"], 4),
                                "macd_hist": round(snapshot["macd_hist"], 6),
                                "rsi14": round(snapshot["rsi14"], 4),
                            },
                        )
                    )
                if has_entry_signal and allow_entry:
                    order_budget = min(cash, current_equity * max_position_pct)
                    target_quantity = int(order_budget // (bar.close * lot_size)) * lot_size
                    if target_quantity > 0:
                        fees = (bar.close * target_quantity) * commission_bps / 10000
                        total_cost = bar.close * target_quantity + fees
                        if total_cost <= cash:
                            cash -= total_cost
                            state["quantity"] = target_quantity
                            state["avg_cost"] = bar.close
                            state["entry_index"] = idx
                            trades.append(
                                BacktestTrade(
                                    ts=bar.ts,
                                    symbol=symbol,
                                    side="buy",
                                    price=round(bar.close, 4),
                                    quantity=target_quantity,
                                    fees=round(fees, 2),
                                    pnl=0.0,
                                    reason="trend_pullback_entry_intel" if enable_intel_gate else "trend_pullback_entry",
                                    gate_event_titles=gate_event_titles,
                                    indicator_snapshot={
                                        "ma5": round(snapshot["ma5"], 4),
                                        "ma20": round(snapshot["ma20"], 4),
                                        "macd_hist": round(snapshot["macd_hist"], 6),
                                        "rsi14": round(snapshot["rsi14"], 4),
                                    },
                                    entry_rule="trend_pullback_entry_intel" if enable_intel_gate else "trend_pullback_entry",
                                    entry_rule_inputs={
                                        "close": round(bar.close, 4),
                                        "ma5": round(snapshot["ma5"], 4),
                                        "ma20": round(snapshot["ma20"], 4),
                                        "macd_hist": round(snapshot["macd_hist"], 6),
                                        "rsi14": round(snapshot["rsi14"], 4),
                                        "position_budget": round(order_budget, 2),
                                    },
                                )
                            )
                            symbol_stats[symbol]["total_trades"] += 1

            market_value = self._market_value(positions, last_prices)
            equity_curve.append(
                BacktestEquityPoint(
                    ts=max(event[2].ts for event in day_events),
                    cash=round(cash, 2),
                    market_value=round(market_value, 2),
                    equity=round(cash + market_value, 2),
                )
            )

        ending_market_value = self._market_value(positions, last_prices)
        ending_equity = cash + ending_market_value
        sell_trades = [trade for trade in trades if trade.side == "sell"]
        winning_trade_count = sum(1 for trade in sell_trades if trade.pnl > 0)
        losing_trade_count = sum(1 for trade in sell_trades if trade.pnl < 0)
        peak = request.capital
        max_drawdown_pct = 0.0
        for point in equity_curve:
            peak = max(peak, point.equity)
            if peak > 0:
                max_drawdown_pct = max(max_drawdown_pct, ((peak - point.equity) / peak) * 100)

        summary = BacktestSummary(
            run_id=run_id,
            strategy_id=request.strategy_id,
            strategy_meta=_strategy_meta(
                request.strategy_id,
                _EXECUTION_RULE_VERSION,
                execution_config_source,
                _INTEL_GATE_FORMULA_VERSION if enable_intel_gate else None,
                intel_gate_config_source,
            ),
            strategy_version=_strategy_version(
                request.strategy_id,
                _EXECUTION_RULE_VERSION,
                _INTEL_GATE_FORMULA_VERSION if enable_intel_gate else None,
            ),
            symbol=request.symbol or (symbols[0] if len(symbols) == 1 else None),
            symbols=list(data.keys()),
            scope="portfolio" if len(data) > 1 else "single_symbol",
            start=request.start,
            end=request.end,
            initial_capital=request.capital,
            ending_cash=round(cash, 2),
            ending_market_value=round(ending_market_value, 2),
            ending_equity=round(ending_equity, 2),
            total_return_pct=round(((ending_equity / request.capital) - 1) * 100, 3)
            if request.capital
            else 0.0,
            max_drawdown_pct=round(max_drawdown_pct, 3),
            total_trades=len(trades),
            closed_trade_count=len(sell_trades),
            winning_trade_count=winning_trade_count,
            losing_trade_count=losing_trade_count,
            win_rate=round((winning_trade_count / len(sell_trades)) * 100, 3) if sell_trades else 0.0,
            gate_blocked_entry_count=gate_blocked_entry_count,
            execution_rule_version=_EXECUTION_RULE_VERSION,
            execution_config_source=execution_config_source,
            execution_params=self._execution_params(
                max_position_pct,
                stop_loss_pct,
                take_profit_pct,
                commission_bps,
                lot_size,
                min_hold_days,
                max_open_positions,
                fee_drag_warn_ratio,
                reward_risk_tight_ratio,
                reward_risk_thin_ratio,
            ),
            intel_gate_formula_version=_INTEL_GATE_FORMULA_VERSION if enable_intel_gate else None,
            intel_gate_config_source=intel_gate_config_source,
            intel_gate_scoring_params=self._intel_gate_scoring_params(
                enable_intel_gate,
                event_keyword_weight,
                event_source_weight,
                event_recency_window_hours,
            ),
            updated_at=_now(),
        )
        symbol_contributions = self._symbol_contributions(symbol_stats, positions, last_prices)
        return BacktestRunResponse(
            summary=summary,
            trades=trades,
            equity_curve=equity_curve,
            symbol_contributions=symbol_contributions,
            blocked_entries=blocked_entries,
        )

    def _normalize_symbols(self, request: BacktestRunRequest) -> list[str]:
        values = [*request.symbols]
        if request.symbol:
            values.insert(0, request.symbol)
        deduped: list[str] = []
        seen: set[str] = set()
        for value in values:
            symbol = value.strip().upper()
            if not symbol or symbol in seen:
                continue
            seen.add(symbol)
            deduped.append(symbol)
        return deduped

    def _filter_bars(self, bars: list[Bar], start: str | None, end: str | None) -> list[Bar]:
        if not start and not end:
            return bars
        start_dt = _parse_trade_time(start) if start else None
        end_dt = _parse_trade_time(end) if end else None
        filtered = [
            bar
            for bar in bars
            if (start_dt is None or bar.ts >= start_dt) and (end_dt is None or bar.ts <= end_dt)
        ]
        return filtered or bars

    def _resolve_intel_gate_config(
        self,
        request: BacktestRunRequest,
    ) -> tuple[bool, int, bool, bool, float, float, float, str | None]:
        if request.intel_gate is not None:
            gate = request.intel_gate
            return (
                bool(gate.enabled),
                int(gate.lookback_hours),
                bool(gate.require_positive_official_event),
                bool(gate.block_negative_official_event),
                float(gate.event_keyword_weight),
                float(gate.event_source_weight),
                float(gate.event_recency_window_hours),
                "intel_gate",
            )
        constraints = request.constraints
        gate_keys = {
            "enable_intel_gate",
            "intel_lookback_hours",
            "require_positive_official_event",
            "block_negative_official_event",
            "event_keyword_weight",
            "event_source_weight",
            "event_recency_window_hours",
        }
        config_source = "constraints" if any(key in constraints for key in gate_keys) else None
        return (
            bool(constraints.get("enable_intel_gate", False)),
            int(constraints.get("intel_lookback_hours", 720)),
            bool(constraints.get("require_positive_official_event", False)),
            bool(constraints.get("block_negative_official_event", True)),
            float(constraints.get("event_keyword_weight", _DEFAULT_EVENT_KEYWORD_WEIGHT)),
            float(constraints.get("event_source_weight", _DEFAULT_EVENT_SOURCE_WEIGHT)),
            float(constraints.get("event_recency_window_hours", _DEFAULT_EVENT_RECENCY_WINDOW_HOURS)),
            config_source,
        )

    def _resolve_execution_config(
        self,
        request: BacktestRunRequest,
        symbol_count: int,
    ) -> tuple[float, float, float, float, int, int, int, float, float, float, str | None]:
        return _resolve_execution_values(request.execution, symbol_count, request.constraints)

    def _indicator_snapshot(self, bars: list[Bar]) -> dict[str, float]:
        closes = [bar.close for bar in bars]
        ema12 = _ema_series(closes, 12)
        ema26 = _ema_series(closes, 26)
        macd_line = (ema12[-1] - ema26[-1]) if ema12 and ema26 else 0.0
        macd_series = [fast - slow for fast, slow in zip(ema12[-len(ema26):], ema26)] if ema26 else []
        macd_signal_series = _ema_series(macd_series, 9)
        macd_signal = macd_signal_series[-1] if macd_signal_series else 0.0
        return {
            "ma5": _sma(closes, 5),
            "ma20": _sma(closes, 20),
            "macd_hist": macd_line - macd_signal,
            "rsi14": _rsi(closes, 14),
        }

    def _should_enter(self, close: float, latest: dict[str, float]) -> bool:
        return (
            close > latest["ma20"]
            and latest["ma5"] >= latest["ma20"] * 0.995
            and latest["macd_hist"] > 0
            and latest["rsi14"] >= 40
        )

    def _should_exit(self, close: float, latest: dict[str, float]) -> bool:
        return close < latest["ma20"] or latest["macd_hist"] < 0 or latest["rsi14"] >= 85

    def _market_value(
        self,
        positions: dict[str, dict[str, float | int | None]],
        last_prices: dict[str, float],
    ) -> float:
        return sum(
            int(state["quantity"]) * last_prices.get(symbol, float(state["avg_cost"]))
            for symbol, state in positions.items()
            if int(state["quantity"]) > 0
        )

    def _official_backtest_events(self, symbol: str, lookback_hours: int) -> list[NewsItem]:
        report = self.intel.get_report(symbol, None, lookback_hours)
        events = [
            event
            for event in [*report.disclosure_events, *report.policy_events]
            if event.source_name in {"巨潮资讯", "中国政府网"}
        ]
        events.sort(key=lambda item: item.published_at)
        return events

    def _intel_entry_allowed(
        self,
        events: list[NewsItem],
        trade_ts: datetime,
        lookback_hours: int,
        require_positive_official_event: bool,
        block_negative_official_event: bool,
        event_keyword_weight: float,
        event_source_weight: float,
        event_recency_window_hours: float,
    ) -> tuple[bool, list[str], str | None, dict[str, float], list[BacktestGateEventRef]]:
        trade_time = trade_ts.astimezone(UTC)
        window_events = [
            event
            for event in events
            if event.published_at.astimezone(UTC) <= trade_time
            and (trade_time - event.published_at.astimezone(UTC)) <= timedelta(hours=lookback_hours)
        ]
        score = self._official_event_score(window_events)
        metrics = self._official_event_metrics(window_events, trade_time, score)
        selected_events = self._select_gate_events(
            window_events,
            trade_time,
            event_keyword_weight,
            event_source_weight,
            event_recency_window_hours,
        )
        refs = self._gate_event_refs(selected_events)
        if not window_events:
            if require_positive_official_event:
                return False, [], "missing_positive_official_event", metrics, refs
            return True, [], None, metrics, refs

        titles = [event.title for event, _, _, _ in selected_events]
        if block_negative_official_event and score < 0:
            return False, titles, "negative_official_event", metrics, refs
        if require_positive_official_event and score <= 0:
            return False, titles, "missing_positive_official_event", metrics, refs
        return True, titles, None, metrics, refs

    def _official_event_score(self, events: list[NewsItem]) -> int:
        return sum(self._official_event_keyword_score(event) for event in events)

    def _official_event_metrics(
        self,
        events: list[NewsItem],
        trade_time: datetime,
        score: int,
    ) -> dict[str, float]:
        if not events:
            return {
                "official_event_count": 0.0,
                "cninfo_event_count": 0.0,
                "gov_policy_event_count": 0.0,
                "positive_event_count": 0.0,
                "negative_event_count": 0.0,
                "event_score": float(score),
                "latest_event_age_hours": -1.0,
                "latest_positive_event_age_hours": -1.0,
                "latest_negative_event_age_hours": -1.0,
            }
        positive_terms = ["合作", "快报", "增长", "创新", "升级", "意见", "实施", "推进", "批复", "签署"]
        negative_terms = ["风险", "问询", "减持", "诉讼", "处罚", "质押", "延期", "下滑", "亏损", "监管"]
        positive_count = 0
        negative_count = 0
        cninfo_count = 0
        gov_policy_count = 0
        latest_published_at = max(event.published_at.astimezone(UTC) for event in events)
        latest_positive_published_at: datetime | None = None
        latest_negative_published_at: datetime | None = None
        for event in events:
            text = f"{event.title} {event.summary}"
            is_positive = any(term in text for term in positive_terms)
            is_negative = any(term in text for term in negative_terms)
            published_at = event.published_at.astimezone(UTC)
            if event.source_name == "巨潮资讯":
                cninfo_count += 1
            if event.source_name == "中国政府网":
                gov_policy_count += 1
            if is_positive:
                positive_count += 1
                latest_positive_published_at = max(latest_positive_published_at, published_at) if latest_positive_published_at else published_at
            if is_negative:
                negative_count += 1
                latest_negative_published_at = max(latest_negative_published_at, published_at) if latest_negative_published_at else published_at
        latest_event_age_hours = (trade_time - latest_published_at).total_seconds() / 3600
        latest_positive_event_age_hours = (
            (trade_time - latest_positive_published_at).total_seconds() / 3600 if latest_positive_published_at else -1.0
        )
        latest_negative_event_age_hours = (
            (trade_time - latest_negative_published_at).total_seconds() / 3600 if latest_negative_published_at else -1.0
        )
        return {
            "official_event_count": float(len(events)),
            "cninfo_event_count": float(cninfo_count),
            "gov_policy_event_count": float(gov_policy_count),
            "positive_event_count": float(positive_count),
            "negative_event_count": float(negative_count),
            "event_score": float(score),
            "latest_event_age_hours": round(latest_event_age_hours, 3),
            "latest_positive_event_age_hours": round(latest_positive_event_age_hours, 3),
            "latest_negative_event_age_hours": round(latest_negative_event_age_hours, 3),
        }

    def _select_gate_events(
        self,
        events: list[NewsItem],
        trade_time: datetime,
        event_keyword_weight: float,
        event_source_weight: float,
        event_recency_window_hours: float,
    ) -> list[tuple[NewsItem, float, str, dict[str, float | int]]]:
        ranked: list[tuple[tuple[float, float, float], NewsItem, float, str, dict[str, float | int]]] = []
        for event in events:
            keyword_score = self._official_event_keyword_score(event)
            published_at = event.published_at.astimezone(UTC)
            age_hours = (trade_time - published_at).total_seconds() / 3600
            source_priority = self._event_source_priority(event)
            recency_score = self._event_recency_score(age_hours, event_recency_window_hours)
            selection_score = (
                (abs(float(keyword_score)) * event_keyword_weight)
                + (float(source_priority) * event_source_weight)
                + recency_score
            )
            selection_reason = self._event_selection_reason(event, keyword_score, age_hours)
            ranked.append(
                (
                    (selection_score, float(source_priority), published_at.timestamp()),
                    event,
                    round(age_hours, 3),
                    selection_reason,
                    {
                        "keyword_score": keyword_score,
                        "source_priority": source_priority,
                        "recency_score": round(recency_score, 3),
                        "selection_score": round(selection_score, 3),
                    },
                )
            )
        ranked.sort(key=lambda item: item[0], reverse=True)
        return [(event, age_hours, selection_reason, debug) for _, event, age_hours, selection_reason, debug in ranked[:3]]

    def _gate_event_refs(
        self,
        selected_events: list[tuple[NewsItem, float, str, dict[str, float | int]]],
    ) -> list[BacktestGateEventRef]:
        refs: list[BacktestGateEventRef] = []
        for index, (event, age_hours, selection_reason, debug) in enumerate(selected_events, start=1):
            refs.append(
                BacktestGateEventRef(
                    title=event.title,
                    source_name=event.source_name,
                    source_url=event.source_url,
                    published_at=event.published_at,
                    event_type=event.event_type,
                    sentiment=event.sentiment,
                    impact_direction=event.impact_direction,
                    confidence=event.confidence,
                    age_hours=age_hours,
                    selection_rank=index,
                    selection_reason=selection_reason,
                    keyword_score=int(debug["keyword_score"]),
                    source_priority=int(debug["source_priority"]),
                    recency_score=float(debug["recency_score"]),
                    selection_score=float(debug["selection_score"]),
                )
            )
        return refs

    def _official_event_keyword_score(self, event: NewsItem) -> int:
        positive_terms = ["合作", "快报", "增长", "创新", "升级", "意见", "实施", "推进", "批复", "签署"]
        negative_terms = ["风险", "问询", "减持", "诉讼", "处罚", "质押", "延期", "下滑", "亏损", "监管"]
        text = f"{event.title} {event.summary}"
        score = 0
        if any(term in text for term in positive_terms):
            score += 1
        if any(term in text for term in negative_terms):
            score -= 1
        return score

    def _event_source_priority(self, event: NewsItem) -> int:
        if event.source_name == "巨潮资讯":
            return 2
        if event.source_name == "中国政府网":
            return 1
        return 0

    def _event_recency_score(self, age_hours: float, recency_window_hours: float) -> float:
        return max(0.0, recency_window_hours - age_hours)

    def _event_selection_reason(self, event: NewsItem, keyword_score: int, age_hours: float) -> str:
        if keyword_score < 0:
            return "negative_keyword_recent" if age_hours <= 24 else "negative_keyword_signal"
        if keyword_score > 0:
            return "positive_keyword_recent" if age_hours <= 24 else "positive_keyword_signal"
        if event.source_name == "巨潮资讯":
            return "recent_cninfo_event"
        if event.source_name == "中国政府网":
            return "recent_gov_policy_event"
        return "recent_official_event"

    def _intel_gate_scoring_params(
        self,
        enabled: bool,
        event_keyword_weight: float,
        event_source_weight: float,
        event_recency_window_hours: float,
    ) -> dict[str, float]:
        if not enabled:
            return {}
        return {
            "event_keyword_weight": round(event_keyword_weight, 3),
            "event_source_weight": round(event_source_weight, 3),
            "event_recency_window_hours": round(event_recency_window_hours, 3),
        }

    def _execution_params(
        self,
        max_position_pct: float,
        stop_loss_pct: float,
        take_profit_pct: float,
        commission_bps: float,
        lot_size: int,
        min_hold_days: int,
        max_open_positions: int,
        fee_drag_warn_ratio: float,
        reward_risk_tight_ratio: float,
        reward_risk_thin_ratio: float,
    ) -> dict[str, float | int]:
        return _execution_params_map(
            max_position_pct,
            stop_loss_pct,
            take_profit_pct,
            commission_bps,
            lot_size,
            min_hold_days,
            max_open_positions,
            fee_drag_warn_ratio,
            reward_risk_tight_ratio,
            reward_risk_thin_ratio,
        )

    def _symbol_contributions(
        self,
        symbol_stats: dict[str, dict[str, float | int]],
        positions: dict[str, dict[str, float | int | None]],
        last_prices: dict[str, float],
    ) -> list[BacktestSymbolContribution]:
        contributions: list[BacktestSymbolContribution] = []
        for symbol in sorted(symbol_stats):
            state = positions[symbol]
            quantity = int(state["quantity"])
            avg_cost = float(state["avg_cost"])
            last_price = last_prices.get(symbol, avg_cost)
            unrealized_pnl = (last_price - avg_cost) * quantity if quantity > 0 else 0.0
            realized_pnl = float(symbol_stats[symbol]["realized_pnl"])
            contributions.append(
                BacktestSymbolContribution(
                    symbol=symbol,
                    realized_pnl=round(realized_pnl, 2),
                    unrealized_pnl=round(unrealized_pnl, 2),
                    total_pnl=round(realized_pnl + unrealized_pnl, 2),
                    total_trades=int(symbol_stats[symbol]["total_trades"]),
                    closed_trade_count=int(symbol_stats[symbol]["closed_trade_count"]),
                    blocked_entry_count=int(symbol_stats[symbol]["blocked_entry_count"]),
                )
            )
        return contributions


class PaperTradingService:
    def __init__(self, market: MarketProviderFacade, risk: RiskService) -> None:
        self.market = market
        self.risk = risk
        self.ledger_path = Path(settings.paper_ledger_path).expanduser()

    def submit_order(self, request: RiskCheckRequest) -> PaperOrderResponse:
        submitted_at = _now()
        order_id = f"paper_ord_{uuid4().hex[:10]}"
        risk_result = self.risk.check(request)
        if risk_result.status == "blocked":
            return PaperOrderResponse(
                order_id=order_id,
                status="rejected",
                submitted_at=submitted_at,
                fill_price=0.0,
                fill_quantity=0,
                requested_quantity=request.quantity,
                detail="risk_check_blocked",
            )

        account_state = self._account_state(request.account_id)
        positions = account_state["positions"]
        if request.side.lower() == "sell":
            position = positions.get(request.symbol)
            available = position["quantity"] if position else 0
            if request.quantity > available:
                return PaperOrderResponse(
                    order_id=order_id,
                    status="rejected",
                    submitted_at=submitted_at,
                    fill_price=0.0,
                    fill_quantity=0,
                    requested_quantity=request.quantity,
                    detail="insufficient_position",
                )

        quote = self.market.get_quote(request.symbol)
        execution = self._simulate_execution(request, quote, account_state)
        if execution["status"] == "rejected":
            self._append_order(
                {
                    "order_id": order_id,
                    "account_id": request.account_id,
                    "symbol": request.symbol,
                    "side": request.side.lower(),
                    "order_type": request.order_type,
                    "price": request.price,
                    "quantity": request.quantity,
                    "fill_price": 0.0,
                    "fill_quantity": 0,
                    "fees": 0.0,
                    "commission": 0.0,
                    "transfer_fee": 0.0,
                    "stamp_duty": 0.0,
                    "slippage_bps": 0.0,
                    "status": "rejected",
                    "detail": execution["detail"],
                    "submitted_at": submitted_at.isoformat(),
                }
            )
            return PaperOrderResponse(
                order_id=order_id,
                status="rejected",
                submitted_at=submitted_at,
                fill_price=0.0,
                fill_quantity=0,
                requested_quantity=request.quantity,
                detail=str(execution["detail"]),
            )

        record = {
            "order_id": order_id,
            "account_id": request.account_id,
            "symbol": request.symbol,
            "side": request.side.lower(),
            "order_type": request.order_type,
            "price": request.price,
            "quantity": request.quantity,
            "fill_price": execution["fill_price"],
            "fill_quantity": execution["fill_quantity"],
            "fees": execution["fees"],
            "commission": execution["commission"],
            "transfer_fee": execution["transfer_fee"],
            "stamp_duty": execution["stamp_duty"],
            "slippage_bps": execution["slippage_bps"],
            "status": self._paper_status(execution["fill_quantity"], request.quantity, risk_result.approval_required),
            "detail": execution["detail"],
            "submitted_at": submitted_at.isoformat(),
        }
        self._append_order(record)
        return PaperOrderResponse(
            order_id=order_id,
            status=record["status"],
            submitted_at=submitted_at,
            fill_price=float(record["fill_price"]),
            fill_quantity=int(record["fill_quantity"]),
            requested_quantity=request.quantity,
            fees=float(record["fees"]),
            commission=float(record["commission"]),
            transfer_fee=float(record["transfer_fee"]),
            stamp_duty=float(record["stamp_duty"]),
            slippage_bps=float(record["slippage_bps"]),
            detail=str(record["detail"]) if record["detail"] is not None else None,
        )

    def positions(self, account_id: str) -> PaperPositionsResponse:
        state = self._account_state(account_id)
        positions: list[PaperPosition] = []
        for symbol, payload in sorted(state["positions"].items()):
            if payload["quantity"] <= 0:
                continue
            quote = self.market.get_quote(symbol)
            market_value = quote.last * payload["quantity"]
            unrealized_pnl = (quote.last - payload["avg_cost"]) * payload["quantity"]
            positions.append(
                PaperPosition(
                    account_id=account_id,
                    symbol=symbol,
                    quantity=payload["quantity"],
                    avg_cost=round(payload["avg_cost"], 4),
                    last_price=quote.last,
                    market_value=round(market_value, 2),
                    unrealized_pnl=round(unrealized_pnl, 2),
                    unrealized_pnl_pct=round(((quote.last / payload["avg_cost"]) - 1) * 100, 3)
                    if payload["avg_cost"]
                    else 0.0,
                    updated_at=_now(),
                )
            )
        return PaperPositionsResponse(account_id=account_id, positions=positions)

    def orders(self, account_id: str) -> PaperOrdersResponse:
        ledger = self._load_ledger()
        orders = [
            PaperOrderRecord(
                order_id=str(order["order_id"]),
                account_id=str(order["account_id"]),
                symbol=str(order["symbol"]),
                side=str(order["side"]),
                order_type=str(order["order_type"]),
                price=float(order["price"]),
                quantity=int(order["quantity"]),
                fill_price=float(order["fill_price"]),
                fill_quantity=int(order["fill_quantity"]),
                fees=float(order.get("fees", 0.0)),
                commission=float(order.get("commission", 0.0)),
                transfer_fee=float(order.get("transfer_fee", 0.0)),
                stamp_duty=float(order.get("stamp_duty", 0.0)),
                slippage_bps=float(order.get("slippage_bps", 0.0)),
                status=str(order["status"]),
                detail=str(order["detail"]) if order.get("detail") is not None else None,
                submitted_at=_parse_trade_time(order["submitted_at"]),
            )
            for order in ledger["orders"]
            if order.get("account_id") == account_id
        ]
        orders.sort(key=lambda item: item.submitted_at, reverse=True)
        return PaperOrdersResponse(account_id=account_id, orders=orders)

    def account_summary(self, account_id: str) -> PaperAccountSummary:
        state = self._account_state(account_id)
        market_value = 0.0
        unrealized_pnl = 0.0
        positions_count = 0
        for symbol, payload in state["positions"].items():
            if payload["quantity"] <= 0:
                continue
            positions_count += 1
            quote = self.market.get_quote(symbol)
            position_value = quote.last * payload["quantity"]
            market_value += position_value
            unrealized_pnl += (quote.last - payload["avg_cost"]) * payload["quantity"]
        cash = float(state["cash"])
        return PaperAccountSummary(
            account_id=account_id,
            initial_cash=settings.paper_initial_cash,
            cash=round(cash, 2),
            market_value=round(market_value, 2),
            equity=round(cash + market_value, 2),
            realized_pnl=round(float(state["realized_pnl"]), 2),
            unrealized_pnl=round(unrealized_pnl, 2),
            positions_count=positions_count,
            updated_at=_now(),
        )

    def performance(self, account_id: str) -> PaperPerformanceResponse:
        ledger = self._load_ledger()
        orders = [
            order
            for order in ledger["orders"]
            if order.get("account_id") == account_id
        ]
        orders.sort(key=lambda item: _parse_trade_time(item["submitted_at"]))

        cash = settings.paper_initial_cash
        positions: dict[str, dict[str, float]] = {}
        marks: dict[str, float] = {}
        realized_pnl = 0.0
        closed_trade_count = 0
        winning_trade_count = 0
        losing_trade_count = 0
        curve: list[PaperPerformancePoint] = []

        for order in orders:
            symbol = str(order["symbol"])
            entry = positions.setdefault(symbol, {"quantity": 0, "avg_cost": 0.0})
            quantity = int(order["fill_quantity"])
            fill_price = float(order["fill_price"])
            marks[symbol] = fill_price
            trade_pnl = 0.0

            if order["side"] == "buy":
                total_cost = entry["avg_cost"] * entry["quantity"] + fill_price * quantity
                entry["quantity"] += quantity
                entry["avg_cost"] = total_cost / entry["quantity"] if entry["quantity"] else 0.0
                cash -= fill_price * quantity + float(order.get("fees", 0.0))
            elif order["side"] == "sell":
                trade_pnl = (fill_price - entry["avg_cost"]) * quantity - float(order.get("fees", 0.0))
                realized_pnl += trade_pnl
                closed_trade_count += 1
                if trade_pnl > 0:
                    winning_trade_count += 1
                elif trade_pnl < 0:
                    losing_trade_count += 1
                entry["quantity"] -= quantity
                cash += (fill_price * quantity) - float(order.get("fees", 0.0))
                if entry["quantity"] <= 0:
                    entry["quantity"] = 0
                    entry["avg_cost"] = 0.0

            market_value = sum(
                payload["quantity"] * marks.get(sym, payload["avg_cost"])
                for sym, payload in positions.items()
                if payload["quantity"] > 0
            )
            curve.append(
                PaperPerformancePoint(
                    ts=_parse_trade_time(order["submitted_at"]),
                    cash=round(cash, 2),
                    market_value=round(market_value, 2),
                    equity=round(cash + market_value, 2),
                )
            )

        account = self.account_summary(account_id)
        if not curve:
            curve = [
                PaperPerformancePoint(
                    ts=_now(),
                    cash=round(settings.paper_initial_cash, 2),
                    market_value=0.0,
                    equity=round(settings.paper_initial_cash, 2),
                )
            ]
        else:
            curve.append(
                PaperPerformancePoint(
                    ts=account.updated_at,
                    cash=account.cash,
                    market_value=account.market_value,
                    equity=account.equity,
                )
            )

        peak = curve[0].equity if curve else settings.paper_initial_cash
        max_drawdown_pct = 0.0
        for point in curve:
            peak = max(peak, point.equity)
            if peak <= 0:
                continue
            drawdown_pct = ((peak - point.equity) / peak) * 100
            max_drawdown_pct = max(max_drawdown_pct, drawdown_pct)

        summary = PaperPerformanceSummary(
            account_id=account_id,
            initial_cash=settings.paper_initial_cash,
            equity=account.equity,
            total_return_pct=round(((account.equity / settings.paper_initial_cash) - 1) * 100, 3)
            if settings.paper_initial_cash
            else 0.0,
            realized_pnl=account.realized_pnl,
            unrealized_pnl=account.unrealized_pnl,
            max_drawdown_pct=round(max_drawdown_pct, 3),
            total_orders=len(orders),
            closed_trade_count=closed_trade_count,
            winning_trade_count=winning_trade_count,
            losing_trade_count=losing_trade_count,
            win_rate=round((winning_trade_count / closed_trade_count) * 100, 3)
            if closed_trade_count
            else 0.0,
            updated_at=account.updated_at,
        )
        return PaperPerformanceResponse(account_id=account_id, summary=summary, curve=curve)

    def _account_state(self, account_id: str) -> dict[str, Any]:
        ledger = self._load_ledger()
        positions: dict[str, dict[str, float]] = {}
        cash = settings.paper_initial_cash
        realized_pnl = 0.0
        for order in ledger["orders"]:
            if order.get("account_id") != account_id:
                continue
            symbol = str(order["symbol"])
            entry = positions.setdefault(symbol, {"quantity": 0, "avg_cost": 0.0})
            quantity = int(order["fill_quantity"])
            fill_price = float(order["fill_price"])
            fees = float(order.get("fees", 0.0))
            if order["side"] == "buy":
                total_cost = entry["avg_cost"] * entry["quantity"] + fill_price * quantity
                entry["quantity"] += quantity
                entry["avg_cost"] = total_cost / entry["quantity"] if entry["quantity"] else 0.0
                cash -= fill_price * quantity + fees
            elif order["side"] == "sell":
                realized_pnl += (fill_price - entry["avg_cost"]) * quantity - fees
                entry["quantity"] -= quantity
                cash += (fill_price * quantity) - fees
                if entry["quantity"] <= 0:
                    entry["quantity"] = 0
                    entry["avg_cost"] = 0.0
        return {"positions": positions, "cash": cash, "realized_pnl": realized_pnl}

    def _paper_status(self, fill_quantity: int, requested_quantity: int, approval_required: bool) -> str:
        if fill_quantity <= 0:
            return "queued_with_warnings" if approval_required else "queued"
        if fill_quantity < requested_quantity:
            return "partially_filled_with_warnings" if approval_required else "partially_filled"
        return "accepted_with_warnings" if approval_required else "accepted"

    def _simulate_execution(
        self,
        request: RiskCheckRequest,
        quote: Quote,
        account_state: dict[str, Any],
    ) -> dict[str, float | int | str]:
        (
            _max_position_pct,
            _stop_loss_pct,
            _take_profit_pct,
            commission_bps,
            lot_size,
            _min_hold_days,
            _max_open_positions,
            _fee_drag_warn_ratio,
            _reward_risk_tight_ratio,
            _reward_risk_thin_ratio,
            _execution_config_source,
        ) = _resolve_execution_values(request.execution, 1)
        if self._is_limit_locked(request, quote):
            return {
                "status": "rejected",
                "detail": "price_limit_locked",
                "fill_price": 0.0,
                "fill_quantity": 0,
                "fees": 0.0,
                "commission": 0.0,
                "transfer_fee": 0.0,
                "stamp_duty": 0.0,
                "slippage_bps": 0.0,
            }

        execution_price = self._execution_price(request, quote)
        if request.order_type.lower() == "limit":
            if request.side.lower() == "buy" and request.price < execution_price:
                return {
                    "status": "rejected",
                    "detail": "limit_price_not_reached",
                    "fill_price": 0.0,
                    "fill_quantity": 0,
                    "fees": 0.0,
                    "commission": 0.0,
                    "transfer_fee": 0.0,
                    "stamp_duty": 0.0,
                    "slippage_bps": 0.0,
                }
            if request.side.lower() == "sell" and request.price > execution_price:
                return {
                    "status": "rejected",
                    "detail": "limit_price_not_reached",
                    "fill_price": 0.0,
                    "fill_quantity": 0,
                    "fees": 0.0,
                    "commission": 0.0,
                    "transfer_fee": 0.0,
                    "stamp_duty": 0.0,
                    "slippage_bps": 0.0,
                }

        max_liquidity_quantity = self._liquidity_capped_quantity(request.quantity, quote.volume, lot_size)
        if max_liquidity_quantity <= 0:
            return {
                "status": "rejected",
                "detail": "no_intraday_liquidity",
                "fill_price": 0.0,
                "fill_quantity": 0,
                "fees": 0.0,
                "commission": 0.0,
                "transfer_fee": 0.0,
                "stamp_duty": 0.0,
                "slippage_bps": 0.0,
            }

        fill_quantity = min(request.quantity, max_liquidity_quantity)
        if request.side.lower() == "buy":
            affordable_quantity = self._affordable_quantity(
                cash=float(account_state["cash"]),
                price=execution_price,
                commission_bps=commission_bps,
                lot_size=lot_size,
            )
            fill_quantity = min(fill_quantity, affordable_quantity)
            if fill_quantity <= 0:
                return {
                    "status": "rejected",
                    "detail": "insufficient_cash",
                    "fill_price": 0.0,
                    "fill_quantity": 0,
                    "fees": 0.0,
                    "commission": 0.0,
                    "transfer_fee": 0.0,
                    "stamp_duty": 0.0,
                    "slippage_bps": 0.0,
                }

        fees = self._paper_fees(
            side=request.side.lower(),
            notional=execution_price * fill_quantity,
            commission_bps=commission_bps,
        )
        return {
            "status": "filled" if fill_quantity == request.quantity else "partial_fill",
            "detail": "partial_liquidity_fill" if fill_quantity < request.quantity else "filled",
            "fill_price": execution_price,
            "fill_quantity": fill_quantity,
            "fees": fees["total"],
            "commission": fees["commission"],
            "transfer_fee": fees["transfer_fee"],
            "stamp_duty": fees["stamp_duty"],
            "slippage_bps": settings.paper_slippage_bps,
        }

    def _execution_price(self, request: RiskCheckRequest, quote: Quote) -> float:
        reference = quote.last or quote.prev_close or request.price
        slippage_ratio = settings.paper_slippage_bps / 10000.0
        if request.side.lower() == "buy":
            return round(reference * (1 + slippage_ratio), 4)
        return round(reference * (1 - slippage_ratio), 4)

    def _liquidity_capped_quantity(self, quantity: int, volume: int, lot_size: int) -> int:
        liquidity_quantity = max(lot_size, int(volume * 0.001))
        liquidity_quantity = max(lot_size, (liquidity_quantity // lot_size) * lot_size)
        return min(quantity, liquidity_quantity)

    def _affordable_quantity(self, cash: float, price: float, commission_bps: float, lot_size: int) -> int:
        if cash <= 0 or price <= 0:
            return 0
        rough_lots = int(cash // (price * lot_size))
        while rough_lots > 0:
            quantity = rough_lots * lot_size
            fees = self._paper_fees("buy", price * quantity, commission_bps)["total"]
            if (price * quantity) + fees <= cash:
                return quantity
            rough_lots -= 1
        return 0

    def _paper_fees(self, side: str, notional: float, commission_bps: float) -> dict[str, float]:
        commission = max(notional * (commission_bps / 10000.0), settings.paper_min_commission) if notional > 0 else 0.0
        transfer_fee = notional * (settings.paper_transfer_fee_bps / 10000.0)
        stamp_duty = notional * (settings.paper_stamp_duty_bps / 10000.0) if side == "sell" else 0.0
        total = commission + transfer_fee + stamp_duty
        return {
            "commission": round(commission, 4),
            "transfer_fee": round(transfer_fee, 4),
            "stamp_duty": round(stamp_duty, 4),
            "total": round(total, 4),
        }

    def _is_limit_locked(self, request: RiskCheckRequest, quote: Quote) -> bool:
        if quote.prev_close <= 0:
            return False
        limit_up = quote.prev_close * 1.1
        limit_down = quote.prev_close * 0.9
        if request.side.lower() == "buy":
            return quote.last >= limit_up * 0.999
        return quote.last <= limit_down * 1.001

    def _append_order(self, record: dict[str, Any]) -> None:
        ledger = self._load_ledger()
        ledger["orders"].append(record)
        self._save_ledger(ledger)

    def _load_ledger(self) -> dict[str, list[dict[str, Any]]]:
        if not self.ledger_path.exists():
            return {"orders": []}
        try:
            text = self.ledger_path.read_text().strip()
            if not text:
                return {"orders": []}
            return json.loads(text)
        except Exception as exc:
            raise ProviderError(f"failed to read paper ledger: {exc}") from exc

    def _save_ledger(self, ledger: dict[str, list[dict[str, Any]]]) -> None:
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        self.ledger_path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2))
