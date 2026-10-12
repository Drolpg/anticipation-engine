"""RF-04 / RF-06 — contrato com a fila e configuração de resiliência do Celery."""

import logging
import uuid

from celery.signals import setup_logging
from sqlalchemy.exc import OperationalError

from anticipation_engine.core.logging import JsonFormatter
from anticipation_engine.services import fila
from anticipation_engine.worker import tasks
from anticipation_engine.worker.celery_app import celery_app


def test_enfileirar_analise_envia_id_como_string(monkeypatch):
    enviados = []
    monkeypatch.setattr(tasks.analisar_credito_task, "delay", lambda *a, **kw: enviados.append((a, kw)))

    titulo_id = uuid.uuid4()
    fila.enfileirar_analise(titulo_id)

    # JSON serializer: UUID não é serializável, então vai como str
    assert enviados == [((str(titulo_id),), {})]


def test_celery_usa_json_como_serializador():
    assert celery_app.conf.task_serializer == "json"
    assert celery_app.conf.accept_content == ["json"]


def test_task_tem_nome_estavel():
    # nome explícito evita quebrar mensagens em voo quando o módulo é renomeado
    assert tasks.analisar_credito_task.name == "anticipation_engine.analisar_credito"


def test_task_e_resiliente():
    task = tasks.analisar_credito_task
    assert task.acks_late is True  # só confirma a mensagem após concluir
    assert task.max_retries == 3
    assert OperationalError in task.autoretry_for  # falha transitória de banco => retry
    assert task.retry_backoff  # backoff exponencial


def test_worker_configura_logs_json_ao_iniciar():
    """RNF-03: o worker é outro processo; sem isto os logs dele saem no formato texto do Celery e sem `titulo_id`.

    O Celery dispara o sinal `setup_logging` ao iniciar; `worker/celery_app.py` deve ligar `configure_logging` nele.
    """
    loggers = [logging.getLogger(), logging.getLogger("anticipation_engine")]
    salvos = [list(lg.handlers) for lg in loggers]
    for lg in loggers:
        lg.handlers.clear()  # parte de um processo "limpo", como o worker real
    try:
        setup_logging.send(sender=None, loglevel=logging.INFO, logfile=None, format="", colorize=False)
        assert any(isinstance(h.formatter, JsonFormatter) for lg in loggers for h in lg.handlers)
    finally:
        for lg, handlers in zip(loggers, salvos, strict=True):
            lg.handlers[:] = handlers
