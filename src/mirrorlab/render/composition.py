"""Frame composition helpers: transitions, letterboxing and comparison views."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Sequence, Tuple

import cv2
import numpy as np

__all__ = ["Transition", "blend", "crossfade", "letterbox", "stack_side_by_side", "tile_grid"]


def blend(a: np.ndarray, b: np.ndarray, alpha: float) -> np.ndarray:
    """Linear blend between two frames of the same shape (``alpha=0`` → ``a``)."""
    if a.shape != b.shape:
        b = cv2.resize(b, (a.shape[1], a.shape[0]))
    return cv2.addWeighted(a, 1.0 - float(alpha), b, float(alpha), 0)


def crossfade(frames: Sequence[np.ndarray], progress: float) -> np.ndarray:
    """Blend a sequence of frames by a 0..1 ``progress`` across the whole list."""
    if not frames:
        raise ValueError("crossfade needs at least one frame")
    if len(frames) == 1:
        return frames[0]
    scaled = max(0.0, min(1.0, float(progress))) * (len(frames) - 1)
    index = min(int(scaled), len(frames) - 2)
    return blend(frames[index], frames[index + 1], scaled - index)


def letterbox(
    frame: np.ndarray, width: int, height: int, colour: Tuple[int, int, int] = (18, 18, 20)
) -> np.ndarray:
    """Fit a frame into ``width``×``height`` preserving aspect ratio."""
    source_h, source_w = frame.shape[:2]
    if source_w == width and source_h == height:
        return frame
    scale = min(width / source_w, height / source_h)
    new_w, new_h = max(1, int(source_w * scale)), max(1, int(source_h * scale))
    resized = cv2.resize(
        frame, (new_w, new_h), interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR
    )
    canvas = np.full((height, width, 3), colour, dtype=np.uint8)
    x0 = (width - new_w) // 2
    y0 = (height - new_h) // 2
    canvas[y0 : y0 + new_h, x0 : x0 + new_w] = resized
    return canvas


def stack_side_by_side(left: np.ndarray, right: np.ndarray, gap: int = 8, label: bool = True) -> np.ndarray:
    """Before/after comparison strip — the screenshot that sells the project."""
    height = max(left.shape[0], right.shape[0])
    left = letterbox(left, int(left.shape[1] * height / left.shape[0]), height)
    right = letterbox(right, int(right.shape[1] * height / right.shape[0]), height)
    divider = np.full((height, gap, 3), 24, dtype=np.uint8)
    canvas = np.hstack([left, divider, right])
    if label:
        font = cv2.FONT_HERSHEY_DUPLEX
        scale = max(0.5, height / 900.0)
        cv2.putText(canvas, "ORIGINAL", (16, int(34 * scale)), font, scale, (235, 235, 235), 1, cv2.LINE_AA)
        x = left.shape[1] + gap + 16
        cv2.putText(canvas, "MIRRORLAB", (x, int(34 * scale)), font, scale, (200, 250, 200), 1, cv2.LINE_AA)
    return canvas


def tile_grid(
    frames: Sequence[np.ndarray], columns: int = 4, cell: Tuple[int, int] = (320, 180), pad: int = 6
) -> np.ndarray:
    """Lay frames out in a grid — used by ``mirrorlab gallery`` and the website."""
    if not frames:
        raise ValueError("tile_grid needs at least one frame")
    columns = max(1, int(columns))
    cell_w, cell_h = cell
    rows = (len(frames) + columns - 1) // columns
    width = columns * cell_w + pad * (columns + 1)
    height = rows * cell_h + pad * (rows + 1)
    canvas = np.full((height, width, 3), 18, dtype=np.uint8)
    for index, frame in enumerate(frames):
        row, column = divmod(index, columns)
        x = pad + column * (cell_w + pad)
        y = pad + row * (cell_h + pad)
        canvas[y : y + cell_h, x : x + cell_w] = letterbox(frame, cell_w, cell_h)
    return canvas


@dataclass
class Transition:
    """A timed cross-fade between the previous and current render.

    Used when switching filters so the change reads as a deliberate cut rather
    than a glitch. The state machine is explicit (``idle`` → ``running`` →
    ``idle``) which keeps it trivially testable.
    """

    duration: float = 0.18
    elapsed: float = 0.0
    active: bool = False
    _previous: Optional[np.ndarray] = field(default=None, repr=False)

    def trigger(self, previous: Optional[np.ndarray]) -> None:
        if previous is None:
            return
        self._previous = previous
        self.elapsed = 0.0
        self.active = True

    def update(self, current: np.ndarray, delta: float) -> np.ndarray:
        """Advance the transition and return the frame to display."""
        if not self.active or self._previous is None:
            return current
        if self._previous.shape != current.shape:
            self._previous = cv2.resize(self._previous, (current.shape[1], current.shape[0]))
        self.elapsed += max(0.0, float(delta))
        progress = self.elapsed / self.duration if self.duration > 0 else 1.0
        if progress >= 1.0:
            self.active = False
            self._previous = None
            return current
        # Ease-out so the cut lands softly instead of snapping.
        eased = 1.0 - (1.0 - progress) ** 2
        return blend(self._previous, current, eased)

    def reset(self) -> None:
        self.active = False
        self.elapsed = 0.0
        self._previous = None
