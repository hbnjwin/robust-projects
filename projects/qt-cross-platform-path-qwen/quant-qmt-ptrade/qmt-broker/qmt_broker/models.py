import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional


def now_ms() -> int:
    return int(time.time() * 1000)


@dataclass(frozen=True)
class SubscriptionKey:
    kind: str
    symbol: str = ""
    period: str = ""
    market: str = ""


@dataclass
class SubscriptionTopic:
    kind: str
    symbol: str = ""
    period: str = ""
    market: str = ""

    def key(self) -> SubscriptionKey:
        return SubscriptionKey(
            kind=self.kind,
            symbol=self.symbol,
            period=self.period,
            market=self.market,
        )


@dataclass
class MarketEvent:
    topic: SubscriptionTopic
    symbol: str
    payload: Dict[str, object]
    ts_ms: int = field(default_factory=now_ms)
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex)

    def to_dict(self) -> Dict[str, object]:
        return {
            "event_id": self.event_id,
            "topic": self.topic.kind,
            "symbol": self.symbol,
            "period": self.topic.period,
            "market": self.topic.market,
            "ts_ms": self.ts_ms,
            "payload": self.payload,
        }


@dataclass
class StreamRequest:
    topics: List[SubscriptionTopic]
    replay: int = 0


def parse_topics(raw_topics: str, symbol: str = "", period: str = "", market: str = "") -> List[SubscriptionTopic]:
    topics = []
    for raw_topic in [item.strip() for item in raw_topics.split(",") if item.strip()]:
        if raw_topic == "bar":
            topics.append(SubscriptionTopic(kind="bar", symbol=symbol, period=period or "1m"))
            continue
        if raw_topic == "whole_quote":
            topics.append(SubscriptionTopic(kind="whole_quote", market=market or symbol))
            continue
        topics.append(SubscriptionTopic(kind=raw_topic, symbol=symbol, period=period))
    return topics


def topic_descriptor(topic: SubscriptionTopic) -> Dict[str, str]:
    return {
        "kind": topic.kind,
        "symbol": topic.symbol,
        "period": topic.period,
        "market": topic.market,
    }


def topic_label(topic: SubscriptionTopic) -> str:
    if topic.kind == "whole_quote":
        return "%s:%s" % (topic.kind, topic.market)
    if topic.period:
        return "%s:%s:%s" % (topic.kind, topic.symbol, topic.period)
    return "%s:%s" % (topic.kind, topic.symbol)


def unique_records_key(records: List[Dict[str, object]]) -> Optional[str]:
    if not records:
        return None
    last = records[-1]
    time_value = last.get("time") or last.get("time_ms") or last.get("ts_ms")
    index_value = last.get("index") or last.get("seq") or last.get("entrustNo") or last.get("tradeIndex")
    if time_value is None and index_value is None:
        return None
    return "%s:%s" % (time_value, index_value)
