from celery import Celery

from nyuydine.config import get_platform_settings

settings = get_platform_settings()

celery_app = Celery(
    "nyuydine",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_always_eager=settings.celery_task_always_eager,
    task_track_started=True,
)

import nyuydine.workers.tasks  # noqa: E402, F401
