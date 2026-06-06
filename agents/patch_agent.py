import contextlib
import json
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

from openai import OpenAI

from config.settings import get_settings
from utils.llm_client import chat_completion_with_retry
from utils.logging import get_logger
from utils.policy import is_path_allowed
from utils.prompts import load_prompt

logger = get_logger("patch_agent")


@dataclass
class FilePatch:
    file_path: str
    new_content: str


class PatchAgent:
    def __init__(self, client: OpenAI | None = None):
        settings = get_settings()
        self.client = client or OpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model
        self.settings = settings

    # ------------------------------------------------------------------
    # Context helpers
    # ------------------------------------------------------------------

    def _collect_context_files(self, primary_files: list[str]) -> dict[str, str]:
        """
        Return {relative_path: content} for every file the LLM should see:
        the primary failing files plus any local modules they import.
        """
        root = Path.cwd()
        context: dict[str, str] = {}

        def _add(path_str: str) -> None:
            p = Path(path_str)
            if not p.is_file() or path_str in context:
                return
            with contextlib.suppress(OSError):
                context[path_str] = p.read_text(encoding="utf-8")
            if path_str not in context:
                logger.debug("Could not read context file: %s", path_str)

        def _resolve_import(module: str) -> None:
            parts = module.split(".")
            for candidate in (
                root.joinpath(*parts).with_suffix(".py"),
                root.joinpath(*parts, "__init__.py"),
            ):
                try:
                    rel = str(candidate.relative_to(root))
                except ValueError:
                    continue
                if is_path_allowed(rel) and candidate.is_file():
                    _add(rel)
                    return

        for file_path in primary_files:
            _add(file_path)
            content = context.get(file_path, "")
            for m in re.finditer(r"^(?:from|import)\s+([\w.]+)", content, re.MULTILINE):
                _resolve_import(m.group(1))

        return context

    def _load_related_source(self, target_file: str) -> str:
        """Load related source module for context (backwards-compat single-file helper)."""
        ctx = self._collect_context_files([target_file])
        ctx.pop(target_file, None)
        return "\n\n".join(f"# {p}\n{c}" for p, c in ctx.items()) if ctx else ""

    # ------------------------------------------------------------------
    # Multi-file patch generation (primary path)
    # ------------------------------------------------------------------

    def generate_multi_patch(
        self,
        failure_context: str,
        target_files: list[str],
        diagnosis: str = "",
    ) -> list[FilePatch]:
        """
        Ask the LLM to repair as many files as needed and return a list of FilePatch.
        Falls back to an empty list on parse failure (caller should use single-file path).
        """
        context_files = self._collect_context_files(target_files)
        if not context_files:
            return []

        files_context = "\n\n".join(
            f"=== {path} ===\n{content}" for path, content in context_files.items()
        )

        prompt = load_prompt(
            "multi_patch",
            {
                "failure_context": failure_context,
                "diagnosis": diagnosis or "No prior diagnosis available.",
                "files_context": files_context,
            },
        )

        logger.info("Generating multi-file patch for %s", target_files)
        response = chat_completion_with_retry(
            self.client,
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.choices[0].message.content or ""
        return self._parse_multi_patch(raw, allowed=set(context_files))

    def _parse_multi_patch(self, raw: str, allowed: set[str]) -> list[FilePatch]:
        text = re.sub(r"```(?:json)?\n?", "", raw).strip().rstrip("`").strip()
        # Pull out the first JSON array in the response
        m = re.search(r"\[.*\]", text, re.DOTALL)
        if not m:
            logger.warning("Multi-patch: no JSON array found in LLM response")
            return []
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError as exc:
            logger.warning("Multi-patch: JSON parse error: %s", exc)
            return []

        patches: list[FilePatch] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            file_path = item.get("file", "").strip()
            new_content = item.get("content", "")
            if not file_path or not isinstance(new_content, str):
                continue
            if file_path not in allowed:
                logger.warning("Multi-patch: LLM proposed disallowed file %r — skipped", file_path)
                continue
            patches.append(FilePatch(file_path=file_path, new_content=new_content))

        logger.info("Multi-patch parsed %d file change(s)", len(patches))
        return patches

    def apply_multi_patch(self, patches: list[FilePatch]) -> list[str]:
        """Apply all patches and return the list of paths that were written."""
        applied: list[str] = []
        for fp in patches:
            self.apply_patch(fp.file_path, fp.new_content)
            applied.append(fp.file_path)
        return applied

    # ------------------------------------------------------------------
    # Single-file patch generation (fallback / backwards compat)
    # ------------------------------------------------------------------

    def generate_patch(
        self,
        failure_context: str,
        target_file: str,
        diagnosis: str = "",
    ) -> str:
        with open(target_file, encoding="utf-8") as f:
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
        cleaned = patch_code.replace("```python", "").replace("```", "").strip()
        target = Path(file_path)
        # Atomic write: write to sibling temp file then replace, avoiding partial writes
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=target.parent,
            prefix=".self_heal_tmp_",
            suffix=target.suffix,
            delete=False,
        ) as tmp:
            tmp.write(cleaned)
            tmp_path = Path(tmp.name)
        tmp_path.replace(target)
        logger.info("Applied patch to %s", file_path)
        return True
