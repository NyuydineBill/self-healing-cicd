import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

from config.settings import Settings, get_settings
from config.validation import ConfigurationError, validate_configuration
from utils.policy import get_allowed_prefixes


def run_health_check(settings: Settings | None = None) -> int:
    """
    Pre-flight check for production use. Returns 0 if all checks pass, 1 otherwise.
    """
    settings = settings or get_settings()
    checks: List[Tuple[str, bool, str]] = []

    def add(name: str, ok: bool, detail: str = "") -> None:
        checks.append((name, ok, detail))

    # Configuration
    try:
        validate_configuration(settings)
        add("Configuration", True, "environment and templates valid")
    except ConfigurationError as exc:
        add("Configuration", False, str(exc))

    # Prompt templates
    for name in ("diagnosis", "patch"):
        path = settings.prompts_dir / f"{name}.txt"
        add(f"Prompt '{name}'", path.is_file(), str(path))

    # Policy
    prefixes = get_allowed_prefixes()
    add("Path policy", bool(prefixes), f"allowed: {', '.join(prefixes)}")

    # Docker (skip if dry-run only deployment)
    if not settings.dry_run:
        docker_bin = shutil.which("docker")
        if not docker_bin:
            add("Docker", False, "docker CLI not found")
        else:
            try:
                proc = subprocess.run(
                    ["docker", "info"],
                    capture_output=True,
                    timeout=10,
                )
                if proc.returncode == 0:
                    add("Docker", True, "daemon running")
                else:
                    add(
                        "Docker",
                        False,
                        "CLI installed but daemon not running — start Docker Desktop",
                    )
            except (subprocess.TimeoutExpired, FileNotFoundError):
                add("Docker", False, "daemon unreachable")
    else:
        add("Docker", True, "skipped (DRY_RUN=true)")

    # Git
    if settings.git_enabled:
        git_dir = settings.project_root / ".git"
        add("Git repository", git_dir.is_dir(), str(git_dir))
    else:
        add("Git repository", True, "skipped (GIT_ENABLED=false)")

    # Results/logs writable
    for directory in (settings.results_dir, settings.logs_dir):
        try:
            directory.mkdir(parents=True, exist_ok=True)
            test_file = directory / ".write_test"
            test_file.write_text("ok", encoding="utf-8")
            test_file.unlink()
            add(f"Writable {directory.name}/", True)
        except OSError as exc:
            add(f"Writable {directory.name}/", False, str(exc))

    # Offline cache (required only when OFFLINE_MODE=true)
    offline_dir = settings.logs_dir / "extracted"
    cached_count = (
        len(list(offline_dir.iterdir())) if offline_dir.is_dir() else 0
    )
    if settings.offline_mode:
        add(
            "Offline log cache",
            cached_count > 0,
            f"{cached_count} run(s) under {offline_dir} (required for OFFLINE_MODE)",
        )
    else:
        add(
            "Offline log cache",
            True,
            f"{cached_count} run(s) cached (optional unless OFFLINE_MODE=true)",
        )

    # Print report
    print("\nSelf-Healing CI/CD — Pre-flight Check\n" + "=" * 40)
    failed = 0
    for name, ok, detail in checks:
        status = "PASS" if ok else "FAIL"
        line = f"[{status}] {name}"
        if detail:
            line += f" — {detail}"
        print(line)
        if not ok:
            failed += 1

    print("=" * 40)
    if failed:
        print(f"{failed} check(s) failed. Fix issues before running main.py.")
        return 1

    print("All checks passed. Ready to run: python main.py")
    return 0


def main() -> int:
    return run_health_check()


if __name__ == "__main__":
    sys.exit(main())
