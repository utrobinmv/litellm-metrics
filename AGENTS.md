# litellm-metrics — AGENTS.md

## Архитектура

```
litellm-metrics (CLI entry point: litellm_metrics.cli:cli)
├── litellm_metrics/__init__.py       → __version__ = "0.1.0"
├── litellm_metrics/config.py         → load_config() — .env + os.environ
├── litellm_metrics/metrics_parser.py → PrometheusParser, MetricSample
├── litellm_metrics/dashboard.py      → MetricsCollector, Dashboard + 13 панелей
└── litellm_metrics/cli.py            → parse_args(), cli() — Rich Live loop
```

**pip-пакет** с `src/` layout. Установка: `pip install -e ".[dev]"`.

## Панели дашборда (13 штук, 3 секции)

### REAL-TIME (зелёная рамка, обновляется каждые N сек)
1. **Proxy Info** — URL, uptime, Redis latency
2. **Live Requests** — total/failed requests (rate), success rate
3. **Live Tokens** — input/output tokens (rate)
4. **Live Process** — virt/res mem, CPU rate, open/max FDs

### LIFETIME (синяя рамка, накопительные)
5. **Total Requests by Model** — запросы и ошибки по requested_model
6. **Total Tokens & Spend** — input/output/total токены, spend ($)
7. **Deployments** — success/failure по api_provider, deployment state
8. **HTTP** — requests by method+status, latency percentiles
9. **Python GC** — collections by generation (0/1/2)
10. **Callback Failures** — litellm_callback_logging_failures_metric

### PERCENTILES (фиолетовая рамка, кумулятивные)
11. **Latency** — 5 метрик (total, LLM API, overhead, TTFT, per-output-token), p50/p90/p99
12. **Spend by Model** — расход и токены по моделям
13. **Failback** — successful/failed fallbacks, cooled down

## Ключевые детали

- **Метрики названы как в Prometheus** — `litellm_proxy_total_requests_metric`, не "Total Requests"
- **Нет эмодзи** — чистый текстовый интерфейс
- **Нет plotext/графиков** — только Rich Tables + Panels
- **`_rate()`** — вычисляет delta/T для counter-метрик между опросами
- **Config priority**: env vars > `.env` file > defaults
- **`.env` ищется** через `Path(__file__).parent.parent.parent / ".env"` (корень проекта)
- **LiteLLM proxy URL**: http://192.168.45.30:31003

## Тестовая стратегия (risk-based)

| Уровень | Файл | Что тестирует | Почему |
|---|---|---|---|
| Unit | test_parser.py | Парсинг Prometheus, histogram, percentiles | Парсинг — основа всего |
| Unit | test_config.py | Приоритет env > .env > default | Неправильный приоритет = недоступный сервер |
| Unit | test_utils.py | Форматирование, rate calc, dollars | Математика, division by zero |
| Integration | test_collector.py | HTTP fetch, API key, error handling | Сетевое взаимодействие |
| Integration | test_dashboard.py | Пустые/нулевые данные → не краш | UI resilience |
| E2E | test_cli.py | `--help`, недоступный URL | Запуск приложения |

## Запуск

```bash
source .venv
litellm-metrics                          # из .env
litellm-metrics --url ... --interval 1   # с параметрами
litellm-metrics --all-metrics            # + сырые метрики
python -m litellm_metrics.cli            # альтернативный запуск
```

## Тестирование

```bash
source .venv
python -m pytest tests/ -v --cov=litellm_metrics --cov-report=term-missing
```
