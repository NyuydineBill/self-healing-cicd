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
#   ./scripts/screenshot-demo.sh docker         optional Docker validation shot
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

hr() { printf '%s\n' "${BOLD}$(printf '=%.0s' {1..72})${RESET}"; }
info() { printf '%s%s%s\n' "$CYAN" "$*" "$RESET"; }
warn() { printf '%s%s%s\n' "$YELLOW" "$*" "$RESET"; }
die()  { printf '%s%s%s\n' "$RED" "ERROR: $*" "$RESET" >&2; exit 1; }

pause_step() {
  [[ "$PAUSE" == true ]] || return 0
  echo
  read -r -p "  Press Enter when ready for the next step… " _
}

capture_now() {
  local num="$1" slide="$2" title="$3"
  echo
  hr
  printf '%s%s  📸  CAPTURE NOW — SCREENSHOT %s  (Slide %s)%s\n' \
    "$BG_YELLOW" "$BOLD" "$num" "$slide" "$RESET"
  printf '%s%s     %s%s\n' "$BOLD" "$MAGENTA" "$title" "$RESET"
  hr
  echo
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
from pathlib import Path

project = "$PROJECT"
results = sorted(Path("results").glob("run_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
if not results:
    print("  (no result JSON found — check orchestrator output above)")
    raise SystemExit(0)

data = json.loads(results[0].read_text())
history = data.get("repair_history") or []
entry = history[-1] if history else {}

diagnosis = entry.get("diagnosis", "")
patch = entry.get("generated_patch") or entry.get("patch", "")

print(f"  Run ID:         {data.get('run_id', '—')}")
print(f"  Failure type:   {data.get('failure_type') or entry.get('failure_type', '—')}")
print(f"  Target file:    {data.get('target_file') or entry.get('target_file', '—')}")
print(f"  Repair success: {data.get('repair_success', '—')}")
print()

if diagnosis:
    print("── LLM Diagnosis " + "─" * 55)
    for line in diagnosis.strip().splitlines():
        print(f"  {line}")
else:
    print("  (diagnosis not in JSON — scroll orchestrator logs above)")
print()

if patch:
    print("── Generated Patch (new file content) " + "─" * 36)
    for line in patch.strip().splitlines():
        print(f"  {line}")
else:
    print("  (patch not in JSON — use git diff in the next step)")
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

  export GITHUB_TRIGGER_RUN_ID="$run_id"
  export TARGET_WORKFLOW_NAMES="Test Pipeline"

  capture_now 2 14 "Pipeline Failure — GitHub Actions → red ❌ Test Pipeline"
  info "Open: $(actions_url)"
  info "Crop: workflow name, Failed badge, branch, 3 jobs / 1 failed."
  pause_step

  capture_now 3 14 "Failure Logs — Tests & Coverage → Run tests with coverage"
  info "On GitHub: open the failed job logs and crop ~15 lines around ${FAILURE_LABEL}."
  info "Terminal reference excerpt from downloaded logs:"
  echo
  show_log_excerpt "$run_id"
  pause_step

  hr
  printf '%s%s  PHASE 3 — LIVE SELF-HEAL (Screenshots 4, 5, 6)%s\n' "$BOLD" "$CYAN" "$RESET"
  hr
  echo

  capture_now 4 15 "LLM Diagnosis — watch orchestrator output below"
  info "Fetching real CI logs from GitHub and running repair (~30–120 s)…"
  echo

  OFFLINE_MODE=false DRY_RUN=false GIT_ENABLED=false \
    AUTO_APPROVE_PATCHES=true REQUIRE_APPROVAL=false LOG_LEVEL=INFO \
    MAX_FAILED_RUNS=1 MAX_FAILURES_PER_RUN=1 STOP_ON_FIRST_SUCCESS=true \
    GITHUB_TRIGGER_RUN_ID="${GITHUB_TRIGGER_RUN_ID}" \
    TARGET_WORKFLOW_NAMES="${TARGET_WORKFLOW_NAMES}" \
    python -u main.py || true

  echo
  capture_now 4 15 "LLM Diagnosis — formatted summary (backup shot)"
  print_diagnosis_and_patch
  pause_step

  capture_now 5 15 "Generated Patch — before / after (highlight + lines only)"
  info "Unified diff of repaired file(s):"
  echo
  git diff --color=always "sample_projects/project_${PROJECT}/" 2>/dev/null \
    || git diff "sample_projects/project_${PROJECT}/" || true
  echo
  info "Highlight ONLY the changed lines in your slide."
  pause_step

  capture_now 6 16 "Validation — pytest passed (green checkmarks)"
  info "Validation output should appear above in orchestrator logs."
  info "Confirming locally:"
  echo
  python -m pytest "sample_projects/project_${PROJECT}/" -v --tb=short --no-header --no-cov && \
    info "✓ Tests passed" || warn "✗ Tests still failing"
  pause_step

  hr
  printf '%s%s  PHASE 4 — PIPELINE SUCCESS (Screenshot 7, optional)%s\n' "$BOLD" "$CYAN" "$RESET"
  hr
  echo

  capture_now 7 16 "Pipeline Success — green ✓ Test Pipeline after push"
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
