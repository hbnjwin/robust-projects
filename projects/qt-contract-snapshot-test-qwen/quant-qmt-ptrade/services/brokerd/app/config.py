from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "brokerd"
    host: str = "127.0.0.1"
    port: int = 19090
    adapter_name: str = "qmt"
    terminal_adapter: str = "simulated"
    api_key: str | None = None
    state_path: str = "~/.openclaw/brokerd-state.json"
    live_routing_enabled: bool = False
    default_account_cash: float = 1000000.0
    background_process_enabled: bool = False
    background_process_interval_seconds: int = 5
    simulated_fill_mode: str = "immediate"
    simulated_fill_shares: int = 100
    simulated_last_price_markup_bps: float = 3.0
    qmt_terminal_path: str | None = None
    qmt_account_alias: str | None = None
    qmt_credential_profile: str | None = None
    qmt_process_name: str | None = None
    qmt_pid_file_path: str | None = None
    qmt_session_file_path: str | None = None
    qmt_lock_file_path: str | None = None
    qmt_singleton_required: bool = True
    qmt_start_command: str | None = None
    qmt_working_directory: str | None = None

    model_config = SettingsConfigDict(
        env_prefix="BROKERD_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
