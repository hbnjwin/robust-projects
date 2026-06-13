import json
import os
import threading
import time
from collections import deque
from typing import Deque, Dict, List


class TradeAuditLogger:
    def __init__(self, path: str, tail_size: int = 200) -> None:
        self.path = path
        self._tail_size = tail_size
        self._tail: Deque[Dict[str, object]] = deque(maxlen=tail_size)
        self._lock = threading.RLock()

    def log(self, record: Dict[str, object]) -> None:
        entry = {"ts_ms": int(time.time() * 1000), **record}
        line = json.dumps(entry, ensure_ascii=False, separators=(",", ":"))
        with self._lock:
            self._tail.append(entry)
            parent = os.path.dirname(self.path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write(line)
                fh.write("\n")

    def tail(self, limit: int = 50) -> List[Dict[str, object]]:
        with self._lock:
            if limit <= 0:
                return []
            return list(self._tail)[-limit:]
