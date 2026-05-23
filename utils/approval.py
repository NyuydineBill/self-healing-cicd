import difflib
import sys
from typing import Optional

from config.settings import get_settings
from utils.logging import get_logger

logger = get_logger("approval")


def format_patch_diff(
    target_file: str, original: str, patched: str, context_lines: int = 3
) -> str:
    """Unified diff for human review."""
    original_lines = original.splitlines(keepends=True)
    patched_lines = patched.splitlines(keepends=True)
    diff = difflib.unified_diff(
        original_lines,
        patched_lines,
        fromfile=f"{target_file} (before)",
        tofile=f"{target_file} (after)",
        n=context_lines,
    )
    return "".join(diff) or "(no line changes detected)\n"


def request_patch_approval(
    target_file: str,
    original_content: str,
    patch_content: str,
    run_id: str | int = "",
) -> bool:
    """
    Decide whether to apply a generated patch.

    Priority: auto-approve → web UI → terminal prompt → reject (non-interactive).
    """
    settings = get_settings()

    if settings.auto_approve_patches:
        logger.info("Patch auto-approved (AUTO_APPROVE_PATCHES=true)")
        return True

    if not settings.require_approval:
        return True

    if settings.web_approval_enabled:
        from utils.approval_web import ApprovalWebServer

        logger.info("Waiting for web approval at http://127.0.0.1:%d", settings.web_approval_port)
        return ApprovalWebServer().wait_for_decision(
            target_file=target_file,
            original_content=original_content,
            patch_content=patch_content,
            run_id=run_id,
        )

    if not sys.stdin.isatty():
        logger.warning(
            "Patch approval required but stdin is not interactive. "
            "Enable WEB_APPROVAL_ENABLED=true, AUTO_APPROVE_PATCHES=true, "
            "or REQUIRE_APPROVAL=false."
        )
        return False

    diff = format_patch_diff(target_file, original_content, patch_content)
    max_lines = settings.approval_diff_max_lines
    diff_lines = diff.splitlines()
    if len(diff_lines) > max_lines:
        diff_display = (
            "\n".join(diff_lines[:max_lines])
            + f"\n... [{len(diff_lines) - max_lines} more lines]"
        )
    else:
        diff_display = diff

    print("\n" + "=" * 60)
    print(f"Patch approval required: {target_file}")
    print("=" * 60)
    print(diff_display)
    print("=" * 60)

    while True:
        answer = input("Apply this patch? [y/N]: ").strip().lower()
        if answer in ("y", "yes"):
            logger.info("Patch approved by operator")
            return True
        if answer in ("n", "no", ""):
            logger.info("Patch rejected by operator")
            return False
        print("Please answer y or n.")
