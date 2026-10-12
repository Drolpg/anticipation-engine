"""RF-06 — lógica do worker (`processar_titulo`), testada sem Celery e sem Redis."""

import logging

from sqlalchemy import update

from anticipation_engine.models import StatusTitulo, Titulo
from anticipation_engine.services.analise_credito import processar_titulo


def test_aprova_titulo_dentro_das_regras(db, session_factory, criar_titulo, sleeps):
    titulo = criar_titulo(valor="1500.50", dias=30)

    resultado = processar_titulo(db, titulo.id)

    assert resultado == StatusTitulo.APROVADO
    assert sleeps == [5]  # simulação de 5 segundos de análise
    with session_factory() as outra:  # persistiu de verdade
        assert outra.get(Titulo, titulo.id).status == StatusTitulo.APROVADO


def test_rejeita_titulo_acima_do_limite(db, session_factory, criar_titulo, sleeps):
    titulo = criar_titulo(valor="2000000.00")

    assert processar_titulo(db, titulo.id) == StatusTitulo.REJEITADO
    with session_factory() as outra:
        assert outra.get(Titulo, titulo.id).status == StatusTitulo.REJEITADO


def test_idempotente_nao_reprocessa_titulo_ja_decidido(db, criar_titulo, sleeps):
    """Celery entrega 'pelo menos uma vez': a mesma mensagem pode chegar duas vezes."""
    titulo = criar_titulo(status=StatusTitulo.APROVADO)

    assert processar_titulo(db, titulo.id) is None
    assert sleeps == []  # nem chegou a "analisar"
    db.refresh(titulo)
    assert titulo.status == StatusTitulo.APROVADO


def test_titulo_inexistente_loga_erro_e_nao_levanta(db, sleeps, caplog):
    import uuid

    with caplog.at_level(logging.INFO, logger="anticipation_engine"):
        resultado = processar_titulo(db, uuid.uuid4())

    assert resultado is None
    assert any(rec.levelno == logging.ERROR for rec in caplog.records)


def test_nao_segura_transacao_aberta_durante_a_analise(db, criar_titulo, monkeypatch):
    """Sessão com transação aberta durante o sleep prende conexão do pool (e locks) à toa."""
    from anticipation_engine.services import analise_credito

    titulo = criar_titulo()
    estado = {}
    monkeypatch.setattr(analise_credito.time, "sleep", lambda _s: estado.update(em_transacao=db.in_transaction()))

    processar_titulo(db, titulo.id)

    assert estado == {"em_transacao": False}


def test_nao_sobrescreve_decisao_feita_por_outro_worker_durante_a_analise(
    db, session_factory, criar_titulo, monkeypatch
):
    """Compare-and-set: UPDATE ... WHERE status = 'PENDENTE'. Quem chegou primeiro ganha."""
    from anticipation_engine.services import analise_credito

    titulo = criar_titulo(valor="1500.50")  # esta análise decidiria APROVADO

    def outro_worker_decide_primeiro(_segundos):
        with session_factory() as outra:
            outra.execute(update(Titulo).where(Titulo.id == titulo.id).values(status=StatusTitulo.REJEITADO))
            outra.commit()

    monkeypatch.setattr(analise_credito.time, "sleep", outro_worker_decide_primeiro)

    assert processar_titulo(db, titulo.id) is None
    with session_factory() as conferencia:
        assert conferencia.get(Titulo, titulo.id).status == StatusTitulo.REJEITADO


def test_loga_analise_concluida_com_id_e_status(db, criar_titulo, sleeps, caplog):
    titulo = criar_titulo()

    with caplog.at_level(logging.INFO, logger="anticipation_engine"):
        processar_titulo(db, titulo.id)

    registros = [r for r in caplog.records if r.getMessage() == "analise_concluida"]
    assert len(registros) == 1
    assert registros[0].titulo_id == str(titulo.id)
    assert registros[0].status == "APROVADO"
