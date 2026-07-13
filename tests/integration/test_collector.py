"""Integration-тесты для MetricsCollector.

Риски: Сеть, авторизация, таймауты.
"""

import pytest
import requests
from pytest_httpserver import HTTPServer

from litellm_metrics.dashboard import MetricsCollector


@pytest.fixture(scope="session")
def httpserver_listen_address():
    return ("127.0.0.1", 0)


class TestCollector:
    """Тесты MetricsCollector."""

    def test_success_returns_parsed_data(self, httpserver: HTTPServer, full_metrics_text):
        """HTTP 200 → возвращает dict с parsed data."""
        httpserver.expect_request("/metrics").respond_with_data(full_metrics_text)
        collector = MetricsCollector(f"{httpserver.url_for('/metrics')}")
        result = collector.collect()
        assert "samples" in result
        assert "histograms" in result
        assert "gauge" in result
        assert "counter" in result
        assert "raw" in result
        assert len(result["samples"]) > 0

    def test_api_key_sent(self, httpserver: HTTPServer, full_metrics_text):
        """API Key есть → заголовок Authorization отправлен."""
        httpserver.expect_request(
            "/metrics",
            headers={"Authorization": "Bearer secret-key"},
        ).respond_with_data(full_metrics_text)
        collector = MetricsCollector(f"{httpserver.url_for('/metrics')}", api_key="secret-key")
        collector.collect()
        httpserver.check_assertions()

    def test_no_api_key_not_sent(self, httpserver: HTTPServer, full_metrics_text):
        """API Key пустой → заголовок не отправлен."""
        httpserver.expect_request("/metrics").respond_with_data(full_metrics_text)
        collector = MetricsCollector(f"{httpserver.url_for('/metrics')}", api_key="")
        collector.collect()
        httpserver.check_assertions()

    def test_http_500_raises(self, httpserver: HTTPServer):
        """HTTP 500 -> HTTPError."""
        httpserver.expect_request("/metrics").respond_with_data("Error", status=500)
        collector = MetricsCollector(f"{httpserver.url_for('/metrics')}")
        with pytest.raises(requests.HTTPError):
            collector.collect()

    def test_full_litellm_metrics_parsed(self, httpserver: HTTPServer, full_metrics_text):
        """Parsing full LiteLLM response."""
        httpserver.expect_request("/metrics").respond_with_data(full_metrics_text)
        collector = MetricsCollector(f"{httpserver.url_for('/metrics')}")
        result = collector.collect()
        # Check key metrics
        assert "litellm_proxy_total_requests_metric_total" in result["counter"]
        assert "litellm_spend_metric_total" in result["counter"]
