from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class CheckStatus(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    ERROR = "error"


class CheckResult(BaseModel):
    """Result of a single health-check execution."""

    rule_id: str
    service_name: str
    check_type: str
    target: str
    status: CheckStatus
    response_time_ms: float | None = None
    status_code: int | None = None
    error_message: str | None = None
    metric_value: float | None = None
    checked_at: datetime
