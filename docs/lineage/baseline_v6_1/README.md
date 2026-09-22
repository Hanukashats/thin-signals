# Thin Signals — пакет реализации плана v6.1

Обновление шестого плана по результатам аудита Auto‑Goal, 17 сентября 2026.

Начать с `weak_signals_production_architecture_v6.md` (внутри версия 6.1), `docs/AUTO_GOAL_AUDIT.md`, затем `docs/CURSOR_HANDOFF.md` и `integration/ADR-006-AUTO-GOAL.md`.

- `data/`: прежняя разметка всех 100 строк, 18 предметных паттернов, шесть предикторов и результаты предыдущего аудита; файлы сохранены без изменений.
- `reference/`: прежний пример предметных gates; не production backend.
- `integration/`: совместимый research manifest, ADR и 18 требований приёмки. Реализация planned, продуктовая приёмка не выполнена.
- `audit/`: воспроизводимые пробы Auto‑Goal, результаты и upstream test log. AG07 — positive control; остальные записи различают дефекты, ограничения и предметное несоответствие.
- `release.json`, `manifest.sha256`: происхождение и целостность этого handoff.

Никакой framework не установлен; сервер Agispace-backend этим пакетом не изменён. Из Auto‑Goal переносим механизмы в существующий PG-backed domain; отдельный файловый daemon не является runtime-контроллером проекта. Fine-tuning остаётся вне критического пути.
