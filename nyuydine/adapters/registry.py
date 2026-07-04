from dataclasses import dataclass, field

from nyuydine.adapters.base import LLMAdapter, PipelineAdapter, RepoAdapter
from nyuydine.adapters.github_pipeline import GitHubActionsAdapter
from nyuydine.adapters.github_repo import GitHubRepoAdapter
from nyuydine.adapters.openai_llm import OpenAILLMAdapter


@dataclass
class AdapterRegistry:
    """Registry of provider adapters for a repair job."""

    pipeline: PipelineAdapter
    repo: RepoAdapter
    llm: LLMAdapter
    extras: dict[str, object] = field(default_factory=dict)


def get_default_registry(
    *,
    token: str,
    owner: str,
    repo: str,
    openai_api_key: str,
    openai_model: str | None = None,
) -> AdapterRegistry:
    """Build the default Phase 1 adapter set (GitHub + OpenAI)."""
    return AdapterRegistry(
        pipeline=GitHubActionsAdapter(token=token, owner=owner, repo=repo),
        repo=GitHubRepoAdapter(token=token, owner=owner, repo=repo),
        llm=OpenAILLMAdapter(api_key=openai_api_key, default_model=openai_model),
    )
