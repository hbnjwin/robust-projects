from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.patrol_engine import PatrolEngine

router = APIRouter(prefix="/api")


def _engine(request: Request) -> PatrolEngine:
    return request.app.state.patrol_engine


@router.get("/health")
async def health():
    """Liveness probe for the patrol service itself."""
    return {"status": "ok"}


@router.get("/status")
async def get_status(engine: PatrolEngine = Depends(_engine)):
    """Overall system status with per-rule alert states."""
    states = await engine.state_manager.get_all_states()
    rules_map = engine.get_rules_map()
    return {
        "active_rules": len(rules_map),
        "states": {
            rule_id: state.model_dump()
            for rule_id, state in states.items()
        },
    }


@router.get("/rules")
async def list_rules(engine: PatrolEngine = Depends(_engine)):
    """List current patrol rules."""
    rules = engine.rule_loader.get_current_rules()
    return {
        "count": len(rules),
        "rules": [r.model_dump() for r in rules],
    }


@router.post("/rules/reload")
async def reload_rules(engine: PatrolEngine = Depends(_engine)):
    """Force hot-reload of patrol rules from the config file."""
    reloaded, rules = engine.rule_loader.check_and_reload()
    if not reloaded:
        # Force reload even if mtime unchanged
        rules = engine.rule_loader.load_rules()

    changes = engine.apply_rules(rules)
    for rule_id in changes["removed"]:
        await engine.state_manager.remove_state(rule_id)

    return {
        "reloaded": True,
        "rules_count": len(rules),
        "changes": changes,
    }


@router.post("/patrol/{rule_id}/trigger")
async def trigger_check(
    rule_id: str, engine: PatrolEngine = Depends(_engine)
):
    """Manually trigger a single patrol check."""
    result = await engine.trigger_check(rule_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Rule '{rule_id}' not found")
    return result


@router.get("/alerts/history")
async def alert_history(engine: PatrolEngine = Depends(_engine)):
    """Recent alert events from in-memory ring buffer."""
    history = engine.alert_engine.get_history()
    return {
        "count": len(history),
        "alerts": [a.model_dump() for a in history],
    }


@router.get("/alerts/silenced")
async def silenced_alerts(engine: PatrolEngine = Depends(_engine)):
    """Alerts suppressed during silent windows."""
    silenced = engine.alert_engine.get_silenced()
    return {
        "count": len(silenced),
        "alerts": [
            {"event": e.model_dump(), "rule_id": r.rule_id}
            for e, r in silenced
        ],
    }
