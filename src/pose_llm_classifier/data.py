"""Explicit, named-keypoint input schema and JSON/JSONL/CSV adapters."""

import csv
import json
import math
from pathlib import Path

LABELS = ("SITTING_HAND_DOWN", "SITTING_HAND_UP", "STANDING_HAND_DOWN", "STANDING_HAND_UP")
KEYPOINTS = (
    "nose",
    "left_eye",
    "right_eye",
    "left_ear",
    "right_ear",
    "left_shoulder",
    "right_shoulder",
    "left_elbow",
    "right_elbow",
    "left_wrist",
    "right_wrist",
    "left_hip",
    "right_hip",
    "left_knee",
    "right_knee",
    "left_ankle",
    "right_ankle",
)


def number(value, field):
    if isinstance(value, bool):
        raise ValueError(f"{field}: boolean is not a coordinate")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field}: expected a finite number") from exc
    if not math.isfinite(result):
        raise ValueError(f"{field}: expected a finite number")
    return result


def class_id(value):
    if value is None or value == "":
        return None
    if isinstance(value, str) and value in LABELS:
        return LABELS.index(value)
    if isinstance(value, bool) or str(value) not in ("0", "1", "2", "3"):
        raise ValueError(f"Unknown class: {value!r}")
    return int(value)


def validate_sample(sample):
    if not isinstance(sample, dict) or not isinstance(sample.get("keypoints"), dict):
        raise ValueError("Sample must contain a named 'keypoints' object")
    result = dict(sample)
    space = sample.get("coordinate_space", "normalized")
    if space not in ("normalized", "pixel"):
        raise ValueError("coordinate_space must be normalized or pixel")
    if sample.get("coordinate_convention", "image") != "image":
        raise ValueError("Only image coordinates (x right, y down) are supported")
    result.update(coordinate_space=space, coordinate_convention="image")
    if space == "pixel":
        for field in ("image_width", "image_height"):
            result[field] = number(sample.get(field), field)
            if result[field] <= 0:
                raise ValueError(f"{field} must be positive")
    points = {}
    for name, point in sample["keypoints"].items():
        if name not in KEYPOINTS:
            raise ValueError(f"Unknown keypoint {name!r}; use named COCO keypoints")
        if point is None:
            points[name] = None
            continue
        if isinstance(point, (list, tuple)) and len(point) in (2, 3):
            point = dict(zip(("x", "y", "confidence"), point))
        if not isinstance(point, dict):
            raise ValueError(f"{name}: expected [x,y], [x,y,confidence], object, or null")
        parsed = {}
        for field in ("confidence", "presence"):
            if field in point:
                parsed[field] = number(point[field], f"{name}.{field}")
                if not 0 <= parsed[field] <= 1:
                    raise ValueError(f"{name}.{field} must be in [0,1]")
        # Missing coordinates are explicit; (0,0) is a valid point.
        if point.get("x") is None and point.get("y") is None:
            points[name] = None
            continue
        parsed.update({axis: number(point.get(axis), f"{name}.{axis}") for axis in ("x", "y")})
        for axis, bound in (
            ("x", result.get("image_width", 1)),
            ("y", result.get("image_height", 1)),
        ):
            maximum = 1 if space == "normalized" else bound
            if not 0 <= parsed[axis] <= maximum:
                raise ValueError(f"{name}.{axis} outside [0,{maximum}]; check coordinate_space")
        points[name] = parsed
    if not any(p is not None for p in points.values()):
        raise ValueError("At least one finite keypoint is required")
    result["keypoints"] = points
    for field in ("label", "prediction"):
        if field in result:
            result[field] = class_id(result[field])
    return result


def iter_samples(path):
    path = Path(path)
    with path.open(encoding="utf-8-sig", newline="") as stream:
        if path.suffix.lower() == ".json":
            payload = json.load(stream)
            rows = payload if isinstance(payload, list) else [payload]
        elif path.suffix.lower() == ".jsonl":
            rows = (json.loads(line) for line in stream if line.strip())
        elif path.suffix.lower() == ".csv":

            def csv_rows():
                for row in csv.DictReader(stream):
                    row["keypoints"] = json.loads(row["keypoints"])
                    yield row

            rows = csv_rows()
        else:
            raise ValueError("Input must be .json, .jsonl or .csv")
        for index, row in enumerate(rows):
            try:
                yield validate_sample(row)
            except (ValueError, TypeError) as exc:
                raise ValueError(f"{path}: sample {index}: {exc}") from exc


def load_sample(source, index=0):
    if index < 0:
        raise ValueError("index must be nonnegative")
    if isinstance(source, dict):
        if index:
            raise IndexError("dict input has only one sample")
        return validate_sample(source)
    for i, sample in enumerate(iter_samples(source)):
        if i == index:
            return sample
    raise IndexError(f"Sample index {index} is out of range")


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8"
    )
