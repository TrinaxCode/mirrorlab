"""Air drawing: paint on the video with your index finger.

Interaction model — deliberately identical to a graphics tablet:

* **index finger extended, others folded** → pen down, stroke follows the tip;
* **pinch (thumb + index touching)** → eraser;
* **open palm held briefly** → clear the canvas;
* **fist** → lift the pen without ending the stroke.

Strokes live on a persistent RGBA-style canvas so they survive across frames,
and each stroke is a spline through the recorded tip positions, drawn with round
caps. Raw landmarks jitter, so the pen position is smoothed separately with a
One-Euro filter at a faster cutoff than the rest of the pipeline.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import TYPE_CHECKING, Deque, List, Optional, Tuple

import cv2
import numpy as np

from .gestures import INDEX_TIP, THUMB_TIP, HandPose
from .utils.logging import get_logger
from .utils.smoothing import OneEuroFilter

if TYPE_CHECKING:  # pragma: no cover - avoids a circular import at runtime
    from .detectors.base import HandObservation

__all__ = ["AirCanvas", "Brush"]

log = get_logger("airdraw")

BGR = Tuple[int, int, int]


@dataclass
class Brush:
    """Pen configuration."""

    colour: BGR = (90, 230, 250)
    thickness: int = 6
    glow: bool = True

    PALETTE: Tuple[BGR, ...] = (
        (90, 230, 250),  # amber
        (120, 250, 160),  # mint
        (250, 180, 90),  # sky
        (200, 120, 250),  # violet
        (120, 120, 255),  # coral
        (255, 255, 255),  # white
    )

    def next_colour(self) -> BGR:
        palette = list(self.PALETTE)
        try:
            index = palette.index(self.colour)
        except ValueError:
            index = -1
        self.colour = palette[(index + 1) % len(palette)]
        return self.colour

    def thicker(self, step: int = 2, maximum: int = 40) -> int:
        self.thickness = min(maximum, self.thickness + step)
        return self.thickness

    def thinner(self, step: int = 2, minimum: int = 1) -> int:
        self.thickness = max(minimum, self.thickness - step)
        return self.thickness


class AirCanvas:
    """Persistent drawing layer driven by hand landmarks.

    Args:
        width, height: Canvas size in pixels.
        smoothing: One-Euro cutoff for the pen; higher = more responsive.
        max_points: Points retained per stroke before it is committed.

    Example:
        >>> canvas = AirCanvas(1280, 720)                    # doctest: +SKIP
        >>> canvas.update(hand, pose, time.time())           # doctest: +SKIP
        >>> frame = canvas.composite(frame)                  # doctest: +SKIP
    """

    def __init__(
        self,
        width: int,
        height: int,
        smoothing: float = 3.2,
        max_points: int = 1024,
    ) -> None:
        self.width = int(width)
        self.height = int(height)
        self.brush = Brush()
        self.layer = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        self.mask = np.zeros((self.height, self.width), dtype=np.uint8)
        self._stroke: Deque[Tuple[int, int]] = deque(maxlen=max_points)
        self._drawing = False
        self._filter_x = OneEuroFilter(min_cutoff=smoothing, beta=0.9)
        self._filter_y = OneEuroFilter(min_cutoff=smoothing, beta=0.9)
        self._last_point: Optional[Tuple[int, int]] = None
        self.strokes: int = 0

    # ------------------------------------------------------------------ #
    def resize(self, width: int, height: int) -> None:
        """Keep the canvas valid when the capture resolution changes."""
        if (width, height) == (self.width, self.height):
            return
        self.layer = cv2.resize(self.layer, (width, height), interpolation=cv2.INTER_LINEAR)
        self.mask = cv2.resize(self.mask, (width, height), interpolation=cv2.INTER_LINEAR)
        self.width, self.height = int(width), int(height)

    def clear(self) -> None:
        self.layer[:] = 0
        self.mask[:] = 0
        self._stroke.clear()
        self._last_point = None
        self.strokes = 0

    # ------------------------------------------------------------------ #
    def update(
        self,
        hand: Optional["HandObservation"],
        pose: Optional[HandPose],
        timestamp: Optional[float] = None,
    ) -> bool:
        """Advance the pen state. Returns ``True`` when a stroke is active."""
        if hand is None or pose is None:
            self._end_stroke()
            return False

        if len(pose.landmarks) <= max(INDEX_TIP, THUMB_TIP):
            self._end_stroke()
            return False

        erasing = pose.pinch
        pointing = pose.is_extended("index") and pose.is_folded("middle") and pose.is_folded("ring")

        if not (pointing or erasing):
            self._end_stroke()
            return False

        raw = (
            pose.landmarks[INDEX_TIP, :2]
            if not erasing
            else ((pose.landmarks[INDEX_TIP, :2] + pose.landmarks[THUMB_TIP, :2]) / 2.0)
        )
        x = float(self._filter_x(raw[0] * self.width, timestamp))
        y = float(self._filter_y(raw[1] * self.height, timestamp))
        point = (
            int(np.clip(x, 0, self.width - 1)),
            int(np.clip(y, 0, self.height - 1)),
        )

        if not self._drawing:
            self._drawing = True
            self._stroke.clear()
            self.strokes += 1

        if erasing:
            self._erase(point)
        else:
            self._stroke.append(point)
            self._paint(point)
        self._last_point = point
        return True

    # ------------------------------------------------------------------ #
    def _paint(self, point: Tuple[int, int]) -> None:
        thickness = self.brush.thickness
        if self._last_point is not None and self._stroke_continuous():
            cv2.line(self.layer, self._last_point, point, self.brush.colour, thickness, cv2.LINE_AA)
            cv2.line(self.mask, self._last_point, point, 255, thickness, cv2.LINE_AA)
        cv2.circle(self.layer, point, max(1, thickness // 2), self.brush.colour, -1, cv2.LINE_AA)
        cv2.circle(self.mask, point, max(1, thickness // 2), 255, -1, cv2.LINE_AA)

    def _stroke_continuous(self) -> bool:
        return self._drawing and self._last_point is not None

    def _erase(self, point: Tuple[int, int]) -> None:
        radius = self.brush.thickness * 4
        cv2.circle(self.layer, point, radius, (0, 0, 0), -1, cv2.LINE_AA)
        cv2.circle(self.mask, point, radius, 0, -1, cv2.LINE_AA)
        self._last_point = point

    def _end_stroke(self) -> None:
        self._drawing = False
        self._stroke.clear()
        self._last_point = None

    # ------------------------------------------------------------------ #
    def composite(self, frame: np.ndarray, glow: bool = True) -> np.ndarray:
        """Blend the drawing layer over ``frame``."""
        if self.layer.shape[:2] != frame.shape[:2]:
            self.resize(frame.shape[1], frame.shape[0])
        if not self.mask.any():
            return frame
        alpha = (self.mask.astype(np.float32) / 255.0)[..., None]
        out = frame.astype(np.float32) * (1.0 - alpha) + self.layer.astype(np.float32) * alpha
        if glow and self.brush.glow:
            bloom = cv2.GaussianBlur(self.layer, (0, 0), 9.0) * alpha
            out = np.clip(out + bloom * 0.45, 0, 255)
        return out.astype(np.uint8)

    def cursor(self) -> Optional[Tuple[int, int]]:
        """Current pen position, for drawing a reticle on the HUD."""
        return self._last_point

    @property
    def active(self) -> bool:
        return self._drawing

    @property
    def point_count(self) -> int:
        return len(self._stroke)

    def stroke_points(self) -> List[Tuple[int, int]]:
        return list(self._stroke)
