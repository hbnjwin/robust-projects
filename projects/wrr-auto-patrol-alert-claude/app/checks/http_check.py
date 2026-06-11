from __future__ import annotations

import time
from datetime import datetime, timezone

import httpx

from app.checks.base import BaseCheck
from app.models.result import CheckResult, CheckStatus
from app.models.rule import PatrolRule


class HttpCheck(BaseCheck):
    async def execute(self, rule: PatrolRule, client: httpx.AsyncClient) -> CheckResult:
        start = time.monotonic()
        try:
            resp = await client.get(rule.target, timeout=rule.timeout_seconds)
            elapsed = (time.monotonic() - start) * 1000

            if resp.status_code == rule.expected_status:
                status = CheckStatus.SUCCESS
                error = None
            else:
                status = CheckStatus.FAILURE
                error = f"expected status {rule.expected_status}, got {resp.status_code}"

            return CheckResult(
                rule_id=rule.rule_id,
                service_name=rule.service_name,
                check_type=rule.check_type.value,
                target=rule.target,
                status=status,
                response_time_ms=round(elapsed, 2),
                status_code=resp.status_code,
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
