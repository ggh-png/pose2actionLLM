"""Optional HTTP interface. Defaults to a clearly identified constant mock."""

import os

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .data import load_sample
from .inference import Classifier


class PredictRequest(BaseModel):
    sample: dict
    min_confidence: float = Field(default=0, ge=0, le=1)


def create_app(classifier=None):
    classifier = classifier or Classifier(
        backend=os.getenv("POSE_BACKEND", "mock"),
        model=os.getenv("POSE_MODEL", "Qwen/Qwen3-4B"),
        base_url=os.getenv("POSE_BASE_URL"),
        reviewed=os.getenv("POSE_VISUALIZATION_REVIEWED") == "1",
    )
    app = FastAPI(title="pose2actionLLM", version="0.1.0")

    @app.get("/health")
    def health():
        return {"status": "ok", "backend": classifier.backend}

    @app.post("/predict")
    def predict(request: PredictRequest):
        try:
            sample = load_sample(request.sample)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        try:
            return classifier.predict(sample, min_confidence=request.min_confidence)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(502, str(exc)) from exc

    return app


app = create_app()
