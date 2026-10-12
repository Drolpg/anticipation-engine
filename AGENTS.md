# AGENTS.md — convenções para contribuição (humana ou automatizada)

Projeto: **Motor de Antecipação de Recebíveis** (API FIDC mock), escrito como código de produção financeira.

## Antes de qualquer coisa
1. Leia `docs/00-constitution.md`, `docs/01-spec.md`, `docs/02-plan.md` e a tarefa atual em `docs/03-tasks.md`.
2. A **spec é a fonte da verdade**. Se o código e a spec divergirem, pare e avise — não "conserte" em silêncio.

## Fluxo obrigatório (SDD + TDD)
- Trabalhe **uma tarefa por vez** (`M0-T1`, `M2-T3`...), na ordem de `docs/03-tasks.md`.
- Os testes em `tests/` **já existem e são o critério de aceite** (fase RED). Seu trabalho é fazê-los passar (GREEN) e depois refatorar mantendo-os verdes.
- **Nunca edite arquivos em `tests/`, `pytest.ini` ou `docs/01-spec.md` para fazer algo passar.** Se achar que um teste está errado, explique por quê e espere decisão do mantenedor.
- Rode primeiro o teste alvo da tarefa (`uv run pytest <arquivo>`), depois a suíte inteira (`uv run pytest`) e `uv run ruff check .` antes de dizer que terminou.

## Stack (não adicionar nada fora dela sem perguntar)
FastAPI · Pydantic v2 (+ pydantic-settings) · SQLAlchemy 2.x **síncrono** + psycopg 3 · PostgreSQL · Celery + Redis · Docker/Compose · Pytest · uv · Ruff.
Removidos do projeto: `django`, `boto3`.

## Convenções rápidas
- Dinheiro é sempre `Decimal` / `Numeric(18,2)`. **Nunca `float`.**
- Camadas: `api` → `services` → `models`/`db`; `worker` → `services`. `services` não importa FastAPI nem Celery em import-time. `api` não contém regra de negócio.
- **Simplicidade**: padrão em camadas do FastAPI. **Não criar** hexagonal/portas, repository, interfaces/Protocols, pasta `adapters/` nem container de DI. As integrações (`services/fila.py`, `analisar()`) são funções simples. Se o repositório atual tiver algo disso, simplifique na tarefa M0-T4.
- Logs: `logging` padrão com `extra={...}`; mensagens são chaves estáveis (`titulo_recebido`), nunca frases livres; **nunca logar CNPJ**.
- Erros ao cliente seguem o envelope `{"error": {"code", "message", ...}}` — nunca stack trace, nunca texto de exceção interna.
- Segredos só via variáveis de ambiente/`.env` (que não vai para o git).
- Commits no padrão Conventional Commits, um por ciclo verde (`feat(titulos): ...`, `test: ...`, `chore: ...`).

## Ao terminar uma tarefa, responda com
1. Arquivos criados/alterados. 2. Comando(s) rodado(s) e resultado. 3. Decisões não óbvias em até 5 linhas (explique o "porquê"). 4. Qualquer divergência da spec encontrada.
