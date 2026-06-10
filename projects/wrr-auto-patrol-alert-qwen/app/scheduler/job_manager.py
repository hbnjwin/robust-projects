"""APScheduler job manager — dynamically manages patrol check jobs."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config.models import PatrolConfig, RuleConfig

if TYPE_CHECKING:
    from app.checker.engine import PatrolEngine

logger = logging.getLogger(__name__)

JOB_PREFIX = "patrol_"


class JobManager:
    """Manages APScheduler jobs for patrol health checks. Supports dynamic add/remove/update."""

    def __init__(self, engine: PatrolEngine):
        self._engine = engine
        self._scheduler = AsyncIOScheduler()
        self._loop: asyncio.AbstractEventLoop | None = None

    @property
    def scheduler(self) -> AsyncIOScheduler:
        return self._scheduler

    def start(self) -> None:
        self._loop = asyncio.get_event_loop()
        self._scheduler.start()
        logger.info("Job scheduler started")

    def shutdown(self) -> None:
        self._scheduler.shutdown(wait=False)
        logger.info("Job scheduler stopped")

    def sync_jobs(self, config: PatrolConfig) -> None:
        """Synchronize scheduler jobs with the current config rules."""
        enabled_rules = config.get_enabled_rules()
        self._engine.sync_rules(enabled_rules)

        desired_ids = {self._job_id(r) for r in enabled_rules}
        current_ids = {j.id for j in self._scheduler.get_jobs() if j.id.startswith(JOB_PREFIX)}

        # Remove jobs for deleted/disabled rules
        for job_id in current_ids - desired_ids:
            self._scheduler.remove_job(job_id)
            logger.info("Removed job: %s", job_id)

        # Add or update jobs for current rules
        for rule in enabled_rules:
            job_id = self._job_id(rule)
            existing = self._scheduler.get_job(job_id)

            if existing:
                # Update interval if changed
                trigger = existing.trigger
                if isinstance(trigger, IntervalTrigger):
                    current_interval = trigger.interval_length
                    new_interval = rule.interval_seconds
                    if current_interval != new_interval:
                        existing.reschedule(trigger=IntervalTrigger(seconds=rule.interval_seconds))
                        logger.info("Updated job %s interval: %d -> %d", job_id, current_interval, new_interval)
            else:
                self._add_job(rule)

    def _add_job(self, rule: RuleConfig) -> None:
        job_id = self._job_id(rule)
        self._scheduler.add_job(
            self._run_check,
            trigger=IntervalTrigger(seconds=rule.interval_seconds),
            id=job_id,
            name=rule.name,
            args=[rule.id],
            replace_existing=True,
            # Run immediately on first schedule, then at interval
            next_run_time=None,
        )
        # Also schedule an immediate first run
        self._scheduler.add_job(
            self._run_check,
            trigger="date",
            id=f"{job_id}_init",
            name=f"{rule.name} (initial)",
            args=[rule.id],
            replace_existing=True,
        )
        logger.info("Added job: %s (every %ds)", job_id, rule.interval_seconds)

    async def _run_check(self, rule_id: str) -> None:
        """Execute a check for the given rule ID."""
        # We need to get the current rule config (it may have been hot-reloaded)
        # The engine has the latest status, but we need the rule config.
        # We'll get it from the config loader via a callback stored on the engine.
        rule = self._get_current_rule(rule_id)
        if rule is None:
            logger.warning("Rule %s not found in current config, skipping", rule_id)
            return
        await self._engine.run_check(rule)

    def _get_current_rule(self, rule_id: str) -> RuleConfig | None:
        """Get current rule config. This is set by main.py via set_config_getter."""
        getter = getattr(self, "_config_getter", None)
        if getter:
            config = getter()
            return config.get_rule_by_id(rule_id)
        return None

    def set_config_getter(self, getter) -> None:
        """Set a callable that returns the current PatrolConfig."""
        self._config_getter = getter

    def get_job_info(self) -> list[dict]:
        """Get info about all scheduled jobs."""
        jobs = []
        for job in self._scheduler.get_jobs():
            if job.id.startswith(JOB_PREFIX):
                jobs.append({
                    "id": job.id,
                    "name": job.name,
                    "next_run": str(job.next_run_time) if job.next_run_time else None,
                })
        return jobs

    @staticmethod
    def _job_id(rule: RuleConfig) -> str:
        return f"{JOB_PREFIX}{rule.id}"
