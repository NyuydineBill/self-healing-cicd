#!/usr/bin/env bash
# Go-live walkthrough for self-healing-cicd
set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== 1. Pre-flight check ==="
python main.py check || true

echo ""
echo "=== 2. Dry-run (no writes, needs GitHub network) ==="
DRY_RUN=true python main.py || echo "(skip if GitHub unreachable)"

echo ""
echo "=== 3. Offline repair from cached logs ==="
OFFLINE_MODE=true AUTO_APPROVE_PATCHES=true REQUIRE_APPROVAL=false \
  MAX_FAILED_RUNS=1 MAX_FAILURES_PER_RUN=1 \
  python main.py

echo ""
echo "=== 4. Interactive local repair (you approve each patch) ==="
echo "Run manually in your terminal:"
echo "  REQUIRE_APPROVAL=true AUTO_APPROVE_PATCHES=false python main.py"
echo ""
echo "=== 5. Full CI self-heal on GitHub ==="
echo "  - Start Docker Desktop"
echo "  - Add OPENAI_API_KEY repo secret"
echo "  - Push to main; ensure Test Pipeline fails"
echo "  - Self-Heal on Failure workflow opens a PR"
