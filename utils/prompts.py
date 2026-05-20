from pathlib import Path
from typing import Any, Dict

from config.settings import get_settings


def load_prompt(template_name: str, variables: Dict[str, Any] | None = None) -> str:
    """
    Load a prompt template from config/prompts/ and substitute variables.

    Template files use {variable_name} placeholders.
    """
    settings = get_settings()
    template_path = settings.prompts_dir / f"{template_name}.txt"

    if not template_path.is_file():
        raise FileNotFoundError(f"Prompt template not found: {template_path}")

    content = template_path.read_text(encoding="utf-8")
    variables = variables or {}

    try:
        return content.format(**variables)
    except KeyError as exc:
        missing = str(exc).strip("'")
        raise KeyError(
            f"Missing variable '{missing}' for prompt template '{template_name}'"
        ) from exc
