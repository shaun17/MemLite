"""Application resource manager bootstrap."""

from dataclasses import dataclass

from memlite.common.config import Settings
from memlite.metrics.service import MetricsService


@dataclass
class ResourceManager:
    """Bootstrap runtime singleton-like services."""

    settings: Settings
    metrics: MetricsService

    @classmethod
    def create(cls, settings: Settings) -> "ResourceManager":
        return cls(settings=settings, metrics=MetricsService())
