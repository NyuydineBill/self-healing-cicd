from typing import Any

from config.settings import get_settings
from nyuydine.adapters.base import PipelineAdapter, PipelineRun
from utils.http_retry import request_with_retry
from utils.logging import get_logger
from utils.secrets import truncate_for_log

logger = get_logger("github_pipeline_adapter")


class GitHubActionsAdapter(PipelineAdapter):
    """GitHub Actions implementation of PipelineAdapter."""

    provider = "github_actions"

    def __init__(
        self,
        *,
        token: str,
        owner: str,
        repo: str,
        excluded_workflow_names: tuple[str, ...] | None = None,
        target_workflow_names: tuple[str, ...] | None = None,
        api_max_retries: int | None = None,
    ) -> None:
        settings = get_settings()
        self.owner = owner
        self.repo = repo
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        }
        self._excluded = {
            n.lower() for n in (excluded_workflow_names or settings.excluded_workflow_names)
        }
        self._targets = {
            n.lower() for n in (target_workflow_names or settings.target_workflow_names)
        }
        self._api_max_retries = api_max_retries or settings.github_api_max_retries

    def _repo_base(self) -> str:
        return f"https://api.github.com/repos/{self.owner}/{self.repo}"

    def _normalize_run(self, run: dict[str, Any]) -> PipelineRun:
        return PipelineRun(
            run_id=str(run["id"]),
            name=run.get("name", ""),
            status=run.get("status", ""),
            conclusion=run.get("conclusion"),
            created_at=run.get("created_at"),
            workflow_url=run.get("html_url"),
            metadata={"provider": self.provider},
        )

    def _is_excluded_workflow(self, workflow_name: str) -> bool:
        name_lower = workflow_name.lower()
        return any(ex in name_lower or name_lower == ex for ex in self._excluded)

    def _is_target_workflow(self, workflow_name: str) -> bool:
        if not self._targets:
            return True
        name_lower = workflow_name.lower()
        return any(t in name_lower or name_lower == t for t in self._targets)

    def get_run(self, run_id: str) -> PipelineRun | None:
        url = f"{self._repo_base()}/actions/runs/{run_id}"
        response = request_with_retry(
            "GET",
            url,
            headers=self.headers,
            timeout=30,
            max_retries=self._api_max_retries,
        )
        if response.status_code != 200:
            logger.error(
                "Failed to fetch workflow run %s (status=%s): %s",
                run_id,
                response.status_code,
                truncate_for_log(response.text, 500),
            )
            return None
        payload = response.json()
        if not isinstance(payload, dict):
            return None
        return self._normalize_run(payload)

    def list_failed_runs(self, *, limit: int = 5) -> list[PipelineRun]:
        url = f"{self._repo_base()}/actions/runs"
        response = request_with_retry(
            "GET",
            url,
            headers=self.headers,
            timeout=30,
            max_retries=self._api_max_retries,
        )
        if response.status_code != 200:
            logger.error(
                "Failed to list workflow runs (status=%s): %s",
                response.status_code,
                truncate_for_log(response.text, 500),
            )
            return []

        payload = response.json()
        raw_runs = payload.get("workflow_runs") if isinstance(payload, dict) else None
        runs: list[dict[str, Any]] = [r for r in (raw_runs or []) if isinstance(r, dict)]

        failed: list[PipelineRun] = []
        for run in runs:
            name = run.get("name", "")
            if self._is_excluded_workflow(name):
                continue
            if not self._is_target_workflow(name):
                continue
            if run.get("conclusion") == "failure":
                failed.append(self._normalize_run(run))

        failed.sort(key=lambda r: r.created_at or "", reverse=True)
        return failed[:limit]

    def download_logs(self, run_id: str) -> bytes | None:
        url = f"{self._repo_base()}/actions/runs/{run_id}/logs"
        response = request_with_retry(
            "GET",
            url,
            headers=self.headers,
            timeout=60,
            max_retries=self._api_max_retries,
        )
        if response.status_code != 200:
            logger.error(
                "Failed to download logs for run %s (status=%s)",
                run_id,
                response.status_code,
            )
            return None
        logger.info("Downloaded logs for run %s", run_id)
        return response.content
