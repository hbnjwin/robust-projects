"""YAML configuration loader with hot-reload support via watchdog."""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Callable, Optional

import yaml
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from app.config.models import PatrolConfig

logger = logging.getLogger(__name__)


class ConfigLoader:
    """Loads and hot-reloads patrol configuration from a YAML file."""

    def __init__(self, config_path: str | Path, on_reload: Optional[Callable[[PatrolConfig], None]] = None):
        self._config_path = Path(config_path)
        self._on_reload = on_reload
        self._config: Optional[PatrolConfig] = None
        self._lock = threading.RLock()
        self._observer: Optional[Observer] = None

    @property
    def config(self) -> PatrolConfig:
        """Get current config (thread-safe)."""
        with self._lock:
            if self._config is None:
                raise RuntimeError("Config not loaded. Call load() first.")
            return self._config

    def load(self) -> PatrolConfig:
        """Load config from YAML file. Raises on parse/validation error."""
        raw = self._config_path.read_text(encoding="utf-8")
        data = yaml.safe_load(raw)
        config = PatrolConfig.model_validate(data)
        with self._lock:
            self._config = config
        logger.info("Config loaded: %d rules, %d mute periods", len(config.rules), len(config.mute_periods))
        return config

    def reload(self) -> bool:
        """Reload config. Returns True on success, False on failure (keeps old config)."""
        try:
            new_config = self._load_raw()
            with self._lock:
                self._config = new_config
            logger.info(
                "Config reloaded: %d rules, %d mute periods",
                len(new_config.rules),
                len(new_config.mute_periods),
            )
            if self._on_reload:
                self._on_reload(new_config)
            return True
        except Exception as e:
            logger.error("Config reload failed, keeping old config: %s", e)
            return False

    def _load_raw(self) -> PatrolConfig:
        raw = self._config_path.read_text(encoding="utf-8")
        data = yaml.safe_load(raw)
        return PatrolConfig.model_validate(data)

    def start_watching(self) -> None:
        """Start watching the config file for changes."""
        handler = _ConfigFileHandler(self)
        self._observer = Observer()
        self._observer.schedule(handler, str(self._config_path.parent), recursive=False)
        self._observer.daemon = True
        self._observer.start()
        logger.info("Watching config file: %s", self._config_path)

    def stop_watching(self) -> None:
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None


class _ConfigFileHandler(FileSystemEventHandler):
    """Watchdog handler that triggers config reload on file change."""

    def __init__(self, loader: ConfigLoader):
        self._loader = loader
        self._config_name = Path(loader._config_path).name

    def on_modified(self, event):
        if event.is_directory:
            return
        if Path(event.src_path).name == self._config_name:
            logger.info("Config file changed, reloading...")
            self._loader.reload()

    def on_created(self, event):
        # Handle editors that delete+recreate (vim, etc.)
        self.on_modified(event)
