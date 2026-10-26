"""Background blur, replacement and removal.

Three pieces, all pure NumPy/OpenCV so they can be tested without a camera or a
model:

* :class:`TemporalMask` stabilises the person mask across frames. A raw
  per-frame segmentation mask shimmers along the silhouette; averaging with the
  previous mask removes that, and a motion term stops the average from leaving a
  ghost trail when you move quickly.
* :func:`blur_background` blurs at a fraction of the resolution and scales back
  up. Blurring a 720p frame with a 51 px kernel is the single most expensive
  step in a naive implementation; at quarter resolution it is ~10x cheaper and
  visually indistinguishable, because the result is blurred anyway.
* :class:`BackgroundProcessor` ties the modes together and is **fail-closed**:
  when no mask is available (the model failed to load, or inference raised), it
  hides the whole frame behind a heavy blur instead of passing the real room
  through. A background effect that silently stops working is a privacy bug.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np

from ..utils.logging import get_logger

__all__ = [
    "BackgroundProcessor",
    "TemporalMask",
    "blur_background",
    "composite",
    "cover_resize",
]

log = get_logger("studio.background")

#: Chroma-key green used by the ``green`` mode (what OBS and Zoom expect).
CHROMA_GREEN = (0, 177, 64)  # BGR


class TemporalMask:
    """Exponential smoothing of a person mask with a motion-aware release.

    Args:
        smoothing: Weight of the previous mask, in ``[0, 1)``. 0 disables smoothing.
    """

    def __init__(self, smoothing: float = 0.55) -> None:
        self.smoothing = float(min(max(smoothing, 0.0), 0.98))
        self._previous: Optional[np.ndarray] = None

    def update(self, mask: np.ndarray) -> np.ndarray:
        mask = mask.astype(np.float32, copy=False)
        previous = self._previous
        if previous is None or previous.shape != mask.shape or self.smoothing == 0.0:
            self._previous = mask
            return mask
        # Where the new mask disagrees strongly with the old one, the subject
        # moved: trust the new mask. Where they agree, average to remove shimmer.
        change = np.abs(mask - previous)
        weight = self.smoothing * (1.0 - np.clip(change * 2.0, 0.0, 1.0))
        smoothed = weight * previous + (1.0 - weight) * mask
        self._previous = smoothed
        return smoothed

    def reset(self) -> None:
        self._previous = None


def blur_background(frame: np.ndarray, strength: int = 51, scale: float = 0.25) -> np.ndarray:
    """Gaussian-blur ``frame`` cheaply by working at ``scale`` of its size."""
    height, width = frame.shape[:2]
    small_w = max(8, int(width * scale))
    small_h = max(8, int(height * scale))
    small = cv2.resize(frame, (small_w, small_h), interpolation=cv2.INTER_AREA)
    kernel = max(3, int(strength * scale)) | 1
    small = cv2.GaussianBlur(small, (kernel, kernel), 0)
    return cv2.resize(small, (width, height), interpolation=cv2.INTER_LINEAR)


def composite(foreground: np.ndarray, background: np.ndarray, alpha: np.ndarray) -> np.ndarray:
    """Blend ``foreground`` over ``background`` using ``alpha`` in ``[0, 1]``."""
    alpha = np.clip(alpha, 0.0, 1.0).astype(np.float32, copy=False)
    if alpha.ndim == 3:
        alpha = alpha[..., 0]
    inverse = 1.0 - alpha
    try:
        return cv2.blendLinear(foreground, background, alpha, inverse)
    except cv2.error:  # pragma: no cover - old OpenCV builds
        weight = alpha[..., None]
        blended = foreground.astype(np.float32) * weight + background.astype(np.float32) * (1.0 - weight)
        return blended.astype(np.uint8)


def cover_resize(image: np.ndarray, size: Tuple[int, int]) -> np.ndarray:
    """Resize ``image`` to ``size`` (w, h), cropping the excess instead of stretching."""
    width, height = size
    src_h, src_w = image.shape[:2]
    scale = max(width / src_w, height / src_h)
    new_w, new_h = max(width, round(src_w * scale)), max(height, round(src_h * scale))
    interpolation = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_CUBIC
    resized = cv2.resize(image, (new_w, new_h), interpolation=interpolation)
    x0 = (new_w - width) // 2
    y0 = (new_h - height) // 2
    return np.ascontiguousarray(resized[y0 : y0 + height, x0 : x0 + width])


class BackgroundProcessor:
    """Applies the selected background mode to a frame.

    Args:
        mode: ``off``, ``blur``, ``replace``, ``green`` or ``black``.
        blur_strength: Kernel size (in full-resolution pixels) for ``blur`` mode.
        image_path: Image used by ``replace``. Without it, ``replace`` degrades to ``blur``.
        smoothing: Temporal mask smoothing, see :class:`TemporalMask`.
    """

    def __init__(
        self,
        mode: str = "off",
        blur_strength: int = 51,
        image_path: str = "",
        smoothing: float = 0.55,
    ) -> None:
        self.mode = mode
        self.blur_strength = int(blur_strength)
        self.image_path = image_path
        self.fail_closed_frames = 0
        self._temporal = TemporalMask(smoothing)
        self._image: Optional[np.ndarray] = None
        self._image_scaled: Optional[np.ndarray] = None
        self._image_error = ""
        if image_path:
            self._load_image(image_path)

    # ------------------------------------------------------------------ #
    def _load_image(self, path: str) -> None:
        target = Path(path).expanduser()
        image = cv2.imread(str(target), cv2.IMREAD_COLOR) if target.is_file() else None
        if image is None:
            self._image_error = f"background image not readable: {target}"
            log.warning("%s — falling back to blur", self._image_error)
            return
        self._image = image
        self._image_scaled = None

    @staticmethod
    def image_readable(path: str) -> bool:
        target = Path(path).expanduser()
        return target.is_file() and cv2.imread(str(target), cv2.IMREAD_COLOR) is not None

    @property
    def has_image(self) -> bool:
        return self._image is not None

    @property
    def needs_mask(self) -> bool:
        return self.mode != "off"

    def set_mode(self, mode: str) -> None:
        if mode != self.mode:
            self.mode = mode
            self._temporal.reset()

    # ------------------------------------------------------------------ #
    def apply(self, frame: np.ndarray, mask: Optional[np.ndarray]) -> np.ndarray:
        """Return ``frame`` with the background treated according to the mode.

        ``mask`` is the person alpha in ``[0, 1]`` at **any** resolution, or ``None``
        when segmentation is unavailable. A low-resolution mask is cheaper end to
        end: temporal smoothing runs at mask size and the result is scaled up once.
        With ``None`` the **whole frame** is blurred rather than returned untouched
        (fail-closed).
        """
        if self.mode == "off":
            return frame

        if mask is None or mask.ndim != 2 or mask.size == 0:
            self.fail_closed_frames += 1
            return blur_background(frame, max(self.blur_strength, 61))

        alpha = self._temporal.update(mask)
        if alpha.shape[:2] != frame.shape[:2]:
            alpha = cv2.resize(alpha, (frame.shape[1], frame.shape[0]), interpolation=cv2.INTER_LINEAR)
        return composite(frame, self._background_for(frame), alpha)

    def _background_for(self, frame: np.ndarray) -> np.ndarray:
        height, width = frame.shape[:2]
        mode = self.mode
        if mode == "blur":
            return blur_background(frame, self.blur_strength)
        if mode == "green":
            return np.full_like(frame, CHROMA_GREEN)
        if mode == "black":
            return np.zeros_like(frame)
        if mode == "replace":
            if self._image is None:
                return blur_background(frame, self.blur_strength)
            cached = self._image_scaled
            if cached is None or cached.shape[:2] != (height, width):
                cached = cover_resize(self._image, (width, height))
                self._image_scaled = cached
            return cached
        raise ValueError(f"unknown background mode: {mode!r}")
