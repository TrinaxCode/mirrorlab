"""Gesture reactions: small animated icons that float up over the picture.

The icons are drawn procedurally at 4x and scaled down, which gives clean
anti-aliased edges and means there is no binary artwork to ship or license.
Each icon is rendered once into an RGBA sprite and cached per size.

A reaction is a one-shot visual signal for the other people on the call ("good",
"love it", "agreed") that costs the speaker no keyboard or mouse. It is rendered
into the frame that goes to the virtual camera, so every call app shows it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

import cv2
import numpy as np

__all__ = ["REACTIONS", "ReactionStage", "render_icon"]

_SUPERSAMPLE = 4
_BASE = 128  # design grid is 128x128


def _canvas() -> np.ndarray:
    size = _BASE * _SUPERSAMPLE
    return np.zeros((size, size, 4), dtype=np.uint8)


def _pts(points: List[List[float]]) -> np.ndarray:
    return (np.array(points, dtype=np.float32) * _SUPERSAMPLE).astype(np.int32)


def _fill(canvas: np.ndarray, polygon: np.ndarray, colour: tuple) -> None:
    cv2.fillPoly(canvas, [polygon], (*colour, 255), cv2.LINE_AA)


def _heart() -> np.ndarray:
    canvas = _canvas()
    t = np.linspace(0, 2 * math.pi, 240)
    x = 16 * np.sin(t) ** 3
    y = 13 * np.cos(t) - 5 * np.cos(2 * t) - 2 * np.cos(3 * t) - np.cos(4 * t)
    scale = 3.3
    points = [[64 + xi * scale, 58 - yi * scale] for xi, yi in zip(x, y)]
    _fill(canvas, _pts(points), (60, 60, 232))
    # Soft highlight, upper left lobe.
    cv2.ellipse(
        canvas,
        (int(40 * _SUPERSAMPLE), int(40 * _SUPERSAMPLE)),
        (int(9 * _SUPERSAMPLE), int(5 * _SUPERSAMPLE)),
        -35,
        0,
        360,
        (150, 150, 255, 255),
        -1,
        cv2.LINE_AA,
    )
    return canvas


def _thumbs_up() -> np.ndarray:
    canvas = _canvas()
    skin = (74, 184, 245)
    shade = (52, 150, 220)
    # Cuff.
    _fill(canvas, _pts([[18, 62], [38, 62], [38, 112], [18, 112]]), (130, 110, 70))
    # Palm and fingers block.
    _fill(
        canvas,
        _pts(
            [
                [38, 62],
                [62, 58],
                [72, 30],
                [84, 28],
                [90, 40],
                [84, 62],
                [108, 62],
                [114, 72],
                [110, 80],
                [114, 88],
                [108, 96],
                [110, 104],
                [102, 112],
                [38, 112],
            ]
        ),
        skin,
    )
    # Finger separations.
    for y in (80, 96):
        cv2.line(
            canvas,
            (int(70 * _SUPERSAMPLE), y * _SUPERSAMPLE),
            (int(108 * _SUPERSAMPLE), y * _SUPERSAMPLE),
            (*shade, 255),
            int(1.6 * _SUPERSAMPLE),
            cv2.LINE_AA,
        )
    return canvas


def _ok() -> np.ndarray:
    canvas = _canvas()
    centre = (64 * _SUPERSAMPLE, 64 * _SUPERSAMPLE)
    cv2.circle(canvas, centre, 52 * _SUPERSAMPLE, (96, 190, 70, 255), -1, cv2.LINE_AA)
    check = _pts([[38, 66], [56, 84], [92, 44]])
    cv2.polylines(canvas, [check], False, (255, 255, 255, 255), 11 * _SUPERSAMPLE // 2, cv2.LINE_AA)
    return canvas


def _star() -> np.ndarray:
    canvas = _canvas()
    points = []
    for i in range(10):
        radius = 56 if i % 2 == 0 else 24
        angle = -math.pi / 2 + i * math.pi / 5
        points.append([64 + radius * math.cos(angle), 66 + radius * math.sin(angle)])
    _fill(canvas, _pts(points), (40, 200, 250))
    return canvas


#: Reaction name -> sprite factory.
REACTIONS: Dict[str, Callable[[], np.ndarray]] = {
    "love": _heart,
    "heart": _heart,
    "thumbs_up": _thumbs_up,
    "ok": _ok,
    "star": _star,
}


def render_icon(name: str, size: int) -> Optional[np.ndarray]:
    """Return an RGBA ``size`` x ``size`` sprite for ``name``, or ``None`` if unknown."""
    factory = REACTIONS.get(name)
    if factory is None:
        return None
    sprite = factory()
    return cv2.resize(sprite, (size, size), interpolation=cv2.INTER_AREA)


@dataclass
class _Floating:
    sprite: np.ndarray
    born: float
    seed: float


class ReactionStage:
    """Tracks live reactions and draws them onto frames.

    Args:
        duration: Seconds a reaction stays on screen.
        max_active: Upper bound on simultaneous icons, so spamming cannot cover the picture.
    """

    def __init__(self, duration: float = 2.4, max_active: int = 6) -> None:
        self.duration = float(duration)
        self.max_active = int(max_active)
        self._active: List[_Floating] = []
        self._sprites: Dict[tuple, np.ndarray] = {}
        self._counter = 0

    @property
    def active(self) -> int:
        return len(self._active)

    def trigger(self, name: str, now: float, frame_height: int) -> bool:
        """Start a reaction. Returns ``False`` for an unknown name."""
        size = max(48, int(frame_height * 0.16))
        key = (name, size)
        sprite = self._sprites.get(key)
        if sprite is None:
            sprite = render_icon(name, size)
            if sprite is None:
                return False
            self._sprites[key] = sprite
        self._counter += 1
        self._active.append(_Floating(sprite=sprite, born=now, seed=(self._counter * 2.399) % (2 * math.pi)))
        del self._active[: -self.max_active]
        return True

    def apply(self, frame: np.ndarray, now: float) -> np.ndarray:
        """Draw every live reaction onto ``frame`` (in place) and return it."""
        if not self._active:
            return frame
        height, width = frame.shape[:2]
        alive: List[_Floating] = []
        for item in self._active:
            age = now - item.born
            if age >= self.duration:
                continue
            alive.append(item)
            progress = age / self.duration
            sprite = item.sprite
            size = sprite.shape[0]
            # Rise from the lower right, drifting side to side; ease out so it slows near the top.
            eased = 1.0 - (1.0 - progress) ** 2
            x = int(width * 0.86 - size / 2 + math.sin(item.seed + progress * 5.0) * size * 0.35)
            y = int(height * 0.88 - eased * height * 0.55 - size / 2)
            opacity = 1.0 if progress < 0.7 else max(0.0, (1.0 - progress) / 0.3)
            _blend_sprite(frame, sprite, x, y, opacity)
        self._active = alive
        return frame


def _blend_sprite(frame: np.ndarray, sprite: np.ndarray, x: int, y: int, opacity: float) -> None:
    height, width = frame.shape[:2]
    sh, sw = sprite.shape[:2]
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(width, x + sw), min(height, y + sh)
    if x1 <= x0 or y1 <= y0:
        return
    patch = sprite[y0 - y : y1 - y, x0 - x : x1 - x]
    alpha = (patch[..., 3:4].astype(np.float32) / 255.0) * float(opacity)
    roi = frame[y0:y1, x0:x1]
    blended = patch[..., :3].astype(np.float32) * alpha + roi.astype(np.float32) * (1.0 - alpha)
    roi[:] = blended.astype(np.uint8)
