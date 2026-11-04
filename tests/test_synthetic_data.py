"""Check profile projections, seated/standing geometry, and paired assets."""

import importlib.util
import json
from collections import Counter
from pathlib import Path

from PIL import Image

from pose_llm_classifier.data import KEYPOINTS, iter_samples, load_sample

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/sample"


def test_side_view_geometry_and_reproducibility():
    spec = importlib.util.spec_from_file_location(
        "synthetic_generator", ROOT / "scripts/generate_synthetic_dataset.py"
    )
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)
    generated = generator.generate_samples(25, 42)
    rows = list(iter_samples(DATA / "synthetic_100.jsonl"))
    assert generated == rows
    assert Counter(row["label"] for row in rows) == {0: 25, 1: 25, 2: 25, 3: 25}
    assert len({json.dumps(row["keypoints"], sort_keys=True) for row in rows}) == 100
    for row in rows:
        assert row["generator_version"] == 4
        assert row["view"] == "side_unmirrored"
        assert 85 <= abs(row["camera_yaw_degrees"]) <= 88
        direction = -1 if row["facing_direction"] == "image_left" else 1
        assert direction * row["camera_yaw_degrees"] > 0
        points = row["keypoints"]
        assert set(points) == set(KEYPOINTS)
        # A frontal torso would have a much wider shoulder/hip separation.
        for joint in ("shoulder", "hip"):
            assert abs(points[f"left_{joint}"]["x"] - points[f"right_{joint}"]["x"]) < 0.02
            assert abs(points[f"left_{joint}"]["y"] - points[f"right_{joint}"]["y"]) < 0.007
        hip_center = (points["left_hip"]["x"] + points["right_hip"]["x"]) / 2
        knee_center = (points["left_knee"]["x"] + points["right_knee"]["x"]) / 2
        seated = row["label"] < 2
        if seated:
            assert 0.14 < direction * (knee_center - hip_center) < 0.25
        else:
            assert abs(knee_center - hip_center) < 0.02
        for side in ("left", "right"):
            hip, knee = points[f"{side}_hip"], points[f"{side}_knee"]
            projected_length = knee["y"] - hip["y"]
            if seated:
                assert 0.14 < direction * (knee["x"] - hip["x"]) < 0.25
                assert 0 < projected_length < 0.035
            else:
                assert abs(knee["x"] - hip["x"]) < 0.04
                assert 0.14 < projected_length < 0.25
    for seated in (True, False):
        directions = Counter(row["facing_direction"] for row in rows if (row["label"] < 2) == seated)
        assert directions == {"image_left": 25, "image_right": 25}


def test_committed_json_and_png_pairs():
    folder = DATA / "synthetic_100"
    manifest = json.loads((folder / "manifest.json").read_text())
    rows = {row["id"]: row for row in iter_samples(DATA / "synthetic_100.jsonl")}
    assert manifest["total"] == len(manifest["samples"]) == 100
    assert manifest["generator_version"] == 4
    assert manifest["view"] == "side_unmirrored"
    assert manifest["projection"] == "orthographic"
    assert manifest["facing_counts"] == {"image_left": 50, "image_right": 50}
    assert len(list(folder.glob("*/*.json"))) == 100
    assert len(list(folder.glob("*/*.png"))) == 100
    assert len(list(folder.glob("overview_*.png"))) == 4
    for record in manifest["samples"]:
        assert load_sample(folder / record["json"]) == rows[record["id"]]
        with Image.open(folder / record["image"]) as image:
            image.verify()
