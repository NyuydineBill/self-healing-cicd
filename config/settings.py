import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Settings:
    """Central configuration for the self-healing CI/CD framework."""

    project_root: Path = field(default_factory=lambda: PROJECT_ROOT)

    # GitHub
    github_token: str = field(default_factory=lambda: os.getenv("GITHUB_TOKEN", ""))
    github_owner: str = field(default_factory=lambda: os.getenv("GITHUB_OWNER", ""))
    github_repo: str = field(default_factory=lambda: os.getenv("GITHUB_REPO", ""))

    # OpenAI
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    openai_model: str = field(default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4o-mini"))

    # Orchestration
    max_retry_attempts: int = field(
        default_factory=lambda: int(os.getenv("MAX_RETRY_ATTEMPTS", "3"))
    )
    max_failed_runs: int = field(
        default_factory=lambda: int(os.getenv("MAX_FAILED_RUNS", "5"))
    )
    max_failures_per_run: int = field(
        default_factory=lambda: int(os.getenv("MAX_FAILURES_PER_RUN", "10"))
    )
    stop_on_first_success: bool = field(
        default_factory=lambda: os.getenv("STOP_ON_FIRST_SUCCESS", "true").lower() == "true"
    )
    sample_projects_dir: str = field(
        default_factory=lambda: os.getenv("SAMPLE_PROJECTS_DIR", "sample_projects")
    )

    # OpenAI request handling
    openai_timeout: float = field(
        default_factory=lambda: float(os.getenv("OPENAI_TIMEOUT", "60"))
    )
    openai_max_retries: int = field(
        default_factory=lambda: int(os.getenv("OPENAI_MAX_RETRIES", "3"))
    )

    # Paths
    logs_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "logs")
    results_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "results")
    prompts_dir: Path = field(
        default_factory=lambda: PROJECT_ROOT / "config" / "prompts"
    )
    failure_memory_path: Path = field(
        default_factory=lambda: PROJECT_ROOT / "results" / "failure_memory.json"
    )

    # Docker validation
    docker_image_tag: str = field(
        default_factory=lambda: os.getenv("DOCKER_IMAGE_TAG", "self-healing-validator")
    )
    docker_cleanup_after_validation: bool = field(
        default_factory=lambda: os.getenv("DOCKER_CLEANUP", "true").lower() == "true"
    )
    validate_full_repo: bool = field(
        default_factory=lambda: os.getenv("VALIDATE_FULL_REPO", "false").lower() == "true"
    )

    # Safety
    dry_run: bool = field(
        default_factory=lambda: os.getenv("DRY_RUN", "false").lower() == "true"
    )
    backup_before_patch: bool = field(
        default_factory=lambda: os.getenv("BACKUP_BEFORE_PATCH", "true").lower() == "true"
    )
    require_approval: bool = field(
        default_factory=lambda: os.getenv("REQUIRE_APPROVAL", "true").lower() == "true"
    )
    auto_approve_patches: bool = field(
        default_factory=lambda: os.getenv("AUTO_APPROVE_PATCHES", "false").lower() == "true"
    )
    approval_diff_max_lines: int = field(
        default_factory=lambda: int(os.getenv("APPROVAL_DIFF_MAX_LINES", "80"))
    )
    allowed_path_prefixes: tuple = field(
        default_factory=lambda: tuple(
            p.strip()
            for p in os.getenv("ALLOWED_PATH_PREFIXES", "sample_projects/").split(",")
            if p.strip()
        )
    )

    # Offline / API
    offline_mode: bool = field(
        default_factory=lambda: os.getenv("OFFLINE_MODE", "false").lower() == "true"
    )
    github_api_max_retries: int = field(
        default_factory=lambda: int(os.getenv("GITHUB_API_MAX_RETRIES", "5"))
    )
    excluded_workflow_names: tuple = field(
        default_factory=lambda: tuple(
            n.strip()
            for n in os.getenv(
                "EXCLUDED_WORKFLOW_NAMES",
                "Self-Heal on Failure,self-heal",
            ).split(",")
            if n.strip()
        )
    )

    # Git integration
    git_enabled: bool = field(
        default_factory=lambda: os.getenv("GIT_ENABLED", "false").lower() == "true"
    )
    git_create_pr: bool = field(
        default_factory=lambda: os.getenv("GIT_CREATE_PR", "true").lower() == "true"
    )
    git_branch_prefix: str = field(
        default_factory=lambda: os.getenv("GIT_BRANCH_PREFIX", "self-heal")
    )
    git_base_branch: str = field(
        default_factory=lambda: os.getenv("GIT_BASE_BRANCH", "main")
    )
    git_push_remote: str = field(
        default_factory=lambda: os.getenv("GIT_PUSH_REMOTE", "origin")
    )
    git_author_name: str = field(
        default_factory=lambda: os.getenv("GIT_AUTHOR_NAME", "Self-Healing Bot")
    )
    git_author_email: str = field(
        default_factory=lambda: os.getenv(
            "GIT_AUTHOR_EMAIL", "self-healing-bot@users.noreply.github.com"
        )
    )

    # Logging
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    log_patch_preview_chars: int = field(
        default_factory=lambda: int(os.getenv("LOG_PATCH_PREVIEW_CHARS", "0"))
    )


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
