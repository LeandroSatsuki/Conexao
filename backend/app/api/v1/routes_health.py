from __future__ import annotations

from datetime import datetime, timezone

import redis
from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import get_settings
from app.database.session import get_engine

router = APIRouter(tags=["health"])


@router.get("/health")
def healthcheck() -> dict[str, object]:
    settings = get_settings()
    database_status = "ok"
    redis_status = "ok"

    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        database_status = "error"

    try:
        client = redis.Redis.from_url(settings.redis_url)
        client.ping()
    except Exception:
        redis_status = "error"

    overall = "ok" if database_status == "ok" and redis_status == "ok" else "degraded"
    return {
        "status": overall,
        "database": database_status,
        "redis": redis_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
