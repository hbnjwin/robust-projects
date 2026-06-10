from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PATROL_")

    # Patrol rules config file path
    rules_config_path: str = "config/patrol_rules.yaml"

    # Alert aggregation flush interval (seconds)
    alert_flush_interval_seconds: int = 60

    # Default consecutive failures before alerting
    default_consecutive_failures_threshold: int = 3

    # Rule-reload polling interval (seconds)
    rule_reload_interval_seconds: int = 30

    # HTTP client defaults
    default_timeout_seconds: float = 10.0
    max_connections: int = 100

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
