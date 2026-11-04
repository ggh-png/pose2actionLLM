#!/usr/bin/env python3
"""Compare JSON, label-free skeleton PNG, and combined inputs on one vision model."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pose_llm_classifier.data import iter_samples, write_json  # noqa: E402
from pose_llm_classifier.evaluation import evaluate  # noqa: E402
from pose_llm_classifier.vision import (  # noqa: E402
    VISION_SYSTEM_PROMPT,
    VisionClassifier,
    render_model_input,
    render_shape_input,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--model", default="Qwen/Qwen3-VL-8B-Instruct")
    parser.add_argument("--base-url", default="http://127.0.0.1:18082/v1")
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--visualization-reviewed", action="store_true")
    parser.add_argument(
        "--modes",
        nargs="+",
        choices=["json_only", "png_only", "png_json"],
        default=["json_only", "png_json"],
    )
    parser.add_argument("--prompt-file", help="Optional frozen system prompt text file")
    parser.add_argument("--image-style", choices=["plot", "clean"], default="plot")
    parser.add_argument("--instruction-role", choices=["system", "user"], default="system")
    parser.add_argument("--image-first", action="store_true")
    args = parser.parse_args()
    prompt = (
        Path(args.prompt_file).read_text().rstrip("\n")
        if args.prompt_file
        else VISION_SYSTEM_PROMPT
    )
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    style_path = output / "image-style.json"
    if style_path.exists() and json.loads(style_path.read_text())["style"] != args.image_style:
        parser.error("Existing image style differs; choose a new output directory")
    write_json(style_path, {"style": args.image_style})
    snapshot = output / "synthetic_100.jsonl"
    data = Path(args.input).read_bytes()
    if snapshot.exists() and snapshot.read_bytes() != data:
        parser.error("Existing snapshot differs; choose a new output directory")
    snapshot.write_bytes(data)
    samples = list(iter_samples(snapshot))
    ids = [sample["id"] for sample in samples]
    if len(ids) != len(set(ids)):
        parser.error("Image mapping requires unique sample IDs")
    images = {}
    manifest = []
    for index, sample in enumerate(samples):
        path = output / "images" / f"{index:04d}.png"
        if not path.exists():
            renderer = render_shape_input if args.image_style == "clean" else render_model_input
            renderer(sample, path)
        images[sample["id"]] = path
        manifest.append(
            {
                "index": index,
                "id": sample["id"],
                "path": str(path.relative_to(output)),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    write_json(output / "image-manifest.json", manifest)
    (output / "system-prompt.txt").write_text(prompt + "\n")
    if args.prepare_only:
        print(f"Prepared {len(samples)} label-free PNGs at {output}")
        return
    if not args.visualization_reviewed:
        parser.error("Inspect the prepared PNGs, then set --visualization-reviewed")
    summaries = {}
    for mode in args.modes:
        image_paths = None if mode == "json_only" else images
        folder = output / mode
        if (folder / "metrics.json").exists():
            parser.error("Existing metrics would be overwritten; choose a new output directory")
        classifier = VisionClassifier(
            "remote",
            args.model,
            args.base_url,
            True,
            image_paths=image_paths,
            include_json=mode != "png_only",
            system_prompt=prompt,
            instruction_role=args.instruction_role,
            image_first=args.image_first,
        )
        print("Evaluating " + mode, flush=True)
        summaries[mode] = evaluate(samples, classifier, folder)
        print(json.dumps(summaries[mode]), flush=True)
    write_json(output / "comparison.json", summaries)


if __name__ == "__main__":
    main()
