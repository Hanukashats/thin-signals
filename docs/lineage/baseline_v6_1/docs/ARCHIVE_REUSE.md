# Аудит переиспользования

Основание: ZIP пользователя от 2026-09-17, SHA256 в data/archive_integrity.json. Исходные документы и сторонние пакеты не перепакованы сюда: используйте оригинальный архив с сохранением provenance и лицензий. Пакет не является новым установленным skill/plugin.

## Канонические пути в исходном ZIP

| Актив | Путь от корня исходного архива | Решение |
|---|---|---|
| Radar plugin | `03_READY_PLUGIN/agispace-opportunity-radar/` | Основной методический донор; готовая упаковка для агента, но не backend |
| POL 1.2.1 | `02_EXPANDED_ARCHIVES/S021_product-opportunity-lab-MASTER-v1.2.1/product-opportunity-lab-MASTER-v1.2.1/source/` | Адаптивные правила, conditional commercial branches; simulator не переносить без исправлений |
| GoalOps | `02_EXPANDED_ARCHIVES/S031_goalops-universal-skill-v0.1/goalops-universal-skill-v0.1/` | Goal/task/evidence/ADR contracts для разработки |
| Trend Radar | `02_EXPANDED_ARCHIVES/S039_Agispace_Trend_Radar_Package/Agispace_Trend_Radar_Package/` | Корпус, методика, карточки, источник/coverage; не обнаружен готовый runtime в этом пакете |
| Текущая база | `04_PROJECT_GUIDE/CURRENT_BASELINE_RU.md` | История согласованных решений; v6 заменяет конфликтующие правила |
| Карта возможностей | `04_PROJECT_GUIDE/CAPABILITY_MAP_RU.md` | Справочник направлений повторного использования, а не live inventory |
| Восстановленный Science/Supply | `05_HISTORY_AND_RECONSTRUCTION/SCIENCE_SUPPLY_RADAR_RECOVERED_RU.md` | Донор понятий, статус reconstructed сохранять |

## Что можно брать целиком

В исследовательской среде можно использовать готовый набор radar instructions/reference files как методическую базу с контекстом задачи. Уже применён доступный agispace-opportunity-radar skill. Это не утверждение об установке архива на сервер. Сохранить readme/provenance, зафиксировать hash, подключить только нужные инструменты.

В продукт нельзя без адаптации переносить весь decision vocabulary: `PRODUCTION BUILD` означает готовность строить бизнес-решение, а не подтверждённость технологического сигнала. E0–E4 evidence и R0–R4 opportunity readiness не заменяют TRL/adoption maturity.

Исходные JSON templates полезны как примеры, но не выполняют роль JSON Schema и не гарантируют межобъектную целостность. Валыдация предметных данных принадлежит domain service.

## Проверенные контрпримеры

data/donor_checks.json содержит результаты прямого вызова функций двух исходных скриптов. Оригиналы не редактировались. Проверки демонстрируют ограничения структуры, а не качество исследовательских выводов или эффективность всего проекта.

1. Radar: пустые claims + R4 + произвольный PASS без evidence → errors=[] и warning об empty ledger.
2. Radar: depends_on между nonexistentA и nonexistentB → errors=[], нет проверки entities.
3. POL route: decision_deadline=True, info_improvement_unavailable=True, hard_fail=True → FORCE_DECISION, не critical failure route.

В reference/policy.py приоритет изменён: unresolved availability/fatal/critical claims обрабатываются до deadline shortcut; UNKNOWN не является PASS. Пример остаётся частичным, не обрабатывает URL-fetching, аутентификацию и настоящий фактчек.

## Важная поправка к Trend Radar

Методика требует валидный количественный библиографический ряд для численной emergence-компоненты. Это полезное ограничение индекса, но не универсальный критерий существования сигнала: новый страховой полис, design-in, работающая установка или присуждённый грант могут быть существенным изменением без роста arXiv. В v6 отдельные качественные ветки не получают выдуманную численную динамику; пригодность для основного списка определяют evidence gates.

## Отложено

Исторические версии навыков, эволюционные R&D-пакеты и сложные многоагентные топологии не устанавливаются одним набором. Не обнаружено оснований считать число файлов количеством независимых скиллов. Для внешней продажи выполнить dependency/license audit точных pinned versions; данный разбор не является юридическим заключением о лицензиях всех исторических вложений.
