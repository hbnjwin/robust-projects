from datetime import datetime

from pydantic import BaseModel, Field


class TerminalProcessState(BaseModel):
    process_name: str | None = None
    pid_file_path: str | None = None
    pid: int | None = None
    process_detected: bool = False
    pid_file_present: bool = False


class TerminalSessionArtifactState(BaseModel):
    session_file_path: str | None = None
    session_file_present: bool = False
    session_state: str
    connected: bool
    logged_in: bool
    last_heartbeat_at: datetime | None = None


class TerminalLockState(BaseModel):
    lock_file_path: str | None = None
    lock_present: bool = False
    lock_owned: bool = False
    singleton_ok: bool = False
    operator_id: str | None = None
    adapter: str | None = None
    updated_at: datetime | None = None


class TerminalHostState(BaseModel):
    adapter: str
    terminal_path: str | None = None
    terminal_path_exists: bool = False
    account_alias: str | None = None
    credential_profile: str | None = None
    start_command: str | None = None
    command_argv: list[str] = Field(default_factory=list)
    start_command_configured: bool = False
    working_directory: str | None = None
    working_directory_exists: bool = False
    process: TerminalProcessState
    session_artifact: TerminalSessionArtifactState
    lock: TerminalLockState


class TerminalLaunchPlan(BaseModel):
    adapter: str
    status: str
    detail: str | None = None
    dry_run: bool = True
    runnable: bool = False
    requires_operator_action: bool = True
    command: str | None = None
    command_argv: list[str] = Field(default_factory=list)
    terminal_path: str | None = None
    working_directory: str | None = None
    account_alias: str | None = None
    credential_profile: str | None = None
    pid_file_path: str | None = None
    session_file_path: str | None = None
    lock_file_path: str | None = None
    singleton_required: bool = False
    blocked_reasons: list[str] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)


class TerminalSessionStatus(BaseModel):
    adapter: str
    session_state: str
    health_state: str = "unknown"
    connected: bool
    logged_in: bool
    terminal_path: str | None = None
    account_alias: str | None = None
    credential_profile: str | None = None
    process_name: str | None = None
    pid_file_path: str | None = None
    session_file_path: str | None = None
    lock_file_path: str | None = None
    start_command: str | None = None
    working_directory: str | None = None
    pid: int | None = None
    process_detected: bool = False
    pid_file_present: bool = False
    session_file_present: bool = False
    lock_present: bool = False
    singleton_ok: bool = False
    lock_owned: bool = False
    start_command_configured: bool = False
    last_heartbeat_at: datetime | None = None
    detail: str | None = None
    host_state: TerminalHostState | None = None


class TerminalSessionControlRequest(BaseModel):
    operator_id: str | None = None
    terminal_path: str | None = None
    account_alias: str | None = None
    credential_profile: str | None = None
    reason: str | None = None


class TerminalSessionControlResponse(BaseModel):
    action: str
    status: str
    detail: str | None = None
    session: TerminalSessionStatus
    launch_plan: TerminalLaunchPlan | None = None


class TerminalPreflightCheck(BaseModel):
    name: str
    status: str
    detail: str | None = None


class TerminalPreflightResponse(BaseModel):
    adapter: str
    status: str
    checks: list[TerminalPreflightCheck] = Field(default_factory=list)
    session: TerminalSessionStatus


class DaemonStatusResponse(BaseModel):
    service: str
    status: str
    adapter: str
    terminal_adapter: str
    live_routing_enabled: bool
    order_count: int = 0
    position_count: int = 0
    last_error: str | None = None
    session: TerminalSessionStatus | None = None


class SubmitOrderRequest(BaseModel):
    account_id: str
    symbol: str
    side: str
    order_type: str
    price: float
    quantity: int
    adapter: str | None = None


class CancelOrderRequest(BaseModel):
    account_id: str
    broker_order_id: str
    reason: str | None = None
    adapter: str | None = None


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


class ProcessOrdersRequest(BaseModel):
    account_id: str | None = None
    limit: int = 50


class ProcessOrdersResponse(BaseModel):
    status: str
    processed_count: int
    filled_count: int
    rejected_count: int
    remaining_queued_count: int
    updated_order_ids: list[str] = Field(default_factory=list)
