from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from datetime import datetime, time, timezone

import httpx

from app.channels.base import BaseChannel
from app.models.alert import AggregatedAlert, AlertEvent
from app.models.rule import AlertChannelConfig, PatrolRule, SilentWindow

logger = logging.getLogger(__name__)


class AlertEngine:
    """Aggregates alert events over a time window, filters by silent windows, dispatches to channels."""

    def __init__(self, flush_interval: int = 60) -> None:
        self._buffer: list[tuple[AlertEvent, PatrolRule]] = []
        self._silenced_buffer: list[tuple[AlertEvent, PatrolRule]] = []
        self._lock = asyncio.Lock()
        self._flush_interval = flush_interval
        self._channel_registry: dict[str, BaseChannel] = {}
        self._flush_task: asyncio.Task | None = None
        self._http_client: httpx.AsyncClient | None = None
        self._alert_history: list[AggregatedAlert] = []
        self._max_history = 100

    def register_channel(self, name: str, channel: BaseChannel) -> None:
        self._channel_registry[name] = channel

    async def start(self, client: httpx.AsyncClient) -> None:
        self._http_client = client
        self._flush_task = asyncio.create_task(self._flush_loop())
        logger.info(
            "AlertEngine started (flush every %ds)", self._flush_interval
        )

    async def stop(self) -> None:
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        # Final flush to avoid losing buffered alerts
        await self._flush()
        logger.info("AlertEngine stopped")

    async def enqueue(self, event: AlertEvent, rule: PatrolRule) -> None:
        async with self._lock:
            self._buffer.append((event, rule))
        logger.debug("Alert enqueued: %s [%s]", event.service_name, event.event_type)

    def get_history(self) -> list[AggregatedAlert]:
        return list(self._alert_history)

    def get_silenced(self) -> list[tuple[AlertEvent, PatrolRule]]:
        return list(self._silenced_buffer)

    async def _flush_loop(self) -> None:
        while True:
            await asyncio.sleep(self._flush_interval)
            try:
                await self._flush()
            except Exception:
                logger.exception("Error during alert flush")

    async def _flush(self) -> None:
        async with self._lock:
            if not self._buffer:
                return
            snapshot = list(self._buffer)
            self._buffer.clear()

        now = datetime.now(timezone.utc)

        # Group by service for aggregation
        to_dispatch: list[tuple[AlertEvent, PatrolRule]] = []
        for event, rule in snapshot:
            if self._is_in_silent_window(rule.silent_windows):
                self._silenced_buffer.append((event, rule))
                logger.info(
                    "Alert silenced for %s (in silent window)", event.service_name
                )
            else:
                to_dispatch.append((event, rule))

        if not to_dispatch:
            return

        # Group events by their alert channel configs for batched dispatch
        # Each unique set of channels gets one aggregated alert
        by_channel_key: dict[str, list[tuple[AlertEvent, PatrolRule]]] = defaultdict(list)
        for event, rule in to_dispatch:
            # Use rule_id as channel key since each rule has its own channel config
            by_channel_key[rule.rule_id].append((event, rule))

        window_start = min(e.created_at for e, _ in to_dispatch)

        for _rule_id, items in by_channel_key.items():
            events = [e for e, _ in items]
            rule = items[0][1]  # all same rule

            aggregated = AggregatedAlert(
                events=events,
                service_count=len({e.service_name for e in events}),
                total_failures=sum(
                    e.consecutive_failures for e in events if e.event_type == "failure"
                ),
                aggregation_window_start=window_start,
                aggregation_window_end=now,
            )

            self._alert_history.append(aggregated)
            if len(self._alert_history) > self._max_history:
                self._alert_history = self._alert_history[-self._max_history:]

            await self._dispatch(aggregated, rule.alert_channels)

    async def _dispatch(
        self, alert: AggregatedAlert, channels: list[AlertChannelConfig]
    ) -> None:
        if not self._http_client:
            logger.error("HTTP client not available, cannot dispatch alert")
            return

        for ch_config in channels:
            channel = self._channel_registry.get(ch_config.channel_type)
            if channel is None:
                logger.warning("Unknown channel type: %s", ch_config.channel_type)
                continue
            try:
                ok = await channel.send(alert, ch_config, self._http_client)
                if ok:
                    logger.info(
                        "Alert dispatched via %s for %d event(s)",
                        ch_config.channel_type,
                        len(alert.events),
                    )
            except Exception:
                logger.exception(
                    "Failed to dispatch alert via %s", ch_config.channel_type
                )

    @staticmethod
    def _is_in_silent_window(windows: list[SilentWindow]) -> bool:
        if not windows:
            return False

        now = datetime.now()
        now_time = now.time()
        now_weekday = now.weekday()  # 0=Mon

        for w in windows:
            if w.days is not None and now_weekday not in w.days:
                continue

            start = time.fromisoformat(w.start)
            end = time.fromisoformat(w.end)

            if start <= end:
                # Normal window, e.g. 00:00 - 08:00
                if start <= now_time <= end:
                    return True
            else:
                # Overnight window, e.g. 23:00 - 07:00
                if now_time >= start or now_time <= end:
                    return True

        return False
