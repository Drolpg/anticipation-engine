"""Endpoint de verificação de disponibilidade (health check)."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    """Retorna o estado de prontidão e saúde do serviço."""
    return {"status": "ok"}
