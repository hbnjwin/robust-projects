from __future__ import annotations

import logging

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.checks import CHECK_REGISTRY
from app.checks.base import BaseCheck
from app.core.alert_engine import AlertEngine
from app.core.rule_loader import RuleLoader
from app.core.state_manager import StateManager
from app.models.rule import CheckType, PatrolRule

logger = logging.getLogger(__name__)


class PatrolEngine:
    """Orchestrates scheduled health checks using APScheduler."""

    def __init__(
        self,
        state_manager: StateManager,
        alert_engine: AlertEngine,
        rule_loader: RuleLoader,
        rule_reload_interval: int = 30,
    ) -> None:
        self._scheduler = AsyncIOScheduler()
        self._state_manager = state_manager
        self._alert_engine = alert_engine
        self._rule_loader = rule_loader
        self._rule_reload_interval = rule_reload_interval
        self._check_registry: dict[CheckType, BaseCheck] = dict(CHECK_REGISTRY)
        self._http_client: httpx.AsyncClient | None = None
        self._rules_map: dict[str, PatrolRule] = {}

    @property
    def state_manager(self) -> StateManager:
        return self._state_manager

    @property
    def alert_engine(self) -> AlertEngine:
        return self._alert_engine

    @property
    def rule_loader(self) -> RuleLoader:
        return self._rule_loader

    async def start(self, client: httpx.AsyncClient) -> None:
        self._http_client = client

        # Register rule-reload polling job
        self._scheduler.add_job(
            self._reload_rules_tick,
            trigger=IntervalTrigger(seconds=self._rule_reload_interval),
            id="__rule_reload_watcher__",
            replace_existing=True,
        )

        self._scheduler.start()
        logger.info("PatrolEngine started")

    async def stop(self) -> None:
        self._scheduler.shutdown(wait=False)
        logger.info("PatrolEngine stopped")

    def apply_rules(self, rules: list[PatrolRule]) -> dict[str, list[str]]:
        """Diff current jobs vs new rules. Add/remove/update scheduler jobs.
        Returns a summary of changes."""
        new_map = {r.rule_id: r for r in rules if r.enabled}
        old_ids = set(self._rules_map.keys())
        new_ids = set(new_map.keys())

        to_add = new_ids - old_ids
        to_remove = old_ids - new_ids
        to_update = new_ids & old_ids

        changes: dict[str, list[str]] = {"added": [], "removed": [], "updated": []}

        # Remove stale jobs
        for rule_id in to_remove:
            self._remove_job(rule_id)
            changes["removed"].append(rule_id)

        # Add new jobs
        for rule_id in to_add:
            self._add_job(new_map[rule_id])
            changes["added"].append(rule_id)

        # Update changed jobs
        for rule_id in to_update:
            old_rule = self._rules_map[rule_id]
            new_rule = new_map[rule_id]
            if old_rule != new_rule:
                self._remove_job(rule_id)
                self._add_job(new_rule)
                changes["updated"].append(rule_id)

        self._rules_map = new_map

        if any(changes.values()):
            logger.info(
                "Rules applied — added: %d, removed: %d, updated: %d",
                len(changes["added"]),
                len(changes["removed"]),
                len(changes["updated"]),
            )

        return changes

    def get_rules_map(self) -> dict[str, PatrolRule]:
        return dict(self._rules_map)

    def _add_job(self, rule: PatrolRule) -> None:
        self._scheduler.add_job(
            self._execute_check,
            trigger=IntervalTrigger(seconds=rule.interval_seconds),
            id=rule.rule_id,
            args=[rule],
            replace_existing=True,
        )
        logger.debug("Added patrol job: %s (every %ds)", rule.rule_id, rule.interval_seconds)

    def _remove_job(self, rule_id: str) -> None:
        try:
            self._scheduler.remove_job(rule_id)
        except Exception:
            pass  # job may not exist
        logger.debug("Removed patrol job: %s", rule_id)

    async def _execute_check(self, rule: PatrolRule) -> None:
        """Job callback: run check, update state, enqueue alert if needed."""
        checker = self._check_registry.get(rule.check_type)
        if checker is None:
            logger.error("No checker for type: %s", rule.check_type)
            return

        if self._http_client is None:
            logger.error("HTTP client not available")
            return

        try:
            result = await checker.execute(rule, self._http_client)
            logger.debug(
                "Check %s: %s (%s)",
                rule.rule_id,
                result.status.value,
                f"{result.response_time_ms}ms" if result.response_time_ms else "n/a",
            )

            event = await self._state_manager.process_result(result, rule)
            if event:
                await self._alert_engine.enqueue(event, rule)
        except Exception:
            logger.exception("Error executing check for %s", rule.rule_id)

    async def trigger_check(self, rule_id: str) -> dict | None:
        """Manually trigger a single check. Returns the check result or None."""
        rule = self._rules_map.get(rule_id)
        if rule is None:
            return None

        checker = self._check_registry.get(rule.check_type)
        if checker is None or self._http_client is None:
            return None

        result = await checker.execute(rule, self._http_client)
        event = await self._state_manager.process_result(result, rule)
        if event:
            await self._alert_engine.enqueue(event, rule)

        return result.model_dump()

    async def _reload_rules_tick(self) -> None:
        """Periodic callback: check if rules file changed and apply."""
        reloaded, rules = self._rule_loader.check_and_reload()
        if reloaded:
            changes = self.apply_rules(rules)
            # Clean up state for removed rules
            for rule_id in changes["removed"]:
                await self._state_manager.remove_state(rule_id)
