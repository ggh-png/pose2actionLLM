"""Headless skeleton plots with anatomical side colors and explicit missing points."""

from pathlib import Path

from .data import KEYPOINTS, LABELS, validate_sample
from .features import extract_features
from .preprocessing import preprocess

EDGES = [("left_shoulder", "right_shoulder"), ("left_hip", "right_hip")]
for _side in ("left", "right"):
    EDGES.extend(
        (f"{_side}_{a}", f"{_side}_{b}")
        for a, b in (
            ("shoulder", "elbow"),
            ("shoulder", "hip"),
            ("hip", "knee"),
        )
    )


def plot_pose(sample, output, show_features=False, title=None):
    # Lazy import keeps loader/prompt/evaluation usable without plotting dependencies.
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    sample = validate_sample(sample)
    points = sample["keypoints"]
    fig = Figure(figsize=(10, 10))
    FigureCanvasAgg(fig)
    ax = fig.add_axes((0.10, 0.25, 0.80, 0.62))
    visible = {name: p for name, p in points.items() if p and p.get("presence", 1) > 0}
    for a, b in EDGES:
        if a in visible and b in visible:
            ax.plot(
                [visible[a]["x"], visible[b]["x"]],
                [visible[a]["y"], visible[b]["y"]],
                color="0.5",
                linewidth=2,
            )
    for name, point in visible.items():
        color = (
            "tab:blue"
            if name.startswith("left_")
            else "tab:orange"
            if name.startswith("right_")
            else "0.3"
        )
        ax.scatter(point["x"], point["y"], c=color, s=35, zorder=3)
        label = name.replace("left_", "L ").replace("right_", "R ")
        label += f"\n({point['x']:.3f}, {point['y']:.3f})"
        quality = [f"{k}={point[k]:.2f}" for k in ("confidence", "presence") if k in point]
        if quality:
            label += "\n" + ", ".join(quality)
        is_left = name.startswith("left_")
        ax.annotate(
            label,
            (point["x"], point["y"]),
            xytext=(-7 if is_left else 7, 3),
            textcoords="offset points",
            fontsize=7,
            ha="right" if is_left else "left",
        )
    normalized = sample["coordinate_space"] == "normalized"
    ax.set_xlim(0, 1 if normalized else sample["image_width"])
    ax.set_ylim(1 if normalized else sample["image_height"], 0)
    ax.set_aspect("equal")
    ax.set_xlabel("x → right")
    ax.set_ylabel("y → down")
    ax.grid(alpha=0.2)
    lines = [title or f"Pose ({sample['coordinate_space']})"]
    for field, caption in (("label", "Ground Truth"), ("prediction", "Prediction")):
        if sample.get(field) is not None:
            lines.append(f"{caption}: {sample[field]} / {LABELS[sample[field]]}")
    if sample.get("label") is not None and sample.get("prediction") is not None:
        lines.append(
            "Result: " + ("Correct" if sample["label"] == sample["prediction"] else "Incorrect")
        )
    fig.suptitle("\n".join(lines), fontsize=12)
    missing = [name for name in KEYPOINTS if name not in visible]
    import textwrap

    notes = [
        "Blue: anatomical left | Orange: anatomical right | origin: top-left",
        textwrap.fill("Missing/absent: " + (", ".join(missing) or "none"), 100),
    ]
    if show_features:
        notes.extend(
            f"{key} = {value:.4f}" if isinstance(value, float) else f"{key} = {value}"
            for key, value in extract_features(sample).items()
        )
    fig.text(0.05, 0.02, "\n".join(notes), fontsize=8, va="bottom")
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=120)
    fig.clear()
    return output


def plot_comparison(sample, output_dir, show_features=False, min_confidence=0):
    directory = Path(output_dir)
    return (
        plot_pose(sample, directory / "raw_pose.png", show_features, "Raw Coordinate"),
        plot_pose(
            preprocess(sample, min_confidence),
            directory / "preprocessed_pose.png",
            show_features,
            "Preprocessed Coordinate",
        ),
    )
