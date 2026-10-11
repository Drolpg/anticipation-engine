"""E2E com infraestrutura REAL (Postgres + Redis + worker Celery).

Pré-requisito:  docker compose up -d --build
Execução:       uv run pytest -m e2e
(Fica fora da execução padrão para a suíte rápida continuar rodando sem Docker.)
"""

import os
import time
from datetime import date, timedelta

import httpx
import pytest

BASE_URL = os.environ.get("E2E_BASE_URL", "http://localhost:8000")

pytestmark = pytest.mark.e2e


@pytest.fixture(scope="module")
def http():
    with httpx.Client(base_url=BASE_URL, timeout=10) as c:
        try:
            c.get("/health").raise_for_status()
        except httpx.HTTPError:
            pytest.skip(f"API não está no ar em {BASE_URL} (rode: docker compose up -d --build)")
        yield c


def _aguardar_decisao(http, titulo_id, limite_s=30):
    inicio = time.monotonic()
    while time.monotonic() - inicio < limite_s:
        status = http.get(f"/titulos/{titulo_id}").json()["status"]
        if status != "PENDENTE":
            return status
        time.sleep(1)
    pytest.fail(f"título {titulo_id} continuou PENDENTE após {limite_s}s — o worker está consumindo a fila?")


def _payload(valor):
    return {
        "cnpj_sacado": "11.222.333/0001-81",
        "valor_titulo": valor,
        "data_vencimento": (date.today() + timedelta(days=30)).isoformat(),
    }


def test_titulo_pequeno_e_aprovado_em_background(http):
    r = http.post("/titulos", json=_payload("1500.50"))
    assert r.status_code == 202
    titulo_id = r.json()["id"]

    # a API NÃO bloqueia nos 5s da análise
    assert http.get(f"/titulos/{titulo_id}").json()["status"] == "PENDENTE"
    assert _aguardar_decisao(http, titulo_id) == "APROVADO"


def test_titulo_grande_e_rejeitado_em_background(http):
    titulo_id = http.post("/titulos", json=_payload("2000000.00")).json()["id"]

    assert _aguardar_decisao(http, titulo_id) == "REJEITADO"
