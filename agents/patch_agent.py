from pathlib import Path
from typing import Optional

from openai import OpenAI

from config.settings import get_settings
from utils.llm_client import chat_completion_with_retry
from utils.logging import get_logger
from utils.prompts import load_prompt

logger = get_logger("patch_agent")


class PatchAgent:

    def __init__(self, client: Optional[OpenAI] = None):
        settings = get_settings()
        self.client = client or OpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model
        self.settings = settings

    def _load_related_source(self, target_file: str) -> str:
        """Load related app.py for sample projects when present."""
        path = Path(target_file)
        for part in path.parts:
            if part.startswith("project_"):
                app_path = self.settings.project_root / "sample_projects" / part / "app.py"
                if app_path.is_file():
                    return app_path.read_text(encoding="utf-8")
        return ""

    def generate_patch(
        self,
        failure_context: str,
        target_file: str,
        diagnosis: str = "",
    ) -> str:
        with open(target_file, "r", encoding="utf-8") as f:
            current_file_content = f.read()

        source_context = self._load_related_source(target_file)

        prompt = load_prompt(
            "patch",
            {
                "failure_context": failure_context,
                "diagnosis": diagnosis or "No prior diagnosis available.",
                "target_file": target_file,
                "current_file_content": current_file_content,
                "source_context": source_context or "None available.",
            },
        )

        logger.info("Generating patch for %s", target_file)

        response = chat_completion_with_retry(
            self.client,
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
        )

        return response.choices[0].message.content or ""

    def apply_patch(self, file_path: str, patch_code: str) -> bool:
        cleaned_patch = (
            patch_code.replace("```python", "").replace("```", "").strip()
        )

        with open(file_path, "w", encoding="utf-8") as file:
            file.write(cleaned_patch)

        logger.info("Applied patch to %s", file_path)
        return True
