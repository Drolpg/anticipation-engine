"""Serviço de análise de crédito e processamento de títulos."""

import logging
import time
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import update
from sqlalchemy.orm import Session

from anticipation_engine.core.config import get_settings
from anticipation_engine.models import StatusTitulo, Titulo

logger = logging.getLogger("anticipation_engine")

LIMITE_VALOR: Decimal = Decimal("1000000.00")
PRAZO_MAXIMO_DIAS: int = 365


def decidir_credito(valor: Decimal, vencimento: date, hoje: date | None = None) -> StatusTitulo:
    """Função pura e determinística para decidir a aprovação ou rejeição de crédito (RN-04).

    Regras:
    - REJEITADO se valor > 1.000.000,00 ou prazo (vencimento - hoje) > 365 dias.
    - APROVADO nos demais casos (fronteiras de exatamente 1.000.000,00 e 365 dias aprovam).
    """
    if hoje is None:
        hoje = date.today()

    prazo_dias = (vencimento - hoje).days
    if valor > LIMITE_VALOR or prazo_dias > PRAZO_MAXIMO_DIAS:
        return StatusTitulo.REJEITADO

    return StatusTitulo.APROVADO


def analisar(valor: Decimal, vencimento: date) -> StatusTitulo:
    """Simula o tempo de análise de crédito em background e retorna a decisão."""
    settings = get_settings()
    time.sleep(settings.analise_delay_seconds)
    return decidir_credito(valor, vencimento)


def processar_titulo(db: Session, titulo_id: uuid.UUID | str) -> StatusTitulo | None:
    """Executa o fluxo idempotente de processamento do título em background (RN-05).

    Passos:
    1. Busca o título pelo ID. Se não existir, loga erro e retorna None.
    2. Se não estiver PENDENTE, retorna None (idempotência).
    3. Encerra a transação corrente (rollback) antes de iniciar a análise de crédito
       para liberar conexões do pool e evitar locks durante a espera.
    4. Executa a análise de crédito simulada.
    5. Atualiza o status de forma atômica (compare-and-set) apenas se ainda estiver PENDENTE.
    6. Se o título já tiver sido alterado concorrentemente por outro worker (rowcount == 0), retorna None.
    7. Loga analise_concluida estruturado e retorna o novo status.
    """
    if isinstance(titulo_id, str):
        titulo_id = uuid.UUID(titulo_id)

    titulo = db.get(Titulo, titulo_id)
    if titulo is None:
        logger.error("titulo_nao_encontrado", extra={"titulo_id": str(titulo_id)})
        return None

    if titulo.status != StatusTitulo.PENDENTE:
        return None

    valor = titulo.valor_titulo
    vencimento = titulo.data_vencimento

    # Libera conexão/transação do banco durante o sleep da análise
    db.rollback()

    novo_status = analisar(valor, vencimento)

    # Compare-and-set: apenas atualiza se continuar PENDENTE
    stmt = (
        update(Titulo).where(Titulo.id == titulo_id, Titulo.status == StatusTitulo.PENDENTE).values(status=novo_status)
    )
    result = db.execute(stmt)
    db.commit()

    if result.rowcount == 0:
        return None

    logger.info(
        "analise_concluida",
        extra={"titulo_id": str(titulo_id), "status": str(novo_status)},
    )
    return novo_status
