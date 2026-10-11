"""RF-03 — modelo SQLAlchemy `Titulo` e enum `StatusTitulo`."""

import uuid
from datetime import date, timedelta
from decimal import Decimal

from anticipation_engine.models import StatusTitulo, Titulo


def test_status_titulo_valores():
    assert {s.value for s in StatusTitulo} == {"PENDENTE", "APROVADO", "REJEITADO"}
    assert StatusTitulo.PENDENTE == "PENDENTE"  # str Enum: serializa direto em JSON


def test_defaults_ao_persistir(db):
    titulo = Titulo(
        cnpj_sacado="11222333000181",
        valor_titulo=Decimal("1500.50"),
        data_vencimento=date.today() + timedelta(days=30),
    )
    db.add(titulo)
    db.commit()

    assert isinstance(titulo.id, uuid.UUID)
    assert titulo.status == StatusTitulo.PENDENTE
    assert titulo.criado_em is not None
    assert titulo.atualizado_em is not None


def test_valor_monetario_nao_perde_precisao(db):
    titulo = Titulo(
        cnpj_sacado="11222333000181",
        valor_titulo=Decimal("0.10"),
        data_vencimento=date.today() + timedelta(days=1),
    )
    db.add(titulo)
    db.commit()
    db.expire_all()

    recarregado = db.get(Titulo, titulo.id)
    assert recarregado.valor_titulo == Decimal("0.10")
    assert isinstance(recarregado.valor_titulo, Decimal)


def test_atualizado_em_acompanha_mudanca_de_status(db, criar_titulo):
    titulo = criar_titulo()
    db.refresh(titulo)  # relê do banco: tipos de data/hora consistentes entre SQLite e Postgres
    antes = titulo.atualizado_em

    titulo.status = StatusTitulo.APROVADO
    db.commit()
    db.refresh(titulo)

    assert titulo.atualizado_em >= antes
    assert titulo.criado_em <= titulo.atualizado_em
