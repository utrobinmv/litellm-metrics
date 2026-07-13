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
- **Live Throughput** -- `litellm_in_flight_requests` (текущие запросы), `litellm_output_tokens_metric` (rate, tok/s), `litellm_request_queue_time_seconds` (p50/p95/p99)

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

## Справочник метрик LiteLLM

Все метрики доступны через HTTP-GET запрос к эндпоинту `/metrics/` (trailing slash обязателен, без него -- 307 redirect). Формат ответа -- Prometheus text exposition format (`text/plain; version=0.0.4`).

```
curl http://<host>:<port>/metrics/
```

### Включение метрик

В `proxy_config.yaml` укажи callback `prometheus`:

```yaml
model_list:
  - model_name: gpt-4o
    litellm_params:
      model: gpt-4o

litellm_settings:
  callbacks: [prometheus]
```

### Особенности сырых данных

- **Counter-метрики** имеют суффикс `_total` в имени (например, `litellm_proxy_total_requests_metric_total`).
- **Histogram-метрики** разбиваются на `_bucket`, `_sum`, `_count` и `_created` -- для получения перцентилей нужно агрегировать бакеты.
- **Лейблы** -- каждая метрика может иметь множество комбинаций лейблов (model, api_key, user и т.д.). Для получения общего значения нужно суммировать все образцы с одинаковым именем.
- **`_created`** -- timestamp создания счётчика (gauge). Используется Prometheus для детекции сбросов.
- **Deprecated** -- `litellm_requests_metric` и `litellm_llm_api_failed_requests_metric` устарели, используйте `litellm_proxy_total_requests_metric` и `litellm_proxy_failed_requests_metric`.

### Proxy -- запросы и ошибки

| Метрика | Тип | Описание |
|---|---|---|
| `litellm_proxy_total_requests_metric_total` | counter | Общее количество запросов к прокси. Лейблы: `requested_model`, `route`, `status_code`, `client_ip`, `hashed_api_key`, `user`, `user_agent`, `team`, `org` и др. |
| `litellm_proxy_failed_requests_metric_total` | counter | Количество неудачных ответов от прокси. Лейблы: аналогично total. |
| `litellm_requests_metric_total` | counter | [DEPRECATED] Количество LLM-вызовов. Используй `litellm_proxy_total_requests_metric_total`. |
| `litellm_llm_api_failed_requests_metric_total` | counter | [DEPRECATED] Неудачные запросы к LLM API. Используй `litellm_proxy_failed_requests_metric_total`. |

### Токены

| Метрика | Тип | Описание |
|---|---|---|
| `litellm_total_tokens_metric_total` | counter | Сумма input + output токенов. Лейблы: `requested_model`, `model`, `hashed_api_key`, `user`, `team`, `end_user` и др. |
| `litellm_input_tokens_metric_total` | counter | Количество input-токенов. Лейблы: аналогично total. |
| `litellm_output_tokens_metric_total` | counter | Количество output-токенов. Лейблы: аналогично total. |
| `litellm_cached_tokens_metric_total` | counter | Токены, отданные из кэша LiteLLM. |

### Затраты

| Метрика | Тип | Описание |
|---|---|---|
| `litellm_spend_metric_total` | counter | Общая сумма расходов в долларах. Лейблы: `model`, `hashed_api_key`, `user`, `team`, `end_user`, `api_key_alias`. |

### Задержки (Latency) -- гистограммы

Все значения в секундах. Для расчёта перцентилей используй бакеты.

| Метрика | Тип | Описание |
|---|---|---|
| `litellm_request_total_latency_metric` | histogram | Полная задержка запроса к LiteLLM (от клиента до ответа). Лейблы: `requested_model`, `model`, `hashed_api_key`, `user`, `team`. |
| `litellm_llm_api_latency_metric` | histogram | Задержка только вызова LLM API (без overhead прокси). Лейблы: аналогично. |
| `litellm_llm_api_time_to_first_token_metric` | histogram | Время до первого токена (TTFT). Лейблы: аналогично. |
| `litellm_overhead_latency_metric` | histogram | Overhead, добавленный LiteLLM (разница между total и LLM API). Лейблы: `api_provider`, `model_group`, `litellm_model_name`, `model_id`. |
| `litellm_deployment_latency_per_output_token` | histogram | Задержка на один output-токен. Лейблы: `api_provider`, `litellm_model_name`, `model_id`. |
| `litellm_request_queue_time_seconds` | histogram | Время в очереди перед обработкой. Лейблы: аналогично total latency. |

### Деплоймент и Failover

| Метрика | Тип | Описание |
|---|---|---|
| `litellm_deployment_state` | gauge | Состояние деплоймента: `0` -- healthy, `1` -- partial outage, `2` -- complete outage. Лейблы: `api_provider`, `api_base`, `litellm_model_name`, `model_id`. |
| `litellm_deployment_success_responses_total` | counter | Успешные ответы от LLM API. Лейблы: `api_provider`, `requested_model`, `client_ip`, `hashed_api_key`, `user_agent`. |
| `litellm_deployment_failure_responses_total` | counter | Неудачные ответы от LLM API. Лейблы: аналогично + `exception_class`, `exception_status`. |
| `litellm_deployment_total_requests_total` | counter | Общее количество запросов к LLM API (success + failure). Лейблы: аналогично success. |
| `litellm_deployment_successful_fallbacks_total` | counter | Успешные фолбэки (primary -> fallback model). |
| `litellm_deployment_failed_fallbacks_total` | counter | Неудачные фолбэки. |
| `litellm_deployment_cooled_down_total` | counter | Количество раз, когда деплоймент был охлаждён (cooled down). Лейблы: `exception_status`. |
| `litellm_deployment_rpm_limit` | gauge | RPM-лимит деплоймента из конфига. |
| `litellm_deployment_tpm_limit` | gauge | TPM-лимит деплоймента из конфига. |

### Кэш

| Метрика | Тип | Описание |
|---|---|---|
| `litellm_cache_hits_metric_total` | counter | Попадания в кэш LiteLLM. |
| `litellm_cache_misses_metric_total` | counter | Промахи кэша. |

### Бюджеты и лимиты

| Метрика | Тип | Описание |
|---|---|---|
| `litellm_remaining_team_budget_metric` | gauge | Оставшийся бюджет команды. Лейблы: `team`, `team_alias`. |
| `litellm_team_max_budget_metric` | gauge | Максимальный бюджет команды. |
| `litellm_team_budget_remaining_hours_metric` | gauge | Часов до сброса бюджета команды. |
| `litellm_remaining_api_key_budget_metric` | gauge | Оставшийся бюджет API-ключа. Лейблы: `hashed_api_key`, `api_key_alias`. |
| `litellm_api_key_max_budget_metric` | gauge | Максимальный бюджет API-ключа. |
| `litellm_api_key_budget_remaining_hours_metric` | gauge | Часов до сброса бюджета API-ключа. |
| `litellm_remaining_user_budget_metric` | gauge | Оставшийся бюджет пользователя. |
| `litellm_user_max_budget_metric` | gauge | Максимальный бюджет пользователя. |
| `litellm_user_budget_remaining_hours_metric` | gauge | Часов до сброса бюджета пользователя. |
| `litellm_remaining_org_budget_metric` | gauge | Оставшийся бюджет организации. |
| `litellm_org_max_budget_metric` | gauge | Максимальный бюджет организации. |
| `litellm_org_budget_remaining_hours_metric` | gauge | Часов до сброса бюджета организации. |
| `litellm_provider_remaining_budget_metric` | gauge | Оставшийся бюджет провайдера. |
| `litellm_remaining_requests_metric` | gauge | Оставшиеся запросы для модели (от провайдера). |
| `litellm_remaining_tokens_metric` | gauge | Оставшиеся токены для модели (от провайдера). |
| `litellm_remaining_api_key_requests_for_model` | gauge | Оставшиеся запросы API-ключа для модели (RPM-лимит). |
| `litellm_remaining_api_key_tokens_for_model` | gauge | Оставшиеся токены API-ключа для модели (TPM-лимит). |

### Guardrails

| Метрика | Тип | Описание |
|---|---|---|
| `litellm_guardrail_requests_total` | counter | Общее количество вызовов guardrails. |
| `litellm_guardrail_errors_total` | counter | Ошибки при выполнении guardrails. |
| `litellm_guardrail_latency_seconds` | histogram | Задержка выполнения guardrails. |

### Callback и Batch

| Метрика | Тип | Описание |
|---|---|---|
| `litellm_callback_logging_failures_metric_total` | counter | Ошибки при отправке логов в callback (S3, Langfuse и др.). Лейблы: `callback_name`. |
| `litellm_check_batch_cost_jobs_polled` | gauge | Количество необработанных batch-заданий. |
| `litellm_check_batch_cost_jobs_processed_total` | counter | Обработанные batch-задачи. |
| `litellm_check_batch_cost_errors_total` | counter | Ошибки в CheckBatchCost. Лейблы: `error_type`. |
| `litellm_check_batch_cost_last_run_timestamp` | gauge | Unix timestamp последнего запуска CheckBatchCost. |
| `litellm_managed_batch_created_total` | counter | Созданные managed batch. |
| `litellm_managed_batch_duration_seconds` | histogram | Длительность завершенных managed batch. |
| `litellm_managed_file_created_total` | counter | Созданные managed file. |
| `litellm_managed_file_deleted_total` | counter | Удалённые managed file. |
| `litellm_managed_file_size_bytes` | gauge | Размер последнего managed batch-файла. |

### Системные (LiteLLM)

| Метрика | Тип | Описание |
|---|---|---|
| `litellm_in_flight_requests` | gauge | Количество HTTP-запросов в процессе обработки на воркере. |
| `litellm_total_users` | gauge | Общее количество пользователей в LiteLLM. |
| `litellm_teams_count` | gauge | Общее количество команд в LiteLLM. |

### Процесс (prometheus_client)

| Метрика | Тип | Описание |
|---|---|---|
| `process_virtual_memory_bytes` | gauge | Виртуальная память процесса (байт). |
| `process_resident_memory_bytes` | gauge | Физическая память процесса (байт). |
| `process_cpu_seconds_total` | counter | Накопленное время CPU (сек). |
| `process_start_time_seconds` | gauge | Время старта процесса (Unix timestamp). |
| `process_open_fds` | gauge | Открытые файловые дескрипторы. |
| `process_max_fds` | gauge | Максимум файловых дескрипторов. |

### Python (prometheus_client)

| Метрика | Тип | Описание |
|---|---|---|
| `python_gc_collections_total` | counter | Количество сборок GC. Лейблы: `generation` (0/1/2). |
| `python_gc_objects_collected_total` | counter | Собранное количество объектов. Лейблы: `generation`. |
| `python_gc_objects_uncollectable_total` | counter | Невозможно собрать объекты. Лейблы: `generation`. |
| `python_info` | gauge | Информация о Python. Лейблы: `implementation`, `major`, `minor`, `patchlevel`, `version`. |

### Расчёт перцентилей из гистограмм

Для histogram-метрик перцентили вычисляются из кумулятивных бакетов:

```python
# Пример: p50 из litellm_request_total_latency_metric
# Бакеты: [(0.005, 0), (0.01, 0), ..., (5.0, 22), (10.0, 163), ..., (+Inf, 715)]
# total = 715, target = 0.5 * 715 = 357.5
# Первый бакет >= 357.5 -> le=30.0 (369) -> p50 = 30.0s
```

### Расчёт rate для counter-метрик

Counter-метрики только растут. Для получения скорости (req/s, tok/s) нужно вычислять delta между опросами:

```python
rate = (current_value - previous_value) / (current_time - previous_time)
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
