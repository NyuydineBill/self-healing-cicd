import os
import requests
from dotenv import load_dotenv

load_dotenv()


class MonitoringAgent:
    def __init__(self):
        self.github_token = os.getenv("GITHUB_TOKEN")
        self.repo_owner = os.getenv("GITHUB_OWNER")
        self.repo_name = os.getenv("GITHUB_REPO")

        self.headers = {
            "Authorization": f"Bearer {self.github_token}",
            "Accept": "application/vnd.github+json"
        }

    def get_failed_runs(self):
        url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/actions/runs"

        response = requests.get(url, headers=self.headers)

        if response.status_code != 200:
            print("Failed to fetch workflow runs")
            print(response.text)
            return []

        runs = response.json()["workflow_runs"]

        failed_runs = []

        for run in runs:
            if run["conclusion"] == "failure":
                failed_runs.append({
                    "run_id": run["id"],
                    "name": run["name"],
                    "status": run["status"],
                    "conclusion": run["conclusion"],
                    "created_at": run["created_at"]
                })

        return failed_runs
    
    def get_workflow_logs(self, run_id):
        url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/actions/runs/{run_id}/logs"

        response = requests.get(url, headers=self.headers)

        if response.status_code != 200:
            print("Failed to fetch workflow logs")
            print(response.text)
            return None

        return response.content