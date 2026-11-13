import shutil
import tempfile

import pytest

from app import config


@pytest.fixture(autouse=True)
def isolated_cache(monkeypatch):
    """Point the TTL cache at a throwaway dir so tests never share state
    or pollute the real cache."""
    tmp = tempfile.mkdtemp(prefix="mscout-test-cache-")
    monkeypatch.setattr(config.settings, "cache_dir", type(config.settings.cache_dir)(tmp))
    yield
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app
    with TestClient(app) as c:
        yield c
