"""
Overkube — Centralised Application Configuration
=================================================
Reads all settings from environment variables (or a .env file).
Import ``settings`` anywhere in the app — never access os.environ directly.

All defaults are safe for local development with SQLite + kind.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application-wide settings loaded from environment / .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = "sqlite:///./overkube.db"

    # ── Kubernetes ────────────────────────────────────────────────────────────
    kube_context: str = "kind-overkube"
    overkube_namespace: str = "overkube"
    collector_interval: int = 30  # seconds between metric collection runs

    # ── Pricing ───────────────────────────────────────────────────────────────
    price_cpu_per_vcpu_hour: float = 0.04   # $ per vCPU-hour
    price_mem_per_gb_hour: float = 0.005    # $ per GB-hour

    # ── GitHub ────────────────────────────────────────────────────────────────
    github_token: str = ""
    github_gitops_repo: str = ""

    # ── App ───────────────────────────────────────────────────────────────────
    app_env: str = "development"
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse comma-separated CORS origins into a list."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


# Singleton — import this everywhere
settings = Settings()
