# Frozen scoring replay — rules 0.1 → 0.2

Evaluation status: **VALID**.

Replayed **170** stored rows from `rules-0.1` through `rules-0.2`.

| split/rules | n | accuracy | P | R | F1 | FP |
|---|---:|---:|---:|---:|---:|---:|
| train/rules-0.1 | 75 | 0.9333 | 0.9184 | 0.9783 | 0.9474 | 4 |
| train/rules-0.2 | 75 | 0.9333 | 0.9184 | 0.9783 | 0.9474 | 4 |
| holdout/rules-0.1 | 95 | 0.9474 | 0.9455 | 0.9630 | 0.9541 | 3 |
| holdout/rules-0.2 | 95 | 0.9474 | 0.9455 | 0.9630 | 0.9541 | 3 |
| all/rules-0.1 | 170 | 0.9412 | 0.9327 | 0.9700 | 0.9510 | 7 |
| all/rules-0.2 | 170 | 0.9412 | 0.9327 | 0.9700 | 0.9510 | 7 |

## Regression checks

- Baseline reproduction mismatches: **0**.
- Changed labels: **0**.
- Confidence decreases / increases: **0 / 0**.

## Limitation

Это замороженный replay сохранённых extraction-результатов. Он проверяет только формулу и не повторяет живой поиск или ответы модели; живой поиск проверяется отдельным bounded canary.

Records SHA-256: `042aab83a94926a6e20767118a93882da1dad715c17167e33d887a580bb71ab7`
Result SHA-256: `fc08036e6e73359e7b99cd39a5e90ffab216938dfc86d779b9d5e9fa9dcce003`
