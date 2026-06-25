from typing import Any

from config.settings import get_settings
from utils.http_retry import request_with_retry
from utils.logging import get_logger
from utils.secrets import truncate_for_log

logger = get_logger("monitoring_agent")


class MonitoringAgent:
    def __init__(self, settings: Any = None) -> None:
        self.settings = settings or get_settings()
        self.github_token = self.settings.github_token
        self.repo_owner = self.settings.github_owner
        self.repo_name = self.settings.github_repo

        self.headers = {
            "Authorization": f"Bearer {self.github_token}",
            "Accept": "application/vnd.github+json",
        }
        self._excluded_names = {n.lower() for n in self.settings.excluded_workflow_names}
        self._target_names = {n.lower() for n in self.settings.target_workflow_names}

    def _is_excluded_workflow(self, workflow_name: str) -> bool:
        name_lower = workflow_name.lower()
        for excluded in self._excluded_names:
            if excluded in name_lower or name_lower == excluded:
                return True
        return False

    def _is_target_workflow(self, workflow_name: str) -> bool:
        if not self._target_names:
            return True
        name_lower = workflow_name.lower()
        return any(target in name_lower or name_lower == target for target in self._target_names)

    def _normalize_run(self, run: dict[str, Any]) -> dict[str, Any]:
        return {
            "run_id": run["id"],
            "name": run.get("name", ""),
            "status": run.get("status"),
            "conclusion": run.get("conclusion"),
            "created_at": run.get("created_at"),
        }

    def _get_run(self, run_id: int | str) -> dict[str, Any] | None:
        url = (
            f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/actions/runs/{run_id}"
        )
        response = request_with_retry(
            "GET",
            url,
            headers=self.headers,
            timeout=30,
            max_retries=self.settings.github_api_max_retries,
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

    def get_failed_runs(self) -> list[dict[str, Any]]:
        trigger_id = self.settings.github_trigger_run_id
        if trigger_id:
            logger.info("Processing trigger run only: %s", trigger_id)
            run = self._get_run(trigger_id)
            if not run:
                return []
            name = run.get("name", "")
            if self._is_excluded_workflow(name):
                logger.warning("Trigger run %s is an excluded workflow: %s", trigger_id, name)
                return []
            if not self._is_target_workflow(name):
                logger.warning("Trigger run %s is not a target workflow: %s", trigger_id, name)
                return []
            if run.get("conclusion") != "failure":
                logger.warning(
                    "Trigger run %s conclusion is %s (not failure)",
                    trigger_id,
                    run.get("conclusion"),
                )
                return []
            return [run]

        url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/actions/runs"

        response = request_with_retry(
            "GET",
            url,
            headers=self.headers,
            timeout=30,
            max_retries=self.settings.github_api_max_retries,
        )

        if response.status_code != 200:
            logger.error(
                "Failed to fetch workflow runs (status=%s): %s",
                response.status_code,
                truncate_for_log(response.text, 500),
            )
            return []

        payload = response.json()
        raw_runs = payload.get("workflow_runs") if isinstance(payload, dict) else None
        runs: list[dict[str, Any]] = [item for item in (raw_runs or []) if isinstance(item, dict)]
        failed_runs: list[dict[str, Any]] = []

        for run in runs:
            name = run.get("name", "")
            if self._is_excluded_workflow(name):
                logger.debug("Skipping excluded workflow: %s", name)
                continue
            if not self._is_target_workflow(name):
                logger.debug("Skipping non-target workflow: %s", name)
                continue

            if run.get("conclusion") == "failure":
                failed_runs.append(self._normalize_run(run))

        failed_runs.sort(key=lambda r: r.get("created_at", ""), reverse=True)
        logger.info("Retrieved %d failed run(s)", len(failed_runs))
        return failed_runs

    def get_workflow_logs(self, run_id: int | str) -> bytes | None:
        url = (
            f"https://api.github.com/repos/{self.repo_owner}/"
            f"{self.repo_name}/actions/runs/{run_id}/logs"
        )

        response = request_with_retry(
            "GET",
            url,
            headers=self.headers,
            timeout=60,
            max_retries=self.settings.github_api_max_retries,
        )

        if response.status_code != 200:
            logger.error(
                "Failed to fetch workflow logs for run %s (status=%s)",
                run_id,
                response.status_code,
            )
            return None

        logger.info("Downloaded logs for run %s", run_id)
        return response.content
