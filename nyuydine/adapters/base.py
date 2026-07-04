from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AutomationMode(str, Enum):
    """How much autonomy the repair engine has for an organization."""

    OBSERVATION = "observation"  # diagnose only (dry run)
    SUGGEST = "suggest"  # patch + require approval, no PR
    AUTO_PR = "auto_pr"  # auto-approve + open PR


@dataclass
class PipelineRun:
    """Provider-neutral representation of a CI pipeline run."""

    run_id: str
    name: str
    status: str
    conclusion: str | None
    created_at: str | None = None
    workflow_url: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class PipelineAdapter(ABC):
    """Fetch and monitor CI/CD pipeline runs (GitHub Actions first)."""

    provider: str

    @abstractmethod
    def get_run(self, run_id: str) -> PipelineRun | None:
        """Fetch a single pipeline run by provider id."""

    @abstractmethod
    def list_failed_runs(self, *, limit: int = 5) -> list[PipelineRun]:
        """List recent failed runs for the configured repository."""

    @abstractmethod
    def download_logs(self, run_id: str) -> bytes | None:
        """Download raw log archive for a run."""

    def is_repairable(self, run: PipelineRun) -> bool:
        return run.conclusion == "failure"


class RepoAdapter(ABC):
    """Clone and interact with source repositories (GitHub first)."""

    provider: str

    @abstractmethod
    def clone(self, destination: str, *, branch: str | None = None) -> None:
        """Clone repository into destination directory."""

    @abstractmethod
    def default_branch(self) -> str:
        """Return the repository default branch name."""


class LLMAdapter(ABC):
    """Interchangeable LLM provider for diagnosis and patching."""

    provider: str

    @abstractmethod
    def chat_completion(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        timeout: float | None = None,
    ) -> str:
        """Return assistant message content from a chat completion."""
