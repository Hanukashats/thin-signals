# ARCHITECTURE.md — Thin Signals

Revision: **7.8** · Date: **2026-10-12** · Living contract
Основа: ADR-009 (harness-first) + ADR-010 (локальный research contour) + ADR-012 (reliability-first research loop); контракт объектов: `docs/PROCESSING_CONTRACT.md`; методика: `docs/METHODOLOGY.md`.

## 1. Обзор

```
[Запрос RU] -> словарь механизма + негативные термины
  -> Discovery: локальный SearXNG (+ arXiv / OpenAlex / Crossref / GitHub REST)
  -> Deep research (опционально): локальный GPT Researcher -> advisory artifact
  -> Ingest: snapshot (sha256, snapshots/) + Docling -> Document / Fragment
  -> Extract (LLM allowlisted, JSON schema): Entity / EvidenceEvent / Claim
  -> Dedup: TEI bge-m3 -> pgvector + правила (один анонс = одно событие)
  -> Gates: policy (порядок §3 METHODOLOGY) + F-P01..18 + M01..06
  -> Score: confidence + reason codes -> Decision
  -> Rank: ТОП-15 + watchlist + реестр исключений
  -> Streamlit RU UI / отчёт
```

Один PostgreSQL 16 (+pgvector) — единственный источник истины фактов, runs и решений. Граф связей — таблицы `nodes`/`edges` в PG.

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
| Search | SearXNG на VM232 `127.0.0.1:28088` | immutable image digest; JSON API; наружу не опубликован |
| Deep research | GPT Researcher v3.7.0 на VM232 `127.0.0.1:28000` | advisory only; exact upstream commit; OpenRouter ZDR request policy |
| Ingest | Docling Serve (VM101 :5001); fallback trafilatura/pdfminer | text + metadata + language |
| Browser fallback | Playwright MCP (VM101) | только при блокировке fetch |
| UI | Streamlit (RU) | три модуля: живые сигналы, отдельный рейтинг потенциала, поиск по архиву старых технологий; факты/гипотезы/проверки/источники |
| Ops | PostgreSQL в Compose; API/UI и research contour в persistent systemd; Caddy TLS на VM105 | loopback для app/research; только private ingress `VM232:18443` |
| Git | SourceCraft (канон) + GitHub mirror (сдача) | секреты только в `.secrets/` |

Статус прогона версионирован отдельно от метки сигнала: `succeeded`,
`degraded`, `failed`. Последний завершённый прогон виден оператору даже при
ошибке; отказ всех discovery-коннекторов даёт `failed`, частичный отказ или
незавершённый countersearch — `degraded`. Ни один из этих статусов не является
оценкой перспективности технологии.

Wide-run использует `retrieval-0.4`: хеш версии, порядка theme ID и хешей
запросов входит в родительский retrieval fingerprint без публикации исходных
строк. DOI и URL служат совместными alias при глобальной склейке: отсутствие
DOI у одной из копий и повтор URL внутри ответа не создают новое событие.
Два разных явных DOI не склеиваются только из-за общего URL; DOI-less запись
при нескольких конфликтующих DOI остаётся отдельной неоднозначной группой.
Сравнение с итоговой карточкой использует полный набор alias группы до выбора
одного представителя, поэтому результат не зависит от порядка тем.
Наблюдения одного события в разных темах считаются один раз, а source-backed
дочернее исключение сохраняется один раз, если это событие не представлено в
итоговом списке/реестре читателя.

GPT Researcher подключается только флагом, выключенным по умолчанию. Адаптер
делает один синхронный запрос к pinned API в унаследованном дедлайне, отбрасывает
сгенерированный отчёт и повторно скачивает его URL как недоверенные leads.
Проверка запрещает non-HTTP, credentials, loopback/private DNS и приватные
redirect-цели; транспорт подключается к уже проверенному числовому IP без
второго DNS lookup, а абсолютный дедлайн действует и на медленный stream.
Текст/размер ограничены. Превышение заявленного post-run cost
fail-closed до передачи lead в harness. Наружу выходят только research id,
стоимость, счётчики и хеши artifact path; не prose, prompt или локальный путь.

Обычный live path повторно получает не более `TS_EVIDENCE_FETCH_LIMIT`
уникальных источников на тематический прогон, primary-first и внутри общего
deadline. Raw body хранится только content-addressed snapshot; публичная карточка
получает bounded fragment, content/fragment hash и `sha256:` reference.
`checklist-v19` повторно хеширует сохранённый blob и капит `verified` до
`supported`, если blob/attestation отсутствует либо ссылка ведёт лишь на snippet
или non-primary fragment. Старые записи без нового provenance не переписываются.

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
- **TS-INV-04** Модельные роли только предлагают типизированные claims/objections/rebuttals; итоговый `PROMOTE|REFRAME|HOLD|REJECT` выдаёт детерминированный арбитр. Ошибка роли или нерешённое критическое возражение дают `HOLD`.

Контур `researcher → critic → defender → control critic` встроен в narrow и
wide запуски за выключенным по умолчанию флагом. Каждая роль получает одинаковый
лимит и один и тот же snapshot-attested evidence bundle. В PostgreSQL сохраняются
только типизированные действия, хеши, provenance и учёт ресурсов; prompts,
цитаты и скрытое рассуждение в публичный trace не попадают.
Structured decoding ограничивает ссылки ID, реально существующими в текущем
раунде. Для defender и control critic вход дополнительно содержит типизированные
`reference_bindings`: существующие/новые доказательства и точную пару
objection/rebuttal. Control critic может цитировать только доказательства своей
пары, а `resolved` обязан включить все доказательства принятого rebuttal.
Один PostgreSQL session advisory lock охватывает reservation, четыре роли и
финализацию на одном pinned connection: другой процесс ждёт канонический
результат, pool не требует второго соединения, а после смерти владельца оставшийся
`running` закрывается как `HOLD`. Сетевой deadline является отменяемым жёстким
wall-clock пределом для DNS, registry, response body и completion. DNS выполняется
внутри отменяемого async-запроса на ограниченном executor; исходное доменное имя
сохраняется, поэтому HTTPX штатно обрабатывает несколько адресов, proxy bypass и
TLS/SNI, а отменённый lookup не порождает поздний POST.

Evaluation не обращается к модели или сети. `score-replay` реконструирует
FeatureVector из 170 сохранённых записей и требует точного совпадения v0.1 перед
сравнением v0.2; несовпадение помечает оценку invalid и даёт ненулевой exit.
`review-eval` исполняет реальный runner/`review-arbiter-0.2` поверх
детерминированных typed fixtures: 8 frozen replay и 8 структурно отличных
sealed holdout, плюс дважды исполняемые `no_defender`/`no_control` role-unavailable
ablations. Arbiter требует attested primary evidence для каждого критического
claim и не менее двух независимых primary-origin для `PROMOTE`/`REFRAME`;
нерелевантный non-critical claim этот gate не закрывает. Safety-метрики выводятся
из typed outputs/provenance, а не fixture labels. Resolved control finding
обязан назвать точный rebuttal и проверить используемые им evidence; replacement
критического claim остаётся critical и не может иметь статус unknown. Gold не
входит в путь решения.
Живой поиск, latency провайдера и yield проверяются только canary.

## 5. Сеть и reuse (ADR 007 бэкенда)

На VM232 продукт обращается к SearXNG по loopback, а GPT Researcher — к нему
по Docker DNS. Сервисы одного хоста не ходят через NetBird/OpenWrt. Исходящий
трафик контейнеров использует один host sing-box; проверенный IP совпадает с
host egress. Публичный путь: домашний edge → Caddy на VM105 → приватный
`VM232:18443` → loopback UI. NetBird hub VM233 остаётся отдельным control plane
и не участвует в этом reverse-proxy пути.

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
