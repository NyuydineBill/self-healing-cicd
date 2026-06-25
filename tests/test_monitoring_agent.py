from unittest.mock import MagicMock, patch

from agents.monitoring_agent import MonitoringAgent


def _settings(**overrides):
    base = MagicMock()
    base.github_token = "token"
    base.github_owner = "owner"
    base.github_repo = "repo"
    base.github_api_max_retries = 1
    base.excluded_workflow_names = ("Self-Heal on Failure",)
    base.target_workflow_names = ()
    base.github_trigger_run_id = ""
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


def test_get_failed_runs_uses_trigger_run_only():
    settings = _settings(github_trigger_run_id="12345", target_workflow_names=("Test Pipeline",))
    agent = MonitoringAgent(settings)
    run_payload = {
        "id": 12345,
        "name": "Test Pipeline",
        "status": "completed",
        "conclusion": "failure",
        "created_at": "2026-06-25T14:00:00Z",
    }

    with patch("agents.monitoring_agent.request_with_retry") as mock_request:
        mock_request.return_value.status_code = 200
        mock_request.return_value.json.return_value = run_payload

        runs = agent.get_failed_runs()

    assert len(runs) == 1
    assert runs[0]["run_id"] == 12345
    assert mock_request.call_count == 1


def test_get_failed_runs_filters_target_workflows():
    settings = _settings(target_workflow_names=("Test Pipeline",))
    agent = MonitoringAgent(settings)
    list_payload = {
        "workflow_runs": [
            {
                "id": 1,
                "name": "Self-Heal on Failure",
                "status": "completed",
                "conclusion": "failure",
                "created_at": "2026-06-25T13:00:00Z",
            },
            {
                "id": 2,
                "name": "Test Pipeline",
                "status": "completed",
                "conclusion": "failure",
                "created_at": "2026-06-25T14:00:00Z",
            },
            {
                "id": 3,
                "name": "Other Workflow",
                "status": "completed",
                "conclusion": "failure",
                "created_at": "2026-06-25T15:00:00Z",
            },
        ]
    }

    with patch("agents.monitoring_agent.request_with_retry") as mock_request:
        mock_request.return_value.status_code = 200
        mock_request.return_value.json.return_value = list_payload

        runs = agent.get_failed_runs()

    assert [r["run_id"] for r in runs] == [2]
