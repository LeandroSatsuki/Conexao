from __future__ import annotations

from app.workers.celery_app import create_celery_app

celery_app = create_celery_app()


@celery_app.task(name="preferenza_connector.health")
def health_task() -> dict[str, str]:
    return {"status": "ok"}
