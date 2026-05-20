import time
from typing import Any, Optional

import requests

from config.settings import get_settings
from utils.logging import get_logger
from utils.secrets import truncate_for_log

logger = get_logger("http_retry")

_RETRYABLE_STATUS = {403, 429, 500, 502, 503, 504}


def request_with_retry(
    method: str,
    url: str,
    *,
    max_retries: Optional[int] = None,
    timeout: float = 30,
    **kwargs: Any,
) -> requests.Response:
    """HTTP request with exponential backoff on rate limits and server errors."""
    settings = get_settings()
    max_retries = max_retries or settings.github_api_max_retries
    last_response: Optional[requests.Response] = None

    for attempt in range(1, max_retries + 1):
        response = requests.request(method, url, timeout=timeout, **kwargs)
        last_response = response

        if response.status_code not in _RETRYABLE_STATUS:
            return response

        if attempt >= max_retries:
            logger.error(
                "GitHub API %s %s failed after %d attempts (status=%s)",
                method,
                url,
                max_retries,
                response.status_code,
            )
            return response

        retry_after = response.headers.get("Retry-After")
        delay = int(retry_after) if retry_after and retry_after.isdigit() else min(
            2 ** attempt, 60
        )
        logger.warning(
            "GitHub API status %s; retry %d/%d in %ds — %s",
            response.status_code,
            attempt,
            max_retries,
            delay,
            truncate_for_log(response.text, 200),
        )
        time.sleep(delay)

    return last_response  # type: ignore[return-value]
