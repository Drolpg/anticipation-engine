"""RF-06 — a task Celery é uma casca fina em volta de `processar_titulo`."""

from anticipation_engine.models import StatusTitulo, Titulo
from anticipation_engine.worker import tasks


def test_task_abre_sessao_propria_e_atualiza_o_titulo(session_factory, criar_titulo, sleeps, monkeypatch):
    titulo = criar_titulo(valor="1500.50")
    monkeypatch.setattr(tasks, "SessionLocal", session_factory)  # troca o banco real pelo de teste

    tasks.analisar_credito_task.run(str(titulo.id))  # .run executa síncrono, sem broker

    with session_factory() as conferencia:
        assert conferencia.get(Titulo, titulo.id).status == StatusTitulo.APROVADO
