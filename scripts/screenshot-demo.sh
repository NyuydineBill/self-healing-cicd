#!/usr/bin/env bash
# Dissertation screenshot walkthrough — push first, then continue automatically.
#
# Typical flow:
#   1. ./scripts/screenshot-demo.sh prepare     # break sample + commit locally
#   2. git push origin main                     # you push
#   3. ./scripts/screenshot-demo.sh continue    # polls CI → repair → capture prompts
#
# Or all-in-one (pauses until you confirm the push):
#   ./scripts/screenshot-demo.sh
#
# Usage:
#   ./scripts/screenshot-demo.sh                prepare → wait for push → continue
#   ./scripts/screenshot-demo.sh prepare        break sample + commit only
#   ./scripts/screenshot-demo.sh continue       after push: CI wait + repair + shots
#   ./scripts/screenshot-demo.sh local          offline repair (no GitHub wait)
#   python scripts/capture_dissertation_slides.py   # auto-generate Slides 10–13 PNGs
#
# Options:
#   --project N      sample project 1–10 (default: 1)
#   --no-pause       skip Enter prompts (smoke test)
#   --commit         auto-commit during prepare (default: yes)
#   --no-commit      only break sample; you commit yourself
#   --wait-secs N    max seconds to poll for CI failure (default: 600)
#
set -euo pipefail
cd "$(dirname "$0")/.."

PROJECT=1
PAUSE=true
MODE="all"
AUTO_COMMIT=true
WAIT_SECS=600

if [[ -t 1 ]]; then
  BOLD='\033[1m' RESET='\033[0m'
  RED='\033[91m' GREEN='\033[92m' YELLOW='\033[93m'
  CYAN='\033[96m' MAGENTA='\033[95m' BG_YELLOW='\033[43m\033[30m'
else
  BOLD='' RESET='' RED='' GREEN='' YELLOW='' CYAN='' MAGENTA='' BG_YELLOW=''
fi

usage() {
  sed -n '2,26p' "$0" | sed 's/^# \{0,1\}//'
  exit 0
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) usage ;;
    --project)
      PROJECT="${2:?missing value for --project}"
      shift 2
      ;;
    --no-pause) PAUSE=false; shift ;;
    --commit) AUTO_COMMIT=true; shift ;;
    --no-commit) AUTO_COMMIT=false; shift ;;
    --wait-secs)
      WAIT_SECS="${2:?missing value for --wait-secs}"
      shift 2
      ;;
    all|prepare|continue|local|docker|github)
      MODE="$1"
      shift
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      ;;
  esac
done

if ! [[ "$PROJECT" =~ ^([1-9]|1[0-5])$ ]]; then
  echo "ERROR: --project must be 1–15" >&2
  exit 1
fi

FAILURE_NAMES=(
  "" AssertionError ImportError SyntaxError "Logic bug"
  ModuleNotFoundError AttributeError NameError IndexError TypeError ZeroDivisionError
  "Multi-file ImportError" "Wrong exception type" "Off-by-one error"
  "Type coercion TypeError" "Retry recovery (multi-bug)"
)
FAILURE_LABEL="${FAILURE_NAMES[$PROJECT]}"

hr() { printf '%s\n' "${BOLD}$(printf '=%.0s' {1..72})${RESET}" >&2; }
info() { printf '%s%s%s\n' "$CYAN" "$*" "$RESET" >&2; }
warn() { printf '%s%s%s\n' "$YELLOW" "$*" "$RESET" >&2; }
die()  { printf '%s%s%s\n' "$RED" "ERROR: $*" "$RESET" >&2; exit 1; }

pause_step() {
  [[ "$PAUSE" == true ]] || return 0
  echo
  read -r -p "  Press Enter when ready for the next step… " _
}

capture_now() {
  local num="$1" slide="$2" title="$3"
  echo >&2
  hr
  printf '%s%s  📸  CAPTURE NOW — Slide %s%s\n' "$BG_YELLOW" "$BOLD" "$slide" "$RESET" >&2
  printf '%s%s     %s%s\n' "$BOLD" "$MAGENTA" "$title" "$RESET" >&2
  hr
  echo >&2
}

load_env() {
  if [[ ! -f .env ]]; then
    return 0
  fi
  while IFS= read -r line || [[ -n "$line" ]]; do
    [[ "$line" =~ ^[[:space:]]*# ]] && continue
    [[ -z "${line// }" ]] && continue
    if [[ "$line" =~ ^([A-Za-z_][A-Za-z0-9_]*)=(.*)$ ]]; then
      key="${BASH_REMATCH[1]}"
      val="${BASH_REMATCH[2]}"
      val="${val#"${val%%[![:space:]]*}"}"
      val="${val%"${val##*[![:space:]]}"}"
      if [[ "$val" == \"*\" && "$val" == *\" ]]; then val="${val:1:${#val}-2}"; fi
      if [[ "$val" == \'*\' && "$val" == *\' ]]; then val="${val:1:${#val}-2}"; fi
      if [[ -z "${!key:-}" ]]; then
        export "${key}=${val}"
      fi
    fi
  done < .env
}

ensure_venv() {
  if [[ -z "${VIRTUAL_ENV:-}" ]] && [[ -d venv/bin/activate ]]; then
    # shellcheck disable=SC1091
    source venv/bin/activate
  fi
}

check_openai() {
  load_env
  [[ -n "${OPENAI_API_KEY:-}" ]] || die "OPENAI_API_KEY not set. Add it to .env"
}

check_github() {
  load_env
  [[ -n "${GITHUB_TOKEN:-}" ]] || die "GITHUB_TOKEN not set. Add it to .env"
  [[ -n "${GITHUB_OWNER:-}" ]] || die "GITHUB_OWNER not set. Add it to .env"
  [[ -n "${GITHUB_REPO:-}" ]] || die "GITHUB_REPO not set. Add it to .env"
}

actions_url() {
  printf 'https://github.com/%s/%s/actions' "${GITHUB_OWNER}" "${GITHUB_REPO}"
}

print_diagnosis_and_patch() {
  python3 - <<PY
import json
import re
from pathlib import Path

project = "$PROJECT"
results = sorted(Path("results").glob("run_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
if not results:
    print("  (no result JSON found — check orchestrator output above)")
    raise SystemExit(0)

data = json.loads(results[0].read_text())
history = data.get("repair_history") or []
entry = history[-1] if history else {}

diagnosis = (entry.get("diagnosis") or "").strip()
patch = (entry.get("generated_patch") or entry.get("patch", "")).strip()
patch = re.sub(r"^```\w*\n?", "", patch)
patch = re.sub(r"\n?```$", "", patch)
target = data.get("target_file") or entry.get("target_file", "—")
failure_type = (data.get("failure_type") or entry.get("failure_type") or "unknown").replace("_", " ")

root_cause = diagnosis
if diagnosis:
    for ln in diagnosis.splitlines():
        ln = ln.strip()
        if re.search(r"cause|failure|assertion", ln, re.I):
            root_cause = re.sub(r"^\d+\.\s*\*+\s*", "", ln).strip("* ").strip()
            root_cause = re.sub(r"\*+", "", root_cause)
            break
else:
    root_cause = f"{failure_type.title()}: see orchestrator logs above"

suggested = "See generated patch below."
if patch:
    for ln in patch.splitlines():
        if "assert" in ln:
            suggested = ln.strip()
            break

print("── Slide 11 — Failure Analysis " + "─" * 42)
print()
print(f"  Root Cause:     {root_cause}")
print(f"  Affected File:  {target}")
print(f"  Suggested Fix:  {suggested}")
print()
if diagnosis and diagnosis != root_cause:
    print("── Full LLM Diagnosis " + "─" * 48)
    for line in diagnosis.splitlines():
        print(f"  {line}")
    print()
if patch:
    print("── Generated Patch " + "─" * 50)
    for line in patch.splitlines():
        print(f"  {line}")
PY
}

show_patch_before_after() {
  python3 - <<PY
from pathlib import Path
import re

project = int("$PROJECT")
target = Path(f"sample_projects/project_{project}/test_unit_failure.py")
backup_dir = Path("results/backups")
before = None
if backup_dir.exists():
    for bak in sorted(backup_dir.rglob(f"*project_{project}*original.bak"), key=lambda p: p.stat().st_mtime, reverse=True):
        before = bak.read_text(encoding="utf-8")
        break
if before is None:
    before = target.read_text(encoding="utf-8")
    # If already repaired, reconstruct broken version for display
    before = before.replace("== 4", "== 999", 1)

after = target.read_text(encoding="utf-8")

def highlight(content: str, marker: str, colour: str) -> None:
    for line in content.splitlines():
        if marker in line:
            line = line.replace(marker, f"{colour}{marker}\033[0m")
        print(f"  {line}")

print("── Slide 12 — Patch Generation (Before → After) " + "─" * 24)
print()
print("  BEFORE")
for line in before.splitlines():
    if "999" in line:
        print(f"  \033[91m{line}\033[0m")
    else:
        print(f"  {line}")
print()
print("           ↓")
print()
print("  AFTER  (patch applied automatically)")
for line in after.splitlines():
    if "== 4" in line:
        print(f"  \033[92m{line}\033[0m")
    else:
        print(f"  {line}")
print()
print("  Highlight ONLY the changed assertion line on your slide.")
PY
}

wait_for_ci_failure() {
  check_github
  info "Polling GitHub for a failed Test Pipeline run (up to ${WAIT_SECS}s)…"
  python3 - <<PY
import os, sys, time
import requests

owner = os.environ["GITHUB_OWNER"]
repo = os.environ["GITHUB_REPO"]
token = os.environ["GITHUB_TOKEN"]
wait_secs = int("${WAIT_SECS}")
headers = {
    "Authorization": f"Bearer {token}",
    "Accept": "application/vnd.github+json",
}
url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs"
deadline = time.time() + wait_secs

def log(msg: str) -> None:
    print(msg, file=sys.stderr)

while time.time() < deadline:
    r = requests.get(url, headers=headers, params={"per_page": 10}, timeout=30)
    if r.status_code != 200:
        log(f"  API error {r.status_code}: {r.text[:200]}")
        time.sleep(15)
        continue
    for run in r.json().get("workflow_runs", []):
        name = (run.get("name") or "").lower()
        if "test pipeline" not in name:
            continue
        status = run.get("status")
        conclusion = run.get("conclusion")
        run_id = run["id"]
        if status != "completed":
            log(f"  … Test Pipeline run {run_id} still {status}")
            break
        if conclusion == "failure":
            log(f"  ✓ Found failed Test Pipeline run: {run_id}")
            print(run_id)
            sys.exit(0)
        if conclusion == "success":
            log(f"  … Latest Test Pipeline run {run_id} succeeded — waiting for your push…")
    time.sleep(15)

log("  ✗ Timed out waiting for a failed Test Pipeline run.")
sys.exit(1)
PY
}

show_log_excerpt() {
  local run_id="$1"
  python3 - <<PY
import io, os, zipfile, requests, re

run_id = "$run_id"
owner = os.environ["GITHUB_OWNER"]
repo = os.environ["GITHUB_REPO"]
token = os.environ["GITHUB_TOKEN"]
headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs/{run_id}/logs"
r = requests.get(url, headers=headers, timeout=60)
if r.status_code != 200:
    print(f"  (could not download logs: HTTP {r.status_code})")
    raise SystemExit(0)

text = ""
with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
    for name in zf.namelist():
        if "test" in name.lower() or "coverage" in name.lower():
            text += zf.read(name).decode("utf-8", errors="replace") + "\n"
    if not text:
        # fallback: first log file
        first = zf.namelist()[0]
        text = zf.read(first).decode("utf-8", errors="replace")

# Find error block
lines = text.splitlines()
idx = None
for i, line in enumerate(lines):
    if re.search(r"AssertionError|ImportError|SyntaxError|ModuleNotFoundError|FAILED|Error", line):
        idx = i
        break

if idx is None:
    excerpt = lines[-25:]
else:
    start = max(0, idx - 5)
    excerpt = lines[start : start + 20]

print("── Log excerpt (for Screenshot 3 reference) " + "─" * 28)
for line in excerpt:
    print(f"  {line}")
PY
}

# ── Phase 1: prepare (break + commit, you push) ───────────────────────────────
run_prepare() {
  hr
  printf '%s%s  PHASE 1 — PREPARE (you push next)%s\n' "$BOLD" "$CYAN" "$RESET"
  hr
  echo

  info "Breaking sample_projects/project_${PROJECT} (${FAILURE_LABEL})…"
  bash scripts/reset-samples.sh >/dev/null
  bash scripts/break-sample.sh "$PROJECT"
  echo

  if [[ "$AUTO_COMMIT" == true ]]; then
    git add "sample_projects/project_${PROJECT}/"
    if [[ -f .github/workflows/test.yml ]]; then
      git add .github/workflows/test.yml
    fi
    if git diff --cached --quiet; then
      warn "Nothing to commit — sample may already be broken."
    else
      git commit -m "test: intentional CI failure in project_${PROJECT} (dissertation demo)"
      info "✓ Committed locally (sample + workflow if changed)."
    fi
  else
    info "Sample broken. Commit yourself:"
    printf '  %sgit add sample_projects/project_%s/\n' "$BOLD" "$PROJECT"
    printf '  git commit -m "test: intentional CI failure for dissertation demo"%s\n' "$RESET"
  fi

  echo
  info "Now push to GitHub:"
  printf '  %sgit push origin main%s\n' "$BOLD" "$RESET"
  echo
  load_env
  info "Actions URL: $(actions_url 2>/dev/null || echo 'https://github.com/OWNER/REPO/actions')"
}

wait_for_push() {
  hr
  printf '%s%s  WAITING FOR YOUR PUSH%s\n' "$BOLD" "$YELLOW" "$RESET"
  hr
  echo
  info "Push your commit, then press Enter here to continue."
  info "The script will wait for Test Pipeline to fail on GitHub."
  pause_step
}

# ── Phase 2+: after push — CI screenshots + live repair ───────────────────────
run_continue() {
  check_openai
  check_github
  ensure_venv
  load_env

  hr
  printf '%s%s  PHASE 2 — AFTER PUSH (continuing automatically)%s\n' "$BOLD" "$CYAN" "$RESET"
  hr
  echo

  local run_id
  run_id="$(wait_for_ci_failure)" || die "No failed Test Pipeline run detected. Push your broken commit first."
  [[ "$run_id" =~ ^[0-9]+$ ]] || die "Invalid run ID from GitHub API (got: ${run_id:0:40}…)"

  export GITHUB_TRIGGER_RUN_ID="$run_id"
  export TARGET_WORKFLOW_NAMES="Test Pipeline"

  capture_now 10 10 "Pipeline Failure — GitHub Actions → red ❌ Test Pipeline"
  info "Open: https://github.com/${GITHUB_OWNER}/${GITHUB_REPO}/actions/runs/${run_id}"
  info "Crop: workflow name, Failed badge, branch, 3 jobs / 1 failed."
  pause_step

  hr
  printf '%s%s  PHASE 3 — LIVE SELF-HEAL (Slides 11–13)%s\n' "$BOLD" "$CYAN" "$RESET"
  hr
  echo

  info "Running self-heal against failed run ${run_id} (~30–120 s)…"
  info "Watch for ReasoningAgent diagnosis in the logs below."
  echo

  OFFLINE_MODE=false DRY_RUN=false GIT_ENABLED=false \
    AUTO_APPROVE_PATCHES=true REQUIRE_APPROVAL=false LOG_LEVEL=INFO \
    MAX_FAILED_RUNS=1 MAX_FAILURES_PER_RUN=1 STOP_ON_FIRST_SUCCESS=true \
    GITHUB_TRIGGER_RUN_ID="${GITHUB_TRIGGER_RUN_ID}" \
    TARGET_WORKFLOW_NAMES="${TARGET_WORKFLOW_NAMES}" \
    python -u main.py || true

  echo
  capture_now 11 11 "Failure Analysis — Root Cause / Affected File / Suggested Fix"
  print_diagnosis_and_patch
  pause_step

  capture_now 12 12 "Patch Generation — Before → After (highlight changed line only)"
  show_patch_before_after
  pause_step

  capture_now 13 13 "Validation — pytest passed (scroll orchestrator logs for Docker/validation)"
  info "Local confirmation:"
  echo
  python -m pytest -o addopts= "sample_projects/project_${PROJECT}/" -v --tb=short --no-header && \
    info "✓ Tests passed" || warn "✗ Tests still failing"
  pause_step

  hr
  printf '%s%s  PHASE 4 — PIPELINE SUCCESS (Slide 13 alt, optional)%s\n' "$BOLD" "$CYAN" "$RESET"
  hr
  echo

  capture_now 13 13 "Pipeline Success — green ✓ after you push the repair"
  info "Commit and push the repair to turn CI green:"
  echo
  printf '  %sgit add sample_projects/project_%s/\n' "$BOLD" "$PROJECT"
  printf '  git commit -m "fix: self-heal project_%s for dissertation demo"\n' "$PROJECT"
  printf '  git push origin main%s\n' "$RESET"
  echo
  info "Or merge the self-heal PR if GIT_ENABLED=true ran in CI."
  info "Then screenshot the green Test Pipeline run at: $(actions_url)"
  pause_step

  info "To restore golden samples later:"
  printf '  %s./scripts/reset-samples.sh && git add sample_projects/ && git commit -m "chore: reset samples"%s\n' \
    "$BOLD" "$RESET"
}

# ── Offline local path (no push required) ───────────────────────────────────
run_local() {
  check_openai
  ensure_venv

  hr
  printf '%s%s  OFFLINE MODE — terminal screenshots only (no push)%s\n' "$BOLD" "$CYAN" "$RESET"
  hr
  echo

  bash scripts/break-sample.sh "$PROJECT" >/dev/null

  local run_id="screenshot_${PROJECT}"
  local extract_dir="logs/extracted/${run_id}"
  mkdir -p "$extract_dir"
  python -m pytest "sample_projects/project_${PROJECT}/" -v --tb=short --no-header --no-cov \
    > /tmp/screenshot_pytest_failure.txt 2>&1 || true

  local ts="2026-06-06T10:00:00.0000000Z"
  local cmd="pytest sample_projects/project_${PROJECT}/ -v --tb=short"
  {
    echo "${ts} ##[group]Run ${cmd}"
    echo "${ts} ${cmd}"
    while IFS= read -r line; do echo "${ts} ${line}"; done < /tmp/screenshot_pytest_failure.txt
    echo "${ts} ##[endgroup]"
  } > "${extract_dir}/0_tests.txt"

  capture_now 4 15 "LLM Diagnosis — orchestrator output below"
  OFFLINE_MODE=true DRY_RUN=false GIT_ENABLED=false \
    AUTO_APPROVE_PATCHES=true REQUIRE_APPROVAL=false LOG_LEVEL=INFO \
    python -u main.py || true

  capture_now 5 15 "Generated Patch — git diff"
  git diff --color=always "sample_projects/project_${PROJECT}/" || true
  pause_step

  capture_now 6 16 "Validation — pytest passed"
  python -m pytest "sample_projects/project_${PROJECT}/" -v --tb=short --no-header --no-cov
  rm -rf "$extract_dir"
  bash scripts/reset-samples.sh >/dev/null
}

run_docker() {
  ensure_venv
  capture_now 6 16 "Docker Validation — build + pytest in container"
  docker build -t self-healing-validator .
  docker run --rm self-healing-validator pytest "sample_projects/project_${PROJECT}/" -v --tb=short
  pause_step
}

# ── main ─────────────────────────────────────────────────────────────────────
case "$MODE" in
  prepare)  run_prepare ;;
  continue) run_continue ;;
  local)    run_local ;;
  docker)   run_docker ;;
  github)   run_prepare; wait_for_push; run_continue ;;
  all)
    run_prepare
    wait_for_push
    run_continue
    ;;
  *) die "Unknown mode: $MODE" ;;
esac
