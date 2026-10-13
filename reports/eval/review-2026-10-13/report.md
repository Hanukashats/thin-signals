# Adversarial review evaluation — replay + sealed holdout

Dataset `review-eval-0.2` · fixture `review-fixtures-0.2` · frozen code `9f3a1398fc3a82bb024e81d1c72e4fadb46eb4fc` · arbiter `review-arbiter-0.2`.

| split/path | P | R | exact | overpromote | false promote | evidence-less | unresolved | coverage | stable | fixture ms | tokens | cost USD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| replay/baseline | 0.4286 | 1.0000 | 0.3750 | 5 | 4 | 7 | 2 | 0.0000 | 1.0000 | 0 | 0 | 0.000000 |
| replay/proposed | 1.0000 | 1.0000 | 1.0000 | 0 | 0 | 0 | 0 | 1.0000 | 1.0000 | 320 | 4800 | 0.032000 |
| replay/no_defender | 0.0000 | 0.0000 | 0.5000 | 0 | 0 | 0 | 0 | 1.0000 | 1.0000 | 240 | 3600 | 0.024000 |
| replay/no_control | 0.0000 | 0.0000 | 0.5000 | 0 | 0 | 0 | 0 | 1.0000 | 1.0000 | 240 | 3600 | 0.024000 |
| holdout/baseline | 0.4286 | 1.0000 | 0.3750 | 5 | 4 | 7 | 2 | 0.0000 | 1.0000 | 0 | 0 | 0.000000 |
| holdout/proposed | 1.0000 | 1.0000 | 1.0000 | 0 | 0 | 0 | 0 | 1.0000 | 1.0000 | 310 | 4650 | 0.031000 |
| holdout/no_defender | 0.0000 | 0.0000 | 0.5000 | 0 | 0 | 0 | 0 | 1.0000 | 1.0000 | 230 | 3450 | 0.023000 |
| holdout/no_control | 0.0000 | 0.0000 | 0.5000 | 0 | 0 | 0 | 0 | 1.0000 | 1.0000 | 230 | 3450 | 0.023000 |
| all/baseline | 0.4286 | 1.0000 | 0.3750 | 10 | 8 | 14 | 4 | 0.0000 | 1.0000 | 0 | 0 | 0.000000 |
| all/proposed | 1.0000 | 1.0000 | 1.0000 | 0 | 0 | 0 | 0 | 1.0000 | 1.0000 | 630 | 9450 | 0.063000 |
| all/no_defender | 0.0000 | 0.0000 | 0.5000 | 0 | 0 | 0 | 0 | 1.0000 | 1.0000 | 470 | 7050 | 0.047000 |
| all/no_control | 0.0000 | 0.0000 | 0.5000 | 0 | 0 | 0 | 0 | 1.0000 | 1.0000 | 470 | 7050 | 0.047000 |

## Interpretation

`baseline` is the pre-review base admission. `proposed` runs all four typed roles and the deterministic arbiter. Role-removal ablations execute the same runner twice with the selected role unavailable; their typed failure, downstream validation, stability and resources are measured rather than reconstructed post hoc.

## Limitation

Это fixture-оценка контрактов и арбитра; она **не измеряет качество живых ответов модели**. Реальный поиск, число квалифицированных сигналов и сетевые расходы проверяются отдельным bounded canary.

Dataset SHA-256: `acf1bd3b7c19f7602a5eb4bf07e2e2d77aef30a5e1513378e7102f570ca37347`
Result SHA-256: `66de648ca54cfd9b33e405a720f7dec00051d409f0c18f42f45a8cd19cc1e0eb`
