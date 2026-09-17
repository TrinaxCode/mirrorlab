"""Filter framework: declarative, chainable, real-time video effects.

A *filter* is a pure-ish function ``frame -> frame`` that may keep private
state between frames (particle positions, previous frame, phase accumulators).
Filters declare their own metadata so the CLI, the HUD and the website can all
list them from a single registry.

Filters compose: ``--filter cartoon+vignette+glitch`` builds a
:class:`FilterChain` that runs each stage in order. Each stage receives the
previous stage's output, which makes complex looks a one-liner.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import cv2
import numpy as np

__all__ = [
    "CATEGORIES",
    "FILTERS",
    "Filter",
    "FilterChain",
    "FilterContext",
    "build_chain",
    "build_filter",
    "filter_catalog",
    "get_filter",
    "list_filters",
    "register_filter",
]


@dataclass
class FilterContext:
    """Per-frame information handed to filters.

    Attributes:
        frame_index: Monotonic frame counter.
        time: Seconds since the pipeline started (float, wall clock based).
        delta: Seconds since the previous frame (``1/fps`` in practice).
        width, height: Frame size in pixels.
        state: Mutable scratch dictionary shared between the frames of one
            filter instance — where filters keep their particle systems.
    """

    frame_index: int = 0
    time: float = 0.0
    delta: float = 1.0 / 30.0
    width: int = 0
    height: int = 0
    state: Dict[str, object] = field(default_factory=dict)

    @property
    def aspect(self) -> float:
        return self.width / self.height if self.height else 1.0


class Filter:
    """Base class for every video effect.

    Subclasses implement :meth:`apply`. Metadata drives the CLI listing and the
    HUD, so keep the labels short and the description concrete.
    """

    name: str = "filter"
    label: str = "Filter"
    label_es: str = "Filtro"
    emoji: str = "🎨"
    category: str = "basic"
    description: str = ""
    description_es: str = ""
    #: Rough cost hint: ``cheap``, ``medium`` or ``heavy``.
    cost: str = "cheap"
    #: ``True`` when the filter benefits from the person mask.
    needs_mask: bool = False

    def __init__(self) -> None:
        self.state: Dict[str, object] = {}

    # -- API --------------------------------------------------------------- #
    def apply(self, frame: np.ndarray, ctx: FilterContext) -> np.ndarray:
        """Return the filtered frame.

        Contract, relied upon by the render loop:

        * ``frame`` must **not** be mutated in place — callers still need the
          original for before/after views and for the next stage;
        * the returned array must not alias any buffer the filter keeps in
          :attr:`state`, because the HUD and the recorder hold on to it.
        """
        raise NotImplementedError

    def reset(self) -> None:
        self.state.clear()

    def __call__(self, frame: np.ndarray, ctx: FilterContext) -> np.ndarray:
        return self.apply(frame, ctx)

    # -- helpers ----------------------------------------------------------- #
    @staticmethod
    def _ensure_bgr(frame: np.ndarray) -> np.ndarray:
        if frame.ndim == 2:
            return cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        if frame.shape[2] == 4:
            return cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
        return frame

    def describe(self) -> str:
        return f"{self.emoji} {self.label} — {self.description}"

    def to_dict(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "label": self.label,
            "label_es": self.label_es,
            "emoji": self.emoji,
            "category": self.category,
            "description": self.description,
            "description_es": self.description_es,
            "cost": self.cost,
        }


#: Human readable category names, used for grouped CLI/website listings.
CATEGORIES: Dict[str, Dict[str, str]] = {
    "basic": {"label": "Basic", "label_es": "Básicos", "emoji": "🎛️"},
    "color": {"label": "Colour", "label_es": "Color", "emoji": "🌈"},
    "artistic": {"label": "Artistic", "label_es": "Artísticos", "emoji": "🖌️"},
    "stylize": {"label": "Stylised", "label_es": "Estilizados", "emoji": "✨"},
    "glitch": {"label": "Glitch & retro", "label_es": "Glitch y retro", "emoji": "📺"},
    "utility": {"label": "Utility", "label_es": "Utilidades", "emoji": "🛠️"},
}

FILTERS: Dict[str, Filter] = {}


def register_filter(filter_instance: Filter) -> Filter:
    """Add a filter instance to the global registry."""
    FILTERS[filter_instance.name] = filter_instance
    return filter_instance


def get_filter(name: str) -> Optional[Filter]:
    """Look up a filter by name, normalising ``Camel Case`` and dashes."""
    key = (name or "").strip().lower().replace("-", "_").replace(" ", "_")
    return FILTERS.get(key)


class FilterChain(Filter):
    """Runs several filters in sequence, sharing one :class:`FilterContext`."""

    name = "chain"
    label = "Chain"
    label_es = "Cadena"
    emoji = "⛓️"
    category = "utility"
    description = "Several filters applied in order."

    def __init__(self, filters: Sequence[Filter]) -> None:
        super().__init__()
        self.filters: List[Filter] = list(filters)

    def apply(self, frame: np.ndarray, ctx: FilterContext) -> np.ndarray:
        out = frame
        for stage in self.filters:
            out = stage.apply(out, ctx)
            if out is None:  # pragma: no cover - a buggy custom filter
                raise RuntimeError(f"Filter {stage.name!r} returned None")
        return out

    def reset(self) -> None:
        for stage in self.filters:
            stage.reset()

    @property
    def cost(self) -> str:  # type: ignore[override]
        order = {"cheap": 0, "medium": 1, "heavy": 2}
        worst = max((order.get(stage.cost, 0) for stage in self.filters), default=0)
        return {0: "cheap", 1: "medium", 2: "heavy"}[worst]

    def describe(self) -> str:
        return " + ".join(stage.label for stage in self.filters)


def build_filter(spec: str) -> Filter:
    """Build a filter (or chain) from a spec such as ``"cartoon+vignette"``.

    Raises:
        KeyError: when a name is unknown — the message lists close matches so
            ``mirrorlab run --filter caroon`` is a one-line fix.
    """
    if not spec:
        return get_filter("original") or _passthrough()
    names = [part.strip() for part in str(spec).replace(",", "+").split("+") if part.strip()]
    if not names:
        return get_filter("original") or _passthrough()

    stages: List[Filter] = []
    for name in names:
        found = get_filter(name)
        if found is None:
            suggestions = _suggest(name)
            hint = f" Did you mean: {', '.join(suggestions)}?" if suggestions else ""
            raise KeyError(f"Unknown filter {name!r}.{hint}\nRun `mirrorlab filters` to list them all.")
        # Instantiate per use so two chains never share mutable state.
        stages.append(type(found)())

    if len(stages) == 1:
        return stages[0]
    return FilterChain(stages)


def build_chain(specs: Iterable[str]) -> Filter:
    """Build one chain from several specs (each may itself be a chain)."""
    stages: List[Filter] = []
    for spec in specs:
        if not spec:
            continue
        built = build_filter(spec)
        if isinstance(built, FilterChain):
            stages.extend(built.filters)
        else:
            stages.append(built)
    if not stages:
        return get_filter("original") or _passthrough()
    return stages[0] if len(stages) == 1 else FilterChain(stages)


def _suggest(name: str, limit: int = 3) -> List[str]:
    """Cheap fuzzy match for friendly error messages."""
    import difflib

    return difflib.get_close_matches(name.lower(), list(FILTERS), n=limit, cutoff=0.5)


def _passthrough() -> Filter:
    class _Passthrough(Filter):
        name = "original"
        label = "Original"
        label_es = "Original"
        emoji = "🎥"
        category = "basic"
        description = "No effect — the raw camera feed."

        def apply(self, frame: np.ndarray, ctx: FilterContext) -> np.ndarray:
            return frame

    return _Passthrough()


def list_filters(category: Optional[str] = None) -> List[Filter]:
    """All registered filters, optionally filtered by category."""
    items = list(FILTERS.values())
    if category:
        items = [f for f in items if f.category == category]
    return sorted(items, key=lambda f: (f.category, f.name))


def filter_catalog() -> List[Dict[str, object]]:
    """Machine-readable filter catalog for the CLI and the website."""
    return [f.to_dict() for f in list_filters()]


def filter_names() -> List[str]:
    return sorted(FILTERS)


def apply_mask_blur(frame: np.ndarray, mask: Optional[np.ndarray], strength: int = 21) -> np.ndarray:
    """Blur everything *outside* ``mask`` — the classic video-call effect.

    Shared by the background-blur, background-replace and privacy filters.
    """
    if mask is None:
        return cv2.GaussianBlur(frame, (strength | 1, strength | 1), 0)
    blurred = cv2.GaussianBlur(frame, (strength | 1, strength | 1), 0)
    # Feather the mask so the cut-out edge does not shimmer.
    alpha = cv2.GaussianBlur(mask.astype(np.float32), (15, 15), 0)[..., None]
    return (frame * alpha + blurred * (1.0 - alpha)).astype(np.uint8)


def tint(frame: np.ndarray, color: Tuple[int, int, int], amount: float = 0.35) -> np.ndarray:
    """Blend a solid BGR colour over the frame."""
    overlay = np.full_like(frame, color, dtype=np.uint8)
    return cv2.addWeighted(frame, 1.0 - amount, overlay, amount, 0)


def to_gray_bgr(frame: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Return ``(gray, gray_as_bgr)`` — the starting point of most stylisations."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return gray, cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)


def sobel_magnitude(gray: np.ndarray) -> np.ndarray:
    """Edge strength in ``[0, 255]``, robust to noise."""
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    magnitude = cv2.magnitude(gx, gy)
    return cv2.convertScaleAbs(magnitude, alpha=1.0, beta=0.0)


class PhaseClock:
    """Deterministic time source so filters are reproducible in tests."""

    def __init__(self, fps: float = 30.0) -> None:
        self.fps = fps
        self._frame = 0

    def tick(self) -> float:
        self._frame += 1
        return self._frame / self.fps

    @property
    def time(self) -> float:
        return time.perf_counter()
