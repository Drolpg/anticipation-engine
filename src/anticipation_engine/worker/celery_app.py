"""Instância e configuração do Celery."""

from celery import Celery

from anticipation_engine.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "anticipation_engine",
    broker=settings.redis_url,
    include=["anticipation_engine.worker.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
)
