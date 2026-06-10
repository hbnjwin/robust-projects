from __future__ import annotations

import operator
import time
from datetime import datetime, timezone
from typing import Any

import httpx

from app.checks.base import BaseCheck
from app.models.result import CheckResult, CheckStatus
from app.models.rule import PatrolRule

_OPERATORS = {
    ">": operator.gt,
    "<": operator.lt,
    ">=": operator.ge,
    "<=": operator.le,
    "==": operator.eq,
}


def _extract_value(data: Any, path: str) -> Any:
    """Traverse a nested dict/list via dot-notation path (e.g. 'data.cpu_usage')."""
    for key in path.split("."):
        if isinstance(data, dict):
            data = data[key]
        elif isinstance(data, list):
            data = data[int(key)]
        else:
            raise KeyError(f"cannot traverse into {type(data).__name__} with key '{key}'")
    return data


class MetricCheck(BaseCheck):
    async def execute(self, rule: PatrolRule, client: httpx.AsyncClient) -> CheckResult:
        if not rule.metric_path or not rule.metric_operator or rule.metric_threshold is None:
            return CheckResult(
                rule_id=rule.rule_id,
                service_name=rule.service_name,
                check_type=rule.check_type.value,
                target=rule.target,
                status=CheckStatus.ERROR,
                error_message="metric_path, metric_operator, and metric_threshold are required",
                checked_at=datetime.now(timezone.utc),
            )

        op_func = _OPERATORS.get(rule.metric_operator)
        if op_func is None:
            return CheckResult(
                rule_id=rule.rule_id,
                service_name=rule.service_name,
                check_type=rule.check_type.value,
                target=rule.target,
                status=CheckStatus.ERROR,
                error_message=f"unsupported operator: {rule.metric_operator}",
                checked_at=datetime.now(timezone.utc),
            )

        start = time.monotonic()
        try:
            resp = await client.get(rule.target, timeout=rule.timeout_seconds)
            elapsed = (time.monotonic() - start) * 1000
            data = resp.json()
            value = float(_extract_value(data, rule.metric_path))

            # op_func(value, threshold) — e.g. value > 90 means FAILURE
            if op_func(value, rule.metric_threshold):
                status = CheckStatus.FAILURE
                error = (
                    f"metric {rule.metric_path}={value} "
                    f"{rule.metric_operator} {rule.metric_threshold}"
                )
            else:
                status = CheckStatus.SUCCESS
                error = None

            return CheckResult(
                rule_id=rule.rule_id,
                service_name=rule.service_name,
                check_type=rule.check_type.value,
                target=rule.target,
                status=status,
                response_time_ms=round(elapsed, 2),
                status_code=resp.status_code,
                metric_value=value,
                error_message=error,
                checked_at=datetime.now(timezone.utc),
            )
        except httpx.TimeoutException:
            elapsed = (time.monotonic() - start) * 1000
            return CheckResult(
                rule_id=rule.rule_id,
                service_name=rule.service_name,
                check_type=rule.check_type.value,
                target=rule.target,
                status=CheckStatus.TIMEOUT,
                response_time_ms=round(elapsed, 2),
                error_message=f"request timed out after {rule.timeout_seconds}s",
                checked_at=datetime.now(timezone.utc),
            )
        except Exception as e:
            elapsed = (time.monotonic() - start) * 1000
            return CheckResult(
                rule_id=rule.rule_id,
                service_name=rule.service_name,
                check_type=rule.check_type.value,
                target=rule.target,
                status=CheckStatus.ERROR,
                response_time_ms=round(elapsed, 2),
                error_message=str(e),
                checked_at=datetime.now(timezone.utc),
            )
