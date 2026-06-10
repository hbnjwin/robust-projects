from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone

import httpx

from app.checks.base import BaseCheck
from app.models.result import CheckResult, CheckStatus
from app.models.rule import PatrolRule


class TcpCheck(BaseCheck):
    async def execute(self, rule: PatrolRule, client: httpx.AsyncClient) -> CheckResult:
        # Parse host:port from target
        parts = rule.target.rsplit(":", 1)
        if len(parts) != 2:
            return CheckResult(
                rule_id=rule.rule_id,
                service_name=rule.service_name,
                check_type=rule.check_type.value,
                target=rule.target,
                status=CheckStatus.ERROR,
                error_message=f"invalid target format, expected host:port, got '{rule.target}'",
                checked_at=datetime.now(timezone.utc),
            )

        host = parts[0]
        try:
            port = int(parts[1])
        except ValueError:
            return CheckResult(
                rule_id=rule.rule_id,
                service_name=rule.service_name,
                check_type=rule.check_type.value,
                target=rule.target,
                status=CheckStatus.ERROR,
                error_message=f"invalid port: {parts[1]}",
                checked_at=datetime.now(timezone.utc),
            )

        start = time.monotonic()
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=rule.timeout_seconds,
            )
            elapsed = (time.monotonic() - start) * 1000
            writer.close()
            await writer.wait_closed()

            return CheckResult(
                rule_id=rule.rule_id,
                service_name=rule.service_name,
                check_type=rule.check_type.value,
                target=rule.target,
                status=CheckStatus.SUCCESS,
                response_time_ms=round(elapsed, 2),
                checked_at=datetime.now(timezone.utc),
            )
        except asyncio.TimeoutError:
            elapsed = (time.monotonic() - start) * 1000
            return CheckResult(
                rule_id=rule.rule_id,
                service_name=rule.service_name,
                check_type=rule.check_type.value,
                target=rule.target,
                status=CheckStatus.TIMEOUT,
                response_time_ms=round(elapsed, 2),
                error_message=f"TCP connection timed out after {rule.timeout_seconds}s",
                checked_at=datetime.now(timezone.utc),
            )
        except Exception as e:
            elapsed = (time.monotonic() - start) * 1000
            return CheckResult(
                rule_id=rule.rule_id,
                service_name=rule.service_name,
                check_type=rule.check_type.value,
                target=rule.target,
                status=CheckStatus.FAILURE,
                response_time_ms=round(elapsed, 2),
                error_message=str(e),
                checked_at=datetime.now(timezone.utc),
            )
