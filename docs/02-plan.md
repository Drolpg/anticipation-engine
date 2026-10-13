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

## 4. Pontos de atenção
| Ponto | Tratamento |
|---|---|
| `env.py` do Alembic chama `fileConfig` e desliga os loggers da aplicação | Usar `disable_existing_loggers=False` (M2-T3). |

## 5. Fora do MVP (evoluções)
Outbox/reconciliação para o título órfão · DLQ e retry por tipo de erro · rate limiting · `Idempotency-Key` no POST · autenticação · métricas/tracing · paginação · **CNPJ alfanumérico** (a Receita passa a emitir CNPJ com letras a partir de jul/2026 — vale confirmar a regra; o validador fica isolado em `core/cnpj.py`) · "hoje" no fuso `America/Sao_Paulo` (MVP usa `date.today()` do servidor) · bureau de crédito real no lugar do `sleep`.

## 6. Débitos técnicos intencionais
Escolhas conscientes para manter o projeto simples e barato. A demo publicada é só para testes, com dados fictícios.

| Débito | Por que foi aceito | Risco | Como pagar |
|---|---|---|---|
| Sem autenticação nem autorização | Avaliadores acessam direto pelo `/docs`; não há dado sensível | Qualquer pessoa com o link cria títulos e pode encher o banco | OAuth2/JWT com escopos por cedente; no mínimo, chave de API |
| Sem HTTPS na demo | Exige domínio e certificado; custo e complexidade fora do objetivo | Tráfego em texto puro (uma chave de API ali daria falsa segurança) | Domínio + proxy com certificado, ou ALB + ACM |
| Sem rate limiting | Mesmo motivo da autenticação | Abuso de volume | Limite por IP no proxy ou na API |
| Instância única, sem backup do banco | Custo mínimo (uma EC2 com Postgres e Redis em containers) | Perda de dados se a máquina ou o disco falhar | RDS com backup automático, ElastiCache e mais de uma instância da API |
| Sem outbox/reconciliação | Ver §5 | Título fica `PENDENTE` quando a fila cai (resposta 503) | Transactional Outbox + job de reconciliação |

Mitigações adotadas na demo: dados fictícios avisados na descrição do Swagger, porta 80 restringível a um IP (`deploy.sh up --my-ip`), alerta de orçamento na conta, e `stop`/`destroy` ao fim da avaliação.
