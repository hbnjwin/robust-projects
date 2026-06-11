"""REST API routes for the patrol system."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

if TYPE_CHECKING:
    from app.checker.engine import PatrolEngine
    from app.config.loader import ConfigLoader
    from app.scheduler.job_manager import JobManager
    from app.alert.aggregator import AlertAggregator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

# These are set by main.py at startup
_config_loader: ConfigLoader | None = None
_engine: PatrolEngine | None = None
_job_manager: JobManager | None = None
_aggregator: AlertAggregator | None = None


def init_routes(
    config_loader: ConfigLoader,
    engine: PatrolEngine,
    job_manager: JobManager,
    aggregator: AlertAggregator,
) -> None:
    global _config_loader, _engine, _job_manager, _aggregator
    _config_loader = config_loader
    _engine = engine
    _job_manager = job_manager
    _aggregator = aggregator


class ReloadResponse(BaseModel):
    success: bool
    message: str
    rule_count: int = 0


class ManualCheckResponse(BaseModel):
    success: bool
    rule_id: str
    status_code: int | None = None
    response_time_ms: float = 0.0
    error: str | None = None


@router.get("/status")
async def get_status():
    """Get patrol system status and service health."""
    if not _engine:
        raise HTTPException(status_code=503, detail="System not initialized")

    statuses = _engine.statuses
    services = []
    for rule_id, status in statuses.items():
        services.append({
            "rule_id": status.rule_id,
            "service": status.service,
            "rule_name": status.rule_name,
            "is_healthy": status.is_healthy,
            "last_check": status.last_check.isoformat() if status.last_check else None,
            "last_success": status.last_success.isoformat() if status.last_success else None,
            "consecutive_failures": status.consecutive_failures,
            "response_time_ms": status.response_time_ms,
            "last_error": status.last_error,
        })

    total = len(services)
    healthy = sum(1 for s in services if s["is_healthy"])

    return {
        "status": "healthy" if healthy == total else "degraded" if healthy > 0 else "down",
        "total_checks": total,
        "healthy": healthy,
        "unhealthy": total - healthy,
        "services": services,
        "scheduled_jobs": _job_manager.get_job_info() if _job_manager else [],
    }


@router.get("/rules")
async def get_rules():
    """Get currently loaded patrol rules."""
    if not _config_loader:
        raise HTTPException(status_code=503, detail="Config not loaded")

    config = _config_loader.config
    return {
        "rules": [r.model_dump() for r in config.rules],
        "mute_periods": [m.model_dump() for m in config.mute_periods],
        "aggregation": config.aggregation.model_dump(),
    }


@router.post("/config/reload", response_model=ReloadResponse)
async def reload_config():
    """Manually trigger config reload."""
    if not _config_loader:
        raise HTTPException(status_code=503, detail="Config not loaded")

    success = _config_loader.reload()
    config = _config_loader.config

    return ReloadResponse(
        success=success,
        message="Config reloaded successfully" if success else "Config reload failed, old config retained",
        rule_count=len(config.rules),
    )


@router.post("/check/{rule_id}", response_model=ManualCheckResponse)
async def manual_check(rule_id: str):
    """Manually trigger a health check for a specific rule."""
    if not _config_loader or not _engine:
        raise HTTPException(status_code=503, detail="System not initialized")

    config = _config_loader.config
    rule = config.get_rule_by_id(rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail=f"Rule '{rule_id}' not found")

    result = await _engine.run_check(rule)

    return ManualCheckResponse(
        success=result.success,
        rule_id=result.rule_id,
        status_code=result.status_code,
        response_time_ms=result.response_time_ms,
        error=result.error,
    )


@router.get("/alerts")
async def get_alerts(limit: int = 50):
    """Get recent alert history."""
    if not _aggregator:
        raise HTTPException(status_code=503, detail="System not initialized")

    return {
        "alerts": _aggregator.get_recent_alerts(limit=min(limit, 100)),
        "total": len(_aggregator.get_recent_alerts(100)),
    }
