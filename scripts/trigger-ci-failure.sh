#!/usr/bin/env bash
# Introduce a failing assertion in project_1 for CI / self-heal demo.
# Revert with: git checkout -- sample_projects/project_1/test_unit_failure.py
set -euo pipefail
cd "$(dirname "$0")/.."

TARGET="sample_projects/project_1/test_unit_failure.py"

if grep -q "assert add(2, 2) == 999" "$TARGET" 2>/dev/null; then
  echo "Failure already present in $TARGET"
  exit 0
fi

cat > "$TARGET" <<'EOF'
from sample_projects.project_1.app import add


def test_add():
    # Intentional failure for self-heal demo — revert before final merge
    assert add(2, 2) == 999
EOF

echo "Updated $TARGET with failing assertion."
echo "Next:"
echo "  git add $TARGET"
echo "  git commit -m 'test: intentional CI failure for self-heal demo'"
echo "  git push origin main"
echo "Then watch: Actions → Test Pipeline (fail) → Self-Heal on Failure"
