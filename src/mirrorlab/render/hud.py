"""Heads-up display: the information layer drawn on top of the composited frame.

Everything here is deliberately dependency-free (OpenCV primitives only) and
resolution-independent: sizes are derived from the frame height so the HUD looks
identical at 480p and 1080p, and on a Retina display.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Dict, List, Sequence, Tuple

import cv2
import numpy as np

from ..detectors.base import FACE_OVAL, HAND_CONNECTIONS, FaceObservation, HandObservation
from ..utils.colors import Palette, get_palette

__all__ = [
    "Hud",
    "HudState",
    "ascii_text",
    "draw_badge",
    "draw_bar",
    "draw_face",
    "draw_hand",
    "draw_reticle",
]

BGR = Tuple[int, int, int]

#: ``cv2.putText`` renders with Hershey vector fonts, which only cover ASCII.
#: Emoji and box-drawing characters come out as rows of question marks, so the
#: HUD sanitises every string it draws. The CLI and the website keep the emoji —
#: terminals and browsers render them fine.
_ASCII_FALLBACK = {
    "\u00b7": "-",  # middle dot
    "\u2192": "->",  # right arrow
    "\u2190": "<-",  # left arrow
    "\u2013": "-",  # en dash
    "\u2014": "-",  # em dash
    "\u00e1": "a",
    "\u00e9": "e",
    "\u00ed": "i",
    "\u00f3": "o",
    "\u00fa": "u",
    "\u00c1": "A",
    "\u00c9": "E",
    "\u00cd": "I",
    "\u00d3": "O",
    "\u00da": "U",
    "\u00f1": "n",
    "\u00d1": "N",
    "\u00fc": "u",
    "\u00bf": "?",
    "\u00a1": "!",
}


def ascii_text(value: object) -> str:
    """Make a string safe for ``cv2.putText``.

    Transliterates the punctuation and accents the bilingual UI actually uses,
    then drops anything still outside printable ASCII (emoji, symbols), and
    collapses the gaps that removal leaves behind.
    """
    text = str(value)
    for source, target in _ASCII_FALLBACK.items():
        text = text.replace(source, target)
    cleaned = "".join(ch if 32 <= ord(ch) < 127 else " " for ch in text)
    return " ".join(cleaned.split())


@dataclass
class HudState:
    """Snapshot of everything the HUD needs for one frame."""

    fps: float = 0.0
    frame_time_ms: float = 0.0
    inference_ms: float = 0.0
    filter_name: str = "original"
    filter_label: str = "Original"
    effect_names: List[str] = field(default_factory=list)
    expression: str = ""
    expression_label: str = ""
    expression_score: float = 0.0
    expression_scores: Dict[str, float] = field(default_factory=dict)
    gesture: str = ""
    gesture_label: str = ""
    gesture_score: float = 0.0
    recording: bool = False
    frozen: bool = False
    air_draw: bool = False
    hands: int = 0
    faces: int = 0
    messages: List[Tuple[str, float]] = field(default_factory=list)  # (text, age seconds)


class Hud:
    """Draws panels, badges and skeleton overlays onto a BGR frame.

    Args:
        palette: Colour theme name or a :class:`~mirrorlab.utils.colors.Palette`.
        show_landmarks: Draw face mesh and hand skeletons.
        show_fps: Draw the performance panel.
        compact: Reduce the HUD to a single line (for small preview windows).
    """

    def __init__(
        self,
        palette: str | Palette = "aurora",
        show_landmarks: bool = True,
        show_fps: bool = True,
        compact: bool = False,
    ) -> None:
        self.palette = palette if isinstance(palette, Palette) else get_palette(palette)
        self.show_landmarks = bool(show_landmarks)
        self.show_fps = bool(show_fps)
        self.compact = bool(compact)
        self._started = time.perf_counter()

    # ------------------------------------------------------------------ #
    def render(
        self,
        frame: np.ndarray,
        state: HudState,
        faces: Sequence[FaceObservation] = (),
        hands: Sequence[HandObservation] = (),
    ) -> np.ndarray:
        """Draw the full HUD and return the frame (mutated in place for speed)."""
        if self.show_landmarks:
            self._draw_skeletons(frame, faces, hands)
        if self.show_fps:
            self._draw_performance(frame, state)
        self._draw_status(frame, state)
        self._draw_scores(frame, state)
        self._draw_toasts(frame, state)
        if state.frozen:
            self._draw_center_banner(frame, "PAUSA", self.palette.warn)
        return frame

    # ------------------------------------------------------------------ #
    # Panels
    # ------------------------------------------------------------------ #
    def _draw_performance(self, frame: np.ndarray, state: HudState) -> None:
        height, _width = frame.shape[:2]
        scale = height / 720.0
        pad = int(12 * scale)
        font = cv2.FONT_HERSHEY_DUPLEX
        font_scale = 0.46 * scale
        thickness = max(1, round(scale))

        lines = [
            f"{state.fps:5.1f} FPS",
            f"{state.frame_time_ms:4.1f} ms frame",
            f"{state.inference_ms:4.1f} ms AI",
            f"{state.hands} hand(s)  {state.faces} face(s)",
        ]
        box_w = int(max(len(line) for line in lines) * 9.2 * scale) + pad * 2
        box_h = int(len(lines) * 18 * scale) + pad
        self._panel(frame, (pad, pad), (box_w, box_h))

        y = pad + int(15 * scale)
        cv2.putText(
            frame,
            ascii_text(lines[0]),
            (pad * 2, y),
            font,
            font_scale * 1.25,
            self.palette.primary,
            thickness,
            cv2.LINE_AA,
        )
        for line in lines[1:]:
            y += int(18 * scale)
            cv2.putText(
                frame,
                ascii_text(line),
                (pad * 2, y),
                font,
                font_scale,
                self.palette.text_dim,
                thickness,
                cv2.LINE_AA,
            )

    def _draw_status(self, frame: np.ndarray, state: HudState) -> None:
        height, width = frame.shape[:2]
        scale = height / 720.0
        pad = int(12 * scale)
        font = cv2.FONT_HERSHEY_DUPLEX

        # Filter badge, top-right.
        label = state.filter_label
        text_w = int(len(label) * 10 * scale)
        x0 = width - text_w - pad * 3
        self._panel(frame, (x0, pad), (text_w + pad * 2, int(30 * scale)))
        cv2.putText(
            frame,
            ascii_text(label),
            (x0 + pad, pad + int(21 * scale)),
            font,
            0.55 * scale,
            self.palette.primary,
            max(1, int(scale)),
            cv2.LINE_AA,
        )

        extras: List[str] = []
        if state.effect_names:
            extras.append("+ " + ", ".join(state.effect_names[:3]))
        if state.air_draw:
            extras.append("* AIR DRAW")
        if state.recording:
            extras.append("* REC")
        for index, text in enumerate(extras):
            y0 = pad + int((34 + index * 26) * scale)
            colour = self.palette.warn if "REC" in text else self.palette.secondary
            cv2.putText(
                frame,
                ascii_text(text),
                (x0 + pad, y0 + int(16 * scale)),
                font,
                0.5 * scale,
                colour,
                max(1, int(scale)),
                cv2.LINE_AA,
            )

        # Expression + gesture badges, bottom-left.
        y = height - pad
        if state.expression_label:
            y = draw_badge(
                frame,
                f"{state.expression_label}  {state.expression_score * 100:.0f}%",
                (pad, y),
                self.palette.secondary,
                scale,
                anchor="bottom",
            )
            y -= int(8 * scale)
        if state.gesture_label:
            draw_badge(frame, state.gesture_label, (pad, y), self.palette.primary, scale, anchor="bottom")

    def _draw_scores(self, frame: np.ndarray, state: HudState) -> None:
        """Small bar chart of the expression scores — the 'why' behind the label."""
        if not state.expression_scores or self.compact:
            return
        height, width = frame.shape[:2]
        scale = height / 720.0
        top = sorted(state.expression_scores.items(), key=lambda kv: -kv[1])[:5]
        if not top or top[0][1] <= 0.01:
            return

        pad = int(12 * scale)
        bar_w = int(120 * scale)
        bar_h = max(3, int(7 * scale))
        row_h = bar_h + int(9 * scale)
        x0 = width - bar_w - pad * 3
        y0 = height - pad - row_h * len(top)
        font = cv2.FONT_HERSHEY_PLAIN

        for index, (name, score) in enumerate(top):
            y = y0 + index * row_h
            cv2.putText(
                frame,
                ascii_text(name[:12]),
                (x0, y),
                font,
                0.85 * scale,
                self.palette.text_dim,
                1,
                cv2.LINE_AA,
            )
            bx = x0 + int(72 * scale)
            cv2.rectangle(frame, (bx, y - bar_h), (bx + bar_w - int(72 * scale), y), (60, 60, 60), -1)
            filled = int((bar_w - 72 * scale) * max(0.0, min(1.0, score)))
            colour = self.palette.primary if index == 0 else self.palette.secondary
            cv2.rectangle(frame, (bx, y - bar_h), (bx + filled, y), colour, -1)

    def _draw_toasts(self, frame: np.ndarray, state: HudState) -> None:
        if not state.messages:
            return
        height, width = frame.shape[:2]
        scale = height / 720.0
        font = cv2.FONT_HERSHEY_DUPLEX
        y = int(height * 0.16)
        for index, (text, age) in enumerate(state.messages[:3]):
            fade = max(0.0, 1.0 - age / 2.0)
            if fade <= 0:
                continue
            size = cv2.getTextSize(text, font, 0.7 * scale, 2)[0]
            x0 = (width - size[0]) // 2 - int(16 * scale)
            y0 = y + index * int(42 * scale)
            self._panel(
                frame, (x0, y0), (size[0] + int(32 * scale), size[1] + int(18 * scale)), alpha=0.55 * fade
            )
            cv2.putText(
                frame,
                ascii_text(text),
                (x0 + int(16 * scale), y0 + size[1] + int(9 * scale)),
                font,
                0.7 * scale,
                self.palette.text,
                2,
                cv2.LINE_AA,
            )

    def _draw_center_banner(self, frame: np.ndarray, text: str, colour: BGR) -> None:
        height, width = frame.shape[:2]
        scale = height / 720.0
        font = cv2.FONT_HERSHEY_DUPLEX
        size = cv2.getTextSize(text, font, 1.6 * scale, 3)[0]
        cv2.putText(
            frame,
            ascii_text(text),
            ((width - size[0]) // 2, height // 2 + size[1] // 2),
            font,
            1.6 * scale,
            colour,
            3,
            cv2.LINE_AA,
        )

    # ------------------------------------------------------------------ #
    def _panel(
        self,
        frame: np.ndarray,
        origin: Tuple[int, int],
        size: Tuple[int, int],
        alpha: float = 0.42,
    ) -> None:
        """Translucent rounded panel with a hairline border."""
        x0, y0 = origin
        w, h = size
        height, width = frame.shape[:2]
        x1, y1 = min(width, x0 + w), min(height, y0 + h)
        x0, y0 = max(0, x0), max(0, y0)
        if x1 <= x0 or y1 <= y0:
            return
        roi = frame[y0:y1, x0:x1]
        overlay = np.full_like(roi, self.palette.panel, dtype=np.uint8)
        cv2.addWeighted(overlay, alpha, roi, 1.0 - alpha, 0, dst=roi)
        cv2.rectangle(frame, (x0, y0), (x1 - 1, y1 - 1), self.palette.primary, 1, cv2.LINE_AA)

    # ------------------------------------------------------------------ #
    def _draw_skeletons(
        self,
        frame: np.ndarray,
        faces: Sequence[FaceObservation],
        hands: Sequence[HandObservation],
    ) -> None:
        height, width = frame.shape[:2]
        scale = max(1, round(height / 480.0))
        for face in faces:
            draw_face(frame, face, width, height, self.palette.face, scale)
        for hand in hands:
            colour = self.palette.right_hand if hand.is_right else self.palette.left_hand
            draw_hand(frame, hand, width, height, colour, scale)


# --------------------------------------------------------------------------- #
# Free functions (usable without a Hud instance)
# --------------------------------------------------------------------------- #
def draw_hand(
    frame: np.ndarray,
    hand: HandObservation,
    width: int,
    height: int,
    colour: BGR = (200, 250, 120),
    scale: int = 1,
) -> None:
    """Draw the 21-point hand skeleton with joint markers."""
    points = [
        (int(hand.landmarks[i, 0] * width), int(hand.landmarks[i, 1] * height))
        for i in range(min(21, hand.landmarks.shape[0]))
    ]
    for start, end in HAND_CONNECTIONS:
        if start < len(points) and end < len(points):
            cv2.line(frame, points[start], points[end], colour, max(1, scale), cv2.LINE_AA)
    for index, point in enumerate(points):
        radius = (4 if index in (4, 8, 12, 16, 20) else 2) * scale
        cv2.circle(frame, point, radius, (255, 255, 255), -1, cv2.LINE_AA)
        cv2.circle(frame, point, radius + scale, colour, max(1, scale), cv2.LINE_AA)


def draw_face(
    frame: np.ndarray,
    face: FaceObservation,
    width: int,
    height: int,
    colour: BGR = (250, 200, 120),
    scale: int = 1,
) -> None:
    """Draw a light face mesh: the oval plus the expressive features."""
    if face.count < 400:
        return
    oval = np.array(
        [[int(face.landmarks[i, 0] * width), int(face.landmarks[i, 1] * height)] for i in FACE_OVAL],
        dtype=np.int32,
    )
    cv2.polylines(frame, [oval], True, colour, max(1, scale), cv2.LINE_AA)

    features = (
        (33, 133),
        (362, 263),  # eye corners
        (61, 291),
        (13, 14),  # mouth
        (105, 334),  # brows
        (1, 168),  # nose bridge
    )
    for start, end in features:
        p0 = (int(face.landmarks[start, 0] * width), int(face.landmarks[start, 1] * height))
        p1 = (int(face.landmarks[end, 0] * width), int(face.landmarks[end, 1] * height))
        cv2.line(frame, p0, p1, colour, max(1, scale), cv2.LINE_AA)

    for index in (33, 133, 362, 263, 1, 61, 291, 13, 14, 152, 10):
        if index < face.count:
            point = (int(face.landmarks[index, 0] * width), int(face.landmarks[index, 1] * height))
            cv2.circle(frame, point, max(1, scale), colour, -1, cv2.LINE_AA)


def draw_badge(
    frame: np.ndarray,
    text: str,
    origin: Tuple[int, int],
    colour: BGR,
    scale: float = 1.0,
    anchor: str = "bottom",
    alpha: float = 0.55,
) -> int:
    """Draw a rounded label chip and return the y coordinate of its top edge."""
    font = cv2.FONT_HERSHEY_DUPLEX
    font_scale = 0.62 * scale
    thickness = max(1, round(scale))
    (text_w, text_h), baseline = cv2.getTextSize(text, font, font_scale, thickness)
    pad_x, pad_y = int(14 * scale), int(9 * scale)
    x0, y = origin
    y0 = y - (text_h + baseline + pad_y * 2) if anchor == "bottom" else y
    w, h = text_w + pad_x * 2, text_h + baseline + pad_y * 2
    x1, y1 = x0 + w, y0 + h

    overlay = frame.copy()
    cv2.rectangle(overlay, (x0, y0), (x1, y1), (20, 20, 22), -1)
    cv2.addWeighted(overlay, alpha, frame, 1.0 - alpha, 0, dst=frame)
    cv2.rectangle(frame, (x0, y0), (x1, y1), colour, max(1, round(scale)), cv2.LINE_AA)
    cv2.putText(
        frame,
        ascii_text(text),
        (x0 + pad_x, y0 + pad_y + text_h),
        font,
        font_scale,
        colour,
        thickness,
        cv2.LINE_AA,
    )
    return y0


def draw_bar(
    frame: np.ndarray,
    origin: Tuple[int, int],
    size: Tuple[int, int],
    value: float,
    colour: BGR,
    background: BGR = (55, 55, 60),
) -> None:
    """Horizontal progress bar with a 0..1 ``value``."""
    x, y = origin
    w, h = size
    cv2.rectangle(frame, (x, y), (x + w, y + h), background, -1, cv2.LINE_AA)
    filled = int(w * max(0.0, min(1.0, value)))
    if filled > 0:
        cv2.rectangle(frame, (x, y), (x + filled, y + h), colour, -1, cv2.LINE_AA)


def draw_reticle(
    frame: np.ndarray, centre: Tuple[int, int], radius: int, colour: BGR, phase: float = 0.0
) -> None:
    """Animated targeting reticle used by air-draw and gesture focus."""
    for index in range(4):
        start = math.radians(phase * 60 + index * 90 + 20)
        end = math.radians(phase * 60 + index * 90 + 70)
        p0 = (int(centre[0] + radius * math.cos(start)), int(centre[1] + radius * math.sin(start)))
        p1 = (int(centre[0] + radius * math.cos(end)), int(centre[1] + radius * math.sin(end)))
        cv2.line(frame, p0, p1, colour, 2, cv2.LINE_AA)
    cv2.circle(frame, centre, max(1, radius // 3), colour, 1, cv2.LINE_AA)
