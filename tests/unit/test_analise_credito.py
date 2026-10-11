"""RN-04 — regra de decisão de crédito (função pura, determinística)."""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from anticipation_engine.models import StatusTitulo
from anticipation_engine.services.analise_credito import (
    LIMITE_VALOR,
    PRAZO_MAXIMO_DIAS,
    decidir_credito,
)

HOJE = date(2026, 1, 15)


def test_constantes_da_regra():
    assert LIMITE_VALOR == Decimal("1000000.00")
    assert PRAZO_MAXIMO_DIAS == 365


def test_titulo_dentro_dos_limites_e_aprovado():
    assert decidir_credito(Decimal("1500.50"), HOJE + timedelta(days=30), hoje=HOJE) == StatusTitulo.APROVADO


@pytest.mark.parametrize(
    "valor, esperado",
    [
        ("1000000.00", StatusTitulo.APROVADO),  # fronteira: igual ao limite aprova
        ("1000000.01", StatusTitulo.REJEITADO),  # 1 centavo acima rejeita
    ],
)
def test_fronteira_de_valor(valor, esperado):
    assert decidir_credito(Decimal(valor), HOJE + timedelta(days=30), hoje=HOJE) == esperado


@pytest.mark.parametrize(
    "dias, esperado",
    [
        (365, StatusTitulo.APROVADO),  # fronteira: igual ao prazo máximo aprova
        (366, StatusTitulo.REJEITADO),
    ],
)
def test_fronteira_de_prazo(dias, esperado):
    assert decidir_credito(Decimal("100.00"), HOJE + timedelta(days=dias), hoje=HOJE) == esperado


def test_nunca_retorna_pendente():
    for valor in ("0.01", "999999.99", "5000000.00"):
        assert decidir_credito(Decimal(valor), HOJE + timedelta(days=10), hoje=HOJE) != StatusTitulo.PENDENTE
