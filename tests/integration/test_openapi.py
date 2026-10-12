"""RNF-09 — a API é autodocumentada (Swagger UI em /docs, ReDoc em /redoc, contrato em /openapi.json)."""

import pytest

from anticipation_engine.core.cnpj import validar_cnpj
from anticipation_engine.schemas.titulo import TituloCreate


@pytest.fixture
def openapi(client):
    r = client.get("/openapi.json")
    assert r.status_code == 200
    return r.json()


@pytest.mark.parametrize("caminho", ["/docs", "/redoc"])
def test_interfaces_de_documentacao_estao_disponiveis(client, caminho):
    r = client.get(caminho)

    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_contrato_descreve_a_api(openapi):
    info = openapi["info"]

    assert info["title"] == "Motor de Antecipação de Recebíveis"
    assert len(info["description"]) > 100  # visão geral do fluxo assíncrono, não só o título
    assert {t["name"] for t in openapi["tags"]} >= {"titulos", "health"}
    assert all(t.get("description") for t in openapi["tags"])


def test_todas_as_operacoes_tem_resumo_e_descricao(openapi):
    for caminho, metodos in openapi["paths"].items():
        for metodo, operacao in metodos.items():
            assert operacao.get("summary"), f"{metodo.upper()} {caminho} sem summary"
            assert operacao.get("description"), f"{metodo.upper()} {caminho} sem description"


@pytest.mark.parametrize(
    "caminho, metodo, status_esperados",
    [
        ("/titulos", "post", {"202", "422", "500", "503"}),
        ("/titulos/{id}", "get", {"200", "404", "422", "500"}),
    ],
)
def test_respostas_de_erro_estao_documentadas_com_o_envelope_real(openapi, caminho, metodo, status_esperados):
    respostas = openapi["paths"][caminho][metodo]["responses"]

    assert status_esperados <= set(respostas)
    for status in status_esperados - {"200", "202"}:
        schema = respostas[status]["content"]["application/json"]["schema"]
        assert schema["$ref"].endswith("/ErrorResponse"), f"{status} deveria usar o envelope {{error: ...}}"
        assert respostas[status]["description"]


def test_nao_expoe_o_erro_padrao_do_fastapi_que_a_api_nao_retorna(openapi):
    """A API responde 422 no envelope unificado; o `HTTPValidationError` do FastAPI seria uma documentação falsa."""
    schemas = openapi["components"]["schemas"]

    assert "HTTPValidationError" not in schemas
    assert "ErrorResponse" in schemas


def test_cada_campo_do_payload_tem_descricao_e_exemplo(openapi):
    propriedades = openapi["components"]["schemas"]["TituloCreate"]["properties"]

    assert set(propriedades) == {"cnpj_sacado", "valor_titulo", "data_vencimento"}
    for nome, prop in propriedades.items():
        assert prop.get("description"), f"{nome} sem description"
        assert prop.get("examples"), f"{nome} sem exemplo"


def test_cada_campo_da_resposta_tem_descricao(openapi):
    for schema in ("TituloCreated", "TituloRead"):
        for nome, prop in openapi["components"]["schemas"][schema]["properties"].items():
            assert prop.get("description"), f"{schema}.{nome} sem description"


def test_exemplos_do_swagger_sao_validos_para_a_propria_api(openapi):
    """Exemplo no Swagger que a API rejeita é pior do que não ter exemplo."""
    propriedades = openapi["components"]["schemas"]["TituloCreate"]["properties"]

    assert validar_cnpj(propriedades["cnpj_sacado"]["examples"][0])
    exemplo = {nome: prop["examples"][0] for nome, prop in propriedades.items()}
    exemplo["data_vencimento"] = "2999-12-31"  # o exemplo fixo pode vencer com o tempo; o formato é o que importa
    TituloCreate.model_validate(exemplo)
