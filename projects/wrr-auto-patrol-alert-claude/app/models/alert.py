from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class AlertStatus(str, Enum):
    OK = "ok"
    FAILING = "failing"  # below consecutive-failure threshold
    ALERTING = "alerting"  # threshold reached, alert sent
    SILENCED = "silenced"  # suppressed during silent window


class AlertState(BaseModel):
    """Per-rule alert state tracked in memory."""

    rule_id: str
    service_name: str
    status: AlertStatus = AlertStatus.OK
    consecutive_failures: int = 0
    first_failure_at: datetime | None = None
    last_failure_at: datetime | None = None
    last_alert_sent_at: datetime | None = None
    last_success_at: datetime | None = None
    failure_details: list[str] = Field(default_factory=list)


class AlertEvent(BaseModel):
    """A single alert event queued for aggregation."""

    rule_id: str
    service_name: str
    event_type: str  # "failure" | "recovery"
    summary: str
    details: list[str] = Field(default_factory=list)
    consecutive_failures: int = 0
    first_failure_at: datetime | None = None
    created_at: datetime


class AggregatedAlert(BaseModel):
    """Bundled alert ready for dispatch to channels."""

    events: list[AlertEvent]
    service_count: int
    total_failures: int
    aggregation_window_start: datetime
    aggregation_window_end: datetime
