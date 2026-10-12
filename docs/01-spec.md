# 01 — Especificação (Spec)

> Fonte da verdade do comportamento. Versão 1.2 · status: **aprovada para implementação**.
>
> **Histórico:** v1.0 versão inicial · v1.1 simplificação (sem hexagonal) · v1.2 Alembic obrigatório (RNF-08) · v1.3 documentação OpenAPI e deploy de demonstração (RNF-09, RNF-10).
> Mudou o comportamento? Altere aqui primeiro (ver `00-constitution.md`).

## 1. Visão geral
API que recebe títulos financeiros (duplicatas/notas fiscais) para antecipação, valida-os, grava-os como `PENDENTE` e responde `202` sem bloquear. Um worker em background faz a análise de crédito (simulada) e decide `APROVADO` ou `REJEITADO`. O cliente acompanha o status por `GET`.

**Fora do escopo do MVP**: autenticação, multi-tenant, cessão/liquidação real, integração com bureau real, paginação/listagem, CNPJ alfanumérico (ver plano §5).

## 2. Glossário
| Termo | Significado |
|---|---|
| Título | Direito creditório a receber (duplicata/NF). |
| Sacado | Devedor do título, identificado pelo CNPJ. |
| Antecipação | Receber hoje, com deságio, um valor que só vence no futuro. |
| Análise de crédito | Decisão sobre aprovar ou rejeitar a antecipação. |

## 3. Fluxo principal
```
Cliente ──POST /titulos──▶ API ──valida──▶ grava PENDENTE ──commit──▶ enfileira(id) ──▶ 202 {id,status}
                                                                          │
                                                          Redis ◀─────────┘
                                                            │
                                                      Worker Celery ──analisa(5s)──▶ UPDATE status (APROVADO|REJEITADO)
Cliente ──GET /titulos/{id}──▶ API ──▶ 200 {…, status}
```

## 4. Requisitos funcionais
| ID | Requisito |
|---|---|
| **RF-01** | `POST /titulos` recebe `cnpj_sacado`, `valor_titulo`, `data_vencimento` (JSON). |
| **RF-02** | Validação rigorosa via Pydantic (regras RN-01..RN-03). Falha ⇒ `422` com envelope de erro e lista de campos. Nada é gravado nem enfileirado. |
| **RF-03** | Título válido é gravado em PostgreSQL com status `PENDENTE`, CNPJ normalizado (14 dígitos) e id UUID gerado pelo sistema. |
| **RF-04** | O id é enviado à fila **somente depois do commit** (senão o worker pode buscar uma linha que ainda não existe). |
| **RF-05** | Resposta `202 Accepted` com `{"id", "status": "PENDENTE"}` e header `Location: /titulos/{id}`. Não espera a análise. |
| **RF-06** | Worker consome o id, executa a análise (RN-04, ~5 s simulados) e atualiza o status. Deve ser **idempotente** e seguro sob concorrência (RN-05). |
| **RF-07** | `GET /titulos/{id}` devolve o título com status atual; `404` se não existir; `422` se o id não for UUID. |
| **RF-08** | Logs estruturados (JSON) e tratamento global de exceções: o cliente nunca recebe stack trace; cada resposta carrega `X-Request-ID`. |
| **RF-09** | `GET /health` ⇒ `200 {"status":"ok"}` (liveness). |

## 5. Regras de negócio
- **RN-01 CNPJ**: aceita formatado (`11.222.333/0001-81`) ou só dígitos; deve ter 14 dígitos, dígitos verificadores corretos e não ser sequência repetida (`11111111111111`). Armazenado só com dígitos. (MVP: apenas numérico.)
- **RN-02 Valor**: `Decimal` > 0, no máximo 2 casas decimais, cabendo em `Numeric(18,2)`. Nunca `float`.
- **RN-03 Vencimento**: estritamente **depois de hoje** (hoje ⇒ inválido).
- **RN-04 Decisão de crédito** (determinística, para ser testável):
  - `REJEITADO` se `valor_titulo > 1.000.000,00` **ou** prazo (`vencimento − hoje`) `> 365` dias;
  - senão `APROVADO`. Fronteiras (exatamente 1.000.000,00 e 365 dias) **aprovam**.
- **RN-05 Estados**: `PENDENTE → APROVADO | REJEITADO`; estados finais são imutáveis. Reprocessar um título já decidido não faz nada. Se outro worker decidir durante a análise, a decisão que chegou primeiro vence (UPDATE condicional `WHERE status = 'PENDENTE'`).
- **RN-06** O cliente **não** envia `status`; campo extra no payload ⇒ `422`.

## 6. Contrato da API

### 6.1 `POST /titulos`
Request:
```json
{ "cnpj_sacado": "11.222.333/0001-81", "valor_titulo": "1500.50", "data_vencimento": "2026-12-31" }
```
Response `202` (header `Location: /titulos/3f1c…`):
```json
{ "id": "3f1c2a52-…", "status": "PENDENTE" }
```

### 6.2 `GET /titulos/{id}`
Response `200`:
```json
{ "id": "3f1c…", "cnpj_sacado": "11222333000181", "valor_titulo": "1500.50",
  "data_vencimento": "2026-12-31", "status": "APROVADO",
  "criado_em": "2026-10-11T18:00:00Z", "atualizado_em": "2026-10-11T18:00:06Z" }
```

### 6.3 Envelope de erro (único formato para qualquer erro)
```json
{ "error": { "code": "VALIDATION_ERROR", "message": "Payload inválido.",
             "details": [ { "field": "cnpj_sacado", "message": "CNPJ inválido" } ] } }
```
| HTTP | `code` | Quando |
|---|---|---|
| 422 | `VALIDATION_ERROR` | Payload/parâmetro inválido (inclui JSON malformado). `details[].field` = nome do campo. |
| 404 | `TITULO_NAO_ENCONTRADO` | `GET` de id inexistente. |
| 404 | `NOT_FOUND` | Rota inexistente. |
| 405 | `METHOD_NOT_ALLOWED` | Método não suportado. |
| 503 | `FILA_INDISPONIVEL` | Título gravado, mas a fila falhou. Título permanece `PENDENTE`. Mensagem genérica (sem detalhe do broker). |
| 500 | `INTERNAL_ERROR` | Qualquer erro não previsto. Inclui `request_id`; stack trace **só** no log. |

## 7. Modelo de dados — tabela `titulos`
| Coluna | Tipo | Notas |
|---|---|---|
| `id` | UUID PK | gerado pela aplicação (`uuid4`). Não sequencial ⇒ não enumerável. |
| `cnpj_sacado` | `varchar(14)` | só dígitos; índice. |
| `valor_titulo` | `numeric(18,2)` | |
| `data_vencimento` | `date` | |
| `status` | `varchar(20)` | enum `StatusTitulo`, default `PENDENTE`; índice. `native_enum=False` (evita dor de migração de ENUM do Postgres). |
| `criado_em` / `atualizado_em` | `timestamptz` | UTC; `atualizado_em` muda a cada UPDATE. |

## 8. Requisitos não funcionais
- **RNF-01 Não bloqueio**: `POST` não depende da análise; a análise não prende transação nem conexão de banco durante o `sleep`.
- **RNF-02 Resiliência**: task Celery com `acks_late`, `max_retries=3`, backoff exponencial, retry só para falha transitória de banco (`OperationalError`); nome de task explícito e estável; serializer JSON.
- **RNF-03 Observabilidade**: log JSON (`timestamp, level, logger, message` + extras); `titulo_id` e `request_id` como extras; **CNPJ nunca é logado**.
- **RNF-04 Segurança**: sem stack trace nas respostas; segredos via `.env` (fora do git, com `.env.example` versionado); Postgres e Redis sem `ports` no host.
- **RNF-05 Infra**: `docker compose up` sobe `api`, `worker`, `db`, `redis` com healthchecks e `depends_on: service_healthy`.
- **RNF-06 Testabilidade**: suíte rápida sem Docker (SQLite + fakes); E2E real opt-in (`pytest -m e2e`).
- **RNF-07 Simplicidade**: padrão em camadas do FastAPI; integrações isoladas em funções simples (`fila.enfileirar_analise`, `analisar`); sem repository nem hexagonal.
- **RNF-08 Schema versionado**: tabelas criadas **somente** por migrações Alembic (`alembic upgrade head`); migração inicial cria `titulos`; models e migrações sempre sincronizados; `downgrade base` funciona.
- **RNF-09 API documentada**: Swagger UI em `/docs`, ReDoc em `/redoc` e contrato em `/openapi.json`; toda operação com resumo, descrição e respostas de erro (`404`, `422`, `500`, `503`) no envelope unificado `ErrorResponse`; campos dos schemas com descrição e exemplo válido; o `HTTPValidationError` padrão do FastAPI não aparece (a API não responde nesse formato).
- **RNF-10 Deploy de demonstração**: IaC em `deploy/aws` (CloudFormation) sobe uma única instância com o mesmo `docker compose`; custo mínimo (`t4g.small`, sem RDS/NAT/ALB); só a porta 80 aberta, sem SSH (acesso por SSM); senha do banco no Parameter Store; script `deploy.sh` com `up`, `deploy`, `status`, `logs`, `stop`, `start`, `destroy`.

## 9. Matriz de rastreabilidade
| Requisito | Testes |
|---|---|
| RN-01 | `unit/test_cnpj.py`, `unit/test_schemas.py` |
| RF-02, RN-02, RN-03, RN-06 | `unit/test_schemas.py`, `integration/test_api_post_titulos.py` (parametrizado) |
| RF-03 | `unit/test_models.py`, `integration/test_api_post_titulos.py` |
| RF-04 | `test_api_post_titulos.py::test_enfileira_somente_depois_do_commit` |
| RF-05 | `test_api_post_titulos.py::test_post_valido_retorna_202…` |
| RF-06, RN-04 | `unit/test_analise_credito.py`, `integration/test_processar_titulo.py`, `integration/test_task_celery.py` |
| RN-05 | `test_processar_titulo.py` (idempotência, compare-and-set, sem transação aberta) |
| RF-07 | `integration/test_api_get_titulos.py` |
| RF-08, RNF-03 | `unit/test_logging.py`, `integration/test_erros_globais.py`, `test_api_post_titulos.py` (log sem CNPJ) |
| RF-09 | `test_erros_globais.py::test_health_retorna_ok` |
| RNF-02 | `unit/test_fila_e_celery.py` |
| RNF-05, RNF-04 | `infra/test_docker_compose.py` |
| RNF-08 | `infra/test_migrations.py`, `infra/test_docker_compose.py` (API roda `alembic upgrade head`) |
| RNF-09 | `integration/test_openapi.py` |
| RNF-10 | `infra/test_deploy_aws.py` |
| Fluxo completo | `integration/test_fluxo_completo.py`, `e2e/test_e2e_compose.py` |

## 10. Critérios de aceite do MVP
1. `uv run pytest` verde (≈105 testes), cobertura ≥ 90%.
2. `docker compose up -d --build` + `uv run pytest -m e2e` verde.
3. Demo manual: `POST` devolve 202 em < 200 ms; `GET` imediato mostra `PENDENTE`; ~5 s depois mostra `APROVADO`/`REJEITADO`.
4. Derrubar o Redis (`docker compose stop redis`) e fazer `POST` ⇒ `503 FILA_INDISPONIVEL` sem vazar detalhes.
