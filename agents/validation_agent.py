import os
import subprocess
import sys
from typing import Any

from config.settings import get_settings
from utils.docker_utils import cleanup_validation_containers
from utils.errors import ErrorCategory, categorize_failure
from utils.logging import get_logger
from utils.validation_scope import resolve_validation_scope

logger = get_logger("validation_agent")


class ValidationAgent:
    def __init__(self, image_tag: str | None = None):
        settings = get_settings()
        self.image_tag = image_tag or settings.docker_image_tag
        self.cleanup_after = settings.docker_cleanup_after_validation
        self.validate_full_repo = settings.validate_full_repo
        self.sample_projects_dir = settings.sample_projects_dir

    def _validate_direct(self, target_file: str | None = None) -> dict[str, Any]:
        """Run pytest in the current environment without Docker."""
        scope = (
            resolve_validation_scope(target_file, self.sample_projects_dir) if target_file else None
        )
        if not scope:
            scope = "."
        logger.info("Direct validation scope: %s", scope)

        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", scope, "-v", "--tb=short"],
                capture_output=True,
                text=True,
                timeout=120,
            )
            combined = result.stdout + result.stderr
            if result.returncode == 0:
                logger.info("Direct validation succeeded (scope=%s)", scope)
                return {"status": "success", "output": combined, "category": None, "scope": scope}
            logger.warning("Direct validation failed (scope=%s)", scope)
            return {
                "status": "failed",
                "output": combined,
                "category": categorize_failure(combined.splitlines()).value,
                "scope": scope,
            }
        except subprocess.TimeoutExpired as exc:
            return {
                "status": "error",
                "output": f"Validation timed out: {exc}",
                "category": ErrorCategory.RUNTIME.value,
                "scope": scope,
            }
        except Exception as exc:
            logger.exception("Direct validation error: %s", exc)
            return {
                "status": "error",
                "output": str(exc),
                "category": ErrorCategory.RUNTIME.value,
                "scope": scope,
            }

    def _pytest_command(self, target_file: str | None = None) -> list[str]:
        """Build docker run pytest args, scoped to project when possible."""
        if self.validate_full_repo or not target_file:
            return ["pytest", "-v"]

        scope = resolve_validation_scope(target_file, self.sample_projects_dir)
        if scope:
            logger.info("Scoped validation to %s", scope)
            return ["pytest", scope, "-v"]

        logger.warning(
            "Could not scope validation for %s; running full test suite",
            target_file,
        )
        return ["pytest", "-v"]

    def validate_patch(self, target_file: str | None = None) -> dict[str, Any]:
        if not os.path.exists("Dockerfile"):
            logger.info("No Dockerfile found; running pytest directly (no Docker)")
            return self._validate_direct(target_file)

        pytest_args = self._pytest_command(target_file)

        try:
            logger.info("Building validation image: %s", self.image_tag)

            build = subprocess.run(
                ["docker", "build", "-t", self.image_tag, "."],
                capture_output=True,
                text=True,
                timeout=300,
            )

            if build.returncode != 0:
                logger.error("Docker build failed")
                result = {
                    "status": "build_failed",
                    "output": build.stderr,
                    "category": ErrorCategory.BUILD.value,
                    "scope": None,
                }
                if self.cleanup_after:
                    cleanup_validation_containers(self.image_tag)
                return result

            run_cmd = ["docker", "run", "--rm", self.image_tag] + pytest_args
            logger.info("Running validation: %s", " ".join(run_cmd[3:]))

            test = subprocess.run(
                run_cmd,
                capture_output=True,
                text=True,
                timeout=300,
            )

            scope = (
                pytest_args[1]
                if len(pytest_args) > 1 and pytest_args[0] == "pytest"
                else "full_repo"
            )

            if self.cleanup_after:
                cleanup_validation_containers(self.image_tag)

            if test.returncode == 0:
                logger.info("Validation succeeded (scope=%s)", scope)
                return {
                    "status": "success",
                    "output": test.stdout,
                    "category": None,
                    "scope": scope,
                }

            logger.warning("Validation tests failed (scope=%s)", scope)
            combined_output = test.stdout + test.stderr
            return {
                "status": "failed",
                "output": combined_output,
                "category": categorize_failure(combined_output.splitlines()).value,
                "scope": scope,
            }

        except subprocess.TimeoutExpired as exc:
            logger.error("Validation timed out: %s", exc)
            if self.cleanup_after:
                cleanup_validation_containers(self.image_tag)
            return {
                "status": "error",
                "output": f"Validation timed out: {exc}",
                "category": ErrorCategory.RUNTIME.value,
                "scope": None,
            }
        except Exception as exc:
            logger.exception("Validation error: %s", exc)
            if self.cleanup_after:
                cleanup_validation_containers(self.image_tag)
            return {
                "status": "error",
                "output": str(exc),
                "category": ErrorCategory.RUNTIME.value,
                "scope": None,
            }
