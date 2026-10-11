"""RF-02 / RN-01 — validação de CNPJ (módulo puro, sem I/O)."""

import pytest

from anticipation_engine.core.cnpj import validar_cnpj


@pytest.mark.parametrize(
    "entrada",
    [
        "11.222.333/0001-81",
        "11222333000181",
        "  11.222.333/0001-81  ",
        "11.444.777/0001-61",
        "00.000.000/0001-91",
    ],
)
def test_cnpj_valido_retorna_somente_digitos(entrada):
    resultado = validar_cnpj(entrada)
    assert len(resultado) == 14
    assert resultado.isdigit()


def test_cnpj_formatado_e_sem_formatacao_normalizam_igual():
    assert validar_cnpj("11.222.333/0001-81") == validar_cnpj("11222333000181") == "11222333000181"


@pytest.mark.parametrize(
    "entrada",
    [
        "11.222.333/0001-82",  # dígito verificador errado
        "11222333000180",  # dígito verificador errado
        "11111111111111",  # todos dígitos iguais (passaria no cálculo, mas é inválido)
        "00000000000000",
        "123",  # curto demais
        "112223330001811",  # longo demais
        "1122233300018X",  # caractere inválido (MVP aceita só numérico)
        "",
        "   ",
    ],
)
def test_cnpj_invalido_levanta_value_error(entrada):
    with pytest.raises(ValueError):
        validar_cnpj(entrada)
