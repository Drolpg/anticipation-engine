"""RNF — contrato da infraestrutura (docker-compose.yml, Dockerfile, segredos).

Estes testes leem arquivos; não precisam de Docker instalado.
Requer PyYAML no grupo dev:  uv add --dev pyyaml
"""

from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[2]
COMPOSE = RAIZ / "docker-compose.yml"


@pytest.fixture(scope="module")
def compose():
    return yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))


def _env(servico: dict) -> dict:
    """`environment` pode ser lista (K=V) ou dict; normaliza para dict."""
    env = servico.get("environment", {})
    if isinstance(env, list):
        return dict(item.split("=", 1) for item in env)
    return env


def test_servicos_obrigatorios(compose):
    assert {"api", "worker", "redis", "db"} <= set(compose["services"])


def test_dockerfile_existe():
    assert (RAIZ / "Dockerfile").is_file()


def test_api_expoe_porta_8000(compose):
    assert any("8000" in str(p) for p in compose["services"]["api"]["ports"])


def test_api_exposta_apenas_em_localhost(compose):
    """A API não tem autenticação: por padrão só a própria máquina acessa (o deploy na AWS muda via API_BIND)."""
    assert all(str(p).startswith("${API_BIND:-127.0.0.1}:") for p in compose["services"]["api"]["ports"])


def test_banco_e_redis_nao_sao_expostos_ao_host(compose):
    assert "ports" not in compose["services"]["db"]
    assert "ports" not in compose["services"]["redis"]


def test_api_aplica_migracoes_antes_de_subir(compose):
    comando = compose["services"]["api"]["command"]
    comando = comando if isinstance(comando, str) else " ".join(comando)
    assert "alembic upgrade head" in comando and "uvicorn" in comando
    assert comando.index("alembic upgrade head") < comando.index("uvicorn")


def test_api_tem_healthcheck(compose):
    assert "healthcheck" in compose["services"]["api"]


def test_worker_espera_a_api_saudavel_porque_ela_aplica_as_migracoes(compose):
    assert compose["services"]["worker"]["depends_on"]["api"]["condition"] == "service_healthy"


def test_worker_roda_celery(compose):
    comando = compose["services"]["worker"]["command"]
    comando = comando if isinstance(comando, str) else " ".join(comando)
    assert "celery" in comando and "worker" in comando


@pytest.mark.parametrize("servico", ["db", "redis"])
def test_healthcheck_nos_servicos_de_dados(compose, servico):
    assert "healthcheck" in compose["services"][servico]


@pytest.mark.parametrize("servico", ["api", "worker"])
@pytest.mark.parametrize("dependencia", ["db", "redis"])
def test_api_e_worker_esperam_dependencias_saudaveis(compose, servico, dependencia):
    depends_on = compose["services"][servico]["depends_on"]
    assert isinstance(depends_on, dict), "use a forma longa: depends_on: {db: {condition: service_healthy}}"
    assert depends_on[dependencia]["condition"] == "service_healthy"


def test_dados_do_postgres_sao_persistidos_em_volume(compose):
    volumes = compose["services"]["db"]["volumes"]
    assert any("/var/lib/postgresql/data" in str(v) for v in volumes)


def test_senha_do_banco_nao_esta_hardcoded_no_compose(compose):
    senha = _env(compose["services"]["db"])["POSTGRES_PASSWORD"]
    assert str(senha).startswith("${"), "use ${POSTGRES_PASSWORD} vindo do arquivo .env"


def test_env_fora_do_git_e_exemplo_versionado():
    assert (RAIZ / ".env.example").is_file()
    linhas = (RAIZ / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert ".env" in [linha.strip() for linha in linhas]
