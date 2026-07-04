import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass
class PlatformSettings:
    """Configuration for the Nyuydine hosted platform (Phase 1)."""

    # API
    api_host: str = field(
        default_factory=lambda: os.getenv("PLATFORM_API_HOST", "0.0.0.0")  # nosec B104
    )
    api_port: int = field(default_factory=lambda: int(os.getenv("PLATFORM_API_PORT", "8080")))
    api_key: str = field(default_factory=lambda: os.getenv("PLATFORM_API_KEY", ""))
    cors_origins: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            o.strip() for o in os.getenv("PLATFORM_CORS_ORIGINS", "*").split(",") if o.strip()
        )
    )

    # Database
    database_url: str = field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL",
            "sqlite:///./platform_data/nyuydine.db",
        )
    )

    # Redis / Celery
    redis_url: str = field(
        default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379/0")
    )
    celery_broker_url: str = field(
        default_factory=lambda: os.getenv(
            "CELERY_BROKER_URL", os.getenv("REDIS_URL", "redis://localhost:6379/0")
        )
    )
    celery_result_backend: str = field(
        default_factory=lambda: os.getenv(
            "CELERY_RESULT_BACKEND",
            os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        )
    )
    celery_task_always_eager: bool = field(
        default_factory=lambda: os.getenv("CELERY_TASK_ALWAYS_EAGER", "false").lower() == "true"
    )

    # GitHub App
    github_app_id: str = field(default_factory=lambda: os.getenv("GITHUB_APP_ID", ""))
    github_app_private_key: str = field(
        default_factory=lambda: os.getenv("GITHUB_APP_PRIVATE_KEY", "")
    )
    github_app_private_key_path: str = field(
        default_factory=lambda: os.getenv("GITHUB_APP_PRIVATE_KEY_PATH", "")
    )
    github_webhook_secret: str = field(
        default_factory=lambda: os.getenv("GITHUB_WEBHOOK_SECRET", "")
    )

    # Repair worker
    workspace_root: Path = field(
        default_factory=lambda: Path(
            os.getenv("PLATFORM_WORKSPACE_ROOT", "platform_data/workspaces")
        )
    )
    default_automation_mode: str = field(
        default_factory=lambda: os.getenv("DEFAULT_AUTOMATION_MODE", "suggest")
    )

    # Shared secrets for LLM (org-level keys come later)
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    openai_model: str = field(default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4o-mini"))

    def resolve_github_private_key(self) -> str:
        if self.github_app_private_key.strip():
            return self.github_app_private_key.replace("\\n", "\n")
        if self.github_app_private_key_path:
            return Path(self.github_app_private_key_path).read_text(encoding="utf-8")
        return ""


@lru_cache
def get_platform_settings() -> PlatformSettings:
    return PlatformSettings()
