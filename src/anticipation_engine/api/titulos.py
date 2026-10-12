"""Endpoints de gerenciamento e consulta de títulos de crédito."""

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from anticipation_engine.core.errors import FilaIndisponivel, TituloNaoEncontrado
from anticipation_engine.db.session import get_db
from anticipation_engine.models import StatusTitulo, Titulo
from anticipation_engine.schemas.titulo import TituloCreate, TituloCreated, TituloRead
from anticipation_engine.services import fila

logger = logging.getLogger("anticipation_engine")

router = APIRouter(prefix="/titulos", tags=["titulos"])

DbSession = Annotated[Session, Depends(get_db)]


@router.post("", response_model=TituloCreated, status_code=status.HTTP_202_ACCEPTED)
def criar_titulo(
    payload: TituloCreate,
    response: Response,
    db: DbSession,
) -> TituloCreated:
    """Cria um novo título e submete para análise de crédito assíncrona."""
    titulo = Titulo(
        cnpj_sacado=payload.cnpj_sacado,
        valor_titulo=payload.valor_titulo,
        data_vencimento=payload.data_vencimento,
        status=StatusTitulo.PENDENTE,
    )
    db.add(titulo)
    db.commit()
    db.refresh(titulo)

    logger.info("titulo_recebido", extra={"titulo_id": str(titulo.id)})

    try:
        fila.enfileirar_analise(titulo.id)
    except Exception:
        logger.error("falha_ao_enfileirar", exc_info=True, extra={"titulo_id": str(titulo.id)})
        raise FilaIndisponivel() from None

    response.headers["Location"] = f"/titulos/{titulo.id}"
    return TituloCreated(id=titulo.id, status=titulo.status)


@router.get("/{id}", response_model=TituloRead)
def obter_titulo(
    id: UUID,
    db: DbSession,
) -> TituloRead:
    """Consulta os dados e status atualizado de um título financeiro."""
    titulo = db.get(Titulo, id)
    if titulo is None:
        raise TituloNaoEncontrado()
    return TituloRead.model_validate(titulo)
