"""Endpoints de gerenciamento e consulta de títulos de crédito."""

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from anticipation_engine.core.errors import FilaIndisponivel, TituloNaoEncontrado
from anticipation_engine.db.session import get_db
from anticipation_engine.models import StatusTitulo, Titulo
from anticipation_engine.schemas.erro import resposta_de_erro
from anticipation_engine.schemas.titulo import TituloCreate, TituloCreated, TituloRead
from anticipation_engine.services import fila

logger = logging.getLogger("anticipation_engine")

router = APIRouter(prefix="/titulos", tags=["titulos"])

DbSession = Annotated[Session, Depends(get_db)]


ERRO_500 = resposta_de_erro(
    "Erro inesperado. O `request_id` permite localizar o stack trace nos logs.",
    "INTERNAL_ERROR",
    "Erro interno do servidor.",
    request_id="3f0c1c52-8c1e-4a43-9b8d-2f1b6f0e9a11",
)


@router.post(
    "",
    response_model=TituloCreated,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Enviar título para antecipação",
    responses={
        202: {"description": "Título recebido e salvo como `PENDENTE`. A análise segue em background."},
        422: resposta_de_erro(
            "Payload inválido.",
            "VALIDATION_ERROR",
            "Payload inválido.",
            details=[{"field": "cnpj_sacado", "message": "CNPJ com dígitos verificadores inválidos."}],
        ),
        500: ERRO_500,
        503: resposta_de_erro(
            "Título salvo, mas a fila de análise está fora do ar. Ele permanece `PENDENTE`.",
            "FILA_INDISPONIVEL",
            "Serviço de mensageria temporariamente indisponível.",
        ),
    },
)
def criar_titulo(
    payload: TituloCreate,
    response: Response,
    db: DbSession,
) -> TituloCreated:
    """Valida o CNPJ, o valor e o vencimento, salva o título como `PENDENTE` e o enfileira para análise.

    A resposta é imediata (`202`) e traz o cabeçalho `Location`; a decisão (`APROVADO` ou `REJEITADO`)
    sai poucos segundos depois e é consultada em `GET /titulos/{id}`.
    """
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


@router.get(
    "/{id}",
    response_model=TituloRead,
    summary="Consultar título",
    responses={
        404: resposta_de_erro("Título não existe.", "TITULO_NAO_ENCONTRADO", "Título não encontrado."),
        422: resposta_de_erro(
            "`id` não é um UUID válido.",
            "VALIDATION_ERROR",
            "Payload inválido.",
            details=[{"field": "id", "message": "Input should be a valid UUID"}],
        ),
        500: ERRO_500,
    },
)
def obter_titulo(
    id: UUID,
    db: DbSession,
) -> TituloRead:
    """Retorna os dados do título e o status atual: `PENDENTE` enquanto em análise, depois `APROVADO` ou `REJEITADO`."""
    titulo = db.get(Titulo, id)
    if titulo is None:
        raise TituloNaoEncontrado()
    return TituloRead.model_validate(titulo)
