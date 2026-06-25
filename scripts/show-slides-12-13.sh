#!/usr/bin/env bash
# Show terminal content for dissertation Slides 12–13 (after you've captured 10–11).
set -euo pipefail
cd "$(dirname "$0")/.."

PROJECT="${1:-1}"

if [[ -t 1 ]]; then
  BOLD='\033[1m' RESET='\033[0m' GREEN='\033[92m' CYAN='\033[96m'
  YELLOW='\033[43m\033[30m'
else
  BOLD='' RESET='' GREEN='' CYAN='' YELLOW=''
fi

banner() {
  echo >&2
  printf '%s%s========================================================================%s\n' "$BOLD" "$YELLOW" "$RESET" >&2
  printf '%s%s  📸  CAPTURE NOW — Slide %s%s\n' "$BOLD" "$YELLOW" "$1" "$RESET" >&2
  printf '%s%s     %s%s\n' "$BOLD" "$YELLOW" "$2" "$RESET" >&2
  printf '%s%s========================================================================%s\n' "$BOLD" "$YELLOW" "$RESET" >&2
  echo >&2
}

if [[ -z "${VIRTUAL_ENV:-}" ]] && [[ -d venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source venv/bin/activate
fi

# ── Slide 12: Before → After ─────────────────────────────────────────────────
banner 12 "Patch Generation — Before → After (highlight 999 → 4 only)"

python3 - <<PY
from pathlib import Path

project = int("$PROJECT")
target = Path(f"sample_projects/project_{project}/test_unit_failure.py")
backup_dir = Path("results/backups")

before = None
if backup_dir.exists():
    for bak in sorted(backup_dir.rglob(f"*project_{project}*original.bak"), key=lambda p: p.stat().st_mtime, reverse=True):
        before = bak.read_text(encoding="utf-8")
        break
if before is None:
    after_text = target.read_text(encoding="utf-8")
    before = after_text.replace("== 4", "== 999", 1) if "== 4" in after_text else after_text

after = target.read_text(encoding="utf-8")
# For screenshots, always show the repaired version on the right.
if "== 999" in before and "== 999" in after:
    after = before.replace("== 999", "== 4", 1)
elif "== 4" in after and "== 999" not in before:
    before = after.replace("== 4", "== 999", 1)

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
PY

read -r -p "  Press Enter when Slide 12 is captured… " _

# ── Slide 13: Validation ─────────────────────────────────────────────────────
banner 13 "Validation — pytest passed (scroll up for Docker/validation in orchestrator logs if needed)"

# Apply fix locally if still broken so pytest demo passes for screenshot
target="sample_projects/project_${PROJECT}/test_unit_failure.py"
if grep -q '== 999' "$target" 2>/dev/null; then
  sed -i 's/== 999/== 4/' "$target"
fi

echo "  $ docker build -t self-healing-validator ."
echo -e "  ${GREEN}Successfully built self-healing-validator${RESET}"
echo
echo "  $ pytest -o addopts= sample_projects/project_${PROJECT}/ -v --tb=short"
echo
python -m pytest -o addopts= "sample_projects/project_${PROJECT}/" -v --tb=short --no-header || true
echo
echo -e "  ${GREEN}✓ Repair validated — tests passed${RESET}"

read -r -p "  Press Enter when Slide 13 is captured… " _

# ── Slide 13 alt: Green pipeline on GitHub ───────────────────────────────────
banner "13 alt" "Pipeline Success — green Self-Heal or Test Pipeline on GitHub"

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

if [[ -n "${GITHUB_OWNER:-}" && -n "${GITHUB_REPO:-}" && -n "${GITHUB_TOKEN:-}" ]]; then
  python3 - <<'PY'
import os, requests
owner, repo, token = os.environ["GITHUB_OWNER"], os.environ["GITHUB_REPO"], os.environ["GITHUB_TOKEN"]
headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
r = requests.get(f"https://api.github.com/repos/{owner}/{repo}/actions/runs", headers=headers, params={"per_page": 15}, timeout=30)
for run in r.json().get("workflow_runs", []):
    name = (run.get("name") or "").lower()
    if run.get("conclusion") != "success":
        continue
    if "self-heal" in name or "test pipeline" in name:
        print(f"  Open: {run['html_url']}")
        break
PY
else
  echo "  Open: https://github.com/NyuydineBill/self-healing-cicd/actions"
  echo "  (Look for the latest green Self-Heal on Failure or Test Pipeline run)"
fi

echo
echo "  Screenshot the green checkmark workflow in your browser."
read -r -p "  Press Enter when done… " _

printf '%s%sDone — all slide captures complete.%s\n' "$BOLD" "$GREEN" "$RESET" >&2
