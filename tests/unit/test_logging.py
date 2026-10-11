"""RF-08 — logs estruturados em JSON."""

import json
import logging
import sys

from anticipation_engine.core.logging import JsonFormatter


def _registro(msg="titulo_recebido", level=logging.INFO, exc_info=None, **extras):
    rec = logging.LogRecord("anticipation_engine.teste", level, __file__, 1, msg, None, exc_info)
    for chave, valor in extras.items():
        setattr(rec, chave, valor)
    return rec


def test_formata_como_json_com_campos_basicos():
    saida = json.loads(JsonFormatter().format(_registro()))
    assert saida["level"] == "INFO"
    assert saida["message"] == "titulo_recebido"
    assert saida["logger"] == "anticipation_engine.teste"
    assert "timestamp" in saida


def test_inclui_campos_extras_no_json():
    saida = json.loads(JsonFormatter().format(_registro(titulo_id="abc-123", request_id="r-1")))
    assert saida["titulo_id"] == "abc-123"
    assert saida["request_id"] == "r-1"


def test_exception_vai_para_o_log_como_campo():
    try:
        raise RuntimeError("falhou")
    except RuntimeError:
        rec = _registro("erro_inesperado", logging.ERROR, exc_info=sys.exc_info())
    saida = json.loads(JsonFormatter().format(rec))
    assert saida["level"] == "ERROR"
    assert "RuntimeError" in saida["exception"]
