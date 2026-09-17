"""Augmented-reality effects anchored to detected landmarks.

Every effect is drawn **procedurally** with OpenCV primitives rather than
composited from PNG assets. That keeps the repository free of binary artwork,
makes the effects resolution-independent, and lets each one be parameterised
(size, colour, tilt) from the configuration or the CLI.

Face effects anchor to the 468/478-point FaceMesh; hand effects anchor to the
21-point hand skeleton. Both receive plain landmark arrays, so they work with
any detector backend.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

import cv2
import numpy as np

from ..detectors.base import FaceObservation, HandObservation
from ..utils.geometry import distance, hand_scale
from ..utils.logging import get_logger

__all__ = [
    "ALL_EFFECTS",
    "FACE_EFFECTS",
    "HAND_EFFECTS",
    "EffectContext",
    "FaceEffect",
    "HandEffect",
    "build_effects",
    "build_hand_effects",
    "effect_catalog",
    "register_face_effect",
    "register_hand_effect",
]

log = get_logger("effects")

BGR = Tuple[int, int, int]

# --------------------------------------------------------------------------- #
# FaceMesh landmark indices (MediaPipe canonical)
# --------------------------------------------------------------------------- #
RIGHT_EYE_OUTER, RIGHT_EYE_INNER = 33, 133
LEFT_EYE_INNER, LEFT_EYE_OUTER = 362, 263
RIGHT_EYE_TOP, RIGHT_EYE_BOTTOM = 159, 145
LEFT_EYE_TOP, LEFT_EYE_BOTTOM = 386, 374
RIGHT_IRIS, LEFT_IRIS = 468, 473
NOSE_TIP, NOSE_BRIDGE = 1, 168
FOREHEAD_TOP = 10
CHIN = 152
MOUTH_RIGHT, MOUTH_LEFT = 61, 291
UPPER_LIP, LOWER_LIP = 13, 14
RIGHT_CHEEK, LEFT_CHEEK = 234, 454
RIGHT_BROW_MID, LEFT_BROW_MID = 105, 334


@dataclass
class EffectContext:
    """Frame metadata passed to every effect."""

    frame_index: int = 0
    time: float = 0.0
    delta: float = 1.0 / 30.0
    width: int = 0
    height: int = 0
    state: Dict[str, object] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.state is None:
            self.state = {}


class FaceEffect:
    """Base class for landmark-anchored face overlays."""

    name: str = "effect"
    label: str = "Effect"
    label_es: str = "Efecto"
    emoji: str = "✨"
    description: str = ""
    description_es: str = ""
    requires_landmarks: bool = True

    def apply(self, frame: np.ndarray, face: FaceObservation, ctx: EffectContext) -> np.ndarray:
        raise NotImplementedError

    def draw_skeleton(self, frame: np.ndarray, face: FaceObservation, ctx: EffectContext) -> None:
        """Hook for effects that want to draw the mesh itself."""


class HandEffect:
    """Base class for hand-anchored overlays."""

    name: str = "hand_effect"
    label: str = "Hand effect"
    label_es: str = "Efecto de mano"
    emoji: str = "🖐️"
    description: str = ""
    description_es: str = ""

    def apply(self, frame: np.ndarray, hand: HandObservation, ctx: EffectContext) -> np.ndarray:
        raise NotImplementedError


FACE_EFFECTS: Dict[str, FaceEffect] = {}
HAND_EFFECTS: Dict[str, HandEffect] = {}


def register_face_effect(effect: FaceEffect) -> FaceEffect:
    FACE_EFFECTS[effect.name] = effect
    return effect


def register_hand_effect(effect: HandEffect) -> HandEffect:
    HAND_EFFECTS[effect.name] = effect
    return effect


def effect_catalog() -> List[dict]:
    rows = [
        {
            "name": e.name,
            "label": e.label,
            "label_es": e.label_es,
            "emoji": e.emoji,
            "description": e.description,
            "description_es": e.description_es,
            "kind": "face",
        }
        for e in FACE_EFFECTS.values()
    ]
    rows += [
        {
            "name": e.name,
            "label": e.label,
            "label_es": e.label_es,
            "emoji": e.emoji,
            "description": e.description,
            "description_es": e.description_es,
            "kind": "hand",
        }
        for e in HAND_EFFECTS.values()
    ]
    return rows


ALL_EFFECTS = {**FACE_EFFECTS, **HAND_EFFECTS}


# --------------------------------------------------------------------------- #
# Geometry helpers
# --------------------------------------------------------------------------- #
def _px(point: Sequence[float], width: int, height: int) -> Tuple[int, int]:
    return round(float(point[0]) * width), round(float(point[1]) * height)


def _face_frame(face: FaceObservation, width: int, height: int) -> Tuple[Tuple[int, int], float, float]:
    """Return ``(centre, inter-ocular distance in px, roll angle in degrees)``.

    Anchoring everything to the eye line is what makes overlays stick to the
    face through head tilts: the inter-ocular distance sets the scale and the
    eye-line angle sets the rotation.
    """
    right = _px(face.point(RIGHT_EYE_OUTER), width, height)
    left = _px(face.point(LEFT_EYE_OUTER), width, height)
    interocular = float(np.hypot(left[0] - right[0], left[1] - right[1]))
    angle_deg = math.degrees(math.atan2(left[1] - right[1], left[0] - right[0]))
    centre = ((right[0] + left[0]) // 2, (right[1] + left[1]) // 2)
    return centre, max(interocular, 8.0), angle_deg


def _rotate(points: np.ndarray, origin: Tuple[int, int], angle_deg: float) -> np.ndarray:
    """Rotate integer points around ``origin`` by ``angle_deg``."""
    theta = math.radians(angle_deg)
    cos_t, sin_t = math.cos(theta), math.sin(theta)
    shifted = points.astype(np.float64) - np.asarray(origin, dtype=np.float64)
    rotated = np.stack(
        [
            shifted[:, 0] * cos_t - shifted[:, 1] * sin_t,
            shifted[:, 0] * sin_t + shifted[:, 1] * cos_t,
        ],
        axis=1,
    )
    return (rotated + np.asarray(origin, dtype=np.float64)).astype(np.int32)


def _ellipse_pts(centre: Tuple[int, int], axes: Tuple[int, int], count: int = 40) -> np.ndarray:
    theta = np.linspace(0, 2 * np.pi, count, endpoint=False)
    xs = centre[0] + axes[0] * np.cos(theta)
    ys = centre[1] + axes[1] * np.sin(theta)
    return np.stack([xs, ys], axis=1).astype(np.int32)


def _blend_poly(frame: np.ndarray, polygon: np.ndarray, colour: BGR, alpha: float = 1.0) -> None:
    """Fill a polygon, optionally with alpha, without mutating the source."""
    if alpha >= 0.999:
        cv2.fillPoly(frame, [polygon], colour, cv2.LINE_AA)
        return
    overlay = frame.copy()
    cv2.fillPoly(overlay, [polygon], colour, cv2.LINE_AA)
    cv2.addWeighted(overlay, alpha, frame, 1.0 - alpha, 0, dst=frame)


def _glow(
    frame: np.ndarray, mask: np.ndarray, colour: BGR, radius: float = 12.0, gain: float = 1.7
) -> np.ndarray:
    """Add a colour bloom around a binary mask."""
    blurred = cv2.GaussianBlur(mask.astype(np.float32) / 255.0, (0, 0), radius)
    layer = np.zeros_like(frame, dtype=np.float32)
    for channel in range(3):
        layer[..., channel] = blurred * colour[channel] * gain
    return np.clip(frame.astype(np.float32) + layer, 0, 255).astype(np.uint8)


# --------------------------------------------------------------------------- #
# Face effects
# --------------------------------------------------------------------------- #
class SunglassesEffect(FaceEffect):
    name = "sunglasses"
    label = "Sunglasses"
    label_es = "Gafas de sol"
    emoji = "🕶️"
    description = "Wayfarers locked to the eye line — tilt your head and they follow."
    description_es = "Gafas ancladas a la línea de los ojos: siguen el movimiento de tu cabeza."

    def __init__(self, colour: BGR = (28, 24, 22), reflect: bool = True) -> None:
        self.colour = colour
        self.reflect = reflect

    def apply(self, frame: np.ndarray, face: FaceObservation, ctx: EffectContext) -> np.ndarray:
        if face.count < 300:
            return frame
        centre, interocular, roll = _face_frame(face, ctx.width, ctx.height)
        lens_w = interocular * 0.62
        lens_h = interocular * 0.46
        interocular * 0.10

        left_centre = (int(centre[0] - interocular / 2 - lens_w * 0.05), centre[1])
        right_centre = (int(centre[0] + interocular / 2 + lens_w * 0.05), centre[1])

        for lens_centre in (left_centre, right_centre):
            pts = _ellipse_pts(lens_centre, (int(lens_w), int(lens_h)))
            pts = _rotate(pts, centre, roll)
            _blend_poly(frame, pts, self.colour, 0.92)
            cv2.polylines(frame, [pts], True, (12, 12, 14), max(1, int(interocular * 0.035)), cv2.LINE_AA)

        # Bridge + temples.
        bridge = np.array(
            [
                [left_centre[0] + int(lens_w * 0.8), centre[1] - int(lens_h * 0.25)],
                [right_centre[0] - int(lens_w * 0.8), centre[1] - int(lens_h * 0.25)],
                [right_centre[0] - int(lens_w * 0.8), centre[1] + int(lens_h * 0.25)],
                [left_centre[0] + int(lens_w * 0.8), centre[1] + int(lens_h * 0.25)],
            ],
            dtype=np.int32,
        )
        _blend_poly(frame, _rotate(bridge, centre, roll), self.colour, 0.95)

        for _side, sign in (("l", -1), ("r", 1)):
            temple = np.array(
                [
                    [centre[0] + sign * int(interocular * 0.95), centre[1] - int(lens_h * 0.3)],
                    [centre[0] + sign * int(interocular * 1.35), centre[1] - int(lens_h * 0.55)],
                    [centre[0] + sign * int(interocular * 1.35), centre[1] - int(lens_h * 0.25)],
                    [centre[0] + sign * int(interocular * 0.95), centre[1] + int(lens_h * 0.05)],
                ],
                dtype=np.int32,
            )
            _blend_poly(frame, _rotate(temple, centre, roll), self.colour, 0.95)

        if self.reflect:
            # A single diagonal streak per lens sells the glass.
            for lens_centre in (left_centre, right_centre):
                streak = np.array(
                    [
                        [lens_centre[0] - int(lens_w * 0.5), lens_centre[1] + int(lens_h * 0.35)],
                        [lens_centre[0] - int(lens_w * 0.1), lens_centre[1] - int(lens_h * 0.55)],
                        [lens_centre[0] + int(lens_w * 0.05), lens_centre[1] - int(lens_h * 0.45)],
                        [lens_centre[0] - int(lens_w * 0.35), lens_centre[1] + int(lens_h * 0.45)],
                    ],
                    dtype=np.int32,
                )
                _blend_poly(frame, _rotate(streak, centre, roll), (190, 195, 200), 0.35)
        return frame


class LaserEyesEffect(FaceEffect):
    name = "laser_eyes"
    label = "Laser eyes"
    label_es = "Rayos láser"
    emoji = "🔴"
    description = "Twin beams from your irises, with an animated flicker."
    description_es = "Dos rayos saliendo de tus pupilas, con parpadeo animado."

    def __init__(self, colour: BGR = (60, 60, 255)) -> None:
        self.colour = colour

    def apply(self, frame: np.ndarray, face: FaceObservation, ctx: EffectContext) -> np.ndarray:
        if face.count < 400:
            return frame
        flicker = 0.75 + 0.25 * math.sin(ctx.time * 22.0)
        for iris_index, brow_index in ((RIGHT_IRIS, RIGHT_EYE_OUTER), (LEFT_IRIS, LEFT_EYE_OUTER)):
            if iris_index >= face.count:
                continue
            origin = _px(face.point(iris_index), ctx.width, ctx.height)
            anchor = _px(face.point(brow_index), ctx.width, ctx.height)
            direction = np.array([origin[0] - anchor[0], origin[1] - anchor[1]], dtype=np.float64)
            norm = float(np.linalg.norm(direction)) or 1.0
            direction /= norm
            end = (int(origin[0] + direction[0] * ctx.width), int(origin[1] + direction[1] * ctx.height))

            beam_radius = max(3, int(ctx.height * 0.012))
            cv2.line(frame, origin, end, self.colour, beam_radius * 2, cv2.LINE_AA)
            cv2.line(frame, origin, end, (255, 255, 255), max(1, beam_radius // 2), cv2.LINE_AA)

        mask = np.zeros(frame.shape[:2], dtype=np.uint8)
        for iris_index in (RIGHT_IRIS, LEFT_IRIS):
            if iris_index < face.count:
                cv2.circle(
                    mask,
                    _px(face.point(iris_index), ctx.width, ctx.height),
                    max(3, int(ctx.height * 0.02)),
                    255,
                    -1,
                )
        cv2.addWeighted(
            _glow(frame, mask, self.colour, radius=18.0, gain=flicker * 2.2), 1.0, frame, 0.0, 0, dst=frame
        )
        return frame


class DogEffect(FaceEffect):
    name = "dog"
    label = "Puppy"
    label_es = "Perrito"
    emoji = "🐶"
    description = "Flappy ears, a boopable nose and a tongue that tracks your jaw."
    description_es = "Orejas, nariz y una lengua que sigue tu mandíbula."

    def apply(self, frame: np.ndarray, face: FaceObservation, ctx: EffectContext) -> np.ndarray:
        if face.count < 400:
            return frame
        width, height = ctx.width, ctx.height
        centre, interocular, roll = _face_frame(face, width, height)
        ear_len = interocular * 1.15
        ear_w = interocular * 0.52
        wobble = math.sin(ctx.time * 3.4) * interocular * 0.10

        # Ears hang from the upper corners of the skull.
        for sign in (-1, 1):
            base = (centre[0] + sign * int(interocular * 0.62), centre[1] - int(interocular * 0.30))
            ear = np.array(
                [
                    [base[0], base[1]],
                    [base[0] + sign * int(ear_w), base[1] + int(ear_len * 0.35)],
                    [base[0] + sign * int(ear_w * 1.15 + wobble), base[1] + int(ear_len)],
                    [base[0] + sign * int(ear_w * 0.25), base[1] + int(ear_len * 0.85)],
                ],
                dtype=np.int32,
            )
            _blend_poly(frame, _rotate(ear, centre, roll), (48, 42, 38), 0.94)
            inner = np.array(
                [
                    [base[0] + sign * int(ear_w * 0.2), base[1] + int(ear_len * 0.25)],
                    [base[0] + sign * int(ear_w * 0.8), base[1] + int(ear_len * 0.45)],
                    [base[0] + sign * int(ear_w * 0.75), base[1] + int(ear_len * 0.85)],
                    [base[0] + sign * int(ear_w * 0.3), base[1] + int(ear_len * 0.7)],
                ],
                dtype=np.int32,
            )
            _blend_poly(frame, _rotate(inner, centre, roll), (150, 120, 165), 0.55)

        # Nose sits on the nose tip landmark.
        nose = _px(face.point(NOSE_TIP), width, height)
        nose_axes = (int(interocular * 0.24), int(interocular * 0.18))
        nose_pts = _rotate(_ellipse_pts(nose, nose_axes), centre, roll)
        _blend_poly(frame, nose_pts, (26, 22, 24), 0.96)
        highlight = _rotate(
            _ellipse_pts(
                (nose[0] - nose_axes[0] // 3, nose[1] - nose_axes[1] // 3),
                (max(1, nose_axes[0] // 4), max(1, nose_axes[1] // 4)),
                16,
            ),
            centre,
            roll,
        )
        _blend_poly(frame, highlight, (140, 150, 160), 0.5)

        # Tongue length follows jawOpen — the expression drives the effect.
        jaw_open = face.blend("jawOpen", 0.0)
        if jaw_open > 0.06:
            mouth = _px(face.point(LOWER_LIP), width, height)
            length = int(interocular * (0.45 + jaw_open * 1.3))
            tongue_w = int(interocular * 0.30)
            tongue = np.array(
                [
                    [mouth[0] - tongue_w // 2, mouth[1] - int(interocular * 0.05)],
                    [mouth[0] + tongue_w // 2, mouth[1] - int(interocular * 0.05)],
                    [mouth[0] + tongue_w // 2, mouth[1] + length],
                    [mouth[0] - tongue_w // 2, mouth[1] + length],
                ],
                dtype=np.int32,
            )
            _blend_poly(frame, _rotate(tongue, centre, roll), (120, 90, 225), 0.95)
            tip = _rotate(
                _ellipse_pts((mouth[0], mouth[1] + length), (tongue_w // 2, tongue_w // 3), 20),
                centre,
                roll,
            )
            _blend_poly(frame, tip, (120, 90, 225), 0.95)
        return frame


class CrownEffect(FaceEffect):
    name = "crown"
    label = "Crown"
    label_es = "Corona"
    emoji = "👑"
    description = "A gold crown, because you are the main character."
    description_es = "Una corona dorada: eres el protagonista."

    def apply(self, frame: np.ndarray, face: FaceObservation, ctx: EffectContext) -> np.ndarray:
        if face.count < 300:
            return frame
        centre, interocular, roll = _face_frame(face, ctx.width, ctx.height)
        base_y = centre[1] - int(interocular * 1.05)
        half = int(interocular * 0.72)
        height = int(interocular * 0.72)
        spikes = 5
        points: List[List[int]] = [[centre[0] - half, base_y + height // 3]]
        for index in range(spikes):
            x_left = centre[0] - half + int((2 * half) * index / spikes)
            x_mid = centre[0] - half + int((2 * half) * (index + 0.5) / spikes)
            x_right = centre[0] - half + int((2 * half) * (index + 1) / spikes)
            points.append([x_left, base_y + height // 3])
            points.append([x_mid, base_y])
            points.append([x_right, base_y + height // 3])
        points.append([centre[0] + half, base_y + height // 3])
        points.append([centre[0] + half, base_y + height])
        points.append([centre[0] - half, base_y + height])
        crown = _rotate(np.array(points, dtype=np.int32), centre, roll)
        _blend_poly(frame, crown, (40, 190, 245), 0.95)
        cv2.polylines(frame, [crown], True, (25, 120, 180), max(1, int(interocular * 0.05)), cv2.LINE_AA)
        # Jewels.
        for index in range(1, spikes):
            x = centre[0] - half + int((2 * half) * index / spikes)
            jewel = _rotate(
                _ellipse_pts(
                    (x, base_y + int(height * 0.75)),
                    (max(2, int(interocular * 0.07)), max(2, int(interocular * 0.07))),
                    14,
                ),
                centre,
                roll,
            )
            _blend_poly(frame, jewel, (90, 60, 235), 0.9)
        return frame


class HaloEffect(FaceEffect):
    name = "halo"
    label = "Halo"
    label_es = "Aureola"
    emoji = "😇"
    description = "A floating ring of light that bobs above your head."
    description_es = "Un anillo de luz que flota sobre tu cabeza."

    def apply(self, frame: np.ndarray, face: FaceObservation, ctx: EffectContext) -> np.ndarray:
        if face.count < 300:
            return frame
        centre, interocular, roll = _face_frame(face, ctx.width, ctx.height)
        bob = math.sin(ctx.time * 1.8) * interocular * 0.08
        halo_centre = (centre[0], int(centre[1] - interocular * 1.25 + bob))
        axes = (int(interocular * 0.85), int(interocular * 0.22))
        ring = _rotate(_ellipse_pts(halo_centre, axes, 60), centre, roll)
        cv2.polylines(frame, [ring], True, (120, 235, 255), max(3, int(interocular * 0.11)), cv2.LINE_AA)
        cv2.polylines(frame, [ring], True, (255, 255, 255), max(1, int(interocular * 0.04)), cv2.LINE_AA)
        mask = np.zeros(frame.shape[:2], dtype=np.uint8)
        cv2.polylines(mask, [ring], True, 255, max(4, int(interocular * 0.14)), cv2.LINE_AA)
        return _glow(frame, mask, (120, 235, 255), radius=16.0, gain=1.5)


class MustacheEffect(FaceEffect):
    name = "mustache"
    label = "Mustache"
    label_es = "Bigote"
    emoji = "🥸"
    description = "A handlebar mustache anchored to your upper lip."
    description_es = "Un bigote anclado a tu labio superior."

    def apply(self, frame: np.ndarray, face: FaceObservation, ctx: EffectContext) -> np.ndarray:
        if face.count < 400:
            return frame
        centre, interocular, roll = _face_frame(face, ctx.width, ctx.height)
        lip = _px(face.point(UPPER_LIP), ctx.width, ctx.height)
        width = int(interocular * 0.62)
        height = int(interocular * 0.24)
        pts = np.array(
            [
                [lip[0] - width, lip[1] - int(height * 0.15)],
                [lip[0] - width // 2, lip[1] - height],
                [lip[0], lip[1] - int(height * 0.35)],
                [lip[0] + width // 2, lip[1] - height],
                [lip[0] + width, lip[1] - int(height * 0.15)],
                [lip[0] + width // 2, lip[1] + int(height * 0.55)],
                [lip[0], lip[1] + int(height * 0.25)],
                [lip[0] - width // 2, lip[1] + int(height * 0.55)],
            ],
            dtype=np.int32,
        )
        _blend_poly(frame, _rotate(pts, centre, roll), (32, 28, 30), 0.95)
        return frame


class BlushEffect(FaceEffect):
    name = "blush"
    label = "Blush"
    label_es = "Rubor"
    emoji = "😊"
    description = "Soft rosy cheeks that intensify when you smile."
    description_es = "Mejillas sonrosadas que se intensifican al sonreír."

    def apply(self, frame: np.ndarray, face: FaceObservation, ctx: EffectContext) -> np.ndarray:
        if face.count < 400:
            return frame
        smile = face.pair("mouthSmileLeft", "mouthSmileRight")
        alpha = 0.25 + 0.35 * smile
        width, height = ctx.width, ctx.height
        _centre, interocular, roll = _face_frame(face, width, height)
        layer = np.zeros_like(frame)
        axes = (int(interocular * 0.42), int(interocular * 0.28))
        for index in (RIGHT_CHEEK, LEFT_CHEEK):
            cheek = _px(face.point(index), width, height)
            cheek = (cheek[0], cheek[1] - int(interocular * 0.12))
            cv2.ellipse(layer, cheek, axes, roll, 0, 360, (120, 90, 245), -1, cv2.LINE_AA)
        layer = cv2.GaussianBlur(layer, (0, 0), max(6.0, interocular * 0.16))
        return cv2.addWeighted(frame, 1.0, layer, alpha, 0)


class PixelVisorEffect(FaceEffect):
    name = "visor"
    label = "Cyber visor"
    label_es = "Visor cyber"
    emoji = "🤖"
    description = "A scanning HUD bar across your eyes, with a live readout."
    description_es = "Una barra HUD que escanea tus ojos, con lectura en vivo."

    def apply(self, frame: np.ndarray, face: FaceObservation, ctx: EffectContext) -> np.ndarray:
        if face.count < 300:
            return frame
        width, height = ctx.width, ctx.height
        centre, interocular, roll = _face_frame(face, width, height)
        bar_h = int(interocular * 0.42)
        bar_w = int(interocular * 1.9)
        pts = np.array(
            [
                [centre[0] - bar_w // 2, centre[1] - bar_h // 2],
                [centre[0] + bar_w // 2, centre[1] - bar_h // 2],
                [centre[0] + bar_w // 2, centre[1] + bar_h // 2],
                [centre[0] - bar_w // 2, centre[1] + bar_h // 2],
            ],
            dtype=np.int32,
        )
        rotated = _rotate(pts, centre, roll)
        _blend_poly(frame, rotated, (10, 18, 22), 0.88)
        cv2.polylines(frame, [rotated], True, (230, 220, 60), max(1, int(interocular * 0.05)), cv2.LINE_AA)

        # Scrolling tick marks + a travelling scan line.
        scan_y = centre[1] - bar_h // 2 + int((math.sin(ctx.time * 2.2) * 0.5 + 0.5) * bar_h)
        cv2.line(
            frame,
            (centre[0] - bar_w // 2 + 6, scan_y),
            (centre[0] + bar_w // 2 - 6, scan_y),
            (60, 240, 250),
            max(1, int(interocular * 0.04)),
            cv2.LINE_AA,
        )
        for index in range(9):
            x = centre[0] - bar_w // 2 + int(bar_w * (index + 0.5) / 9)
            tick_h = int(bar_h * (0.18 + 0.14 * (index % 3)))
            cv2.line(frame, (x, centre[1] - tick_h), (x, centre[1] + tick_h), (90, 220, 240), 1, cv2.LINE_AA)

        text = f"ID {ctx.frame_index % 9973:04d}  EXP {(face.pair('mouthSmileLeft','mouthSmileRight'))*100:03.0f}%"
        cv2.putText(
            frame,
            text,
            (centre[0] - bar_w // 2 + 8, centre[1] + bar_h // 2 + int(interocular * 0.28)),
            cv2.FONT_HERSHEY_PLAIN,
            max(0.8, interocular * 0.035),
            (90, 240, 250),
            1,
            cv2.LINE_AA,
        )
        return frame


class MaskEffect(FaceEffect):
    name = "mask"
    label = "Face mask"
    label_es = "Mascarilla"
    emoji = "😷"
    description = "A surgical mask fitted to your face oval."
    description_es = "Una mascarilla ajustada al óvalo de tu cara."

    def apply(self, frame: np.ndarray, face: FaceObservation, ctx: EffectContext) -> np.ndarray:
        if face.count < 400:
            return frame
        width, height = ctx.width, ctx.height
        nose = _px(face.point(NOSE_TIP), width, height)
        chin = _px(face.point(CHIN), width, height)
        right_cheek = _px(face.point(RIGHT_CHEEK), width, height)
        left_cheek = _px(face.point(LEFT_CHEEK), width, height)

        top_y = nose[1] - int((chin[1] - nose[1]) * 0.45)
        bottom_y = chin[1] + int((chin[1] - nose[1]) * 0.18)
        mask = np.array(
            [
                [right_cheek[0] + int((left_cheek[0] - right_cheek[0]) * 0.06), top_y],
                [left_cheek[0] - int((left_cheek[0] - right_cheek[0]) * 0.06), top_y],
                [left_cheek[0] + int((left_cheek[0] - right_cheek[0]) * 0.02), (top_y + bottom_y) // 2],
                [int((left_cheek[0] + right_cheek[0]) / 2), bottom_y],
                [right_cheek[0] - int((left_cheek[0] - right_cheek[0]) * 0.02), (top_y + bottom_y) // 2],
            ],
            dtype=np.int32,
        )
        _blend_poly(frame, mask, (215, 220, 228), 0.93)
        cv2.polylines(frame, [mask], True, (170, 175, 185), 2, cv2.LINE_AA)
        # Pleats.
        span = bottom_y - top_y
        for index in range(1, 4):
            y = top_y + int(span * index / 4)
            cv2.line(frame, (right_cheek[0], y), (left_cheek[0], y), (190, 195, 205), 1, cv2.LINE_AA)
        # Ear loops.
        span_x = left_cheek[0] - right_cheek[0]
        cv2.ellipse(
            frame,
            (right_cheek[0] - int(span_x * 0.05), top_y + span // 3),
            (max(3, span_x // 12), max(4, span // 2)),
            0,
            300,
            60,
            (150, 155, 165),
            2,
            cv2.LINE_AA,
        )
        cv2.ellipse(
            frame,
            (left_cheek[0] + int(span_x * 0.05), top_y + span // 3),
            (max(3, span_x // 12), max(4, span // 2)),
            0,
            120,
            240,
            (150, 155, 165),
            2,
            cv2.LINE_AA,
        )
        return frame


class BigEyesEffect(FaceEffect):
    name = "big_eyes"
    label = "Big eyes"
    label_es = "Ojos grandes"
    emoji = "👀"
    description = "Local lens warp that enlarges both eyes — anime mode."
    description_es = "Deformación local que agranda los ojos, modo anime."

    def __init__(self, strength: float = 0.45) -> None:
        self.strength = float(strength)

    def apply(self, frame: np.ndarray, face: FaceObservation, ctx: EffectContext) -> np.ndarray:
        if face.count < 400:
            return frame
        width, height = ctx.width, ctx.height
        map_x, map_y = np.meshgrid(np.arange(width, dtype=np.float32), np.arange(height, dtype=np.float32))
        eye_radius = max(
            8.0, distance(face.point(RIGHT_EYE_OUTER), face.point(LEFT_EYE_OUTER)) * width * 0.42
        )

        for index in (RIGHT_IRIS, LEFT_IRIS):
            if index >= face.count:
                continue
            cx, cy = face.point(index) * np.array([width, height])
            dx = map_x - cx
            dy = map_y - cy
            dist = np.sqrt(dx * dx + dy * dy) + 1e-6
            influence = np.clip(1.0 - dist / eye_radius, 0.0, 1.0) ** 2
            scale = 1.0 - self.strength * influence
            map_x = cx + dx * scale
            map_y = cy + dy * scale
        return cv2.remap(frame, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


class GooglyEyesEffect(FaceEffect):
    name = "googly"
    label = "Googly eyes"
    label_es = "Ojos locos"
    emoji = "🙃"
    description = "Two wobbling paper eyes stuck over yours."
    description_es = "Dos ojos de papel que se mueven sobre los tuyos."

    def __init__(self, colour: BGR = (245, 245, 245)) -> None:
        self.colour = colour

    def apply(self, frame: np.ndarray, face: FaceObservation, ctx: EffectContext) -> np.ndarray:
        if face.count < 300:
            return frame
        centre, interocular, roll = _face_frame(face, ctx.width, ctx.height)
        radius = max(6, int(interocular * 0.42))
        wobble_x = math.sin(ctx.time * 5.5) * radius * 0.22
        wobble_y = math.cos(ctx.time * 4.1) * radius * 0.22

        for sign in (-1, 1):
            eye_centre = (centre[0] + sign * int(interocular * 0.52), centre[1])
            white = _rotate(_ellipse_pts(eye_centre, (radius, radius), 28), centre, roll)
            _blend_poly(frame, white, self.colour, 0.97)
            cv2.polylines(frame, [white], True, (40, 40, 40), max(1, int(radius * 0.10)), cv2.LINE_AA)
            pupil_centre = (int(eye_centre[0] + wobble_x), int(eye_centre[1] + wobble_y))
            pupil = _rotate(
                _ellipse_pts(pupil_centre, (max(2, radius // 3), max(2, radius // 3)), 20), centre, roll
            )
            _blend_poly(frame, pupil, (20, 20, 24), 0.98)
        return frame


# --------------------------------------------------------------------------- #
# Hand effects
# --------------------------------------------------------------------------- #
class HandTrailEffect(HandEffect):
    name = "trails"
    label = "Finger trails"
    label_es = "Estelas"
    emoji = "🌈"
    description = "Glowing ribbons that follow your fingertips and fade out."
    description_es = "Cintas brillantes que siguen tus dedos y se desvanecen."

    TIPS = (4, 8, 12, 16, 20)
    COLOURS = ((90, 220, 250), (250, 180, 90), (120, 250, 160), (240, 120, 200), (200, 160, 250))

    def __init__(self, length: int = 18) -> None:
        self.length = max(4, int(length))

    def apply(self, frame: np.ndarray, hand: HandObservation, ctx: EffectContext) -> np.ndarray:
        trails = ctx.state.setdefault("trails", {})  # type: ignore[assignment]
        key = hand.handedness or "Unknown"
        history: List[np.ndarray] = trails.setdefault(key, [])  # type: ignore[union-attr]

        tips = np.array(
            [[hand.landmarks[i, 0], hand.landmarks[i, 1]] for i in self.TIPS],
            dtype=np.float64,
        )
        history.append(tips)
        while len(history) > self.length:
            history.pop(0)
        if len(history) < 2:
            return frame

        canvas = np.zeros_like(frame)
        for finger in range(tips.shape[0]):
            colour = self.COLOURS[finger % len(self.COLOURS)]
            points = [
                (int(history[i][finger, 0] * ctx.width), int(history[i][finger, 1] * ctx.height))
                for i in range(len(history))
            ]
            for index in range(1, len(points)):
                alpha = index / len(points)
                thickness = max(1, int(alpha * ctx.height * 0.012))
                cv2.line(canvas, points[index - 1], points[index], colour, thickness, cv2.LINE_AA)
            cv2.circle(canvas, points[-1], max(2, int(ctx.height * 0.008)), colour, -1, cv2.LINE_AA)

        glow = cv2.GaussianBlur(canvas, (0, 0), 7.0)
        return cv2.addWeighted(cv2.addWeighted(frame, 1.0, glow, 0.9, 0), 1.0, canvas, 0.75, 0)


class FireHandsEffect(HandEffect):
    name = "fire"
    label = "Fire hands"
    label_es = "Manos de fuego"
    emoji = "🔥"
    description = "Flames rising off every fingertip, brighter when you spread your hand."
    description_es = "Llamas saliendo de tus dedos, más intensas al abrir la mano."

    def apply(self, frame: np.ndarray, hand: HandObservation, ctx: EffectContext) -> np.ndarray:
        rng = np.random.default_rng(ctx.frame_index * 7919 + hash(hand.handedness) % 1000)
        scale = hand_scale(hand.landmarks) * ctx.height
        canvas = np.zeros_like(frame)

        for index in (4, 8, 12, 16, 20):
            tip = (int(hand.landmarks[index, 0] * ctx.width), int(hand.landmarks[index, 1] * ctx.height))
            particles = 26
            for _ in range(particles):
                rise = rng.uniform(0.0, 1.0) ** 1.6
                offset_x = rng.normal(0, scale * 0.22 * (1 - rise * 0.6))
                offset_y = -rise * scale * 1.5
                radius = max(1, int(scale * 0.16 * (1.0 - rise)))
                heat = 1.0 - rise
                colour = (int(40 * heat), int(140 * heat + 60), int(255 * heat))
                cv2.circle(
                    canvas,
                    (int(tip[0] + offset_x), int(tip[1] + offset_y)),
                    radius,
                    colour,
                    -1,
                    cv2.LINE_AA,
                )
        blur = cv2.GaussianBlur(canvas, (0, 0), max(3.0, scale * 0.09))
        return cv2.addWeighted(cv2.addWeighted(frame, 1.0, blur, 1.1, 0), 1.0, canvas, 0.85, 0)


class SparkleEffect(HandEffect):
    name = "sparkles"
    label = "Sparkles"
    label_es = "Destellos"
    emoji = "✨"
    description = "A four-point star twinkles at each fingertip."
    description_es = "Una estrella de cuatro puntas brilla en cada dedo."

    def apply(self, frame: np.ndarray, hand: HandObservation, ctx: EffectContext) -> np.ndarray:
        canvas = np.zeros_like(frame)
        for finger, index in enumerate((4, 8, 12, 16, 20)):
            phase = ctx.time * 6.0 + finger * 1.1
            size = (0.5 + 0.5 * math.sin(phase)) * ctx.height * 0.045 + 3
            x = int(hand.landmarks[index, 0] * ctx.width)
            y = int(hand.landmarks[index, 1] * ctx.height)
            colour = (150, 240, 255)
            cv2.line(canvas, (int(x - size), y), (int(x + size), y), colour, 2, cv2.LINE_AA)
            cv2.line(canvas, (x, int(y - size)), (x, int(y + size)), colour, 2, cv2.LINE_AA)
            cv2.circle(canvas, (x, y), max(2, int(size * 0.22)), (255, 255, 255), -1, cv2.LINE_AA)
        glow = cv2.GaussianBlur(canvas, (0, 0), 8.0)
        return cv2.addWeighted(cv2.addWeighted(frame, 1.0, glow, 1.0, 0), 1.0, canvas, 0.9, 0)


class HandSkeletonEffect(HandEffect):
    name = "skeleton"
    label = "Wireframe hand"
    label_es = "Mano wireframe"
    emoji = "🦾"
    description = "Draws the 21-point skeleton with joint dots and a bone glow."
    description_es = "Dibuja el esqueleto de 21 puntos con brillo en los huesos."

    def apply(self, frame: np.ndarray, hand: HandObservation, ctx: EffectContext) -> np.ndarray:
        from ..detectors.base import HAND_CONNECTIONS

        points = [
            (int(hand.landmarks[i, 0] * ctx.width), int(hand.landmarks[i, 1] * ctx.height))
            for i in range(min(21, hand.landmarks.shape[0]))
        ]
        colour = (250, 200, 80) if hand.is_right else (200, 250, 120)
        canvas = np.zeros_like(frame)
        for start, end in HAND_CONNECTIONS:
            if start < len(points) and end < len(points):
                cv2.line(canvas, points[start], points[end], colour, 3, cv2.LINE_AA)
        for index, point in enumerate(points):
            radius = 6 if index in (4, 8, 12, 16, 20) else 4
            cv2.circle(canvas, point, radius, (255, 255, 255), -1, cv2.LINE_AA)
            cv2.circle(canvas, point, radius + 2, colour, 1, cv2.LINE_AA)
        glow = cv2.GaussianBlur(canvas, (0, 0), 6.0)
        return cv2.addWeighted(cv2.addWeighted(frame, 1.0, glow, 0.8, 0), 1.0, canvas, 0.9, 0)


# Register everything.
for _effect in (
    SunglassesEffect(),
    LaserEyesEffect(),
    DogEffect(),
    CrownEffect(),
    HaloEffect(),
    MustacheEffect(),
    BlushEffect(),
    PixelVisorEffect(),
    MaskEffect(),
    BigEyesEffect(),
    GooglyEyesEffect(),
):
    register_face_effect(_effect)

for _effect in (  # type: ignore[assignment]
    HandTrailEffect(),
    FireHandsEffect(),
    SparkleEffect(),
    HandSkeletonEffect(),
):
    register_hand_effect(_effect)


def build_effects(names: Sequence[str]) -> List[FaceEffect]:
    """Resolve face-effect names, warning about anything unknown."""
    resolved: List[FaceEffect] = []
    for name in names:
        key = (name or "").strip().lower().replace("-", "_").replace(" ", "_")
        effect = FACE_EFFECTS.get(key)
        if effect is None:
            if key in HAND_EFFECTS:
                continue
            log.warning("Unknown face effect %r — ignoring.", name)
            continue
        resolved.append(type(effect)())
    return resolved


def build_hand_effects(names: Sequence[str]) -> List[HandEffect]:
    """Resolve hand-effect names, warning about anything unknown."""
    resolved: List[HandEffect] = []
    for name in names:
        key = (name or "").strip().lower().replace("-", "_").replace(" ", "_")
        effect = HAND_EFFECTS.get(key)
        if effect is None:
            if key in FACE_EFFECTS:
                continue
            log.warning("Unknown hand effect %r — ignoring.", name)
            continue
        resolved.append(type(effect)())
    return resolved
