"""Derived features in normalized image space; unavailable features are null."""

from math import hypot

from .preprocessing import preprocess


def extract_features(sample):
    points = preprocess(sample)["keypoints"]
    features = {}
    torso_lengths = []
    for side in ("left", "right"):
        shoulder, wrist, hip = (
            points.get(f"{side}_{part}") for part in ("shoulder", "wrist", "hip")
        )
        features[f"{side}_hand_above_shoulder"] = (
            wrist["y"] < shoulder["y"] if wrist and shoulder else None
        )
        if shoulder and hip:
            torso_lengths.append(hypot(shoulder["x"] - hip["x"], shoulder["y"] - hip["y"]))
    torso = sum(torso_lengths) / len(torso_lengths) if torso_lengths else None
    features["torso_length"] = torso
    for side in ("left", "right"):
        shoulder, wrist = (points.get(f"{side}_{part}") for part in ("shoulder", "wrist"))
        features[f"{side}_wrist_relative_y"] = (
            (wrist["y"] - shoulder["y"]) / torso if wrist and shoulder and torso else None
        )
    return features
