import os
from urllib.parse import quote

from git import Repo

from nyuydine.adapters.base import RepoAdapter
from utils.http_retry import request_with_retry
from utils.logging import get_logger

logger = get_logger("github_repo_adapter")


class GitHubRepoAdapter(RepoAdapter):
    """Clone and inspect GitHub repositories."""

    provider = "github"

    def __init__(self, *, token: str, owner: str, repo: str) -> None:
        self.owner = owner
        self.repo = repo
        self.token = token
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        }

    def _clone_url(self) -> str:
        # x-access-token works for GitHub App installation tokens and PATs.
        safe_token = quote(self.token, safe="")
        return f"https://x-access-token:{safe_token}@github.com/{self.owner}/{self.repo}.git"

    def clone(self, destination: str, *, branch: str | None = None) -> None:
        os.makedirs(destination, exist_ok=True)
        logger.info("Cloning %s/%s into %s", self.owner, self.repo, destination)
        kwargs: dict = {"depth": 1}
        if branch:
            kwargs["branch"] = branch
        Repo.clone_from(self._clone_url(), destination, **kwargs)

    def default_branch(self) -> str:
        url = f"https://api.github.com/repos/{self.owner}/{self.repo}"
        response = request_with_retry(
            "GET",
            url,
            headers=self._headers,
            timeout=30,
            max_retries=3,
        )
        if response.status_code == 200:
            payload = response.json()
            if isinstance(payload, dict) and payload.get("default_branch"):
                return str(payload["default_branch"])
        return "main"
