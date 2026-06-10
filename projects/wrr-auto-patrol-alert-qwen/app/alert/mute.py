"""Mute period manager — determines whether alerts should be suppressed based on time windows."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

from app.config.models import MutePeriodConfig

logger = logging.getLogger(__name__)


class MuteManager:
    """Manages mute periods and determines if alerts should be suppressed."""

    def __init__(self, mute_periods: list[MutePeriodConfig] | None = None):
        self._periods: list[MutePeriodConfig] = mute_periods or []
        # Buffer for alerts during mute periods (flushed when mute ends)
        self._buffered_alerts: list[dict] = []
        self._was_muted: bool = False

    def update_periods(self, periods: list[MutePeriodConfig]) -> None:
        self._periods = periods

    def is_muted(self, now: datetime | None = None) -> bool:
        """Check if the current time falls within any mute period."""
        now = now or datetime.now()
        for period in self._periods:
            if self._is_in_period(period, now):
                return True
        return False

    def buffer_alert(self, alert_data: dict) -> None:
        """Buffer an alert during a mute period."""
        self._buffered_alerts.append(alert_data)

    def flush_buffer(self) -> list[dict]:
        """Return and clear all buffered alerts (called when mute period ends)."""
        alerts = self._buffered_alerts
        self._buffered_alerts = []
        return alerts

    def check_mute_transition(self, now: datetime | None = None) -> list[dict] | None:
        """Check if we just exited a mute period and return buffered alerts if so."""
        now = now or datetime.now()
        currently_muted = self.is_muted(now)

        if self._was_muted and not currently_muted:
            # Transitioned from muted -> not muted: flush buffer
            self._was_muted = currently_muted
            buffered = self.flush_buffer()
            if buffered:
                logger.info("Mute period ended, flushing %d buffered alerts", len(buffered))
            return buffered

        self._was_muted = currently_muted
        return None

    def get_active_mute_period(self, now: datetime | None = None) -> Optional[MutePeriodConfig]:
        """Get the currently active mute period, if any."""
        now = now or datetime.now()
        for period in self._periods:
            if self._is_in_period(period, now):
                return period
        return None

    @staticmethod
    def _is_in_period(period: MutePeriodConfig, now: datetime) -> bool:
        """Check if `now` falls within the given mute period."""
        if period.is_one_time():
            assert period.start and period.end
            return period.start <= now <= period.end

        if period.is_recurring():
            # Parse cron-like expression for daily recurring mute
            # We support simple "HH:MM * * * *" format for daily mutes
            return _check_cron_mute(period, now)

        return False


def _check_cron_mute(period: MutePeriodConfig, now: datetime) -> bool:
    """
    Check recurring mute period.
    Supports cron format: "MM HH * * *" (minute hour daily)
    Mute lasts for duration_minutes from the cron trigger time.
    """
    if not period.cron or not period.duration_minutes:
        return False

    parts = period.cron.strip().split()
    if len(parts) != 5:
        logger.warning("Invalid cron expression: %s", period.cron)
        return False

    try:
        cron_minute = int(parts[0])
        cron_hour = int(parts[1])
    except ValueError:
        # Wildcard minute/hour not supported for mute periods
        logger.warning("Cron mute requires specific minute and hour: %s", period.cron)
        return False

    # Calculate mute start/end for today
    mute_start = now.replace(hour=cron_hour, minute=cron_minute, second=0, microsecond=0)
    mute_end = mute_start + timedelta(minutes=period.duration_minutes)

    # Handle overnight: if mute spans midnight (e.g., 23:00 to 07:00 next day)
    if mute_end > mute_start + timedelta(days=1):
        # Check if now is after start today OR before end tomorrow
        yesterday_start = mute_start - timedelta(days=1)
        yesterday_end = mute_end - timedelta(days=1)
        return now >= mute_start or (yesterday_start <= now <= yesterday_end)

    if mute_end < mute_start:
        # Duration wrapped around midnight
        return now >= mute_start or now <= mute_end

    return mute_start <= now <= mute_end
