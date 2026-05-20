import time
from typing import Any, List, Optional

from openai import OpenAI

from config.settings import get_settings
from utils.logging import get_logger

logger = get_logger("llm_client")


def chat_completion_with_retry(
    client: OpenAI,
    *,
    model: str,
    messages: List[dict],
    timeout: Optional[float] = None,
    max_retries: Optional[int] = None,
) -> Any:
    """
    Call OpenAI chat completions with timeout and exponential backoff retries.
    """
    settings = get_settings()
    timeout = timeout if timeout is not None else settings.openai_timeout
    max_retries = max_retries if max_retries is not None else settings.openai_max_retries

    last_error: Optional[Exception] = None

    for attempt in range(1, max_retries + 1):
        try:
            return client.chat.completions.create(
                model=model,
                messages=messages,
                timeout=timeout,
            )
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
