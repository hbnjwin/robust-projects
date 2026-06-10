"""Patrol inspection engine — orchestrates health checks and feeds results to the alert pipeline."""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from app.checker.http_checker import CheckResult, execute_http_check
from app.config.models import RuleConfig

if TYPE_CHECKING:
    from app.alert.aggregator import AlertAggregator

logger = logging.getLogger(__name__)

# Maximum number of recent results to keep in memory
MAX_RESULTS = 500


@dataclass
class ServiceStatus:
    """Current status of a monitored service."""

    service: str
    rule_id: str
    rule_name: str
    is_healthy: bool = True
    last_check: Optional[datetime] = None
    last_success: Optional[datetime] = None
    consecutive_failures: int = 0
    response_time_ms: float = 0.0
    last_error: Optional[str] = None


class PatrolEngine:
    """Core inspection engine that runs checks and reports failures to the aggregator."""

    def __init__(self, aggregator: AlertAggregator):
        self._aggregator = aggregator
        self._statuses: dict[str, ServiceStatus] = {}  # rule_id -> status
        self._recent_results: deque[CheckResult] = deque(maxlen=MAX_RESULTS)

    @property
    def statuses(self) -> dict[str, ServiceStatus]:
        return dict(self._statuses)

    @property
    def recent_results(self) -> list[CheckResult]:
        return list(self._recent_results)

    def sync_rules(self, rules: list[RuleConfig]) -> None:
        """Update internal status tracking to match current rules."""
        current_ids = {r.id for r in rules}
        # Remove statuses for deleted rules
        removed = set(self._statuses.keys()) - current_ids
        for rid in removed:
            del self._statuses[rid]
        # Add statuses for new rules
        for rule in rules:
            if rule.id not in self._statuses:
                self._statuses[rule.id] = ServiceStatus(
                    service=rule.service,
                    rule_id=rule.id,
                    rule_name=rule.name,
                )

    async def run_check(self, rule: RuleConfig) -> CheckResult:
        """Run a single health check and process the result."""
        result = await execute_http_check(rule)
        self._recent_results.append(result)
        self._update_status(result)

        if not result.success:
            await self._aggregator.on_check_failure(result)
        else:
            # Recovery: if service was previously down, send recovery alert
            status = self._statuses.get(result.rule_id)
            if status and status.consecutive_failures > 0:
                await self._aggregator.on_check_recovery(result)

        return result

    def _update_status(self, result: CheckResult) -> None:
        """Update service status based on check result."""
        if result.rule_id not in self._statuses:
            self._statuses[result.rule_id] = ServiceStatus(
                service=result.service,
                rule_id=result.rule_id,
                rule_name=result.rule_name,
            )

        status = self._statuses[result.rule_id]
        status.last_check = result.timestamp
        status.response_time_ms = result.response_time_ms

        if result.success:
            status.is_healthy = True
            status.consecutive_failures = 0
            status.last_success = result.timestamp
            status.last_error = None
        else:
            status.is_healthy = False
            status.consecutive_failures += 1
            status.last_error = result.error
