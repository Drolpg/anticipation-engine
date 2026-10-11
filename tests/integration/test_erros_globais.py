"""RF-08 — tratamento global de exceções, request-id e health."""

import logging
import uuid

from anticipation_engine.db.session import get_db

SEGREDO = "segredo-interno-xyz"


def test_erro_inesperado_retorna_500_sem_vazar_detalhes(client, caplog):
    from anticipation_engine.main import app

    def db_quebrado():
        raise RuntimeError(f"falha com {SEGREDO}")
        yield  # pragma: no cover  (torna a função um generator, como o get_db real)

    app.dependency_overrides[get_db] = db_quebrado

    with caplog.at_level(logging.INFO, logger="anticipation_engine"):
        r = client.get(f"/titulos/{uuid.uuid4()}")

    assert r.status_code == 500
    corpo = r.json()
    assert corpo["error"]["code"] == "INTERNAL_ERROR"
    assert SEGREDO not in r.text
    assert "Traceback" not in r.text
    assert "RuntimeError" not in r.text
    # o request_id permite achar o stack trace nos logs sem expô-lo ao cliente
    assert corpo["error"]["request_id"] == r.headers["x-request-id"]

    erros = [rec for rec in caplog.records if rec.levelno == logging.ERROR]
    assert erros and erros[0].exc_info is not None  # stack trace fica no LOG, não na resposta


def test_toda_resposta_tem_x_request_id(client):
    r = client.get("/health")
    uuid.UUID(r.headers["x-request-id"])


def test_x_request_id_do_cliente_e_propagado(client):
    r = client.get("/health", headers={"X-Request-ID": "meu-id-123"})
    assert r.headers["x-request-id"] == "meu-id-123"


def test_rota_inexistente_usa_o_envelope_de_erro(client):
    r = client.get("/nao-existe")

    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


def test_metodo_nao_permitido_usa_o_envelope_de_erro(client):
    r = client.delete("/titulos")

    assert r.status_code == 405
    assert r.json()["error"]["code"] == "METHOD_NOT_ALLOWED"


def test_health_retorna_ok(client):
    r = client.get("/health")

    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
