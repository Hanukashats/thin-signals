# ADR-008: Implementation path without model training + SourceCraft hosting

Дата: 2026-09-18. Статус: **accepted**. LivingSet revision **7.1**.  
Parent: ADR-007 (Living/GoAll), ADR-006 (goal_control).

## Контекст

Оператор зафиксировал:

1. **Обучение модели** остаётся в плане только как **опциональный** контур. MVP и ближайшие волны реализуются за счёт **логики, skills, plugins и готовых frameworks** с адаптацией под Thin Signals — не fine-tuning / не обязательный sklearn-классификатор.
2. Git-хостинг проекта — **SourceCraft** (Yandex), аналог GitHub; агентский доступ через SEC SSH (`id_ed25519_sourcecraft`) и PAT для API/CLI.
3. Из развилки планирования (после docs-only P0) берём следующие два направления bootstrap: **скелет репо + связность LivingSet** и подготовка к **GoAll-исполнению** (не полный product runtime в этом ADR).

## Решение

### A. Implementation path

- Critical path: frozen LLM + harness + evidence ledger + P01–P18 + adapted skills/plugins (radar, POL branches, GoalOps contracts, RuntimeAdapter).
- `tz.classifier` / обучение модели: **deferred optional** — не блокирует P1–P4 и сдачу, пока нет отдельного operator escalate. Eval (TZ-02) строится на правилах/gates/ablation harness, не на «обученной модели» как обязательстве.
- Не заявлять соответствие пункту ТЗ «обучение» без явного включения optional-контура или ответа организаторов.

### B. SourceCraft

- Canonical remote: SourceCraft (`git@ssh.sourcecraft.dev:<org>/<repo>.git`).
- Auth для агентов: `D:\WORK\SEC\id_ed25519_sourcecraft` (+ `.pub` в UI https://sourcecraft.dev/me/ssh). Signing key в SEC на будущее (`id_ed25519_sourcecraft_sign`).
- API/CLI: Personal Access Token → канон SEC **`SOURCECRAFT_API_PAVEL.txt`** (env `SOURCECRAFT_TOKEN`); путь зафиксирован в LivingSet `docs/ops/secrets.paths.yaml`. **Не** коммитить значение, **не** AgentMemory.
- CLI: `src` (install + `src auth setup`). Создание репо: `src repo create <org> --slug …`.

### C. Bootstrap после P0 (из «вторых» опций планирования)

1. Инициализировать git в `1/`, remote SourceCraft, initial push LivingSet.
2. Добавить тонкий скелет: `schemas/` stubs, `scripts/check_living_links.py` (связность ID), `.gitignore`, опционально `.sourcecraft/ci.yaml` позже.
3. Затем GoAll P1: inventory → `backend.reuse` → W1a.

## Последствия

- W5b-classifier не в критическом пути хакатона.
- PAT path известен (`SOURCECRAFT_API_PAVEL.txt`). Для create/push нужен org slug (или default org после `src auth`).
- LivingSet revision → **7.1**.

## Приёмка

- forks: `implementation.path` decided; `tz.classifier` deferred optional; `hosting.sourcecraft` decided.
- CONCEPT/ARCHITECTURE/plan/STATUS обновлены.
- Access note без секретов: `docs/ops/SOURCECRAFT.md`.
- Репозиторий создан и LivingSet запушен **или** STATUS фиксирует UNRESOLVED + точный next trigger (PAT/org).
