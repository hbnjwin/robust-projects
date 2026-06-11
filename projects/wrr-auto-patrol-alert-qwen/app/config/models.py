"""Pydantic models for patrol configuration."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class HttpMethod(str, Enum):
    GET = "GET"
    HEAD = "HEAD"
    POST = "POST"


class ExpectConfig(BaseModel):
    """Expected conditions for a health check."""

    status_code: int = 200
    timeout_ms: int = Field(default=5000, ge=100, le=60000)
    body_contains: Optional[str] = None


class RuleConfig(BaseModel):
    """A single patrol inspection rule."""

    id: str = Field(..., min_length=1, description="Unique rule identifier")
    name: str = Field(..., min_length=1, description="Human-readable rule name")
    service: str = Field(..., min_length=1, description="Service name for grouping")
    url: str = Field(..., min_length=1, description="Health check URL")
    method: HttpMethod = HttpMethod.GET
    interval_seconds: int = Field(default=60, ge=10, le=3600)
    expect: ExpectConfig = Field(default_factory=ExpectConfig)
    enabled: bool = True
    headers: Optional[dict[str, str]] = None


class MutePeriodConfig(BaseModel):
    """A mute/quiet period during which alerts are suppressed."""

    name: str = Field(..., min_length=1)
    # Recurring mute: cron-based
    cron: Optional[str] = None
    duration_minutes: Optional[int] = Field(default=None, ge=1, le=1440)
    # One-time mute: fixed datetime range
    start: Optional[datetime] = None
    end: Optional[datetime] = None

    def is_recurring(self) -> bool:
        return self.cron is not None

    def is_one_time(self) -> bool:
        return self.start is not None and self.end is not None


class AggregationConfig(BaseModel):
    """Alert aggregation settings."""

    dedup_window_seconds: int = Field(default=300, ge=10, description="Dedup time window")
    aggregate_window_seconds: int = Field(default=180, ge=10, description="Grouping window")
    group_by: str = Field(default="service", description="Field to group alerts by")
    suppress_after_count: int = Field(default=5, ge=1, description="Consecutive failures before suppression")
    suppress_interval_seconds: int = Field(default=1800, ge=60, description="Suppression cooldown")


class GlobalConfig(BaseModel):
    """Global settings."""

    alert_webhook: str = Field(..., description="DingTalk webhook URL")
    default_interval_seconds: int = Field(default=60, ge=10, le=3600)


class PatrolConfig(BaseModel):
    """Root patrol configuration model."""

    global_config: GlobalConfig = Field(alias="global")
    mute_periods: list[MutePeriodConfig] = Field(default_factory=list)
    aggregation: AggregationConfig = Field(default_factory=AggregationConfig)
    rules: list[RuleConfig] = Field(default_factory=list)

    model_config = {"populate_by_name": True}

    def get_enabled_rules(self) -> list[RuleConfig]:
        return [r for r in self.rules if r.enabled]

    def get_rule_by_id(self, rule_id: str) -> Optional[RuleConfig]:
        for r in self.rules:
            if r.id == rule_id:
                return r
        return None
