from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class CheckType(str, Enum):
    HTTP = "http"
    TCP = "tcp"
    METRIC = "metric"


class SilentWindow(BaseModel):
    """Time window during which alerts are suppressed."""

    start: str  # HH:MM format, e.g. "00:00"
    end: str  # HH:MM format, e.g. "08:00"
    days: Optional[list[int]] = None  # 0=Mon..6=Sun, None means every day


class AlertChannelConfig(BaseModel):
    """Configuration for an alert notification channel."""

    channel_type: str  # "dingtalk"
    webhook_url: str
    secret: Optional[str] = None


class PatrolRule(BaseModel):
    """A single patrol (health-check) rule definition."""

    rule_id: str
    service_name: str
    check_type: CheckType
    target: str  # URL or host:port
    interval_seconds: int = 60
    timeout_seconds: float = 10.0
    consecutive_failures_threshold: int = 3
    enabled: bool = True

    # HTTP check
    expected_status: int = 200

    # Metric check
    metric_path: Optional[str] = None  # dot-notation JSON path
    metric_operator: Optional[str] = None  # ">", "<", ">=", "<=", "=="
    metric_threshold: Optional[float] = None

    alert_channels: list[AlertChannelConfig] = Field(default_factory=list)
    silent_windows: list[SilentWindow] = Field(default_factory=list)
    tags: dict[str, str] = Field(default_factory=dict)
