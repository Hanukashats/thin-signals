# Adversarial review evaluation — replay + sealed holdout

Dataset `review-eval-0.1` · fixture `review-fixtures-0.1` · frozen code `9f3a1398fc3a82bb024e81d1c72e4fadb46eb4fc`.

| split/path | P | R | false promote | evidence-less | unresolved | coverage | stable | fixture ms | tokens | cost USD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| replay/baseline | 0.4286 | 1.0000 | 4 | 1 | 1 | 0.7143 | 1.0000 | 0 | 0 | 0.000000 |
| replay/proposed | 1.0000 | 1.0000 | 0 | 0 | 0 | 1.0000 | 1.0000 | 320 | 4800 | 0.032000 |
| replay/no_defender | 1.0000 | 0.3333 | 0 | 0 | 0 | 1.0000 | 1.0000 | 240 | 3600 | 0.024000 |
| replay/no_control | 1.0000 | 0.3333 | 0 | 0 | 0 | 1.0000 | 1.0000 | 240 | 3600 | 0.024000 |
| holdout/baseline | 0.4286 | 1.0000 | 4 | 1 | 1 | 0.8571 | 1.0000 | 0 | 0 | 0.000000 |
| holdout/proposed | 1.0000 | 1.0000 | 0 | 0 | 0 | 1.0000 | 1.0000 | 310 | 4650 | 0.031000 |
| holdout/no_defender | 1.0000 | 0.3333 | 0 | 0 | 0 | 1.0000 | 1.0000 | 230 | 3450 | 0.023000 |
| holdout/no_control | 1.0000 | 0.3333 | 0 | 0 | 0 | 1.0000 | 1.0000 | 230 | 3450 | 0.023000 |
| all/baseline | 0.4286 | 1.0000 | 8 | 2 | 2 | 0.7857 | 1.0000 | 0 | 0 | 0.000000 |
| all/proposed | 1.0000 | 1.0000 | 0 | 0 | 0 | 1.0000 | 1.0000 | 630 | 9450 | 0.063000 |
| all/no_defender | 1.0000 | 0.3333 | 0 | 0 | 0 | 1.0000 | 1.0000 | 470 | 7050 | 0.047000 |
| all/no_control | 1.0000 | 0.3333 | 0 | 0 | 0 | 1.0000 | 1.0000 | 470 | 7050 | 0.047000 |

## Interpretation

`baseline` is the pre-review base admission. `proposed` runs all four typed roles and the deterministic arbiter. Ablations omit defender or independent control and therefore remain fail-closed.

## Limitation

Это fixture-оценка контрактов и арбитра; она **не измеряет качество живых ответов модели**. Реальный поиск, число квалифицированных сигналов и сетевые расходы проверяются отдельным bounded canary.

Dataset SHA-256: `07371c1af0f2d8efa0d65d5d085012a635c186c87e2b891070fe7a1c66dbd175`
Result SHA-256: `b26922c55e9d3e100d6510387de53eaafd239aac04d87de37f93051a9616bf0a`
