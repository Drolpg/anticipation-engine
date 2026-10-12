"""Schemas Pydantic para validação e serialização de títulos."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from anticipation_engine.core.cnpj import validar_cnpj
from anticipation_engine.models import StatusTitulo


class TituloCreate(BaseModel):
    """Payload de entrada para criação de um título financeiro."""

    model_config = ConfigDict(extra="forbid")

    cnpj_sacado: str
    valor_titulo: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    data_vencimento: date

    @field_validator("cnpj_sacado")
    @classmethod
    def validar_e_normalizar_cnpj(cls, v: str) -> str:
        return validar_cnpj(v)

    @field_validator("data_vencimento")
    @classmethod
    def validar_vencimento_futuro(cls, v: date) -> date:
        if v <= date.today():
            raise ValueError("Data de vencimento deve ser estritamente no futuro.")
        return v


class TituloCreated(BaseModel):
    """Resposta assíncrona 202 Accepted confirmando recebimento do título."""

    id: uuid.UUID
    status: StatusTitulo


class TituloRead(BaseModel):
    """Representação completa de leitura do título com status atualizado."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    cnpj_sacado: str
    valor_titulo: Decimal
    data_vencimento: date
    status: StatusTitulo
    criado_em: datetime
    atualizado_em: datetime
