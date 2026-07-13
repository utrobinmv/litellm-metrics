"""Integration-тесты для Dashboard resilience.

Риски: Падение UI при отсутствии данных или делении на ноль.
"""

import pytest

from litellm_metrics.dashboard import Dashboard


@pytest.fixture
def dashboard():
    return Dashboard(config={"metrics_url": "http://test", "refresh_interval": 2})


def _empty_metrics():
    """Полностью пустой dict метрик."""
    return {
        "samples": [],
        "histograms": {},
        "gauge": {},
        "counter": {},
        "raw": "",
    }


def _minimal_metrics():
    """Minimal dict with zeros."""
    return {
        "samples": [],
        "histograms": {},
        "gauge": {
            "process_virtual_memory_bytes": 0,
            "process_resident_memory_bytes": 0,
            "process_open_fds": 0,
            "process_max_fds": 0,
        },
        "counter": {
            "litellm_proxy_total_requests_metric_total": 0,
            "litellm_proxy_failed_requests_metric_total": 0,
            "litellm_input_tokens_metric_total": 0,
            "litellm_output_tokens_metric_total": 0,
            "litellm_total_tokens_metric_total": 0,
            "litellm_spend_metric_total": 0,
            "process_cpu_seconds_total": 0,
        },
        "raw": "",
    }


class TestDashboardResilience:
    """Тесты устойчивости Dashboard к отсутствию данных."""

    def test_empty_metrics_no_crash(self, dashboard):
        """Empty Metrics: пустой dict → не падает."""
        result = dashboard.build(_empty_metrics())
        assert result is not None

    def test_minimal_metrics_no_crash(self, dashboard):
        """Minimal Metrics: нули → не падает."""
        result = dashboard.build(_minimal_metrics())
        assert result is not None

    def test_all_panels_render_without_crash(self, dashboard):
        """Все панели рендерятся без краша на минимальных данных."""
        metrics = _minimal_metrics()
        panels = [
            dashboard._proxy_info_panel(metrics),
            dashboard._live_requests_panel(metrics),
            dashboard._live_tokens_panel(metrics),
            dashboard._live_process_panel(metrics),
            dashboard._total_requests_panel(metrics),
            dashboard._total_tokens_spend_panel(metrics),
            dashboard._deployments_panel(metrics),
            dashboard._http_panel(metrics),
            dashboard._gc_panel(metrics),
            dashboard._callback_failures_panel(metrics),
            dashboard._latency_panel(metrics),
            dashboard._spend_by_model_panel(metrics),
            dashboard._fallback_panel(metrics),
            dashboard._all_metrics_panel(metrics),
        ]
        assert all(p is not None for p in panels)
