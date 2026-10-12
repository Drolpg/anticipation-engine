"""RF-01..RF-05 — POST /titulos."""

import logging
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from anticipation_engine.models import StatusTitulo, Titulo
from anticipation_engine.services import fila

CNPJ_DIGITOS = "11222333000181"


def test_post_valido_retorna_202_com_id_e_status_pendente(client, payload_valido):
    r = client.post("/titulos", json=payload_valido)

    assert r.status_code == 202
    corpo = r.json()
    uuid.UUID(corpo["id"])  # levanta se não for UUID
    assert corpo["status"] == "PENDENTE"
    assert r.headers["location"] == f"/titulos/{corpo['id']}"


def test_post_persiste_titulo_normalizado_como_pendente(client, db, payload_valido):
    r = client.post("/titulos", json=payload_valido)

    titulo = db.get(Titulo, uuid.UUID(r.json()["id"]))
    assert titulo is not None
    assert titulo.status == StatusTitulo.PENDENTE
    assert titulo.cnpj_sacado == CNPJ_DIGITOS
    assert titulo.valor_titulo == Decimal("1500.50")


def test_post_enfileira_o_id_do_titulo(client, payload_valido, enfileirados):
    r = client.post("/titulos", json=payload_valido)

    assert [str(i) for i in enfileirados] == [r.json()["id"]]


def test_enfileira_somente_depois_do_commit(client, session_factory, payload_valido, monkeypatch):
    """Evita a race condition clássica: worker pega o ID antes da linha existir no banco."""
    visto = {}

    def fake(titulo_id):
        with session_factory() as outra_sessao:  # conexão independente da requisição
            visto["existe"] = outra_sessao.get(Titulo, titulo_id) is not None

    monkeypatch.setattr(fila, "enfileirar_analise", fake)

    assert client.post("/titulos", json=payload_valido).status_code == 202
    assert visto == {"existe": True}


INVALIDOS = [
    ("cnpj_sacado", "11.222.333/0001-82"),
    ("cnpj_sacado", "11111111111111"),
    ("cnpj_sacado", "123"),
    ("valor_titulo", "0"),
    ("valor_titulo", "-1"),
    ("valor_titulo", "abc"),
    ("valor_titulo", "10.999"),
    ("data_vencimento", (date.today() - timedelta(days=1)).isoformat()),
    ("data_vencimento", date.today().isoformat()),
    ("data_vencimento", "31/12/2030"),
    ("status", "APROVADO"),  # cliente não decide o status
]


@pytest.mark.parametrize("campo, valor", INVALIDOS)
def test_payload_invalido_retorna_422_sem_salvar_nem_enfileirar(client, db, payload_valido, enfileirados, campo, valor):
    payload_valido[campo] = valor

    r = client.post("/titulos", json=payload_valido)

    assert r.status_code == 422
    erro = r.json()["error"]
    assert erro["code"] == "VALIDATION_ERROR"
    assert campo in [d["field"] for d in erro["details"]]
    assert all(isinstance(d["message"], str) and d["message"] for d in erro["details"])
    assert enfileirados == []
    assert db.scalar(select(func.count()).select_from(Titulo)) == 0


@pytest.mark.parametrize("campo", ["cnpj_sacado", "valor_titulo", "data_vencimento"])
def test_campo_obrigatorio_ausente_retorna_422(client, payload_valido, campo):
    payload_valido.pop(campo)

    r = client.post("/titulos", json=payload_valido)

    assert r.status_code == 422
    assert campo in [d["field"] for d in r.json()["error"]["details"]]


def test_corpo_que_nao_e_json_retorna_422_no_mesmo_formato(client):
    r = client.post("/titulos", content="isto não é json", headers={"content-type": "application/json"})

    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_falha_na_fila_retorna_503_e_mantem_titulo_pendente(client, db, payload_valido, monkeypatch, caplog):
    def fila_fora_do_ar(_titulo_id):
        raise ConnectionError("redis://:s3nh4-secreta@redis:6379 connection refused")

    monkeypatch.setattr(fila, "enfileirar_analise", fila_fora_do_ar)

    with caplog.at_level(logging.INFO, logger="anticipation_engine"):
        r = client.post("/titulos", json=payload_valido)

    assert r.status_code == 503
    assert r.json()["error"]["code"] == "FILA_INDISPONIVEL"
    assert "s3nh4" not in r.text  # nada de detalhe interno vazando
    # título já commitado continua PENDENTE (reconciliação futura: ver plan.md, "Fora do MVP")
    assert db.scalars(select(Titulo)).one().status == StatusTitulo.PENDENTE
    assert any(rec.levelno == logging.ERROR for rec in caplog.records)


def test_log_info_de_titulo_recebido_nao_expoe_cnpj(client, payload_valido, caplog):
    with caplog.at_level(logging.INFO, logger="anticipation_engine"):
        r = client.post("/titulos", json=payload_valido)

    registros = [rec for rec in caplog.records if rec.getMessage() == "titulo_recebido"]
    assert len(registros) == 1
    assert registros[0].levelno == logging.INFO
    assert registros[0].titulo_id == r.json()["id"]
    # CNPJ do sacado não deve aparecer em nenhum atributo de nenhum log
    assert all(CNPJ_DIGITOS not in str(rec.__dict__) for rec in caplog.records)
