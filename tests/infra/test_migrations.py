"""RNF-08 — o schema é versionado pelo Alembic e as migrações acompanham os models.

Roda em SQLite temporário (sem Docker). Requer `alembic.ini` na raiz e `migrations/`.

Atenção: o `env.py` gerado pelo Alembic chama `fileConfig(...)`, que por padrão DESLIGA os loggers existentes
e quebraria os testes de log. Use `fileConfig(config.config_file_name, disable_existing_loggers=False)`.
"""

from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect

RAIZ = Path(__file__).resolve().parents[2]


@pytest.fixture
def alembic_cfg(tmp_path):
    url = f"sqlite:///{tmp_path / 'migracao.db'}"
    cfg = Config(str(RAIZ / "alembic.ini"))
    cfg.set_main_option("script_location", str(RAIZ / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg, url


def test_upgrade_head_cria_a_tabela_titulos(alembic_cfg):
    cfg, url = alembic_cfg

    command.upgrade(cfg, "head")

    inspetor = inspect(create_engine(url))
    assert "titulos" in inspetor.get_table_names()
    colunas = {c["name"] for c in inspetor.get_columns("titulos")}
    assert {"id", "cnpj_sacado", "valor_titulo", "data_vencimento", "status", "criado_em", "atualizado_em"} <= colunas


def test_migracoes_estao_sincronizadas_com_os_models(alembic_cfg):
    """Se alguém muda um model e esquece de gerar a migração, este teste falha."""
    import anticipation_engine.models  # noqa: F401
    from anticipation_engine.db.base import Base

    cfg, url = alembic_cfg
    command.upgrade(cfg, "head")

    with create_engine(url).connect() as conexao:
        diferencas = compare_metadata(MigrationContext.configure(conexao), Base.metadata)

    assert diferencas == []


def test_downgrade_base_remove_a_tabela(alembic_cfg):
    cfg, url = alembic_cfg
    command.upgrade(cfg, "head")

    command.downgrade(cfg, "base")

    assert "titulos" not in inspect(create_engine(url)).get_table_names()
