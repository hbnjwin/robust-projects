from __future__ import annotations

from abc import ABC, abstractmethod

import httpx

from app.models.alert import AggregatedAlert
from app.models.rule import AlertChannelConfig


class BaseChannel(ABC):
    @abstractmethod
    async def send(
        self,
        alert: AggregatedAlert,
        config: AlertChannelConfig,
        client: httpx.AsyncClient,
    ) -> bool:
        """Send an aggregated alert. Return True if successful."""
        ...
