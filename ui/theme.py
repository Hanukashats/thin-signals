"""Approved AGI Space dusk treatment for the Streamlit operator viewer."""
from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path

import streamlit as st

LOGO_PATH = Path(__file__).with_name("assets") / "agi-space-logo-official.jpg"
FAVICON_PATH = Path(__file__).with_name("assets") / "agi-space-mark.png"

THEME_CSS = r"""
:root {
  --ts-canvas: #E5ECEE;
  --ts-rail: #D8E5E9;
  --ts-detail: #EDF2F2;
  --ts-card: #F5F7F6;
  --ts-selected: #D3EBED;
  --ts-muted-surface: #DCE2DF;
  --ts-border: #B7C4C5;
  --ts-ink: #142226;
  --ts-secondary: #536367;
  --ts-action: #087A84;
}

[data-testid="stAppViewContainer"], [data-testid="stMain"] {
  background: var(--ts-canvas);
  color: var(--ts-ink);
}
[data-testid="stHeader"] { background: transparent; }
[data-testid="stSidebar"] { background: var(--ts-rail); border-right: 1px solid var(--ts-border); }
.block-container { max-width: 1240px; padding-top: 2.4rem; padding-bottom: 4rem; }
h1, h2, h3, [data-testid="stMetricValue"] {
  color: var(--ts-ink) !important;
  font-family: Georgia, "Times New Roman", serif !important;
  letter-spacing: -0.018em;
}
p, label, button, input, textarea, [data-testid="stCaptionContainer"] {
  font-family: "Source Sans 3", "Segoe UI", Arial, sans-serif;
}
p, [data-testid="stCaptionContainer"] { color: var(--ts-secondary); }

.ts-brand {
  align-items: center;
  background: #0B5D52;
  border: 1px solid #0B5D52;
  border-radius: 14px;
  display: grid;
  gap: 18px;
  grid-template-columns: 64px 1fr auto;
  margin: 0 0 22px;
  padding: 12px 14px;
}
.ts-brand img {
  background: #FFFFFF;
  border-radius: 12px;
  display: block;
  height: 64px;
  object-fit: cover;
  width: 64px;
}
.ts-brand__name { color: #FFFFFF; font: 700 23px/1.1 Georgia, serif; }
.ts-brand__note { color: #DDEBE4; font-size: 13px; margin-top: 4px; }
.ts-brand__state {
  background: #DDEBE4;
  border-radius: 999px;
  color: #315D4A;
  font-size: 13px;
  font-weight: 700;
  padding: 8px 13px;
  white-space: nowrap;
}

[data-testid="stVerticalBlockBorderWrapper"] {
  background: var(--ts-card);
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
[data-testid="stExpander"] {
  background: var(--ts-card);
  border: 1px solid var(--ts-border) !important;
  border-radius: 12px !important;
}
[data-testid="stAlert"] { border-radius: 12px; }
[data-testid="stTabs"] button[aria-selected="true"] { color: var(--ts-action); }
[data-testid="stTabs"] button[aria-selected="true"]::after { background: var(--ts-action); }
.stButton > button, .stDownloadButton > button {
  border-color: var(--ts-action);
  border-radius: 9px;
  min-height: 42px;
}
.stButton > button[kind="primary"] {
  background: var(--ts-action);
  color: #FFFFFF;
}
.stButton > button[kind="primary"] p { color: #FFFFFF !important; }
div[data-baseweb="input"] > div, div[data-baseweb="textarea"] > div,
div[data-baseweb="base-input"], textarea {
  background: var(--ts-card) !important;
  border-color: var(--ts-border);
}
a { color: var(--ts-action) !important; }
hr { border-color: var(--ts-border); }
#MainMenu, footer { visibility: hidden; }

@media (max-width: 700px) {
  .block-container { padding: 1rem 1rem 3rem; }
  .ts-brand { grid-template-columns: 48px 1fr; padding: 9px 11px; }
  .ts-brand img { border-radius: 9px; height: 48px; width: 48px; }
  .ts-brand__name { font-size: 18px; }
  .ts-brand__state { display: none; }
  [data-testid="stMetric"] { min-height: 96px; }
  [data-testid="stMetricValue"] { font-size: 1rem; overflow-wrap: anywhere; }
  h1 { font-size: 2rem !important; }
}
"""


@lru_cache(maxsize=1)
def _logo_data_uri() -> str:
    encoded = base64.b64encode(FAVICON_PATH.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def apply_theme() -> None:
    st.markdown(f"<style>{THEME_CSS}</style>", unsafe_allow_html=True)


def brand_header() -> None:
    st.markdown(
        f"""
        <div class="ts-brand">
          <img src="{_logo_data_uri()}" alt="AGI Space">
          <div>
            <div class="ts-brand__name">Тонкие сигналы</div>
            <div class="ts-brand__note">Рабочий стол технологической разведки</div>
          </div>
          <div class="ts-brand__state">● Закрытый стенд</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
