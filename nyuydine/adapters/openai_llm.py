from openai import OpenAI

from config.settings import get_settings
from nyuydine.adapters.base import LLMAdapter
from utils.llm_client import chat_completion_with_retry
from utils.logging import get_logger

logger = get_logger("openai_llm_adapter")


class OpenAILLMAdapter(LLMAdapter):
    """OpenAI implementation of LLMAdapter."""

    provider = "openai"

    def __init__(self, *, api_key: str | None = None, default_model: str | None = None) -> None:
        settings = get_settings()
        self.api_key = api_key or settings.openai_api_key
        self.default_model = default_model or settings.openai_model
        self._client = OpenAI(api_key=self.api_key)

    def chat_completion(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        timeout: float | None = None,
    ) -> str:
        settings = get_settings()
        response = chat_completion_with_retry(
            self._client,
            model=model or self.default_model,
            messages=messages,
            timeout=timeout or settings.openai_timeout,
        )
        content = response.choices[0].message.content or ""
        if not content:
            logger.warning("OpenAI returned empty completion")
        return content
