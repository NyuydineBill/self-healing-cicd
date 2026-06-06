from unittest.mock import MagicMock, patch

import pytest

from orchestrator.workflow import WorkflowOrchestrator


class MockMonitor:
    def get_failed_runs(self):
        return [
            {"run_id": 101, "name": "CI", "conclusion": "failure"},
            {"run_id": 102, "name": "CI", "conclusion": "failure"},
        ]

    def get_workflow_logs(self, run_id):
        return b"fake-zip" if run_id == 101 else None


class MockAnalyzer:
    def extract_failure_context(self, log_text):
        if "ERROR_A" in log_text:
            return ["AssertionError: A"]
        if "ERROR_B" in log_text:
            return ["ImportError: B"]
        return []

    def extract_failed_file(self, log_text):
        if "project_1" in log_text:
            return "sample_projects/project_1/test_a.py"
        if "project_2" in log_text:
            return "sample_projects/project_2/test_b.py"
        return None

    def extract_failing_command(self, log_text):
        return None


class MockReasoner:
    def diagnose_failure(self, failure_context, failure_type="unknown"):
        return f"diagnosis for {failure_type}"


class MockPatcher:
    def generate_patch(self, failure_context, target_file, diagnosis=""):
        return f"# patched {target_file}"

    def apply_patch(self, file_path, patch_code):
        return True


class MockValidator:
    def validate_patch(self, target_file=None):
        return {"status": "success", "output": "ok", "scope": target_file}


@pytest.fixture
def orchestrator(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setenv("DRY_RUN", "true")
    monkeypatch.setenv("MAX_FAILED_RUNS", "2")
    monkeypatch.setenv("MAX_FAILURES_PER_RUN", "5")
    monkeypatch.setenv("STOP_ON_FIRST_SUCCESS", "true")

    import config.settings as settings_module

    settings_module._settings = None

    return WorkflowOrchestrator(
        monitor=MockMonitor(),
        analyzer=MockAnalyzer(),
        reasoner=MockReasoner(),
        patcher=MockPatcher(),
        validator=MockValidator(),
        failure_memory=MagicMock(),
        results_store=MagicMock(),
    )


@patch("orchestrator.workflow.save_and_extract_logs")
@patch("orchestrator.workflow.iter_log_files")
def test_processes_multiple_log_failures(mock_iter, mock_save, orchestrator, monkeypatch):
    monkeypatch.setenv("DRY_RUN", "false")
    monkeypatch.setenv("BACKUP_BEFORE_PATCH", "false")
    monkeypatch.setenv("STOP_ON_FIRST_SUCCESS", "false")

    orchestrator.monitor = MockMonitor()
    orchestrator.monitor.get_failed_runs = lambda: [
        {"run_id": 101, "name": "CI", "conclusion": "failure"},
    ]
    orchestrator.dry_run = False
    orchestrator.settings.backup_before_patch = False
    orchestrator.settings.stop_on_first_success = False

    mock_save.return_value = "/tmp/logs"
    mock_iter.return_value = [
        ("/tmp/a.log", "ERROR_A project_1"),
        ("/tmp/b.log", "ERROR_B project_2"),
    ]

    batch = orchestrator.run()

    assert batch.status == "completed"
    assert len(batch.results) == 2
    assert batch.results[0].target_file.endswith("test_a.py")
    assert batch.results[1].target_file.endswith("test_b.py")


@patch("orchestrator.workflow.save_and_extract_logs")
@patch("orchestrator.workflow.iter_log_files")
def test_deduplicates_same_target_per_run(mock_iter, mock_save, orchestrator):
    mock_save.return_value = "/tmp/logs"
    mock_iter.return_value = [
        ("/tmp/a.log", "ERROR_A project_1"),
        ("/tmp/c.log", "ERROR_A project_1 again"),
    ]

    batch = orchestrator.run()

    assert len(batch.results) == 1


@patch("orchestrator.workflow.save_and_extract_logs")
@patch("orchestrator.workflow.iter_log_files")
def test_no_failures_returns_empty_batch(mock_iter, mock_save, orchestrator):
    orchestrator.monitor = MagicMock()
    orchestrator.monitor.get_failed_runs.return_value = []

    batch = orchestrator.run()

    assert batch.status == "no_failures"
    assert batch.results == []


@patch("orchestrator.workflow.save_and_extract_logs")
@patch("orchestrator.workflow.iter_log_files")
def test_dry_run_completes_without_apply(mock_iter, mock_save, orchestrator):
    mock_save.return_value = "/tmp/logs"
    mock_iter.return_value = [("/tmp/a.log", "ERROR_A project_1")]
    orchestrator.patcher = MagicMock(spec=["generate_patch", "apply_patch"])
    orchestrator.patcher.generate_patch.return_value = "# patch"
    orchestrator.reasoner = MagicMock()
    orchestrator.reasoner.diagnose_failure.return_value = "diag"

    batch = orchestrator.run()

    assert batch.results[0].status == "dry_run_complete"
    orchestrator.patcher.apply_patch.assert_not_called()
