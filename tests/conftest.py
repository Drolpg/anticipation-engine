"""Fixtures compartilhadas.

Decisões (ver docs/02-plan.md, §3):
- Os testes NÃO dependem de Postgres/Redis. Usam SQLite em arquivo temporário
  (conexões separadas => isolamento de transação realista) e a fila é substituída
  por um fake. Postgres/Redis reais são exercitados só nos testes `e2e`.
- DATABASE_URL é forçada ANTES de importar a aplicação, para que nada tente
  conectar no Postgres do Docker durante os testes.
"""

import os

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def engine(tmp_path):
    import anticipation_engine.models  # noqa: F401  (registra as tabelas no metadata)
    from anticipation_engine.db.base import Base

    eng = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture
def session_factory(engine):
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def db(session_factory):
    with session_factory() as session:
        yield session


@pytest.fixture
def enfileirados(monkeypatch):
    """Substitui o envio real à fila e registra os IDs enfileirados."""
    from anticipation_engine.services import fila

    chamadas = []
    monkeypatch.setattr(fila, "enfileirar_analise", lambda titulo_id: chamadas.append(titulo_id))
    return chamadas


@pytest.fixture
def client(session_factory, enfileirados):
    from anticipation_engine.db.session import get_db
    from anticipation_engine.main import app

    def _get_db_teste():
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _get_db_teste
    # raise_server_exceptions=False: queremos ver a resposta 500 tratada pelo handler global
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def sleeps(monkeypatch):
    """Evita o sleep(5) real do worker e registra os valores pedidos."""
    from anticipation_engine.services import analise_credito

    chamadas = []
    monkeypatch.setattr(analise_credito.time, "sleep", lambda s: chamadas.append(s))
    return chamadas


@pytest.fixture
def payload_valido():
    return {
        "cnpj_sacado": "11.222.333/0001-81",
        "valor_titulo": "1500.50",
        "data_vencimento": (date.today() + timedelta(days=30)).isoformat(),
    }


@pytest.fixture
def criar_titulo(db):
    """Fábrica de títulos direto no banco (sem passar pela API)."""
    from anticipation_engine.models import StatusTitulo, Titulo

    def _criar(
        *,
        cnpj="11222333000181",
        valor="1500.50",
        dias=30,
        status=StatusTitulo.PENDENTE,
    ):
        titulo = Titulo(
            id=uuid.uuid4(),
            cnpj_sacado=cnpj,
            valor_titulo=Decimal(valor),
            data_vencimento=date.today() + timedelta(days=dias),
            status=status,
        )
        db.add(titulo)
        db.commit()
        return titulo

    return _criar
