import zipfile

from agents.monitoring_agent import MonitoringAgent
from agents.analysis_agent import AnalysisAgent
from agents.reasoning_agent import ReasoningAgent
from agents.patch_agent import PatchAgent
from agents.validation_agent import ValidationAgent 


monitor = MonitoringAgent()
analyzer = AnalysisAgent()
reasoner = ReasoningAgent()
patcher = PatchAgent()
validator = ValidationAgent()

failed_runs = monitor.get_failed_runs()

print("Failed Workflow Runs:", failed_runs)

if failed_runs:

    run_id = failed_runs[0]["run_id"]

    logs = monitor.get_workflow_logs(run_id)

    if logs:

        zip_path = "logs/workflow_logs.zip"

        with open(zip_path, "wb") as f:
            f.write(logs)

        print("Workflow logs downloaded successfully.")

        with zipfile.ZipFile(zip_path, 'r') as zip_ref:

            zip_ref.extractall("logs/extracted")

            for file_name in zip_ref.namelist():

                with open(f"logs/extracted/{file_name}", "r", errors="ignore") as log_file:

                    log_text = log_file.read()

                    errors = analyzer.extract_failure_context(log_text)

                    if errors:
                        diagnosis = reasoner.diagnose_failure(
                            "\n".join(errors)
                        )
                        print("LLM Diagnosis:", diagnosis)

                        patch = patcher.generate_patch(
                            "\n".join(errors)
                        )
                        print("Generated Patch:", patch)
                        patcher.apply_patch(
                            "sample_projects/project_1/test_app.py",
                            patch
                        )


                        validation_result = validator.validate_patch()
                        print("Validation Result:", validation_result)