"""Configurações centrais da aplicação carregadas via variáveis de ambiente."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurações da aplicação gerenciadas pelo Pydantic Settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/hopedb"
    redis_url: str = "redis://localhost:6379/0"
    analise_delay_seconds: int = 5
    app_env: str = "development"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Retorna a instância singleton em cache das configurações."""
    return Settings()
