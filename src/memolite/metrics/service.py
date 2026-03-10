"""In-memory metrics service with counters and latency histograms."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MetricsService:
    """Track counters and latency measurements in memory."""

    counters: dict[str, int] = field(default_factory=dict)
    timings_ms: dict[str, list[float]] = field(default_factory=dict)

    def increment(self, name: str, value: int = 1) -> None:
        self.counters[name] = self.counters.get(name, 0) + value

    def set_gauge(self, name: str, value: int) -> None:
        self.counters[name] = value

    def observe_timing(self, name: str, value_ms: float) -> None:
        bucket = self.timings_ms.setdefault(name, [])
        bucket.append(round(value_ms, 3))

    def snapshot(self) -> dict[str, object]:
        return {
            "counters": dict(self.counters),
            "timings_ms": {
                name: {
                    "count": len(values),
                    "last": values[-1] if values else 0.0,
                    "avg": round(sum(values) / len(values), 3) if values else 0.0,
                    "max": max(values) if values else 0.0,
                }
                for name, values in self.timings_ms.items()
            },
        }
