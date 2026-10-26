"""Auto-framing: keep the speaker centred without a motorised camera.

The framer turns face boxes into a smooth, bounded crop of the frame.

Why it is more than "crop around the face":

* **Deadzone.** A face that wobbles a few pixels must not move the picture.
  The target only changes when the subject has moved outside a small band.
* **Time-based smoothing.** The crop eases toward its target with a time
  constant, so the motion looks the same at 15 and 60 fps.
* **Sub-pixel crop.** The crop is applied with an affine warp, not integer
  slicing, so slow pans do not stutter pixel by pixel.
* **Limited zoom.** Cropping then upscaling softens the image. ``max_zoom``
  bounds how far it is allowed to go.
* **Graceful loss.** When the face is lost the crop holds for a moment, then
  eases back to the full frame instead of snapping.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

import cv2
import numpy as np

__all__ = ["AutoFramer", "Rect", "union_box"]

Box = Tuple[float, float, float, float]  # normalised x0, y0, x1, y1


@dataclass(frozen=True)
class Rect:
    """A crop rectangle in pixels. ``w``/``h`` always keep the frame's aspect ratio."""

    x: float
    y: float
    w: float
    h: float


def union_box(boxes: Sequence[Box]) -> Optional[Box]:
    """Smallest box containing every box, or ``None`` when empty."""
    if not boxes:
        return None
    return (
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    )


class AutoFramer:
    """Smooth face-following crop.

    Args:
        frame_size: ``(width, height)`` of the incoming frame.
        max_zoom: Largest zoom factor; 1.8 means the crop is never smaller than 1/1.8 of the frame.
        face_ratio: Desired height of the face box as a fraction of the crop height.
        tau: Smoothing time constant in seconds. Larger is calmer.
        deadzone: Fraction of the crop size the subject may drift before the target moves.
        hold: Seconds to keep the last framing after the face is lost.
    """

    def __init__(
        self,
        frame_size: Tuple[int, int],
        max_zoom: float = 1.8,
        face_ratio: float = 0.30,
        tau: float = 0.45,
        deadzone: float = 0.05,
        hold: float = 2.0,
    ) -> None:
        self.width, self.height = int(frame_size[0]), int(frame_size[1])
        self.max_zoom = float(max_zoom)
        self.face_ratio = float(face_ratio)
        self.tau = max(1e-3, float(tau))
        self.deadzone = float(deadzone)
        self.hold = float(hold)

        # State is (centre_x, centre_y, crop_height) in pixels.
        self._state: Tuple[float, float, float] = (self.width / 2.0, self.height / 2.0, float(self.height))
        self._target: Tuple[float, float, float] = self._state
        self._last_seen: Optional[float] = None
        self._last_time: Optional[float] = None
        self._locked = False  # True once the first face has been framed

    # ------------------------------------------------------------------ #
    @property
    def zoom(self) -> float:
        return self.height / self._state[2]

    def reset(self) -> None:
        self._state = (self.width / 2.0, self.height / 2.0, float(self.height))
        self._target = self._state
        self._last_seen = None
        self._last_time = None
        self._locked = False

    # ------------------------------------------------------------------ #
    def update(self, boxes: Sequence[Box], now: float) -> Rect:
        """Advance the framing by one frame and return the crop rectangle."""
        dt = 0.0 if self._last_time is None else max(0.0, min(now - self._last_time, 0.5))
        self._last_time = now

        subject = union_box(list(boxes))
        if subject is not None:
            self._last_seen = now
            self._retarget(subject)
        elif self._last_seen is not None and (now - self._last_seen) > self.hold:
            self._target = (self.width / 2.0, self.height / 2.0, float(self.height))

        if subject is not None and not self._locked:
            # First face after start (or after a reset): frame it immediately
            # rather than panning in from the full frame.
            self._locked = True
            self._state = self._target
            return self._rect()

        alpha = 1.0 - math.exp(-dt / self.tau) if dt > 0 else 0.0
        cx, cy, ch = self._state
        tx, ty, th = self._target
        cx += (tx - cx) * alpha
        cy += (ty - cy) * alpha
        ch += (th - ch) * alpha
        self._state = (cx, cy, ch)
        return self._rect()

    # ------------------------------------------------------------------ #
    def _retarget(self, box: Box) -> None:
        x0, y0, x1, y1 = box
        face_cx = (x0 + x1) / 2.0 * self.width
        face_cy = (y0 + y1) / 2.0 * self.height
        face_h = max((y1 - y0) * self.height, 1.0)
        face_w = max((x1 - x0) * self.width, 1.0)

        aspect = self.width / self.height
        # Size the crop so the face fills `face_ratio` of its height, but never so
        # tight that a wide group is cut off.
        wanted_h = face_h / self.face_ratio
        wanted_h = max(wanted_h, face_w / (self.face_ratio * 1.6) / aspect)
        crop_h = min(float(self.height), max(self.height / self.max_zoom, wanted_h))
        # Eyes sit near the upper third: put the face centre at ~40% of the crop.
        crop_cy = face_cy + (0.5 - 0.40) * crop_h
        crop_cx = face_cx

        cur_cx, cur_cy, cur_h = self._target
        band_x = self.deadzone * crop_h * aspect
        band_y = self.deadzone * crop_h
        band_h = self.deadzone * crop_h
        new_cx = crop_cx if abs(crop_cx - cur_cx) > band_x else cur_cx
        new_cy = crop_cy if abs(crop_cy - cur_cy) > band_y else cur_cy
        new_h = crop_h if abs(crop_h - cur_h) > band_h else cur_h
        self._target = (new_cx, new_cy, new_h)

    def _rect(self) -> Rect:
        cx, cy, ch = self._state
        aspect = self.width / self.height
        cw = ch * aspect
        x = min(max(cx - cw / 2.0, 0.0), self.width - cw)
        y = min(max(cy - ch / 2.0, 0.0), self.height - ch)
        return Rect(x, y, cw, ch)

    # ------------------------------------------------------------------ #
    def crop(self, frame: np.ndarray, rect: Rect) -> np.ndarray:
        """Crop ``rect`` out of ``frame`` and scale it back to the frame size (sub-pixel)."""
        if rect.w >= self.width - 0.5 and rect.h >= self.height - 0.5:
            return frame
        height, width = frame.shape[:2]
        scale = width / rect.w
        matrix = np.array([[scale, 0.0, -rect.x * scale], [0.0, scale, -rect.y * scale]], dtype=np.float32)
        return cv2.warpAffine(
            frame,
            matrix,
            (width, height),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REPLICATE,
        )


def face_boxes(faces: Sequence[object]) -> List[Box]:
    """Normalised bounding boxes for the faces that have one."""
    boxes: List[Box] = []
    for face in faces:
        bbox = getattr(face, "bbox", None)
        if bbox is not None:
            boxes.append((float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])))
            continue
        landmarks = getattr(face, "landmarks", None)
        if landmarks is not None and len(landmarks):
            xs, ys = landmarks[:, 0], landmarks[:, 1]
            boxes.append((float(xs.min()), float(ys.min()), float(xs.max()), float(ys.max())))
    return boxes
