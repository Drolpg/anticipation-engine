"""Tasks assíncronas do Celery."""

from sqlalchemy.exc import OperationalError

from anticipation_engine.db.session import SessionLocal
from anticipation_engine.services.analise_credito import processar_titulo
from anticipation_engine.worker.celery_app import celery_app


@celery_app.task(
    name="anticipation_engine.analisar_credito",
    acks_late=True,
    max_retries=3,
    retry_backoff=True,
    autoretry_for=(OperationalError,),
)
def analisar_credito_task(titulo_id: str) -> None:
    """Executa a análise de crédito de forma assíncrona com sessão dedicada."""
    with SessionLocal() as db:
        processar_titulo(db, titulo_id)
