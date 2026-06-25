import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agents.analysis_agent import AnalysisAgent
from agents.monitoring_agent import MonitoringAgent
from agents.patch_agent import PatchAgent
from agents.reasoning_agent import ReasoningAgent
from agents.validation_agent import ValidationAgent
from config.settings import get_settings
from utils.approval import request_patch_approval
from utils.assertion_repair import deterministic_assertion_test_fix
from utils.audit_log import (
    record_patch_applied,
    record_patch_rejected,
    record_pr_opened,
    record_run_outcome,
)
from utils.discovery import discover_all_test_targets
from utils.docker_utils import cleanup_validation_containers
from utils.errors import ErrorCategory, categorize_failure
from utils.failure_memory import FailureMemory
from utils.file_backup import FileBackupManager
from utils.git_repair import GitRepairError, GitRepairManager
from utils.log_extractor import iter_log_files, save_and_extract_logs
from utils.logging import get_logger, set_run_id
from utils.offline_logs import discover_offline_runs, iter_offline_logs
from utils.policy import PolicyViolation, enforce_path_policy, is_path_allowed
from utils.results_store import ResultsStore
from utils.secrets import safe_patch_summary
from utils.validation_scope import resolve_validation_scope

logger = get_logger("orchestrator")


@dataclass
class RepairAttempt:
    attempt: int
    target_file: str
    failure_type: str
    diagnosis: str
    patch: str
    validation: dict[str, Any]
    success: bool


@dataclass
class WorkflowResult:
    run_id: int | str | None = None
    status: str = "no_action"
    message: str = ""
    failure_type: str | None = None
    target_file: str | None = None  # primary failing file (backwards compat)
    target_files: list[str] = field(default_factory=list)  # all files touched
    attempts: list[RepairAttempt] = field(default_factory=list)
    repair_success: bool = False
    git_info: dict[str, Any] | None = None


@dataclass
class BatchWorkflowResult:
    """Aggregated outcome when processing multiple failures."""

    status: str = "no_action"
    message: str = ""
    results: list[WorkflowResult] = field(default_factory=list)

    @property
    def repair_success(self) -> bool:
        return any(r.repair_success for r in self.results)

    @property
    def repairs_succeeded(self) -> int:
        return sum(1 for r in self.results if r.repair_success)


class WorkflowOrchestrator:
    """
    Coordinates multi-agent self-healing workflow with retry management,
    persistent failure memory, and structured result persistence.
    """

    def __init__(
        self,
        monitor: MonitoringAgent | None = None,
        analyzer: AnalysisAgent | None = None,
        reasoner: ReasoningAgent | None = None,
        patcher: PatchAgent | None = None,
        validator: ValidationAgent | None = None,
        failure_memory: FailureMemory | None = None,
        results_store: ResultsStore | None = None,
    ):
        self.settings = get_settings()
        self.monitor = monitor or MonitoringAgent()
        self.analyzer = analyzer or AnalysisAgent()
        self.reasoner = reasoner or ReasoningAgent()
        self.patcher = patcher or PatchAgent()
        self.validator = validator or ValidationAgent()
        self.failure_memory = failure_memory or FailureMemory()
        self.results_store = results_store or ResultsStore()
        self.backup_manager = FileBackupManager()
        self.git_manager: GitRepairManager | None = None
        if self.settings.git_enabled and not self.settings.dry_run:
            try:
                self.git_manager = GitRepairManager()
            except GitRepairError as exc:
                logger.warning("Git integration disabled: %s", exc)
        self.max_retries = self.settings.max_retry_attempts
        self.dry_run = self.settings.dry_run

    def run(self) -> BatchWorkflowResult:
        """Execute the full self-healing pipeline across failed runs."""
        if self.dry_run:
            logger.warning(
                "DRY_RUN enabled: patches will not be written and Docker validation is skipped"
            )
        logger.info("Starting self-healing workflow orchestration")

        if self.settings.offline_mode:
            return self._run_offline()

        failed_runs = self.monitor.get_failed_runs()
        logger.info("Found %d failed workflow run(s)", len(failed_runs))

        sample_test_paths = discover_all_test_targets()
        logger.info("Discovered %d sample test file(s)", len(sample_test_paths))

        if not failed_runs:
            batch = BatchWorkflowResult(
                status="no_failures",
                message="No failed workflow runs detected.",
            )
            self._persist_batch(batch)
            return batch

        all_results: list[WorkflowResult] = []
        runs_to_process = failed_runs[: self.settings.max_failed_runs]

        for run in runs_to_process:
            run_id = run["run_id"]
            logger.info(
                "Processing failed run: %s (%s)",
                run_id,
                run.get("name", "unknown"),
            )

            run_results = self._process_run(
                run_id=run_id,
                sample_test_paths=sample_test_paths,
            )
            self._finalize_git_for_run(run_id, run_results)
            all_results.extend(run_results)

            if self.settings.stop_on_first_success and any(r.repair_success for r in run_results):
                logger.info("Stopping: repair succeeded for run %s", run_id)
                break

            if self.dry_run and any(r.status == "dry_run_complete" for r in run_results):
                break

        if not all_results:
            last_run_id = runs_to_process[-1]["run_id"]
            batch = BatchWorkflowResult(
                status="no_errors_in_logs",
                message="No parseable errors found in workflow logs.",
                results=[
                    WorkflowResult(
                        run_id=last_run_id,
                        status="no_errors_in_logs",
                        message="No parseable errors found in workflow logs.",
                    )
                ],
            )
        else:
            succeeded = sum(1 for r in all_results if r.repair_success)
            batch = BatchWorkflowResult(
                status="completed",
                message=(
                    f"Processed {len(all_results)} failure(s); {succeeded} repaired successfully."
                ),
                results=all_results,
            )

        self._persist_batch(batch)
        return batch

    def _run_offline(self) -> BatchWorkflowResult:
        """Process failures from cached logs under logs/extracted/ (no GitHub API)."""
        logger.info("OFFLINE_MODE: using cached logs only")

        sample_test_paths = discover_all_test_targets()
        offline_runs = discover_offline_runs()[: self.settings.max_failed_runs]

        if not offline_runs:
            batch = BatchWorkflowResult(
                status="no_offline_logs",
                message="No cached runs found under logs/extracted/.",
            )
            self._persist_batch(batch)
            return batch

        all_results: list[WorkflowResult] = []
        for run_id, extract_dir in offline_runs:
            logger.info("Processing offline run: %s", run_id)
            run_results = self._process_offline_run(
                run_id=run_id,
                extract_dir=extract_dir,
                sample_test_paths=sample_test_paths,
            )
            all_results.extend(run_results)

            if self.settings.stop_on_first_success and any(r.repair_success for r in run_results):
                break

        batch = BatchWorkflowResult(
            status="completed",
            message=f"Offline mode: processed {len(all_results)} failure(s).",
            results=all_results,
        )
        self._persist_batch(batch)
        return batch

    def _process_offline_run(
        self,
        *,
        run_id: str,
        extract_dir: Any,
        sample_test_paths: list[str],
    ) -> list[WorkflowResult]:
        set_run_id(run_id)
        results: list[WorkflowResult] = []
        processed_targets: set[tuple[str, str]] = set()
        failures_handled = 0

        for _log_path, log_text in iter_offline_logs(run_id, extract_dir):
            if failures_handled >= self.settings.max_failures_per_run:
                break

            errors = self.analyzer.extract_failure_context(log_text)
            if not errors:
                continue

            target_file = self._resolve_target_file(log_text, sample_test_paths)
            if not target_file:
                logger.warning("Could not resolve target file from offline log for run %s", run_id)
                continue

            try:
                enforce_path_policy(target_file)
            except PolicyViolation as exc:
                logger.warning("%s", exc)
                results.append(
                    WorkflowResult(
                        run_id=run_id,
                        status="policy_rejected",
                        message=str(exc),
                        target_file=target_file,
                    )
                )
                continue

            dedupe_key = (str(run_id), target_file)
            if dedupe_key in processed_targets:
                continue
            processed_targets.add(dedupe_key)

            failure_type = categorize_failure(errors).value
            failing_command = self.analyzer.extract_failing_command(log_text)
            target_files = self._filter_files_to_scope(
                target_file,
                self.analyzer.extract_failed_files(log_text),
            )
            if target_file not in target_files:
                target_files.insert(0, target_file)
            repair_result = self._repair_with_retries(
                run_id=run_id,
                errors=errors,
                target_file=target_file,
                target_files=target_files,
                failure_type=failure_type,
                failing_command=failing_command,
            )
            results.append(repair_result)
            failures_handled += 1

            if repair_result.repair_success and self.settings.stop_on_first_success:
                break

        return results

    def _process_run(
        self,
        *,
        run_id: int | str,
        sample_test_paths: list[str],
    ) -> list[WorkflowResult]:
        """Process all failures found in a single workflow run's logs."""
        set_run_id(run_id)
        results: list[WorkflowResult] = []
        processed_targets: set[tuple[str, str]] = set()

        logs = self.monitor.get_workflow_logs(run_id)
        if not logs:
            results.append(
                WorkflowResult(
                    run_id=run_id,
                    status="log_fetch_failed",
                    message="Could not download workflow logs.",
                )
            )
            return results

        extract_dir = save_and_extract_logs(logs, run_id)
        failures_handled = 0

        for log_path, log_text in iter_log_files(extract_dir):
            if failures_handled >= self.settings.max_failures_per_run:
                logger.info(
                    "Reached MAX_FAILURES_PER_RUN (%d) for run %s",
                    self.settings.max_failures_per_run,
                    run_id,
                )
                break

            # Skip root-level runner/system logs (e.g. 0_test.txt — GitHub runner metadata)
            if Path(log_path).parent == extract_dir:
                logger.debug("Skipping system log: %s", log_path)
                continue

            errors = self.analyzer.extract_failure_context(log_text)
            if not errors:
                continue

            target_file = self._resolve_target_file(log_text, sample_test_paths)
            if not target_file:
                logger.warning(
                    "Could not resolve target file from log: %s | snippet: %.300s",
                    log_path,
                    log_text.replace("\n", " "),
                )
                continue

            try:
                enforce_path_policy(target_file)
            except PolicyViolation as exc:
                logger.warning("%s", exc)
                results.append(
                    WorkflowResult(
                        run_id=run_id,
                        status="policy_rejected",
                        message=str(exc),
                        target_file=target_file,
                    )
                )
                continue

            dedupe_key = (str(run_id), target_file)
            if dedupe_key in processed_targets:
                logger.debug("Skipping duplicate target %s for run %s", target_file, run_id)
                continue
            processed_targets.add(dedupe_key)

            failure_type = categorize_failure(errors).value
            failing_command = self.analyzer.extract_failing_command(log_text)
            target_files = self._filter_files_to_scope(
                target_file,
                self.analyzer.extract_failed_files(log_text),
            )
            if target_file not in target_files:
                target_files.insert(0, target_file)
            logger.info(
                "Failure detected | type=%s | files=%s | command=%r | log=%s",
                failure_type,
                target_files,
                failing_command,
                log_path,
            )

            repair_result = self._repair_with_retries(
                run_id=run_id,
                errors=errors,
                target_file=target_file,
                target_files=target_files,
                failure_type=failure_type,
                failing_command=failing_command,
            )
            results.append(repair_result)
            failures_handled += 1

            if repair_result.repair_success and self.settings.stop_on_first_success:
                break
            if self.dry_run and repair_result.status == "dry_run_complete":
                break

        return results

    def _resolve_target_file(self, log_text: str, sample_test_paths: list[str]) -> str | None:
        # Prefer sample_projects failures over framework tests/ paths in the same log.
        sample_prefix = f"{self.settings.sample_projects_dir}/"
        for path in self.analyzer.extract_failed_files(log_text):
            normalized = path.replace("\\", "/")
            if normalized.startswith(sample_prefix):
                return path

        # 1. Parser + LLM pattern matching
        target_file = self.analyzer.extract_failed_file(log_text)

        # 2. Broad scan: any .py path in the log that passes policy AND exists on disk
        if not target_file:
            target_file = self._broad_file_search(log_text)

        # 3. Basename match against discovered test files
        if not target_file:
            for path in sample_test_paths:
                if os.path.basename(path) in log_text:
                    target_file = path
                    break

        # 4. Last resort: first discovered test file
        if not target_file and sample_test_paths:
            target_file = sample_test_paths[0]

        return target_file

    def _filter_files_to_scope(self, primary: str, files: list[str]) -> list[str]:
        """Keep only files under the same repair scope as the primary failure."""
        scope = resolve_validation_scope(primary, self.settings.sample_projects_dir)
        if not scope:
            return files
        prefix = f"{scope}/"
        scoped = [f for f in files if f.startswith(prefix)]
        if primary not in scoped:
            scoped.insert(0, primary)
        elif scoped[0] != primary:
            scoped.remove(primary)
            scoped.insert(0, primary)
        if len(scoped) < len(files):
            logger.info(
                "Scoped repair files to %s: %s (dropped %d unrelated path(s))",
                scope,
                scoped,
                len(files) - len(scoped),
            )
        return scoped

    def _broad_file_search(self, log_text: str) -> str | None:
        """Find any relative .py path in the log that passes path policy."""
        candidates: list[str] = []
        for match in re.finditer(r"\b((?:[\w][\w.-]*/)+[\w.-]+\.py)\b", log_text):
            path = match.group(1)
            if is_path_allowed(path):
                candidates.append(path)
        if candidates:
            logger.info("Broad file search candidates: %s", candidates)
            return candidates[0]
        return None

    def _repair_with_retries(
        self,
        *,
        run_id: int | str,
        errors: list[str],
        target_file: str,
        target_files: list[str] | None = None,
        failure_type: str,
        failing_command: str | None = None,
    ) -> WorkflowResult:
        failure_context = "\n".join(errors)
        attempts: list[RepairAttempt] = []
        all_files = target_files or [target_file]

        if self.settings.backup_before_patch and not self.dry_run:
            self.backup_manager.backup_originals(all_files, run_id)

        for attempt in range(1, self.max_retries + 1):
            logger.info(
                "Repair attempt %d/%d | primary=%s | files=%s",
                attempt,
                self.max_retries,
                target_file,
                all_files,
            )

            diagnosis = ""
            patch = ""
            applied_files: list[str] = []

            try:
                diagnosis = self.reasoner.diagnose_failure(
                    failure_context,
                    failure_type=failure_type,
                )
                logger.debug("Diagnosis received (%d chars)", len(diagnosis) if diagnosis else 0)

                if self.dry_run:
                    # Dry-run: generate patch for primary file only (no writes)
                    patch = self.patcher.generate_patch(
                        failure_context,
                        target_file=target_file,
                        diagnosis=diagnosis,
                    )
                    logger.info(
                        "[DRY_RUN] Would patch %s — %s",
                        all_files,
                        safe_patch_summary(patch),
                    )
                    validation = {
                        "status": "dry_run",
                        "output": "Patch not applied; validation skipped.",
                        "category": None,
                    }
                else:
                    # --- approval gate (primary file only for the diff preview) ---
                    with open(target_file, encoding="utf-8") as f:
                        original_content = f.read()

                    from agents.patch_agent import FilePatch

                    fixed_content = (
                        deterministic_assertion_test_fix(target_file, failure_context)
                        if len(all_files) == 1
                        else None
                    )
                    if fixed_content:
                        logger.info("Using deterministic assertion repair for %s", target_file)
                        patches = [FilePatch(file_path=target_file, new_content=fixed_content)]
                    elif len(all_files) == 1:
                        patch = self.patcher.generate_patch(
                            failure_context,
                            target_file=target_file,
                            diagnosis=diagnosis,
                        )
                        patches = [FilePatch(file_path=target_file, new_content=patch)]
                    else:
                        patches = self.patcher.generate_multi_patch(
                            failure_context,
                            target_files=all_files,
                            diagnosis=diagnosis,
                        )

                    # Fall back to single-file patch if multi-patch returned nothing
                    if not patches:
                        logger.info("Multi-patch returned empty; falling back to single-file patch")
                        patch = self.patcher.generate_patch(
                            failure_context,
                            target_file=target_file,
                            diagnosis=diagnosis,
                        )
                        patches = [FilePatch(file_path=target_file, new_content=patch)]

                    patch = patches[0].new_content  # for approval preview / logging

                    logger.debug(
                        "Generated patch(es) for %d file(s): %s",
                        len(patches),
                        safe_patch_summary(patch, self.settings.log_patch_preview_chars),
                    )

                    if not request_patch_approval(
                        target_file,
                        original_content,
                        patch,
                        run_id=run_id,
                    ):
                        validation = {
                            "status": "approval_denied",
                            "output": "Operator or policy denied patch application.",
                            "category": None,
                        }
                        record_patch_rejected(
                            run_id=run_id,
                            target_file=target_file,
                            reason="approval_denied",
                            attempt=attempt,
                        )
                    else:
                        if self.settings.backup_before_patch:
                            self.backup_manager.backup_before_attempts(all_files, run_id, attempt)
                        applied_files = self.patcher.apply_multi_patch(patches)
                        validation = self.validator.validate_patch(
                            target_file=target_file,
                            failing_command=failing_command,
                        )
                        if validation.get("status") == "failed":
                            output = validation.get("output", "")
                            logger.warning(
                                "Validation failed on attempt %d — last 1200 chars:\n%s",
                                attempt,
                                output[-1200:] if output else "(no output)",
                            )

            except Exception as exc:
                logger.error(
                    "Repair attempt %d failed with exception: %s",
                    attempt,
                    exc,
                    exc_info=True,
                )
                validation = {
                    "status": "error",
                    "output": str(exc),
                    "category": ErrorCategory.RUNTIME.value,
                }

            success = validation.get("status") == "success"
            dry_run_complete = self.dry_run and validation.get("status") == "dry_run"

            if not success and not self.dry_run and self.settings.backup_before_patch:
                self.backup_manager.restore_originals(all_files, run_id)

            repair_attempt = RepairAttempt(
                attempt=attempt,
                target_file=target_file,
                failure_type=failure_type,
                diagnosis=diagnosis,
                patch=patch,
                validation=validation,
                success=success,
            )
            attempts.append(repair_attempt)

            self.failure_memory.record_repair(
                run_id=run_id,
                failure_type=failure_type,
                target_file=target_file,
                diagnosis=diagnosis,
                generated_patch=patch,
                validation_outcome=validation,
                attempt=attempt,
                success=success,
            )

            if dry_run_complete:
                logger.info("Dry-run complete on attempt %d (no files modified)", attempt)
                return WorkflowResult(
                    run_id=run_id,
                    status="dry_run_complete",
                    message="Dry-run finished: diagnosis and patch generated without applying.",
                    failure_type=failure_type,
                    target_file=target_file,
                    target_files=all_files,
                    attempts=attempts,
                    repair_success=False,
                )

            if success:
                repaired_files = applied_files or all_files
                logger.info(
                    "Repair succeeded on attempt %d — %d file(s) changed",
                    attempt,
                    len(repaired_files),
                )
                record_patch_applied(
                    run_id=run_id,
                    target_file=target_file,
                    patch_summary=safe_patch_summary(patch),
                    attempt=attempt,
                )
                record_run_outcome(
                    run_id=run_id,
                    success=True,
                    total_attempts=attempt,
                    target_file=target_file,
                )
                if self.settings.backup_before_patch:
                    self.backup_manager.clear_run_backups_list(repaired_files, run_id)
                cleanup_validation_containers()
                git_info = self._git_commit_repair(
                    run_id=run_id,
                    target_files=repaired_files,
                    failure_type=failure_type,
                    attempt=attempt,
                )
                return WorkflowResult(
                    run_id=run_id,
                    status="repaired",
                    message=f"Repair succeeded on attempt {attempt} ({len(repaired_files)} file(s) changed).",
                    failure_type=failure_type,
                    target_file=target_file,
                    target_files=repaired_files,
                    attempts=attempts,
                    repair_success=True,
                    git_info=git_info,
                )

            logger.warning(
                "Repair attempt %d failed (status=%s)",
                attempt,
                validation.get("status"),
            )
            record_patch_rejected(
                run_id=run_id,
                target_file=target_file,
                reason=f"validation_{validation.get('status', 'unknown')}",
                attempt=attempt,
            )
            failure_context = self._enrich_context_for_retry(
                failure_context, validation, failing_command=failing_command
            )

        if not self.dry_run:
            cleanup_validation_containers()
            if self.settings.backup_before_patch:
                self.backup_manager.restore_originals(all_files, run_id)
                logger.info("Restored %d original file(s) after exhausted retries", len(all_files))

        record_run_outcome(
            run_id=run_id,
            success=False,
            total_attempts=self.max_retries,
            target_file=target_file,
        )
        return WorkflowResult(
            run_id=run_id,
            status="repair_failed",
            message=f"All {self.max_retries} repair attempts exhausted.",
            failure_type=failure_type,
            target_file=target_file,
            target_files=all_files,
            attempts=attempts,
            repair_success=False,
        )

    def _git_commit_repair(
        self,
        *,
        run_id: int | str,
        target_files: list[str],
        failure_type: str,
        attempt: int,
    ) -> dict[str, Any] | None:
        if not self.git_manager:
            return None
        try:
            branch = self.git_manager.commit_repair(
                run_id=run_id,
                target_files=target_files,
                failure_type=failure_type,
                attempt=attempt,
            )
            return {"branch": branch, "committed": True}
        except (GitRepairError, Exception) as exc:
            logger.error("Git commit failed: %s", exc, exc_info=True)
            return {"status": "failed", "error": str(exc)}

    def _finalize_git_for_run(
        self,
        run_id: int | str,
        results: list[WorkflowResult],
    ) -> None:
        if not self.git_manager:
            return

        repaired = [r for r in results if r.repair_success and r.target_file]
        if not repaired:
            return

        # Prefer the expanded target_files list; fall back to target_file
        files = list(
            dict.fromkeys(
                f
                for r in repaired
                for f in (r.target_files if r.target_files else [r.target_file or ""])
                if f
            )
        )
        git_result = self.git_manager.finalize_run(run_id, files)

        for result in repaired:
            result.git_info = {**(result.git_info or {}), **git_result}

        if git_result.get("pr_url"):
            logger.info("Pull request: %s", git_result["pr_url"])
            for result in repaired:
                record_pr_opened(
                    run_id=run_id,
                    pr_url=git_result["pr_url"],
                    branch=git_result.get("branch", ""),
                    target_file=result.target_file or "",
                )

    def _enrich_context_for_retry(
        self,
        failure_context: str,
        validation: dict[str, Any],
        failing_command: str | None = None,
    ) -> str:
        output = validation.get("output", "")
        status = validation.get("status", "unknown")
        scope = validation.get("scope", "unknown")
        cmd_line = f"Validation command: {failing_command}\n" if failing_command else ""
        return (
            f"{failure_context}\n\n"
            f"Previous repair attempt failed validation.\n"
            f"Validation status: {status}\n"
            f"Validation scope: {scope}\n"
            f"{cmd_line}"
            f"Validation output:\n{output[:2000]}"
        )

    def _persist_batch(self, batch: BatchWorkflowResult) -> None:
        for result in batch.results:
            self._persist_result(result)

        self.results_store.save_metrics(
            {
                "batch_status": batch.status,
                "batch_message": batch.message,
                "dry_run": self.dry_run,
                "failures_processed": len(batch.results),
                "repair_success": batch.repair_success,
                "repairs_succeeded": batch.repairs_succeeded,
            }
        )

    def _persist_result(self, result: WorkflowResult) -> None:
        payload = {
            "status": result.status,
            "message": result.message,
            "dry_run": self.dry_run,
            "failure_type": result.failure_type,
            "target_file": result.target_file,
            "repair_success": result.repair_success,
            "git_info": result.git_info,
            "attempts": [
                {
                    "attempt": a.attempt,
                    "target_file": a.target_file,
                    "failure_type": a.failure_type,
                    "validation_status": a.validation.get("status"),
                    "validation_scope": a.validation.get("scope"),
                    "success": a.success,
                }
                for a in result.attempts
            ],
            "repair_history": self.failure_memory.get_repair_history(result.run_id),
        }

        if result.run_id is not None:
            self.results_store.save_run_result(result.run_id, payload)
