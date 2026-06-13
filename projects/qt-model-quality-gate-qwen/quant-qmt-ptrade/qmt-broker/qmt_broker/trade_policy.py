from dataclasses import dataclass
from typing import Dict, Optional

from qmt_broker.config import BrokerConfig


@dataclass
class TradePolicyResult:
    ok: bool
    code: str = ""
    detail: str = ""

    def to_dict(self) -> Dict[str, object]:
        return {"ok": self.ok, "code": self.code, "detail": self.detail}


class TradePolicy:
    def __init__(self, config: BrokerConfig) -> None:
        self.config = config

    def describe(self) -> Dict[str, object]:
        return {
            "allowed_accounts": list(self.config.allowed_accounts),
            "allowed_account_types": list(self.config.allowed_account_types),
            "allowed_symbols": list(self.config.allowed_symbols),
            "blocked_symbols": list(self.config.blocked_symbols),
            "allowed_sides": list(self.config.allowed_sides),
            "max_order_volume": self.config.max_order_volume,
            "max_order_value": self.config.max_order_value,
            "allow_credit_queries": self.config.allow_credit_queries,
            "allow_credit_orders": self.config.allow_credit_orders,
            "require_order_approval": self.config.require_order_approval,
            "approval_accounts": list(self.config.approval_accounts),
            "approval_symbols": list(self.config.approval_symbols),
            "approval_order_value": self.config.approval_order_value,
            "approval_pending_ttl_sec": self.config.approval_pending_ttl_sec,
            "approval_reminder_before_sec": self.config.approval_reminder_before_sec,
            "approval_min_approvers": self.config.approval_min_approvers,
            "approvers": sorted((self.config.approver_secrets or {}).keys()),
        }

    def validate_order(self, payload: Dict[str, object]) -> TradePolicyResult:
        account_id = str(payload.get("account_id", "") or self.config.trader_account_id)
        account_type = str(
            payload.get("account_type", self.config.trader_account_type or "STOCK") or self.config.trader_account_type or "STOCK"
        ).upper()
        symbol = str(payload.get("symbol", "")).upper()
        side = str(payload.get("side", "")).lower()
        volume = int(payload.get("volume", 0))
        price = float(payload.get("estimated_price", payload.get("price", 0)) or 0)

        if self.config.allowed_accounts and account_id not in self.config.allowed_accounts:
            return TradePolicyResult(False, "account_not_allowed", "account_id is not in the allowed list")
        if self.config.allowed_account_types and account_type not in self.config.allowed_account_types:
            return TradePolicyResult(False, "account_type_not_allowed", "account_type is not in the allowed list")
        if account_type == "CREDIT" and not self.config.allow_credit_orders:
            return TradePolicyResult(False, "credit_orders_disabled", "credit orders are disabled by policy")
        if self.config.allowed_symbols and symbol not in self.config.allowed_symbols:
            return TradePolicyResult(False, "symbol_not_allowed", "symbol is not in the allowed list")
        if symbol and symbol in self.config.blocked_symbols:
            return TradePolicyResult(False, "symbol_blocked", "symbol is explicitly blocked")
        if self.config.allowed_sides and side not in self.config.allowed_sides:
            return TradePolicyResult(False, "side_not_allowed", "side is not allowed")
        if volume <= 0:
            return TradePolicyResult(False, "invalid_volume", "volume must be positive")
        if self.config.max_order_volume > 0 and volume > self.config.max_order_volume:
            return TradePolicyResult(False, "volume_exceeded", "volume exceeds max_order_volume")
        if self.config.max_order_value > 0:
            if price <= 0:
                return TradePolicyResult(False, "price_required", "price or estimated_price is required for risk checks")
            notional = price * volume
            if notional > self.config.max_order_value:
                return TradePolicyResult(False, "notional_exceeded", "order notional exceeds max_order_value")
        return TradePolicyResult(True)

    def validate_credit_query(self, account_type: str) -> TradePolicyResult:
        if (account_type or "CREDIT").upper() == "CREDIT" and not self.config.allow_credit_queries:
            return TradePolicyResult(False, "credit_queries_disabled", "credit queries are disabled by policy")
        return TradePolicyResult(True)

    def approval_reason(self, payload: Dict[str, object]) -> str:
        account_id = str(payload.get("account_id", "") or self.config.trader_account_id)
        symbol = str(payload.get("symbol", "")).upper()
        price = float(payload.get("estimated_price", payload.get("price", 0)) or 0)
        volume = int(payload.get("volume", 0) or 0)
        if self.config.require_order_approval:
            return "approval_required_by_policy"
        if self.config.approval_accounts and account_id in self.config.approval_accounts:
            return "approval_required_for_account"
        if self.config.approval_symbols and symbol in self.config.approval_symbols:
            return "approval_required_for_symbol"
        if self.config.approval_order_value > 0 and price > 0 and volume > 0:
            if price * volume >= self.config.approval_order_value:
                return "approval_required_for_order_value"
        if bool(payload.get("require_approval", False)):
            return "approval_required_by_request"
        return ""

    def validate_approver(self, approver_id: str, approver_secret: str) -> TradePolicyResult:
        approvers = self.config.approver_secrets or {}
        if not approvers:
            return TradePolicyResult(True)
        if not approver_id:
            return TradePolicyResult(False, "approver_required", "approver_id is required")
        expected = approvers.get(approver_id)
        if expected is None:
            return TradePolicyResult(False, "approver_unknown", "approver_id is not authorized")
        if approver_secret != expected:
            return TradePolicyResult(False, "approver_secret_invalid", "approver_secret is invalid")
        return TradePolicyResult(True)
