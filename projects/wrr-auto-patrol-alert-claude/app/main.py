from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from app.api.routes import router
from app.channels.dingtalk import DingTalkChannel
from app.config import AppSettings
from app.core.alert_engine import AlertEngine
from app.core.patrol_engine import PatrolEngine
from app.core.rule_loader import RuleLoader
from app.core.state_manager import StateManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = AppSettings()

    # Build components bottom-up
    state_manager = StateManager()
    alert_engine = AlertEngine(flush_interval=settings.alert_flush_interval_seconds)
    rule_loader = RuleLoader(config_path=settings.rules_config_path)
    patrol_engine = PatrolEngine(
        state_manager=state_manager,
        alert_engine=alert_engine,
        rule_loader=rule_loader,
        rule_reload_interval=settings.rule_reload_interval_seconds,
    )

    # Register alert channels
    alert_engine.register_channel("dingtalk", DingTalkChannel())

    # Shared HTTP client with connection pooling
    async with httpx.AsyncClient(
        limits=httpx.Limits(
            max_connections=settings.max_connections,
            max_keepalive_connections=settings.max_connections // 2,
        ),
        timeout=httpx.Timeout(settings.default_timeout_seconds),
    ) as client:
        # Load initial rules and apply to scheduler
        rules = rule_loader.load_rules()
        patrol_engine.apply_rules(rules)

        # Start engines
        await alert_engine.start(client)
        await patrol_engine.start(client)

        # Expose via app.state for API routes
        app.state.patrol_engine = patrol_engine
        app.state.settings = settings

        logger.info(
            "Auto-patrol service started with %d rules", len(rules)
        )

        yield

        # Shutdown
        await patrol_engine.stop()
        await alert_engine.stop()
        logger.info("Auto-patrol service stopped")


app = FastAPI(title="Auto Patrol Service", lifespan=lifespan)
app.include_router(router)
