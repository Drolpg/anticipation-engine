"""Configuração de logs estruturados em JSON (RF-08).

Formata logs em JSON com campos essenciais (timestamp, level, message, logger),
campos extras recebidos via extra={...} e informações de exceção quando presentes.
"""

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

# Atributos padrão do logging.LogRecord que não devem ser replicados como extras
RESERVED_ATTRS = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "msecs",
    "message",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
    "taskName",
}


class JsonFormatter(logging.Formatter):
    """Formatador que serializa registros de log como objetos JSON."""

    def format(self, record: logging.LogRecord) -> str:
        """Formata o registro de log em uma linha JSON estruturada."""
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }

        # Trata exceções (exc_info)
        if record.exc_info:
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)
            payload["exception"] = record.exc_text
        elif record.exc_text:
            payload["exception"] = record.exc_text

        # Trata stack info quando presente
        if record.stack_info:
            payload["stack_info"] = self.formatStack(record.stack_info)

        # Captura campos passados via extra={...}
        for key, value in record.__dict__.items():
            if key not in RESERVED_ATTRS and not key.startswith("_"):
                payload[key] = value

        return json.dumps(payload, default=str)


def configure_logging(level: int | str = logging.INFO) -> None:
    """Configura o logger da aplicação 'anticipation_engine'.

    Garante:
    - Formatação estruturada em JSON via JsonFormatter.
    - Configura apenas o logger 'anticipation_engine' (não afeta o root logger).
    - propagate=True para não quebrar a captura de logs por fixtures como pytest caplog.
    - Idempotência: chamadas repetidas não duplicam handlers.
    """
    logger = logging.getLogger("anticipation_engine")

    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)

    logger.setLevel(level)
    logger.propagate = True

    # Evita duplicar handlers se já configurado
    for handler in logger.handlers:
        if isinstance(handler.formatter, JsonFormatter):
            return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
