"""Test orchestration and HTTP failures without downloading or running a model."""

import importlib.util
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from pose_llm_classifier.data import iter_samples

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("automation", ROOT / "scripts/run_pipeline.py")
automation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(automation)
DATA = ROOT / "data/sample/poses.jsonl"


@pytest.fixture
def runner(tmp_path, monkeypatch):
    monkeypatch.setattr(automation, "doctor", lambda: {"python": "test", "gpu": "not used"})
    # Plot rendering is covered by pipeline tests; keep orchestration tests small.
    monkeypatch.setattr(automation, "plot_comparison", lambda *args: None)

    def run(*options):
        args = automation.parse_args(
            ["--input", str(DATA), "--output-root", str(tmp_path), "--no-error-plots", *options]
        )
        code = automation.run(args)
        folder = sorted(args.output_root.iterdir())[-1]
        return code, folder, json.loads((folder / "run.json").read_text())

    return run


def test_mock_run_reports_metrics(runner):
    code, folder, state = runner("--mode", "mock")
    assert code == 0
    assert state["status"] == "completed"
    assert state["dataset"]["total"] == 4
    assert state["evaluations"][0]["metrics"]["accuracy"] == 0.25
    assert (folder / "feedback.md").exists()
    assert len((folder / "prompts.jsonl").read_text().splitlines()) == 4


def test_review_gate_does_not_call_endpoint(runner, monkeypatch):
    def forbidden(*args):
        pytest.fail("Unreviewed data must not reach endpoint")

    monkeypatch.setattr(automation, "endpoint_models", forbidden)
    code, _, state = runner("--mode", "remote")
    assert code == 2
    assert state["status"] == "needs_review"
    assert not state["evaluations"]


def test_invalid_input_preserves_feedback(runner):
    code, folder, state = runner("--input", "/missing/pose.jsonl")
    assert code == 1
    assert state["status"] == "failed"
    assert "FileNotFoundError" in (folder / "feedback.md").read_text()


def test_few_shot_overlap_normalized(runner, tmp_path):
    sample = next(iter_samples(DATA))
    sample.update(coordinate_space="pixel", image_width=640, image_height=480)
    sample["keypoints"] = {
        key: [point["x"] * 640, point["y"] * 480] for key, point in sample["keypoints"].items()
    }
    path = tmp_path / "examples.json"
    path.write_text(json.dumps(sample))
    # Use a separate output root so data file is not mistaken for a run folder.
    code, _, state = runner("--few-shot", str(path), "--output-root", str(tmp_path / "runs"))
    assert code == 1
    assert "overlap" in state["error"]


def test_remote_http_pipeline_and_parse_feedback(runner, monkeypatch):
    monkeypatch.delenv("POSE_API_KEY", raising=False)

    class Handler(BaseHTTPRequestHandler):
        count = 0

        def log_message(self, *args):
            pass

        def reply(self, value):
            body = json.dumps(value).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            self.reply({"data": [{"id": "test-model"}]})

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            assert body["model"] == "test-model"
            Handler.count += 1
            # Single-sample smoke works, then fail parsing on one evaluation sample.
            self.reply(
                {"choices": [{"message": {"content": "bad reply" if Handler.count == 3 else "0"}}]}
            )

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        code, folder, state = runner(
            "--mode",
            "remote",
            "--visualization-reviewed",
            "--models",
            "test-model",
            "--base-url",
            f"http://127.0.0.1:{server.server_port}/v1",
        )
        assert code == 1
        assert state["status"] == "completed_with_failures"
        assert state["evaluations"][0]["metrics"]["failed"] == 1
        records = [
            json.loads(line)
            for line in (folder / "model_00/zero_shot/predictions.jsonl").read_text().splitlines()
        ]
        assert records[1]["raw_response"] == "bad reply"
        assert records[1]["messages"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
