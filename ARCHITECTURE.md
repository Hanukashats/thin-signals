# ARCHITECTURE.md — Thin Signals

Revision: **7.8** · Delivery package date: **2026-09-29** · Living contract
Основа: ADR-009 (harness-first, сжатый стек, reuse VM101); контракт объектов: `docs/PROCESSING_CONTRACT.md`; методика: `docs/METHODOLOGY.md`.

## 1. Обзор

```
[Запрос RU] -> словарь механизма + негативные термины
  -> Discovery: SearXNG (+ arXiv / OpenAlex / Crossref / GitHub REST / Google Patents via SearXNG)
  -> Ingest: snapshot (sha256, snapshots/) + Docling -> Document / Fragment
  -> Extract (LLM allowlisted, JSON schema): Entity / EvidenceEvent / Claim
  -> Dedup: TEI bge-m3 -> pgvector + правила (один анонс = одно событие)
  -> Gates: policy (порядок §3 METHODOLOGY) + F-P01..18 + M01..06
  -> Score: confidence + reason codes -> Decision
  -> Rank: ТОП-15 + watchlist + реестр исключений
  -> Streamlit RU UI / отчёт
```

Один PostgreSQL 16 (+pgvector) — единственный источник истины фактов, runs и решений. Граф связей — таблицы `nodes`/`edges` в PG.

ADR-010 добавляет singleton `workspace`: FK на завершённый Run и descriptor
последнего архивного поиска. Run/Decision и публикация рабочего стола атомарны.
Сохранение архива проверяет revision; чтение не пишет. Внутренние fanout-темы не
публикуются. Возврат из кэша выбирает сохранённый Run без изменения его stats.
`GET /v1/workspace/latest` возвращает три модуля одним snapshot;
`POST /v1/workspace/archive` принимает query/families/expected_revision (409 при
конфликте). Версии и hash архива проверяются без пересчёта научных решений.

Демонстрационный сеанс живёт только в session_state: копия snapshot, различные
открытые Run ID, число архивных отправок и notice происхождения. Reset и открытие
примера не вызывают HTTP. Флаг repeated берётся из POST до GET проекции workspace.
Обычный вход сохраняет автозагрузку; демо подавляет её до явного выбора. Черновики
виджетов хранятся отдельно от временных ключей Streamlit и явно передаются клиенту.

## 2. Компоненты

| Слой | Выбор 7.2 | Граница |
|---|---|---|
| API / domain | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 + Alembic | typed contracts; команды идемпотентны по `idempotency_key` |
| Harness | Python state machine `ts/harness` (stages 0–11 из METHODOLOGY §5.3 донора) | run/step в PG; BackgroundTasks + lease/heartbeat; cancel |
| Scoring | `ts/scoring/policy.py` (адаптация `reference/policy.py`, F03 исправлен) + `rules-x.y.yaml` | детерминированно; LLM-числа не входят |
| Eval | `ts eval` CLI | адаптер CSV/JSON организаторов; P/R/F1; отчёт в `reports/` |
| SoT | PostgreSQL 16 + pgvector + FTS | documents, fragments, entities, events, claims, edges, observations, decisions, runs |
| Snapshots | `snapshots/<sha256>` на диске + `documents.blob_ref` | immutable; бэкап tar |
| LLM | OpenRouter, режим ZDR (см. §7), модели только из списка ТЗ | `provider` + `model_id` логируются в каждом ответе |
| Embeddings | TEI bge-m3 через LiteLLM `embedding-local` (VM101) | dim pinned; laptop-профиль: FTS без векторов |
| Search | SearXNG (VM101 :28088 или локальный контейнер) | JSON API; engines pinned |
| Ingest | Docling Serve (VM101 :5001); fallback trafilatura/pdfminer | text + metadata + language |
| Browser fallback | Playwright MCP (VM101) | только при блокировке fetch |
| UI | Streamlit (RU) | три модуля: живые сигналы, отдельный рейтинг потенциала, поиск по архиву старых технологий; факты/гипотезы/проверки/источники |
| Ops | PostgreSQL в Compose; API/UI в persistent systemd; Caddy TLS; вход через host accounts | разные DynamicUser, LoadCredential, loopback, без OIDC/tenant |
| Git | SourceCraft (канон) + GitHub mirror (сдача) | секреты только в `.secrets/` |

Не добавлять: Neo4j, S3, Procrastinate, Redis, Kafka, K8s, BERTopic, вторая vector DB, LoRA. Replacement matrix — `docs/plan/PLAN_7.2.md` §6.

## 3. Repo layout (целевой)

```
ts/                 пакет: api/, harness/, scoring/, connectors/, ingest/, eval/, ui/
ts/tests/           unit + сценарии из METHODOLOGY §8 и KNOWN_GAPS
alembic/            миграции schema v1
compose.yaml        pg (pgvector), api, ui; profiles laptop|vm101
reference/          policy.py + tests (v6.1, без правок)
donors/             radar 0.1.1, goalops 0.1, POL 1.2.1 (без правок, provenance в donors/README.md)
data/               registries, dataset_patterns_100, negatives_v1 (W2), source_trust.yaml
docs/               METHODOLOGY, EVAL, PROCESSING_CONTRACT, adr/, plan/, lineage/, audits/, ops/
reports/            eval_<date>.md, live-run receipts
```

## 4. Инварианты процесса (вместо goal_control 18 TS-AG)

- **TS-INV-01** Идемпотентный run: тот же запрос + `corpus_version` + `rules_version` → прежний `run_id`; шаг повторяется по `input_hash`.
- **TS-INV-02** Claim принимается только с `fragment_id` прочитанного snapshot; PASS gate без evidence невозможен (semantic validator, не структурный rc=0).
- **TS-INV-03** Статус run (`succeeded`) ≠ решение сигнала (`weak_signal|watchlist|mature|noise`); UI показывает оба раздельно.

## 5. Сеть и reuse (ADR 007 бэкенда)

На VM101 сервисы вызываются по loopback/Docker DNS (`http://127.0.0.1:28088`, `:5001`, `:4000`, `:8080`). С ноутбука — только через NetBird или laptop-профиль с локальными аналогами. Продуктовый API не получает operator-права backend и Docker socket.

## 6. Открытые развилки

`llm.provider` (ключи — operator gate). Закрыты в 7.2: `tz.classifier`, `backend.reuse`, `graph.neo4j`, `sources.epo_cordis`, `ui.stack`.

## 7. LLM-провайдер и защита данных (условие организатора, 2026-09-22)

Доступ к LLM — через OpenRouter API с включённой защитой данных: на уровне организации в OpenRouter включён режим Zero Data Retention и запрет обучения на данных; в каждом запросе передаётся `provider: {zdr: true, data_collection: deny}`, поэтому маршрутизация возможна только на endpoint'ы провайдеров, которые не хранят промпты и ответы. Используются только модели из списка ТЗ:

| Роль | Модель (id OpenRouter) | ZDR-провайдеры | Цена in/out, $/1M |
|---|---|---|---|
| Основная: извлечение фактов, разметка признаков P/M, резюме RU | `qwen/qwen3.6-35b-a3b` | DeepInfra, CoreWeave, Parasail, AkashML, SiliconFlow, Phala | 0.10 / 0.90 |
| Судья/эскалация: спорные карточки, финальный ТОП-15 | `openai/gpt-5.6-luna` | Azure | 0.20 / 1.20 |
| Fallback семейства Qwen (медленнее) | `qwen/qwen3-235b-a22b-2507` | DeepInfra, Nebius, Novita, Parasail | 0.09 / 0.55 |
| Резерв (дорого) | `openai/gpt-4.1` | Azure | 2.00 / 8.00 |

Автовыбор моделей (`openrouter/auto`) не используется. Ответ, чей `provider` не входит в `/api/v1/endpoints/zdr`, отбрасывается харнессом; `provider` и `model_id` сохраняются в `runs`. LLM не даёт числа для скоринга (§2) и не строит выдачу «из памяти» — только из snapshot'ов найденных источников.
