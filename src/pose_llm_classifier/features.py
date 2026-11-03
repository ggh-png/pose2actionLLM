"""Derived features in normalized image space; unavailable features are null."""

from math import hypot

from .preprocessing import preprocess


def extract_features(sample):
    points = preprocess(sample)["keypoints"]
    features = {}
    torso_lengths = []
    for side in ("left", "right"):
        shoulder, elbow, hip = (
            points.get(f"{side}_{part}") for part in ("shoulder", "elbow", "hip")
        )
        features[f"{side}_elbow_above_shoulder"] = (
            elbow["y"] < shoulder["y"] if elbow and shoulder else None
        )
        if shoulder and hip:
            torso_lengths.append(hypot(shoulder["x"] - hip["x"], shoulder["y"] - hip["y"]))
    torso = sum(torso_lengths) / len(torso_lengths) if torso_lengths else None
    features["torso_length"] = torso
    for side in ("left", "right"):
        shoulder, elbow = (points.get(f"{side}_{part}") for part in ("shoulder", "elbow"))
        features[f"{side}_elbow_relative_y"] = (
            (elbow["y"] - shoulder["y"]) / torso if elbow and shoulder and torso else None
        )
    return features
