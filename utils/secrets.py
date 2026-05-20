import re
from typing import Iterable, List, Optional, Set

_SECRET_PATTERNS = [
    re.compile(r"ghp_[A-Za-z0-9_]{20,}", re.I),
    re.compile(r"gho_[A-Za-z0-9_]{20,}", re.I),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}", re.I),
    re.compile(r"sk-[A-Za-z0-9]{20,}", re.I),
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]+", re.I),
]

_known_secrets: Set[str] = set()


def register_secrets(values: Iterable[Optional[str]]) -> None:
    """Register literal secret values to redact from logs."""
    for value in values:
        if value and len(value) >= 8:
            _known_secrets.add(value)


def mask_secrets(text: str) -> str:
    """Redact tokens and registered secrets from a string."""
    if not text:
        return text

    masked = text
    for secret in _known_secrets:
        masked = masked.replace(secret, "***REDACTED***")

    for pattern in _SECRET_PATTERNS:
        masked = pattern.sub("***REDACTED***", masked)

    return masked


def safe_patch_summary(patch: str, max_preview: int = 0) -> str:
    """Return a safe log line for patch content (no full body at INFO)."""
    length = len(patch or "")
    if max_preview <= 0:
        return f"<patch omitted, {length} chars>"
    preview = (patch or "")[:max_preview]
    return f"<patch preview {len(preview)}/{length} chars: {mask_secrets(preview)!r}>"


def truncate_for_log(text: str, limit: int = 500) -> str:
    """Truncate and mask text for safe logging."""
    if not text:
        return ""
    clipped = text if len(text) <= limit else f"{text[:limit]}... [truncated]"
    return mask_secrets(clipped)
