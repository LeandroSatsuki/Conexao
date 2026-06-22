from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("APP_NAME", "Preferenza Connector")
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///./test.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("API_V1_PREFIX", "/api/v1")
os.environ.setdefault("CORS_ORIGINS", "*")
os.environ.setdefault("DEFAULT_TENANT_ID", "preferenza")
os.environ.setdefault("SANKHYA_TIMEOUT_SECONDS", "5")
os.environ.setdefault("FERNET_KEY", Fernet.generate_key().decode("utf-8"))

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

existing_app_module = sys.modules.get("app")
if existing_app_module is not None:
    module_file = getattr(existing_app_module, "__file__", "") or ""
    if str(BACKEND_ROOT) not in module_file:
        for module_name in list(sys.modules):
            if module_name == "app" or module_name.startswith("app."):
                del sys.modules[module_name]

from app.database.base import Base  # noqa: E402
from app.database.session import get_engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def engine():
    return get_engine()


@pytest.fixture(autouse=True)
def reset_database(engine):
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture()
def client():
    return TestClient(app)
