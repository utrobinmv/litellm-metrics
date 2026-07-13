"""litellm-metrics — Конфигурация подключения к LiteLLM proxy серверу."""

import os
from pathlib import Path

from dotenv import load_dotenv


def load_config() -> dict:
    """Загружает конфигурацию из .env и переменных окружения."""
    # Ищем .env рядом с файлом конфигурации (в корне проекта)
    env_path = Path(__file__).parent.parent.parent / ".env"
    load_dotenv(env_path)

    return {
        "metrics_url": os.getenv("LITELLM_METRICS_URL", "http://localhost:4000/metrics/"),
        "base_url": os.getenv("LITELLM_BASE_URL", "http://localhost:4000"),
        "api_key": os.getenv("LITELLM_API_KEY", ""),
        "refresh_interval": int(os.getenv("REFRESH_INTERVAL", "2")),
    }
