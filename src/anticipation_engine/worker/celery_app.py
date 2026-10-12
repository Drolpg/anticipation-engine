from typing import Any

from celery import Celery
from celery.signals import setup_logging

from anticipation_engine.core.config import get_settings
from anticipation_engine.core.logging import configure_logging

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


@setup_logging.connect
def configurar_logs_do_worker(**kwargs: Any) -> None:
    """Configura logs estruturados em JSON quando o worker do Celery inicializa."""
    configure_logging(settings.log_level)
