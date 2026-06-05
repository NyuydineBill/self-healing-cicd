import shutil
import subprocess

from config.settings import Settings


class ConfigurationError(Exception):
    """Raised when required configuration or runtime dependencies are missing."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        message = "Configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        super().__init__(message)


def _docker_available() -> bool:
    if not shutil.which("docker"):
        return False
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def validate_configuration(settings: Settings) -> None:
    """
    Fail fast with clear errors when required config or tools are missing.

    Dry-run mode relaxes GitHub and Docker requirements but still needs OpenAI
    for diagnosis and patch generation.
    """
    errors: list[str] = []

    if not settings.openai_api_key:
        errors.append("OPENAI_API_KEY is required (set in .env or environment)")

    if settings.git_enabled and not settings.dry_run and not settings.github_token:
        errors.append("GITHUB_TOKEN is required when GIT_ENABLED=true (for push/PR)")

    if settings.offline_mode:
        if not settings.openai_api_key:
            errors.append("OPENAI_API_KEY is required in OFFLINE_MODE")
        if errors:
            raise ConfigurationError(errors)
        return

    if settings.dry_run:
        if errors:
            raise ConfigurationError(errors)
        return

    if not settings.github_token:
        errors.append("GITHUB_TOKEN is required (set in .env or environment)")
    if not settings.github_owner:
        errors.append("GITHUB_OWNER is required (set in .env or environment)")
    if not settings.github_repo:
        errors.append("GITHUB_REPO is required (set in .env or environment)")

    if not _docker_available():
        errors.append("Docker is not available (install Docker and ensure the daemon is running)")

    prompts_dir = settings.prompts_dir
    for name in ("diagnosis", "patch"):
        if not (prompts_dir / f"{name}.txt").is_file():
            errors.append(f"Prompt template missing: {prompts_dir / f'{name}.txt'}")

    if settings.max_retry_attempts < 1:
        errors.append("MAX_RETRY_ATTEMPTS must be at least 1")
    if settings.max_failed_runs < 1:
        errors.append("MAX_FAILED_RUNS must be at least 1")
    if settings.max_failures_per_run < 1:
        errors.append("MAX_FAILURES_PER_RUN must be at least 1")
    if settings.openai_max_retries < 1:
        errors.append("OPENAI_MAX_RETRIES must be at least 1")
    if settings.openai_timeout <= 0:
        errors.append("OPENAI_TIMEOUT must be greater than 0")

    if errors:
        raise ConfigurationError(errors)
