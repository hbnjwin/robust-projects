"""Auto-patrol alert system — FastAPI entry point."""

from __future__ import annotations

import asyncio
import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app.alert.aggregator import AlertAggregator
from app.alert.dingtalk import DingTalkNotifier
from app.alert.mute import MuteManager
from app.api.routes import init_routes, router
from app.checker.engine import PatrolEngine
from app.config.loader import ConfigLoader
from app.config.models import PatrolConfig
from app.scheduler.job_manager import JobManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# Default config path
CONFIG_PATH = Path(__file__).parent.parent / "config" / "patrol_rules.yaml"

# Global references for lifecycle management
_loader: ConfigLoader | None = None
_job_manager: JobManager | None = None
_mute_check_task: asyncio.Task | None = None


def _on_config_reload(config: PatrolConfig) -> None:
    """Callback when config is hot-reloaded."""
    global _job_manager
    logger.info("Reloading all components with new config...")

    # Update mute manager
    _mute_manager = MuteManager(config.mute_periods)
    _aggregator_local.update_mute_manager(_mute_manager)
    _aggregator_local.update_config(config.aggregation)

    # Update notifier webhook
    _notifier_local.update_webhook(config.global_config.alert_webhook)

    # Sync scheduler jobs
    if _job_manager:
        _job_manager.sync_jobs(config)

    logger.info("All components reloaded successfully")


# Module-level references for the reload callback
_aggregator_local: AlertAggregator | None = None
_notifier_local: DingTalkNotifier | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle: startup and shutdown."""
    global _loader, _job_manager, _mute_check_task
    global _aggregator_local, _notifier_local

    logger.info("Starting auto-patrol system...")

    # 1. Load config
    _loader = ConfigLoader(CONFIG_PATH, on_reload=_on_config_reload)
    try:
        config = _loader.load()
    except Exception as e:
        logger.error("Failed to load config: %s", e)
        raise

    # 2. Initialize components
    notifier = DingTalkNotifier(config.global_config.alert_webhook)
    _notifier_local = notifier

    mute_manager = MuteManager(config.mute_periods)
    aggregator = AlertAggregator(notifier, mute_manager, config.aggregation)
    _aggregator_local = aggregator

    engine = PatrolEngine(aggregator)
    job_manager = JobManager(engine)
    _job_manager = job_manager

    # Wire config getter for job_manager to fetch latest rules
    job_manager.set_config_getter(lambda: _loader.config)

    # 3. Initialize API routes
    init_routes(_loader, engine, job_manager, aggregator)

    # 4. Sync jobs with current config
    job_manager.sync_jobs(config)

    # 5. Start scheduler
    job_manager.start()

    # 6. Start config file watcher
    _loader.start_watching()

    # 7. Start periodic mute transition checker (every 60s)
    async def _check_mute_loop():
        while True:
            await asyncio.sleep(60)
            try:
                await aggregator.check_mute_transition()
            except Exception:
                logger.exception("Error checking mute transition")

    _mute_check_task = asyncio.create_task(_check_mute_loop())

    logger.info(
        "Auto-patrol system started: %d rules, %d mute periods",
        len(config.get_enabled_rules()),
        len(config.mute_periods),
    )

    yield

    # Shutdown
    logger.info("Shutting down auto-patrol system...")
    if _mute_check_task:
        _mute_check_task.cancel()
    if _loader:
        _loader.stop_watching()
    if _job_manager:
        _job_manager.shutdown()
    logger.info("Auto-patrol system stopped")


app = FastAPI(
    title="Auto-Patrol Alert System",
    description="Intelligent auto-patrol with alert aggregation, mute periods, and hot-reloadable rules",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(router)


@app.get("/health")
async def health():
    return {"status": "ok"}
