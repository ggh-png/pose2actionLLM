"""Mock development backend and an explicit opt-in remote chat backend."""

import json
import os
import re
import urllib.error
import urllib.request

from .data import LABELS
from .features import extract_features
from .preprocessing import preprocess


def pose_payload(sample, min_confidence=0):
    processed = preprocess(sample, min_confidence)
    return {
        "coordinate_convention": "image: origin top-left, x right, y down",
        "coordinate_space": "normalized",
        "keypoints": processed["keypoints"],
        "features": extract_features(processed),
    }


def build_messages(sample, examples=(), min_confidence=0):
    system = (
        "Classify a single 2D human pose. Return exactly one digit (0, 1, 2, or 3). "
        "Class map: " + json.dumps(dict(enumerate(LABELS))) + ". "
        "Only 8 joints are available: left/right shoulder, elbow, hip, knee. No wrists or ankles. For the existing HAND_UP label, use at least one elbow above its same-side shoulder as an arm-raised proxy; actual hand height is unobservable. "
        "Left/right are anatomical. Missing points are null; never interpret them as zero. "
        "Infer sitting/standing from the available joint geometry. /no_think"
    )
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

    def predict(self, sample, examples=(), min_confidence=0):
        messages = build_messages(sample, examples, min_confidence)
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
