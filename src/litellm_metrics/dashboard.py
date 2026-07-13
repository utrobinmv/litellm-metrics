"""litellm-metrics -- Real-time console dashboard for LiteLLM proxy monitoring.

Uses Rich Live Display.
Fetches metrics from /metrics/ endpoint in Prometheus format.

Sections:
  1. REAL-TIME (green border) -- updates every N sec
     Proxy Info, Live Requests, Live Tokens, Live Process
  2. LIFETIME (blue border) -- cumulative counters
     Total Requests, Total Tokens & Spend, Deployments, HTTP, GC
  3. PERCENTILES (magenta border) -- cumulative histograms
     Latency, Spend by Model
"""

import time
from datetime import datetime

import requests
from rich.columns import Columns
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table

from .metrics_parser import PrometheusParser

# -- Formatting utilities ------------------------------------------------

def fmt_bytes(n: float) -> str:
    """Format bytes into human readable."""
    if n < 0:
        return "N/A"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}PB"


def fmt_tokens(n: float) -> str:
    """Format token counts."""
    if n >= 1e9:
        return f"{n/1e9:.2f}B"
    if n >= 1e6:
        return f"{n/1e6:.2f}M"
    if n >= 1e3:
        return f"{n/1e3:.1f}K"
    return f"{n:.0f}"


def fmt_time(s: float) -> str:
    """Format seconds."""
    if s < 0.001:
        return f"{s*1e6:.0f}us"
    if s < 1:
        return f"{s*1000:.1f}ms"
    if s < 60:
        return f"{s:.2f}s"
    return f"{s/60:.1f}m"


def fmt_uptime(seconds: float) -> str:
    """Format uptime."""
    days = int(seconds // 86400)
    hours = int((seconds % 86400) // 3600)
    mins = int((seconds % 3600) // 60)
    if days > 0:
        return f"{days}d {hours}h {mins}m"
    if hours > 0:
        return f"{hours}h {mins}m"
    return f"{mins}m"


def fmt_dollars(n: float) -> str:
    """Format dollars."""
    if n >= 1e6:
        return f"${n/1e6:.2f}M"
    if n >= 1e3:
        return f"${n/1e3:.2f}K"
    return f"${n:.4f}"


# -- Metric name aliases (LiteLLM appends _total to counters) -----------

# Counter metrics -- real names on the wire
M_TOTAL_REQ = "litellm_proxy_total_requests_metric_total"
M_FAILED_REQ = "litellm_proxy_failed_requests_metric_total"
M_FAILED_REQ_ALT = "litellm_llm_api_failed_requests_metric_total"
M_SPEND = "litellm_spend_metric_total"
M_TOTAL_TOKENS = "litellm_total_tokens_metric_total"
M_INPUT_TOKENS = "litellm_input_tokens_metric_total"
M_OUTPUT_TOKENS = "litellm_output_tokens_metric_total"

# Deployment counters (also have _total suffix on real server)
M_DEPLOY_SUCCESS = "litellm_deployment_success_responses_total"
M_DEPLOY_FAILURE = "litellm_deployment_failure_responses_total"
M_DEPLOY_TOTAL = "litellm_deployment_total_requests_total"

# Histogram metrics -- no _total suffix
H_TOTAL_LATENCY = "litellm_request_total_latency_metric"
H_LLM_LATENCY = "litellm_llm_api_latency_metric"
H_OVERHEAD_LATENCY = "litellm_overhead_latency_metric"
H_TTFT = "litellm_llm_api_time_to_first_token_metric"
H_DEPLOY_LATENCY = "litellm_deployment_latency_per_output_token"


# -- Metrics collector ---------------------------------------------------

class MetricsCollector:
    """Fetches and parses metrics from a LiteLLM proxy server."""

    def __init__(self, metrics_url: str, api_key: str = ""):
        self.metrics_url = metrics_url
        self.headers: dict[str, str] = {}
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"
        self.parser = PrometheusParser(skip_system=False)

    def fetch(self) -> str:
        """Fetch raw metrics text."""
        resp = requests.get(self.metrics_url, headers=self.headers, timeout=10)
        resp.raise_for_status()
        return resp.text

    def collect(self) -> dict:
        """Fetch, parse, and structure all metrics."""
        raw = self.fetch()
        samples = self.parser.parse(raw)
        histograms = self.parser.parse_histogram(samples)

        gauge: dict[str, float] = {}
        counter: dict[str, float] = {}
        for s in samples:
            if s.metric_type == "gauge":
                gauge[s.name] = s.value
            elif s.metric_type == "counter":
                counter[s.name] = s.value

        return {
            "samples": samples,
            "histograms": histograms,
            "gauge": gauge,
            "counter": counter,
            "raw": raw,
        }


# -- Dashboard panels ----------------------------------------------------

class Dashboard:
    """Builds a Rich dashboard from collected LiteLLM proxy metrics."""

    def __init__(self, config: dict):
        self.config = config
        self.start_time = time.time()
        self.prev_counters: dict[str, tuple[float, float]] = {}
        self.console = Console()

    def _rate(self, name: str, value: float) -> float:
        """Compute rate (delta / time) for counter metrics."""
        now = time.time()
        prev_val, prev_time = self.prev_counters.get(name, (value, now))
        rate = (value - prev_val) / max(now - prev_time, 0.001)
        self.prev_counters[name] = (value, now)
        return max(rate, 0)

    # -- REAL-TIME -----------------------------------------------------

    def _proxy_info_panel(self, metrics: dict) -> Panel:
        """Top panel: proxy information."""
        g = metrics["gauge"]

        url = self.config["metrics_url"].rstrip("/")
        uptime = time.time() - self.start_time
        process_start = g.get("process_start_time_seconds", 0)
        server_uptime = time.time() - process_start if process_start > 0 else uptime

        content = Table(show_header=False, box=None, padding=(0, 1))
        content.add_column("Metric", style="bold cyan", width=38)
        content.add_column("Value", style="white")

        content.add_row("Server", f"{url}")
        content.add_row("Dashboard Uptime", fmt_uptime(uptime))
        content.add_row("Process Uptime", fmt_uptime(server_uptime))

        title = f" LITELLM METRICS  |  {datetime.now().strftime('%H:%M:%S')} "
        return Panel(content, title=title, border_style="bold green", padding=(0, 1))

    def _live_requests_panel(self, metrics: dict) -> Panel:
        """Panel: current request rates."""
        c = metrics["counter"]

        # Sum across all label combinations
        total_req = sum(v for k, v in c.items() if k == M_TOTAL_REQ)
        # Try both failed request metric names
        failed_req = sum(v for k, v in c.items() if k in (M_FAILED_REQ, M_FAILED_REQ_ALT))

        total_rate = self._rate(M_TOTAL_REQ, total_req)
        failed_rate = self._rate(M_FAILED_REQ, failed_req)

        success_rate = total_rate - failed_rate
        err_style = "red" if failed_rate > 0 else "green"

        content = Table(show_header=False, box=None, padding=(0, 1))
        content.add_column("Metric", style="bold cyan", width=38)
        content.add_column("Value", style="white", justify="right")

        content.add_row("litellm_proxy_total_requests (rate)",
                        f"[bold green]{total_rate:.2f}")
        content.add_row("litellm_proxy_failed_requests (rate)",
                        f"[bold {err_style}]{failed_rate:.2f}")
        content.add_row("Success rate (req/s)",
                        f"[bold green]{success_rate:.2f}")

        return Panel(content, title=" LIVE REQUESTS ", border_style="green", padding=(0, 1))

    def _live_tokens_panel(self, metrics: dict) -> Panel:
        """Panel: current token rates."""
        c = metrics["counter"]

        input_total = sum(v for k, v in c.items() if k == M_INPUT_TOKENS)
        output_total = sum(v for k, v in c.items() if k == M_OUTPUT_TOKENS)

        input_rate = self._rate(M_INPUT_TOKENS, input_total)
        output_rate = self._rate(M_OUTPUT_TOKENS, output_total)

        content = Table(show_header=False, box=None, padding=(0, 1))
        content.add_column("Metric", style="bold cyan", width=38)
        content.add_column("Value", style="white", justify="right")

        content.add_row("litellm_input_tokens (rate)",
                        f"[bold green]{input_rate:.1f}")
        content.add_row("litellm_output_tokens (rate)",
                        f"[bold green]{output_rate:.1f}")

        return Panel(content, title=" LIVE TOKENS ", border_style="green", padding=(0, 1))

    def _live_process_panel(self, metrics: dict) -> Panel:
        """Panel: current system metrics."""
        g = metrics["gauge"]
        c = metrics["counter"]

        virt_mem = g.get("process_virtual_memory_bytes", 0)
        res_mem = g.get("process_resident_memory_bytes", 0)
        cpu_sec = c.get("process_cpu_seconds_total", 0)
        open_fds = g.get("process_open_fds", 0)
        max_fds = g.get("process_max_fds", 0)

        cpu_rate = self._rate("process_cpu_seconds_total", cpu_sec)

        content = Table(show_header=False, box=None, padding=(0, 1))
        content.add_column("Metric", style="bold cyan", width=38)
        content.add_column("Value", style="white", justify="right")

        content.add_row("process_virtual_memory_bytes", fmt_bytes(virt_mem))
        content.add_row("process_resident_memory_bytes", fmt_bytes(res_mem))
        content.add_row("process_cpu_seconds_total (rate)", f"{cpu_rate:.2f}")
        content.add_row("process_open_fds", f"{open_fds:.0f} / {max_fds:.0f}")

        return Panel(content, title=" LIVE PROCESS ", border_style="green", padding=(0, 1))

    # -- LIFETIME ------------------------------------------------------

    def _total_requests_panel(self, metrics: dict) -> Panel:
        """Panel: cumulative request stats by model."""
        model_stats: dict[str, dict] = {}

        for s in metrics["samples"]:
            if s.name == M_TOTAL_REQ:
                model = s.labels.get("requested_model", "unknown")
                if model not in model_stats:
                    model_stats[model] = {"total": 0, "failed": 0}
                model_stats[model]["total"] += s.value

            if s.name == M_FAILED_REQ or s.name == M_FAILED_REQ_ALT:
                model = s.labels.get("requested_model", "unknown")
                if model not in model_stats:
                    model_stats[model] = {"total": 0, "failed": 0}
                model_stats[model]["failed"] += s.value

        content = Table(show_header=True, box=None, padding=(0, 1))
        content.add_column("Model", style="bold cyan", width=28)
        content.add_column("Total", style="white", justify="right")
        content.add_column("Failed", style="red", justify="right")

        for model in sorted(model_stats.keys()):
            stats = model_stats[model]
            err_style = "red" if stats["failed"] > 0 else "green"
            content.add_row(
                model,
                f"{stats['total']:.0f}",
                f"[bold {err_style}]{stats['failed']:.0f}",
            )

        if not model_stats:
            content.add_row("No data", "", "")

        return Panel(content, title=" TOTAL REQUESTS BY MODEL ", border_style="blue", padding=(0, 1))

    def _total_tokens_spend_panel(self, metrics: dict) -> Panel:
        """Panel: cumulative tokens and spend."""
        c = metrics["counter"]

        input_total = sum(v for k, v in c.items() if k == M_INPUT_TOKENS)
        output_total = sum(v for k, v in c.items() if k == M_OUTPUT_TOKENS)
        total_tokens = sum(v for k, v in c.items() if k == M_TOTAL_TOKENS)
        total_spend = sum(v for k, v in c.items() if k == M_SPEND)

        content = Table(show_header=False, box=None, padding=(0, 1))
        content.add_column("Metric", style="bold cyan", width=38)
        content.add_column("Value", style="white", justify="right")

        content.add_row("litellm_input_tokens_metric", fmt_tokens(input_total))
        content.add_row("litellm_output_tokens_metric", fmt_tokens(output_total))
        content.add_row("litellm_total_tokens_metric", fmt_tokens(total_tokens))
        content.add_row("")
        content.add_row("litellm_spend_metric", f"[bold yellow]{fmt_dollars(total_spend)}")

        return Panel(content, title=" TOTAL TOKENS & SPEND ", border_style="blue", padding=(0, 1))

    def _deployments_panel(self, metrics: dict) -> Panel:
        """Panel: deployment states (LLM provider)."""
        provider_stats: dict[str, dict] = {}

        for s in metrics["samples"]:
            if s.name in (M_DEPLOY_SUCCESS, M_DEPLOY_FAILURE, M_DEPLOY_TOTAL):
                provider = s.labels.get("api_provider", "unknown")
                if provider not in provider_stats:
                    provider_stats[provider] = {"success": 0, "failure": 0, "total": 0}
                if s.name == M_DEPLOY_SUCCESS:
                    provider_stats[provider]["success"] += s.value
                elif s.name == M_DEPLOY_FAILURE:
                    provider_stats[provider]["failure"] += s.value
                elif s.name == M_DEPLOY_TOTAL:
                    provider_stats[provider]["total"] += s.value

        # Deployment state (gauge)
        deployment_states: dict[str, str] = {}
        for s in metrics["samples"]:
            if s.name == "litellm_deployment_state":
                provider = s.labels.get("api_provider", "unknown")
                state_val = s.value
                if state_val == 0:
                    state = "healthy"
                elif state_val == 1:
                    state = "partial"
                else:
                    state = "outage"
                deployment_states[provider] = state

        content = Table(show_header=True, box=None, padding=(0, 1))
        content.add_column("Provider", style="bold cyan", width=20)
        content.add_column("Success", style="green", justify="right")
        content.add_column("Failure", style="red", justify="right")
        content.add_column("Total", style="white", justify="right")
        content.add_column("State", style="yellow", justify="right")

        for provider in sorted(provider_stats.keys()):
            stats = provider_stats[provider]
            state = deployment_states.get(provider, "-")
            state_style = "green" if state == "healthy" else ("yellow" if state == "partial" else "red")
            content.add_row(
                provider,
                f"{stats['success']:.0f}",
                f"{stats['failure']:.0f}",
                f"{stats['total']:.0f}",
                f"[bold {state_style}]{state}",
            )

        if not provider_stats:
            content.add_row("No data", "", "", "", "")

        return Panel(content, title=" DEPLOYMENTS ", border_style="blue", padding=(0, 1))

    def _http_panel(self, metrics: dict) -> Panel:
        """Panel: HTTP metrics."""
        h = metrics["histograms"]
        parser = PrometheusParser()

        http_counts: dict[str, float] = {}
        for s in metrics["samples"]:
            if s.name == "http_requests_total":
                method = s.labels.get("method", "")
                status = s.labels.get("status", "")
                key = f"{method} {status}"
                http_counts[key] = s.value

        def http_pct(p: float) -> str:
            hist = h.get("http_request_duration_highr_seconds")
            if not hist or not hist["buckets"]:
                return "N/A"
            return fmt_time(parser.percentile_from_histogram(hist["buckets"], p))

        content = Table(show_header=False, box=None, padding=(0, 1))
        content.add_column("Metric", style="bold cyan", width=40)
        content.add_column("Value", style="white", justify="right")

        for key in sorted(http_counts.keys()):
            content.add_row(f"http_requests_total{{{key}}}", f"{http_counts[key]:.0f}")

        if not http_counts:
            content.add_row("http_requests_total", "No data")

        content.add_row("")
        content.add_row("http_request_duration p50", f"[green]{http_pct(0.5)}")
        content.add_row("http_request_duration p95", f"[yellow]{http_pct(0.95)}")
        content.add_row("http_request_duration p99", f"[red]{http_pct(0.99)}")

        return Panel(content, title=" HTTP ", border_style="blue", padding=(0, 1))

    def _gc_panel(self, metrics: dict) -> Panel:
        """Panel: Python garbage collector."""
        gc_0 = gc_1 = gc_2 = 0
        for s in metrics["samples"]:
            if s.name == "python_gc_collections_total":
                gen = s.labels.get("generation", "")
                if gen == "0":
                    gc_0 = s.value
                elif gen == "1":
                    gc_1 = s.value
                elif gen == "2":
                    gc_2 = s.value

        content = Table(show_header=False, box=None, padding=(0, 1))
        content.add_column("Metric", style="bold cyan", width=40)
        content.add_column("Value", style="white", justify="right")

        content.add_row("python_gc_collections_total{gen=0}", f"{gc_0:.0f}")
        content.add_row("python_gc_collections_total{gen=1}", f"{gc_1:.0f}")
        content.add_row("python_gc_collections_total{gen=2}", f"{gc_2:.0f}")

        return Panel(content, title=" PYTHON GC ", border_style="blue", padding=(0, 1))

    def _callback_failures_panel(self, metrics: dict) -> Panel:
        """Panel: callback logging errors."""
        callback_failures: dict[str, float] = {}
        for s in metrics["samples"]:
            if s.name == "litellm_callback_logging_failures_metric":
                cb_name = s.labels.get("callback_name", "unknown")
                callback_failures[cb_name] = s.value

        content = Table(show_header=True, box=None, padding=(0, 1))
        content.add_column("Callback", style="bold cyan", width=30)
        content.add_column("Failures", style="red", justify="right")

        for cb in sorted(callback_failures.keys()):
            content.add_row(cb, f"{callback_failures[cb]:.0f}")

        if not callback_failures:
            content.add_row("No failures", "0")

        return Panel(content, title=" CALLBACK FAILURES ", border_style="blue", padding=(0, 1))

    # -- PERCENTILES ---------------------------------------------------

    def _latency_panel(self, metrics: dict) -> Panel:
        """Panel: latency percentiles (histograms)."""
        h = metrics["histograms"]
        parser = PrometheusParser()

        def pct(name: str, p: float) -> str:
            hist = h.get(name)
            if not hist or not hist["buckets"]:
                return "N/A"
            val = parser.percentile_from_histogram(hist["buckets"], p)
            return fmt_time(val)

        content = Table(show_header=False, box=None, padding=(0, 1))
        content.add_column("Metric", style="bold cyan", width=40)
        content.add_column("p50", style="green", justify="right")
        content.add_column("p90", style="yellow", justify="right")
        content.add_column("p99", style="red", justify="right")

        content.add_row("litellm_request_total_latency",
                        pct(H_TOTAL_LATENCY, 0.5),
                        pct(H_TOTAL_LATENCY, 0.9),
                        pct(H_TOTAL_LATENCY, 0.99))
        content.add_row("litellm_llm_api_latency",
                        pct(H_LLM_LATENCY, 0.5),
                        pct(H_LLM_LATENCY, 0.9),
                        pct(H_LLM_LATENCY, 0.99))
        content.add_row("litellm_overhead_latency",
                        pct(H_OVERHEAD_LATENCY, 0.5),
                        pct(H_OVERHEAD_LATENCY, 0.9),
                        pct(H_OVERHEAD_LATENCY, 0.99))
        content.add_row("litellm_llm_api_ttft",
                        pct(H_TTFT, 0.5),
                        pct(H_TTFT, 0.9),
                        pct(H_TTFT, 0.99))
        content.add_row("litellm_deployment_latency_per_tok",
                        pct(H_DEPLOY_LATENCY, 0.5),
                        pct(H_DEPLOY_LATENCY, 0.9),
                        pct(H_DEPLOY_LATENCY, 0.99))

        return Panel(content, title=" LATENCY (cumulative) ", border_style="magenta", padding=(0, 1))

    def _spend_by_model_panel(self, metrics: dict) -> Panel:
        """Panel: spend and tokens by model."""
        model_spend: dict[str, float] = {}
        model_tokens: dict[str, float] = {}

        for s in metrics["samples"]:
            if s.name == M_SPEND:
                model = s.labels.get("model", "unknown")
                model_spend[model] = s.value
            if s.name == M_TOTAL_TOKENS:
                model = s.labels.get("model", "unknown")
                model_tokens[model] = s.value

        content = Table(show_header=True, box=None, padding=(0, 1))
        content.add_column("Model", style="bold cyan", width=30)
        content.add_column("Spend", style="yellow", justify="right")
        content.add_column("Tokens", style="white", justify="right")

        all_models = sorted(set(list(model_spend.keys()) + list(model_tokens.keys())))
        for model in all_models:
            spend = model_spend.get(model, 0)
            tokens = model_tokens.get(model, 0)
            content.add_row(model, fmt_dollars(spend), fmt_tokens(tokens))

        if not all_models:
            content.add_row("No data", "", "")

        return Panel(content, title=" SPEND BY MODEL ", border_style="magenta", padding=(0, 1))

    def _fallback_panel(self, metrics: dict) -> Panel:
        """Panel: failover metrics."""
        successful_fallbacks = 0
        failed_fallbacks = 0
        cooled_down = 0

        for s in metrics["samples"]:
            if s.name == "litellm_deployment_successful_fallbacks":
                successful_fallbacks += s.value
            elif s.name == "litellm_deployment_failed_fallbacks":
                failed_fallbacks += s.value
            elif s.name == "litellm_deployment_cooled_down":
                cooled_down += s.value

        err_style = "red" if failed_fallbacks > 0 else "green"

        content = Table(show_header=False, box=None, padding=(0, 1))
        content.add_column("Metric", style="bold cyan", width=40)
        content.add_column("Value", style="white", justify="right")

        content.add_row("litellm_deployment_successful_fallbacks",
                        f"[bold green]{successful_fallbacks:.0f}")
        content.add_row("litellm_deployment_failed_fallbacks",
                        f"[bold {err_style}]{failed_fallbacks:.0f}")
        content.add_row("litellm_deployment_cooled_down",
                        f"{cooled_down:.0f}")

        return Panel(content, title=" FAILBACK ", border_style="magenta", padding=(0, 1))

    def _all_metrics_panel(self, metrics: dict) -> Panel:
        """Panel: full list of all metrics (for detailed analysis)."""
        content = Table(show_header=True, box=None, padding=(0, 1))
        content.add_column("Metric", style="bold cyan", width=42)
        content.add_column("Value", style="white", justify="right")
        content.add_column("Labels", style="dim", width=30)

        for s in sorted(metrics["samples"], key=lambda x: x.name):
            if s.name.endswith("_bucket") or s.name.endswith("_created"):
                continue
            labels = ", ".join(f'{k}={v}' for k, v in s.labels.items()) or "-"
            if s.value >= 1e9:
                val = f"{s.value/1e9:.2f}B"
            elif s.value >= 1e6:
                val = f"{s.value/1e6:.2f}M"
            elif s.value >= 1e3:
                val = f"{s.value/1e3:.1f}K"
            elif s.value == int(s.value):
                val = f"{s.value:.0f}"
            else:
                val = f"{s.value:.4g}"
            content.add_row(s.name, val, labels)

        return Panel(content, title=" ALL METRICS (raw) ", border_style="dim white", padding=(0, 1))

    def build(self, metrics: dict) -> Group:
        """
        Build the full dashboard.
        Returns a Rich Group with all panels.
        """
        # REAL-TIME
        proxy_info = self._proxy_info_panel(metrics)
        live_req = self._live_requests_panel(metrics)
        live_tok = self._live_tokens_panel(metrics)
        live_proc = self._live_process_panel(metrics)

        # LIFETIME
        total_req = self._total_requests_panel(metrics)
        total_tok = self._total_tokens_spend_panel(metrics)
        deployments = self._deployments_panel(metrics)
        http_pan = self._http_panel(metrics)
        gc_pan = self._gc_panel(metrics)
        cb_fail = self._callback_failures_panel(metrics)

        # PERCENTILES
        latency_pan = self._latency_panel(metrics)
        spend_pan = self._spend_by_model_panel(metrics)
        fallback_pan = self._fallback_panel(metrics)

        return Group(
            proxy_info,
            Columns([live_req, live_tok, live_proc], equal=True, expand=True),
            Columns([total_req, total_tok, deployments], equal=True, expand=True),
            Columns([http_pan, gc_pan, cb_fail], equal=True, expand=True),
            Columns([latency_pan, spend_pan], equal=True, expand=True),
            fallback_pan,
        )
