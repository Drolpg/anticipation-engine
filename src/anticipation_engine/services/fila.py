"""Módulo de integração com a fila de mensageria."""

from uuid import UUID


def enfileirar_analise(titulo_id: UUID) -> None:
    """Enfileira a análise de crédito de um título para processamento assíncrono."""
    from anticipation_engine.worker.tasks import analisar_credito_task

    analisar_credito_task.delay(str(titulo_id))
