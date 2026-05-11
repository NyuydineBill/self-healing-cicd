import os
import zipfile

from agents.monitoring_agent import MonitoringAgent
from agents.analysis_agent import AnalysisAgent
from agents.reasoning_agent import ReasoningAgent
from agents.patch_agent import PatchAgent
from agents.validation_agent import ValidationAgent


def discover_sample_tests(base_dir="sample_projects"):

    sample_tests = []

    if not os.path.isdir(base_dir):
        return sample_tests

    for project_name in sorted(os.listdir(base_dir)):

        project_dir = os.path.join(
            base_dir,
            project_name
        )

        if not os.path.isdir(project_dir):
            continue

        for root, _, files in os.walk(project_dir):

            for filename in sorted(files):

                if (
                    filename.startswith("test_")
                    and filename.endswith(".py")
                ):

                    sample_tests.append(
                        os.path.join(root, filename)
                    )

    return sample_tests


monitor = MonitoringAgent()
analyzer = AnalysisAgent()
reasoner = ReasoningAgent()
patcher = PatchAgent()
validator = ValidationAgent()


failed_runs = monitor.get_failed_runs()

print("Failed Workflow Runs:", failed_runs)


sample_test_paths = discover_sample_tests()

print(
    "Discovered sample test files:",
    sample_test_paths
)


if failed_runs:

    run_id = failed_runs[0]["run_id"]

    logs = monitor.get_workflow_logs(run_id)

    if logs:

        os.makedirs("logs", exist_ok=True)

        zip_path = "logs/workflow_logs.zip"

        with open(zip_path, "wb") as f:
            f.write(logs)

        print(
            "Workflow logs downloaded successfully."
        )

        with zipfile.ZipFile(
            zip_path,
            "r"
        ) as zip_ref:

            zip_ref.extractall(
                "logs/extracted"
            )

            for file_name in zip_ref.namelist():

                extracted_path = os.path.join(
                    "logs/extracted",
                    file_name
                )

                if not os.path.isfile(
                    extracted_path
                ):
                    continue

                with open(
                    extracted_path,
                    "r",
                    errors="ignore"
                ) as log_file:

                    log_text = log_file.read()

                    errors = analyzer.extract_failure_context(
                        log_text
                    )

                    if not errors:
                        continue

                    # Detect actual failed file
                    target_file = analyzer.extract_failed_file(
                        log_text
                    )

                    # Fallback: try matching test files
                    if not target_file:

                        for path in sample_test_paths:

                            if (
                                os.path.basename(path)
                                in log_text
                            ):

                                target_file = path
                                break

                    # Final fallback
                    if (
                        not target_file
                        and sample_test_paths
                    ):

                        target_file = sample_test_paths[0]

                    print(
                        "Detected failed file:",
                        target_file
                    )

                    if target_file:

                        diagnosis = reasoner.diagnose_failure(
                            "\n".join(errors)
                        )

                        print(
                            "LLM Diagnosis:",
                            diagnosis
                        )

                        patch = patcher.generate_patch(
                            "\n".join(errors),
                            target_file=target_file
                        )

                        print(
                            "Generated Patch:",
                            patch
                        )

                        print(
                            "Applying patch to:",
                            target_file
                        )

                        patcher.apply_patch(
                            target_file,
                            patch
                        )

                        validation_result = validator.validate_patch()

                        print(
                            "Validation Result:",
                            validation_result
                        )

                        break