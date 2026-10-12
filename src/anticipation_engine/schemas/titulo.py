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

    cnpj_sacado: str = Field(
        description="CNPJ do sacado (devedor do título), com ou sem máscara. Os dígitos verificadores são validados.",
        examples=["11.222.333/0001-81"],
    )
    valor_titulo: Decimal = Field(
        gt=0,
        max_digits=18,
        decimal_places=2,
        description="Valor de face em reais, maior que zero e com no máximo 2 casas decimais. Envie como string.",
        examples=["1500.50"],
    )
    data_vencimento: date = Field(
        description="Data de vencimento (AAAA-MM-DD). Deve ser estritamente posterior a hoje.",
        examples=["2030-12-31"],
    )

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

    id: uuid.UUID = Field(description="Identificador do título. Use em `GET /titulos/{id}` para acompanhar a análise.")
    status: StatusTitulo = Field(
        description="Sempre `PENDENTE` neste momento: a análise de crédito roda em background."
    )


class TituloRead(BaseModel):
    """Representação completa de leitura do título com status atualizado."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(description="Identificador do título.")
    cnpj_sacado: str = Field(description="CNPJ do sacado, somente dígitos (14).", examples=["11222333000181"])
    valor_titulo: Decimal = Field(description="Valor de face em reais, como string com 2 casas.", examples=["1500.50"])
    data_vencimento: date = Field(description="Data de vencimento (AAAA-MM-DD).")
    status: StatusTitulo = Field(
        description="`PENDENTE` (em análise), `APROVADO` ou `REJEITADO` "
        "(valor acima de R$ 1.000.000,00 ou prazo acima de 365 dias)."
    )
    criado_em: datetime = Field(description="Momento em que o título foi recebido (UTC).")
    atualizado_em: datetime = Field(description="Última mudança de status (UTC).")
