"""Shared entry points for the six project scripts."""

import argparse
import json
import random
from pathlib import Path

from .data import iter_samples, load_sample, write_json
from .evaluation import evaluate
from .features import extract_features
from .inference import Classifier, build_messages
from .preprocessing import preprocess
from .visualization import plot_comparison, plot_pose


def parser(command):
    p = argparse.ArgumentParser(description=command.replace("_", " "))
    p.add_argument("--input", required=True)
    p.add_argument("--output-dir", default="results/" + command)
    p.add_argument("--min-confidence", type=float, default=0)
    if command == "visualize_pose":
        p.add_argument("--index", type=int, default=0)
        p.add_argument("--prediction", type=int, choices=range(4))
        p.add_argument("--show-preprocessed", action="store_true")
        p.add_argument("--show-features", action="store_true")
    if command == "visualize_dataset":
        p.add_argument("--num-samples", type=int, default=16)
        p.add_argument("--class-id", type=int, choices=range(4))
        p.add_argument("--seed", type=int, default=42)
        p.add_argument("--errors-only", action="store_true")
        p.add_argument("--show-features", action="store_true")
    if command in ("preprocess", "extract_features"):
        p.add_argument("--output", required=True)
    if command in ("evaluate_llm", "benchmark_models"):
        p.add_argument("--backend", choices=("mock", "remote"), default="mock")
        p.add_argument("--model", default="Qwen/Qwen3-4B")
        p.add_argument("--base-url")
        p.add_argument("--visualization-reviewed", action="store_true")
        p.add_argument("--few-shot", help="Separate labeled training examples; never the test file")
        p.add_argument("--no-error-plots", action="store_true")
        p.add_argument("--dry-run", action="store_true", help="Write prompts without inference")
    if command == "benchmark_models":
        p.add_argument("--models", nargs="+", required=True)
    return p


def run(command, argv=None):
    p = parser(command)
    args = p.parse_args(argv)
    try:
        if not 0 <= args.min_confidence <= 1:
            raise ValueError("min-confidence must be in [0,1]")
        output = Path(args.output_dir)
        if command == "visualize_pose":
            sample = load_sample(args.input, args.index)
            if args.prediction is not None:
                sample["prediction"] = args.prediction
            if args.show_preprocessed:
                paths = plot_comparison(sample, output, args.show_features, args.min_confidence)
            else:
                paths = [plot_pose(sample, output / "raw_pose.png", args.show_features)]
            for path in paths:
                print(path)
        elif command == "visualize_dataset":
            if args.num_samples <= 0:
                raise ValueError("num-samples must be positive")
            rng, selected, count = random.Random(args.seed), [], 0
            # Reservoir sampling bounds memory independently of dataset size.
            for index, sample in enumerate(iter_samples(args.input)):
                if args.class_id is not None and sample.get("label") != args.class_id:
                    continue
                if args.errors_only and (
                    sample.get("prediction") is None
                    or sample.get("label") is None
                    or sample["prediction"] == sample["label"]
                ):
                    continue
                count += 1
                if len(selected) < args.num_samples:
                    selected.append((index, sample))
                else:
                    slot = rng.randrange(count)
                    if slot < args.num_samples:
                        selected[slot] = index, sample
            if not selected:
                raise ValueError("No samples match the requested filters")
            for index, sample in sorted(selected):
                print(plot_pose(sample, output / f"sample_{index:04d}.png", args.show_features))
            write_json(
                output / "selection.json",
                {"seed": args.seed, "indices": sorted(i for i, _ in selected)},
            )
        elif command in ("preprocess", "extract_features"):
            if Path(args.input).resolve() == Path(args.output).resolve():
                raise ValueError("Output must differ from input")
            path = Path(args.output)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8") as stream:
                for sample in iter_samples(args.input):
                    result = preprocess(sample, args.min_confidence)
                    if command == "extract_features":
                        result["features"] = extract_features(result)
                    stream.write(json.dumps(result, ensure_ascii=False, allow_nan=False) + "\n")
            print(path)
        else:
            examples = []
            if args.few_shot:
                if Path(args.few_shot).resolve() == Path(args.input).resolve():
                    raise ValueError(
                        "Few-shot examples must be separate from the evaluation dataset"
                    )
                examples = list(iter_samples(args.few_shot))
            if args.dry_run:
                output.mkdir(parents=True, exist_ok=True)
                with (output / "prompts.jsonl").open("w", encoding="utf-8") as stream:
                    for sample in iter_samples(args.input):
                        stream.write(
                            json.dumps(build_messages(sample, examples, args.min_confidence)) + "\n"
                        )
                print(output / "prompts.jsonl")
                return
            models = args.models if command == "benchmark_models" else [args.model]
            summaries = []
            for index, model in enumerate(models):
                classifier = Classifier(
                    args.backend, model, args.base_url, args.visualization_reviewed
                )
                folder = output / f"model_{index:02d}" if command == "benchmark_models" else output
                summaries.append(
                    evaluate(
                        iter_samples(args.input),
                        classifier,
                        folder,
                        examples,
                        not args.no_error_plots,
                        args.min_confidence,
                    )
                )
            if command == "benchmark_models":
                write_json(output / "benchmark.json", summaries)
            print(json.dumps(summaries, indent=2))
    except (ValueError, IndexError, KeyError, OSError, RuntimeError) as exc:
        p.error(str(exc))
