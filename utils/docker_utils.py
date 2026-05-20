import subprocess
from typing import List

from config.settings import get_settings
from utils.logging import get_logger

logger = get_logger("docker_utils")


def cleanup_validation_containers(image_tag: str | None = None) -> None:
    """Remove validation containers and optionally the built image."""
    settings = get_settings()
    tag = image_tag or settings.docker_image_tag

    _run_quiet(["docker", "container", "prune", "-f", "--filter", f"ancestor={tag}"])

    if settings.docker_cleanup_after_validation:
        _run_quiet(["docker", "rmi", "-f", tag])
        logger.info("Removed validation image: %s", tag)
    else:
        logger.debug("Docker image cleanup disabled; kept image %s", tag)


def _run_quiet(cmd: List[str]) -> None:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0 and result.stderr:
            logger.debug("Docker command %s: %s", cmd, result.stderr.strip())
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        logger.warning("Docker cleanup command failed: %s", exc)
