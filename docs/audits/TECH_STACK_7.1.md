# Техстек LivingSet 7.1 — функция и зачем

Источник: `ARCHITECTURE.md`. Не развёрнутый сервис — спецификация.

| Компонент | Функция | Зачем |
|---|---|---|
| Python 3.12 + FastAPI + Pydantic | HTTP API, typed contracts | Backend запросов и run state |
| SQLAlchemy / Alembic | ORM, миграции | Схема ledger |
| PostgreSQL + pgvector + FTS | SoT фактов, векторы, полнотекст | Документы, claims, tenants, гибридный поиск |
| S3 / object store | Сырые файлы | Immutable snapshots |
| Neo4j | Проекция графа из PG | Обход связей; не второй SoT. На сервере может не быть — тогда defer |
| Procrastinate + PG | Очередь jobs | Ingest, retry/cancel |
| Hermes + RuntimeAdapter | Агентный исполнитель | Skills; OpenCode fallback |
| goal_control в domain | Цели, ревизии, verifier | Без Auto-Goal daemon |
| Frozen LLM (allowlist) | Извлечение claims | Без fine-tuning |
| BGE-M3 / TEI через LiteLLM | Embeddings | Retrieval; pin model/dim |
| BERTopic | Пакетные темы | Не обязательный входной фильтр |
| NumPy / SciPy | Арифметика | Проценты не из LLM |
| Skills: radar, POL, GoalOps | Предметные ветки | P01–P18, CONTINUE/SKIP/JUMP/EXIT |
| React + Refine + Ant Design | UI | Карточки, фильтры |
| ECharts / Cytoscape / Tiptap | Ряды, граф, отчёт | Русская выдача |
| Docker Compose + OIDC | Деплой | Стенд жюри |
| SourceCraft | Git | Канон репозитория |

Не в MVP: Redis, Kafka, K8s, Temporal, вторая vector DB, LoRA.  
Обучение модели — optional (ADR-008).
