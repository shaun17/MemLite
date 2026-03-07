"""HTTP load testing helpers for MemLite APIs."""

from __future__ import annotations

import asyncio
from statistics import mean
from time import perf_counter


async def load_test_memory_search(
    *,
    base_url: str,
    org_id: str,
    project_id: str,
    query: str,
    total_requests: int = 100,
    concurrency: int = 10,
    timeout_seconds: float = 5.0,
) -> dict[str, float | int]:
    """Run a concurrent load test against the memory search API."""
    import httpx

    limiter = asyncio.Semaphore(max(concurrency, 1))
    timings: list[float] = []
    failures = 0

    async with httpx.AsyncClient(base_url=base_url, timeout=timeout_seconds) as client:
        async def _single_request() -> None:
            nonlocal failures
            async with limiter:
                started = perf_counter()
                response = await client.post(
                    "/memories/search",
                    json={
                        "query": query,
                        "session_id": f"{org_id}:{project_id}:load-test",
                        "session_key": f"{org_id}:{project_id}:load-test",
                        "semantic_set_id": f"{org_id}:{project_id}:load-test",
                        "mode": "mixed",
                        "limit": 5,
                        "context_window": 1,
                    },
                )
                timings.append((perf_counter() - started) * 1000)
                if response.status_code >= 400:
                    failures += 1

        await asyncio.gather(*[_single_request() for _ in range(total_requests)])

    success_count = total_requests - failures
    return {
        "total_requests": total_requests,
        "concurrency": concurrency,
        "success_count": success_count,
        "failure_count": failures,
        "avg_latency_ms": round(mean(timings), 3) if timings else 0.0,
        "p95_latency_ms": round(_percentile(timings, 0.95), 3) if timings else 0.0,
        "max_latency_ms": round(max(timings), 3) if timings else 0.0,
    }


def _percentile(values: list[float], ratio: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(max(int(len(ordered) * ratio) - 1, 0), len(ordered) - 1)
    return ordered[index]
