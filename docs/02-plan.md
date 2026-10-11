# 02 — Plano técnico

## 1. Arquitetura
Camadas simples, no padrão do FastAPI. Sem hexagonal, sem repository, sem interfaces.

```
HTTP ─▶ api/ (routers) ─▶ services/ (regra de negócio) ─▶ models/ + db/ (SQLAlchemy) ─▶ PostgreSQL
                               │
                               └─▶ services/fila.py ─▶ Celery ─▶ Redis ─▶ worker/tasks.py ─▶ services/analise_credito.py
```
- `api/` só traduz HTTP ⇄ serviços (sem regra de negócio).
- `services/` tem a regra e **não importa FastAPI**; só `fila.py` conhece o Celery (e importa a task dentro da função).
- `worker/` é uma casca fina: abre sessão e chama `services/`.

## 2. Estrutura de diretórios (alvo)
```
anticipation_engine/
├─ AGENTS.md  pytest.ini  pyproject.toml  uv.lock  Dockerfile  docker-compose.yml
├─ .env.example  .env (ignorado)  alembic.ini  migrations/
├─ docs/  (00-constitution, 01-spec, 02-plan, 03-tasks)
├─ src/anticipation_engine/
│  ├─ main.py                  # app FastAPI, lifespan (logging), handlers, middleware request-id
│  ├─ core/   config.py  cnpj.py  logging.py  errors.py
│  ├─ db/     base.py  session.py          # Base, engine, SessionLocal, get_db
│  ├─ models/ __init__.py  titulo.py       # Titulo, StatusTitulo
│  ├─ schemas/ titulo.py                   # TituloCreate, TituloCreated, TituloRead
│  ├─ services/  analise_credito.py        # decidir_credito, analisar (sleep 5s), processar_titulo
│  │             fila.py                   # enfileirar_analise()
│  ├─ api/    titulos.py  health.py
│  └─ worker/ celery_app.py  tasks.py
└─ tests/  conftest.py  unit/  integration/  infra/  e2e/
```
O `main.py` da raiz é apagado: o app passa a viver em `anticipation_engine.main:app`.

## 3. Decisões que afetam o código
| Decisão | Motivo |
|---|---|
| SQLAlchemy 2.x **síncrono** + psycopg 3; endpoints `def` | Celery é síncrono; menos armadilhas. |
| PK **UUID** gerado na aplicação | Não enumerável. |
| **Commit → depois enfileira**; fila falhou ⇒ `503` e título fica `PENDENTE` | Worker nunca lê linha inexistente. Título órfão é limitação conhecida (solução real: outbox, §6). |
| Idempotência + **compare-and-set** no UPDATE; sem transação aberta durante a análise | Fila entrega "pelo menos uma vez". |
| `Decimal` + `Numeric(18,2)` | Correção financeira. |
| Schema via **Alembic** (obrigatório); a API não cria tabelas | Padrão de produção; o `docker compose` roda `alembic upgrade head` antes de subir a API. |
| Testes com SQLite em arquivo + fakes; Postgres/Redis só no E2E | Suíte em ~1 s sem Docker. |
| Envelope de erro único com `code` estável | Cliente programa contra o `code`. |
| Log JSON com `logging` da stdlib; configurar **só** o logger `anticipation_engine` (propagate ligado) | Sem dependência extra; não quebra o `caplog` dos testes. |

## 4. Estado atual do repositório (a corrigir)
- `pyproject.toml`: tem `django` e `boto3` (fora da stack); faltam SQLAlchemy, Celery, psycopg, pydantic-settings, alembic, pytest.
- `docker-compose.yml`: só `api` + `db`; faltam `worker`, `redis`, healthchecks, `depends_on` com condição; senha em texto; chave `version` obsoleta; `build: .` sem `Dockerfile`; `DATABASE_URL` sem driver (`postgresql+psycopg://`).
- `main.py` na raiz: `uvicorn.run()` sem argumentos e import sem uso.
- `README.md` vazio; `.gitignore` sem `.env`.

## 5. Riscos
| Risco | Mitigação |
|---|---|
| `requires-python >=3.14` pode não ter wheels de alguma dependência (testei em 3.13, não em 3.14) | M0-T2: rodar `uv sync`; se falhar, `uv python pin 3.13`. |
| `env.py` do Alembic chama `fileConfig` e desliga os loggers da aplicação | Usar `disable_existing_loggers=False` (M2-T3). |
| Agente "consertar" teste em vez do código | `AGENTS.md` proíbe; revisão do diff por milestone. |

## 6. Fora do MVP (assunto de entrevista, não de código)
Outbox/reconciliação para o título órfão · DLQ e retry por tipo de erro · rate limiting · `Idempotency-Key` no POST · autenticação · métricas/tracing · paginação · **CNPJ alfanumérico** (a Receita passa a emitir CNPJ com letras a partir de jul/2026 — vale confirmar a regra; o validador fica isolado em `core/cnpj.py`) · "hoje" no fuso `America/Sao_Paulo` (MVP usa `date.today()` do servidor) · bureau de crédito real no lugar do `sleep`.
