import functools
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    String secrets have no defaults — app will fail to start
    if any of these are missing from the .env file.
    Numeric/boolean constants have defaults matching Section 14
    of system_architecture_guide.md.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── Anthropic ─────────────────────────────────────
    anthropic_api_key: str

    # ── Supabase ──────────────────────────────────────
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str

    # ── LangSmith ─────────────────────────────────────
    langchain_api_key: str
    langchain_tracing_v2: bool = True
    langchain_project: str = "cv-agent"

    # ── Sentry ────────────────────────────────────────
    sentry_dsn_backend: str

    # ── App Config ────────────────────────────────────
    next_public_api_url: str = "http://localhost:8000"

    # ── QC Constants ──────────────────────────────────
    max_qc_iterations: int = 3
    ats_threshold: float = 70.0
    semantic_threshold: float = 65.0
    qc_combined_weight_ats: float = 0.5
    qc_combined_weight_semantic: float = 0.5

    # ── TOP_N Constants ───────────────────────────────
    top_n_experience: int = 3
    top_n_projects: int = 3
    top_n_awards: int = 3
    top_n_education: int = 2
    top_n_organizations: int = 2
    top_n_certificates: int = 5
    top_n_skills: int = 15

    # ── LLM & Storage Constants ───────────────────────
    signed_url_expiry_seconds: int = 3600
    llm_timeout_seconds: int = 60
    llm_max_retries: int = 3


@functools.lru_cache
def get_settings() -> Settings:
    """
    Returns a cached singleton of Settings.
    The .env file is read only once per process.

    Usage:
        from config import get_settings
        settings = get_settings()
        print(settings.anthropic_api_key)
    """
    return Settings()