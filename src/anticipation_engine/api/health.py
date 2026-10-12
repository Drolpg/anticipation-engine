"""Endpoint de verificação de disponibilidade (health check)."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health", summary="Verificar saúde do serviço")
def health() -> dict[str, str]:
    """Responde `200` quando a API está no ar. Usado pelo healthcheck do Docker e por monitoramento externo."""
    return {"status": "ok"}
