"""Ponto de entrada da aplicação FastAPI."""

import logging
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from anticipation_engine.api import health_router, titulos_router
from anticipation_engine.core.config import get_settings
from anticipation_engine.core.errors import AppError
from anticipation_engine.core.logging import configure_logging

logger = logging.getLogger("anticipation_engine")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Gerencia ciclo de vida da aplicação inicializando logs estruturados."""
    settings = get_settings()
    configure_logging(settings.log_level)
    yield


app = FastAPI(
    title="Motor de Antecipação de Recebíveis",
    lifespan=lifespan,
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next: Any) -> Any:
    """Propaga ou gera o identificador de correlação X-Request-ID para cada requisição."""
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Trata erros previstos da aplicação padronizando o envelope de erro."""
    request_id = getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID") or str(uuid.uuid4())
    content: dict[str, Any] = {
        "error": {
            "code": exc.code,
            "message": exc.message,
        }
    }
    if exc.details:
        content["error"]["details"] = exc.details

    return JSONResponse(
        status_code=exc.status_code,
        content=content,
        headers={"X-Request-ID": request_id},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Trata falhas de validação de schemas do Pydantic no envelope unificado."""
    request_id = getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID") or str(uuid.uuid4())
    details = []
    for err in exc.errors():
        loc = err.get("loc", ())
        field = str(loc[-1]) if loc else "body"
        msg = str(err.get("msg", "Erro de validação"))
        if msg.startswith("Value error, "):
            msg = msg[len("Value error, ") :]
        details.append({"field": field, "message": msg})

    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Payload inválido.",
                "details": details,
            }
        },
        headers={"X-Request-ID": request_id},
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Trata exceções HTTP do Starlette (404 Not Found, 405 Method Not Allowed, etc.)."""
    request_id = getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID") or str(uuid.uuid4())
    code = "HTTP_ERROR"
    message = str(exc.detail) if exc.detail else "Erro HTTP."
    if exc.status_code == 404:
        code = "NOT_FOUND"
        message = "Recurso não encontrado."
    elif exc.status_code == 405:
        code = "METHOD_NOT_ALLOWED"
        message = "Método não permitido."

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": code,
                "message": message,
            }
        },
        headers={"X-Request-ID": request_id},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Trata exceções inesperadas gravando stack trace no log e ocultando do cliente."""
    request_id = getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID") or str(uuid.uuid4())
    logger.error("erro_inesperado", exc_info=True, extra={"request_id": request_id})
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "Erro interno do servidor.",
                "request_id": request_id,
            }
        },
        headers={"X-Request-ID": request_id},
    )


app.include_router(titulos_router)
app.include_router(health_router)
