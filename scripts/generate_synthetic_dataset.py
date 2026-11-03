"""Generate balanced synthetic poses and render individual/class overview PNGs."""

import argparse
import json
import random
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pose_llm_classifier.data import LABELS, validate_sample, write_json  # noqa: E402
from pose_llm_classifier.features import extract_features  # noqa: E402
from pose_llm_classifier.visualization import EDGES, plot_pose  # noqa: E402


def generate_samples(per_class=25, seed=42):
    """Vary body proportions, limbs, position and scale while preserving labels.

    Seated poses use a schematic oblique view: thighs run mostly horizontally,
    shins mostly vertically. Standing poses have nearly straight vertical legs.
    These are illustrative poses, not a physiological or camera simulation.
    """
    if per_class < 1:
        raise ValueError("per_class must be positive")
    rng = random.Random(seed)
    samples = []
    for label in range(4):
        for index in range(per_class):
            seated, hands_up = label < 2, label % 2 == 1
            raised = ("left", "right", "both")[index % 3] if hands_up else "none"
            shoulder_y = rng.uniform(0.27, 0.31)
            hip_y = rng.uniform(0.52, 0.57)
            shoulder_width = rng.uniform(0.15, 0.21)
            hip_width = rng.uniform(0.10, 0.15)
            lean = rng.uniform(-0.035, 0.035)
            points = {"nose": [0.5 + lean, shoulder_y - rng.uniform(0.10, 0.13)]}
            seat_direction = rng.choice((-1, 1))
            for side, sign in (("left", -1), ("right", 1)):
                sx = 0.5 + lean + sign * shoulder_width / 2
                sy = shoulder_y + rng.uniform(-0.008, 0.008)
                hx = 0.5 + sign * hip_width / 2
                points[f"{side}_shoulder"] = [sx, sy]
                points[f"{side}_hip"] = [hx, hip_y]
                up = raised in (side, "both")
                points[f"{side}_elbow"] = [
                    sx + sign * rng.uniform(0.065, 0.11),
                    sy + rng.uniform(-0.10, -0.055) if up else sy + rng.uniform(0.095, 0.14),
                ]
                points[f"{side}_wrist"] = [
                    sx + sign * rng.uniform(0.085, 0.16),
                    sy - rng.uniform(0.16, 0.205) if up else sy + rng.uniform(0.19, 0.25),
                ]
                if seated:
                    kx = hx + seat_direction * rng.uniform(0.15, 0.21)
                    ky = hip_y + rng.uniform(0.015, 0.055)
                    ax = kx + rng.uniform(-0.035, 0.035)
                    ay = ky + rng.uniform(0.19, 0.24)
                else:
                    kx = hx + sign * rng.uniform(0.0, 0.025)
                    ky = hip_y + rng.uniform(0.15, 0.18)
                    ax = kx + sign * rng.uniform(0.0, 0.025)
                    ay = ky + rng.uniform(0.14, 0.17)
                points[f"{side}_knee"] = [kx, ky]
                points[f"{side}_ankle"] = [ax, ay]
            # Uniform scale preserves limb angles and hand-height relations.
            scale = rng.uniform(0.82, 1.0)
            dx, dy = rng.uniform(-0.055, 0.055), rng.uniform(-0.025, 0.025)
            points = {
                name: [
                    round(0.5 + (x - 0.5) * scale + dx, 5),
                    round(0.5 + (y - 0.5) * scale + dy, 5),
                ]
                for name, (x, y) in points.items()
            }
            sample = validate_sample(
                {
                    "id": f"synthetic-{label}-{index:03d}",
                    "synthetic": True,
                    "generator_seed": seed,
                    "coordinate_space": "normalized",
                    "label": label,
                    "raised_hand": raised,
                    "keypoints": points,
                }
            )
            features = extract_features(sample)
            assert (
                features["left_hand_above_shoulder"] or features["right_hand_above_shoulder"]
            ) == hands_up
            samples.append(sample)
    return samples


def plot_overview(samples, output, title, columns=5):
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    rows = (len(samples) + columns - 1) // columns
    fig = Figure(figsize=(columns * 2.3, rows * 2.7))
    FigureCanvasAgg(fig)
    axes = fig.subplots(rows, columns, squeeze=False)
    for ax, sample in zip(axes.flat, samples):
        points = sample["keypoints"]
        for a, b in EDGES:
            ax.plot(
                [points[a]["x"], points[b]["x"]],
                [points[a]["y"], points[b]["y"]],
                color="0.45",
                linewidth=1.4,
            )
        for name, point in points.items():
            color = (
                "tab:blue"
                if name.startswith("left_")
                else ("tab:orange" if name.startswith("right_") else "0.3")
            )
            ax.scatter(point["x"], point["y"], c=color, s=12, zorder=3)
        ax.set(xlim=(0, 1), ylim=(1, 0), aspect="equal", xticks=[], yticks=[])
        ax.set_title(f"{sample['id']} | {sample['raised_hand']}", fontsize=8)
    for ax in list(axes.flat)[len(samples) :]:
        ax.set_visible(False)
    fig.suptitle(title + "\nSynthetic poses | blue: left, orange: right | y down", fontsize=13)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(output, dpi=120)
    fig.clear()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--per-class", type=int, default=25)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=Path("data/sample/synthetic_100.jsonl"))
    parser.add_argument("--output-dir", type=Path, default=Path("results/synthetic_100"))
    args = parser.parse_args()
    if args.per_class < 1:
        parser.error("--per-class must be positive")
    samples = generate_samples(args.per_class, args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(json.dumps(s, ensure_ascii=False) + "\n" for s in samples), encoding="utf-8"
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for label, name in enumerate(LABELS):
        group = [sample for sample in samples if sample["label"] == label]
        folder = args.output_dir / f"{label}_{name}"
        for sample in group:
            plot_pose(sample, folder / f"{sample['id']}.png", title=sample["id"])
        plot_overview(group, args.output_dir / f"overview_{label}_{name}.png", name)
        print(f"{name}: {len(group)} individual PNGs + overview", flush=True)
    write_json(
        args.output_dir / "manifest.json",
        {
            "dataset": str(args.output),
            "seed": args.seed,
            "total": len(samples),
            "counts": {LABELS[k]: v for k, v in Counter(s["label"] for s in samples).items()},
            "note": "Synthetic illustrations only; not real pose data or a performance benchmark.",
        },
    )
    print(f"Dataset: {args.output}\nImages: {args.output_dir}")


if __name__ == "__main__":
    main()
