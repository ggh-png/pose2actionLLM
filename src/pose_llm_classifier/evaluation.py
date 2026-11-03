"""Streaming evaluation with auditable prompts, failure accounting and error plots."""

import json
import time
from pathlib import Path

from .data import LABELS, write_json
from .visualization import plot_pose


def evaluate(samples, classifier, output_dir, examples=(), save_errors=True, min_confidence=0):
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    confusion = [[0] * 4 for _ in range(4)]
    total = correct = failed = 0
    durations = []
    with (output / "predictions.jsonl").open("w", encoding="utf-8") as stream:
        for index, sample in enumerate(samples):
            if sample.get("label") is None:
                raise ValueError(f"Evaluation sample {index} has no label")
            total += 1
            start = time.perf_counter()
            try:
                result = classifier.predict(sample, examples, min_confidence)
            except (ValueError, RuntimeError) as exc:
                result = {"prediction": None, "error": str(exc)}
                failed += 1
            elapsed = time.perf_counter() - start
            durations.append(elapsed)
            prediction = result["prediction"]
            row = dict(sample, **result, index=index, elapsed_seconds=elapsed)
            stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
            if prediction is not None:
                confusion[sample["label"]][prediction] += 1
                correct += prediction == sample["label"]
                if save_errors and prediction != sample["label"]:
                    plot_pose(
                        row,
                        output
                        / "errors"
                        / f"sample_{index:04d}_GT_{sample['label']}_PRED_{prediction}.png",
                    )
    if not total:
        raise ValueError("Evaluation dataset is empty")
    per_class = {}
    for i, name in enumerate(LABELS):
        tp = confusion[i][i]
        predicted = sum(row[i] for row in confusion)
        support = sum(confusion[i])
        precision = tp / predicted if predicted else 0
        recall = tp / support if support else 0
        per_class[name] = {
            "precision": precision,
            "recall_on_valid_predictions": recall,
            "f1_on_valid_predictions": 2 * precision * recall / (precision + recall)
            if precision + recall
            else 0,
            "valid_support": support,
        }
    summary = {
        "backend": classifier.backend,
        "model": classifier.model if classifier.backend == "remote" else "mock-constant-0",
        "is_mock": classifier.backend == "mock",
        "total": total,
        "correct": correct,
        "failed": failed,
        "accuracy": correct / total,
        "confusion_matrix": confusion,
        "labels": LABELS,
        "per_class": per_class,
        "mean_latency_seconds": sum(durations) / total,
        "note": "Mock metrics are plumbing checks only. Failures count as incorrect in accuracy; "
        "confusion matrix and per-class metrics exclude failed predictions.",
    }
    write_json(output / "metrics.json", summary)
    return summary
