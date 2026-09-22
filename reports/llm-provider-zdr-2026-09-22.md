# LLM-провайдер: OpenRouter ZDR — выбор модели (2026-09-22)

Основание: организатор (Светлана, чат 22.09) разрешил OpenRouter при включённой защите данных и только ZDR-моделях, с описанием в архитектуре. Fork `llm.provider` → `openrouter_zdr`.

## Что проверено (live, ключ бэкенда VM101)

- `GET /api/v1/endpoints/zdr` — 876 endpoint'ов, 309 моделей с ZDR.
- Из списка ТЗ на OpenRouter в ZDR доступны: `qwen/qwen3.6-35b-a3b`, `qwen/qwen3-235b-a22b-2507`, `openai/gpt-4.1`, `openai/gpt-5.6-luna`. YandexGPT и GigaChat на OpenRouter отсутствуют.
- Запрос с `provider: {zdr: true, data_collection: deny}` маршрутизируется только на ZDR-провайдеров; ответ содержит поле `provider`.

## Тест извлечения (RU-текст о раунде Multiverse Computing → JSON events/claims по схеме)

| Модель | Провайдер в ответе | strict `json_schema` под ZDR | Время | Токены | Качество |
|---|---|---|---|---|---|
| `qwen/qwen3.6-35b-a3b` | AkashML | да (`require_parameters: true` прошёл) | 2.8 s | 582 | 2 события, 3 claim'а; корректно разделил source_fact / vendor_statement, edge-заявление вендора → `unknown`, critical |
| `openai/gpt-5.6-luna` | Azure | да, но без `require_parameters` (Azure не декларирует параметр) | 9.6 s | 952 | 2 события, 6 claim'ов; аккуратнее по датам, статусы `supported` |
| `qwen/qwen3-235b-a22b-2507` | Novita | да, без `require_parameters` | 37 s | 923 | 3 события, 7 claim'ов; все пометил vendor_statement/verified — хуже различает вид утверждения |

## Решение

- Основная: `qwen/qwen3.6-35b-a3b` — в списке ТЗ, ZDR у 6+ провайдеров, самая быстрая и дешёвая ($0.10/$0.90 за 1M), strict structured output работает.
- Судья/эскалация (спорные карточки, финальный ТОП-15): `openai/gpt-5.6-luna` — в списке ТЗ, Azure ZDR, $0.20/$1.20.
- Fallback: `qwen/qwen3-235b-a22b-2507`; резерв `openai/gpt-4.1` (в 10 раз дороже).
- Не использовать: `openrouter/auto`, модели вне списка ТЗ, запросы без `zdr: true`.

## Ключ

Dev-копия проектного ключа бэкенда в `/opt/thin-signals/.secrets/openrouter_key` (лимит $100, остаток ~$84 на 22.09). Рекомендация оператору: отдельный ключ `thin-signals` в той же организации с включённым ZDR — для раздельного учёта расходов. Отдельный ключ из Agent Memory (`WORK_OPENROUTER_CLOUD_2026-09-19`, лимит $50) — для картинок/облачных задач, не для харнесса.
