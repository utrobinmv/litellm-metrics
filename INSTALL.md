# INSTALL.md -- Установка litellm-metrics с нуля

## Шаг 1: Клонирование репозитория

```bash
git clone https://github.com/utrobinmv/litellm-metrics.git
cd litellm-metrics
```

## Шаг 2: Python

Требуется Python 3.11+. Если используется pyenv:

```bash
pyenv install 3.11.15
pyenv local 3.11.15
```

## Шаг 3: Создание виртуального окружения

```bash
python3 -m venv ~/workspace/venvs/litellm-metrics/default
```

## Шаг 4: Активация и установка зависимостей

```bash
source .venv
pip install --upgrade pip
pip install -e ".[dev]"
```

## Шаг 5: Настройка .env

```bash
cp .env.example .env
```

Отредактируй `.env` под свой сервер:

```ini
LITELLM_METRICS_URL=http://192.168.45.30:31003/metrics/
LITELLM_BASE_URL=http://192.168.45.30:31003
LITELLM_API_KEY=
REFRESH_INTERVAL=2
```

## Шаг 6: Проверка работы

```bash
# Проверка CLI
litellm-metrics --help

# Проверка подключения к серверу
litellm-metrics --url http://192.168.45.30:31003/metrics/ --interval 1
```

## Шаг 7: Запуск тестов

```bash
python -m pytest tests/ -v --cov=litellm_metrics --cov-report=term-missing
```

## Линтинг и типизация

```bash
ruff check src/ tests/
mypy src/litellm_metrics/
```

## Повторное развёртывание

Если нужно развернуть проект заново:

```bash
cd ~/workspace/projects/litellm-metrics
rm -rf ~/workspace/venvs/litellm-metrics/default
python3 -m venv ~/workspace/venvs/litellm-metrics/default
source .venv
pip install --upgrade pip
pip install -e ".[dev]"
python -m pytest tests/ -v
```
