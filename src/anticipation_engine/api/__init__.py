"""Camada de API HTTP da aplicação."""

from anticipation_engine.api.health import router as health_router
from anticipation_engine.api.titulos import router as titulos_router

__all__ = ["health_router", "titulos_router"]
