#!/usr/bin/env python3
"""Run benchmark models from a checkout or installed package."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pose_llm_classifier.cli import run  # noqa: E402

if __name__ == "__main__":
    run("benchmark_models")
