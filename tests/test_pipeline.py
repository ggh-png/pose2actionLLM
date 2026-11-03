import copy
import json
from pathlib import Path

import pytest

from pose_llm_classifier.cli import run
from pose_llm_classifier.data import iter_samples, load_sample
from pose_llm_classifier.evaluation import evaluate
from pose_llm_classifier.features import extract_features
from pose_llm_classifier.inference import Classifier, build_messages, parse_prediction
from pose_llm_classifier.preprocessing import preprocess
from pose_llm_classifier.visualization import plot_comparison, plot_pose

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/sample"


@pytest.fixture
def sample():
    return load_sample(DATA / "pixel.json")


@pytest.mark.parametrize("name", ["poses.jsonl", "poses.csv"])
def test_file_adapters(name):
    samples = list(iter_samples(DATA / name))
    assert [s["label"] for s in samples] == list(range(4))
    assert load_sample(DATA / name, 2)["label"] == 2


def test_normalize_without_mutation(sample):
    before = copy.deepcopy(sample)
    result = preprocess(sample)
    assert result["keypoints"]["left_shoulder"]["x"] == pytest.approx(0.4)
    assert result["keypoints"]["left_shoulder"]["y"] == pytest.approx(0.28)
    assert sample == before
    assert preprocess(result) == result


@pytest.mark.parametrize("value", [float("nan"), float("inf"), True, "bad", -1, 9999])
def test_reject_invalid_coordinate(sample, value):
    sample["keypoints"]["nose"]["x"] = value
    with pytest.raises(ValueError):
        load_sample(sample)


def test_missing_and_confidence(sample):
    sample["keypoints"]["nose"] = [0, 0]
    sample["keypoints"]["left_wrist"] = None
    sample["keypoints"]["right_wrist"] = {"x": 10, "y": 20, "confidence": 0.1}
    result = preprocess(sample, 0.5)
    assert result["keypoints"]["nose"]["x"] == 0
    assert result["keypoints"]["right_wrist"] is None
    assert extract_features(result)["left_hand_above_shoulder"] is None


def test_features_follow_downward_y(sample):
    features = extract_features(sample)
    assert features["left_hand_above_shoulder"] is True
    assert features["right_hand_above_shoulder"] is False
    assert features["left_wrist_relative_y"] < 0


def test_prompt_does_not_leak_labels(sample):
    sample.update(label=3, prediction=1, secret="do not include", id="label-bearing-id")
    payload = json.loads(build_messages(sample)[-1]["content"])
    assert set(payload) == {"keypoints", "features", "coordinate_space", "coordinate_convention"}
    assert payload["keypoints"]["left_shoulder"]["x"] == pytest.approx(0.4)
    messages = build_messages(sample, [sample])
    assert messages[-2] == {"role": "assistant", "content": "3"}


@pytest.mark.parametrize("text", ["class 2", "2 or 3", "<think>1</think>2", "4", "", None])
def test_strict_prediction(text):
    with pytest.raises(ValueError):
        parse_prediction(text)


def test_remote_requires_review():
    with pytest.raises(ValueError, match="Inspect"):
        Classifier("remote", base_url="http://localhost:8000/v1")


def test_remote_protocol_with_fake_transport(sample, monkeypatch):
    import io

    from pose_llm_classifier import inference

    def respond(request, timeout):
        body = json.loads(request.data)
        assert request.full_url == "http://localhost:8000/v1/chat/completions"
        assert body["model"] == "test-model"
        assert "label" not in json.loads(body["messages"][-1]["content"])
        return io.BytesIO(b'{"choices":[{"message":{"content":"3"}}]}')

    monkeypatch.setattr(inference.urllib.request, "urlopen", respond)
    result = Classifier("remote", "test-model", "http://localhost:8000/v1", True).predict(sample)
    assert result["prediction"] == 3


def test_plots_and_missing_edges(sample, tmp_path):
    sample["keypoints"]["left_wrist"] = None
    for path in plot_comparison(sample, tmp_path, True):
        assert path.read_bytes().startswith(b"\x89PNG")
    assert plot_pose(dict(sample, prediction=0), tmp_path / "error.png").exists()


def test_evaluation_and_failure_accounting(tmp_path):
    result = evaluate(iter_samples(DATA / "poses.jsonl"), Classifier(), tmp_path)
    assert result["accuracy"] == 0.25
    assert result["is_mock"] is True
    assert len(list((tmp_path / "errors").glob("*.png"))) == 3

    class Broken:
        backend, model = "remote", "broken"

        def predict(self, *args):
            raise ValueError("invalid reply")

    result = evaluate(iter_samples(DATA / "poses.jsonl"), Broken(), tmp_path / "broken")
    assert result["failed"] == 4
    assert result["accuracy"] == 0


def test_dataset_filters_and_dry_run(tmp_path):
    run(
        "visualize_dataset",
        ["--input", str(DATA / "poses.jsonl"), "--class-id", "3", "--output-dir", str(tmp_path)],
    )
    assert (tmp_path / "sample_0003.png").exists()
    run(
        "evaluate_llm",
        [
            "--input",
            str(DATA / "poses.jsonl"),
            "--backend",
            "remote",
            "--dry-run",
            "--output-dir",
            str(tmp_path),
        ],
    )
    assert len((tmp_path / "prompts.jsonl").read_text().splitlines()) == 4


def test_api_validation(sample):
    from fastapi.testclient import TestClient

    from pose_llm_classifier.api import create_app

    client = TestClient(create_app(Classifier()))
    assert client.get("/health").json()["backend"] == "mock"
    response = client.post("/predict", json={"sample": sample})
    assert response.status_code == 200
    assert response.json()["backend"] == "mock"
    assert client.post("/predict", json={"sample": {}}).status_code == 422
