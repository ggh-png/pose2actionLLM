"""Label-free skeleton rendering and image+JSON transport for vision models."""

import base64
from pathlib import Path

from .inference import Classifier, build_messages
from .preprocessing import preprocess
from .visualization import EDGES

VISION_SYSTEM_PROMPT = """Look at the SHAPE of ONE skeleton and classify it. Return exactly one digit: 0, 1, 2, or 3. No explanation or additional text.

This is a skeleton diagram, not a photograph. Only the colored joint dots and gray bone segments form the body. Ignore the plot border, grid, axis lines, legend, and text when judging the body shape. Blue means anatomical left; orange means anatomical right. Joint names help identify which dots connect.

The body graph contains only shoulders, elbows, hips, and knees. Each shoulder connects to its elbow and hip; each hip connects to its knee. There are no wrists or ankles. Do not invent extra limbs, hands, feet, or a chair.

FIRST: judge the lower-body SHAPE, temporarily ignoring the arm branches.
Follow shoulder -> hip -> knee on both sides.
- SITTING: the body makes a bent, corner-like shape at the hips. The torso goes toward the hips, then the thigh segments turn SIDEWAYS toward the knees, like a bent L or its mirror image. Knees are often near hip height. This sideways thigh/hip corner is the key cue; no chair is needed.
- STANDING: the body makes a long, extended, approximately straight shape. Torso and thigh segments continue in roughly the same direction, like an elongated I. Knees extend mostly DOWN from the hips rather than out to the side.
Use the direction of the drawn hip-to-knee segments. Do not mistake elbow branches for thighs. Do not infer sitting/standing from arm position, frame location, or skeleton size.

SECOND: judge the arm-branch SHAPE, temporarily ignoring the thigh branches.
Follow each shoulder -> elbow segment.
- HAND_UP: at least one arm branch points upward or roughly sideways from its shoulder. Its elbow is above or approximately level with its shoulder. One raised arm is enough.
- HAND_DOWN: the available arm branches point downward from their shoulders, with elbows clearly lower.
Actual hands are not shown; HAND_UP/HAND_DOWN are elbow-based labels.

When an image is provided, use the visible skeleton shape as the primary evidence. Optional JSON is only a backup for joint identity or an unclear connection; do not turn the task into decimal-coordinate arithmetic. If only JSON is provided, mentally connect the named joints and apply the same straight-versus-bent and arm-direction rules. Ignore the features object. Null is missing, never zero; use the available side.

Map the two independent shape decisions:
SITTING + HAND_DOWN -> 0
SITTING + HAND_UP -> 1
STANDING + HAND_DOWN -> 2
STANDING + HAND_UP -> 3

Output only the matching digit."""


def render_model_input(sample, output, min_confidence=0):
    """Render only normalized geometry; sample metadata never reaches any artist."""
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    points = preprocess(sample, min_confidence)["keypoints"]
    fig = Figure(figsize=(6, 6), dpi=100)
    FigureCanvasAgg(fig)
    ax = fig.add_axes((0.12, 0.12, 0.80, 0.80))
    visible = {name: p for name, p in points.items() if p is not None}
    for start, end in EDGES:
        if start in visible and end in visible:
            a, b = visible[start], visible[end]
            ax.plot([a["x"], b["x"]], [a["y"], b["y"]], color="0.45", linewidth=2.5)
    for name, point in visible.items():
        left = name.startswith("left_")
        ax.scatter(
            point["x"], point["y"], color="tab:blue" if left else "tab:orange", s=32, zorder=3
        )
        ax.annotate(
            name.replace("left_", "L ").replace("right_", "R "),
            (point["x"], point["y"]),
            xytext=(-7 if left else 7, 4),
            textcoords="offset points",
            ha="right" if left else "left",
            fontsize=7,
        )
    ax.set(xlim=(0, 1), ylim=(1, 0), aspect="equal", xlabel="x: right", ylabel="y: down")
    ax.grid(alpha=0.2)
    fig.text(0.12, 0.035, "Blue: anatomical left | Orange: anatomical right", fontsize=8)
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=100)
    fig.clear()
    return path


class VisionClassifier(Classifier):
    """Vision requests with optional JSON and one actual PNG image."""

    def __init__(
        self,
        *args,
        image_paths=None,
        include_json=True,
        system_prompt=None,
        instruction_role="system",
        image_first=False,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        if instruction_role not in ("system", "user"):
            raise ValueError("instruction_role must be system or user")
        self.instruction_role = instruction_role
        self.image_first = image_first
        self.image_paths = image_paths
        self.include_json = include_json
        self.system_prompt = VISION_SYSTEM_PROMPT if system_prompt is None else system_prompt
        if image_paths is None and not include_json:
            raise ValueError("At least one input modality is required")

    def build_messages(self, sample, examples=(), min_confidence=0):
        if examples:
            raise ValueError("Vision benchmark currently supports zero-shot only")
        messages = build_messages(sample, min_confidence=min_confidence)
        messages[0]["content"] = self.system_prompt
        if self.image_paths is not None:
            image_path = Path(self.image_paths[sample["id"]])
            image_bytes = image_path.read_bytes()
            if not image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
                raise ValueError("Expected a PNG image")
            encoded = base64.b64encode(image_bytes).decode("ascii")
            messages[-1]["content"] = [
                {
                    "type": "text",
                    "text": messages[-1]["content"]
                    if self.include_json
                    else "Classify this single skeleton image. Return one class digit.",
                },
                {"type": "image_url", "image_url": {"url": "data:image/png;base64," + encoded}},
            ]
        if self.instruction_role == "user":
            prefix = messages[0]["content"] + "\n\n"
            if isinstance(messages[-1]["content"], list):
                messages[-1]["content"][0]["text"] = prefix + messages[-1]["content"][0]["text"]
            else:
                messages[-1]["content"] = prefix + messages[-1]["content"]
            messages = [messages[-1]]
        if self.image_first and isinstance(messages[-1]["content"], list):
            messages[-1]["content"] = list(reversed(messages[-1]["content"]))
        return messages


def render_shape_input(sample, output, min_confidence=0):
    """Draw a zoomed skeleton without text, axes, grid, or class metadata."""
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    points = preprocess(sample, min_confidence)["keypoints"]
    visible = {name: p for name, p in points.items() if p is not None}
    xs = [p["x"] for p in visible.values()]
    ys = [p["y"] for p in visible.values()]
    span = max(max(xs) - min(xs), max(ys) - min(ys), 0.01) * 1.30
    center_x = (max(xs) + min(xs)) / 2
    center_y = (max(ys) + min(ys)) / 2
    fig = Figure(figsize=(6, 6), dpi=100)
    FigureCanvasAgg(fig)
    ax = fig.add_axes((0, 0, 1, 1))
    for start, end in EDGES:
        if start in visible and end in visible:
            a, b = visible[start], visible[end]
            ax.plot([a["x"], b["x"]], [a["y"], b["y"]], color="0.35", linewidth=5)
    for name, point in visible.items():
        ax.scatter(
            point["x"],
            point["y"],
            color="tab:blue" if name.startswith("left_") else "tab:orange",
            s=80,
            zorder=3,
        )
    ax.set(
        xlim=(center_x - span / 2, center_x + span / 2),
        ylim=(center_y + span / 2, center_y - span / 2),
        aspect="equal",
    )
    ax.set_axis_off()
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=100)
    fig.clear()
    return path
