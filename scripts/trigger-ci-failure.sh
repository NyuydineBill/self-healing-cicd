#!/usr/bin/env bash
# Introduce a failing test in project_1 for CI / self-heal demo (default).
# For other scenarios: ./scripts/break-sample.sh 2
set -euo pipefail
exec "$(dirname "$0")/break-sample.sh" "${1:-1}"
