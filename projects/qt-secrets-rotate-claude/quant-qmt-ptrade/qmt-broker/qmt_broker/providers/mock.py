import random
import threading
import time
from typing import Dict, List

from qmt_broker.models import SubscriptionTopic, now_ms
from qmt_broker.providers.base import MarketDataProvider, ProviderCallback, normalize_limit


def _seed(symbol: str) -> int:
    return sum(ord(ch) for ch in symbol) or 1


class MockMarketDataProvider(MarketDataProvider):
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._handles = {}
        self._running = True
        self._thread = threading.Thread(target=self._pump, daemon=True)
        self._thread.start()

    def name(self) -> str:
        return "mock"

    def capabilities(self) -> Dict[str, object]:
        return {
            "provider": "mock",
            "supports": [
                "quote",
                "bar",
                "tick",
                "whole_quote",
                "l2_quote",
                "l2_order",
                "l2_transaction",
                "bars_diagnostics",
            ],
        }

    def get_quote(self, symbol: str) -> Dict[str, object]:
        base = float(_seed(symbol) % 1000) / 10.0 + 10.0
        ts = now_ms()
        return {
            "symbol": symbol,
            "time": ts,
            "lastPrice": round(base + (ts % 700) / 1000.0, 3),
            "open": round(base - 0.2, 3),
            "high": round(base + 0.8, 3),
            "low": round(base - 0.6, 3),
            "lastClose": round(base - 0.1, 3),
            "volume": 100000 + (ts % 10000),
            "amount": 1000000 + (ts % 100000),
            "askPrice1": round(base + 0.01, 3),
            "bidPrice1": round(base - 0.01, 3),
            "askVol1": 500 + (ts % 20),
            "bidVol1": 400 + (ts % 20),
        }

    def get_bars(
        self,
        symbol: str,
        period: str,
        limit: int,
        start_time: str = "",
        end_time: str = "",
    ) -> List[Dict[str, object]]:
        del start_time, end_time
        limit = normalize_limit(limit, 60)
        end_ts = now_ms()
        step_ms = 60000 if period == "1m" else 300000 if period == "5m" else 86400000
        quote = self.get_quote(symbol)
        records = []
        base = float(quote["lastPrice"])
        for index in range(limit):
            ts = end_ts - (limit - index - 1) * step_ms
            price = round(base - 0.3 + index * 0.01, 3)
            records.append(
                {
                    "time": ts,
                    "open": price,
                    "high": round(price + 0.15, 3),
                    "low": round(price - 0.1, 3),
                    "close": round(price + 0.05, 3),
                    "volume": 1000 + index * 20,
                    "amount": 100000 + index * 500,
                }
            )
        return records

    def get_ticks(
        self,
        symbol: str,
        limit: int,
        start_time: str = "",
        end_time: str = "",
        run_prefetch: bool = False,
        wait_timeout_ms: int = 0,
        poll_interval_ms: int = 250,
    ) -> List[Dict[str, object]]:
        del start_time, end_time, run_prefetch, wait_timeout_ms, poll_interval_ms
        limit = normalize_limit(limit, 100)
        quote = self.get_quote(symbol)
        end_ts = int(quote["time"])
        records = []
        for index in range(limit):
            ts = end_ts - (limit - index - 1) * 300
            last_price = round(float(quote["lastPrice"]) - 0.05 + index * 0.001, 3)
            records.append(
                {
                    "time": ts,
                    "lastPrice": last_price,
                    "lastClose": quote["lastClose"],
                    "open": quote["open"],
                    "high": max(last_price, quote["high"]),
                    "low": min(last_price, quote["low"]),
                    "volume": 10000 + index * 10,
                    "amount": 500000 + index * 1000,
                    "askPrice1": round(last_price + 0.01, 3),
                    "bidPrice1": round(last_price - 0.01, 3),
                }
            )
        return records

    def backfill_ticks(
        self,
        symbol: str,
        start_time: str = "",
        end_time: str = "",
    ) -> List[Dict[str, object]]:
        del start_time, end_time
        return self.get_ticks(symbol, 600, "", "", run_prefetch=False, wait_timeout_ms=0, poll_interval_ms=250)

    def get_l2_quote(
        self,
        symbol: str,
        limit: int,
        start_time: str = "",
        end_time: str = "",
    ) -> List[Dict[str, object]]:
        del start_time, end_time
        limit = normalize_limit(limit, 20)
        quote = self.get_quote(symbol)
        records = []
        for index in range(limit):
            ts = int(quote["time"]) - (limit - index - 1) * 200
            records.append(
                {
                    "time": ts,
                    "lastPrice": quote["lastPrice"],
                    "askPrice1": quote["askPrice1"],
                    "askVol1": 1000 + index,
                    "bidPrice1": quote["bidPrice1"],
                    "bidVol1": 900 + index,
                    "totalAskVol": 5000 + index * 10,
                    "totalBidVol": 4500 + index * 10,
                }
            )
        return records

    def get_l2_order(
        self,
        symbol: str,
        limit: int,
        start_time: str = "",
        end_time: str = "",
    ) -> List[Dict[str, object]]:
        del start_time, end_time
        limit = normalize_limit(limit, 20)
        ts = now_ms()
        return [
            {
                "time": ts - (limit - index - 1) * 150,
                "entrustNo": 100000 + index,
                "entrustType": "B" if index % 2 == 0 else "S",
                "price": round(11.0 + index * 0.01, 3),
                "volume": 100 + index,
                "symbol": symbol,
            }
            for index in range(limit)
        ]

    def get_l2_transaction(
        self,
        symbol: str,
        limit: int,
        start_time: str = "",
        end_time: str = "",
    ) -> List[Dict[str, object]]:
        del start_time, end_time
        limit = normalize_limit(limit, 20)
        ts = now_ms()
        return [
            {
                "time": ts - (limit - index - 1) * 120,
                "tradeIndex": 200000 + index,
                "price": round(11.2 + index * 0.01, 3),
                "volume": 80 + index,
                "tradeType": "成交",
                "symbol": symbol,
            }
            for index in range(limit)
        ]

    def prefetch_history(
        self,
        symbol: str,
        period: str,
        start_time: str = "",
        end_time: str = "",
        wait_timeout_ms: int = 0,
        poll_interval_ms: int = 250,
    ) -> Dict[str, object]:
        return {
            "ok": True,
            "provider": "mock",
            "symbol": symbol,
            "period": period,
            "start_time": start_time,
            "end_time": end_time,
            "mode": "noop",
            "cache_ready": True,
            "wait_timeout_ms": wait_timeout_ms,
            "poll_interval_ms": poll_interval_ms,
        }

    def diagnose_bars(
        self,
        symbol: str,
        period: str,
        limit: int,
        start_time: str = "",
        end_time: str = "",
        run_prefetch: bool = False,
        wait_timeout_ms: int = 0,
        poll_interval_ms: int = 250,
    ) -> Dict[str, object]:
        before_records = self.get_bars(symbol, period, min(limit, 3), start_time, end_time)
        prefetch = None
        if run_prefetch:
            prefetch = self.prefetch_history(
                symbol,
                period,
                start_time,
                end_time,
                wait_timeout_ms=wait_timeout_ms,
                poll_interval_ms=poll_interval_ms,
            )
        after_records = self.get_bars(symbol, period, min(limit, 3), start_time, end_time)
        return {
            "ok": True,
            "provider": "mock",
            "symbol": symbol,
            "period": period,
            "limit": normalize_limit(limit, 60),
            "start_time": start_time,
            "end_time": end_time,
            "run_prefetch": run_prefetch,
            "wait_timeout_ms": wait_timeout_ms,
            "poll_interval_ms": poll_interval_ms,
            "diagnosis": "mock_data_ready",
            "before": {
                "market": {"ok": True, "record_count": len(before_records), "sample": before_records[-2:]},
                "market_ex": {"ok": True, "record_count": len(before_records), "sample": before_records[-2:]},
                "local": {"ok": True, "record_count": len(before_records), "sample": before_records[-2:]},
            },
            "prefetch": prefetch,
            "polls": [],
            "after": {
                "market": {"ok": True, "record_count": len(after_records), "sample": after_records[-2:]},
                "market_ex": {"ok": True, "record_count": len(after_records), "sample": after_records[-2:]},
                "local": {"ok": True, "record_count": len(after_records), "sample": after_records[-2:]},
            },
        }

    def get_sector_list(self) -> List[str]:
        return ["沪A", "深A"]

    def get_stock_list_in_sector(self, sector_name: str) -> List[str]:
        catalog = {
            "沪A": ["600000.SH", "600519.SH"],
            "深A": ["000001.SZ", "300750.SZ"],
        }
        return list(catalog.get(sector_name, []))

    def get_instrument_detail(self, symbol: str) -> Dict[str, object]:
        symbol = str(symbol or "").strip().upper()
        if symbol.endswith(".SH"):
            exchange = "SH"
            name = "Mock Shanghai"
        else:
            exchange = "SZ"
            name = "Mock Shenzhen"
        return {
            "InstrumentName": name,
            "OpenDate": "20200101",
            "ExpireDate": "",
            "ExchangeID": exchange,
            "InstrumentID": symbol.split(".", 1)[0],
            "ProductID": "stock",
            "ProductName": "A股",
        }

    def default_security_master_sectors(self) -> List[str]:
        return ["沪A", "深A"]

    def subscribe(self, topic: SubscriptionTopic, callback: ProviderCallback) -> str:
        if topic.kind in {"l2_quote", "l2_order", "l2_transaction"}:
            raise ValueError("mock provider uses polling for l2 topics")
        handle = "%s-%d-%d" % (topic.kind, int(time.time() * 1000), random.randint(1000, 9999))
        with self._lock:
            self._handles[handle] = {
                "topic": topic,
                "callback": callback,
                "last_emit_ms": 0,
            }
        return handle

    def unsubscribe(self, handle: str) -> None:
        with self._lock:
            self._handles.pop(handle, None)

    def close(self) -> None:
        self._running = False
        self._thread.join(timeout=1.0)

    def _pump(self) -> None:
        while self._running:
            time.sleep(0.4)
            with self._lock:
                items = list(self._handles.items())
            for _, meta in items:
                topic = meta["topic"]
                callback = meta["callback"]
                try:
                    if topic.kind == "whole_quote":
                        symbols = ["000001.SZ", "600000.SH"]
                        if topic.market == "SH":
                            symbols = ["600000.SH"]
                        elif topic.market == "SZ":
                            symbols = ["000001.SZ"]
                        for symbol in symbols:
                            callback(topic, symbol, self.get_quote(symbol))
                        continue
                    symbol = topic.symbol
                    if topic.kind == "quote":
                        callback(topic, symbol, self.get_quote(symbol))
                    elif topic.kind == "tick":
                        callback(topic, symbol, self.get_ticks(symbol, 1)[-1])
                    elif topic.kind == "bar":
                        callback(topic, symbol, self.get_bars(symbol, topic.period or "1m", 1)[-1])
                except Exception:
                    continue
