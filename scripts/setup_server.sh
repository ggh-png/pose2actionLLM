#!/usr/bin/env bash
# Standalone first-time setup; can also run from an existing checkout.
set -euo pipefail

SETUP_REPO='https://github.com/ggh-png/pose2actionLLM.git'
SETUP_REF='main'
SETUP_PYTHON="${POSE_PYTHON:-python3}"
SETUP_DIR="${HOME}/pose2actionLLM"
SETUP_ENV=''
SETUP_SYSTEM=0
SETUP_VLLM=0
SETUP_DOCS=0
SETUP_DEV=0
SETUP_SMOKE=1
SETUP_CHECK=0

# Reuse this checkout when invoked directly from its scripts directory.
SETUP_SCRIPT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -e "$SETUP_SCRIPT_ROOT/.git" && -f "$SETUP_SCRIPT_ROOT/pyproject.toml" ]]; then
  SETUP_DIR="$SETUP_SCRIPT_ROOT"
fi

usage() {
  cat <<'HELP'
Usage: bash setup_server.sh [options]

Prepare a Linux server: prerequisites -> clone/reuse repo -> isolated Python
venv -> packages -> mock smoke test -> setup report. No model weights are loaded.

  --directory PATH    Checkout directory (default: current checkout or ~/pose2actionLLM)
  --venv PATH         Python environment (default: CHECKOUT/.venv-server)
  --python COMMAND    Python >=3.10 executable (default: POSE_PYTHON or python3)
  --ref REF           Branch/tag used when cloning (default: main)
  --repo URL          Repository to clone (default: official project repository)
  --install-system    Install git, Python/venv/pip, curl, CA certificates using apt
                      (Debian/Ubuntu only; uses sudo if not root)
  --with-vllm         Install GPU dependencies for vLLM; requires working nvidia-smi
  --with-docs         Install MkDocs documentation tools
  --with-dev          Install API, tests and lint dependencies
  --skip-smoke        Skip the final mock pipeline test
  --check             Show prerequisites and plan only; make no changes
  -h, --help          Show this help

Existing checkouts are reused without pulling, resetting or switching branches.
System packages and vLLM are installed only when explicitly requested.
HELP
}

fail() { echo "Setup error: $*" >&2; exit 1; }
value_required() {
  [[ $# -ge 2 && -n "$2" && "$2" != --* ]] || fail "$1 requires a value"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --directory) value_required "$@"; SETUP_DIR="$2"; shift 2 ;;
    --venv) value_required "$@"; SETUP_ENV="$2"; shift 2 ;;
    --python) value_required "$@"; SETUP_PYTHON="$2"; shift 2 ;;
    --repo) value_required "$@"; SETUP_REPO="$2"; shift 2 ;;
    --ref) value_required "$@"; SETUP_REF="$2"; shift 2 ;;
    --install-system) SETUP_SYSTEM=1; shift ;;
    --with-vllm) SETUP_VLLM=1; shift ;;
    --with-docs) SETUP_DOCS=1; shift ;;
    --with-dev) SETUP_DEV=1; shift ;;
    --skip-smoke) SETUP_SMOKE=0; shift ;;
    --check) SETUP_CHECK=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) fail "Unknown option: $1 (see --help)" ;;
  esac
done
[[ -n "$SETUP_DIR" && "$SETUP_DIR" != / ]] || fail 'Choose a project directory, not /'
SETUP_ENV="${SETUP_ENV:-$SETUP_DIR/.venv-server}"

if [[ "$SETUP_CHECK" == 1 ]]; then
  printf 'Repository: %s\nDirectory: %s\nEnvironment: %s\nPython: %s\n' \
    "$SETUP_REPO" "$SETUP_DIR" "$SETUP_ENV" "$SETUP_PYTHON"
  printf 'Install system packages=%s, vLLM=%s, docs=%s, dev=%s, mock test=%s\n' \
    "$SETUP_SYSTEM" "$SETUP_VLLM" "$SETUP_DOCS" "$SETUP_DEV" "$SETUP_SMOKE"
  for command in git "$SETUP_PYTHON" nvidia-smi; do
    if command -v "$command" >/dev/null 2>&1; then
      printf 'Found: %s\n' "$command"
    else
      printf 'Unavailable: %s\n' "$command"
    fi
  done
  exit 0
fi

[[ "$(uname -s)" == Linux ]] || fail 'This setup script targets Linux servers'
if [[ "$SETUP_SYSTEM" == 1 ]]; then
  command -v apt-get >/dev/null || fail '--install-system supports Debian/Ubuntu apt only'
  SETUP_PRIVILEGE=()
  if [[ "$EUID" != 0 ]]; then
    command -v sudo >/dev/null || fail 'sudo or root is required for system packages'
    SETUP_PRIVILEGE=(sudo)
  fi
  "${SETUP_PRIVILEGE[@]}" apt-get update
  "${SETUP_PRIVILEGE[@]}" apt-get install -y git python3 python3-venv python3-pip curl ca-certificates
fi
command -v git >/dev/null || fail 'git is missing; use --install-system on Ubuntu/Debian'
command -v "$SETUP_PYTHON" >/dev/null || fail "Python is missing: $SETUP_PYTHON"
"$SETUP_PYTHON" -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' || \
  fail 'Python >=3.10 is required; use --python python3.12 if available'
if [[ "$SETUP_VLLM" == 1 ]]; then
  command -v nvidia-smi >/dev/null || fail 'nvidia-smi is missing; prepare the NVIDIA driver first'
  nvidia-smi --query-gpu=name,memory.total --format=csv,noheader || fail 'NVIDIA driver/GPU is unavailable'
fi

if [[ -e "$SETUP_DIR" && ! -d "$SETUP_DIR" ]]; then
  fail "Not a directory: $SETUP_DIR"
fi
if [[ -e "$SETUP_DIR/.git" ]]; then
  [[ -f "$SETUP_DIR/pyproject.toml" && -f "$SETUP_DIR/scripts/run_pipeline.py" ]] || \
    fail 'Existing checkout is not the expected pose2actionLLM project'
  printf 'Reusing checkout without updating: %s\n' "$SETUP_DIR"
else
  if [[ -d "$SETUP_DIR" && -n "$(ls -A -- "$SETUP_DIR")" ]]; then
    fail 'Destination is nonempty and is not a project checkout; choose another --directory'
  fi
  git clone --branch "$SETUP_REF" -- "$SETUP_REPO" "$SETUP_DIR"
fi
# Resolve paths before changing cwd; relative --directory/--venv use invocation cwd.
SETUP_ENV="$("$SETUP_PYTHON" -c 'import pathlib,sys; print(pathlib.Path(sys.argv[1]).resolve())' "$SETUP_ENV")"
cd "$SETUP_DIR"
SETUP_DIR="$PWD"
if [[ -d "$SETUP_ENV" && ! -f "$SETUP_ENV/pyvenv.cfg" && -n "$(ls -A -- "$SETUP_ENV")" ]]; then
  fail 'Environment directory is nonempty and is not a Python venv; choose another --venv'
fi
if [[ ! -x "$SETUP_ENV/bin/python" ]]; then
  "$SETUP_PYTHON" -m venv "$SETUP_ENV" || \
    fail 'Cannot create venv; install python3-venv or use --python with venv support'
fi
[[ -f "$SETUP_ENV/pyvenv.cfg" ]] || fail '--venv must point to an isolated Python venv'
"$SETUP_ENV/bin/python" -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' || \
  fail 'Existing venv needs Python >=3.10; choose a new --venv directory'
"$SETUP_ENV/bin/python" -m pip --version >/dev/null || {
  "$SETUP_ENV/bin/python" -m ensurepip --upgrade || fail 'Cannot bootstrap pip inside venv'
}
SETUP_SPEC='.'
SETUP_EXTRAS=()
[[ "$SETUP_DOCS" == 0 ]] || SETUP_EXTRAS+=(docs)
[[ "$SETUP_DEV" == 0 ]] || SETUP_EXTRAS+=(api dev)
if [[ ${#SETUP_EXTRAS[@]} -gt 0 ]]; then
  SETUP_JOINED="$(IFS=,; echo "${SETUP_EXTRAS[*]}")"
  SETUP_SPEC=".[$SETUP_JOINED]"
fi
"$SETUP_ENV/bin/python" -m pip install -e "$SETUP_SPEC"
if [[ "$SETUP_VLLM" == 1 ]]; then
  "$SETUP_ENV/bin/python" -m pip install 'vllm>=0.11,<1'
  "$SETUP_ENV/bin/python" -c 'import vllm; print("vLLM", vllm.__version__)'
fi
mkdir -p results/setup
if [[ "$SETUP_SMOKE" == 1 ]]; then
  MPLBACKEND=Agg "$SETUP_ENV/bin/python" scripts/run_pipeline.py \
    --input data/sample/poses.jsonl --mode mock --preview-per-class 1 --no-error-plots
fi
"$SETUP_ENV/bin/python" - "$SETUP_DIR" "$SETUP_ENV" <<'PY'
import importlib.metadata
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

packages = {}
for name in ('pose2actionLLM', 'matplotlib', 'vllm', 'mkdocs', 'fastapi', 'pytest'):
    try:
        packages[name] = importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        pass
report = dict(time_utc=datetime.now(timezone.utc).isoformat(), python=platform.python_version(),
              checkout=sys.argv[1], venv=sys.argv[2], packages=packages,
              note='Setup completed. Actual model download/inference was not run.')
Path('results/setup/setup.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
PY
printf '\nSetup complete.\nCheckout: %s\nEnvironment: %s\nReport: %s/results/setup/setup.json\n' \
  "$SETUP_DIR" "$SETUP_ENV" "$SETUP_DIR"
printf 'Next commands:\n  cd %q\n  export POSE_RUN_VENV=%q\n  bash scripts/run_server.sh --input data/test.jsonl\n' \
  "$SETUP_DIR" "$SETUP_ENV"
