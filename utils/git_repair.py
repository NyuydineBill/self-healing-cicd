from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests
from git import Actor, GitCommandError, InvalidGitRepositoryError, Repo

from config.settings import get_settings
from utils.logging import get_logger
from utils.secrets import mask_secrets

logger = get_logger("git_repair")


class GitRepairError(Exception):
    """Raised when git repair operations fail."""


class GitRepairManager:
    """
    Create repair branches, commit fixes, push, and open pull requests.
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self.repo_path = Path.cwd()  # repo being healed, not the installed package root
        self._repo: Repo | None = None
        self._active_branches: dict[str, str] = {}
        if self.settings.git_create_pr:
            self._warn_if_pr_blocked()

    def _warn_if_pr_blocked(self) -> None:
        """
        Probe the GitHub API early so users get a clear, actionable message
        instead of a silent failure at the end of the run.
        """
        if not self.settings.github_owner or not self.settings.github_repo:
            return
        try:
            resp = requests.get(
                f"https://api.github.com/repos/{self.settings.github_owner}"
                f"/{self.settings.github_repo}",
                headers={
                    "Authorization": f"Bearer {self.settings.github_pr_token}",
                    "Accept": "application/vnd.github+json",
                },
                timeout=10,
            )
            if resp.status_code != 200:
                logger.warning(
                    "GitHub API probe failed (status=%s) — PR creation may not work",
                    resp.status_code,
                )
                return

            # GITHUB_TOKEN responses carry X-OAuth-Scopes; PATs carry repo/workflow scopes.
            # An empty scope string on a GITHUB_TOKEN is normal — it has implicit scopes
            # defined by the job's `permissions:` block.  We can't reliably detect the
            # Actions "allow PRs" setting remotely, so emit a one-time advisory instead.
            token = self.settings.github_pr_token or ""
            if len(token) < 40 or token.startswith("ghp_") or token.startswith("github_pat_"):
                return  # PAT — no restriction to warn about

            logger.info(
                "PR creation is enabled. If PRs fail with 403, go to repo "
                "Settings → Actions → General and enable "
                "'Allow GitHub Actions to create and approve pull requests'."
            )
        except Exception:  # nosec B110
            pass  # non-critical probe; never block the main flow

    @property
    def repo(self) -> Repo:
        if self._repo is None:
            try:
                self._repo = Repo(self.repo_path)
            except InvalidGitRepositoryError as exc:
                raise GitRepairError(f"Not a git repository: {self.repo_path}") from exc
        return self._repo

    def _branch_name(self, run_id: int | str) -> str:
        timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
        prefix = self.settings.git_branch_prefix
        return f"{prefix}/run-{run_id}-{timestamp}"

    def begin_run(self, run_id: int | str) -> str:
        """Create and checkout a repair branch for a workflow run."""
        if str(run_id) in self._active_branches:
            return self._active_branches[str(run_id)]

        branch = self._branch_name(run_id)
        repo = self.repo

        if branch in repo.heads:
            repo.git.checkout(branch)
        else:
            # Branch from current HEAD so validated patches stay in the working tree
            repo.git.checkout("-b", branch)

        self._active_branches[str(run_id)] = branch
        logger.info(
            "Checked out repair branch %s (PR base=%s)",
            branch,
            self.settings.git_base_branch,
        )
        return branch

    def _commit_message(
        self,
        *,
        target_files: list[str],
        run_id: int | str,
        failure_type: str,
        attempt: int,
    ) -> str:
        """Build commit message; include DCO Signed-off-by when enabled."""
        subject = (
            f"fix(self-heal): repair {target_files[0]}"
            if len(target_files) == 1
            else f"fix(self-heal): repair {len(target_files)} files"
        )
        lines = [
            subject,
            "",
            f"Run: {run_id}",
            f"Failure type: {failure_type}",
            f"Attempt: {attempt}",
        ]
        if len(target_files) > 1:
            lines.append("")
            lines.extend(f"  - {f}" for f in target_files)
        if self.settings.git_sign_off:
            lines.extend(
                [
                    "",
                    f"Signed-off-by: {self.settings.git_author_name} "
                    f"<{self.settings.git_author_email}>",
                ]
            )
        return "\n".join(lines)

    def commit_repair(
        self,
        *,
        run_id: int | str,
        target_files: list[str],
        failure_type: str,
        attempt: int,
    ) -> str:
        """Stage and commit a validated multi-file repair."""
        branch = self.begin_run(run_id)
        repo = self.repo

        for f in target_files:
            repo.git.add(f)

        message = self._commit_message(
            target_files=target_files,
            run_id=run_id,
            failure_type=failure_type,
            attempt=attempt,
        )

        if not repo.index.diff("HEAD") and not repo.untracked_files:
            logger.warning("No changes to commit for %s", target_files)
            return branch

        author = Actor(
            self.settings.git_author_name,
            self.settings.git_author_email,
        )
        commit = repo.index.commit(
            message,
            author=author,
            committer=author,
        )
        logger.info(
            "Committed repair on %s (%s) — %d file(s)",
            branch,
            commit.hexsha[:8],
            len(target_files),
        )
        return branch

    def push_branch(self, branch: str) -> None:
        remote_name = self.settings.git_push_remote
        repo = self.repo
        remote = repo.remote(remote_name)

        push_url = (
            f"https://x-access-token:{self.settings.github_token}"
            f"@github.com/{self.settings.github_owner}"
            f"/{self.settings.github_repo}.git"
        )

        original_url = remote.url
        try:
            remote.set_url(push_url)
            with repo.git.custom_environment(GIT_TERMINAL_PROMPT="0"):
                remote.push(refspec=f"{branch}:{branch}")
        except GitCommandError as exc:
            raise GitRepairError(
                f"Failed to push branch {branch}: {mask_secrets(str(exc))}"
            ) from exc
        finally:
            remote.set_url(original_url)

        logger.info("Pushed branch %s to %s", branch, remote_name)

    def create_pull_request(
        self,
        *,
        branch: str,
        run_id: int | str,
        repaired_files: list[str],
    ) -> str | None:
        if not self.settings.git_create_pr:
            return None

        url = (
            f"https://api.github.com/repos/{self.settings.github_owner}/"
            f"{self.settings.github_repo}/pulls"
        )
        title = f"[self-heal] Repair CI failure (run {run_id})"
        body = (
            "## Self-healing CI/CD repair\n\n"
            f"Automated repair for failed workflow run `{run_id}`.\n\n"
            "### Files changed\n" + "\n".join(f"- `{f}`" for f in repaired_files) + "\n\n"
            "_Generated by the self-healing orchestrator._"
        )

        token = self.settings.github_pr_token
        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
            },
            json={
                "title": title,
                "head": branch,
                "base": self.settings.git_base_branch,
                "body": body,
            },
            timeout=30,
        )

        if response.status_code not in (200, 201):
            detail = mask_secrets(response.text[:500])
            if response.status_code == 403 and "pull request" in detail.lower():
                logger.error(
                    "Failed to create PR (403): GitHub Actions cannot open PRs with "
                    "the default token. Fix: enable 'Allow GitHub Actions to create "
                    "and approve pull requests' in repo Settings → Actions → General, "
                    "or set GITHUB_PR_TOKEN secret to a PAT with repo scope. Branch "
                    "was pushed: %s",
                    branch,
                )
            else:
                logger.error(
                    "Failed to create PR (status=%s): %s",
                    response.status_code,
                    detail,
                )
            return None

        pr_url = response.json().get("html_url")
        logger.info("Created pull request: %s", pr_url)
        return pr_url

    def finalize_run(
        self,
        run_id: int | str,
        repaired_files: list[str],
    ) -> dict[str, Any]:
        """Push branch and optionally open a pull request."""
        branch = self._active_branches.get(str(run_id))
        if not branch:
            return {"status": "skipped", "reason": "no_branch"}

        result: dict[str, Any] = {
            "status": "success",
            "branch": branch,
            "pr_url": None,
        }

        try:
            self.push_branch(branch)
            result["pr_url"] = self.create_pull_request(
                branch=branch,
                run_id=run_id,
                repaired_files=repaired_files,
            )
        except GitRepairError as exc:
            logger.error("Git finalize failed: %s", exc)
            result["status"] = "failed"
            result["error"] = str(exc)

        return result
