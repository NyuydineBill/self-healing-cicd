"""
Entry point for the self-healing CI/CD framework.

Usage:
  python main.py              Run the orchestrator
  python main.py check        Pre-flight health check
  python main.py approve-ui   Start web approval UI only
  python -m config.check      Same as check
"""

import sys

from config.settings import get_settings
from config.validation import ConfigurationError, validate_configuration
from orchestrator.workflow import WorkflowOrchestrator
from utils.logging import get_logger, setup_logging

setup_logging()
logger = get_logger("main")


def run_orchestrator() -> int:
    settings = get_settings()

    try:
        validate_configuration(settings)
    except ConfigurationError as exc:
        logger.error("%s", exc)
        return 2

    if settings.dry_run:
        logger.info("Running in DRY_RUN mode")
    if settings.offline_mode:
        logger.info("Running in OFFLINE_MODE (cached logs only)")
    if settings.web_approval_enabled:
        logger.info(
            "Web approval enabled: http://127.0.0.1:%d",
            settings.web_approval_port,
        )
    elif settings.require_approval and not settings.auto_approve_patches:
        logger.info("Patch approval required before apply (REQUIRE_APPROVAL=true)")

    batch = WorkflowOrchestrator().run()

    logger.info(
        "Workflow finished: status=%s message=%s",
        batch.status,
        batch.message,
    )

    for result in batch.results:
        pr_url = (result.git_info or {}).get("pr_url")
        logger.info(
            "  Run %s | %s | file=%s | success=%s%s",
            result.run_id,
            result.status,
            result.target_file,
            result.repair_success,
            f" | PR: {pr_url}" if pr_url else "",
        )
        for attempt in result.attempts:
            logger.info(
                "    Attempt %d: validation=%s",
                attempt.attempt,
                attempt.validation.get("status"),
            )

    if batch.status in ("no_failures", "no_offline_logs"):
        return 0

    if any(r.status == "dry_run_complete" for r in batch.results):
        return 0

    return 0 if batch.repair_success else 1


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]

    if argv and argv[0] in ("check", "--check"):
        from config.check import run_health_check

        return run_health_check()

    if argv and argv[0] in ("approve-ui", "approve-ui-server"):
        from utils.approval_web import run_standalone_server

        port = int(argv[1]) if len(argv) > 1 else None
        run_standalone_server(port=port)
        return 0

    if argv and argv[0] in ("run", "--run"):
        argv = argv[1:]

    return run_orchestrator()


if __name__ == "__main__":
    raise SystemExit(main())
