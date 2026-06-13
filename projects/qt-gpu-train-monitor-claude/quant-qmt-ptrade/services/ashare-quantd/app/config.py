from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "ashare-quantd"
    host: str = "127.0.0.1"
    port: int = 8787
    timezone: str = "Asia/Shanghai"
    market_data_provider: str = "auto"
    intel_provider: str = "official"
    tushare_token: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "TS_TOKEN",
            "TUSHARE_TOKEN",
            "ASHARE_QUANTD_TS_TOKEN",
            "ASHARE_QUANTD_TUSHARE_TOKEN",
        ),
    )
    tushare_quote_ttl_seconds: int = 3600
    tushare_bars_ttl_seconds: int = 300
    tushare_error_ttl_seconds: int = 300
    tushare_intel_ttl_seconds: int = 900
    akshare_quote_ttl_seconds: int = 60
    akshare_bars_ttl_seconds: int = 120
    akshare_error_ttl_seconds: int = 120
    gov_policy_ttl_seconds: int = 1800
    cninfo_disclosure_ttl_seconds: int = 1800
    intel_event_store_path: str = "~/.openclaw/ashare-quantd-intel-events.json"
    intel_scheduler_targets_path: str = "~/.openclaw/ashare-quantd-intel-targets.json"
    intel_scheduler_enabled: bool = False
    intel_scheduler_interval_seconds: int = 900
    paper_ledger_path: str = "~/.openclaw/ashare-quantd-paper-ledger.json"
    paper_initial_cash: float = 1000000.0
    paper_slippage_bps: float = 4.0
    paper_min_commission: float = 5.0
    paper_stamp_duty_bps: float = 5.0
    paper_transfer_fee_bps: float = 1.0
    watchlist_path: str = "~/.openclaw/ashare-quantd-watchlist.json"
    watchlist_alerts_path: str = "~/.openclaw/ashare-quantd-watchlist-alerts.json"
    watchlist_scheduler_enabled: bool = False
    watchlist_scheduler_interval_seconds: int = 300
    broker_adapter: str = "disabled"
    broker_live_enabled: bool = False
    broker_state_path: str = "~/.openclaw/ashare-quantd-broker-state.json"
    broker_daemon_base_url: str | None = None
    broker_daemon_api_key: str | None = None
    broker_daemon_timeout_seconds: int = 10
    broker_daemon_adapter: str = "qmt"

    model_config = SettingsConfigDict(
        env_prefix="ASHARE_QUANTD_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )


settings = Settings()
