import json
import urllib.error
import urllib.request
from typing import Dict, List

from qmt_broker.config import BrokerConfig


class ApprovalNotifier:
    def __init__(self, config: BrokerConfig) -> None:
        self.config = config

    def status(self) -> Dict[str, object]:
        return {
            "enabled": bool(self._targets()),
            "channels": [item["channel"] for item in self._targets()],
            "approval_reminder_before_sec": self.config.approval_reminder_before_sec,
        }

    def notify(self, event_name: str, request: Dict[str, object]) -> List[Dict[str, object]]:
        payload = {
            "event": event_name,
            "request": request,
            "summary": self._summary(event_name, request),
        }
        results: List[Dict[str, object]] = []
        for target in self._targets():
            sender = getattr(self, "_send_%s" % target["channel"])
            result = {"channel": target["channel"], "ok": True}
            try:
                sender(target, payload)
            except Exception as exc:
                result["ok"] = False
                result["error"] = str(exc)
            results.append(result)
        return results

    def _targets(self) -> List[Dict[str, str]]:
        targets: List[Dict[str, str]] = []
        for url in self.config.approval_webhook_urls:
            targets.append({"channel": "webhook", "url": url})
        if self.config.wecom_webhook_url:
            targets.append({"channel": "wecom", "url": self.config.wecom_webhook_url})
        if self.config.telegram_bot_token and self.config.telegram_chat_id:
            targets.append(
                {
                    "channel": "telegram",
                    "token": self.config.telegram_bot_token,
                    "chat_id": self.config.telegram_chat_id,
                }
            )
        if self.config.feishu_webhook_url:
            targets.append({"channel": "feishu", "url": self.config.feishu_webhook_url})
        return targets

    def _send_webhook(self, target: Dict[str, str], payload: Dict[str, object]) -> None:
        self._post_json(target["url"], payload)

    def _send_wecom(self, target: Dict[str, str], payload: Dict[str, object]) -> None:
        self._post_json(
            target["url"],
            {
                "msgtype": "markdown",
                "markdown": {"content": payload["summary"]},
            },
        )

    def _send_telegram(self, target: Dict[str, str], payload: Dict[str, object]) -> None:
        self._post_json(
            "https://api.telegram.org/bot%s/sendMessage" % target["token"],
            {
                "chat_id": target["chat_id"],
                "text": payload["summary"],
            },
        )

    def _send_feishu(self, target: Dict[str, str], payload: Dict[str, object]) -> None:
        self._post_json(
            target["url"],
            {
                "msg_type": "text",
                "content": {"text": payload["summary"]},
            },
        )

    def _summary(self, event_name: str, request: Dict[str, object]) -> str:
        payload = request.get("payload", {})
        symbol = payload.get("symbol", "")
        side = payload.get("side", "")
        volume = payload.get("volume", 0)
        account_id = payload.get("account_id", "")
        lines = [
            "qmt-broker %s" % event_name,
            "request_id=%s" % request.get("request_id", ""),
            "status=%s" % request.get("status", ""),
            "account_id=%s" % account_id,
            "symbol=%s" % symbol,
            "side=%s volume=%s" % (side, volume),
        ]
        reason = str(request.get("reason", ""))
        if reason:
            lines.append("reason=%s" % reason)
        expires_at_ms = int(request.get("expires_at_ms", 0) or 0)
        if expires_at_ms > 0:
            lines.append("expires_at_ms=%s" % expires_at_ms)
        links = request.get("links", {})
        if isinstance(links, dict):
            order_ids = ",".join(str(item) for item in links.get("order_ids", []))
            order_sysids = ",".join(str(item) for item in links.get("order_sysids", []))
            trade_ids = ",".join(str(item) for item in links.get("trade_ids", []))
            if order_ids:
                lines.append("order_ids=%s" % order_ids)
            if order_sysids:
                lines.append("order_sysids=%s" % order_sysids)
            if trade_ids:
                lines.append("trade_ids=%s" % trade_ids)
        return "\n".join(lines)

    def _post_json(self, url: str, payload: Dict[str, object]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(url, data=body, method="POST")
        request.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(request, timeout=3) as response:
                response.read()
        except urllib.error.HTTPError as exc:
            raise RuntimeError("notify http %s for %s" % (exc.code, url)) from exc
