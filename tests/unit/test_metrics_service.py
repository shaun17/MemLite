from memlite.metrics.service import MetricsService


def test_metrics_service_accumulates_counters():
    service = MetricsService()

    service.increment("requests")
    service.increment("requests", 2)

    assert service.snapshot()["counters"]["requests"] == 3


def test_metrics_service_tracks_timings():
    service = MetricsService()

    service.observe_timing("search_latency_ms", 10.0)
    service.observe_timing("search_latency_ms", 14.0)

    snapshot = service.snapshot()
    assert snapshot["timings_ms"]["search_latency_ms"]["count"] == 2
    assert snapshot["timings_ms"]["search_latency_ms"]["avg"] == 12.0
