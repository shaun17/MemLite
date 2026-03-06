"""Minimal metrics service."""

from dataclasses import dataclass, field


@dataclass
class MetricsService:
    """In-memory metrics counters for bootstrap stage."""

    counters: dict[str, int] = field(default_factory=dict)

    def increment(self, name: str, value: int = 1) -> None:
        self.counters[name] = self.counters.get(name, 0) + value

    def snapshot(self) -> dict[str, int]:
        return dict(self.counters)
