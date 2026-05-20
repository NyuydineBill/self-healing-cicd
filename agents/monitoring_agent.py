from typing import Any, Dict, List, Optional

from config.settings import get_settings
from utils.http_retry import request_with_retry
from utils.logging import get_logger
from utils.secrets import truncate_for_log

logger = get_logger("monitoring_agent")


class MonitoringAgent:
    def __init__(self, settings=None):
        self.settings = settings or get_settings()
        self.github_token = self.settings.github_token
        self.repo_owner = self.settings.github_owner
        self.repo_name = self.settings.github_repo

        self.headers = {
            "Authorization": f"Bearer {self.github_token}",
            "Accept": "application/vnd.github+json",
        }
        self._excluded_names = {
            n.lower() for n in self.settings.excluded_workflow_names
        }

    def _is_excluded_workflow(self, workflow_name: str) -> bool:
        name_lower = workflow_name.lower()
        for excluded in self._excluded_names:
            if excluded in name_lower or name_lower == excluded:
                return True
        return False

    def get_failed_runs(self) -> List[Dict[str, Any]]:
        url = (
            f"https://api.github.com/repos/{self.repo_owner}/"
            f"{self.repo_name}/actions/runs"
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
                "Failed to fetch workflow runs (status=%s): %s",
                response.status_code,
                truncate_for_log(response.text, 500),
            )
            return []

        runs = response.json()["workflow_runs"]
        failed_runs = []

        for run in runs:
            name = run.get("name", "")
            if self._is_excluded_workflow(name):
                logger.debug("Skipping excluded workflow: %s", name)
                continue

            if run["conclusion"] == "failure":
                failed_runs.append({
                    "run_id": run["id"],
                    "name": name,
                    "status": run["status"],
                    "conclusion": run["conclusion"],
                    "created_at": run["created_at"],
                })

        logger.info("Retrieved %d failed run(s)", len(failed_runs))
        return failed_runs

    def get_workflow_logs(self, run_id: int | str) -> Optional[bytes]:
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
