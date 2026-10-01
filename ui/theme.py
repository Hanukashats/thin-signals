"""Approved AGI Space Deep Space treatment for the Streamlit operator viewer."""
from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path

import streamlit as st

LOGO_PATH = Path(__file__).with_name("assets") / "agi-space-logo-official.jpg"
METALLIC_LOGO_PATH = Path(__file__).with_name("assets") / "agi-space-logo-metallic-2026-10-01.jpg"
TRANSPARENT_LOGO_PATH = Path(__file__).with_name("assets") / "agi-space-logo-transparent.png"
FAVICON_PATH = Path(__file__).with_name("assets") / "agi-space-mark.png"

THEME_CSS = r"""
:root {
  color-scheme: dark;
  --ts-canvas: #0A0F14;
  --ts-rail: #0D171F;
  --ts-detail: #101B24;
  --ts-card: #111E27;
  --ts-selected: #123741;
  --ts-muted-surface: #14232D;
  --ts-border: #29424D;
  --ts-border-strong: #5B7782;
  --ts-ink: #EAF7F8;
  --ts-secondary: #A3BAC1;
  --ts-action: #31D7E6;
  --ts-action-strong: #0EAABC;
}

[data-testid="stAppViewContainer"] {
  background:
    radial-gradient(circle at 11% -8%, rgba(0, 229, 255, 0.13), transparent 32rem),
    radial-gradient(circle at 92% 16%, rgba(32, 92, 166, 0.10), transparent 28rem),
    var(--ts-canvas);
  color: var(--ts-ink);
}
[data-testid="stMain"] { background: transparent; }
[data-testid="stHeader"] { background: transparent; }
[data-testid="stSidebar"] { background: var(--ts-rail); border-right: 1px solid var(--ts-border); }
.block-container { max-width: 1540px; padding-top: 1.6rem; padding-bottom: 4rem; }
h1, h2, h3, [data-testid="stMetricValue"] {
  color: var(--ts-ink) !important;
  font-family: "Source Serif 4", Georgia, "Times New Roman", serif !important;
  letter-spacing: -0.018em;
}
p, label, button, input, textarea, [data-testid="stCaptionContainer"] {
  font-family: "Source Sans 3", "Segoe UI", Arial, sans-serif;
}
p, [data-testid="stCaptionContainer"] { color: var(--ts-secondary); }
label, [data-testid="stWidgetLabel"] p { color: var(--ts-ink) !important; }

.ts-brand {
  align-items: center;
  background: linear-gradient(115deg, rgba(13, 23, 31, 0.76), rgba(16, 27, 36, 0.42));
  border: 1px solid #29424D;
  box-shadow: 0 18px 45px rgba(0, 0, 0, 0.28);
  border-radius: 14px;
  display: grid;
  gap: 18px;
  grid-template-columns: 112px 1fr auto;
  margin: 0 0 22px;
  overflow: hidden;
  padding: 9px 18px;
  position: relative;
}
.ts-brand::after {
  background: linear-gradient(90deg, transparent 0%, #31D7E6 42%, #D9F6FA 67%, transparent 100%);
  bottom: 0;
  content: "";
  height: 2px;
  left: 0;
  position: absolute;
  right: 0;
}
.ts-brand img {
  background: transparent;
  border-radius: 8px;
  display: block;
  height: 84px;
  object-fit: contain;
  width: 112px;
}
.ts-brand__name { color: #F4F8F8; font: 700 23px/1.1 "Source Serif 4", Georgia, serif; }
.ts-brand__note { color: #A8C0C6; font-size: 13px; margin-top: 4px; }
.ts-brand__state {
  background: #12323A;
  border: 1px solid rgba(49, 215, 230, 0.26);
  border-radius: 999px;
  color: #BDEFF3;
  font-size: 13px;
  font-weight: 700;
  padding: 8px 13px;
  white-space: nowrap;
}

[data-testid="stVerticalBlockBorderWrapper"] {
  background: rgba(17, 30, 39, 0.90);
  backdrop-filter: blur(10px);
  border-color: var(--ts-border) !important;
  border-radius: 14px;
}
[data-testid="stMetric"] {
  background: var(--ts-detail);
  border: 1px solid var(--ts-border);
  border-radius: 12px;
  min-height: 112px;
  padding: 13px 15px;
}
[data-testid="stMetricValue"] {
  font-size: 1.3rem;
  line-height: 1.18;
  overflow-wrap: anywhere;
  white-space: normal;
}
[data-testid="stMetricLabel"] { color: var(--ts-secondary); }
[data-testid="stMetricValue"] [data-testid="stMarkdownContainer"],
[data-testid="stMetricValue"] p {
  overflow: visible;
  text-overflow: clip;
  white-space: normal;
}
[data-testid="stMetricDelta"] { color: var(--ts-action); }
[data-testid="stHorizontalBlock"] > [data-testid="column"] { min-width: 0; }
[data-testid="stRadio"] div[role="radiogroup"] {
  background: rgba(13, 23, 31, 0.86);
  border: 1px solid var(--ts-border);
  border-radius: 12px;
  display: flex;
  gap: 6px;
  margin: 0 0 18px;
  padding: 6px;
}
[data-testid="stRadio"] div[role="radiogroup"] label {
  border: 1px solid transparent;
  border-radius: 8px;
  min-height: 42px;
  padding: 8px 16px;
}
[data-testid="stRadio"] div[role="radiogroup"] label:has(input:checked) {
  background: var(--ts-selected);
  border-color: rgba(49, 215, 230, 0.45);
}
[data-testid="stRadio"] div[role="radiogroup"] label:has(input:checked) p {
  color: var(--ts-action) !important;
  font-weight: 750;
}
[data-testid="stExpander"] {
  background: var(--ts-card);
  border: 1px solid var(--ts-border) !important;
  border-radius: 12px !important;
}
[data-testid="stExpander"] summary, [data-testid="stExpander"] summary p {
  color: var(--ts-ink) !important;
}
[data-testid="stAlert"] { border-radius: 12px; }
[data-testid="stTabs"] [role="tablist"] { border-bottom-color: var(--ts-border); }
[data-testid="stTabs"] button { color: var(--ts-secondary); }
[data-testid="stTabs"] button[aria-selected="true"] { color: var(--ts-action); }
[data-testid="stTabs"] button[aria-selected="true"]::after { background: var(--ts-action); }
.stButton > button, .stDownloadButton > button {
  background: transparent;
  border-color: var(--ts-action-strong);
  color: var(--ts-action);
  border-radius: 9px;
  min-height: 42px;
}
.stButton > button[kind="primary"] {
  background: var(--ts-action);
  border-color: var(--ts-action);
  color: #041014;
}
.stButton > button[kind="primary"] p { color: #041014 !important; font-weight: 750; }
div[data-baseweb="input"] > div, div[data-baseweb="textarea"] > div,
div[data-baseweb="base-input"], textarea {
  background: #0D171F !important;
  border-color: var(--ts-border-strong) !important;
}
input, textarea { color: var(--ts-ink) !important; caret-color: var(--ts-action); }
input::placeholder, textarea::placeholder { color: #718991 !important; opacity: 1; }
button:focus-visible, a:focus-visible, input:focus-visible, textarea:focus-visible,
[tabindex]:focus-visible {
  outline: 3px solid #31D7E6 !important;
  outline-offset: 3px;
}
a { color: var(--ts-action) !important; }
hr { border-color: var(--ts-border); }
#MainMenu, footer { visibility: hidden; }

@media (max-width: 1180px) {
  .block-container { max-width: 100%; padding-left: 1.5rem; padding-right: 1.5rem; }
  .ts-brand { grid-template-columns: 96px 1fr auto; }
  .ts-brand img { height: 72px; width: 96px; }
}

@media (max-width: 900px) {
  .ts-brand__state { display: none; }
}

@media (max-width: 700px) {
  .block-container { padding: 1rem 1rem 3rem; }
  .ts-brand { gap: 10px; grid-template-columns: 74px 1fr; padding: 8px 10px; }
  .ts-brand img { border-radius: 7px; height: 58px; width: 74px; }
  .ts-brand__name { font-size: 18px; }
  .ts-brand__state { display: none; }
  [data-testid="stMetric"] { min-height: 96px; }
  [data-testid="stMetricValue"] { font-size: 1rem; overflow-wrap: anywhere; }
  h1 { font-size: 2rem !important; }
  [data-testid="stHorizontalBlock"] { flex-wrap: wrap !important; }
  [data-testid="stHorizontalBlock"] > [data-testid="column"] {
    flex: 1 1 100% !important;
    width: 100% !important;
  }
  [data-testid="stRadio"] div[role="radiogroup"] { align-items: stretch; flex-direction: column; }
}
"""


@lru_cache(maxsize=4)
def _asset_data_uri(path: Path) -> str:
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    return f"data:{mime};base64,{encoded}"


def apply_theme() -> None:
    st.markdown(f"<style>{THEME_CSS}</style>", unsafe_allow_html=True)


def brand_header() -> None:
    st.markdown(
        f"""
        <div class="ts-brand">
          <img src="{_asset_data_uri(TRANSPARENT_LOGO_PATH)}" alt="AGI Space">
          <div>
            <div class="ts-brand__name">Тонкие сигналы</div>
            <div class="ts-brand__note">Evidence-first · рабочий стол технологической разведки</div>
          </div>
          <div class="ts-brand__state">● Закрытый стенд</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
