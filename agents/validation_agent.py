import os
import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

from config.settings import get_settings
from utils.docker_utils import cleanup_validation_containers
from utils.errors import ErrorCategory, categorize_failure
from utils.logging import get_logger
from utils.validation_scope import resolve_validation_scope

logger = get_logger("validation_agent")

_UNSAFE_REPLAY_RE = re.compile(
    r"\brm\b|\brmdir\b|git\s+push|docker\s+push|kubectl\s+delete|--force|>\s*/|\bsudo\b",
    re.IGNORECASE,
)

_COV_ARG_RE = re.compile(r"^--cov")
_COV_REPORT_RE = re.compile(r"^--cov-report")


def _strip_cov_args(parts: list[str]) -> list[str]:
    return [
        p
        for p in parts
        if not _COV_ARG_RE.match(p) and not _COV_REPORT_RE.match(p) and p != "--no-cov"
    ]


def _inject_pytest_ini_override(parts: list[str]) -> list[str]:
    """Override pytest.ini addopts (self-heal CI has pytest but not pytest-cov)."""
    if "-m" not in parts or "pytest" not in parts or "-o" in parts:
        return parts
    idx = parts.index("pytest") + 1
    return parts[:idx] + ["-o", "addopts="] + parts[idx:]


class ValidationAgent:
    def __init__(self, image_tag: str | None = None):
        settings = get_settings()
        self.image_tag = image_tag or settings.docker_image_tag
        self.cleanup_after = settings.docker_cleanup_after_validation
        self.validate_full_repo = settings.validate_full_repo
        self.sample_projects_dir = settings.sample_projects_dir
        self.validation_timeout = settings.validation_timeout

    def _normalize_replay_parts(self, parts: list[str]) -> list[str]:
        """Make a CI command runnable in the local repair environment."""
        if not parts:
            return parts

        raw_binary = Path(parts[0]).name.lower()
        binary = raw_binary[:-4] if raw_binary.endswith(".exe") else raw_binary
        use_local_python = binary in ("python", "python3") or not os.path.isfile(parts[0])

        if binary == "pytest":
            parts = [sys.executable, "-m", "pytest"] + parts[1:]
            use_local_python = True
        elif use_local_python:
            parts[0] = sys.executable

        if use_local_python and "-m" in parts and "pytest" in parts:
            parts = _inject_pytest_ini_override(_strip_cov_args(parts))

        return parts

    def _validate_by_replay(
        self,
        command: str,
        *,
        target_file: str | None = None,
    ) -> dict[str, Any]:
        """Re-run the exact command that failed in CI — the most accurate validation."""
        if _UNSAFE_REPLAY_RE.search(command):
            logger.warning("Replay command looks unsafe, falling back to pytest: %r", command)
            return self._validate_direct(target_file)

        try:
            parts = shlex.split(command)
        except ValueError as exc:
            logger.warning("Could not parse replay command %r: %s", command, exc)
            return self._validate_direct(target_file)

        if not parts:
            return self._validate_direct(target_file)

        parts = self._normalize_replay_parts(parts)

        logger.info("Replay validation: %s", " ".join(parts))
        try:
            result = subprocess.run(
                parts,
                capture_output=True,
                text=True,
                timeout=self.validation_timeout,
                env=self._pytest_env(),
            )
        except FileNotFoundError as exc:
            logger.warning("Replay command not found (%s); falling back to pytest", exc)
            return self._validate_direct(target_file)
        except subprocess.TimeoutExpired as exc:
            return {
                "status": "error",
                "output": f"Replay validation timed out: {exc}",
                "category": ErrorCategory.RUNTIME.value,
                "scope": command,
            }

        combined = result.stdout + result.stderr
        if result.returncode == 0:
            logger.info("Replay validation succeeded: %s", command)
            return {"status": "success", "output": combined, "category": None, "scope": command}

        logger.warning("Replay validation failed (exit=%d): %s", result.returncode, command)
        return {
            "status": "failed",
            "output": combined,
            "category": categorize_failure(combined.splitlines()).value,
            "scope": command,
        }

    def _pytest_env(self) -> dict[str, str]:
        return {**os.environ, "PYTEST_ADDOPTS": ""}

    def _validate_direct(self, target_file: str | None = None) -> dict[str, Any]:
        """Run pytest in the current environment without Docker."""
        if target_file and Path(target_file).is_file():
            sample_scope = resolve_validation_scope(target_file, self.sample_projects_dir)
            if sample_scope and sample_scope.startswith(f"{self.sample_projects_dir}/"):
                scope = sample_scope
            else:
                scope = target_file
        elif target_file:
            scope = resolve_validation_scope(target_file, self.sample_projects_dir) or "."
        else:
            scope = "."
        logger.info("Direct validation scope: %s", scope)

        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "-o", "addopts=", scope, "-v", "--tb=short"],
                capture_output=True,
                text=True,
                timeout=self.validation_timeout,
                env=self._pytest_env(),
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
            return ["pytest", "-o", "addopts=", "-v", "--tb=short"]

        scope = resolve_validation_scope(target_file, self.sample_projects_dir)
        if scope:
            logger.info("Scoped validation to %s", scope)
            return ["pytest", "-o", "addopts=", scope, "-v", "--tb=short"]

        logger.warning(
            "Could not scope validation for %s; running full test suite",
            target_file,
        )
        return ["pytest", "-o", "addopts=", "-v", "--tb=short"]

    def validate_patch(
        self,
        target_file: str | None = None,
        failing_command: str | None = None,
    ) -> dict[str, Any]:
        # Scoped validation beats full-suite replay (avoids pytest.ini addopts conflicts).
        if target_file and not self.validate_full_repo:
            scope = resolve_validation_scope(target_file, self.sample_projects_dir)
            if scope or Path(target_file).is_file():
                logger.info(
                    "Scoped validation for %s (not replaying full CI command)",
                    scope or target_file,
                )
                return self._validate_direct(target_file)

        if failing_command:
            logger.info("Using CI command replay for validation")
            return self._validate_by_replay(failing_command, target_file=target_file)

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
