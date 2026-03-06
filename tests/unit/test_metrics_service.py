from memlite.metrics.service import MetricsService


def test_metrics_service_accumulates_counters():
    service = MetricsService()

    service.increment("requests")
    service.increment("requests", 2)

    assert service.snapshot()["requests"] == 3
