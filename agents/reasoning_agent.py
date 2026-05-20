from typing import Optional

from openai import OpenAI

from config.settings import get_settings
from utils.llm_client import chat_completion_with_retry
from utils.logging import get_logger
from utils.prompts import load_prompt

logger = get_logger("reasoning_agent")


class ReasoningAgent:

    def __init__(self, client: Optional[OpenAI] = None):
        settings = get_settings()
        self.client = client or OpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model

    def diagnose_failure(
        self,
        failure_context: str,
        failure_type: str = "unknown",
    ) -> str:
        prompt = load_prompt(
            "diagnosis",
            {
                "failure_context": failure_context,
                "failure_type": failure_type,
            },
        )

        logger.info("Requesting LLM diagnosis (failure_type=%s)", failure_type)

        response = chat_completion_with_retry(
            self.client,
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
        )

        diagnosis = response.choices[0].message.content or ""
        logger.info("Diagnosis complete (%d chars)", len(diagnosis))
        return diagnosis
