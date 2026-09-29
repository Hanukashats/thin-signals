# Readable scientific typography

Delivery package date: 2026-09-29.

This is an analyst workbench for reading evidence in Russian and English.
The established dark palette and three-panel hierarchy remain the visual
contract. Its scientific character comes from quiet editorial headings and
precise numeric alignment, not from monospaced paragraphs or decoration.

## Decision

Use **Source Sans 3** for controls, evidence, labels and metrics: 16 px base,
regular text, semibold emphasis, 1.5 line height. Use **Source Serif 4 Semibold**
only for headings and the product name. Metrics stay sans-serif with tabular
figures; technical identifiers retain the framework's code face. Paragraphs
remain left aligned; no extra all-cap labels or tracking are introduced.

The previous CSS named both families without providing their files. The
production browser had neither registered and used platform fallbacks. The
change makes the existing intended design consistent across devices rather
than introducing a new visual direction.

## Delivery and licensing

The unmodified official Adobe WOFF2 assets include Cyrillic and Latin. Native
Streamlit static serving supplies them from `ui/static/fonts/` on the same
origin; the existing theme stylesheet declares `@font-face` with `swap`, without
a Google Fonts/CDN request or inline base64 font payload.
The static directory contains only public font assets/licenses; no runtime
credentials or private data. Exact sources, SHA-256 and OFL licenses are
recorded beside the fonts. Total font payload is about 422 kB before HTTP
compression. Missing network fonts retain readable platform fallbacks.

Official sources:

- https://github.com/adobe-fonts/source-sans/tree/3.052R
- https://github.com/adobe-fonts/source-serif/tree/4.005R
- Native static serving verified against installed Streamlit 1.64.0. Its
  advertised `theme.fontFaces` configuration did not register browser faces in
  the initial runtime probe; explicit CSS declarations in the existing theme
  work across selected framework themes and are verified in the browser.

The organizer's presentation template requires Montserrat. Presentation
typography follows that requirement; the website families are not substituted
into its first five prescribed slides.

## Acceptance

Browser verification must show loaded local faces for Cyrillic, metrics in
Source Sans 3, readable cards/controls at desktop and 390 px mobile widths,
visible keyboard focus and no page-wide horizontal overflow. Public production
login and a separate authenticated staging workbench are recorded independently;
a staging login never counts as production authentication.
