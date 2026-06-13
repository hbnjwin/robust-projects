from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse

from .config import settings
from .models import (
    AdviceRequest,
    AdviceResponse,
    BacktestRunRequest,
    BacktestRunResponse,
    BrokerAccountSummary,
    BrokerCancelRequest,
    BrokerCancelResponse,
    BrokerKillSwitchRequest,
    BrokerOrdersResponse,
    BrokerOrderRequest,
    BrokerOrderResponse,
    BrokerPositionsResponse,
    BrokerStatusResponse,
    BarsResponse,
    HealthResponse,
    Indicators,
    IntelEventsResponse,
    IntelIngestRequest,
    IntelIngestResponse,
    IntelItemsResponse,
    IntelReport,
    IntelSchedulerStatus,
    IntelSchedulerTargetRequest,
    MarketDecisionStatus,
    MarketProviderStatus,
    OpsStatusResponse,
    OpsSubsystemStatus,
    PaperAccountSummary,
    PaperOrderResponse,
    PaperOrdersResponse,
    PaperPerformanceResponse,
    PaperPositionsResponse,
    Quote,
    RiskCheckRequest,
    RiskCheckResponse,
    WatchlistAlertsResponse,
    WatchlistItemRequest,
    WatchlistResponse,
    WatchlistStatus,
)
from .services import (
    AdviceService,
    BacktestService,
    BrokerAdapterService,
    IndicatorService,
    IntelHistoryService,
    IntelSchedulerService,
    IntelService,
    MarketProviderFacade,
    PaperTradingService,
    RiskService,
    WatchlistService,
    ProviderError,
)

market_service = MarketProviderFacade()
intel_service = IntelService()
intel_history_service = IntelHistoryService(intel_service)
intel_scheduler_service = IntelSchedulerService(intel_history_service)
indicator_service = IndicatorService(market_service)
advice_service = AdviceService(market_service, intel_service, indicator_service)
risk_service = RiskService(market_service, intel_service, indicator_service)
paper_service = PaperTradingService(market_service, risk_service)
backtest_service = BacktestService(market_service, intel_service)
watchlist_service = WatchlistService(market_service, intel_service, indicator_service)
broker_service = BrokerAdapterService(market_service, risk_service, paper_service)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await intel_scheduler_service.start()
    await watchlist_service.start()
    try:
        yield
    finally:
        await watchlist_service.stop()
        await intel_scheduler_service.stop()


app = FastAPI(title="ashare-quantd", version="0.1.0", lifespan=lifespan)


def _provider_error_status_code(detail: str) -> int:
    text = detail.casefold()
    if "unknown market_data_provider mode" in text or "unsupported intraday interval" in text:
        return 400
    if "symbol_not_found" in text or "could not find symbol" in text or "no intelligence data available" in text:
        return 404
    return 503


@app.exception_handler(ProviderError)
async def provider_error_handler(_request, exc: ProviderError) -> JSONResponse:
    detail = str(exc)
    return JSONResponse(
        status_code=_provider_error_status_code(detail),
        content={"detail": detail},
    )


def _market_ops_summary(market_provider: MarketProviderStatus) -> tuple[str, str | None]:
    if market_provider.effective_provider in {"mock", "unavailable"} or "unavailable" in market_provider.effective_provider:
        return "degraded", "live_providers_unavailable_or_not_configured"
    capability_checks = (
        ("quote", market_provider.quote_ready, market_provider.quote_block_reason),
        ("daily", market_provider.daily_ready, market_provider.daily_block_reason),
        ("intraday", market_provider.intraday_ready, market_provider.intraday_block_reason),
    )
    for capability_name, ready, block_reason in capability_checks:
        if not ready:
            return "degraded", f"{capability_name}_blocked:{block_reason or 'provider_unavailable'}"
    return "ok", None


def _intel_items_response(
    symbol: str | None,
    sector: str | None,
    lookback_hours: int,
    items: list,
    *,
    limit: int,
    extra_filters: dict[str, str | int | bool | None] | None = None,
) -> IntelItemsResponse:
    filters: dict[str, str | int | bool | None] = {
        "lookback_hours": lookback_hours,
        "limit": limit,
    }
    if extra_filters:
        filters.update(extra_filters)
    return IntelItemsResponse(
        scope={"symbol": symbol, "sector": sector},
        filters=filters,
        total_items=len(items),
        items=items[:limit],
    )


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    decision_status = market_service.decision_status()
    watchlist_status = watchlist_service.status()
    broker_status_value = broker_service.status()
    return HealthResponse(
        service=settings.app_name,
        status="ok",
        timezone=settings.timezone,
        market_data_provider=market_service.effective_provider,
        intel_provider=intel_service.effective_provider,
        provider_mode=settings.market_data_provider,
        intel_scheduler_enabled=intel_scheduler_service.enabled,
        intel_scheduler_running=intel_scheduler_service.running,
        intel_event_count=intel_history_service.store.total_events,
        watchlist_scheduler_enabled=watchlist_service.enabled,
        watchlist_scheduler_running=watchlist_service.running,
        watchlist_item_count=watchlist_status.item_count,
        watchlist_alert_count=watchlist_status.alert_count,
        broker_adapter_mode=broker_status_value.adapter_mode,
        broker_kill_switch_active=broker_status_value.kill_switch.active,
        market_quote_selected_source=decision_status.quote_selected_source,
        market_bars_selected_source=decision_status.bars_selected_source,
        market_quote_recent_switch_count=decision_status.quote_recent_switch_count,
        market_bars_recent_switch_count=decision_status.bars_recent_switch_count,
    )


@app.get("/v1/ops/status", response_model=OpsStatusResponse)
def ops_status() -> OpsStatusResponse:
    market_decision = market_service.decision_status()
    market_provider = market_service.provider_status("600519.SH")
    intel_status = intel_scheduler_service.status()
    watchlist_status_value = watchlist_service.status()
    broker_status_value = broker_service.status()
    paper_ledger_path = Path(settings.paper_ledger_path).expanduser()
    market_status, market_detail = _market_ops_summary(market_provider)
    ops_subsystems = [
        OpsSubsystemStatus(
            name="market",
            status=market_status,
            detail=market_detail,
            metrics={
                "effective_provider": market_provider.effective_provider,
                "provider_mode": market_provider.provider_mode,
                "quote_ready": market_provider.quote_ready,
                "quote_block_reason": market_provider.quote_block_reason,
                "intraday_ready": market_provider.intraday_ready,
                "intraday_block_reason": market_provider.intraday_block_reason,
                "daily_ready": market_provider.daily_ready,
                "daily_block_reason": market_provider.daily_block_reason,
                "quote_selected_source": market_decision.quote_selected_source,
                "bars_selected_source": market_decision.bars_selected_source,
                "quote_recent_switch_count": market_decision.quote_recent_switch_count,
                "bars_recent_switch_count": market_decision.bars_recent_switch_count,
            },
        ),
        OpsSubsystemStatus(
            name="intel",
            status="ok" if intel_status.last_error is None else "degraded",
            detail=intel_status.last_error,
            metrics={
                "event_count": intel_status.total_events,
                "scheduler_enabled": intel_status.enabled,
                "scheduler_running": intel_status.running,
                "target_count": intel_status.target_count,
            },
        ),
        OpsSubsystemStatus(
            name="watchlist",
            status="ok" if watchlist_status_value.last_error is None else "degraded",
            detail=watchlist_status_value.last_error,
            metrics={
                "item_count": watchlist_status_value.item_count,
                "alert_count": watchlist_status_value.alert_count,
                "scheduler_enabled": watchlist_status_value.enabled,
                "scheduler_running": watchlist_status_value.running,
            },
        ),
        OpsSubsystemStatus(
            name="broker",
            status="blocked" if broker_status_value.kill_switch.active else "ok",
            detail=broker_status_value.kill_switch.reason if broker_status_value.kill_switch.active else broker_status_value.last_error,
            metrics={
                "adapter_mode": broker_status_value.adapter_mode,
                "live_enabled": broker_status_value.live_enabled,
                "dry_run_only": broker_status_value.dry_run_only,
                "kill_switch_active": broker_status_value.kill_switch.active,
            },
        ),
        OpsSubsystemStatus(
            name="paper",
            status="ok" if paper_ledger_path.exists() or settings.paper_initial_cash > 0 else "degraded",
            detail=None if paper_ledger_path.exists() else "paper_ledger_not_created_yet",
            metrics={
                "ledger_path": str(paper_ledger_path),
                "ledger_exists": paper_ledger_path.exists(),
                "initial_cash": settings.paper_initial_cash,
            },
        ),
    ]
    overall_status = "ok"
    if any(item.status == "degraded" for item in ops_subsystems):
        overall_status = "degraded"
    if any(item.status == "blocked" for item in ops_subsystems):
        overall_status = "blocked"
    return OpsStatusResponse(
        service=settings.app_name,
        generated_at=datetime.now(UTC),
        overall_status=overall_status,
        subsystems=ops_subsystems,
    )


@app.get("/v1/market/quote", response_model=Quote)
def market_quote(symbol: str = Query(..., min_length=6)) -> Quote:
    return market_service.get_quote(symbol)


@app.get("/v1/market/bars", response_model=BarsResponse)
def market_bars(
    symbol: str = Query(..., min_length=6),
    interval: str = Query("1d"),
    limit: int = Query(120, ge=1, le=500),
) -> BarsResponse:
    return market_service.get_bars(symbol, interval, limit)


@app.get("/v1/market/provider-status", response_model=MarketProviderStatus)
def market_provider_status(
    symbol: str = Query("600519.SH", min_length=6),
) -> MarketProviderStatus:
    return market_service.provider_status(symbol)


@app.get("/v1/market/decision-status", response_model=MarketDecisionStatus)
def market_decision_status() -> MarketDecisionStatus:
    return market_service.decision_status()


@app.get("/v1/indicators/calc", response_model=Indicators)
def indicators_calc(
    symbol: str = Query(..., min_length=6),
    interval: str = Query("1d"),
    sets: str = Query("ma,macd,rsi,boll"),
) -> Indicators:
    return indicator_service.get_indicators(symbol, interval, sets)


@app.get("/v1/intel/report", response_model=IntelReport)
def intel_report(
    symbol: str | None = Query(default=None),
    sector: str | None = Query(default=None),
    lookback_hours: int = Query(72, ge=1, le=240),
) -> IntelReport:
    return intel_service.get_report(symbol, sector, lookback_hours)


@app.get("/v1/intel/news", response_model=IntelItemsResponse)
def intel_news(
    symbol: str | None = Query(default=None),
    sector: str | None = Query(default=None),
    source_name: str | None = Query(default=None),
    event_type: str | None = Query(default=None),
    lookback_hours: int = Query(72, ge=1, le=240),
    limit: int = Query(20, ge=1, le=100),
) -> IntelItemsResponse:
    if not symbol and not sector:
        raise HTTPException(status_code=400, detail="symbol or sector is required")
    items = intel_service.get_news(symbol, sector, lookback_hours, source_name=source_name, event_type=event_type)
    return _intel_items_response(
        symbol,
        sector,
        lookback_hours,
        items,
        limit=limit,
        extra_filters={"source_name": source_name, "event_type": event_type},
    )


@app.get("/v1/intel/policy", response_model=IntelItemsResponse)
def intel_policy(
    symbol: str | None = Query(default=None),
    sector: str | None = Query(default=None),
    official_only: bool = Query(True),
    lookback_hours: int = Query(72, ge=1, le=240),
    limit: int = Query(20, ge=1, le=100),
) -> IntelItemsResponse:
    if not symbol and not sector:
        raise HTTPException(status_code=400, detail="symbol or sector is required")
    items = intel_service.get_policy(symbol, sector, lookback_hours)
    return _intel_items_response(
        symbol,
        sector,
        lookback_hours,
        items,
        limit=limit,
        extra_filters={"official_only": official_only},
    )


@app.get("/v1/intel/disclosures", response_model=IntelItemsResponse)
def intel_disclosures(
    symbol: str = Query(..., min_length=6),
    lookback_hours: int = Query(72, ge=1, le=240),
    limit: int = Query(20, ge=1, le=100),
) -> IntelItemsResponse:
    items = intel_service.get_disclosures(symbol, lookback_hours)
    return _intel_items_response(symbol, None, lookback_hours, items, limit=limit)


@app.get("/v1/intel/events", response_model=IntelEventsResponse)
def intel_events(
    symbol: str | None = Query(default=None),
    sector: str | None = Query(default=None),
    event_type: str | None = Query(default=None),
    source_name: str | None = Query(default=None),
    category: str | None = Query(default=None),
    lookback_hours: int = Query(720, ge=1, le=2160),
    limit: int = Query(100, ge=1, le=500),
) -> IntelEventsResponse:
    return intel_history_service.events(symbol, sector, event_type, source_name, category, lookback_hours, limit)


@app.post("/v1/intel/ingest", response_model=IntelIngestResponse)
def intel_ingest(request: IntelIngestRequest) -> IntelIngestResponse:
    try:
        return intel_history_service.ingest(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/v1/intel/scheduler/status", response_model=IntelSchedulerStatus)
def intel_scheduler_status() -> IntelSchedulerStatus:
    return intel_scheduler_service.status()


@app.post("/v1/intel/scheduler/run", response_model=IntelSchedulerStatus)
def intel_scheduler_run() -> IntelSchedulerStatus:
    return intel_scheduler_service.run_once()


@app.post("/v1/intel/scheduler/targets", response_model=IntelSchedulerStatus)
def intel_scheduler_target(request: IntelSchedulerTargetRequest) -> IntelSchedulerStatus:
    try:
        return intel_scheduler_service.upsert_target(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/v1/intel/scheduler/targets", response_model=IntelSchedulerStatus)
def intel_scheduler_target_delete(
    symbol: str | None = Query(default=None),
    sector: str | None = Query(default=None),
) -> IntelSchedulerStatus:
    try:
        return intel_scheduler_service.remove_target(symbol, sector)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/v1/watchlist/items", response_model=WatchlistResponse)
def watchlist_items() -> WatchlistResponse:
    return watchlist_service.watchlist()


@app.post("/v1/watchlist/items", response_model=WatchlistResponse)
def watchlist_item_upsert(request: WatchlistItemRequest) -> WatchlistResponse:
    return watchlist_service.upsert_item(request)


@app.delete("/v1/watchlist/items", response_model=WatchlistResponse)
def watchlist_item_delete(symbol: str = Query(..., min_length=6)) -> WatchlistResponse:
    return watchlist_service.remove_item(symbol)


@app.get("/v1/watchlist/alerts", response_model=WatchlistAlertsResponse)
def watchlist_alerts(
    symbol: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(100, ge=1, le=500),
) -> WatchlistAlertsResponse:
    return watchlist_service.alerts(symbol, status, limit)


@app.get("/v1/watchlist/status", response_model=WatchlistStatus)
def watchlist_status() -> WatchlistStatus:
    return watchlist_service.status()


@app.post("/v1/watchlist/scan", response_model=WatchlistStatus)
def watchlist_scan() -> WatchlistStatus:
    return watchlist_service.run_once()


@app.get("/v1/broker/status", response_model=BrokerStatusResponse)
def broker_status() -> BrokerStatusResponse:
    return broker_service.status()


@app.post("/v1/broker/kill-switch", response_model=BrokerStatusResponse)
def broker_kill_switch(request: BrokerKillSwitchRequest) -> BrokerStatusResponse:
    return broker_service.set_kill_switch(request)


@app.post("/v1/broker/orders", response_model=BrokerOrderResponse)
def broker_order(request: BrokerOrderRequest) -> BrokerOrderResponse:
    return broker_service.submit_order(request)


@app.post("/v1/broker/cancel", response_model=BrokerCancelResponse)
def broker_cancel(request: BrokerCancelRequest) -> BrokerCancelResponse:
    return broker_service.cancel_order(request)


@app.get("/v1/broker/orders", response_model=BrokerOrdersResponse)
def broker_orders(account_id: str = Query(..., min_length=1)) -> BrokerOrdersResponse:
    return broker_service.orders(account_id)


@app.get("/v1/broker/positions", response_model=BrokerPositionsResponse)
def broker_positions(account_id: str = Query(..., min_length=1)) -> BrokerPositionsResponse:
    return broker_service.positions(account_id)


@app.get("/v1/broker/account", response_model=BrokerAccountSummary)
def broker_account(account_id: str = Query(..., min_length=1)) -> BrokerAccountSummary:
    return broker_service.account(account_id)


@app.post("/v1/advice/generate", response_model=AdviceResponse)
def advice_generate(request: AdviceRequest) -> AdviceResponse:
    return advice_service.generate(request)


@app.post("/v1/risk/check", response_model=RiskCheckResponse)
def risk_check(request: RiskCheckRequest) -> RiskCheckResponse:
    return risk_service.check(request)


@app.post("/v1/paper/orders", response_model=PaperOrderResponse)
def paper_order(request: RiskCheckRequest) -> PaperOrderResponse:
    return paper_service.submit_order(request)


@app.get("/v1/paper/positions", response_model=PaperPositionsResponse)
def paper_positions(account_id: str = Query(..., min_length=1)) -> PaperPositionsResponse:
    return paper_service.positions(account_id)


@app.get("/v1/paper/orders", response_model=PaperOrdersResponse)
def paper_orders(account_id: str = Query(..., min_length=1)) -> PaperOrdersResponse:
    return paper_service.orders(account_id)


@app.get("/v1/paper/account", response_model=PaperAccountSummary)
def paper_account(account_id: str = Query(..., min_length=1)) -> PaperAccountSummary:
    return paper_service.account_summary(account_id)


@app.get("/v1/paper/performance", response_model=PaperPerformanceResponse)
def paper_performance(account_id: str = Query(..., min_length=1)) -> PaperPerformanceResponse:
    return paper_service.performance(account_id)


@app.post("/v1/backtest/run", response_model=BacktestRunResponse)
def backtest_run(request: BacktestRunRequest) -> BacktestRunResponse:
    return backtest_service.run(request)


def main() -> None:
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    main()
