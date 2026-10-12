# 03 — Tasks (TDD, ordem de execução)

> v1.2 — simplificado: **sem hexagonal/portas**; **Alembic obrigatório**. Meta: concluir em ~2 dias.

## Cronograma sugerido (2 dias)
| Dia | Milestones | Resultado ao fim do dia |
|---|---|---|
| 1 | M0 → M4 | Fundação, banco, schemas e regra do worker verdes (`tests/unit` + `test_processar_titulo`) |
| 2 | M5 → M7 (+ M8 se sobrar tempo) | Celery, API completa, Docker e E2E |
Se apertar: pule M8-T3/T4; **nunca** pule os testes nem o Alembic.

Os testes **já estão escritos (RED)**. Cada milestone = ler o teste → implementar o mínimo → verde → refatorar → commit.
Marque `[x]` ao concluir. Comandos assumem a raiz do projeto.

## Como usar com o Antigravity
**Prompt de abertura (1x por sessão):**
> Leia `AGENTS.md`, `docs/00-constitution.md`, `docs/01-spec.md`, `docs/02-plan.md` e `docs/03-tasks.md`. Vamos executar uma tarefa por vez, em TDD. Os testes em `tests/` já existem e não podem ser alterados. Confirme em 5 linhas o que entendeu da arquitetura (camadas simples, sem hexagonal) antes de escrever código.

**Prompt por tarefa:**
> Execute a tarefa **M?-T?** de `docs/03-tasks.md`. Rode o teste alvo antes (deve falhar), implemente o mínimo para passar, rode a suíte inteira e `ruff`. Não toque em `tests/`. Ao final responda no formato do `AGENTS.md`.

**Depois de cada milestone**, traga o diff para o Claude revisar contra a spec (checklist "Revisão" de cada milestone).

> ⚠️ **Arquitetura:** padrão em camadas do FastAPI, **sem** hexagonal, portas, repository, Protocols ou pasta `adapters/`. Se a sessão do agente já tiver criado algo assim, simplificar na **M0-T4**.

---

## M0 — Preparação do projeto
- [x] **M0-T1 Dependências (uv).**
  `uv remove django boto3`
  `uv add "fastapi" "uvicorn[standard]" "pydantic>=2" pydantic-settings "sqlalchemy>=2" "psycopg[binary]" "celery[redis]" alembic`
  `uv add --dev pytest pytest-cov httpx pyyaml ruff`
- [x] **M0-T2 Versão do Python.** Rode `uv sync`. Se alguma dependência não instalar em 3.14: `uv python pin 3.13` e ajuste `requires-python`. Registre o resultado em `docs/02-plan.md` §5.
- [x] **M0-T3 Ruff** em `pyproject.toml` (`line-length = 120`, regras `E,F,I,B,UP`).
- [x] **M0-T4 Estrutura e arquitetura.** Criar os pacotes do plano §2 (com `__init__.py`), mover o app para `src/anticipation_engine/main.py` e **apagar o `main.py` da raiz**. Respeitar a regra de dependência (`api → services → models/db`). Nada de `portas.py`/`adapters/`.
- [x] **M0-T5 Baseline RED.** `uv run pytest` ⇒ falhas/erros de import esperados (nada implementado). Guarde o número. Isso prova que os testes realmente testam algo.

**Aprendizado:** por que `src/` layout? o que `uv.lock` garante? **Revisão:** `pyproject` sem django/boto3; árvore igual ao plano.

## M1 — Fundação: config, CNPJ, logging, erros
Alvo: `tests/unit/test_cnpj.py` · `tests/unit/test_logging.py`
- [x] **M1-T1 `core/cnpj.py`** — `validar_cnpj(str) -> str` (RN-01). Cálculo dos dígitos verificadores módulo 11, **sem libs externas** (você precisa saber explicar o algoritmo).
- [x] **M1-T2 `core/logging.py`** — `JsonFormatter` e `configure_logging()` (só o logger `anticipation_engine`, `propagate` ligado, idempotente).
- [x] **M1-T3 `core/config.py`** — `Settings` (pydantic-settings): `database_url`, `redis_url`, `analise_delay_seconds=5`; `get_settings()` com `lru_cache`.
- [x] **M1-T4 `core/errors.py`** — `AppError` base (`status_code`, `code`, `message`), `TituloNaoEncontrado`, `FilaIndisponivel`.

**Aprendizado:** módulo 11; por que `extra={}` e não f-string no log. **Revisão:** CNPJ nunca aparece em log; sem `print`.

## M2 — Modelos e banco
Alvo: `tests/unit/test_models.py`
- [x] **M2-T1 `db/base.py`** (`DeclarativeBase`) e **`db/session.py`** (`engine` com `pool_pre_ping=True`, `SessionLocal`, `get_db` com `with`).
- [x] **M2-T2 `models/titulo.py`** — `StatusTitulo(str, Enum)` e `Titulo` conforme spec §7 (`Uuid`, `Numeric(18,2)`, `Enum(..., native_enum=False)`, timestamps UTC, `onupdate`). Exportar em `models/__init__.py`.
- [x] **M2-T3 Alembic (obrigatório).** Alvo: `tests/infra/test_migrations.py`.
  1. `uv run alembic init migrations` (gera `alembic.ini` + `migrations/`).
  2. `alembic.ini`: `script_location = %(here)s/migrations` e `sqlalchemy.url =` vazio.
  3. `migrations/env.py`: importar `Base` e `anticipation_engine.models`; `target_metadata = Base.metadata`; se `sqlalchemy.url` não vier definido, usar `get_settings().database_url`; **trocar `fileConfig(config.config_file_name)` por `fileConfig(config.config_file_name, disable_existing_loggers=False)`** (senão os loggers da aplicação são desligados e os testes de log quebram).
  4. `uv run alembic revision --autogenerate -m "cria tabela titulos"` e **ler a migração gerada** (colunas, índices, `downgrade`).
  5. A API **não** cria tabelas; quem cria é `alembic upgrade head`.

**Aprendizado:** por que `Numeric` e não `float`; `expire_on_commit`. **Revisão:** índices em `cnpj_sacado` e `status`.

## M3 — Schemas (Pydantic)
Alvo: `tests/unit/test_schemas.py`
- [x] **M3-T1 `schemas/titulo.py`** — `TituloCreate` (`extra="forbid"`, CNPJ via `validar_cnpj`, `Decimal` com `gt=0, max_digits=18, decimal_places=2`, vencimento futuro), `TituloCreated`, `TituloRead` (`from_attributes=True`).

**Aprendizado:** validadores `Annotated`/`field_validator`; mass assignment. **Revisão:** nenhum `float` no arquivo.

## M4 — Regra de crédito + lógica do worker
Alvo: `tests/unit/test_analise_credito.py` · `tests/integration/test_processar_titulo.py`
- [x] **M4-T1 `services/analise_credito.py` (regra)** — constantes `LIMITE_VALOR`, `PRAZO_MAXIMO_DIAS`; `decidir_credito(valor, vencimento, hoje=None)` (função pura); `analisar(valor, vencimento)` = `time.sleep(settings.analise_delay_seconds)` + `decidir_credito`. Mantenha `import time` no módulo (os testes trocam o sleep).
- [x] **M4-T2 `processar_titulo(db, titulo_id)`** conforme RN-05: ler → se inexistente, `log.error` e `None` → se não `PENDENTE`, `None` → **encerrar a transação** (`rollback`) → chamar `analisar(valor, vencimento)` → `UPDATE … WHERE id=:id AND status='PENDENTE'` → `commit` → checar `rowcount` → `log.info("analise_concluida", extra={titulo_id, status})`.

**Aprendizado:** por que não segurar transação durante o `sleep`; compare-and-set vs `SELECT … FOR UPDATE`; por que **não** usamos hexagonal aqui (plano §4). **Revisão:** `processar_titulo` não importa Celery nem FastAPI.

## M5 — Celery e a fila
Alvo: `tests/unit/test_fila_e_celery.py` · `tests/integration/test_task_celery.py`
- [x] **M5-T1 `worker/celery_app.py`** — `Celery` com broker `settings.redis_url`, `task_serializer="json"`, `accept_content=["json"]`, `include` das tasks.
- [x] **M5-T2 `worker/tasks.py`** — `analisar_credito_task(titulo_id: str)`: `name="anticipation_engine.analisar_credito"`, `acks_late=True`, `max_retries=3`, `retry_backoff=True`, `autoretry_for=(OperationalError,)`. Corpo: abre `SessionLocal()` e chama `processar_titulo`. (Casca fina!)
- [x] **M5-T3 `services/fila.py`** — `enfileirar_analise(titulo_id: UUID)` ⇒ `analisar_credito_task.delay(str(titulo_id))` (import dentro da função, para `services` não depender do Celery em import-time).

**Aprendizado:** `acks_late` e o que acontece se o worker morre; at-least-once vs exactly-once; por que UUID vira `str`.

## M6 — API
Alvo: `tests/integration/test_api_post_titulos.py` · `test_api_get_titulos.py` · `test_erros_globais.py` · `test_fluxo_completo.py`
- [x] **M6-T1 `api/titulos.py`** — `POST /titulos` (202, `Location`; **commit antes de enfileirar**; falha na fila ⇒ `log.error(exc_info=True)` + `FilaIndisponivel`) e `GET /titulos/{id}` (UUID tipado; `TituloNaoEncontrado`). Chame `fila.enfileirar_analise(...)` **via módulo** (os testes fazem monkeypatch nele).
- [x] **M6-T2 `api/health.py`** — `GET /health`.
- [x] **M6-T3 `main.py`** — `lifespan` chamando `configure_logging()`; middleware `X-Request-ID` (propaga o do cliente ou gera UUID; resposta 500 inclui `request_id`); handlers: `AppError`, `RequestValidationError` (→ `details[{field,message}]`), `StarletteHTTPException` (`NOT_FOUND`/`METHOD_NOT_ALLOWED`), e `Exception` genérico (log com stack, resposta sem detalhe).
- [x] **M6-T4 Logs de domínio**: `titulo_recebido` (extra `titulo_id`), `falha_ao_enfileirar`, `erro_inesperado`.

**Aprendizado:** por que 202 e não 201; por que 503 e não 500 quando a fila cai; ordem dos handlers. **Revisão:** `api/` sem regra de negócio; nenhum CNPJ nos logs; nenhum `detail` cru do FastAPI na resposta.

## M7 — Infra (Docker/Compose) + E2E
Alvo: `tests/infra/test_docker_compose.py` · `tests/e2e/test_e2e_compose.py`
- [x] **M7-T1 `Dockerfile`** (imagem slim com `uv`, deps travadas por `uv.lock`, usuário não-root).
- [x] **M7-T2 `docker-compose.yml`** — serviços `api` (porta 8000; comando `sh -c "alembic upgrade head && uvicorn anticipation_engine.main:app --host 0.0.0.0"`), `worker` (`celery -A anticipation_engine.worker.celery_app worker --loglevel=INFO`), `db` (Postgres, volume, healthcheck `pg_isready`), `redis` (healthcheck `redis-cli ping`). `depends_on` na forma longa com `condition: service_healthy`. Sem `ports` em `db`/`redis`. Remover `version:`.
- [x] **M7-T3 Segredos.** `.env.example` versionado, `.env` no `.gitignore`, compose usando `${POSTGRES_PASSWORD}`; `DATABASE_URL=postgresql+psycopg://…`.
- [x] **M7-T4 E2E.** `docker compose up -d --build` e `uv run pytest -m e2e`. Depois o teste manual do critério 4 da spec (derrubar o Redis).

**Aprendizado:** `service_started` vs `service_healthy`; por que só a API roda a migração e o worker apenas espera o banco ficar saudável. **Revisão:** `docker compose config` limpo.

## M8 — Fechamento
- [x] **M8-T1** `uv run pytest --cov=anticipation_engine --cov-report=term-missing` ≥ 90%.
- [x] **M8-T2** `README.md`: o que é, diagrama, como subir, como testar, "fora do MVP".
- [x] **M8-T3** (opcional) GitHub Actions: ruff + pytest.
- [x] **M8-T4** Ensaio de entrevista: explicar em voz alta o fluxo completo, o porquê de commit→fila e do compare-and-set, e como o Alembic entra, sem olhar o código.
