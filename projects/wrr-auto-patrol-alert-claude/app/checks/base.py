from __future__ import annotations

from abc import ABC, abstractmethod

import httpx

from app.models.result import CheckResult
from app.models.rule import PatrolRule


class BaseCheck(ABC):
    @abstractmethod
    async def execute(self, rule: PatrolRule, client: httpx.AsyncClient) -> CheckResult:
        ...
