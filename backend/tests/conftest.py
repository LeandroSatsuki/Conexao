from __future__ import annotations

import os
import sys
from pathlib import Path
from tempfile import gettempdir
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("APP_NAME", "Preferenza Connector")
TEST_DB_PATH = Path(gettempdir()) / f"preferenza-test-{uuid4().hex}.db"
os.environ.setdefault("DATABASE_URL", f"sqlite+pysqlite:///{TEST_DB_PATH.as_posix()}")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("CELERY_BROKER_URL", "memory://")
os.environ.setdefault("CELERY_RESULT_BACKEND", "cache+memory://")
os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "true")
os.environ.setdefault("CELERY_TASK_EAGER_PROPAGATES", "false")
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
from app.database.session import get_engine, get_session_factory  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture()
def engine():
    return get_engine()


@pytest.fixture(autouse=True)
def reset_database():
    TEST_DB_PATH.unlink(missing_ok=True)
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    yield
    engine.dispose()
    TEST_DB_PATH.unlink(missing_ok=True)


@pytest.fixture()
def client():
    return TestClient(app)
