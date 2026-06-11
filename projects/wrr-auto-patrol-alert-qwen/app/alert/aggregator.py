"""Alert aggregator — dedup, grouping, and suppression to prevent alert storms."""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from app.alert.dingtalk import DingTalkNotifier
from app.alert.mute import MuteManager
from app.checker.http_checker import CheckResult
from app.config.models import AggregationConfig

logger = logging.getLogger(__name__)


@dataclass
class _DedupEntry:
    """Tracks dedup state for a single alert key."""
    first_seen: float
    last_sent: float = 0.0
    count: int = 0
    consecutive_failures: int = 0
    last_suppress_sent: float = 0.0


@dataclass
class _AggregateBuffer:
    """Buffer for collecting alerts within an aggregation window."""
    alerts: list[dict] = field(default_factory=list)
    window_start: float = 0.0
    timer_task: Optional[asyncio.Task] = None


class AlertAggregator:
    """
    Three-stage alert pipeline:
    1. Dedup: same rule_id within dedup_window -> only first alert passes through
    2. Grouping: alerts within aggregate_window grouped by service -> merged into one message
    3. Suppression: after N consecutive failures, only send every suppress_interval
    """

    def __init__(
        self,
        notifier: DingTalkNotifier,
        mute_manager: MuteManager,
        config: AggregationConfig,
    ):
        self._notifier = notifier
        self._mute = mute_manager
        self._config = config
        self._dedup: dict[str, _DedupEntry] = {}  # key: rule_id
        self._agg_buffer: dict[str, _AggregateBuffer] = defaultdict(_AggregateBuffer)  # key: group_by value
        self._alert_history: list[dict] = []  # recent alert records for API
        self._lock = asyncio.Lock()

    def update_config(self, config: AggregationConfig) -> None:
        self._config = config

    def update_mute_manager(self, mute_manager: MuteManager) -> None:
        self._mute = mute_manager

    async def on_check_failure(self, result: CheckResult) -> None:
        """Process a failed health check result through the alert pipeline."""
        alert_data = {
            "rule_id": result.rule_id,
            "rule_name": result.rule_name,
            "service": result.service,
            "error": result.error,
            "status_code": result.status_code,
            "response_time_ms": result.response_time_ms,
            "timestamp": result.timestamp.isoformat(),
        }

        # Update dedup tracking
        async with self._lock:
            entry = self._dedup.get(result.rule_id)
            now = time.monotonic()

            if entry is None:
                entry = _DedupEntry(first_seen=now)
                self._dedup[result.rule_id] = entry

            entry.count += 1
            entry.consecutive_failures += 1

            # Stage 1: Dedup — same alert within dedup_window is suppressed
            if (now - entry.last_sent) < self._config.dedup_window_seconds:
                logger.debug("Dedup: suppressed alert for %s (within %ds window)", result.rule_id, self._config.dedup_window_seconds)
                return

            # Stage 3: Suppression — after N failures, only send at suppress_interval
            if entry.consecutive_failures > self._config.suppress_after_count:
                if (now - entry.last_suppress_sent) < self._config.suppress_interval_seconds:
                    logger.debug(
                        "Suppress: %s has %d consecutive failures, waiting for suppress interval",
                        result.rule_id,
                        entry.consecutive_failures,
                    )
                    return
                entry.last_suppress_sent = now
                alert_data["suppressed"] = True
                alert_data["consecutive_failures"] = entry.consecutive_failures
                alert_data["error"] = (
                    f"[持续异常] {result.error} (已连续失败{entry.consecutive_failures}次)"
                )

            entry.last_sent = now

        alert_data["consecutive_failures"] = entry.consecutive_failures

        # Record in history
        self._record_alert(alert_data)

        # Check mute period
        if self._mute.is_muted():
            self._mute.buffer_alert(alert_data)
            logger.info("Muted: buffered alert for %s", result.rule_id)
            return

        # Stage 2: Aggregation — buffer alerts and flush as group
        await self._buffer_and_flush(alert_data)

    async def on_check_recovery(self, result: CheckResult) -> None:
        """Handle service recovery."""
        async with self._lock:
            entry = self._dedup.get(result.rule_id)
            if entry:
                entry.consecutive_failures = 0
                entry.count = 0

        # Only notify if the service was actually down
        if not self._mute.is_muted():
            await self._notifier.send_recovery(result.service, result.rule_name)

    async def check_mute_transition(self) -> None:
        """Called periodically to check if a mute period just ended and flush buffered alerts."""
        flushed = self._mute.check_mute_transition()
        if flushed:
            await self._notifier.send_mute_summary(flushed)

    async def _buffer_and_flush(self, alert_data: dict) -> None:
        """Buffer alert into aggregation group; flush when window expires."""
        group_key = alert_data.get(self._config.group_by, alert_data.get("service", "default"))

        async with self._lock:
            buf = self._agg_buffer[group_key]
            buf.alerts.append(alert_data)

            if buf.window_start == 0:
                buf.window_start = time.monotonic()

            # If only one alert in buffer, start the aggregation window timer
            if len(buf.alerts) == 1:
                buf.timer_task = asyncio.create_task(
                    self._flush_after_window(group_key)
                )

    async def _flush_after_window(self, group_key: str) -> None:
        """Wait for the aggregation window then flush all buffered alerts for the group."""
        await asyncio.sleep(self._config.aggregate_window_seconds)

        async with self._lock:
            buf = self._agg_buffer.get(group_key)
            if not buf or not buf.alerts:
                return
            alerts = buf.alerts
            buf.alerts = []
            buf.window_start = 0
            buf.timer_task = None

        # Send aggregated notification
        await self._notifier.send_aggregated_alert(alerts)

    def _record_alert(self, alert_data: dict) -> None:
        """Keep recent alert history (for API)."""
        self._alert_history.append(alert_data)
        if len(self._alert_history) > 100:
            self._alert_history = self._alert_history[-100:]

    def get_recent_alerts(self, limit: int = 50) -> list[dict]:
        return self._alert_history[-limit:]
