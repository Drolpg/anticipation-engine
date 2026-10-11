"""RF-02 — validação estrutural via Pydantic (sem banco, sem HTTP)."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from anticipation_engine.schemas.titulo import TituloCreate

HOJE = date.today()


def _dados(**overrides):
    base = {
        "cnpj_sacado": "11.222.333/0001-81",
        "valor_titulo": "1500.50",
        "data_vencimento": HOJE + timedelta(days=30),
    }
    base.update(overrides)
    return base


def _campos_com_erro(exc: ValidationError) -> set[str]:
    return {str(e["loc"][0]) for e in exc.value.errors()}


def test_payload_valido_normaliza_cnpj_e_usa_decimal():
    titulo = TituloCreate(**_dados())
    assert titulo.cnpj_sacado == "11222333000181"
    assert titulo.valor_titulo == Decimal("1500.50")
    assert isinstance(titulo.valor_titulo, Decimal)


def test_vencimento_amanha_e_valido():
    TituloCreate(**_dados(data_vencimento=HOJE + timedelta(days=1)))


@pytest.mark.parametrize("dias", [0, -1, -365])
def test_vencimento_hoje_ou_passado_e_invalido(dias):
    with pytest.raises(ValidationError) as exc:
        TituloCreate(**_dados(data_vencimento=HOJE + timedelta(days=dias)))
    assert _campos_com_erro(exc) == {"data_vencimento"}


@pytest.mark.parametrize("valor", ["0", "0.00", "-10", "abc", "10.999", "10000000000000000.00"])
def test_valor_invalido(valor):
    # 10.999 => 3 casas decimais; 10000000000000000.00 => estoura Numeric(18,2)
    with pytest.raises(ValidationError) as exc:
        TituloCreate(**_dados(valor_titulo=valor))
    assert _campos_com_erro(exc) == {"valor_titulo"}


def test_cnpj_invalido():
    with pytest.raises(ValidationError) as exc:
        TituloCreate(**_dados(cnpj_sacado="11.222.333/0001-82"))
    assert _campos_com_erro(exc) == {"cnpj_sacado"}


@pytest.mark.parametrize("campo", ["cnpj_sacado", "valor_titulo", "data_vencimento"])
def test_campos_obrigatorios(campo):
    dados = _dados()
    dados.pop(campo)
    with pytest.raises(ValidationError) as exc:
        TituloCreate(**dados)
    assert _campos_com_erro(exc) == {campo}


def test_cliente_nao_pode_enviar_status():
    """Proteção contra mass assignment: status é decidido pelo sistema."""
    with pytest.raises(ValidationError) as exc:
        TituloCreate(**_dados(status="APROVADO"))
    assert "status" in _campos_com_erro(exc)
