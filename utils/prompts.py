import re
from typing import Any

from config.settings import get_settings

# Control characters and null bytes that could confuse the LLM or inject
# unexpected instructions via crafted log content.
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# Heuristic: flag strings that look like prompt injection attempts.
_INJECTION_PATTERNS = re.compile(
    r"(ignore previous instructions|ignore all prior|disregard the above"
    r"|you are now|new system prompt|<\|im_start\|>)",
    re.IGNORECASE,
)


def _sanitize(value: str) -> str:
    """Remove control chars and warn on suspected prompt injection strings."""
    cleaned = _CONTROL_CHARS_RE.sub("", value)
    if _INJECTION_PATTERNS.search(cleaned):
        from utils.logging import get_logger

        get_logger("prompts").warning(
            "Possible prompt injection pattern detected in template variable; content sanitized."
        )
        cleaned = _INJECTION_PATTERNS.sub("[REDACTED]", cleaned)
    return cleaned


def load_prompt(template_name: str, variables: dict[str, Any] | None = None) -> str:
    """
    Load a prompt template from config/prompts/ and substitute variables.

    Template files use {variable_name} placeholders. String values are
    sanitized to strip control characters and flag injection attempts before
    being interpolated.
    """
    settings = get_settings()
    template_path = settings.prompts_dir / f"{template_name}.txt"

    if not template_path.is_file():
        raise FileNotFoundError(f"Prompt template not found: {template_path}")

    content = template_path.read_text(encoding="utf-8")
    variables = variables or {}
    sanitized = {k: _sanitize(v) if isinstance(v, str) else v for k, v in variables.items()}

    try:
        return content.format(**sanitized)
    except KeyError as exc:
        missing = str(exc).strip("'")
        raise KeyError(
            f"Missing variable '{missing}' for prompt template '{template_name}'"
        ) from exc
