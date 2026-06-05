import time
from typing import Any

from openai import OpenAI

from config.settings import get_settings
from utils.logging import get_logger

logger = get_logger("llm_client")

# Approximate cost per 1k tokens in USD — update as pricing changes.
_COST_PER_1K: dict[str, dict[str, float]] = {
    "gpt-4o": {"input": 0.005, "output": 0.015},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-4-turbo": {"input": 0.01, "output": 0.03},
    "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
}


def _log_usage(model: str, usage: Any) -> None:
    """Log token counts and estimated cost after a successful completion."""
    if usage is None:
        return
    prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
    completion_tokens = getattr(usage, "completion_tokens", 0) or 0
    total_tokens = getattr(usage, "total_tokens", prompt_tokens + completion_tokens)

    # Find the cost table entry by matching a prefix of the model name.
    rates = next(
        (v for k, v in _COST_PER_1K.items() if model.startswith(k)),
        None,
    )
    if rates:
        est_cost = (prompt_tokens / 1000 * rates["input"]) + (
            completion_tokens / 1000 * rates["output"]
        )
        logger.info(
            "LLM usage: model=%s prompt_tokens=%d completion_tokens=%d total=%d est_cost_usd=%.6f",
            model,
            prompt_tokens,
            completion_tokens,
            total_tokens,
            est_cost,
        )
    else:
        logger.info(
            "LLM usage: model=%s prompt_tokens=%d completion_tokens=%d total=%d",
            model,
            prompt_tokens,
            completion_tokens,
            total_tokens,
        )


def chat_completion_with_retry(
    client: OpenAI,
    *,
    model: str,
    messages: list[dict],
    timeout: float | None = None,
    max_retries: int | None = None,
) -> Any:
    """Call OpenAI chat completions with timeout, exponential backoff, and usage logging."""
    settings = get_settings()
    timeout = timeout if timeout is not None else settings.openai_timeout
    max_retries = max_retries if max_retries is not None else settings.openai_max_retries

    last_error: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                timeout=timeout,
            )
            _log_usage(model, getattr(response, "usage", None))
            return response
        except Exception as exc:
            last_error = exc
            if attempt >= max_retries:
                logger.error(
                    "LLM request failed after %d attempt(s): %s",
                    max_retries,
                    exc,
                )
                raise

            delay = min(2 ** (attempt - 1), 30)
            logger.warning(
                "LLM request attempt %d/%d failed (%s); retrying in %ds",
                attempt,
                max_retries,
                exc,
                delay,
            )
            time.sleep(delay)

    if last_error:
        raise last_error
    raise RuntimeError("LLM retry loop exited without result")
