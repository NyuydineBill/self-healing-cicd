import re

from openai import OpenAI

from config.settings import get_settings
from parsers import get_parser
from utils.llm_client import chat_completion_with_retry
from utils.logging import get_logger

logger = get_logger("analysis_agent")

# Ordered from most to least specific
_CMD_PATTERNS = [
    r"##\[group\]Run\s+(.+)",  # GitHub Actions step "Run <cmd>"
    r"\[command\](.+)",  # GitHub Actions [command] full-path binary
    r"^\+\s+(.+)",  # set -x shell trace
]

# Commands safe to replay in CI validation
_SAFE_COMMAND_BASES = {
    "pytest",
    "python",
    "python3",
    "ruff",
    "flake8",
    "pylint",
    "mypy",
    "tsc",
    "npx",
    "npm",
    "node",
    "go",
    "cargo",
    "make",
    "pip",
    "uv",
    "black",
    "isort",
}

# Patterns that disqualify a command as unsafe to replay
_UNSAFE_RE = re.compile(
    r"\brm\b|\brmdir\b|git\s+push|docker\s+push|kubectl\s+delete"
    r"|--force|>\s*/|&&\s*rm\b|\bsudo\b|\bdrop\b|\btruncate\b",
    re.IGNORECASE,
)


class AnalysisAgent:
    def extract_failure_context(self, log_text: str) -> list[str]:
        parser = get_parser(log_text)
        logger.debug("Using log parser: %s", parser.language)
        errors = parser.extract_failure_context(log_text)
        if errors:
            logger.debug(
                "Extracted %d error line(s) via %s parser",
                len(errors),
                parser.language,
            )
        return errors

    def extract_failed_file(self, log_text: str) -> str | None:
        parser = get_parser(log_text)
        result = parser.extract_failed_file(log_text)
        if result:
            return result
        logger.debug("Pattern matching found no target file; trying LLM fallback")
        return self._llm_identify_file(log_text)

    def extract_failed_files(self, log_text: str) -> list[str]:
        """
        Return every file involved in the failure, not just the primary one.
        Includes imported modules mentioned in the traceback so the LLM can
        see — and fix — the root cause even when it lives in a different file.
        """
        seen: dict[str, None] = {}  # ordered deduplication

        # 1. All File "..." paths in the traceback
        for m in re.finditer(r'File\s+"([^"]+\.py)"', log_text):
            path = m.group(1)
            # Normalise absolute paths to relative if possible
            for prefix in ("./", "/"):
                if path.startswith(prefix):
                    path = path[len(prefix) :]
            # Only keep paths that look like repo-relative (no leading /usr, /opt …)
            if not path.startswith("/") and "/" in path:
                seen[path] = None

        # 2. FAILED test lines (pytest short form)
        for m in re.finditer(r"FAILED\s+([\w./\\-]+\.py)", log_text):
            seen[m.group(1)] = None

        # 3. ImportError / ModuleNotFoundError — extract the module's file path
        for m in re.finditer(r"(?:ImportError|ModuleNotFoundError)[^\n]*\(([^)]+\.py)\)", log_text):
            seen[m.group(1)] = None

        # 4. Always include the single primary file (LLM fallback) as a safety net
        primary = self.extract_failed_file(log_text)
        if primary:
            seen[primary] = None

        files = list(seen.keys())
        logger.info("Identified %d file(s) for repair: %s", len(files), files)
        return files

    def extract_failing_command(self, log_text: str) -> str | None:
        """
        Extract the CI command that failed so ValidationAgent can replay it.
        Returns a shell-safe command string or None if nothing reliable is found.
        """
        # 1. Try structured log patterns first
        for pattern in _CMD_PATTERNS:
            for m in re.finditer(pattern, log_text, re.MULTILINE):
                cmd = m.group(1).strip()
                if self._is_replayable(cmd):
                    logger.info("Extracted failing command: %r", cmd)
                    return cmd

        # 2. Scan for known test/lint runner invocations anywhere in the log
        for runner in (
            "pytest",
            "ruff check",
            "ruff",
            "mypy",
            "flake8",
            "pylint",
            "npm test",
            "npm run test",
            "go test",
            "cargo test",
        ):
            pattern = rf"(?:^|\s){re.escape(runner)}(\s+[^\n]*)?"
            match = re.search(pattern, log_text, re.MULTILINE)
            if match:
                cmd = (runner + (match.group(1) or "")).strip()
                if self._is_replayable(cmd):
                    logger.info("Extracted failing command (runner scan): %r", cmd)
                    return cmd

        return None

    def _is_replayable(self, cmd: str) -> bool:
        if not cmd or len(cmd) < 3:
            return False
        if _UNSAFE_RE.search(cmd):
            return False
        # Strip full path to get the binary name
        binary = cmd.split()[0].split("/")[-1].split("\\")[-1].lower()
        base = binary[:-4] if binary.endswith(".exe") else binary
        return base in _SAFE_COMMAND_BASES

    def _llm_identify_file(self, log_text: str) -> str | None:
        settings = get_settings()
        if not settings.openai_api_key:
            return None
        client = OpenAI(
            api_key=settings.openai_api_key,
            timeout=settings.openai_timeout,
            max_retries=settings.openai_max_retries,
        )
        truncated = log_text[-4000:]
        try:
            resp = chat_completion_with_retry(
                client,
                model=settings.openai_model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a CI failure analyst. "
                            "Return ONLY the relative path of the Python source file that "
                            "needs to be fixed to resolve the test failure (e.g. tests/test_foo.py). "
                            "If you cannot determine the file, return the single word UNKNOWN."
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"From this CI log, what Python file needs to be fixed?\n\nLog:\n{truncated}",
                    },
                ],
                timeout=settings.openai_timeout,
            )
            file_path = resp.choices[0].message.content.strip()
            logger.info("LLM file identification response: %r", file_path)
            if (
                file_path
                and file_path != "UNKNOWN"
                and file_path.endswith(".py")
                and "/" in file_path
            ):
                logger.info("LLM identified target file: %s", file_path)
                return file_path
        except Exception as exc:
            logger.warning("LLM file identification failed: %s", exc)
        return None
