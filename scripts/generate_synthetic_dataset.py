"""Generate balanced synthetic poses and render individual/class overview PNGs."""

import argparse
import json
import math
import random
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pose_llm_classifier.data import LABELS, validate_sample, write_json  # noqa: E402
from pose_llm_classifier.features import extract_features  # noqa: E402
from pose_llm_classifier.visualization import EDGES, plot_pose  # noqa: E402

GENERATOR_VERSION = 4
DATASET_VIEW = "side_unmirrored"


def generate_samples(per_class=25, seed=42):
    """Vary body proportions, limbs, position and scale while preserving labels.

    Orthographically project a 3D joint schematic from a near-profile camera
    (85-88 degrees from frontal). Shoulder/hip pairs nearly overlap in image
    space; seated thighs extend forward and standing thighs point down.
    Both image-facing directions are included, with anatomical labels retained.
    """
    if per_class < 1:
        raise ValueError("per_class must be positive")
    rng = random.Random(seed)
    samples = []
    for label in range(4):
        for index in range(per_class):
            seated, hands_up = label < 2, label % 2 == 1
            raised = ("left", "right", "both")[index % 3] if hands_up else "none"
            facing_sign = (-1, 1)[(label * per_class + index) % 2]
            yaw_degrees = facing_sign * rng.uniform(85.0, 88.0)
            yaw = math.radians(yaw_degrees)
            shoulder_y = rng.uniform(0.27, 0.31)
            hip_y = rng.uniform(0.52, 0.57)
            shoulder_width = rng.uniform(0.15, 0.21)
            hip_width = rng.uniform(0.10, 0.15)
            lean_forward = rng.uniform(-0.025, 0.025)
            thigh_length = rng.uniform(0.18, 0.23)
            world_points = {}
            for side, sign in (("left", 1), ("right", -1)):
                # World axes: anatomical lateral, body forward, image-down.
                lateral_shoulder = sign * shoulder_width / 2
                lateral_hip = sign * hip_width / 2
                sy = shoulder_y + rng.uniform(-0.003, 0.003)
                hy = hip_y + rng.uniform(-0.003, 0.003)
                world_points[f"{side}_shoulder"] = [lateral_shoulder, lean_forward, sy]
                world_points[f"{side}_hip"] = [lateral_hip, 0.0, hy]
                up = raised in (side, "both")
                world_points[f"{side}_elbow"] = [
                    lateral_shoulder + sign * rng.uniform(0.015, 0.035),
                    lean_forward + rng.uniform(0.025, 0.065),
                    sy + rng.uniform(-0.16, -0.12) if up else sy + rng.uniform(0.12, 0.16),
                ]
                if seated:
                    knee_forward = thigh_length + rng.uniform(-0.008, 0.008)
                    ky = hip_y + rng.uniform(0.01, 0.03)
                else:
                    knee_forward = rng.uniform(-0.012, 0.012)
                    ky = hip_y + thigh_length + rng.uniform(-0.008, 0.008)
                world_points[f"{side}_knee"] = [
                    lateral_hip, knee_forward, ky,
                ]
            points = {
                name: [0.5 + math.cos(yaw) * lateral + math.sin(yaw) * forward, down]
                for name, (lateral, forward, down) in world_points.items()
            }
            # Uniform scale preserves limb angles and elbow-height relations.
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
                    "generator_version": GENERATOR_VERSION,
                    "view": DATASET_VIEW,
                    "facing_direction": "image_left" if facing_sign < 0 else "image_right",
                    "camera_yaw_degrees": round(yaw_degrees, 4),
                    "coordinate_space": "normalized",
                    "label": label,
                    "raised_arm": raised,
                    "keypoints": points,
                }
            )
            features = extract_features(sample)
            assert (
                features["left_elbow_above_shoulder"] or features["right_elbow_above_shoulder"]
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
        ax.set_title(f"{sample['id']} | {sample['raised_arm']}", fontsize=8)
    for ax in list(axes.flat)[len(samples) :]:
        ax.set_visible(False)
    fig.suptitle(
        title + "\nSide view (3D schematic projection) | blue: anatomical left, orange: right | y down",
        fontsize=13,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(output, dpi=120)
    fig.clear()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--per-class", type=int, default=25)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=Path("data/sample/synthetic_100.jsonl"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/sample/synthetic_100"))
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
            write_json(folder / f"{sample['id']}.json", sample)
            plot_pose(sample, folder / f"{sample['id']}.png", title=sample["id"])
        plot_overview(group, args.output_dir / f"overview_{label}_{name}.png", name)
        print(f"{name}: {len(group)} individual PNGs + overview", flush=True)
    write_json(
        args.output_dir / "manifest.json",
        {
            "dataset": str(args.output),
            "seed": args.seed,
            "generator_version": GENERATOR_VERSION,
            "view": DATASET_VIEW,
            "total": len(samples),
            "counts": {LABELS[k]: v for k, v in Counter(s["label"] for s in samples).items()},
            "samples": [
                {
                    "id": sample["id"],
                    "label": sample["label"],
                    "json": f"{sample['label']}_{LABELS[sample['label']]}/{sample['id']}.json",
                    "image": f"{sample['label']}_{LABELS[sample['label']]}/{sample['id']}.png",
                }
                for sample in samples
            ],
            "projection": "orthographic",
            "camera_yaw_absolute_range_degrees": [85, 88],
            "facing_counts": dict(Counter(s["facing_direction"] for s in samples)),
            "note": "All poses use a side-view projection of 3D joint schematics. Near/far joints remain in the synthetic input despite potential real-camera occlusion. Not measured poses or a performance benchmark.",
        },
    )
    print(f"Dataset: {args.output}\nImages: {args.output_dir}")


if __name__ == "__main__":
    main()
