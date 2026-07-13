"""Unit-тесты для config.py.

Риски: Неправильный приоритет переменных окружения.
"""

import os
from pathlib import Path
from unittest import mock

from litellm_metrics.config import load_config


class TestLoadConfig:
    """Тесты load_config()."""

    def test_defaults_without_env(self, tmp_path):
        """Значения по умолчанию (без .env)."""
        fake_env = tmp_path / ".env"
        with (
            mock.patch.object(Path, "__truediv__", return_value=fake_env),
            mock.patch("litellm_metrics.config.load_dotenv"),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            for key in ["LITELLM_METRICS_URL", "LITELLM_API_KEY", "REFRESH_INTERVAL"]:
                os.environ.pop(key, None)
            result = load_config()
            assert result["metrics_url"] == "http://localhost:4000/metrics/"
            assert result["api_key"] == ""
            assert result["refresh_interval"] == 2

    def test_env_file_override(self, tmp_path):
        """Override via .env."""
        env_file = tmp_path / ".env"
        env_file.write_text("LITELLM_METRICS_URL=http://custom:9000/metrics\n")
        with (
            mock.patch.object(Path, "__truediv__", return_value=env_file),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            for key in ["LITELLM_METRICS_URL", "LITELLM_API_KEY", "REFRESH_INTERVAL"]:
                os.environ.pop(key, None)
            result = load_config()
            assert result["metrics_url"] == "http://custom:9000/metrics"

    def test_env_var_priority_over_file(self, tmp_path):
        """Env Var > .env file > Default."""
        env_file = tmp_path / ".env"
        env_file.write_text("LITELLM_METRICS_URL=http://file:8000/metrics\n")
        with (
            mock.patch.object(Path, "__truediv__", return_value=env_file),
            mock.patch.dict(os.environ, {"LITELLM_METRICS_URL": "http://env:9000/metrics"}),
        ):
            result = load_config()
            assert result["metrics_url"] == "http://env:9000/metrics"

    def test_refresh_interval_is_int(self, tmp_path):
        """REFRESH_INTERVAL парсится как int."""
        env_file = tmp_path / ".env"
        env_file.write_text("REFRESH_INTERVAL=5\n")
        with (
            mock.patch.object(Path, "__truediv__", return_value=env_file),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            for key in ["REFRESH_INTERVAL"]:
                os.environ.pop(key, None)
            result = load_config()
            assert isinstance(result["refresh_interval"], int)
            assert result["refresh_interval"] == 5

    def test_missing_env_file_uses_defaults(self, tmp_path):
        """Отсутствующий .env -> дефолты (не падает)."""
        nonexistent = tmp_path / "nonexistent.env"
        with (
            mock.patch.object(Path, "__truediv__", return_value=nonexistent),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            for key in ["LITELLM_METRICS_URL", "LITELLM_API_KEY", "REFRESH_INTERVAL"]:
                os.environ.pop(key, None)
            result = load_config()
            assert result["metrics_url"] == "http://localhost:4000/metrics/"
