"""Benchmark helpers for local MemLite search workloads."""

from __future__ import annotations

from statistics import mean
from time import perf_counter
from uuid import uuid4

from memolite.common.config import Settings


async def benchmark_search_workload(
    *,
    settings: Settings,
    episode_count: int = 25,
    query_iterations: int = 10,
) -> dict[str, float | int]:
    """Seed a small workload and measure episodic and semantic search latency."""
    from memolite.app.resources import ResourceManager

    resources = ResourceManager.create(settings)
    await resources.initialize()
    try:
        run_id = uuid4().hex[:8]
        project_id = f"bench-project-{run_id}"
        session_key = f"bench-session-{run_id}"
        set_id = f"bench-set-{run_id}"
        await resources.project_store.create_project("bench-org", project_id)
        await resources.session_store.create_session(
            session_key=session_key,
            org_id="bench-org",
            project_id=project_id,
            session_id=session_key,
            user_id="bench-user",
        )
        for index in range(episode_count):
            episode_uid = f"bench-episode-{run_id}-{index}"
            content = (
                f"Travel preference note {index}. "
                "Seat preference is aisle for long flight trips."
            )
            await resources.episode_store.add_episode(
                {
                    "uid": episode_uid,
                    "session_key": session_key,
                    "session_id": session_key,
                    "producer_id": "bench-user",
                    "producer_role": "user",
                    "sequence_num": index,
                    "content": content,
                    "content_type": "text",
                    "episode_type": "message",
                    "metadata_json": '{"source":"benchmark"}',
                }
            )
            episode = (await resources.episode_store.get_episodes([episode_uid]))[0]
            await resources.derivative_pipeline.create_derivatives(episode)

        await resources.semantic_feature_store.add_feature(
            set_id=set_id,
            category="profile",
            tag="travel",
            feature_name="seat_preference",
            value="aisle",
            embedding=await resources.semantic_service.generate_feature_embedding(
                "aisle travel preference"
            ),
        )

        episodic_timings: list[float] = []
        semantic_timings: list[float] = []
        for _ in range(query_iterations):
            started = perf_counter()
            await resources.episodic_search.search(
                query="travel seat preference",
                session_id=session_key,
                limit=5,
            )
            episodic_timings.append((perf_counter() - started) * 1000)

            started = perf_counter()
            await resources.semantic_service.semantic_search(
                query="travel seat preference",
                set_id=set_id,
                tag="travel",
                limit=5,
            )
            semantic_timings.append((perf_counter() - started) * 1000)

        return {
            "episode_count": episode_count,
            "query_iterations": query_iterations,
            "episodic_avg_latency_ms": round(mean(episodic_timings), 3),
            "episodic_p95_latency_ms": round(_percentile(episodic_timings, 0.95), 3),
            "semantic_avg_latency_ms": round(mean(semantic_timings), 3),
            "semantic_p95_latency_ms": round(_percentile(semantic_timings, 0.95), 3),
        }
    finally:
        await resources.close()


def _percentile(values: list[float], ratio: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(max(int(len(ordered) * ratio) - 1, 0), len(ordered) - 1)
    return ordered[index]
