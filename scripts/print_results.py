#!/usr/bin/env python3
"""
Print the saved experiment results as a formatted table.
Used for thesis Figure 4.6 and 4.7 screenshots.

Usage:
    python scripts/print_results.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
RESULTS_FILE = ROOT / "results" / "experiment_results.json"

_RESET = "\033[0m"
_BOLD = "\033[1m"
_GREEN = "\033[92m"
_RED = "\033[91m"
_CYAN = "\033[96m"
_YELLOW = "\033[93m"
_WHITE = "\033[97m"
_BG_BLUE = "\033[44m"


def main() -> None:
    sys.stdout.reconfigure(write_through=True)  # type: ignore[attr-defined]

    if not RESULTS_FILE.exists():
        print(f"No results file found at {RESULTS_FILE}")
        sys.exit(1)

    data = json.loads(RESULTS_FILE.read_text())
    experiments = data.get("experiments", [])

    print(f"\n{_BOLD}{_BG_BLUE}{'':^72}{_RESET}")
    print(f"{_BOLD}{_BG_BLUE}{'  SELF-HEALING CI/CD — EXPERIMENTAL EVALUATION RESULTS':^72}{_RESET}")
    print(f"{_BOLD}{_BG_BLUE}{'':^72}{_RESET}\n")

    # ── Figure 4.6: Per-project validation results ─────────────────────────
    width = 72
    print(f"{_BOLD}{_CYAN}{'=' * width}{_RESET}")
    # print(f"{_BOLD}{_CYAN}  Figure 4.6 — Per-Scenario Validation Results{_RESET}")
    print(f"{_BOLD}{_CYAN}{'=' * width}{_RESET}")

    header = (
        f"  {'#':<4} {'Failure Type':<28} {'Result':<10} "
        f"{'Attempts':<10} {'Time (s)':<10} {'Verified'}"
    )
    print(f"\n{_BOLD}{header}{_RESET}")
    print(f"  {'─' * 68}")

    for e in experiments:
        n = e["project"]
        ftype = e["failure_type"]
        success = e["repair_success"]
        verified = e.get("repair_verified", False)
        attempts = e["attempts"]
        elapsed = e["elapsed_seconds"]

        result_str = f"{_GREEN}REPAIRED ✓{_RESET}" if success else f"{_RED}FAILED   ✗{_RESET}"
        verified_str = f"{_GREEN}YES{_RESET}" if verified else ("—" if not success else f"{_RED}NO{_RESET}")

        print(
            f"  {n:<4} {ftype:<28} {result_str:<20} "
            f"{attempts:<10} {elapsed:<10} {verified_str}"
        )

    print(f"  {'─' * 68}\n")

    # ── Figure 4.7: Summary statistics ────────────────────────────────────
    print(f"{_BOLD}{_CYAN}{'=' * width}{_RESET}")
    # print(f"{_BOLD}{_CYAN}  Figure 4.7 — Experimental Evaluation Summary{_RESET}")
    print(f"{_BOLD}{_CYAN}{'=' * width}{_RESET}\n")

    total = len(experiments)
    succeeded = sum(1 for e in experiments if e["repair_success"])
    verified_count = sum(1 for e in experiments if e.get("repair_verified"))
    failed = total - succeeded
    success_rate = 100 * succeeded / total if total else 0

    successful = [e for e in experiments if e["repair_success"]]
    avg_time = sum(e["elapsed_seconds"] for e in successful) / len(successful) if successful else 0
    avg_attempts = sum(e["attempts"] for e in successful) / len(successful) if successful else 0
    min_time = min((e["elapsed_seconds"] for e in successful), default=0)
    max_time = max((e["elapsed_seconds"] for e in successful), default=0)

    rows = [
        ("Total scenarios evaluated",   str(total)),
        ("Successfully repaired",        f"{_GREEN}{_BOLD}{succeeded}/{total}{_RESET}"),
        ("Repair success rate",          f"{_GREEN}{_BOLD}{success_rate:.1f}%{_RESET}"),
        ("Independently verified",       f"{verified_count}/{total}"),
        ("Failed (framework limitation)", f"{_YELLOW}{failed}{_RESET}"),
        ("Average repair time",          f"{_BOLD}{avg_time:.1f}s{_RESET}"),
        ("Min / Max repair time",        f"{min_time:.1f}s / {max_time:.1f}s"),
        ("Average LLM attempts",         f"{_BOLD}{avg_attempts:.1f}{_RESET}"),
        ("Single-attempt repairs",       str(sum(1 for e in successful if e["attempts"] == 1))),
        ("Multi-attempt repairs",        str(sum(1 for e in successful if e["attempts"] > 1))),
    ]

    for label, value in rows:
        print(f"  {_WHITE}{label:<36}{_RESET}  {value}")

    failure_note = next(
        (e for e in experiments if not e["repair_success"]), None
    )
    if failure_note:
        print(
            f"\n  {_YELLOW}Note: Project {failure_note['project']} ({failure_note['failure_type']}) "
            f"was not repaired — the framework cannot create new files from scratch "
            f"(missing module did not exist on disk).{_RESET}"
        )

    print()


if __name__ == "__main__":
    main()
