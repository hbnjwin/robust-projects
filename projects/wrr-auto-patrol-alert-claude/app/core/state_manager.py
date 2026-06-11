from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from app.models.alert import AlertEvent, AlertState, AlertStatus
from app.models.result import CheckResult, CheckStatus
from app.models.rule import PatrolRule

logger = logging.getLogger(__name__)

_MAX_DETAIL_HISTORY = 10


class StateManager:
    """Tracks per-rule alert state. Implements consecutive-failure gating to prevent alert storms."""

    def __init__(self) -> None:
        self._states: dict[str, AlertState] = {}
        self._lock = asyncio.Lock()

    async def process_result(
        self, result: CheckResult, rule: PatrolRule
    ) -> AlertEvent | None:
        """Process a check result, update state, return an AlertEvent if a threshold is crossed or recovery detected."""
        async with self._lock:
            state = self._states.get(rule.rule_id)
            if state is None:
                state = AlertState(
                    rule_id=rule.rule_id, service_name=rule.service_name
                )
                self._states[rule.rule_id] = state

            now = datetime.now(timezone.utc)

            if result.status == CheckStatus.SUCCESS:
                return self._handle_success(state, now)
            else:
                return self._handle_failure(state, rule, result, now)

    def _handle_success(
        self, state: AlertState, now: datetime
    ) -> AlertEvent | None:
        event = None
        prev_status = state.status

        if prev_status in (AlertStatus.ALERTING, AlertStatus.SILENCED):
            # Service recovered — generate recovery event
            event = AlertEvent(
                rule_id=state.rule_id,
                service_name=state.service_name,
                event_type="recovery",
                summary=f"Service recovered after {state.consecutive_failures} consecutive failures",
                details=state.failure_details[-3:],
                consecutive_failures=state.consecutive_failures,
                first_failure_at=state.first_failure_at,
                created_at=now,
            )
            logger.info(
                "Service %s recovered after %d failures",
                state.service_name,
                state.consecutive_failures,
            )

        # Reset state
        state.status = AlertStatus.OK
        state.consecutive_failures = 0
        state.first_failure_at = None
        state.last_failure_at = None
        state.last_success_at = now
        state.failure_details.clear()

        return event

    def _handle_failure(
        self,
        state: AlertState,
        rule: PatrolRule,
        result: CheckResult,
        now: datetime,
    ) -> AlertEvent | None:
        state.consecutive_failures += 1
        state.last_failure_at = now
        if state.first_failure_at is None:
            state.first_failure_at = now

        detail = result.error_message or f"{result.status.value}: {result.target}"
        state.failure_details.append(detail)
        if len(state.failure_details) > _MAX_DETAIL_HISTORY:
            state.failure_details = state.failure_details[-_MAX_DETAIL_HISTORY:]

        threshold = rule.consecutive_failures_threshold

        if state.consecutive_failures < threshold:
            state.status = AlertStatus.FAILING
            logger.debug(
                "Service %s failing (%d/%d)",
                state.service_name,
                state.consecutive_failures,
                threshold,
            )
            return None

        if state.status == AlertStatus.ALERTING:
            # Already alerted, suppress duplicate
            return None

        # Threshold crossed — generate failure alert
        state.status = AlertStatus.ALERTING
        state.last_alert_sent_at = now

        event = AlertEvent(
            rule_id=state.rule_id,
            service_name=state.service_name,
            event_type="failure",
            summary=(
                f"Health check failed {state.consecutive_failures} times consecutively"
            ),
            details=state.failure_details[-3:],
            consecutive_failures=state.consecutive_failures,
            first_failure_at=state.first_failure_at,
            created_at=now,
        )
        logger.warning(
            "Service %s reached failure threshold (%d/%d)",
            state.service_name,
            state.consecutive_failures,
            threshold,
        )
        return event

    async def get_state(self, rule_id: str) -> AlertState | None:
        async with self._lock:
            return self._states.get(rule_id)

    async def get_all_states(self) -> dict[str, AlertState]:
        async with self._lock:
            return {k: v.model_copy() for k, v in self._states.items()}

    async def remove_state(self, rule_id: str) -> None:
        async with self._lock:
            self._states.pop(rule_id, None)
