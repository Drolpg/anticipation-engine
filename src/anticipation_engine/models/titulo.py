"""Modelo de dados para títulos financeiros e seus status."""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import Date, DateTime, Numeric, String, Uuid, func
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column

from anticipation_engine.db.base import Base


class StatusTitulo(StrEnum):
    """Estados possíveis de um título no fluxo de antecipação."""

    PENDENTE = "PENDENTE"
    APROVADO = "APROVADO"
    REJEITADO = "REJEITADO"


class Titulo(Base):
    """Representação de um título financeiro (duplicata / NF) submetido para antecipação."""

    __tablename__ = "titulos"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    cnpj_sacado: Mapped[str] = mapped_column(
        String(14),
        index=True,
        nullable=False,
    )
    valor_titulo: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False,
    )
    data_vencimento: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    status: Mapped[StatusTitulo] = mapped_column(
        SQLEnum(StatusTitulo, native_enum=False, length=20),
        default=StatusTitulo.PENDENTE,
        index=True,
        nullable=False,
    )
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        nullable=False,
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        server_default=func.now(),
        nullable=False,
    )
