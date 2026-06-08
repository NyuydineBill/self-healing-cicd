#!/usr/bin/env python3
"""
Experiment runner for self-healing CI/CD thesis evaluation.

For each sample project:
  1. Breaks the project (introduces the known failure).
  2. Captures the real pytest failure output locally.
  3. Wraps it in GitHub Actions log format and saves to logs/extracted/.
  4. Runs the orchestrator in offline mode to repair it.
  5. Validates the repair.
  6. Records timing, attempts, and outcome to results/experiment_results.json.
  7. Resets the project back to golden state.

Usage:
    python scripts/run_experiments.py             # all projects (1-10, broken by script)
    python scripts/run_experiments.py 1 3 4       # specific projects
    python scripts/run_experiments.py --projects-only 11 12 13 14  # already-broken projects

Requires: OPENAI_API_KEY in .env  (no GitHub token needed — offline mode)
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
LOGS_EXTRACTED = ROOT / "logs" / "extracted"
RESULTS_DIR = ROOT / "results"
EXPERIMENT_RESULTS = RESULTS_DIR / "experiment_results.json"

# Projects broken by break-sample.sh (1-10)
SCRIPTABLE_PROJECTS = list(range(1, 11))
# Projects whose failure is their permanent "broken" state (already wrong by design)
DESIGN_BROKEN_PROJECTS = list(range(11, 16))

FAILURE_LABELS = {
    1: "AssertionError",
    2: "ImportError",
    3: "SyntaxError",
    4: "Logic bug (wrong result)",
    5: "ModuleNotFoundError",
    6: "AttributeError",
    7: "NameError",
    8: "IndexError",
    9: "TypeError",
    10: "ZeroDivisionError",
    11: "Multi-file ImportError",
    12: "Wrong exception type",
    13: "Off-by-one error",
    14: "Type coercion TypeError",
    15: "Retry recovery (cascading)",
}


def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def run(cmd: list[str], cwd: Path | None = None, capture: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=cwd or ROOT,
        capture_output=capture,
        text=True,
    )


def break_project(n: int) -> bool:
    """Use break-sample.sh to introduce the known failure for project n (1-10)."""
    result = run(["bash", "scripts/break-sample.sh", str(n)])
    return result.returncode == 0


def reset_projects() -> None:
    run(["bash", "scripts/reset-samples.sh"])


def capture_pytest_failure(n: int) -> str | None:
    """Run pytest against the broken project and return the output."""
    result = run(
        [
            "python", "-m", "pytest",
            f"sample_projects/project_{n}/",
            "-v", "--tb=short", "--no-header", "--no-cov",
        ],
        capture=True,
    )
    # Failure is expected (returncode != 0)
    output = result.stdout + result.stderr
    # Project is broken if pytest reports FAILED or an error (not just coverage fail)
    if "FAILED" not in output and "ERROR" not in output and "Error" not in output:
        print(f"  WARNING: project_{n} appears to be passing — check break step.")
        return None
    return output


def write_fake_log(run_id: str, project_n: int, pytest_output: str) -> Path:
    """
    Write a GitHub Actions-style log file so offline mode can process it.
    Format mirrors what the real GitHub Actions runner produces.
    """
    extract_dir = LOGS_EXTRACTED / run_id
    extract_dir.mkdir(parents=True, exist_ok=True)

    ts = "2026-06-06T10:00:00.0000000Z"
    cmd = f"pytest sample_projects/project_{project_n}/ -v --tb=short"
    lines = [
        f"{ts} ##[group]Run {cmd}",
        f"{ts} {cmd}",
    ]
    for line in pytest_output.splitlines():
        lines.append(f"{ts} {line}")
    lines.append(f"{ts} ##[endgroup]")

    log_path = extract_dir / f"0_test_project_{project_n}.txt"
    log_path.write_text("\n".join(lines), encoding="utf-8")
    return extract_dir


def run_orchestrator(run_id: str) -> tuple[bool, int, float, str]:
    """
    Run the orchestrator in offline mode against a specific run_id.
    Returns (success, attempts, elapsed_seconds, status).
    """
    env = os.environ.copy()
    env.update({
        "OFFLINE_MODE": "true",
        "DRY_RUN": "false",
        "GIT_ENABLED": "false",
        "AUTO_APPROVE_PATCHES": "true",
        "REQUIRE_APPROVAL": "false",
        "LOG_LEVEL": "INFO",
    })

    # Isolate: temporarily rename every other extracted run directory so the
    # orchestrator only sees the one log we created for this experiment.
    stashed: list[tuple[Path, Path]] = []
    for d in LOGS_EXTRACTED.iterdir():
        if d.is_dir() and d.name != run_id:
            hidden = d.with_name(f"_stashed_{d.name}")
            d.rename(hidden)
            stashed.append((hidden, d))

    start = time.monotonic()
    result = subprocess.run(
        ["python", "main.py"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    elapsed = time.monotonic() - start

    # Restore stashed directories
    for hidden, original in stashed:
        hidden.rename(original)

    # Primary: parse the result JSON written by the orchestrator
    for f in sorted(RESULTS_DIR.glob(f"run_{run_id}_*.json"), reverse=True):
        try:
            data = json.loads(f.read_text())
            success = bool(data.get("repair_success"))
            attempts = len(data.get("attempts", [])) or 1
            status = data.get("status", "unknown")
            return success, attempts, elapsed, status
        except Exception:  # nosec B110
            pass

    # Fallback: scan captured output
    output = result.stdout + result.stderr
    success = "| repaired |" in output and "success=True" in output
    attempts = max(output.count("Attempt "), 1)
    status = "repaired" if success else "repair_failed"
    return success, attempts, elapsed, status


def verify_repair(n: int) -> bool:
    """Run pytest to confirm the project passes after repair."""
    result = run(
        [
            "python", "-m", "pytest",
            f"sample_projects/project_{n}/",
            "--no-cov", "-q", "--no-header",
        ],
        capture=True,
    )
    return result.returncode == 0


def cleanup_fake_log(run_id: str) -> None:
    d = LOGS_EXTRACTED / run_id
    if d.exists():
        shutil.rmtree(d)


def run_experiment(n: int, is_design_broken: bool = False) -> dict:
    log(f"{'=' * 60}")
    log(f"PROJECT {n}: {FAILURE_LABELS.get(n, 'Unknown')} {'(design-broken)' if is_design_broken else ''}")

    result_entry: dict = {
        "project": n,
        "failure_type": FAILURE_LABELS.get(n, "unknown"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "break_succeeded": False,
        "pytest_failure_captured": False,
        "repair_success": False,
        "repair_verified": False,
        "attempts": 0,
        "elapsed_seconds": 0.0,
        "status": "not_run",
        "notes": "",
    }

    # Step 1: break the project (or confirm it's already broken)
    if not is_design_broken:
        log(f"  Breaking project_{n}...")
        if not break_project(n):
            log(f"  SKIP: break-sample.sh failed for project_{n}")
            result_entry["notes"] = "break script failed"
            return result_entry
    result_entry["break_succeeded"] = True

    # Step 2: capture the real pytest failure output
    log(f"  Capturing pytest failure output for project_{n}...")
    failure_output = capture_pytest_failure(n)
    if not failure_output:
        log(f"  SKIP: project_{n} is not actually failing")
        result_entry["notes"] = "project not failing after break"
        if not is_design_broken:
            reset_projects()
        return result_entry
    result_entry["pytest_failure_captured"] = True
    log(f"  Failure captured ({len(failure_output)} chars).")

    # Step 3: write fake GitHub Actions log
    run_id = f"exp_{n:03d}"
    log(f"  Writing fake log (run_id={run_id})...")
    write_fake_log(run_id, n, failure_output)

    # Step 4: run orchestrator in offline mode
    log(f"  Running orchestrator (offline, auto-approve)...")
    try:
        success, attempts, elapsed, status = run_orchestrator(run_id)
    except subprocess.TimeoutExpired:
        log("  TIMEOUT: orchestrator exceeded 5 minutes")
        result_entry["notes"] = "orchestrator timeout"
        cleanup_fake_log(run_id)
        if not is_design_broken:
            reset_projects()
        return result_entry

    result_entry.update({
        "repair_success": success,
        "attempts": attempts,
        "elapsed_seconds": round(elapsed, 1),
        "status": status,
    })
    log(f"  Orchestrator done: success={success}, attempts={attempts}, elapsed={elapsed:.1f}s, status={status}")

    # Step 5: verify repair
    if success:
        log(f"  Verifying repair with pytest...")
        verified = verify_repair(n)
        result_entry["repair_verified"] = verified
        log(f"  Verification: {'PASS' if verified else 'FAIL (patch did not fix test)'}")
    else:
        log(f"  Repair failed — skipping verification.")

    # Step 6: cleanup
    cleanup_fake_log(run_id)
    if not is_design_broken:
        log(f"  Resetting project_{n} to golden state...")
        reset_projects()

    return result_entry


def print_summary(results: list[dict]) -> None:
    print("\n" + "=" * 70)
    print("EXPERIMENT SUMMARY")
    print("=" * 70)
    header = f"{'#':<4} {'Failure Type':<28} {'Success':<9} {'Attempts':<10} {'Time(s)':<9} {'Verified'}"
    print(header)
    print("-" * 70)
    for r in results:
        success_str = "YES" if r["repair_success"] else "NO"
        verified_str = "YES" if r.get("repair_verified") else ("—" if not r["repair_success"] else "NO")
        print(
            f"{r['project']:<4} {r['failure_type']:<28} {success_str:<9} "
            f"{r['attempts']:<10} {r['elapsed_seconds']:<9} {verified_str}"
        )
    print("-" * 70)
    succeeded = sum(1 for r in results if r["repair_success"])
    verified = sum(1 for r in results if r.get("repair_verified"))
    total = len(results)
    if total:
        avg_time = sum(r["elapsed_seconds"] for r in results if r["repair_success"]) / max(succeeded, 1)
        avg_attempts = sum(r["attempts"] for r in results if r["repair_success"]) / max(succeeded, 1)
        print(f"\nTotal:            {total} projects")
        print(f"Repaired:         {succeeded}/{total} ({100 * succeeded // total}%)")
        print(f"Verified passing: {verified}/{total}")
        print(f"Avg repair time:  {avg_time:.1f}s (successful repairs only)")
        print(f"Avg attempts:     {avg_attempts:.1f} (successful repairs only)")


def main() -> None:
    args = sys.argv[1:]

    # Determine which projects to run
    design_only = "--projects-only" in args
    if design_only:
        args.remove("--projects-only")

    if args:
        try:
            projects = [int(a) for a in args]
        except ValueError:
            print("Usage: python scripts/run_experiments.py [project_numbers...]")
            sys.exit(1)
    elif design_only:
        projects = DESIGN_BROKEN_PROJECTS
    else:
        projects = SCRIPTABLE_PROJECTS + DESIGN_BROKEN_PROJECTS

    # Ensure required env
    if not os.environ.get("OPENAI_API_KEY"):
        # Try loading .env
        env_file = ROOT / ".env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith("OPENAI_API_KEY=") and "=" in line:
                    key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if key and not key.startswith("sk-your"):
                        os.environ["OPENAI_API_KEY"] = key
                        break

    if not os.environ.get("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY not set. Add it to .env or export it.")
        sys.exit(1)

    LOGS_EXTRACTED.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    results: list[dict] = []
    for n in projects:
        is_design = n in DESIGN_BROKEN_PROJECTS
        entry = run_experiment(n, is_design_broken=is_design)
        results.append(entry)
        # Save incrementally so partial runs are not lost
        EXPERIMENT_RESULTS.write_text(json.dumps({"experiments": results}, indent=2))
        print()

    # Final summary
    print_summary(results)
    print(f"\nFull results saved to: {EXPERIMENT_RESULTS}")


if __name__ == "__main__":
    main()
