"""Envelope de erro unificado, usado na documentação OpenAPI (o formato real é montado em `main.py`)."""

from typing import Any

from pydantic import BaseModel, Field


class ErroDetalhe(BaseModel):
    """Detalhe de um erro de validação."""

    field: str = Field(description="Campo do payload com problema.", examples=["cnpj_sacado"])
    message: str = Field(description="O que está errado.", examples=["CNPJ com dígitos verificadores inválidos."])


class ErroCorpo(BaseModel):
    """Conteúdo do envelope de erro."""

    code: str = Field(
        description="Código estável, próprio para tratamento por código cliente.", examples=["VALIDATION_ERROR"]
    )
    message: str = Field(description="Mensagem legível, sem detalhes internos.", examples=["Payload inválido."])
    details: list[ErroDetalhe] | None = Field(default=None, description="Presente em erros de validação (422).")
    request_id: str | None = Field(
        default=None,
        description="Presente em erros 500. É o valor do cabeçalho `X-Request-ID`, para localizar o erro nos logs.",
    )


class ErrorResponse(BaseModel):
    """Toda resposta de erro da API tem este formato."""

    error: ErroCorpo


def resposta_de_erro(descricao: str, codigo: str, mensagem: str, **extra: Any) -> dict[str, Any]:
    """Monta uma entrada do parâmetro `responses` do FastAPI com exemplo realista."""
    exemplo = {"error": {"code": codigo, "message": mensagem, **extra}}
    return {
        "model": ErrorResponse,
        "description": descricao,
        "content": {"application/json": {"example": exemplo}},
    }
