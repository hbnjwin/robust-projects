from abc import ABC, abstractmethod
from typing import Callable, Dict, List, Optional, Sequence

from qmt_broker.models import SubscriptionTopic


ProviderCallback = Callable[[SubscriptionTopic, str, Dict[str, object]], None]
TradeProviderCallback = Callable[[str, Dict[str, object]], None]


class MarketDataProvider(ABC):
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def capabilities(self) -> Dict[str, object]:
        raise NotImplementedError

    @abstractmethod
    def get_quote(self, symbol: str) -> Dict[str, object]:
        raise NotImplementedError

    @abstractmethod
    def get_bars(
        self,
        symbol: str,
        period: str,
        limit: int,
        start_time: str = "",
        end_time: str = "",
    ) -> List[Dict[str, object]]:
        raise NotImplementedError

    @abstractmethod
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
        raise NotImplementedError

    @abstractmethod
    def get_l2_quote(
        self,
        symbol: str,
        limit: int,
        start_time: str = "",
        end_time: str = "",
    ) -> List[Dict[str, object]]:
        raise NotImplementedError

    @abstractmethod
    def get_l2_order(
        self,
        symbol: str,
        limit: int,
        start_time: str = "",
        end_time: str = "",
    ) -> List[Dict[str, object]]:
        raise NotImplementedError

    @abstractmethod
    def get_l2_transaction(
        self,
        symbol: str,
        limit: int,
        start_time: str = "",
        end_time: str = "",
    ) -> List[Dict[str, object]]:
        raise NotImplementedError

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
            "ok": False,
            "error": "prefetch_not_supported",
            "symbol": symbol,
            "period": period,
            "start_time": start_time,
            "end_time": end_time,
            "wait_timeout_ms": wait_timeout_ms,
            "poll_interval_ms": poll_interval_ms,
        }

    def prefetch_history_batch(
        self,
        symbols: Sequence[str],
        period: str,
        start_time: str = "",
        end_time: str = "",
        wait_timeout_ms: int = 0,
        poll_interval_ms: int = 250,
    ) -> Dict[str, object]:
        clean_symbols = tuple(str(symbol or "").strip().upper() for symbol in symbols if str(symbol or "").strip())
        if not clean_symbols:
            return {
                "ok": False,
                "error": "empty_symbol_batch",
                "symbols": [],
                "period": period,
                "start_time": start_time,
                "end_time": end_time,
                "wait_timeout_ms": wait_timeout_ms,
                "poll_interval_ms": poll_interval_ms,
            }
        results = [
            self.prefetch_history(
                symbol,
                period,
                start_time,
                end_time,
                wait_timeout_ms=wait_timeout_ms,
                poll_interval_ms=poll_interval_ms,
            )
            for symbol in clean_symbols
        ]
        ok_count = sum(1 for result in results if bool(result.get("ok")))
        cache_ready_count = sum(1 for result in results if bool(result.get("cache_ready")))
        return {
            "ok": ok_count == len(clean_symbols),
            "provider": self.name(),
            "symbols": list(clean_symbols),
            "symbol_count": len(clean_symbols),
            "ok_count": ok_count,
            "cache_ready_count": cache_ready_count,
            "period": period,
            "start_time": start_time,
            "end_time": end_time,
            "wait_timeout_ms": wait_timeout_ms,
            "poll_interval_ms": poll_interval_ms,
            "results": results,
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
        return {
            "ok": False,
            "error": "bars_diagnostics_not_supported",
            "symbol": symbol,
            "period": period,
            "limit": limit,
            "start_time": start_time,
            "end_time": end_time,
            "run_prefetch": run_prefetch,
            "wait_timeout_ms": wait_timeout_ms,
            "poll_interval_ms": poll_interval_ms,
        }

    def get_sector_list(self) -> List[str]:
        return []

    def get_stock_list_in_sector(self, sector_name: str) -> List[str]:
        del sector_name
        return []

    def get_instrument_detail(self, symbol: str) -> Dict[str, object]:
        del symbol
        return {}

    def default_security_master_sectors(self) -> List[str]:
        return []

    def backfill_ticks(
        self,
        symbol: str,
        start_time: str = "",
        end_time: str = "",
    ) -> List[Dict[str, object]]:
        return self.get_ticks(symbol, -1, start_time, end_time, run_prefetch=False, wait_timeout_ms=0, poll_interval_ms=250)

    @abstractmethod
    def subscribe(self, topic: SubscriptionTopic, callback: ProviderCallback) -> str:
        raise NotImplementedError

    @abstractmethod
    def unsubscribe(self, handle: str) -> None:
        raise NotImplementedError

    def close(self) -> None:
        return None


def normalize_limit(limit: int, fallback: int = 200) -> int:
    if limit <= 0:
        return fallback
    if limit > 5000:
        return 5000
    return limit


def window_args(start_time: Optional[str], end_time: Optional[str]) -> Dict[str, str]:
    return {
        "start_time": start_time or "",
        "end_time": end_time or "",
    }


class TradeProvider(ABC):
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def capabilities(self) -> Dict[str, object]:
        raise NotImplementedError

    @abstractmethod
    def status(self) -> Dict[str, object]:
        raise NotImplementedError

    def get_account_infos(self) -> List[Dict[str, object]]:
        return []

    def get_account_statuses(self) -> List[Dict[str, object]]:
        return []

    @abstractmethod
    def set_event_callback(self, callback: TradeProviderCallback) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_asset(self, account_id: str = "", account_type: str = "") -> Optional[Dict[str, object]]:
        raise NotImplementedError

    @abstractmethod
    def get_orders(self, account_id: str = "", account_type: str = "") -> List[Dict[str, object]]:
        raise NotImplementedError

    @abstractmethod
    def get_order(self, account_id: str, order_id: int, account_type: str = "") -> Optional[Dict[str, object]]:
        raise NotImplementedError

    @abstractmethod
    def get_trades(self, account_id: str = "", account_type: str = "") -> List[Dict[str, object]]:
        raise NotImplementedError

    @abstractmethod
    def get_positions(self, account_id: str = "", account_type: str = "") -> List[Dict[str, object]]:
        raise NotImplementedError

    @abstractmethod
    def get_position(
        self,
        account_id: str,
        symbol: str,
        account_type: str = "",
    ) -> Optional[Dict[str, object]]:
        raise NotImplementedError

    @abstractmethod
    def place_order(self, payload: Dict[str, object]) -> Dict[str, object]:
        raise NotImplementedError

    @abstractmethod
    def cancel_order(self, payload: Dict[str, object]) -> Dict[str, object]:
        raise NotImplementedError

    def get_credit_detail(self, account_id: str = "", account_type: str = "") -> Optional[Dict[str, object]]:
        return None

    def get_credit_compacts(self, account_id: str = "", account_type: str = "") -> List[Dict[str, object]]:
        return []

    def get_credit_subjects(self, account_id: str = "", account_type: str = "") -> List[Dict[str, object]]:
        return []

    def get_credit_slo_codes(self, account_id: str = "", account_type: str = "") -> List[Dict[str, object]]:
        return []

    def get_credit_assure(self, account_id: str = "", account_type: str = "") -> List[Dict[str, object]]:
        return []

    def close(self) -> None:
        return None
