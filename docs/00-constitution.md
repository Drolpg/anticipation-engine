# 00 — Constituição do Projeto

Princípios que valem para **todas** as decisões. Em caso de dúvida, volte aqui.

## 1. Por que este projeto existe
Preparação prática para a vaga de Desenvolvedor Backend Python na Hope Asset (gestora de FIDCs). O que a vaga valoriza — e que este projeto precisa demonstrar de forma defensável em entrevista: **alta volumetria, estabilidade, integrações, tratamento de erros, correção financeira**.

Meta de aprendizado: o autor deve conseguir explicar **cada linha e cada decisão** em voz alta. Código que ele não consegue explicar é dívida, mesmo que passe nos testes.

## 2. Método: SDD + TDD
| Fase | Artefato | Quem lidera |
|---|---|---|
| Especificar | `docs/01-spec.md` | autor + Claude (revisão) |
| Planejar | `docs/02-plan.md` | autor + Claude |
| Quebrar em tarefas | `docs/03-tasks.md` | Claude |
| RED — testes que falham | `tests/**` | Claude escreve, autor lê e entende |
| GREEN — implementação mínima | `src/**` | autor com Antigravity |
| REFACTOR | `src/**` | autor com Antigravity, testes verdes |
| Validar | revisão do diff contra a spec | Claude |

Regras do método:
1. **Mudou o comportamento? Mude a spec primeiro**, depois o teste, depois o código.
2. Teste é critério de aceite. Não se altera teste para "fazer passar".
3. Um ciclo verde = um commit pequeno.
4. Cada requisito da spec tem ≥ 1 teste (matriz de rastreabilidade na seção 9 da spec).

## 3. Princípios de engenharia
- **Correção financeira antes de tudo**: `Decimal`/`Numeric`, nada de `float`; fronteiras de regra testadas no centavo.
- **Falhar de forma previsível**: todo erro tem código estável, status HTTP correto e log com contexto. O cliente nunca vê stack trace.
- **Idempotência**: fila entrega "pelo menos uma vez"; processar duas vezes a mesma mensagem não pode corromper nada.
- **Não bloquear**: a API responde rápido (202); trabalho lento vai para o worker.
- **Observabilidade desde o dia 1**: log estruturado em JSON, `request_id` ponta a ponta, `titulo_id` em todo log do domínio.
- **Segredos fora do código e do git**; banco e Redis nunca expostos ao host.
- **Simplicidade deliberada**: o autor precisa entender e construir tudo em ~2 dias. Sem async no ORM, sem microsserviços, sem hexagonal, sem abstrações "para o futuro". O que ficou de fora está listado e justificado no plano (seção "Fora do MVP").

## 4. Qualidade (Definition of Done de qualquer tarefa)
- [ ] Testes alvo da tarefa verdes; suíte completa verde (`uv run pytest`).
- [ ] `uv run ruff check .` e `uv run ruff format --check .` sem erros.
- [ ] Cobertura ≥ 90% (`uv run pytest --cov=anticipation_engine`).
- [ ] Nenhum segredo, CNPJ ou stack trace em log/resposta.
- [ ] Spec atualizada se algo mudou.
- [ ] O autor consegue explicar a decisão principal da tarefa.

## 5. Convenções
- Python ≥ 3.13 (ver plano §5), tipagem em todas as assinaturas públicas.
- Domínio em português (`Titulo`, `cnpj_sacado`, `StatusTitulo`) — espelha o vocabulário do negócio; infraestrutura em inglês (`get_db`, `celery_app`).
- Estrutura em camadas (ver plano). Dependência só aponta "para dentro": `api → services → models/db`. Sem hexagonal/portas/repository: simplicidade é requisito.
- Commits: Conventional Commits (`feat`, `fix`, `test`, `docs`, `refactor`, `chore`).
- Branch: `main` sempre verde; trabalho em `feat/<milestone>`.
