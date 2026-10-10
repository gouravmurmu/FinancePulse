import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.db.session import _session_factory, get_engine
from app.main import create_app


@pytest.fixture
def make_client(monkeypatch: pytest.MonkeyPatch):
    def _make(**env: str) -> TestClient:
        monkeypatch.delenv("DATABASE_URL", raising=False)
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        get_settings.cache_clear()
        get_engine.cache_clear()
        _session_factory.cache_clear()
        return TestClient(create_app(Settings()), raise_server_exceptions=False)

    yield _make
    get_settings.cache_clear()
    get_engine.cache_clear()
    _session_factory.cache_clear()
