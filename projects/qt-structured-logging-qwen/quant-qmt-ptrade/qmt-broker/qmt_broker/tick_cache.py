import json
import threading
import time
from typing import Dict, List, Optional


def _json_event(raw: str) -> Optional[Dict[str, object]]:
    try:
        payload = json.loads(raw)
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


class RedisTickCache:
    def __init__(
        self,
        redis_url: str,
        key_prefix: str = "qmt-broker",
        max_records: int = 512,
        ttl_sec: int = 900,
        reconnect_retry_sec: int = 5,
    ) -> None:
        self._redis_url = str(redis_url or "").strip()
        self._key_prefix = str(key_prefix or "qmt-broker").strip() or "qmt-broker"
        self._max_records = max(1, int(max_records))
        self._ttl_sec = max(30, int(ttl_sec))
        self._reconnect_retry_sec = max(1, int(reconnect_retry_sec))
        self._lock = threading.RLock()
        self._client = None
        self._last_error = ""
        self._next_retry_at = 0.0

    def enabled(self) -> bool:
        return bool(self._redis_url)

    def append_event(self, symbol: str, event: Dict[str, object]) -> None:
        clean_symbol = str(symbol or "").strip().upper()
        if not self.enabled() or not clean_symbol:
            return
        client = self._ensure_client()
        if client is None:
            return
        event_json = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
        now_ms = int(time.time() * 1000)
        try:
            pipe = client.pipeline()
            pipe.lpush(self._ticks_key(clean_symbol), event_json)
            pipe.ltrim(self._ticks_key(clean_symbol), 0, self._max_records - 1)
            pipe.expire(self._ticks_key(clean_symbol), self._ttl_sec)
            pipe.zadd(self._symbols_key(), {clean_symbol: now_ms})
            pipe.expire(self._symbols_key(), max(self._ttl_sec * 2, 60))
            pipe.execute()
            with self._lock:
                self._last_error = ""
        except Exception as exc:
            self._record_error(exc)

    def get_recent_ticks(self, symbol: str, limit: int) -> List[Dict[str, object]]:
        clean_symbol = str(symbol or "").strip().upper()
        if not self.enabled() or not clean_symbol:
            return []
        client = self._ensure_client()
        if client is None:
            return []
        try:
            rows = client.lrange(self._ticks_key(clean_symbol), 0, max(limit, 1) - 1)
        except Exception as exc:
            self._record_error(exc)
            return []
        ticks: List[Dict[str, object]] = []
        for raw in reversed(rows):
            event = _json_event(raw)
            if event is None:
                continue
            payload = event.get("payload")
            if isinstance(payload, dict):
                ticks.append(payload)
        return ticks

    def status(self) -> Dict[str, object]:
        if not self.enabled():
            return {
                "enabled": False,
                "backend": "disabled",
                "connected": False,
                "key_prefix": self._key_prefix,
                "max_records": self._max_records,
                "ttl_sec": self._ttl_sec,
                "cached_symbols": [],
                "last_error": "",
            }
        client = self._ensure_client()
        cached_symbols: List[str] = []
        if client is not None:
            try:
                cutoff_ms = int(time.time() * 1000) - self._ttl_sec * 1000
                client.zremrangebyscore(self._symbols_key(), "-inf", cutoff_ms)
                raw_symbols = client.zrevrange(self._symbols_key(), 0, 31)
                cached_symbols = [str(symbol) for symbol in raw_symbols]
            except Exception as exc:
                self._record_error(exc)
        with self._lock:
            last_error = self._last_error
        return {
            "enabled": True,
            "backend": "redis",
            "connected": client is not None,
            "key_prefix": self._key_prefix,
            "max_records": self._max_records,
            "ttl_sec": self._ttl_sec,
            "cached_symbols": cached_symbols,
            "last_error": last_error,
        }

    def close(self) -> None:
        with self._lock:
            client = self._client
            self._client = None
        if client is None:
            return
        close = getattr(client, "close", None)
        if callable(close):
            try:
                close()
            except Exception:
                return

    def _ensure_client(self):
        if not self.enabled():
            return None
        with self._lock:
            if self._client is not None:
                return self._client
            if time.time() < self._next_retry_at:
                return None
        try:
            import redis

            client = redis.Redis.from_url(self._redis_url, decode_responses=True)
            client.ping()
        except Exception as exc:
            self._record_error(exc)
            return None
        with self._lock:
            self._client = client
            self._last_error = ""
            self._next_retry_at = 0.0
            return self._client

    def _record_error(self, exc: Exception) -> None:
        with self._lock:
            self._client = None
            self._last_error = str(exc)
            self._next_retry_at = time.time() + self._reconnect_retry_sec

    def _ticks_key(self, symbol: str) -> str:
        return "%s:ticks:%s" % (self._key_prefix, symbol)

    def _symbols_key(self) -> str:
        return "%s:ticks:symbols" % self._key_prefix
