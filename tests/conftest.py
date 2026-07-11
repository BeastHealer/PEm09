"""
Pytest configuration and shared fixtures.
"""

import pytest
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture(scope="session")
def project_root_path():
    """Provide project root path."""
    return project_root


@pytest.fixture
def temp_dir(tmp_path):
    """Provide temporary directory."""
    return tmp_path


@pytest.fixture(autouse=True)
def setup_env(monkeypatch):
    """Setup test environment variables."""
    monkeypatch.setenv("PROXYAPI_KEY", "test_proxyapi_key_12345")
    monkeypatch.setenv("OPENAI_API_KEY", "test_proxyapi_key_12345")
    monkeypatch.setenv("OPENAI_API_BASE", "https://api.proxyapi.ru/openai/v1")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test_telegram_token")
    monkeypatch.setenv("LOG_LEVEL", "ERROR")

