"""Deterministic reference for the numeric system prompt; not the LLM backend."""

from math import hypot

from .preprocessing import preprocess


def classify_rules(sample, min_confidence=0):
    points = preprocess(sample, min_confidence)["keypoints"]
    torsos, thighs, arms = [], [], []
    for side in ("left", "right"):
        shoulder, elbow, hip, knee = (
            points[f"{side}_{part}"] for part in ("shoulder", "elbow", "hip", "knee")
        )
        if shoulder is not None and hip is not None:
            torsos.append((hip["x"] - shoulder["x"], hip["y"] - shoulder["y"]))
        if hip is not None and knee is not None:
            thighs.append((knee["x"] - hip["x"], knee["y"] - hip["y"]))
        if shoulder is not None and elbow is not None:
            arms.append(elbow["y"] - shoulder["y"])

    def mean_vector(vectors):
        return tuple(sum(v[i] for v in vectors) / len(vectors) for i in (0, 1))

    torso_length = sum(hypot(*v) for v in torsos) / len(torsos) if torsos else 0.0
    torso = mean_vector(torsos) if torsos else (0.0, 1.0)
    if hypot(*torso) <= 1e-8:
        torso = (0.0, 1.0)
    thigh = mean_vector(thighs) if thighs else None
    dot = cross = None
    if thigh is None or hypot(*thigh) <= 1e-8:
        standing = True
    else:
        dot = torso[0] * thigh[0] + torso[1] * thigh[1]
        cross = abs(torso[0] * thigh[1] - torso[1] * thigh[0])
        standing = dot > cross
    threshold = 0.05 * torso_length
    hand_up = any(delta <= threshold for delta in arms)
    return {
        "prediction": 2 * int(standing) + int(hand_up),
        "standing": standing,
        "hand_up": hand_up,
        "torso_vector": torso,
        "thigh_vector": thigh,
        "torso_length": torso_length,
        "dot": dot,
        "absolute_cross": cross,
        "arm_delta_y": arms,
        "arm_threshold": threshold,
    }
