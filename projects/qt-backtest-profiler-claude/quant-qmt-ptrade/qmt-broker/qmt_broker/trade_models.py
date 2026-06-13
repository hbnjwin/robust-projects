import time
from dataclasses import dataclass, field
from typing import Dict, List


def now_ms() -> int:
    return int(time.time() * 1000)


@dataclass
class TradeStreamFilter:
    topics: List[str]
    account_id: str = ""
    replay: int = 0


@dataclass
class TradeEvent:
    topic: str
    payload: Dict[str, object]
    ts_ms: int = field(default_factory=now_ms)

    def to_dict(self) -> Dict[str, object]:
        return {
            "topic": self.topic,
            "ts_ms": self.ts_ms,
            "payload": self.payload,
        }


def parse_trade_topics(raw_topics: str) -> List[str]:
    allowed = {
        "disconnected",
        "account_status",
        "order",
        "asset",
        "trade",
        "position",
        "order_error",
        "cancel_error",
        "order_async_response",
        "cancel_async_response",
    }
    topics = []
    for topic in [item.strip() for item in raw_topics.split(",") if item.strip()]:
        if topic in allowed:
            topics.append(topic)
    return topics
