from __future__ import annotations

import logging
from pathlib import Path

import yaml

from app.models.rule import PatrolRule

logger = logging.getLogger(__name__)


class RuleLoader:
    """Loads patrol rules from YAML. Supports hot-reload via file mtime polling."""

    def __init__(self, config_path: str) -> None:
        self._config_path = Path(config_path)
        self._last_mtime: float = 0
        self._current_rules: list[PatrolRule] = []

    def load_rules(self) -> list[PatrolRule]:
        """Read YAML file and parse into PatrolRule models."""
        if not self._config_path.exists():
            logger.error("Rules config not found: %s", self._config_path)
            return []

        try:
            raw = yaml.safe_load(self._config_path.read_text(encoding="utf-8"))
        except Exception:
            logger.exception("Failed to parse rules YAML: %s", self._config_path)
            return self._current_rules  # keep old rules on parse failure

        if not raw or "rules" not in raw:
            logger.warning("No 'rules' key in config file")
            return []

        rules: list[PatrolRule] = []
        for i, entry in enumerate(raw["rules"]):
            try:
                rules.append(PatrolRule(**entry))
            except Exception:
                logger.exception("Failed to parse rule #%d", i)

        self._last_mtime = self._config_path.stat().st_mtime
        self._current_rules = rules
        logger.info("Loaded %d patrol rules from %s", len(rules), self._config_path)
        return rules

    def check_and_reload(self) -> tuple[bool, list[PatrolRule]]:
        """Poll file mtime. If changed, reload. Returns (was_reloaded, current_rules)."""
        if not self._config_path.exists():
            return False, self._current_rules

        try:
            current_mtime = self._config_path.stat().st_mtime
        except OSError:
            return False, self._current_rules

        if current_mtime <= self._last_mtime:
            return False, self._current_rules

        logger.info("Rules file changed, reloading...")
        rules = self.load_rules()
        return True, rules

    def get_current_rules(self) -> list[PatrolRule]:
        return list(self._current_rules)
