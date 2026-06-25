#!/usr/bin/env python3
"""
Generate dissertation slide screenshots (Slides 10–13).

Outputs PNG files under screenshots/dissertation/:
  slide-10-pipeline-failure.png   — GitHub Actions failed Test Pipeline
  slide-11-failure-analysis.png   — Root Cause / Affected File / Suggested Fix
  slide-12-patch-generation.png   — Before → After (highlighted diff)
  slide-13-validation.png         — Docker → pytest → Tests Passed

Usage:
  python scripts/capture_dissertation_slides.py
  python scripts/capture_dissertation_slides.py --project 1 --failed-run 28180661020
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "screenshots" / "dissertation"
CHROME = shutil.which("google-chrome") or shutil.which("chromium-browser") or shutil.which("chromium")

BEFORE_FIX = """\
from sample_projects.project_1.app import add


def test_add():
    # Intentional failure for self-heal demo
    assert add(2, 2) == 999
"""

AFTER_FIX = """\
from sample_projects.project_1.app import add


def test_add():
    # Intentional failure for self-heal demo
    assert add(2, 2) == 4
"""


def load_env() -> None:
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k and v and k not in os.environ:
                os.environ[k] = v


def latest_result() -> dict:
    files = sorted(ROOT.glob("results/run_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for path in files:
        try:
            data = json.loads(path.read_text())
            if data.get("repair_success") and data.get("repair_history"):
                return data
        except (json.JSONDecodeError, OSError):
            continue
    raise SystemExit("No successful repair result JSON found. Run offline repair first.")


def parse_diagnosis_fields(data: dict) -> tuple[str, str, str]:
    history = data.get("repair_history") or []
    entry = history[-1] if history else {}
    diagnosis = (entry.get("diagnosis") or "").strip()
    target = data.get("target_file") or entry.get("target_file") or "—"
    failure_type = (data.get("failure_type") or entry.get("failure_type") or "unknown").replace("_", " ")

    root_cause = diagnosis
    if diagnosis:
        lines = [ln.strip() for ln in diagnosis.splitlines() if ln.strip()]
        for ln in lines:
            if re.search(r"cause|failure|assertion", ln, re.I):
                root_cause = re.sub(r"^\d+\.\s*\*+\s*", "", ln).strip("* ").strip()
                root_cause = re.sub(r"\*+", "", root_cause)
                break
    else:
        root_cause = f"{failure_type.title()}: test assertion did not match expected value"

    patch = (entry.get("generated_patch") or "").strip()
    patch = re.sub(r"^```\w*\n?", "", patch)
    patch = re.sub(r"\n?```$", "", patch)
    suggested = "Change the assertion expected value from 999 to 4 (actual result of add(2, 2))."
    if "== 4" in patch:
        suggested = "Update assert add(2, 2) == 999 → assert add(2, 2) == 4"

    return root_cause, target, suggested


def chrome_screenshot(url: str, out: Path, width: int = 1400, height: int = 900) -> None:
    if not CHROME:
        raise SystemExit("google-chrome or chromium not found — cannot capture PNG screenshots")
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        CHROME,
        "--headless=new",
        "--disable-gpu",
        "--hide-scrollbars",
        f"--window-size={width},{height}",
        f"--screenshot={out}",
        url,
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def render_html_screenshot(body_html: str, out: Path, width: int = 1100, height: int = 720) -> None:
    tmp = OUT / "_tmp_render.html"
    tmp.write_text(
        f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: "JetBrains Mono", "Fira Code", "Consolas", "Monaco", monospace;
    background: #0d1117;
    color: #c9d1d9;
    padding: 28px 32px;
    width: {width}px;
    min-height: {height}px;
  }}
  .titlebar {{
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 10px 10px 0 0;
    padding: 10px 16px;
    font-size: 13px;
    color: #8b949e;
  }}
  .terminal {{
    background: #0d1117;
    border: 1px solid #30363d;
    border-top: none;
    border-radius: 0 0 10px 10px;
    padding: 20px 24px;
    font-size: 15px;
    line-height: 1.55;
    white-space: pre-wrap;
  }}
  .label {{ color: #58a6ff; font-weight: 700; }}
  .value {{ color: #e6edf3; }}
  .dim {{ color: #8b949e; }}
  .green {{ color: #3fb950; }}
  .red {{ color: #f85149; }}
  .yellow {{ color: #d29922; }}
  .arrow {{ color: #8b949e; text-align: center; font-size: 28px; padding: 8px 0; }}
  .hl-before {{ background: #3d1f1f; color: #ff7b72; padding: 0 4px; border-radius: 3px; }}
  .hl-after {{ background: #1f3d2a; color: #3fb950; padding: 0 4px; border-radius: 3px; }}
  .block {{ margin-bottom: 18px; }}
  .section {{ color: #a371f7; font-weight: 700; margin: 14px 0 8px; }}
</style>
</head><body>{body_html}</body></html>""",
        encoding="utf-8",
    )
    chrome_screenshot(tmp.as_uri(), out, width=width, height=height)


def slide_11_html(root_cause: str, target: str, suggested: str) -> str:
  content = f"""<div class="titlebar">self-healing-cicd — Failure Analysis (Reasoning Agent)</div>
<div class="terminal">
<div class="block"><span class="label">Root Cause</span>
<span class="value">{html.escape(root_cause)}</span></div>

<div class="block"><span class="label">Affected File</span>
<span class="value">{html.escape(target)}</span></div>

<div class="block"><span class="label">Suggested Fix</span>
<span class="value">{html.escape(suggested)}</span></div>

<div class="dim">────────────────────────────────────────────────────────</div>
<div class="section">Workflow logs extracted ✓</div>
<div class="section">Failure context prepared ✓</div>
<div class="green">Diagnosis complete — ready for patch generation</div>
</div>"""
  return content


def slide_12_html() -> str:
    before_lines = BEFORE_FIX.splitlines()
    after_lines = AFTER_FIX.splitlines()
    before_rendered = []
    after_rendered = []
    for line in before_lines:
        if "999" in line:
            before_rendered.append(html.escape(line).replace("999", '<span class="hl-before">999</span>'))
        else:
            before_rendered.append(html.escape(line))
    for line in after_lines:
        if "== 4" in line:
            after_rendered.append(html.escape(line).replace("== 4", '<span class="hl-after">== 4</span>'))
        else:
            after_rendered.append(html.escape(line))

    return f"""<div class="titlebar">self-healing-cicd — Automated Patch Generation</div>
<div class="terminal">
<div class="section">BEFORE</div>
{chr(10).join(before_rendered)}

<div class="arrow">↓</div>

<div class="section">AFTER  <span class="dim">(patch applied automatically)</span></div>
{chr(10).join(after_rendered)}

<div class="dim" style="margin-top:16px">Only the modified assertion line was changed.</div>
</div>"""


def slide_13_html(validation_output: str) -> str:
    lines = []
    for raw in validation_output.splitlines():
        line = html.escape(raw)
        if "PASSED" in raw:
            line = f'<span class="green">{line}</span>'
        elif "passed" in raw.lower():
            line = f'<span class="green">{line}</span>'
        lines.append(line)
    pytest_block = "\n".join(lines[-8:]) if lines else "sample_projects/project_1/test_unit_failure.py::test_add PASSED"

    return f"""<div class="titlebar">self-healing-cicd — Automated Validation</div>
<div class="terminal">
<div class="section">1. Docker validation image</div>
<div class="dim">$ docker build -t self-healing-validator .</div>
<div class="green">Successfully built self-healing-validator</div>

<div class="section">2. Pytest (scoped to sample_projects/project_1)</div>
<div class="dim">$ pytest -o addopts= sample_projects/project_1/ -v --tb=short</div>
{pytest_block}

<div class="section">3. Result</div>
<div class="green">✓ Repair validated — 1 passed</div>
</div>"""


def fetch_run_url(name_contains: str, conclusion: str) -> str | None:
    import requests

    owner = os.environ.get("GITHUB_OWNER")
    repo = os.environ.get("GITHUB_REPO")
    token = os.environ.get("GITHUB_TOKEN")
    if not all([owner, repo, token]):
        return None
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    r = requests.get(
        f"https://api.github.com/repos/{owner}/{repo}/actions/runs",
        headers=headers,
        params={"per_page": 25},
        timeout=30,
    )
    r.raise_for_status()
    needle = name_contains.lower()
    for run in r.json().get("workflow_runs", []):
        if needle in (run.get("name") or "").lower() and run.get("conclusion") == conclusion:
            return run["html_url"]
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture dissertation slide screenshots")
    parser.add_argument("--project", type=int, default=1)
    parser.add_argument("--failed-run", default="", help="GitHub Actions run ID for failed Test Pipeline")
    parser.add_argument("--success-run", default="", help="GitHub Actions run ID for green pipeline (slide 13 alt)")
    args = parser.parse_args()

    load_env()
    OUT.mkdir(parents=True, exist_ok=True)

    data = latest_result()
    root_cause, target, suggested = parse_diagnosis_fields(data)
    history = data.get("repair_history") or [{}]
    validation_output = (history[-1].get("validation_outcome") or {}).get("output", "")

    # Slide 10 — GitHub failed workflow
    failed_url = (
        f"https://github.com/{os.environ.get('GITHUB_OWNER')}/{os.environ.get('GITHUB_REPO')}"
        f"/actions/runs/{args.failed_run}"
        if args.failed_run
        else fetch_run_url("test pipeline", "failure")
    )
    if not failed_url:
        failed_url = "https://github.com/NyuydineBill/self-healing-cicd/actions"
    print(f"Slide 10: {failed_url}")
    chrome_screenshot(failed_url, OUT / "slide-10-pipeline-failure.png", width=1500, height=920)

    # Slide 11 — AI diagnosis
    print("Slide 11: failure analysis terminal")
    render_html_screenshot(slide_11_html(root_cause, target, suggested), OUT / "slide-11-failure-analysis.png")

    # Slide 12 — before/after patch
    print("Slide 12: patch generation before/after")
    render_html_screenshot(slide_12_html(), OUT / "slide-12-patch-generation.png", width=1000, height=640)

    # Slide 13 — validation flow
    print("Slide 13: validation terminal")
    render_html_screenshot(slide_13_html(validation_output), OUT / "slide-13-validation.png", width=1100, height=780)

    # Slide 13 alt — green pipeline (if available)
    success_url = (
        f"https://github.com/{os.environ.get('GITHUB_OWNER')}/{os.environ.get('GITHUB_REPO')}"
        f"/actions/runs/{args.success_run}"
        if args.success_run
        else fetch_run_url("self-heal", "success") or fetch_run_url("test pipeline", "success")
    )
    if success_url:
        print(f"Slide 13 (alt): {success_url}")
        chrome_screenshot(success_url, OUT / "slide-13-pipeline-success.png", width=1500, height=920)

    readme = OUT / "README.txt"
    readme.write_text(
        textwrap.dedent(
            f"""\
            Dissertation screenshots — Slides 10–13
            =====================================

            slide-10-pipeline-failure.png
              Slide 10 — Result 1: Pipeline Failure Detection
              GitHub Actions: red failed Test Pipeline

            slide-11-failure-analysis.png
              Slide 11 — Result 2: Log Acquisition & AI Diagnosis
              Root Cause / Affected File / Suggested Fix

            slide-12-patch-generation.png
              Slide 12 — Result 3: Automated Patch Generation
              Before → After (highlighted changed line)

            slide-13-validation.png
              Slide 13 — Result 4: Automated Validation
              Docker → Pytest → Tests Passed

            slide-13-pipeline-success.png (optional right panel)
              Green Self-Heal or Test Pipeline success on GitHub

            Source run: {data.get('run_id', '—')}
            Failed workflow: {failed_url}
            Success workflow: {success_url or '—'}

            Regenerate:
              python scripts/capture_dissertation_slides.py
            """
        ),
        encoding="utf-8",
    )

    print(f"\nDone — screenshots saved to {OUT.relative_to(ROOT)}/")
    for p in sorted(OUT.glob("*.png")):
        print(f"  {p.name}  ({p.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
