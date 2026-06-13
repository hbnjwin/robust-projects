from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class AdviceAction(str, Enum):
    BUY_WATCH = "buy_watch"
    BUY_CANDIDATE = "buy_candidate"
    HOLD = "hold"
    REDUCE = "reduce"
    SELL_WATCH = "sell_watch"
    AVOID = "avoid"


class LimitStatus(str, Enum):
    NORMAL = "normal"
    LIMIT_UP = "limit_up"
    LIMIT_DOWN = "limit_down"


class TradingStatus(str, Enum):
    TRADING = "trading"
    HALTED = "halted"
    CLOSED = "closed"


class SourceTier(str, Enum):
    OFFICIAL = "official"
    PRIMARY_MEDIA = "primary_media"
    COMMERCIAL_MEDIA = "commercial_media"
    RUMOR = "rumor"


class ImpactDirection(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    MIXED = "mixed"
    NEUTRAL = "neutral"


class Magnitude(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Confidence(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ProviderCandidateScore(BaseModel):
    source: str
    status: str = "ok"
    error_code: str | None = None
    detail: str | None = None
    freshness_bucket: int
    completeness: int
    trading_bonus: int = 0
    coverage: int = 0
    source_priority: int
    score_vector: list[int] = Field(default_factory=list)


class ProviderSourceAudit(BaseModel):
    source: str
    consecutive_failures: int = 0
    last_success_at: datetime | None = None
    last_error_at: datetime | None = None
    last_error_code: str | None = None


class ProviderDecision(BaseModel):
    mode: str
    selected_source: str
    reason: str
    audit_window_seconds: int = 300
    recent_switch_count: int = 0
    selected_source_streak: int = 0
    candidates: list[ProviderCandidateScore] = Field(default_factory=list)
    source_audit: list[ProviderSourceAudit] = Field(default_factory=list)


class Quote(BaseModel):
    symbol: str
    name: str
    last: float
    open: float
    high: float
    low: float
    prev_close: float
    change: float
    change_pct: float
    volume: int
    amount: float
    turnover_ratio: float
    amplitude_pct: float
    limit_status: LimitStatus
    trading_status: TradingStatus
    market_time: datetime
    source: str
    received_at: datetime
    provider_decision: ProviderDecision | None = None


class Bar(BaseModel):
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    amount: float


class BarsResponse(BaseModel):
    symbol: str
    interval: str
    bars: list[Bar]
    source: str
    provider_decision: ProviderDecision | None = None


class NewsItem(BaseModel):
    id: str
    title: str
    summary: str
    source_name: str
    source_url: str
    source_tier: SourceTier
    published_at: datetime
    symbols: list[str] = Field(default_factory=list)
    sectors: list[str] = Field(default_factory=list)
    themes: list[str] = Field(default_factory=list)
    event_type: str
    sentiment: str
    impact_direction: ImpactDirection
    impact_magnitude: Magnitude
    confidence: Confidence


class IntelSummary(BaseModel):
    top_catalysts: list[str] = Field(default_factory=list)
    top_risks: list[str] = Field(default_factory=list)


class IntelSectorContext(BaseModel):
    net_direction: ImpactDirection
    confidence: Confidence


class IntelReport(BaseModel):
    scope: dict[str, str | None]
    as_of: datetime
    headline_events: list[NewsItem] = Field(default_factory=list)
    policy_events: list[NewsItem] = Field(default_factory=list)
    disclosure_events: list[NewsItem] = Field(default_factory=list)
    sector_context: IntelSectorContext
    summary: IntelSummary


class IntelStoredEvent(BaseModel):
    item: NewsItem
    categories: list[str] = Field(default_factory=list)
    stored_at: datetime
    report_as_of: datetime
    triggered_by: str = "manual"


class IntelIngestRequest(BaseModel):
    symbol: str | None = None
    sector: str | None = None
    lookback_hours: int = 72
    triggered_by: str = "manual"


class IntelIngestResponse(BaseModel):
    ingest_id: str
    scope: dict[str, str | None]
    lookback_hours: int
    as_of: datetime
    added_count: int
    updated_count: int
    total_events: int
    category_counts: dict[str, int] = Field(default_factory=dict)


class IntelEventsResponse(BaseModel):
    scope: dict[str, str | None]
    filters: dict[str, str | int | None]
    total_events: int
    filtered_events: int
    events: list[IntelStoredEvent] = Field(default_factory=list)


class IntelItemsResponse(BaseModel):
    scope: dict[str, str | None]
    filters: dict[str, str | int | bool | None]
    total_items: int
    items: list[NewsItem] = Field(default_factory=list)


class IntelSchedulerTarget(BaseModel):
    symbol: str | None = None
    sector: str | None = None
    lookback_hours: int = 72
    enabled: bool = True


class IntelSchedulerTargetRequest(BaseModel):
    symbol: str | None = None
    sector: str | None = None
    lookback_hours: int = 72
    enabled: bool = True


class IntelSchedulerRunResult(BaseModel):
    target: IntelSchedulerTarget
    added_count: int
    updated_count: int
    total_events: int
    status: str
    detail: str | None = None


class IntelSchedulerStatus(BaseModel):
    enabled: bool
    running: bool
    interval_seconds: int
    target_count: int
    total_events: int
    last_run_started_at: datetime | None = None
    last_run_finished_at: datetime | None = None
    last_error: str | None = None
    targets: list[IntelSchedulerTarget] = Field(default_factory=list)
    last_results: list[IntelSchedulerRunResult] = Field(default_factory=list)


class WatchlistItem(BaseModel):
    symbol: str
    sector: str | None = None
    notes: str | None = None
    enabled: bool = True
    added_at: datetime


class WatchlistItemRequest(BaseModel):
    symbol: str
    sector: str | None = None
    notes: str | None = None
    enabled: bool = True


class WatchlistAlert(BaseModel):
    alert_id: str
    symbol: str
    sector: str | None = None
    kind: str
    severity: str
    title: str
    detail: str
    source: str
    triggered_at: datetime
    status: str = "open"


class WatchlistResponse(BaseModel):
    items: list[WatchlistItem] = Field(default_factory=list)


class WatchlistAlertsResponse(BaseModel):
    total_alerts: int
    alerts: list[WatchlistAlert] = Field(default_factory=list)


class WatchlistScanResult(BaseModel):
    symbol: str
    generated_alerts: int = 0
    skipped: bool = False
    detail: str | None = None


class WatchlistStatus(BaseModel):
    enabled: bool
    running: bool
    interval_seconds: int
    item_count: int
    alert_count: int
    last_scan_started_at: datetime | None = None
    last_scan_finished_at: datetime | None = None
    last_error: str | None = None
    last_results: list[WatchlistScanResult] = Field(default_factory=list)


class BacktestExecutionConfig(BaseModel):
    max_position_pct: float = 0.2
    stop_loss_pct: float = 0.06
    take_profit_pct: float = 0.12
    commission_bps: float = 3.0
    lot_size: int = 100
    min_hold_days: int = 5
    max_open_positions: int | None = None
    fee_drag_warn_ratio: float = 0.25
    reward_risk_tight_ratio: float = 1.2
    reward_risk_thin_ratio: float = 0.9


class PortfolioPosition(BaseModel):
    symbol: str
    sector: str | None = None
    market_value: float
    beta: float | None = None


class PortfolioRiskConfig(BaseModel):
    max_sector_pct: float = 0.35
    max_total_exposure_pct: float = 0.9
    max_daily_orders: int = 12


class Indicators(BaseModel):
    symbol: str
    interval: str
    latest: dict[str, float]


class AdviceRequest(BaseModel):
    symbol: str
    strategy_id: str
    risk_profile: str = "balanced"
    include_intel: bool = True
    time_horizon: str = "swing"
    account_equity: float | None = None
    available_cash: float | None = None
    execution: BacktestExecutionConfig | None = None


class Catalyst(BaseModel):
    title: str
    source_tier: SourceTier
    published_at: datetime


class TradePlan(BaseModel):
    entry_zone: list[float]
    stop_loss: float
    target_zone: list[float]
    time_horizon: str
    suggested_position_value: float | None = None
    suggested_quantity: int | None = None
    estimated_entry_fee: float | None = None


class StrategyMeta(BaseModel):
    strategy_id: str
    strategy_version: str
    execution_rule_version: str
    intel_version: str | None = None
    execution_config_source: str | None = None
    intel_config_source: str | None = None


class AdviceResponse(BaseModel):
    symbol: str
    action: AdviceAction
    confidence: float
    thesis: str
    market_state: dict[str, str]
    catalysts: list[Catalyst]
    trade_plan: TradePlan
    risk_flags: list[str] = Field(default_factory=list)
    actionability: str
    strategy_meta: StrategyMeta | None = None
    strategy_version: str | None = None
    execution_rule_version: str | None = None
    execution_config_source: str | None = None
    execution_params: dict[str, float | int] = Field(default_factory=dict)


class RiskCheckRequest(BaseModel):
    account_id: str
    strategy_id: str | None = None
    symbol: str
    sector: str | None = None
    side: str
    order_type: str
    price: float
    quantity: int
    account_equity: float | None = None
    current_position_value: float | None = None
    pending_order_value: float | None = None
    daily_order_count: int | None = None
    portfolio_positions: list[PortfolioPosition] = Field(default_factory=list)
    execution: BacktestExecutionConfig | None = None
    portfolio_risk: PortfolioRiskConfig | None = None


class RiskRuleResult(BaseModel):
    rule: str
    status: str
    message: str | None = None


class RiskCheckResponse(BaseModel):
    status: str
    checks: list[RiskRuleResult]
    approval_required: bool
    strategy_meta: StrategyMeta | None = None
    strategy_version: str | None = None
    execution_rule_version: str | None = None
    execution_config_source: str | None = None
    execution_params: dict[str, float | int] = Field(default_factory=dict)
    portfolio_risk_config_source: str | None = None
    portfolio_risk_params: dict[str, float | int] = Field(default_factory=dict)


class BrokerOrderRequest(RiskCheckRequest):
    approval_token: str | None = None


class BrokerCancelRequest(BaseModel):
    account_id: str
    broker_order_id: str
    reason: str | None = None
    approval_token: str | None = None


class BrokerOrderResponse(BaseModel):
    broker_order_id: str
    adapter_mode: str
    dry_run: bool
    status: str
    submitted_at: datetime
    approval_required: bool
    risk_status: str
    routed_order_id: str | None = None
    fill_price: float = 0.0
    fill_quantity: int = 0
    detail: str | None = None


class BrokerCancelResponse(BaseModel):
    broker_order_id: str
    adapter_mode: str
    dry_run: bool
    status: str
    canceled_at: datetime
    approval_required: bool
    routed_order_id: str | None = None
    detail: str | None = None


class BrokerKillSwitchRequest(BaseModel):
    active: bool
    reason: str | None = None


class BrokerKillSwitchState(BaseModel):
    active: bool
    reason: str | None = None
    updated_at: datetime


class BrokerStatusResponse(BaseModel):
    adapter_mode: str
    live_enabled: bool
    dry_run_only: bool
    daemon_configured: bool = False
    daemon_base_url: str | None = None
    daemon_adapter: str | None = None
    daemon_status: str | None = None
    kill_switch: BrokerKillSwitchState
    capabilities: list[str] = Field(default_factory=list)
    last_submission_at: datetime | None = None
    last_error: str | None = None


class BrokerPosition(BaseModel):
    account_id: str
    symbol: str
    quantity: int
    avg_cost: float
    last_price: float
    market_value: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    updated_at: datetime


class BrokerPositionsResponse(BaseModel):
    account_id: str
    adapter_mode: str
    status: str
    detail: str | None = None
    positions: list[BrokerPosition] = Field(default_factory=list)


class BrokerOrderRecord(BaseModel):
    broker_order_id: str
    account_id: str
    symbol: str
    side: str
    order_type: str
    price: float
    quantity: int
    status: str
    submitted_at: datetime
    routed_order_id: str | None = None
    fill_price: float = 0.0
    fill_quantity: int = 0
    detail: str | None = None


class BrokerOrdersResponse(BaseModel):
    account_id: str
    adapter_mode: str
    status: str
    detail: str | None = None
    orders: list[BrokerOrderRecord] = Field(default_factory=list)


class BrokerAccountSummary(BaseModel):
    account_id: str
    adapter_mode: str
    status: str
    cash: float
    available_cash: float
    market_value: float
    equity: float
    positions_count: int
    updated_at: datetime
    detail: str | None = None


class PaperOrderResponse(BaseModel):
    order_id: str
    status: str
    submitted_at: datetime
    fill_price: float
    fill_quantity: int
    requested_quantity: int
    fees: float = 0.0
    commission: float = 0.0
    transfer_fee: float = 0.0
    stamp_duty: float = 0.0
    slippage_bps: float = 0.0
    detail: str | None = None


class PaperPosition(BaseModel):
    account_id: str
    symbol: str
    quantity: int
    avg_cost: float
    last_price: float
    market_value: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    updated_at: datetime


class PaperPositionsResponse(BaseModel):
    account_id: str
    positions: list[PaperPosition]


class PaperOrderRecord(BaseModel):
    order_id: str
    account_id: str
    symbol: str
    side: str
    order_type: str
    price: float
    quantity: int
    fill_price: float
    fill_quantity: int
    fees: float = 0.0
    commission: float = 0.0
    transfer_fee: float = 0.0
    stamp_duty: float = 0.0
    slippage_bps: float = 0.0
    status: str
    detail: str | None = None
    submitted_at: datetime


class PaperOrdersResponse(BaseModel):
    account_id: str
    orders: list[PaperOrderRecord]


class PaperAccountSummary(BaseModel):
    account_id: str
    initial_cash: float
    cash: float
    market_value: float
    equity: float
    realized_pnl: float
    unrealized_pnl: float
    positions_count: int
    updated_at: datetime


class PaperPerformancePoint(BaseModel):
    ts: datetime
    cash: float
    market_value: float
    equity: float


class PaperPerformanceSummary(BaseModel):
    account_id: str
    initial_cash: float
    equity: float
    total_return_pct: float
    realized_pnl: float
    unrealized_pnl: float
    max_drawdown_pct: float
    total_orders: int
    closed_trade_count: int
    winning_trade_count: int
    losing_trade_count: int
    win_rate: float
    updated_at: datetime


class PaperPerformanceResponse(BaseModel):
    account_id: str
    summary: PaperPerformanceSummary
    curve: list[PaperPerformancePoint]


class BacktestIntelGateConfig(BaseModel):
    enabled: bool = False
    lookback_hours: int = 720
    require_positive_official_event: bool = False
    block_negative_official_event: bool = True
    event_keyword_weight: float = 100.0
    event_source_weight: float = 10.0
    event_recency_window_hours: float = 72.0


class BacktestRunRequest(BaseModel):
    strategy_id: str
    symbol: str | None = None
    symbols: list[str] = Field(default_factory=list)
    start: str | None = None
    end: str | None = None
    capital: float = 1000000.0
    execution: BacktestExecutionConfig | None = None
    intel_gate: BacktestIntelGateConfig | None = None
    constraints: dict[str, float | bool | int | str] = Field(default_factory=dict)


class BacktestTrade(BaseModel):
    ts: datetime
    symbol: str
    side: str
    price: float
    quantity: int
    fees: float
    pnl: float
    reason: str
    gate_event_titles: list[str] = Field(default_factory=list)
    indicator_snapshot: dict[str, float] = Field(default_factory=dict)
    entry_rule: str | None = None
    entry_rule_inputs: dict[str, float] = Field(default_factory=dict)
    holding_days: int | None = None
    exit_rule: str | None = None
    exit_rule_inputs: dict[str, float] = Field(default_factory=dict)


class BacktestEquityPoint(BaseModel):
    ts: datetime
    cash: float
    market_value: float
    equity: float


class BacktestSummary(BaseModel):
    run_id: str
    strategy_id: str
    strategy_meta: StrategyMeta | None = None
    strategy_version: str | None = None
    symbol: str | None = None
    symbols: list[str] = Field(default_factory=list)
    scope: str
    start: str | None = None
    end: str | None = None
    initial_capital: float
    ending_cash: float
    ending_market_value: float
    ending_equity: float
    total_return_pct: float
    max_drawdown_pct: float
    total_trades: int
    closed_trade_count: int
    winning_trade_count: int
    losing_trade_count: int
    win_rate: float
    gate_blocked_entry_count: int = 0
    execution_rule_version: str | None = None
    execution_config_source: str | None = None
    execution_params: dict[str, float | int] = Field(default_factory=dict)
    intel_gate_formula_version: str | None = None
    intel_gate_config_source: str | None = None
    intel_gate_scoring_params: dict[str, float] = Field(default_factory=dict)
    updated_at: datetime


class BacktestSymbolContribution(BaseModel):
    symbol: str
    realized_pnl: float
    unrealized_pnl: float
    total_pnl: float
    total_trades: int
    closed_trade_count: int
    blocked_entry_count: int


class BacktestGateEventRef(BaseModel):
    title: str
    source_name: str
    source_url: str
    published_at: datetime
    event_type: str
    sentiment: str
    impact_direction: ImpactDirection
    confidence: Confidence
    age_hours: float
    selection_rank: int
    selection_reason: str
    keyword_score: int
    source_priority: int
    recency_score: float
    selection_score: float


class BacktestBlockedEntry(BaseModel):
    ts: datetime
    symbol: str
    price: float
    reason: str
    blocked_rule: str | None = None
    blocked_rule_inputs: dict[str, float] = Field(default_factory=dict)
    gate_event_titles: list[str] = Field(default_factory=list)
    gate_events: list[BacktestGateEventRef] = Field(default_factory=list)
    indicator_snapshot: dict[str, float] = Field(default_factory=dict)


class BacktestRunResponse(BaseModel):
    summary: BacktestSummary
    trades: list[BacktestTrade]
    equity_curve: list[BacktestEquityPoint]
    symbol_contributions: list[BacktestSymbolContribution] = Field(default_factory=list)
    blocked_entries: list[BacktestBlockedEntry] = Field(default_factory=list)


class HealthResponse(BaseModel):
    service: str
    status: str
    timezone: str
    market_data_provider: str
    intel_provider: str
    provider_mode: str
    intel_scheduler_enabled: bool = False
    intel_scheduler_running: bool = False
    intel_event_count: int = 0
    watchlist_scheduler_enabled: bool = False
    watchlist_scheduler_running: bool = False
    watchlist_item_count: int = 0
    watchlist_alert_count: int = 0
    broker_adapter_mode: str | None = None
    broker_kill_switch_active: bool = False
    market_quote_selected_source: str | None = None
    market_bars_selected_source: str | None = None
    market_quote_recent_switch_count: int = 0
    market_bars_recent_switch_count: int = 0


class OpsSubsystemStatus(BaseModel):
    name: str
    status: str
    detail: str | None = None
    metrics: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class OpsStatusResponse(BaseModel):
    service: str
    generated_at: datetime
    overall_status: str
    subsystems: list[OpsSubsystemStatus] = Field(default_factory=list)


class ProviderCheck(BaseModel):
    name: str
    status: str
    error_code: str | None = None
    detail: str | None = None


class MarketProviderStatus(BaseModel):
    provider_mode: str
    effective_provider: str
    token_configured: bool
    probe_symbol: str
    quote_ready: bool = False
    quote_block_reason: str | None = None
    intraday_ready: bool = False
    intraday_block_reason: str | None = None
    daily_ready: bool = False
    daily_block_reason: str | None = None
    checks: list[ProviderCheck]


class MarketDecisionStatus(BaseModel):
    provider_mode: str
    effective_provider: str
    audit_window_seconds: int
    quote_recent_switch_count: int
    bars_recent_switch_count: int
    quote_selected_source: str | None = None
    bars_selected_source: str | None = None
    quote_selected_source_streak: int = 0
    bars_selected_source_streak: int = 0
    quote_source_audit: list[ProviderSourceAudit] = Field(default_factory=list)
    bars_source_audit: list[ProviderSourceAudit] = Field(default_factory=list)
