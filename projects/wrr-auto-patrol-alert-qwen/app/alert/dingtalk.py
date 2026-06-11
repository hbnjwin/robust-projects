"""DingTalk webhook notification sender."""

from __future__ import annotations

import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY_S = 2.0


class DingTalkNotifier:
    """Sends alert messages to DingTalk group via webhook."""

    def __init__(self, webhook_url: str):
        self._webhook_url = webhook_url

    def update_webhook(self, webhook_url: str) -> None:
        self._webhook_url = webhook_url

    async def send_text(self, content: str) -> bool:
        """Send a plain text message."""
        payload = {
            "msgtype": "text",
            "text": {"content": content},
        }
        return await self._send(payload)

    async def send_markdown(self, title: str, text: str) -> bool:
        """Send a Markdown-formatted message."""
        payload = {
            "msgtype": "markdown",
            "markdown": {"title": title, "text": text},
        }
        return await self._send(payload)

    async def send_aggregated_alert(self, alerts: list[dict]) -> bool:
        """Send an aggregated alert summary as Markdown."""
        if not alerts:
            return True

        if len(alerts) == 1:
            return await self._send_single_alert(alerts[0])

        # Build summary for multiple alerts
        services = set()
        details = []
        for a in alerts:
            svc = a.get("service", "unknown")
            services.add(svc)
            error = a.get("error", "Unknown error")
            rule_name = a.get("rule_name", a.get("rule_id", "?"))
            details.append(f"- **{rule_name}** ({svc}): {error}")

        title = f"⚠️ {len(alerts)}个巡检异常 ({len(services)}个服务)"
        text_lines = [
            f"## ⚠️ 巡检告警汇总",
            f"",
            f"**异常数量**: {len(alerts)}条",
            f"**涉及服务**: {', '.join(sorted(services))}",
            f"",
            f"### 详情",
            *details,
        ]

        return await self.send_markdown(title, "\n".join(text_lines))

    async def send_recovery(self, service: str, rule_name: str) -> bool:
        """Send a recovery notification."""
        title = f"✅ {service} 已恢复"
        text = f"## ✅ 服务恢复\n\n**{rule_name}** ({service}) 已恢复正常。"
        return await self.send_markdown(title, text)

    async def send_mute_summary(self, buffered_alerts: list[dict]) -> bool:
        """Send a summary of alerts that were buffered during a mute period."""
        if not buffered_alerts:
            return True

        services = set()
        for a in buffered_alerts:
            services.add(a.get("service", "unknown"))

        title = f"🔕 静默期间累计 {len(buffered_alerts)} 条告警"
        details = []
        for a in buffered_alerts:
            rule_name = a.get("rule_name", a.get("rule_id", "?"))
            error = a.get("error", "Unknown")
            details.append(f"- {rule_name}: {error}")

        text_lines = [
            f"## 🔕 静默期告警汇总",
            f"",
            f"静默期间共 **{len(buffered_alerts)}** 条告警被抑制。",
            f"**涉及服务**: {', '.join(sorted(services))}",
            f"",
            *details,
        ]

        return await self.send_markdown(title, "\n".join(text_lines))

    async def _send_single_alert(self, alert: dict) -> bool:
        service = alert.get("service", "unknown")
        rule_name = alert.get("rule_name", alert.get("rule_id", "?"))
        error = alert.get("error", "Unknown error")
        failures = alert.get("consecutive_failures", 1)

        title = f"⚠️ {rule_name} 异常"
        text_lines = [
            f"## ⚠️ 巡检告警",
            f"",
            f"- **规则**: {rule_name}",
            f"- **服务**: {service}",
            f"- **错误**: {error}",
            f"- **连续失败**: {failures}次",
        ]
        return await self.send_markdown(title, "\n".join(text_lines))

    async def _send(self, payload: dict) -> bool:
        """Send payload with retry logic."""
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(self._webhook_url, json=payload)
                    if resp.status_code == 200:
                        body = resp.json()
                        if body.get("errcode", -1) == 0:
                            logger.debug("DingTalk message sent successfully")
                            return True
                        logger.warning("DingTalk API error: %s", body)
                    else:
                        logger.warning("DingTalk HTTP %d on attempt %d", resp.status_code, attempt)
            except Exception as e:
                logger.warning("DingTalk send failed (attempt %d/%d): %s", attempt, MAX_RETRIES, e)

            if attempt < MAX_RETRIES:
                import asyncio
                await asyncio.sleep(RETRY_DELAY_S * attempt)

        logger.error("Failed to send DingTalk message after %d attempts", MAX_RETRIES)
        return False
