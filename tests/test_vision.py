import base64
import copy
import io
import json

import pytest

from pose_llm_classifier.data import load_sample
from pose_llm_classifier.vision import VISION_SYSTEM_PROMPT, VisionClassifier, render_model_input


def sample():
    return load_sample("data/sample/synthetic_100/3_STANDING_HAND_UP/synthetic-3-022.json")


def test_image_does_not_depend_on_ground_truth_or_ids(tmp_path):
    pose = sample()
    original = copy.deepcopy(pose)
    a = render_model_input(pose, tmp_path / "a.png").read_bytes()
    pose.update(label=0, prediction=1, id="label-secret", raised_arm="class-secret")
    b = render_model_input(pose, tmp_path / "b.png").read_bytes()
    assert a == b
    assert original["label"] == 3
    assert a.startswith(b"\x89PNG\r\n\x1a\n")


def test_multimodal_request_contains_real_png_and_identical_json(tmp_path, monkeypatch):
    pose = sample()
    path = render_model_input(pose, tmp_path / "0000.png")
    classifier = VisionClassifier(
        "remote", "vision-test", "http://localhost:18082/v1", True, image_paths={pose["id"]: path}
    )
    text_only = VisionClassifier("mock").build_messages(pose)

    def respond(request, timeout):
        body = json.loads(request.data)
        assert body["messages"][0] == text_only[0]
        text, image = body["messages"][1]["content"]
        assert text["text"] == text_only[1]["content"]
        assert set(json.loads(text["text"])) == {
            "keypoints",
            "features",
            "coordinate_space",
            "coordinate_convention",
        }
        prefix, encoded = image["image_url"]["url"].split(",", 1)
        assert prefix == "data:image/png;base64"
        assert base64.b64decode(encoded) == path.read_bytes()
        return io.BytesIO(b'{"choices":[{"message":{"content":"3"}}]}')

    monkeypatch.setattr("pose_llm_classifier.inference.urllib.request.urlopen", respond)
    assert classifier.predict(pose)["prediction"] == 3


def test_png_only_excludes_json(tmp_path):
    pose = sample()
    path = render_model_input(pose, tmp_path / "0000.png")
    classifier = VisionClassifier("mock", image_paths={pose["id"]: path}, include_json=False)
    messages = classifier.build_messages(pose)
    text, image = messages[-1]["content"]
    assert text["text"] == "Classify this single skeleton image. Return one class digit."
    assert pose["id"] not in text["text"]
    assert "keypoints" not in text["text"]
    assert image["type"] == "image_url"


def test_missing_both_modalities_rejected():
    import pytest

    with pytest.raises(ValueError, match="At least one input modality"):
        VisionClassifier("mock", include_json=False)


def test_clean_shape_renderer_ignores_labels(tmp_path):
    from pose_llm_classifier.vision import render_shape_input

    pose = sample()
    a = render_shape_input(pose, tmp_path / "clean-a.png").read_bytes()
    pose.update(label=0, prediction=2, id="private-class-id", raised_arm="secret")
    b = render_shape_input(pose, tmp_path / "clean-b.png").read_bytes()
    assert a == b


def test_cli_refuses_to_mix_image_styles(tmp_path):
    import subprocess
    import sys
    from pathlib import Path

    source = tmp_path / "pose.json"
    source.write_text(json.dumps(sample()))
    command = [
        sys.executable,
        str(Path(__file__).resolve().parents[1] / "scripts/benchmark_vision.py"),
        "--input",
        str(source),
        "--output-dir",
        str(tmp_path / "run"),
        "--prepare-only",
        "--image-style",
    ]
    subprocess.run(command + ["clean"], check=True, capture_output=True)
    result = subprocess.run(command + ["plot"], capture_output=True, text=True)
    assert result.returncode != 0
    assert "Existing image style differs" in result.stderr


@pytest.mark.parametrize("mode", ["json_only", "png_only", "png_json"])
def test_native_user_adapter_preserves_instruction_and_input(tmp_path, mode):
    pose = sample()
    path = render_model_input(pose, tmp_path / "input.png")
    image_paths = None if mode == "json_only" else {pose["id"]: path}
    kwargs = {"image_paths": image_paths, "include_json": mode != "png_only"}
    original = VisionClassifier("mock", **kwargs).build_messages(pose)
    adapted = VisionClassifier(
        "mock", **kwargs, instruction_role="user", image_first=True
    ).build_messages(pose)
    assert len(adapted) == 1 and adapted[0]["role"] == "user"
    old_content = original[-1]["content"]
    new_content = adapted[0]["content"]
    if isinstance(old_content, list):
        assert new_content[0] == old_content[1]
        assert new_content[1]["text"] == VISION_SYSTEM_PROMPT + "\n\n" + old_content[0]["text"]
    else:
        assert new_content == VISION_SYSTEM_PROMPT + "\n\n" + old_content
