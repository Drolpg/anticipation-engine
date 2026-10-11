"""Fluxo ponta a ponta SEM infraestrutura: POST -> worker -> GET (fila e sleep fakes)."""

from datetime import date, timedelta

from anticipation_engine.services.analise_credito import processar_titulo


def test_fluxo_aprovado(client, db, payload_valido, enfileirados, sleeps):
    titulo_id = client.post("/titulos", json=payload_valido).json()["id"]
    assert client.get(f"/titulos/{titulo_id}").json()["status"] == "PENDENTE"

    processar_titulo(db, enfileirados[0])  # o que o worker faria ao consumir a fila

    assert client.get(f"/titulos/{titulo_id}").json()["status"] == "APROVADO"


def test_fluxo_rejeitado_por_valor_alto(client, db, payload_valido, enfileirados, sleeps):
    payload_valido["valor_titulo"] = "2000000.00"
    titulo_id = client.post("/titulos", json=payload_valido).json()["id"]

    processar_titulo(db, enfileirados[0])

    assert client.get(f"/titulos/{titulo_id}").json()["status"] == "REJEITADO"


def test_fluxo_rejeitado_por_prazo_longo(client, db, payload_valido, enfileirados, sleeps):
    payload_valido["data_vencimento"] = (date.today() + timedelta(days=400)).isoformat()
    titulo_id = client.post("/titulos", json=payload_valido).json()["id"]

    processar_titulo(db, enfileirados[0])

    assert client.get(f"/titulos/{titulo_id}").json()["status"] == "REJEITADO"
