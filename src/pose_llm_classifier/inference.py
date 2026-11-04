"""Mock development backend and an explicit opt-in remote chat backend."""

import json
import os
import re
import urllib.error
import urllib.request

from .features import extract_features
from .preprocessing import preprocess

SYSTEM_PROMPT = """You are a deterministic rule executor for one 2D human pose.
Apply ONLY the numeric rules below. Do not guess from pose names or appearance.
Output exactly one digit: 0, 1, 2, or 3. No other text.

CLASSES
0 = SITTING_HAND_DOWN
1 = SITTING_HAND_UP
2 = STANDING_HAND_DOWN
3 = STANDING_HAND_UP

INPUT
JSON contains normalized image keypoints: left/right shoulder, elbow, hip, knee.
x increases rightward; y increases downward. Left/right are anatomical.
A missing point is null. Never replace null with coordinates (0,0).
Use only the keypoints. Ignore the optional features object.
No wrists or ankles are available; HAND_UP means the elbow-based proxy below.
All angles and lengths refer to this normalized 2D coordinate plane.

EXACT PROCEDURE
Use both available sides. Average vectors component by component.
A pair is available only when both of its points are non-null.

A. BODY POSTURE
1. For each available shoulder-hip pair, calculate the downward torso vector:
   tx = hip_x - shoulder_x
   ty = hip_y - shoulder_y
   T = the mean of these torso vectors.
   If none exist, or T has length <= 0.00000001, use T = (0,1).
2. For each available hip-knee pair, calculate the thigh vector:
   vx = knee_x - hip_x
   vy = knee_y - hip_y
   V = the mean of these thigh vectors.
3. If there are no hip-knee pairs, or V has length <= 0.00000001,
   set standing = 1 as a fixed fallback. Otherwise calculate:
   dot = T_x * V_x + T_y * V_y
   cross = abs(T_x * V_y - T_y * V_x)
   If dot > cross: standing = 1.
   If dot <= cross: standing = 0.
   This means STANDING when the torso-to-thigh direction angle is less
   than 45 degrees; SITTING when it is 45 degrees or greater.
   Equivalently, the shoulder-hip-knee joint angle is greater than 135
   degrees for STANDING, and at most 135 degrees for SITTING.
   For an upright torso this reduces to:
   knee_y - hip_y > abs(knee_x - hip_x) => STANDING;
   knee_y - hip_y <= abs(knee_x - hip_x) => SITTING.
   Equality is always SITTING. Do not apply an extra tolerance.

B. ARM POSITION
1. Compute L as the mean Euclidean length of the available shoulder-hip
   pairs: sqrt(tx*tx + ty*ty). If none exist, L = 0.
   threshold = 0.05 * L.
2. For each available shoulder-elbow pair, calculate:
   delta_y = elbow_y - shoulder_y.
3. If at least one available side has delta_y <= threshold, set hand_up = 1.
   Otherwise set hand_up = 0, including when no shoulder-elbow pairs exist.
   Thus an elbow above the shoulder, at shoulder height, or no more than
   5 percent of torso length below the shoulder counts as HAND_UP.
   HAND_DOWN requires every available elbow to be farther below its shoulder.
   Equality is always HAND_UP. Do not use the other side to cancel an up arm.

C. OUTPUT
class_id = 2 * standing + hand_up.
standing=0, hand_up=0 => 0
standing=0, hand_up=1 => 1
standing=1, hand_up=0 => 2
standing=1, hand_up=1 => 3

Return only class_id as a single digit."""


def pose_payload(sample, min_confidence=0):
    processed = preprocess(sample, min_confidence)
    return {
        "coordinate_convention": "image: origin top-left, x right, y down",
        "coordinate_space": "normalized",
        "keypoints": processed["keypoints"],
        "features": extract_features(processed),
    }


def build_messages(sample, examples=(), min_confidence=0):
    system = SYSTEM_PROMPT
    messages = [{"role": "system", "content": system}]
    for example in examples:
        if example.get("label") is None:
            raise ValueError("Few-shot examples require labels")
        messages.extend(
            [
                {"role": "user", "content": json.dumps(pose_payload(example, min_confidence))},
                {"role": "assistant", "content": str(example["label"])},
            ]
        )
    messages.append({"role": "user", "content": json.dumps(pose_payload(sample, min_confidence))})
    return messages


class InvalidPrediction(ValueError):
    """Preserve the model output so automatic feedback can diagnose parse failures."""

    def __init__(self, raw_response):
        super().__init__(f"Model must return exactly one class digit, got {raw_response!r}")
        self.raw_response = raw_response


def parse_prediction(text):
    if not isinstance(text, str) or not re.fullmatch(r"\s*[0-3]\s*", text):
        raise InvalidPrediction(text)
    return int(text.strip())


class Classifier:
    def __init__(
        self, backend="mock", model="Qwen/Qwen3-4B", base_url=None, reviewed=False, timeout=60
    ):
        if backend not in ("mock", "remote"):
            raise ValueError("backend must be mock or remote")
        if backend == "remote" and not reviewed:
            raise ValueError("Inspect pose visualizations first, then set --visualization-reviewed")
        if backend == "remote" and (
            not base_url or not base_url.startswith(("http://", "https://"))
        ):
            raise ValueError("Remote inference requires an explicit http(s) base URL ending in /v1")
        self.backend, self.model, self.base_url, self.timeout = backend, model, base_url, timeout

    def build_messages(self, sample, examples=(), min_confidence=0):
        return build_messages(sample, examples, min_confidence)

    def predict(self, sample, examples=(), min_confidence=0):
        messages = self.build_messages(sample, examples, min_confidence)
        if self.backend == "mock":
            # Constant by design: validates plumbing, never claims to classify geometry.
            raw = "0"
        else:
            request = urllib.request.Request(
                self.base_url.rstrip("/") + "/chat/completions",
                data=json.dumps(
                    {"model": self.model, "messages": messages, "temperature": 0, "max_tokens": 256}
                ).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            key = os.environ.get("POSE_API_KEY")
            if key:
                request.add_header("Authorization", f"Bearer {key}")
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    payload = json.load(response)
                raw = payload["choices"][0]["message"]["content"]
            except (
                urllib.error.URLError,
                TimeoutError,
                KeyError,
                IndexError,
                TypeError,
                json.JSONDecodeError,
            ) as exc:
                raise RuntimeError(f"Remote inference failed: {type(exc).__name__}") from exc
        try:
            prediction = parse_prediction(raw)
        except InvalidPrediction as exc:
            exc.messages = messages
            raise
        return {
            "prediction": prediction,
            "raw_response": raw,
            "backend": self.backend,
            "model": self.model if self.backend == "remote" else "mock-constant-0",
            "messages": messages,
        }
