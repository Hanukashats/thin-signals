# Аудит: pgvector vs гибрид и reuse сервисов бэкенда

Дата: 2026-09-18. Оператор дал инвентарь VM. Решение не оформлено отдельным ADR — зафиксировано здесь для handoff. При внедрении: Architect → ADR-009 + LivingSet 7.2.

## pgvector

**Актуален**, если PostgreSQL остаётся SoT. Гибрид = PG FTS + pgvector + RRF, эмбеддинги с уже живого TEI через LiteLLM.

Qdrant сейчас не ставить: его нет в инвентаре, это второй store и sync. Открыть fork `search.vector_store` только после измеренного упирания P2.

Chroma Odysseus (:8100) — не product SoT (Line B).

## Рекомендуемые DECIDED (ещё не в forks.yaml)

| Fork (предложение) | Выбор |
|---|---|
| embeddings.runtime | LiteLLM → TEI `embedding-local` |
| search.hybrid | PG FTS + pgvector + RRF |
| ingest.tools | Docling + SearXNG + Playwright fallback |
| graph.neo4j | MINIMAL defer, если Neo4j нет на VM |

OpenViking: кэш/retrieval допустим; PASS/claim только после записи в PG.

## Сервисы — reuse / adapt / skip

| Сервис | Слушает / MCP | Функция | Для Thin Signals |
|---|---|---|---|
| Agent Memory 0.9.29 | :3111 · MCP stdio→HTTP | remember / lessons | **Dev-only**, не SoT сигналов |
| OpenViking 0.4.17 | :1933 /mcp | знания, retrieval | **Adapt** осторожно; факты в PG |
| LiteLLM 1.98.0 | :4000 /v1 | модели, embedding-* | **Reuse** |
| Graphify | :3847 /mcp | граф *кода* | **Dev-only** |
| Hermes 0.21.0 | :8642 health | агент, skills overlay | **Reuse** RuntimeAdapter |
| TEI | :8080 | embeddings | **Reuse** |
| omni-embed / infinity-mm | :8090 / :7997 | мультимодал | **Skip MVP** |
| Parakeet / Whisper / Speaches | STT/TTS | голос | **Skip** продукта |
| Docling Serve | :5001 | document ingest | **Reuse** |
| GPT Researcher | :8000 | длинный research | **Adapt** за adapter + budget |
| SearXNG Line A | :28088 | web search | **Reuse** |
| Playwright MCP + Browserless | :8931 / :3000 | браузер | **Reuse** fallback |
| Gatus / Caddy / AEM / NetBird | ops | доступ, мониторинг | **Reuse ops** |
| OpenMAIC / Odysseus+Chroma | Line B / UI | чужой стек | **Не SoT** |
| goal-kernel :8766 | GOAL vNext | donor | **Не** второй product controller |
| Telegram/Cursor/Codex operators | outbound | удалённая разработка | **Dev** |
| Funes / vpn-diag | lab | lab | **Skip** |

## Стыковка

```text
Запрос → domain API → jobs
  → SearXNG + Docling + (opt) Playwright / GPT-Researcher
  → LiteLLM + TEI
  → PG ledger + FTS + pgvector
  → P01–P18 + goal_control
  → Refine UI

Dev: AgentMemory + OpenViking + Graphify — не факты сигнала
```
