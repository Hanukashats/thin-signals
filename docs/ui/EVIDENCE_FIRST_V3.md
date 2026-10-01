# Evidence-first UI v4 — three-module workbench

Date: 2026-10-01. Concept/material date: 2026-09-29. Figma:
`RbbhSTdppIVib4AUkGKvia`, page `6:8`, editable desktop frame `41:178`
(`Desktop / Three modules v4 · Deep Space`). Earlier frames remain unchanged as
lineage; `30:97` is the visual ancestor that was shown before implementation.

## Logo decision

- Supplied source lockup is preserved unchanged as
  `ui/assets/agi-space-logo-metallic-2026-10-01.jpg`, SHA-256
  `b226984701d68a44fa9fa245ffbf061c9f79673076a444b896070b0472a7a1cd`.
- The UI uses `agi-space-logo-transparent.png`; pixels outside the mark are
  transparent, so there is no black rectangular plate behind it.
- `agi-space-mark.png` is the transparent square favicon. Compressing the full
  wordmark into a favicon would make it unreadable.
- Teal remains the action/evidence colour. Brand blue is not reused as a semantic success/warning state.

## Operator contract

- Run state, card verdict and evidence coverage are separate facts.
- `watchlist` is shown as “наблюдение”, never promoted by list position.
- Facts contain only available evidence fragments. Generated reach/application text lives under “Гипотезы”; rule/checklist state under “Проверки”; citations under “Источники”.
- Date fields are explicitly labelled as query context until a typed API filter exists.
- No inactive navigation or “create check” control is shipped without a backend action.

## Three modules

1. **Тонкие сигналы** — live query, admitted ranking and source-level evidence.
2. **Потенциал** — a separate deterministic review queue for scored observations
   below weak-signal status: near-watchlist exclusions [0.25, 0.35), or high-index
   watchlist observations [0.35, 0.60). The target gate is explicit. Only current
   checklist rows are ranked; historical results require a new run.
   Its 0–100 values are triage indices, never success or market probabilities.
3. **Новая жизнь** — reproducible lookup over the sealed 2026-09-29 research
   package: old barrier, changed constraint, first product, buyers, risk and
   source links. Search never rewrites the archived research ranking.

## Responsive and accessible behaviour

- Strong input boundary `#71868D`, visible 3 px keyboard focus ring, minimum 42 px buttons.
- Layout reflows at 1180, 900 and 700 px; the brand status chip hides before the title/logo.
- Production keeps system font fallbacks because no licensed Source Sans/Serif webfont bundle is stored in the repository.
