"""RF-07 — GET /titulos/{id}."""

import uuid
from decimal import Decimal

from anticipation_engine.models import StatusTitulo


def test_get_retorna_o_titulo(client, criar_titulo):
    titulo = criar_titulo(valor="1500.50")

    r = client.get(f"/titulos/{titulo.id}")

    assert r.status_code == 200
    corpo = r.json()
    assert corpo["id"] == str(titulo.id)
    assert corpo["cnpj_sacado"] == "11222333000181"
    assert Decimal(corpo["valor_titulo"]) == Decimal("1500.50")
    assert corpo["data_vencimento"] == titulo.data_vencimento.isoformat()
    assert corpo["status"] == "PENDENTE"
    assert corpo["criado_em"]
    assert corpo["atualizado_em"]


def test_get_reflete_status_atual(client, criar_titulo):
    titulo = criar_titulo(status=StatusTitulo.REJEITADO)

    assert client.get(f"/titulos/{titulo.id}").json()["status"] == "REJEITADO"


def test_get_inexistente_retorna_404_padronizado(client):
    r = client.get(f"/titulos/{uuid.uuid4()}")

    assert r.status_code == 404
    assert r.json()["error"]["code"] == "TITULO_NAO_ENCONTRADO"


def test_get_com_id_malformado_retorna_422(client):
    r = client.get("/titulos/nao-e-um-uuid")

    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"
