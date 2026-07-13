"""E2E-тесты для CLI.

Риски: Неправильная инициализация приложения.
"""

import subprocess
import sys


class TestCLI:
    """Тесты CLI аргументов и запуска."""

    def test_help_flag(self):
        """--help выводит помощь и завершается."""
        result = subprocess.run(
            [sys.executable, "-m", "litellm_metrics.cli", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "LiteLLM Metrics" in result.stdout or "usage" in result.stdout.lower()

    def test_invalid_url_exits_with_error(self):
        """Startup Failure: недоступный сервер → sys.exit(1)."""
        result = subprocess.run(
            [sys.executable, "-m", "litellm_metrics.cli", "--url", "http://127.0.0.1:19999/metrics", "--interval", "1"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode != 0
        assert "ERROR" in result.stdout or "error" in result.stdout.lower() or "Cannot connect" in result.stdout
