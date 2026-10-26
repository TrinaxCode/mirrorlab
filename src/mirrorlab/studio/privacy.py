"""Privacy shutter: cover the camera on demand, or when you walk away.

The shutter is the one feature in this project where failing silently is not
acceptable, so its contract is strict:

* When the shutter is closed, **no pixel of the camera frame reaches the
  output**. The cover is built from scratch, not blended over the frame.
* Opening and closing fade over a short time so the change is not jarring, and
  that fade is the only time camera pixels and cover mix.
* Whether to cover is the OR of two independent reasons: the user closed the
  shutter, or nobody is in frame (:class:`AwayDetector`). A manual close is never
  undone by a face reappearing, because the two reasons do not share state.
"""

from __future__ import annotations

from typing import Optional, Tuple

import cv2
import numpy as np

from .background import blur_background

__all__ = ["AwayDetector", "PrivacyShutter", "render_card"]


def render_card(size: Tuple[int, int], text: str) -> np.ndarray:
    """A calm dark card with centred text, built independently of any camera frame."""
    width, height = size
    ramp = np.linspace(38, 22, height, dtype=np.float32).reshape(height, 1)
    base = np.repeat(ramp, width, axis=1).astype(np.uint8)
    card = cv2.merge([base, base, np.clip(base.astype(np.int16) + 4, 0, 255).astype(np.uint8)])
    if text:
        font = cv2.FONT_HERSHEY_SIMPLEX
        scale = max(0.6, width / 900.0)
        thickness = max(1, round(scale * 1.6))
        (tw, th), _ = cv2.getTextSize(text, font, scale, thickness)
        # Shrink long text to fit rather than clip it.
        if tw > width * 0.9:
            scale *= (width * 0.9) / tw
            (tw, th), _ = cv2.getTextSize(text, font, scale, thickness)
        origin = ((width - tw) // 2, (height + th) // 2)
        cv2.putText(card, text, origin, font, scale, (214, 214, 220), thickness, cv2.LINE_AA)
    return card


class PrivacyShutter:
    """A fading cover over the output.

    Args:
        mode: ``card`` (text on a dark card), ``black`` or ``blur`` (a heavy blur of the frame).
        text: Label drawn on the ``card`` cover.
        fade: Seconds the open/close transition takes.
    """

    def __init__(self, mode: str = "card", text: str = "Be right back", fade: float = 0.25) -> None:
        self.mode = mode
        self.text = text
        self.fade = max(0.0, float(fade))
        self.closed = False
        self.level = 0.0  # 0 = fully open, 1 = fully covered
        self._last_time: Optional[float] = None
        self._card: Optional[np.ndarray] = None

    # ------------------------------------------------------------------ #
    def set_closed(self, closed: bool) -> None:
        self.closed = bool(closed)

    def toggle(self) -> bool:
        self.closed = not self.closed
        return self.closed

    # ------------------------------------------------------------------ #
    def _advance(self, now: float, force: bool) -> None:
        dt = 0.0 if self._last_time is None else max(0.0, now - self._last_time)
        self._last_time = now
        goal = 1.0 if (self.closed or force) else 0.0
        if self.fade <= 0.0:
            self.level = goal
            return
        step = dt / self.fade
        if goal > self.level:
            self.level = min(goal, self.level + step)
        else:
            self.level = max(goal, self.level - step)

    def cover(self, frame: np.ndarray) -> np.ndarray:
        height, width = frame.shape[:2]
        if self.mode == "black":
            return np.zeros_like(frame)
        if self.mode == "blur":
            return blur_background(frame, 101, scale=0.1)
        card = self._card
        if card is None or card.shape[:2] != (height, width):
            card = render_card((width, height), self.text)
            self._card = card
        return card

    def apply(self, frame: np.ndarray, now: float, force: bool = False) -> np.ndarray:
        """Return the frame with the shutter state applied.

        ``force`` closes the shutter without changing the user's own state; it is
        how the away detector and the camera-lost handler cover the output.
        """
        self._advance(now, force)
        if self.level <= 0.0:
            return frame
        cover = self.cover(frame)
        if self.level >= 1.0:
            return cover
        # Mid-fade only: the single case where camera pixels and cover coexist.
        alpha = np.float32(self.level)
        return cv2.addWeighted(cover, float(alpha), frame, float(1.0 - alpha), 0.0)


class AwayDetector:
    """Reports ``True`` once nobody has been in frame for ``timeout`` seconds.

    It returns to ``False`` the moment a face is seen again. A ``timeout`` of 0
    disables it.
    """

    def __init__(self, timeout: float) -> None:
        self.timeout = max(0.0, float(timeout))
        self._since: Optional[float] = None

    def update(self, face_present: bool, now: float) -> bool:
        if self.timeout <= 0.0:
            return False
        if face_present:
            self._since = None
            return False
        if self._since is None:
            self._since = now
        return (now - self._since) >= self.timeout

    def reset(self) -> None:
        self._since = None
