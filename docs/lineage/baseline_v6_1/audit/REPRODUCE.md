# Воспроизведение аудита Auto‑Goal

Использовать исходный архив `auto-goal-vnext-portable-v0.3.0-4e3257d8.tar.gz`, SHA256 `1f1f2aefefa205f7cafaf985dd58e124652882d7976c36ba11f9c30eb4e7cd55`. Исходники не продублированы в данном ZIP. В нём есть результаты и тестовый скрипт, который импортирует тестовый helper и запускает временный HTTP server на loopback.

После безопасной распаковки в отдельный каталог:

```bash
# Из каталога распакованного donor-пакета:
sh scripts/self-test.sh

# Из каталога этого handoff; аргумент заменить абсолютным путём к donor:
python audit/reproduce_findings.py /absolute/path/to/auto-goal-vnext-portable-v0.3.0-4e3257d8

python /absolute/path/to/auto-goal-vnext-portable-v0.3.0-4e3257d8/.cursor/skills/auto-goal/scripts/goal_constructor.py preview integration/thin-signals-research.manifest.json
```

Проверить синтаксис CLI preview по `--help`, если используется другая версия donor. Пробы пишут probe_results.json и verifier_empty_context.txt рядом со своим скриптом и останавливают тестовый server. Они не устанавливают daemon и не активируют существующие пользовательские цели.

Ожидается: 59 upstream tests PASS; 14 записей observed=true. Это **воспроизведение поведения исходной версии**, не утверждение о правильности поведения. AG07 — положительный контроль; AG11 — прямой storage-test stale snapshots, а не конкурентный HTTP race. После исправлений часть observed должна стать false — тогда пробы преобразуют в regression tests с новыми ожиданиями.

Полный audit report описывает границы каждой проверки. Фактическое измерение scientific quality и тесты production integration выполняются отдельно.
