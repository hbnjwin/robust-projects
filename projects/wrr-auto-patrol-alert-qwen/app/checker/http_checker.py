"""HTTP health check implementation."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import httpx

from app.config.models import RuleConfig

logger = logging.getLogger(__name__)


@dataclass
class CheckResult:
    """Result of a single health check execution."""

    rule_id: str
    service: str
    rule_name: str
    success: bool
    status_code: Optional[int] = None
    response_time_ms: float = 0.0
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


async def execute_http_check(rule: RuleConfig) -> CheckResult:
    """Execute an HTTP health check for the given rule."""
    timeout_s = rule.expect.timeout_ms / 1000.0
    start = time.monotonic()

    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            resp = await client.request(
                method=rule.method.value,
                url=rule.url,
                headers=rule.headers,
            )

        elapsed_ms = (time.monotonic() - start) * 1000

        # Check status code
        if resp.status_code != rule.expect.status_code:
            return CheckResult(
                rule_id=rule.id,
                service=rule.service,
                rule_name=rule.name,
                success=False,
                status_code=resp.status_code,
                response_time_ms=elapsed_ms,
                error=f"Expected status {rule.expect.status_code}, got {resp.status_code}",
            )

        # Check body content
        if rule.expect.body_contains:
            body = resp.text
            if rule.expect.body_contains not in body:
                return CheckResult(
                    rule_id=rule.id,
                    service=rule.service,
                    rule_name=rule.name,
                    success=False,
                    status_code=resp.status_code,
                    response_time_ms=elapsed_ms,
                    error=f"Response body missing expected content: '{rule.expect.body_contains}'",
                )

        return CheckResult(
            rule_id=rule.id,
            service=rule.service,
            rule_name=rule.name,
            success=True,
            status_code=resp.status_code,
            response_time_ms=elapsed_ms,
        )

    except httpx.TimeoutException:
        elapsed_ms = (time.monotonic() - start) * 1000
        return CheckResult(
            rule_id=rule.id,
            service=rule.service,
            rule_name=rule.name,
            success=False,
            response_time_ms=elapsed_ms,
            error=f"Request timed out after {rule.expect.timeout_ms}ms",
        )
    except httpx.ConnectError as e:
        elapsed_ms = (time.monotonic() - start) * 1000
        return CheckResult(
            rule_id=rule.id,
            service=rule.service,
            rule_name=rule.name,
            success=False,
            response_time_ms=elapsed_ms,
            error=f"Connection failed: {e}",
        )
    except Exception as e:
        elapsed_ms = (time.monotonic() - start) * 1000
        logger.exception("Unexpected error checking %s", rule.id)
        return CheckResult(
            rule_id=rule.id,
            service=rule.service,
            rule_name=rule.name,
            success=False,
            response_time_ms=elapsed_ms,
            error=f"Unexpected error: {e}",
        )
