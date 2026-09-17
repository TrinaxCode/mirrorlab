"""Detector result types shared by every backend.

MirrorLab treats detector output as plain data: no backend-specific objects
leak past this module. That is what lets the same expression classifier,
gesture engine and overlay renderer run on top of MediaPipe Tasks, MediaPipe
Solutions, or a plain OpenCV fallback.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

__all__ = [
    "BLENDSHAPE_NAMES",
    "FACE_OVAL",
    "FACE_TESSELLATION_EDGES",
    "FINGER_NAMES",
    "HAND_CONNECTIONS",
    "FaceObservation",
    "FrameAnalysis",
    "HandObservation",
    "Landmark",
]

#: The 52 ARKit-style blendshape channels exposed by MediaPipe's FaceLandmarker.
BLENDSHAPE_NAMES: Tuple[str, ...] = (
    "_neutral",
    "browDownLeft",
    "browDownRight",
    "browInnerUp",
    "browOuterUpLeft",
    "browOuterUpRight",
    "cheekPuff",
    "cheekSquintLeft",
    "cheekSquintRight",
    "eyeBlinkLeft",
    "eyeBlinkRight",
    "eyeLookDownLeft",
    "eyeLookDownRight",
    "eyeLookInLeft",
    "eyeLookInRight",
    "eyeLookOutLeft",
    "eyeLookOutRight",
    "eyeLookUpLeft",
    "eyeLookUpRight",
    "eyeSquintLeft",
    "eyeSquintRight",
    "eyeWideLeft",
    "eyeWideRight",
    "jawForward",
    "jawLeft",
    "jawOpen",
    "jawRight",
    "mouthClose",
    "mouthDimpleLeft",
    "mouthDimpleRight",
    "mouthFrownLeft",
    "mouthFrownRight",
    "mouthFunnel",
    "mouthLeft",
    "mouthLowerDownLeft",
    "mouthLowerDownRight",
    "mouthPressLeft",
    "mouthPressRight",
    "mouthPucker",
    "mouthRight",
    "mouthRollLower",
    "mouthRollUpper",
    "mouthShrugLower",
    "mouthShrugUpper",
    "mouthSmileLeft",
    "mouthSmileRight",
    "mouthStretchLeft",
    "mouthStretchRight",
    "mouthUpperUpLeft",
    "mouthUpperUpRight",
    "noseSneerLeft",
    "noseSneerRight",
)

FINGER_NAMES: Tuple[str, ...] = ("thumb", "index", "middle", "ring", "pinky")

#: MediaPipe hand skeleton, as index pairs into the 21 hand landmarks.
HAND_CONNECTIONS: Tuple[Tuple[int, int], ...] = (
    (0, 1),
    (1, 2),
    (2, 3),
    (3, 4),  # thumb
    (0, 5),
    (5, 6),
    (6, 7),
    (7, 8),  # index
    (5, 9),
    (9, 10),
    (10, 11),
    (11, 12),  # middle
    (9, 13),
    (13, 14),
    (14, 15),
    (15, 16),  # ring
    (13, 17),
    (17, 18),
    (18, 19),
    (19, 20),  # pinky
    (0, 17),  # palm base
)

#: Coarse face outline (a subset of the 468-point mesh), used for cheap masks
#: and for drawing a friendly face silhouette instead of the full tessellation.
FACE_OVAL: Tuple[int, ...] = (
    10,
    338,
    297,
    332,
    284,
    251,
    389,
    356,
    454,
    323,
    361,
    288,
    397,
    365,
    379,
    378,
    400,
    377,
    152,
    148,
    176,
    149,
    150,
    136,
    172,
    58,
    132,
    93,
    234,
    127,
    162,
    21,
    54,
    103,
    67,
    109,
)

#: Tessellation edges for a lightweight, readable face mesh overlay.
FACE_TESSELLATION_EDGES: Tuple[Tuple[int, int], ...] = (
    *tuple((FACE_OVAL[i], FACE_OVAL[(i + 1) % len(FACE_OVAL)]) for i in range(len(FACE_OVAL))),
    (10, 152),
    (234, 454),
    (127, 356),
    (21, 251),
    (54, 284),
    (168, 6),
    (6, 197),
    (197, 195),
    (195, 5),
    (5, 4),
    (4, 1),
    (1, 19),
    (19, 94),
    (94, 2),
    (98, 97),
    (97, 2),
    (2, 326),
    (326, 327),
    (327, 294),
    (61, 13),
    (13, 291),
    (291, 14),
    (14, 17),
    (17, 61),
    (78, 308),
    (308, 415),
    (415, 310),
    (310, 311),
    (311, 312),
    (312, 13),
    (82, 312),
    (312, 13),
    (13, 311),
    (311, 310),
    (310, 415),
    (415, 308),
    (308, 324),
)


@dataclass(frozen=True)
class Landmark:
    """A single normalized landmark.

    Attributes:
        x, y: Normalized image coordinates in ``[0, 1]``.
        z: Relative depth (smaller = closer to the camera), same scale as ``x``.
        visibility: Present/confidence score when the model provides one.
    """

    x: float
    y: float
    z: float = 0.0
    visibility: float = 1.0

    def as_tuple(self) -> Tuple[float, float, float]:
        return (self.x, self.y, self.z)

    def to_pixel(self, width: int, height: int) -> Tuple[int, int]:
        return round(self.x * width), round(self.y * height)


@dataclass
class FaceObservation:
    """Everything MirrorLab knows about one detected face in one frame."""

    landmarks: np.ndarray  # (N, 3) normalized
    blendshapes: Dict[str, float] = field(default_factory=dict)
    transformation_matrix: Optional[np.ndarray] = None  # (4, 4) camera-space pose
    bbox: Optional[Tuple[float, float, float, float]] = None  # x_min, y_min, x_max, y_max
    confidence: float = 1.0

    @property
    def has_blendshapes(self) -> bool:
        return bool(self.blendshapes)

    @property
    def count(self) -> int:
        return int(self.landmarks.shape[0]) if self.landmarks is not None else 0

    def point(self, index: int) -> np.ndarray:
        """Landmark ``index`` as an ``(x, y)`` array (raises on bad index)."""
        return np.asarray(self.landmarks[index, :2], dtype=np.float64)

    def blend(self, name: str, default: float = 0.0) -> float:
        """Blendshape score by name, tolerating a missing channel."""
        return float(self.blendshapes.get(name, default))

    def pair(self, left: str, right: str) -> float:
        """Mean of a left/right blendshape pair — the usual way to read symmetry."""
        return (self.blend(left) + self.blend(right)) / 2.0

    def bbox_pixels(self, width: int, height: int, pad: float = 0.0) -> Tuple[int, int, int, int]:
        """Bounding box in pixels, optionally padded by a fraction of its size."""
        if self.landmarks is None or self.landmarks.size == 0:
            return (0, 0, 0, 0)
        xs, ys = self.landmarks[:, 0], self.landmarks[:, 1]
        x0, x1 = float(xs.min()), float(xs.max())
        y0, y1 = float(ys.min()), float(ys.max())
        pad_x, pad_y = (x1 - x0) * pad, (y1 - y0) * pad
        return (
            round((x0 - pad_x) * width),
            round((y0 - pad_y) * height),
            round((x1 + pad_x) * width),
            round((y1 + pad_y) * height),
        )


@dataclass
class HandObservation:
    """Everything MirrorLab knows about one detected hand in one frame."""

    landmarks: np.ndarray  # (21, 3) normalized image coordinates
    world_landmarks: Optional[np.ndarray] = None  # (21, 3) metric, wrist-centred
    handedness: str = "Unknown"  # "Left" | "Right" | "Unknown"
    score: float = 1.0
    gesture: str = ""  # filled in by the gesture classifier
    gesture_score: float = 0.0

    @property
    def is_right(self) -> bool:
        return self.handedness.lower().startswith("r")

    def point(self, index: int) -> np.ndarray:
        return np.asarray(self.landmarks[index, :2], dtype=np.float64)

    def bbox_pixels(self, width: int, height: int, pad: float = 0.0) -> Tuple[int, int, int, int]:
        if self.landmarks is None or self.landmarks.size == 0:
            return (0, 0, 0, 0)
        xs, ys = self.landmarks[:, 0], self.landmarks[:, 1]
        x0, x1 = float(xs.min()), float(xs.max())
        y0, y1 = float(ys.min()), float(ys.max())
        pad_x, pad_y = (x1 - x0) * pad, (y1 - y0) * pad
        return (
            round((x0 - pad_x) * width),
            round((y0 - pad_y) * height),
            round((x1 + pad_x) * width),
            round((y1 + pad_y) * height),
        )

    def count_extended(self, threshold: float = 0.55) -> int:
        """How many fingers are currently extended (uses ``Landmark.extended``)."""
        return sum(1 for finger in FINGER_NAMES if getattr(self, f"{finger}_extended", False))


@dataclass
class FrameAnalysis:
    """The complete per-frame detector output handed to filters and overlays."""

    faces: List[FaceObservation] = field(default_factory=list)
    hands: List[HandObservation] = field(default_factory=list)
    frame_index: int = 0
    timestamp_ms: int = 0
    inference_ms: float = 0.0
    backend: str = ""

    @property
    def primary_face(self) -> Optional[FaceObservation]:
        """The largest face, which is the one the HUD reports on."""
        if not self.faces:
            return None
        return max(self.faces, key=lambda f: _face_area(f))

    @property
    def primary_hand(self) -> Optional[HandObservation]:
        return self.hands[0] if self.hands else None

    @property
    def has_face(self) -> bool:
        return bool(self.faces)

    @property
    def has_hands(self) -> bool:
        return bool(self.hands)

    def hand_by_side(self, side: str) -> Optional[HandObservation]:
        """Return the hand whose handedness matches ``"left"`` or ``"right"``."""
        for hand in self.hands:
            if hand.handedness.lower().startswith(side[0].lower()):
                return hand
        return None


def _face_area(face: FaceObservation) -> float:
    if face.landmarks is None or face.landmarks.size == 0:
        return 0.0
    xs, ys = face.landmarks[:, 0], face.landmarks[:, 1]
    return float((xs.max() - xs.min()) * (ys.max() - ys.min()))
