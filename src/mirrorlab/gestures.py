"""Hand pose analysis and gesture recognition.

The classifier is **geometric and explainable**: it derives a
:class:`HandPose` (which fingers are extended, how much they curl, how far the
thumb is from the index tip, whether the palm faces the camera, how the hand is
rotated) and then matches that pose against declarative gesture definitions.

Why not a trained classifier? Because a rule-based engine:

* needs no extra model download and runs in microseconds on one CPU core;
* is invariant to hand size and distance, thanks to normalisation by
  :func:`~mirrorlab.utils.geometry.hand_scale`;
* can be extended by users with a handful of lines — see
  :data:`GESTURES` — which matters more for a playground than a 0.3 % accuracy
  gain on a benchmark nobody runs on their webcam.

Twenty-two static gestures and six dynamic ones ship out of the box.
"""

from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable, ClassVar, Deque, Dict, List, Optional, Sequence, Tuple

import numpy as np

from .utils.geometry import angle, clamp, distance, finger_curl, hand_scale
from .utils.logging import get_logger

if TYPE_CHECKING:  # pragma: no cover - avoids a circular import at runtime
    from .detectors.base import HandObservation

__all__ = [
    "FINGER_NAMES",
    "GESTURES",
    "GESTURE_ALIASES",
    "DynamicGesture",
    "FingerState",
    "GestureDefinition",
    "GestureMatch",
    "GestureTracker",
    "HandPose",
    "analyze_hand",
    "classify_gesture",
    "classify_hands",
    "gesture_catalog",
    "gesture_display",
    "resolve_gesture_name",
]

log = get_logger("gestures")

#: Canonical finger order, thumb first. Defined here (not imported from the
#: detector layer) so this module stays dependency-free and importable on its
#: own — which is what keeps the expression/gesture logic unit-testable without
#: MediaPipe installed.
FINGER_NAMES: Tuple[str, ...] = ("thumb", "index", "middle", "ring", "pinky")

# MediaPipe hand landmark indices.
WRIST = 0
THUMB_CMC, THUMB_MCP, THUMB_IP, THUMB_TIP = 1, 2, 3, 4
INDEX_MCP, INDEX_PIP, INDEX_DIP, INDEX_TIP = 5, 6, 7, 8
MIDDLE_MCP, MIDDLE_PIP, MIDDLE_DIP, MIDDLE_TIP = 9, 10, 11, 12
RING_MCP, RING_PIP, RING_DIP, RING_TIP = 13, 14, 15, 16
PINKY_MCP, PINKY_PIP, PINKY_DIP, PINKY_TIP = 17, 18, 19, 20

#: ``(mcp, pip, dip, tip)`` joint chains for the four long fingers.
FINGER_JOINTS: Dict[str, Tuple[int, int, int, int]] = {
    "index": (INDEX_MCP, INDEX_PIP, INDEX_DIP, INDEX_TIP),
    "middle": (MIDDLE_MCP, MIDDLE_PIP, MIDDLE_DIP, MIDDLE_TIP),
    "ring": (RING_MCP, RING_PIP, RING_DIP, RING_TIP),
    "pinky": (PINKY_MCP, PINKY_PIP, PINKY_DIP, PINKY_TIP),
}

#: A finger counts as extended below this curl score.
EXTENDED_CURL = 0.45
#: A finger counts as folded above this curl score.
FOLDED_CURL = 0.55


@dataclass
class FingerState:
    """Per-finger analysis result."""

    name: str
    extended: bool
    curl: float
    pip_angle: float
    tip: np.ndarray
    reach_ratio: float

    @property
    def folded(self) -> bool:
        return not self.extended


@dataclass
class HandPose:
    """A rich, backend-independent description of one hand's posture."""

    handedness: str
    fingers: Dict[str, FingerState]
    landmarks: np.ndarray
    scale: float
    center: np.ndarray
    pinch_ratio: float
    thumb_index_gap: float
    spread: float
    palm_facing_camera: bool
    rotation_deg: float
    fingers_together: float
    ok_ring_ratio: float
    source: Optional["HandObservation"] = None

    # -- finger queries ---------------------------------------------------- #
    def is_extended(self, finger: str) -> bool:
        state = self.fingers.get(finger)
        return bool(state and state.extended)

    def is_folded(self, finger: str) -> bool:
        state = self.fingers.get(finger)
        return bool(state and not state.extended)

    @property
    def extended_count(self) -> int:
        return sum(1 for state in self.fingers.values() if state.extended)

    @property
    def extended_names(self) -> List[str]:
        return [name for name in FINGER_NAMES if self.is_extended(name)]

    @property
    def folded_names(self) -> List[str]:
        return [name for name in FINGER_NAMES if self.is_folded(name)]

    @property
    def thumb_extended(self) -> bool:
        return self.is_extended("thumb")

    @property
    def pinch(self) -> bool:
        """True when the thumb and index tip are touching."""
        return self.pinch_ratio < 0.42

    def point(self, index: int) -> np.ndarray:
        return np.asarray(self.landmarks[index, :2], dtype=np.float64)

    def describe(self) -> str:
        parts = []
        for name in FINGER_NAMES:
            state = self.fingers[name]
            parts.append(f"{name[0].upper()}{'↑' if state.extended else '↓'}{state.curl:.2f}")
        return " ".join(parts)


@dataclass
class GestureDefinition:
    """Declarative gesture rule.

    Attributes:
        name: Canonical snake_case identifier used by the CLI and config.
        label: Human readable English label.
        label_es: Spanish label (MirrorLab ships bilingual UI text).
        emoji: Shown in the HUD and in the web demo.
        matcher: Maps a :class:`HandPose` to a confidence in ``[0, 1]``.
        threshold: Minimum confidence for the match to count.
        category: ``static``, ``count`` or ``symbol`` — used for HUD grouping.
        description: One-line explanation, surfaced by ``mirrorlab gestures``.
        action: Default action bound to the gesture for hands-free control.
    """

    name: str
    label: str
    label_es: str
    emoji: str
    matcher: Callable[[HandPose], float]
    threshold: float = 0.6
    category: str = "static"
    description: str = ""
    action: str = ""

    def match(self, pose: HandPose) -> float:
        try:
            return float(clamp(self.matcher(pose), 0.0, 1.0))
        except Exception:  # pragma: no cover - a broken custom rule must not crash the loop
            return 0.0


@dataclass
class GestureMatch:
    """The winning gesture plus the full score table."""

    name: str
    score: float
    definition: Optional[GestureDefinition]
    scores: Dict[str, float] = field(default_factory=dict)
    pose: Optional[HandPose] = None

    @property
    def label(self) -> str:
        return self.definition.label if self.definition else self.name

    @property
    def emoji(self) -> str:
        return self.definition.emoji if self.definition else "🖐️"

    @property
    def action(self) -> str:
        return self.definition.action if self.definition else ""

    def display(self, spanish: bool = True) -> str:
        """``"✌️ Victoria"`` — the label the HUD and toasts show."""
        if self.definition is None:
            return self.name
        return f"{self.definition.emoji} {self.definition.label_es if spanish else self.definition.label}"


# --------------------------------------------------------------------------- #
# Pose analysis
# --------------------------------------------------------------------------- #
def analyze_hand(hand: "HandObservation") -> HandPose:
    """Turn raw landmarks into a :class:`HandPose`.

    Every geometric quantity is normalised by :func:`hand_scale`, which is what
    makes the resulting thresholds work whether the hand is 40 cm or 1.5 m from
    the lens.
    """
    points = np.asarray(hand.landmarks, dtype=np.float64)
    # Some backends (and some malformed inputs) return fewer than 21 points.
    # Pad rather than raise: a degraded pose is far more useful than a crash in
    # the middle of a live video loop.
    if points.shape[0] < 21:
        padded = np.zeros((21, 3), dtype=np.float64)
        padded[: points.shape[0], : points.shape[1] if points.ndim > 1 else 1] = points
        points = padded
    scale = hand_scale(points)
    wrist = points[WRIST, :2]

    fingers: Dict[str, FingerState] = {}

    # --- four long fingers ------------------------------------------------ #
    for name, (mcp, pip, dip, tip) in FINGER_JOINTS.items():
        curl = finger_curl(points, mcp, pip, dip, tip)
        pip_angle = angle(points[mcp], points[pip], points[dip])
        reach = distance(wrist, points[tip, :2]) / scale
        baseline = distance(wrist, points[pip, :2]) / scale
        reach_ratio = reach / baseline if baseline > 1e-6 else 1.0
        extended = curl < EXTENDED_CURL and reach_ratio > 1.02
        fingers[name] = FingerState(
            name=name,
            extended=bool(extended),
            curl=curl,
            pip_angle=pip_angle,
            tip=points[tip, :2].copy(),
            reach_ratio=reach_ratio,
        )

    # --- thumb: its own geometry, since it folds across the palm ---------- #
    thumb_tip = points[THUMB_TIP, :2]
    thumb_ip = points[THUMB_IP, :2]
    thumb_mcp = points[THUMB_MCP, :2]
    pinky_mcp = points[PINKY_MCP, :2]
    index_mcp = points[INDEX_MCP, :2]

    # A tucked thumb sits close to the index MCP; an extended one swings away.
    thumb_away = distance(thumb_tip, index_mcp) / scale
    thumb_angle = angle(thumb_mcp, thumb_ip, thumb_tip)
    thumb_curl = clamp(
        0.6 * clamp((1.05 - thumb_away) / 0.7, 0.0, 1.0)
        + 0.4 * clamp((150.0 - thumb_angle) / 90.0, 0.0, 1.0),
        0.0,
        1.0,
    )
    thumb_extended = thumb_curl < 0.5 and thumb_away > 0.62
    fingers["thumb"] = FingerState(
        name="thumb",
        extended=bool(thumb_extended),
        curl=thumb_curl,
        pip_angle=thumb_angle,
        tip=thumb_tip.copy(),
        reach_ratio=thumb_away,
    )

    # --- aggregate features ----------------------------------------------- #
    thumb_index_gap = distance(thumb_tip, points[INDEX_TIP, :2]) / scale
    pinch_ratio = thumb_index_gap

    fingertips = np.array([fingers[f].tip for f in ("index", "middle", "ring", "pinky")])
    spread = _mean_pairwise_spread(fingertips) / scale

    middle_tip = points[MIDDLE_TIP, :2]
    ok_ring_ratio = distance(thumb_tip, middle_tip) / scale

    # Palm orientation: the sign of the 2-D cross product tells us which side
    # of the palm plane faces the camera.
    v1 = index_mcp - wrist
    v2 = pinky_mcp - wrist
    cross_z = float(v1[0] * v2[1] - v1[1] * v2[0])
    palm_facing = (cross_z < 0) if hand.is_right else (cross_z > 0)

    rotation = math.degrees(math.atan2(index_mcp[1] - pinky_mcp[1], index_mcp[0] - pinky_mcp[0]))
    fingers_together = _mean_adjacent_gap(fingertips) / scale

    return HandPose(
        handedness=hand.handedness,
        fingers=fingers,
        landmarks=points,
        scale=scale,
        center=np.asarray(points[:, :2].mean(axis=0)),
        pinch_ratio=pinch_ratio,
        thumb_index_gap=thumb_index_gap,
        spread=spread,
        palm_facing_camera=bool(palm_facing),
        rotation_deg=float(rotation),
        fingers_together=float(fingers_together),
        ok_ring_ratio=float(ok_ring_ratio),
        source=hand,
    )


def _mean_pairwise_spread(points: np.ndarray) -> float:
    if points.shape[0] < 2:
        return 0.0
    gaps = [
        float(np.linalg.norm(points[i] - points[j]))
        for i in range(points.shape[0])
        for j in range(i + 1, points.shape[0])
    ]
    return sum(gaps) / len(gaps)


def _mean_adjacent_gap(points: np.ndarray) -> float:
    if points.shape[0] < 2:
        return 0.0
    return float(np.mean([np.linalg.norm(points[i] - points[i + 1]) for i in range(points.shape[0] - 1)]))


# --------------------------------------------------------------------------- #
# Matchers
# --------------------------------------------------------------------------- #
def _pattern(extended: Sequence[str], folded: Sequence[str]):
    """Build a matcher that rewards exactly this extended/folded pattern."""

    def matcher(pose: HandPose) -> float:
        total = len(extended) + len(folded)
        if total == 0:
            return 0.0
        hits = sum(1 for name in extended if pose.is_extended(name))
        hits += sum(1 for name in folded if pose.is_folded(name))
        return hits / total

    return matcher


def _confidence(pose: HandPose, names: Sequence[str], wanted_extended: bool) -> float:
    """Average certainty of a finger-state constraint (used to sharpen scores)."""
    values = []
    for name in names:
        state = pose.fingers.get(name)
        if state is None:
            continue
        if wanted_extended:
            values.append(clamp((EXTENDED_CURL - state.curl) / EXTENDED_CURL, 0.0, 1.0))
        else:
            values.append(clamp((state.curl - FOLDED_CURL) / (1.0 - FOLDED_CURL), 0.0, 1.0))
    return sum(values) / len(values) if values else 0.0


def _match_ok(pose: HandPose) -> float:
    touch = clamp((0.55 - pose.pinch_ratio) / 0.30, 0.0, 1.0)
    others = (
        int(pose.is_extended("middle")) + int(pose.is_extended("ring")) + int(pose.is_extended("pinky"))
    ) / 3.0
    return 0.65 * touch + 0.35 * others


def _match_pinch(pose: HandPose) -> float:
    return clamp((0.45 - pose.pinch_ratio) / 0.28, 0.0, 1.0)


def _match_thumbs_up(pose: HandPose) -> float:
    if not pose.is_extended("thumb"):
        return 0.0
    folded = all(pose.is_folded(name) for name in ("index", "middle", "ring", "pinky"))
    if not folded:
        return 0.0
    # Thumb tip must sit clearly above (smaller y) the rest of the hand.
    thumb_y = pose.fingers["thumb"].tip[1]
    others_y = np.mean([pose.fingers[name].tip[1] for name in ("index", "middle", "ring", "pinky")])
    lift = clamp((others_y - thumb_y) / (0.9 * pose.scale), 0.0, 1.0)
    return 0.5 * _confidence(pose, ["index", "middle", "ring", "pinky"], False) + 0.5 * lift


def _match_thumbs_down(pose: HandPose) -> float:
    if not pose.is_extended("thumb"):
        return 0.0
    folded = all(pose.is_folded(name) for name in ("index", "middle", "ring", "pinky"))
    if not folded:
        return 0.0
    thumb_y = pose.fingers["thumb"].tip[1]
    others_y = np.mean([pose.fingers[name].tip[1] for name in ("index", "middle", "ring", "pinky")])
    drop = clamp((thumb_y - others_y) / (0.9 * pose.scale), 0.0, 1.0)
    return 0.5 * _confidence(pose, ["index", "middle", "ring", "pinky"], False) + 0.5 * drop


def _match_spock(pose: HandPose) -> float:
    if not all(pose.is_extended(name) for name in ("index", "middle", "ring", "pinky")):
        return 0.0
    if pose.is_extended("thumb"):
        return 0.0
    tips = pose.fingers
    inner_gap = distance(tips["index"].tip, tips["middle"].tip) / pose.scale
    outer_gap = distance(tips["ring"].tip, tips["pinky"].tip) / pose.scale
    middle_gap = distance(tips["middle"].tip, tips["ring"].tip) / pose.scale
    # Vulcan salute: the middle/ring gap is much wider than the other two.
    return clamp((middle_gap - max(inner_gap, outer_gap)) / 0.45, 0.0, 1.0)


def _match_claw(pose: HandPose) -> float:
    partial = [
        name
        for name in ("index", "middle", "ring", "pinky")
        if EXTENDED_CURL * 0.9 < pose.fingers[name].curl < 0.95
    ]
    return (len(partial) / 4.0) * 0.9 if len(partial) >= 3 else 0.0


def _match_gun(pose: HandPose) -> float:
    good = pose.is_extended("thumb") and pose.is_extended("index")
    folded = all(pose.is_folded(n) for n in ("middle", "ring", "pinky"))
    if not (good and folded):
        return 0.0
    return 0.6 + 0.4 * _confidence(pose, ["middle", "ring", "pinky"], False)


def _match_call_me(pose: HandPose) -> float:
    good = pose.is_extended("thumb") and pose.is_extended("pinky")
    folded = all(pose.is_folded(n) for n in ("index", "middle", "ring"))
    if not (good and folded):
        return 0.0
    return 0.6 + 0.4 * _confidence(pose, ["index", "middle", "ring"], False)


def _match_open_palm(pose: HandPose) -> float:
    if pose.extended_count < 5:
        return 0.0
    spread = clamp((pose.spread - 0.55) / 0.55, 0.0, 1.0)
    return 0.65 + 0.35 * spread


def _match_fist(pose: HandPose) -> float:
    if pose.extended_count > 0:
        return 0.0
    return 0.55 + 0.45 * _confidence(pose, list(FINGER_NAMES), False)


def _match_pinch_zoom(pose: HandPose) -> float:
    """Two-hand pinch is handled by the engine; single-hand pinch here."""
    return _match_pinch(pose)


GESTURES: Dict[str, GestureDefinition] = {}


def _register(definition: GestureDefinition) -> GestureDefinition:
    GESTURES[definition.name] = definition
    return definition


_register(
    GestureDefinition(
        "fist",
        "Fist",
        "Puño",
        "✊",
        _match_fist,
        0.55,
        "count",
        "All fingers folded — used as the 'stop / freeze' gesture.",
        action="freeze",
    )
)
_register(
    GestureDefinition(
        "open_palm",
        "Open palm",
        "Palma abierta",
        "🖐️",
        _match_open_palm,
        0.6,
        "count",
        "Five extended fingers — 'stop', or the reset gesture.",
        action="reset",
    )
)
_register(
    GestureDefinition(
        "pointing",
        "Pointing",
        "Señalando",
        "☝️",
        _pattern(["index"], ["thumb", "middle", "ring", "pinky"]),
        0.8,
        "count",
        "Index up, rest folded — the air-drawing cursor.",
        action="draw",
    )
)
_register(
    GestureDefinition(
        "peace",
        "Peace",
        "Victoria",
        "✌️",
        _pattern(["index", "middle"], ["thumb", "ring", "pinky"]),
        0.8,
        "count",
        "Index and middle up — cycles to the next filter.",
        action="next_filter",
    )
)
_register(
    GestureDefinition(
        "three",
        "Three",
        "Tres",
        "3️⃣",
        _pattern(["index", "middle", "ring"], ["pinky"]),
        0.8,
        "count",
        "Three fingers up.",
    )
)


def _match_four(pose: HandPose) -> float:
    """Index, middle, ring and pinky up *and the thumb tucked in*.

    The thumb constraint is a hard gate rather than a weighted term: a hand
    with all five fingers out is an open palm, and scoring it 4/5 would let
    "four" outrank "open_palm" — which is exactly the bug this prevents.
    """
    if not all(pose.is_extended(name) for name in ("index", "middle", "ring", "pinky")):
        return 0.0
    if pose.is_extended("thumb"):
        return 0.0
    return 0.7 + 0.3 * _confidence(pose, ["thumb"], False)


_register(
    GestureDefinition(
        "four",
        "Four",
        "Cuatro",
        "4️⃣",
        _match_four,
        0.72,
        "count",
        "Four fingers up, thumb folded.",
    )
)
_register(
    GestureDefinition(
        "thumbs_up",
        "Thumbs up",
        "Pulgar arriba",
        "👍",
        _match_thumbs_up,
        0.6,
        "symbol",
        "Thumb up, fist closed — confirms and saves a snapshot.",
        action="snapshot",
    )
)
_register(
    GestureDefinition(
        "thumbs_down",
        "Thumbs down",
        "Pulgar abajo",
        "👎",
        _match_thumbs_down,
        0.6,
        "symbol",
        "Thumb down, fist closed — deletes the last capture.",
        action="discard",
    )
)
_register(
    GestureDefinition(
        "ok",
        "OK sign",
        "Señal OK",
        "👌",
        _match_ok,
        0.62,
        "symbol",
        "Thumb and index tips touching, other fingers up.",
        action="toggle_hud",
    )
)
_register(
    GestureDefinition(
        "pinch",
        "Pinch",
        "Pellizco",
        "🤏",
        _match_pinch,
        0.6,
        "symbol",
        "Thumb and index close together — the precision control.",
        action="pinch",
    )
)
_register(
    GestureDefinition(
        "rock",
        "Rock",
        "Rock",
        "🤘",
        _pattern(["index", "pinky"], ["thumb", "middle", "ring"]),
        0.8,
        "symbol",
        "Index and pinky up — toggles the glitch filter.",
        action="toggle_glitch",
    )
)
_register(
    GestureDefinition(
        "call_me",
        "Call me",
        "Llamada",
        "🤙",
        _pattern(["thumb", "pinky"], ["index", "middle", "ring"]),
        0.7,
        "symbol",
        "Thumb and pinky up — 'hang loose'.",
    )
)
_register(
    GestureDefinition(
        "gun",
        "Gun",
        "Pistola",
        "🔫",
        _match_gun,
        0.68,
        "symbol",
        "Thumb and index out, rest folded.",
    )
)
_register(
    GestureDefinition(
        "ily",
        "I love you",
        "Te quiero",
        "🤟",
        _pattern(["thumb", "index", "pinky"], ["middle", "ring"]),
        0.72,
        "symbol",
        "ASL sign for 'I love you' — the love filter.",
        action="filter:love",
    )
)
_register(
    GestureDefinition(
        "spock",
        "Vulcan salute",
        "Saludo vulcano",
        "🖖",
        _match_spock,
        0.55,
        "symbol",
        "Live long and prosper.",
    )
)
_register(
    GestureDefinition(
        "claw",
        "Claw",
        "Garra",
        "🫳",
        _match_claw,
        0.6,
        "count",
        "Partially curled fingers — the 'grab' pose.",
    )
)


def _match_one(pose: HandPose) -> float:
    """Only the thumb out, held roughly **sideways**.

    Direction is what separates "one" from a thumbs-up/down, and both are the
    same finger pattern — so the vertical component has to be part of the rule.
    """
    if not pose.is_extended("thumb"):
        return 0.0
    if not all(pose.is_folded(name) for name in ("index", "middle", "ring", "pinky")):
        return 0.0
    thumb_root = pose.point(THUMB_MCP)
    thumb_tip = pose.fingers["thumb"].tip
    vertical = abs(float(thumb_tip[1]) - float(thumb_root[1])) / max(pose.scale, 1e-6)
    return 0.75 + 0.25 * (1.0 - clamp(vertical / 1.2, 0.0, 1.0))


_register(
    GestureDefinition(
        "one",
        "One",
        "Uno",
        "1️⃣",
        _match_one,
        0.75,
        "count",
        "Only the thumb out, held sideways.",
    )
)
_register(
    GestureDefinition(
        "six",
        "Six",
        "Seis",
        "6️⃣",
        _pattern(["thumb", "index"], ["middle", "ring", "pinky"]),
        0.72,
        "count",
        "Thumb and index out — also reads as 'L'.",
    )
)
_register(
    GestureDefinition(
        "seven",
        "Seven",
        "Siete",
        "7️⃣",
        _pattern(["thumb", "index", "middle"], ["ring", "pinky"]),
        0.72,
        "count",
        "Thumb, index and middle out.",
    )
)
_register(
    GestureDefinition(
        "eight",
        "Eight",
        "Ocho",
        "8️⃣",
        _pattern(["thumb", "index", "middle", "ring"], ["pinky"]),
        0.72,
        "count",
        "Four fingers plus thumb.",
    )
)
_register(
    GestureDefinition(
        "pinch_zoom",
        "Pinch zoom",
        "Zoom con pinza",
        "🔍",
        _match_pinch_zoom,
        0.6,
        "dynamic",
        "Distance between both hands' pinches drives zoom (two hands required).",
        action="zoom",
    )
)
_register(
    GestureDefinition(
        "none",
        "No gesture",
        "Sin gesto",
        "•",
        lambda pose: 0.0,
        2.0,
        "static",
        "No confident match — reported so the HUD can show 'searching…'.",
    )
)

#: Alternate spellings accepted from the CLI and config files.
GESTURE_ALIASES: Dict[str, str] = {
    "point": "pointing",
    "point_up": "pointing",
    "index": "pointing",
    "victory": "peace",
    "v": "peace",
    "two": "peace",
    "thumb_up": "thumbs_up",
    "thumbsup": "thumbs_up",
    "like": "thumbs_up",
    "thumb_down": "thumbs_down",
    "thumbsdown": "thumbs_down",
    "dislike": "thumbs_down",
    "okay": "ok",
    "perfect": "ok",
    "horns": "rock",
    "metal": "rock",
    "shaka": "call_me",
    "hang_loose": "call_me",
    "love": "ily",
    "i_love_you": "ily",
    "vulcan": "spock",
    "palm": "open_palm",
    "stop": "open_palm",
    "grab": "claw",
    "pinching": "pinch",
}


def resolve_gesture_name(name: str) -> str:
    """Map an alias to its canonical gesture name."""
    key = (name or "").strip().lower().replace("-", "_").replace(" ", "_")
    return GESTURE_ALIASES.get(key, key)


# --------------------------------------------------------------------------- #
# Classification
# --------------------------------------------------------------------------- #
def classify_gesture(hand: "HandObservation") -> GestureMatch:
    """Classify a single :class:`HandObservation` into a gesture.

    Returns the highest scoring definition above its threshold; when nothing
    clears the bar the result is ``none`` with ``score = 0``, so callers can
    distinguish "no hand" from "hand doing something unrecognised".
    """
    pose = analyze_hand(hand)
    scores: Dict[str, float] = {}
    best_name, best_score = "none", 0.0

    for name, definition in GESTURES.items():
        if name == "none":
            continue
        score = definition.match(pose)
        if score <= 0.0:
            continue
        scores[name] = score
        if score >= definition.threshold and score > best_score:
            best_name, best_score = name, score

    # Generic pinch must not shadow OK: OK requires the other fingers up.
    if best_name == "pinch" and scores.get("ok", 0.0) >= GESTURES["ok"].threshold:
        best_name, best_score = "ok", scores["ok"]

    return GestureMatch(
        name=best_name,
        score=best_score,
        definition=GESTURES.get(best_name),
        scores=dict(sorted(scores.items(), key=lambda kv: -kv[1])),
        pose=pose,
    )


def classify_hands(hands: Sequence["HandObservation"], annotate: bool = True) -> List[GestureMatch]:
    """Classify several hands, optionally writing the labels back onto them."""
    matches = [classify_gesture(hand) for hand in hands]
    if annotate:
        for hand, match in zip(hands, matches):
            hand.gesture = match.name
            hand.gesture_score = match.score
    return matches


def gesture_display(name: str, spanish: bool = True) -> str:
    """``"peace"`` → ``"✌️ Victoria"`` for HUD and CLI output."""
    definition = GESTURES.get(resolve_gesture_name(name))
    if definition is None:
        return name
    return f"{definition.emoji} {definition.label_es if spanish else definition.label}"


def gesture_catalog() -> List[dict]:
    """Machine-readable catalog — powers ``mirrorlab gestures`` and the website."""
    return [
        {
            "name": d.name,
            "label": d.label,
            "label_es": d.label_es,
            "emoji": d.emoji,
            "category": d.category,
            "threshold": d.threshold,
            "description": d.description,
            "action": d.action,
        }
        for d in GESTURES.values()
    ]


# --------------------------------------------------------------------------- #
# Dynamic gestures
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class DynamicGesture:
    """A recognised motion event."""

    name: str
    label: str
    label_es: str
    emoji: str
    strength: float
    timestamp: float

    def display(self, spanish: bool = True) -> str:
        return f"{self.emoji} {self.label_es if spanish else self.label}"


class GestureTracker:
    """Detects motion gestures from the trajectory of a hand's centre.

    Tracks a short history of ``(timestamp, x, y)`` in normalized coordinates
    and fires when a fast, directional displacement is followed by a stop —
    the classic swipe signature. Vertical and horizontal swipes use the
    dominant axis, so diagonal motion still resolves to one direction.
    """

    #: Motion gestures that are actually emitted. Declared here so the CLI, the
    #: website and the tests all read the same list — anything not reachable
    #: from :meth:`update` must not be advertised.
    SWIPES: ClassVar[Dict[str, Tuple[str, str, str]]] = {
        "swipe_left": ("Swipe left", "Deslizar izquierda", "⬅️"),
        "swipe_right": ("Swipe right", "Deslizar derecha", "➡️"),
        "swipe_up": ("Swipe up", "Deslizar arriba", "⬆️"),
        "swipe_down": ("Swipe down", "Deslizar abajo", "⬇️"),
        "circle": ("Circle", "Círculo", "🔄"),
        "wave": ("Wave", "Saludo", "👋"),
    }

    def __init__(
        self,
        history: int = 18,
        min_displacement: float = 0.16,
        max_duration: float = 0.65,
        cooldown: float = 0.8,
    ) -> None:
        self.min_displacement = float(min_displacement)
        self.max_duration = float(max_duration)
        self.cooldown = float(cooldown)
        self._history: Deque[Tuple[float, float, float]] = deque(maxlen=history)
        self._last_fire: Dict[str, float] = {}
        self._last_center: Optional[Tuple[float, float]] = None
        self._wave_flips: Deque[float] = deque(maxlen=8)

    def reset(self) -> None:
        self._history.clear()
        self._last_fire.clear()
        self._wave_flips.clear()
        self._last_center = None

    def update(
        self, center: Optional[Sequence[float]], timestamp: Optional[float] = None
    ) -> Optional[DynamicGesture]:
        """Feed a hand centre; returns a :class:`DynamicGesture` when one fires."""
        now = time.perf_counter() if timestamp is None else float(timestamp)
        if center is None:
            self._history.clear()
            self._last_center = None
            return None

        x, y = float(center[0]), float(center[1])
        self._history.append((now, x, y))
        previous = self._last_center
        self._last_center = (x, y)

        # --- wave: several horizontal direction flips in a short window ---- #
        if previous is not None:
            dx_step = x - previous[0]
            if abs(dx_step) > 0.012:
                self._wave_flips.append(math.copysign(1.0, dx_step))
        if len(self._wave_flips) >= 5:
            flips = sum(
                1 for i in range(1, len(self._wave_flips)) if self._wave_flips[i] != self._wave_flips[i - 1]
            )
            if flips >= 4 and self._ready("wave", now):
                self._last_fire["wave"] = now
                self._wave_flips.clear()
                return self._make("wave", min(1.0, flips / 5.0), now)

        # --- swipe: a fast, large, mostly-straight displacement ------------ #
        window = [sample for sample in self._history if now - sample[0] <= self.max_duration]
        if len(window) < 3:
            return None

        t0, x0, y0 = window[0]
        dx, dy = x - x0, y - y0
        duration = max(now - t0, 1e-3)
        if duration > self.max_duration:
            return None

        # Straightness: a curved path (a circle) has a large spread about the
        # chord, so we can separate the two cases with one number.
        path_length = 0.0
        max_deviation = 0.0
        chord = math.hypot(dx, dy)
        for i in range(1, len(window)):
            _, px, py = window[i]
            _, qx, qy = window[i - 1]
            path_length += math.hypot(px - qx, py - qy)
            if chord > 1e-6:
                deviation = abs((px - x0) * dy - (py - y0) * dx) / chord
                max_deviation = max(max_deviation, deviation)

        if chord < self.min_displacement:
            return None
        efficiency = chord / max(path_length, 1e-6)

        if efficiency < 0.6 and max_deviation > 0.06 and self._ready("circle", now):
            self._last_fire["circle"] = now
            return self._make("circle", clamp(efficiency, 0.0, 1.0), now)

        speed = chord / duration
        strength = clamp((speed - 0.25) / 1.4, 0.0, 1.0)
        if strength <= 0.0:
            return None

        if abs(dx) >= abs(dy):
            name = "swipe_right" if dx > 0 else "swipe_left"
        else:
            name = "swipe_down" if dy > 0 else "swipe_up"

        if not self._ready(name, now):
            return None
        self._last_fire[name] = now
        self._history.clear()
        return self._make(name, strength, now)

    def _ready(self, name: str, now: float) -> bool:
        return (now - self._last_fire.get(name, -1e9)) >= self.cooldown

    def _make(self, name: str, strength: float, now: float) -> DynamicGesture:
        label, label_es, emoji = self.SWIPES[name]
        return DynamicGesture(
            name=name,
            label=label,
            label_es=label_es,
            emoji=emoji,
            strength=float(strength),
            timestamp=now,
        )
