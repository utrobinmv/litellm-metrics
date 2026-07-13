# litellm-metrics

Real-time консольный дашборд для мониторинга LiteLLM proxy сервера.

Забирает метрики с `/metrics` endpoint (Prometheus format) и отображает их в терминале с автоматическим обновлением.

## Быстрый старт

```bash
git clone https://github.com/utrobinmv/litellm-metrics.git
cd litellm-metrics

# Установка
pip install -e ".[dev]"

# Настройка
cp .env.example .env
# Отредактируй .env под свой сервер

# Запуск
litellm-metrics
```

## Установка

```bash
# Из PyPI (когда будет доступно)
pip install litellm-metrics

# Из репозитория
git clone https://github.com/utrobinmv/litellm-metrics.git
cd litellm-metrics
pip install -e ".[dev]"
```

Подробная инструкция по установке с нуля -- в INSTALL.md.

## Использование

```bash
# Запуск (читает .env)
litellm-metrics

# С параметрами
litellm-metrics --url http://192.168.45.30:31003/metrics/ --interval 1
litellm-metrics --all-metrics    # + сырые метрики
```

## Настройка

Файл `.env` в корне проекта (шаблон в `.env.example`):

```ini
LITELLM_METRICS_URL=http://192.168.45.30:31003/metrics/
LITELLM_BASE_URL=http://192.168.45.30:31003
LITELLM_API_KEY=sk-litellm-...
REFRESH_INTERVAL=2
```

Приоритет: env-переменные > `.env` файл > значения по умолчанию.

## Что мониторит

### REAL-TIME (зелёная рамка) -- обновляется каждые N сек

- **Proxy Info** -- URL сервера, uptime, Redis latency
- **Live Requests** -- `litellm_proxy_total_requests_metric` (rate), `litellm_proxy_failed_requests_metric` (rate), success rate
- **Live Tokens** -- `litellm_input_tokens_metric` (rate), `litellm_output_tokens_metric` (rate)
- **Live Process** -- `process_virtual_memory_bytes`, `process_resident_memory_bytes`, `process_cpu_seconds_total` (rate), `process_open_fds`

### LIFETIME (синяя рамка) -- накопительные счётчики

- **Total Requests by Model** -- запросы и ошибки по моделям (`requested_model`)
- **Total Tokens & Spend** -- input/output/total токены, `litellm_spend_metric` ($)
- **Deployments** -- успех/ошибки по провайдерам (`api_provider`), состояние деплоя (healthy/partial/outage)
- **HTTP** -- `http_requests_total` по method+status, latency percentiles (p50/p95/p99)
- **Python GC** -- `python_gc_collections_total` по generation (0/1/2)
- **Callback Failures** -- ошибки callback-логирования (`litellm_callback_logging_failures_metric`)

### PERCENTILES (фиолетовая рамка) -- кумулятивные гистограммы

- **Latency** -- `litellm_request_total_latency`, `litellm_llm_api_latency`, `litellm_overhead_latency`, TTFT, latency per output token (p50/p90/p99)
- **Spend by Model** -- расход и токены по моделям
- **Failback** -- успешные/неудачные фолбэки, cooled down

## Тестирование

```bash
# Тесты
python -m pytest tests/ -v

# Тесты с покрытием
python -m pytest tests/ -v --cov=litellm_metrics --cov-report=term-missing

# Линтинг
ruff check src/ tests/

# Типизация
mypy src/litellm_metrics/
```

## Архитектура

```
litellm-metrics (CLI entry point: litellm_metrics.cli:cli)
├── litellm_metrics/__init__.py       -- __version__ = "0.1.0"
├── litellm_metrics/config.py         -- load_config() -- .env + os.environ
├── litellm_metrics/metrics_parser.py -- PrometheusParser, MetricSample
├── litellm_metrics/dashboard.py      -- MetricsCollector, Dashboard + 13 панелей
└── litellm_metrics/cli.py            -- parse_args(), cli() -- Rich Live loop
```
