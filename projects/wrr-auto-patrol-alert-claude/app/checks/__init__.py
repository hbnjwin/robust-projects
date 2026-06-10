from app.checks.base import BaseCheck
from app.checks.http_check import HttpCheck
from app.checks.tcp_check import TcpCheck
from app.checks.metric_check import MetricCheck
from app.models.rule import CheckType

CHECK_REGISTRY: dict[CheckType, BaseCheck] = {
    CheckType.HTTP: HttpCheck(),
    CheckType.TCP: TcpCheck(),
    CheckType.METRIC: MetricCheck(),
}

__all__ = ["BaseCheck", "HttpCheck", "TcpCheck", "MetricCheck", "CHECK_REGISTRY"]
