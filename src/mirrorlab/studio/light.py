"""Studio light: automatic exposure that follows your face, not the room.

Webcam auto-exposure meters the whole frame. A bright window behind you makes
the camera expose for the window and leaves your face dark. This module meters
only the face region instead, and corrects with a gamma curve (one 256-entry
lookup table, so it costs almost nothing).

Two details keep it from being annoying in a call:

* the correction is **smoothed over time** (about a second), otherwise the image
  pumps every time you move your head;
* the correction is **bounded**, so a covered lens or a very dark room never
  produces a blown-out frame full of noise.
"""

from __future__ import annotations

import math
from typing import Optional, Tuple

import cv2
import numpy as np

__all__ = ["StudioLight", "gamma_lut"]

Box = Tuple[float, float, float, float]


def gamma_lut(gamma: float) -> np.ndarray:
    """256-entry LUT for ``out = 255 * (in / 255) ** gamma``."""
    table = (np.linspace(0.0, 1.0, 256, dtype=np.float32) ** gamma) * 255.0
    return np.clip(table, 0, 255).astype(np.uint8)


class StudioLight:
    """Face-metered exposure correction.

    Args:
        strength: 0 disables the effect, 1 corrects fully toward the target.
        target: Desired mean face luma in ``[0, 1]``.
        tau: Smoothing time constant in seconds.
        limits: Allowed gamma range. Below 1 brightens, above 1 darkens.
    """

    def __init__(
        self,
        strength: float = 0.6,
        target: float = 0.50,
        tau: float = 1.0,
        limits: Tuple[float, float] = (0.55, 1.25),
    ) -> None:
        self.strength = float(min(max(strength, 0.0), 1.0))
        self.target = float(target)
        self.tau = max(1e-3, float(tau))
        self.limits = limits
        self.gamma = 1.0
        self._last_time: Optional[float] = None

    def reset(self) -> None:
        self.gamma = 1.0
        self._last_time = None

    # ------------------------------------------------------------------ #
    @staticmethod
    def face_luma(frame: np.ndarray, box: Box) -> float:
        """Mean luma of the central part of ``box`` (skips hair and background)."""
        height, width = frame.shape[:2]
        x0, y0, x1, y1 = box
        # Shrink to the middle 60% so hair, collar and background do not skew the reading.
        cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
        half_w, half_h = (x1 - x0) * 0.30, (y1 - y0) * 0.30
        left = int(max(0.0, (cx - half_w)) * width)
        right = int(min(1.0, (cx + half_w)) * width)
        top = int(max(0.0, (cy - half_h)) * height)
        bottom = int(min(1.0, (cy + half_h)) * height)
        if right - left < 4 or bottom - top < 4:
            return -1.0
        patch = frame[top:bottom:2, left:right:2]
        luma = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)
        return float(luma.mean()) / 255.0

    def update(self, frame: np.ndarray, box: Optional[Box], now: float) -> float:
        """Update the smoothed gamma from this frame's face reading and return it."""
        dt = 0.0 if self._last_time is None else max(0.0, min(now - self._last_time, 0.5))
        self._last_time = now
        if box is None:
            return self.gamma
        luma = self.face_luma(frame, box)
        if luma <= 0.02:
            return self.gamma  # a covered lens carries no exposure information
        luma = min(luma, 0.98)
        wanted = math.log(self.target) / math.log(luma)
        wanted = min(max(wanted, self.limits[0]), self.limits[1])
        wanted = 1.0 + (wanted - 1.0) * self.strength
        alpha = 1.0 - math.exp(-dt / self.tau) if dt > 0 else 1.0
        self.gamma += (wanted - self.gamma) * alpha
        return self.gamma

    def apply(self, frame: np.ndarray, box: Optional[Box], now: float) -> np.ndarray:
        gamma = self.update(frame, box, now)
        if abs(gamma - 1.0) < 0.01:
            return frame
        return cv2.LUT(frame, gamma_lut(gamma))
