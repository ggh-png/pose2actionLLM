"""Normalize by image dimensions; never infer axes or mirror anatomical sides."""

from .data import validate_sample


def preprocess(sample, min_confidence=0.0):
    if not 0 <= min_confidence <= 1:
        raise ValueError("min_confidence must be in [0,1]")
    result = validate_sample(sample)
    pixel = result["coordinate_space"] == "pixel"
    width = result["image_width"] if pixel else 1
    height = result["image_height"] if pixel else 1
    points = {}
    for name, point in result["keypoints"].items():
        if (
            point is None
            or point.get("confidence", 1) < min_confidence
            or point.get("presence", 1) <= 0
        ):
            points[name] = None
        else:
            points[name] = dict(point, x=point["x"] / width, y=point["y"] / height)
    if not any(point is not None for point in points.values()):
        raise ValueError("No usable keypoints remain after preprocessing")
    result.update(keypoints=points, coordinate_space="normalized")
    return result
