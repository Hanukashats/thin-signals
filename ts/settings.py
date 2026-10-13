"""Runtime settings from .env / environment (no secrets inline; *_FILE point to files)."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_ALLOWED_MODELS = (
    "qwen/qwen3.6-35b-a3b",        # primary
    "openai/gpt-5.6-luna",         # judge / escalation
    "qwen/qwen3-235b-a22b-2507",   # fallback
    "openai/gpt-4.1",              # reserve
)


def _read_secret(path: str | None) -> str | None:
    if not path:
        return None
    p = Path(path)
    if not p.is_absolute():
        p = Path(os.environ.get("TS_ROOT", Path.cwd())) / p
    return p.read_text().strip() if p.exists() else None


def _load_dotenv(root: Path) -> None:
    if os.environ.get("TS_DISABLE_DOTENV", "").lower() in {"1", "true", "yes"}:
        return
    env = root / ".env"
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        v = v.split(" #", 1)[0].strip().strip('"').strip("'")
        os.environ.setdefault(k.strip(), v)


@dataclass
class Settings:
    root: Path
    profile: str
    database_url: str
    pg_password: str | None
    rules_version: str
    snapshot_dir: Path
    openrouter_url: str
    openrouter_key: str | None
    llm_primary: str
    llm_judge: str
    llm_fallback: str
    llm_provider_policy: dict
    allowed_models: tuple[str, ...] = DEFAULT_ALLOWED_MODELS
    product_mode: bool = False
    searxng_url: str | None = None
    docling_url: str | None = None
    litellm_url: str | None = None
    embedding_alias: str = "embedding-local"
    extra: dict = field(default_factory=dict)
    search_max_workers: int = 6
    search_deadline_seconds: float = 90.0
    wide_search_deadline_seconds: float = 540.0
    source_timeout_seconds: float = 40.0
    gpt_researcher_enabled: bool = False
    gpt_researcher_url: str | None = None
    gpt_researcher_max_cost_usd: float = 0.08
    gpt_researcher_max_leads: int = 12
    evidence_fetch_limit: int = 24
    adversarial_review_enabled: bool = False
    review_time_seconds: float = 45.0
    review_max_output_tokens: int = 1200
    review_max_cost_usd: float = 0.03
    review_evidence_limit: int = 12

    @property
    def sqlalchemy_url(self) -> str:
        url = self.database_url
        if self.pg_password and "@" in url and ":" not in url.split("//", 1)[1].split("@", 1)[0]:
            scheme, rest = url.split("//", 1)
            user, host = rest.split("@", 1)
            url = f"{scheme}//{user}:{self.pg_password}@{host}"
        return url


def load(root: str | Path | None = None) -> Settings:
    root = Path(root or os.environ.get("TS_ROOT") or Path.cwd()).resolve()
    os.environ.setdefault("TS_ROOT", str(root))
    _load_dotenv(root)
    g = os.environ.get
    return Settings(
        root=root,
        profile=g("TS_PROFILE", "laptop"),
        database_url=g("TS_DATABASE_URL", "postgresql+psycopg://ts@127.0.0.1:55432/thin_signals"),
        pg_password=_read_secret(g("TS_PG_PASSWORD_FILE", ".secrets/pg_password")),
        rules_version=g("TS_RULES_VERSION", "rules-0.1"),
        snapshot_dir=root / g("TS_SNAPSHOT_DIR", "snapshots"),
        openrouter_url=g("TS_OPENROUTER_URL", "https://openrouter.ai/api/v1"),
        openrouter_key=_read_secret(g("TS_OPENROUTER_KEY_FILE", ".secrets/openrouter_key")),
        llm_primary=g("TS_LLM_PRIMARY", DEFAULT_ALLOWED_MODELS[0]),
        llm_judge=g("TS_LLM_JUDGE", DEFAULT_ALLOWED_MODELS[1]),
        llm_fallback=g("TS_LLM_FALLBACK", DEFAULT_ALLOWED_MODELS[2]),
        llm_provider_policy=json.loads(g("TS_LLM_PROVIDER_POLICY", '{"zdr": true, "data_collection": "deny"}')),
        product_mode=g("TS_PRODUCT_MODE", "false").lower() == "true",
        searxng_url=g("TS_SEARXNG_URL"),
        docling_url=g("TS_DOCLING_URL"),
        litellm_url=g("TS_LITELLM_URL"),
        embedding_alias=g("TS_EMBEDDING_ALIAS", "embedding-local"),
        search_max_workers=int(g("TS_SEARCH_MAX_WORKERS", "6")),
        search_deadline_seconds=float(g("TS_SEARCH_DEADLINE_SECONDS", "90")),
        wide_search_deadline_seconds=float(g("TS_WIDE_SEARCH_DEADLINE_SECONDS", "540")),
        source_timeout_seconds=float(g("TS_SOURCE_TIMEOUT_SECONDS", "40")),
        gpt_researcher_enabled=g("TS_GPT_RESEARCHER_ENABLED", "false").lower() == "true",
        gpt_researcher_url=g("TS_GPT_RESEARCHER_URL"),
        gpt_researcher_max_cost_usd=float(g("TS_GPT_RESEARCHER_MAX_COST_USD", "0.08")),
        gpt_researcher_max_leads=int(g("TS_GPT_RESEARCHER_MAX_LEADS", "12")),
        evidence_fetch_limit=int(g("TS_EVIDENCE_FETCH_LIMIT", "24")),
        adversarial_review_enabled=g(
            "TS_ADVERSARIAL_REVIEW_ENABLED", "false",
        ).lower() == "true",
        review_time_seconds=float(g("TS_REVIEW_TIME_SECONDS", "45")),
        review_max_output_tokens=int(g("TS_REVIEW_MAX_OUTPUT_TOKENS", "1200")),
        review_max_cost_usd=float(g("TS_REVIEW_MAX_COST_USD", "0.03")),
        review_evidence_limit=int(g("TS_REVIEW_EVIDENCE_LIMIT", "12")),
    )
