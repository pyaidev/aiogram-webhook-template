from prometheus_client import CollectorRegistry, Counter, Histogram


class Metrics:
    def __init__(self) -> None:
        self.registry = CollectorRegistry()
        self.requests = Counter(
            "bot_http_requests_total",
            "HTTP responses",
            ["route", "status"],
            registry=self.registry,
        )
        self.duration = Histogram(
            "bot_http_duration_seconds",
            "HTTP request duration",
            ["route"],
            registry=self.registry,
        )
        self.accepted = Counter(
            "bot_webhook_updates_total",
            "Persisted webhook updates",
            ["result"],
            registry=self.registry,
        )
