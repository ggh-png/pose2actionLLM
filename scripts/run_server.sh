#!/usr/bin/env bash
# Bootstrap only project dependencies unless --install-vllm is explicitly given.
set -euo pipefail
TASK_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$TASK_ROOT"
TASK_PYTHON="${POSE_PYTHON:-python3}"
TASK_ENV="${POSE_RUN_VENV:-$TASK_ROOT/.venv-server}"
TASK_INSTALL_VLLM=0
TASK_ARGS=()
for arg in "$@"; do
  case "$arg" in
    --install-vllm) TASK_INSTALL_VLLM=1 ;;
    -h|--help) exec "$TASK_PYTHON" scripts/run_pipeline.py --help ;;
    *) TASK_ARGS+=("$arg") ;;
  esac
done
if [[ ! -x "$TASK_ENV/bin/python" ]]; then
  "$TASK_PYTHON" -m venv "$TASK_ENV" || {
    echo 'Cannot create venv. Install python3-venv (or set POSE_PYTHON to a Python with venv support).' >&2
    exit 1
  }
fi
"$TASK_ENV/bin/python" -m pip install -e .
if [[ "$TASK_INSTALL_VLLM" == 1 ]]; then
  # This downloads GPU dependencies; intended for the model server only.
  "$TASK_ENV/bin/python" -m pip install 'vllm>=0.11,<1'
fi
export MPLBACKEND=Agg
exec "$TASK_ENV/bin/python" scripts/run_pipeline.py "${TASK_ARGS[@]}"
