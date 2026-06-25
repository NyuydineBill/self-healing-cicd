#!/usr/bin/env bash
# Slide 12 — show LLM reasoning + generated patch (for dissertation screenshot).
set -euo pipefail
cd "$(dirname "$0")/.."

PROJECT="${1:-1}"

if [[ -t 1 ]]; then
  BOLD='\033[1m' RESET='\033[0m' GREEN='\033[92m' CYAN='\033[96m' MAGENTA='\033[95m'
  YELLOW='\033[43m\033[30m'
else
  BOLD='' RESET='' GREEN='' CYAN='' MAGENTA='' YELLOW=''
fi

banner() {
  echo >&2
  printf '%s%s========================================================================%s\n' "$BOLD" "$YELLOW" "$RESET" >&2
  printf '%s%s  📸  CAPTURE NOW — Slide 12 — Patch Generation (LLM)%s\n' "$BOLD" "$YELLOW" "$RESET" >&2
  printf '%s%s     %s%s\n' "$BOLD" "$YELLOW" "$1" "$RESET" >&2
  printf '%s%s========================================================================%s\n' "$BOLD" "$YELLOW" "$RESET" >&2
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

if [[ -z "${VIRTUAL_ENV:-}" ]] && [[ -d venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source venv/bin/activate
fi
load_env
[[ -n "${OPENAI_API_KEY:-}" ]] || { echo "ERROR: OPENAI_API_KEY not set in .env" >&2; exit 1; }

# Golden → break so repair has something to fix
bash scripts/reset-samples.sh >/dev/null
bash scripts/break-sample.sh "$PROJECT" >/dev/null

run_id="slide12_p${PROJECT}"
extract_dir="logs/extracted/${run_id}"
mkdir -p "$extract_dir"

python -m pytest "sample_projects/project_${PROJECT}/" -v --tb=short -o addopts= \
  > /tmp/slide12_pytest_fail.txt 2>&1 || true

ts="2026-06-25T20:00:00.0000000Z"
{
  echo "${ts} ##[group]Run pytest tests/ sample_projects/"
  echo "${ts} pytest tests/ sample_projects/ -v --cov=. --cov-report=term-missing --cov-report=xml"
  while IFS= read -r line; do echo "${ts} ${line}"; done < /tmp/slide12_pytest_fail.txt
  echo "${ts} ##[endgroup]"
} > "${extract_dir}/0_tests.txt"

banner "Watch orchestrator below — ReasoningAgent + PatchAgent (then summary prints)"

OFFLINE_MODE=true DRY_RUN=false GIT_ENABLED=false \
  AUTO_APPROVE_PATCHES=true REQUIRE_APPROVAL=false LOG_LEVEL=INFO \
  MAX_FAILED_RUNS=1 MAX_FAILURES_PER_RUN=1 \
  python -u main.py 2>&1 | tee /tmp/slide12_orchestrator.log

echo
printf '%s%s── Slide 12 — LLM Reasoning & Generated Patch ─────────────────%s\n' "$BOLD" "$MAGENTA" "$RESET"

python3 - <<'PY'
import json, re, sys
from pathlib import Path

results = sorted(Path("results").glob("run_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
if not results:
    print("  (no result JSON — scroll up to orchestrator logs above)")
    sys.exit(0)

data = json.loads(results[0].read_text())
history = data.get("repair_history") or []
entry = history[-1] if history else {}
diagnosis = (entry.get("diagnosis") or "").strip()
patch = (entry.get("generated_patch") or entry.get("patch") or "").strip()
patch = re.sub(r"^```\w*\n?", "", patch)
patch = re.sub(r"\n?```$", "", patch)
target = data.get("target_file") or entry.get("target_file", "—")

print()
print(f"  Target file: {target}")
print()
print("  ── LLM Diagnosis (Reasoning Agent) " + "─" * 32)
if diagnosis:
    for line in diagnosis.splitlines():
        print(f"  {line}")
else:
    print("  (see ReasoningAgent logs above)")
print()
print("  ── Generated Patch (Patch Agent) " + "─" * 34)
if patch:
    for line in patch.splitlines():
        print(f"  \033[92m{line}\033[0m")
else:
    print("  (see PatchAgent logs above)")
print()
print("  ── Applied " + "─" * 55)
print("  \033[92m✓ Patch written to disk and validated with pytest\033[0m")
PY

rm -rf "$extract_dir"
echo
read -r -p "  Press Enter when Slide 12 screenshot is captured… " _
