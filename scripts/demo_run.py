#!/usr/bin/env python3
"""
Demo runner for thesis evidence screenshots.

Runs one sample project end-to-end with all agent output streaming live.
After each stage a clear banner is printed so you can screenshot each piece.

Usage:
    python scripts/demo_run.py           # default: project 1 (AssertionError)
    python scripts/demo_run.py 3         # SyntaxError
    python scripts/demo_run.py 6         # AttributeError
    python scripts/demo_run.py 10        # ZeroDivisionError
    python scripts/demo_run.py 11        # Multi-file ImportError

Evidence stages produced:
    1. Pytest failure output  — "Monitoring agent detecting failed workflow"
    2. Orchestrator live logs — Analysis agent, LLM diagnosis, patch generation,
                                validation success
    3. Diagnosis + patch text — printed from result JSON after the run
    4. Pytest verification    — proof the repair worked
    5. Summary table          — timing / attempts / status
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
    11: "Multi-file ImportError (design-broken)",
    12: "Wrong exception type (design-broken)",
    13: "Off-by-one error (design-broken)",
    14: "Type coercion TypeError (design-broken)",
    15: "Retry recovery — cascading hidden bug (design-broken)",
}

DESIGN_BROKEN = {11, 12, 13, 14, 15}

# ANSI colours
_RESET = "\033[0m"
_BOLD = "\033[1m"
_CYAN = "\033[96m"
_GREEN = "\033[92m"
_YELLOW = "\033[93m"
_RED = "\033[91m"
_MAGENTA = "\033[95m"
_WHITE = "\033[97m"
_BG_BLUE = "\033[44m"
_BG_GREEN = "\033[42m"
_BG_RED = "\033[41m"


def banner(stage: int, total: int, title: str, colour: str = _CYAN) -> None:
    width = 70
    pad = " " * ((width - len(title) - 4) // 2)
    line = "=" * width
    print(f"\n{_BOLD}{colour}{line}{_RESET}")
    print(f"{_BOLD}{colour}  STAGE {stage}/{total}  {pad}{title}{_RESET}")
    print(f"{_BOLD}{colour}{line}{_RESET}\n")


def section(title: str, colour: str = _YELLOW) -> None:
    print(f"\n{_BOLD}{colour}── {title} {'─' * (60 - len(title))}{_RESET}\n")


def run(cmd: list[str], capture: bool = True, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=ROOT,
        capture_output=capture,
        text=True,
        env=env,
    )


def write_fake_log(run_id: str, project_n: int, pytest_output: str) -> None:
    extract_dir = LOGS_EXTRACTED / run_id
    extract_dir.mkdir(parents=True, exist_ok=True)
    ts = "2026-06-06T10:00:00.0000000Z"
    cmd = f"pytest sample_projects/project_{project_n}/ -v --tb=short"
    lines = [f"{ts} ##[group]Run {cmd}", f"{ts} {cmd}"]
    for line in pytest_output.splitlines():
        lines.append(f"{ts} {line}")
    lines.append(f"{ts} ##[endgroup]")
    (extract_dir / f"0_test_project_{project_n}.txt").write_text(
        "\n".join(lines), encoding="utf-8"
    )


def cleanup_fake_log(run_id: str) -> None:
    d = LOGS_EXTRACTED / run_id
    if d.exists():
        shutil.rmtree(d)


def stash_other_logs(run_id: str) -> list[tuple[Path, Path]]:
    stashed: list[tuple[Path, Path]] = []
    for d in LOGS_EXTRACTED.iterdir():
        if d.is_dir() and d.name != run_id:
            hidden = d.with_name(f"_stashed_{d.name}")
            d.rename(hidden)
            stashed.append((hidden, d))
    return stashed


def restore_stashed(stashed: list[tuple[Path, Path]]) -> None:
    for hidden, original in stashed:
        if hidden.exists():
            hidden.rename(original)


def load_env() -> None:
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if k and v and k not in os.environ:
                    os.environ[k] = v


def main() -> None:
    # Force unbuffered output so stage banners appear before subprocess logs
    sys.stdout.reconfigure(write_through=True)  # type: ignore[attr-defined]
    load_env()

    if not os.environ.get("OPENAI_API_KEY"):
        print(f"{_RED}ERROR: OPENAI_API_KEY not set. Add it to .env or export it.{_RESET}")
        sys.exit(1)

    # Pick project
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    label = FAILURE_LABELS.get(n, "Unknown")
    is_design_broken = n in DESIGN_BROKEN
    run_id = f"demo_{n:03d}"

    total_stages = 5

    print(f"\n{_BOLD}{_BG_BLUE}{'':^70}{_RESET}")
    print(f"{_BOLD}{_BG_BLUE}{'  SELF-HEALING CI/CD — LIVE DEMO':^70}{_RESET}")
    print(f"{_BOLD}{_BG_BLUE}{f'  Project {n}: {label}':^70}{_RESET}")
    print(f"{_BOLD}{_BG_BLUE}{'':^70}{_RESET}\n")

    # ── STAGE 1: Introduce / confirm the failure ───────────────────────────
    banner(1, total_stages, "MONITORING AGENT — detecting failed workflow", _CYAN)
    section("Breaking project (introducing known failure)")

    if not is_design_broken:
        r = run(["bash", "scripts/break-sample.sh", str(n)])
        if r.returncode != 0:
            print(f"{_RED}break-sample.sh failed — aborting.{_RESET}")
            sys.exit(1)
        print(f"  {_GREEN}✓ Failure introduced into project_{n}{_RESET}")
    else:
        print(f"  {_YELLOW}Project {n} is permanently broken by design (no break step needed){_RESET}")

    section("Pytest failure output (what the CI runner sees)")
    failure_result = run(
        [
            "python", "-m", "pytest",
            f"sample_projects/project_{n}/",
            "-v", "--tb=short", "--no-header", "--no-cov",
        ],
        capture=True,
    )
    failure_output = failure_result.stdout + failure_result.stderr
    print(failure_output)

    if "FAILED" not in failure_output and "ERROR" not in failure_output and "Error" not in failure_output:
        print(f"{_RED}WARNING: project_{n} does not appear to be failing. Aborting.{_RESET}")
        sys.exit(1)

    # ── STAGE 2: Write GitHub Actions log ─────────────────────────────────
    banner(2, total_stages, "ANALYSIS AGENT — extracting failure context", _MAGENTA)
    section("Packaging pytest output as GitHub Actions log format")
    write_fake_log(run_id, n, failure_output)
    log_path = LOGS_EXTRACTED / run_id / f"0_test_project_{n}.txt"
    print(f"  Log written to: {log_path.relative_to(ROOT)}")
    print(f"  Size: {log_path.stat().st_size} bytes\n")

    # Show the first few lines of the fake log
    lines = log_path.read_text().splitlines()
    for line in lines[:6]:
        print(f"  {_WHITE}{line}{_RESET}")
    if len(lines) > 6:
        print(f"  {_WHITE}  … ({len(lines) - 6} more lines){_RESET}")

    # ── STAGE 3: Run orchestrator (streaming) ─────────────────────────────
    banner(3, total_stages, "ORCHESTRATOR — LLM diagnosis + patch generation + validation", _YELLOW)
    section("Starting orchestrator (LOG_LEVEL=INFO — all agent logs visible below)")
    sys.stdout.flush()
    sys.stderr.flush()

    env = os.environ.copy()
    env.update({
        "OFFLINE_MODE": "true",
        "DRY_RUN": "false",
        "GIT_ENABLED": "false",
        "AUTO_APPROVE_PATCHES": "true",
        "REQUIRE_APPROVAL": "false",
        "LOG_LEVEL": "INFO",
    })

    stashed = stash_other_logs(run_id)
    start = time.monotonic()

    # Stream orchestrator output directly to terminal (no capture)
    # -u disables Python's own output buffering inside the subprocess
    proc = subprocess.run(
        ["python", "-u", "main.py"],
        cwd=ROOT,
        env=env,
        timeout=300,
    )

    elapsed = time.monotonic() - start
    restore_stashed(stashed)
    cleanup_fake_log(run_id)

    # ── STAGE 4: Show LLM diagnosis + generated patch from result JSON ─────
    banner(4, total_stages, "LLM OUTPUT — diagnosis and generated patch", _GREEN)

    result_files = sorted(RESULTS_DIR.glob(f"run_{run_id}_*.json"), reverse=True)
    if not result_files:
        # Fallback: check any recent result file
        result_files = sorted(RESULTS_DIR.glob("run_*.json"), reverse=True)[:1]

    repair_success = proc.returncode == 0
    diagnosis_text = ""
    patch_text = ""

    if result_files:
        try:
            data = json.loads(result_files[0].read_text())
            repair_success = bool(data.get("repair_success", repair_success))
            history = data.get("repair_history", [])
            if history:
                entry = history[-1]
                diagnosis_text = entry.get("diagnosis", "")
                patch_text = entry.get("generated_patch", "")
        except Exception:  # nosec B110
            pass

    if diagnosis_text:
        section("LLM Diagnosis")
        for line in diagnosis_text.strip().splitlines():
            print(f"  {line}")
    else:
        section("LLM Diagnosis")
        print(f"  {_YELLOW}(diagnosis not captured in result JSON — see orchestrator logs above){_RESET}")

    if patch_text:
        section("Generated Patch (new file content)")
        for line in patch_text.strip().splitlines():
            print(f"  {_GREEN}{line}{_RESET}")
    else:
        section("Generated Patch")
        print(f"  {_YELLOW}(patch content not captured in result JSON — see orchestrator logs above){_RESET}")

    # ── STAGE 5: Verify + reset ────────────────────────────────────────────
    banner(5, total_stages, "VALIDATION — pytest confirms repair succeeded", _GREEN)
    section("Running pytest against repaired project")

    verify_result = run(
        [
            "python", "-m", "pytest",
            f"sample_projects/project_{n}/",
            "--no-cov", "-v", "--tb=short", "--no-header",
        ],
        capture=True,
    )
    print(verify_result.stdout + verify_result.stderr)
    verified = verify_result.returncode == 0

    if not is_design_broken:
        run(["bash", "scripts/reset-samples.sh"])
    else:
        subprocess.run(
            ["git", "checkout", "--", f"sample_projects/project_{n}/"],
            cwd=ROOT,
            capture_output=True,
        )

    # ── Final summary ──────────────────────────────────────────────────────
    width = 70
    print(f"\n{_BOLD}{'=' * width}{_RESET}")
    print(f"{_BOLD}  EXPERIMENT SUMMARY{_RESET}")
    print(f"{_BOLD}{'=' * width}{_RESET}")
    print(f"  Project:       {n} — {label}")
    print(f"  Repair status: {(_BOLD + _GREEN + 'SUCCESS ✓' + _RESET) if repair_success else (_BOLD + _RED + 'FAILED ✗' + _RESET)}")
    print(f"  Verified:      {(_BOLD + _GREEN + 'YES ✓' + _RESET) if verified else (_BOLD + _RED + 'NO ✗' + _RESET)}")
    print(f"  Elapsed:       {elapsed:.1f}s")
    print(f"{_BOLD}{'=' * width}{_RESET}\n")


if __name__ == "__main__":
    main()
