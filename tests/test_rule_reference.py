"""Geometry boundary checks independent of the synthetic evaluation labels."""

import pytest

from pose_llm_classifier.rule_reference import classify_rules


def pose(knee=(0.5, 1.0), elbow=(0.5, 0.75)):
    points = {
        f"{side}_{part}": None
        for side in ("left", "right")
        for part in ("shoulder", "elbow", "hip", "knee")
    }
    points.update(
        left_shoulder=[0.5, 0.0], left_hip=[0.5, 0.5], left_knee=list(knee), left_elbow=list(elbow)
    )
    return {"coordinate_space": "normalized", "keypoints": points}


@pytest.mark.parametrize(
    "knee,elbow,expected",
    [
        ((0.75, 0.5), (0.5, 0.75), 0),
        ((0.75, 0.5), (0.5, 0.0), 1),
        ((0.5, 1.0), (0.5, 0.75), 2),
        ((0.5, 1.0), (0.5, 0.0), 3),
        ((0.75, 0.75), (0.5, 0.025), 1),  # Both thresholds: sitting and up.
        ((0.75, 0.750001), (0.5, 0.025001), 2),
    ],
)
def test_boundaries(knee, elbow, expected):
    assert classify_rules(pose(knee, elbow))["prediction"] == expected


def test_tilt_and_missing_fallbacks():
    sample = pose()
    sample["keypoints"].update(
        left_shoulder=[0.1, 0.1], left_hip=[0.4, 0.4], left_knee=[0.7, 0.7], left_elbow=None
    )
    assert classify_rules(sample)["prediction"] == 2
    sample["keypoints"] = dict.fromkeys(sample["keypoints"])
    with pytest.raises(ValueError, match="At least one finite keypoint"):
        classify_rules(sample)
    sample["keypoints"]["left_elbow"] = [0.0, 0.0]
    result = classify_rules(sample)
    assert result["prediction"] == 2
    assert result["arm_threshold"] == 0


def test_available_up_arm_wins():
    sample = pose()
    sample["keypoints"].update(right_shoulder=[0.6, 0.0], right_elbow=[0.6, 0.0])
    assert classify_rules(sample)["prediction"] == 3


def test_reference_metrics_keep_backend_name(tmp_path):
    from pose_llm_classifier.evaluation import evaluate

    class Reference:
        backend, model = "deterministic", "numeric-rule-reference"

        def predict(self, sample, *args):
            return classify_rules(sample)

    sample = dict(pose(), label=2)
    metrics = evaluate([sample], Reference(), tmp_path, save_errors=False)
    assert metrics["model"] == "numeric-rule-reference"
    assert metrics["is_mock"] is False
    assert metrics["accuracy"] == 1.0
