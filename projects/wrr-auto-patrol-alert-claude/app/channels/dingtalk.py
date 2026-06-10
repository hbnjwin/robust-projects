from __future__ import annotations

import hashlib
import hmac
import base64
import logging
import time
import urllib.parse
from datetime import timezone

import httpx

from app.channels.base import BaseChannel
from app.models.alert import AggregatedAlert
from app.models.rule import AlertChannelConfig

logger = logging.getLogger(__name__)


def _sign(secret: str, timestamp: int) -> str:
    """Generate DingTalk HMAC-SHA256 signature."""
    string_to_sign = f"{timestamp}\n{secret}"
    hmac_code = hmac.new(
        secret.encode("utf-8"),
        string_to_sign.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    return urllib.parse.quote_plus(base64.b64encode(hmac_code).decode("utf-8"))


class DingTalkChannel(BaseChannel):
    async def send(
        self,
        alert: AggregatedAlert,
        config: AlertChannelConfig,
        client: httpx.AsyncClient,
    ) -> bool:
        markdown_body = self._build_markdown(alert)
        title = self._build_title(alert)

        url = config.webhook_url
        if config.secret:
            ts = int(time.time() * 1000)
            sign = _sign(config.secret, ts)
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}timestamp={ts}&sign={sign}"

        payload = {
            "msgtype": "markdown",
            "markdown": {"title": title, "text": markdown_body},
        }

        try:
            resp = await client.post(url, json=payload, timeout=10)
            data = resp.json()
            if data.get("errcode") == 0:
                logger.info("DingTalk alert sent: %s", title)
                return True
            logger.error("DingTalk API error: %s", data)
            return False
        except Exception:
            logger.exception("Failed to send DingTalk alert")
            return False

    def _build_title(self, alert: AggregatedAlert) -> str:
        has_failure = any(e.event_type == "failure" for e in alert.events)
        has_recovery = any(e.event_type == "recovery" for e in alert.events)

        if has_failure and has_recovery:
            return f"[Patrol] {alert.service_count} services status changed"
        elif has_recovery:
            return f"[Recovery] {alert.service_count} services recovered"
        else:
            return f"[Alert] {alert.service_count} services failed"

    def _build_markdown(self, alert: AggregatedAlert) -> str:
        lines: list[str] = []
        ts = alert.aggregation_window_end.astimezone(timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S UTC"
        )
        lines.append(f"### Auto Patrol Report ({ts})")
        lines.append("")

        for event in alert.events:
            icon = "RED" if event.event_type == "failure" else "GREEN"
            lines.append(f"**[{icon}] {event.service_name}**")
            lines.append(f"- Type: {event.event_type}")
            lines.append(f"- {event.summary}")
            if event.consecutive_failures > 0:
                lines.append(f"- Consecutive failures: {event.consecutive_failures}")
            if event.first_failure_at:
                fail_ts = event.first_failure_at.strftime("%H:%M:%S")
                lines.append(f"- First failure at: {fail_ts}")
            if event.details:
                lines.append(f"- Details: {event.details[-1]}")
            lines.append("")

        lines.append(f"---")
        lines.append(
            f"Total: {alert.service_count} service(s), "
            f"{alert.total_failures} failure(s)"
        )
        return "\n".join(lines)
