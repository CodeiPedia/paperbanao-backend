import base64
import io
import re
import logging

import matplotlib
matplotlib.use("Agg")  # headless rendering, no display needed on the server
import matplotlib.pyplot as plt

logger = logging.getLogger("paperbanao")


def _fig_to_base64(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


def draw_right_triangle(params):
    """A right-angled triangle with the right angle at the bottom-left,
    given exact base/height so proportions are always mathematically
    accurate (never hand-wavy or AI-hallucinated)."""
    base = float(params.get("base", 4))
    height = float(params.get("height", 3))
    labels = [s.strip() for s in params.get("labels", "A,B,C").split(",")]
    base_label = params.get("base_label", "")
    height_label = params.get("height_label", "")
    hyp_label = params.get("hyp_label", "")

    fig, ax = plt.subplots(figsize=(4, 3.5))
    A, B, C = (0, 0), (base, 0), (0, height)
    triangle = plt.Polygon([A, B, C], fill=False, edgecolor="black", linewidth=1.8)
    ax.add_patch(triangle)

    marker_size = min(base, height) * 0.12
    ax.plot([0, marker_size, marker_size, 0], [marker_size, marker_size, 0, marker_size], "k-", linewidth=1)

    if len(labels) >= 3:
        ax.text(A[0] - 0.15 * base, A[1] - 0.1 * height, labels[0], fontsize=13, fontweight="bold")
        ax.text(B[0] + 0.05 * base, B[1] - 0.1 * height, labels[1], fontsize=13, fontweight="bold")
        ax.text(C[0] - 0.15 * base, C[1] + 0.05 * height, labels[2], fontsize=13, fontweight="bold")
    if base_label:
        ax.text(base / 2, -0.12 * height, base_label, fontsize=11, ha="center")
    if height_label:
        ax.text(-0.16 * base, height / 2, height_label, fontsize=11, va="center", rotation=90)
    if hyp_label:
        ax.text(base / 2 + 0.08 * base, height / 2 + 0.05 * height, hyp_label, fontsize=11)

    ax.set_xlim(-0.35 * base, 1.25 * base)
    ax.set_ylim(-0.3 * height, 1.25 * height)
    ax.set_aspect("equal")
    ax.axis("off")
    return _fig_to_base64(fig)


def draw_circle(params):
    radius_label = params.get("radius_label", "")
    center_label = params.get("center_label", "O")
    point_label = params.get("point_label", "P")

    fig, ax = plt.subplots(figsize=(3.5, 3.5))
    circle = plt.Circle((0, 0), 1, fill=False, edgecolor="black", linewidth=1.8)
    ax.add_patch(circle)
    ax.plot(0, 0, "ko", markersize=4)
    ax.text(-0.12, -0.12, center_label, fontsize=12, fontweight="bold")
    ax.plot([0, 1], [0, 0], "k-", linewidth=1.5)
    if radius_label:
        ax.text(0.4, 0.08, radius_label, fontsize=11)
    ax.plot(1, 0, "ko", markersize=4)
    ax.text(1.05, -0.05, point_label, fontsize=12, fontweight="bold")

    ax.set_xlim(-1.4, 1.4)
    ax.set_ylim(-1.4, 1.4)
    ax.set_aspect("equal")
    ax.axis("off")
    return _fig_to_base64(fig)


def draw_bargraph(params):
    categories = [c.strip() for c in params.get("categories", "A,B,C").split(",")]
    values = [float(v.strip()) for v in params.get("values", "1,2,3").split(",")]
    x_label = params.get("x_label", "")
    y_label = params.get("y_label", "")

    fig, ax = plt.subplots(figsize=(4.5, 3.2))
    ax.bar(categories, values, color="white", edgecolor="black", linewidth=1.5)
    if x_label:
        ax.set_xlabel(x_label, fontsize=10)
    if y_label:
        ax.set_ylabel(y_label, fontsize=10)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    return _fig_to_base64(fig)


DIAGRAM_TYPES = {
    "triangle": draw_right_triangle,
    "circle": draw_circle,
    "bargraph": draw_bargraph,
}

# Matches: [DIAGRAM:triangle|base=4|height=3|base_label=4 cm]
DIAGRAM_TAG_RE = re.compile(r"\[DIAGRAM:\s*(\w+)\s*\|([^\]]*)\]")


def _parse_params(param_str):
    params = {}
    for part in param_str.split("|"):
        if "=" in part:
            key, _, value = part.partition("=")
            params[key.strip()] = value.strip()
    return params


def process_diagrams(text: str):
    """Finds every [DIAGRAM:type|params] tag the AI included in its
    response, renders each as an accurate PNG, and replaces the tag with a
    short {{DIAGRAM:id}} marker in the text. Returns (new_text, diagrams)
    where diagrams maps marker id -> base64 PNG data, so the actual image
    bytes never bloat the question/answer text itself.

    If a tag is malformed or rendering fails for any reason, that one tag
    is just dropped (silently, replaced with nothing) rather than
    breaking generation of the entire paper over one bad diagram.
    """
    diagrams = {}
    counter = [0]

    def replace_match(m):
        diagram_type = m.group(1).lower()
        params = _parse_params(m.group(2))
        draw_fn = DIAGRAM_TYPES.get(diagram_type)
        if not draw_fn:
            logger.warning(f"[Diagram] Unknown diagram type requested: {diagram_type}")
            return ""
        try:
            counter[0] += 1
            marker_id = f"diagram_{counter[0]}"
            diagrams[marker_id] = draw_fn(params)
            return f"{{{{DIAGRAM:{marker_id}}}}}"
        except Exception as e:
            logger.error(f"[Diagram Generation Error] type={diagram_type} params={params} error={e}")
            return ""

    new_text = DIAGRAM_TAG_RE.sub(replace_match, text)
    return new_text, diagrams
