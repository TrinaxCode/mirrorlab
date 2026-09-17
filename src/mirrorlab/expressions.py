"""Facial expression recognition.

MirrorLab reads expressions from the **52 ARKit blendshapes** that MediaPipe's
FaceLandmarker produces. Blendshapes are muscle-activation coefficients — a
smile really is ``mouthSmileLeft`` rising — which makes classification far more
robust than hand-tuned ratios between landmarks.

When only the legacy Solutions backend is available (no blendshapes) the
classifier transparently falls back to a geometric estimator built from mouth
and eye aspect ratios, so the feature degrades instead of disappearing. The
active strategy is reported in :attr:`ExpressionResult.method`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable, ClassVar, Dict, List, Optional, Tuple

import numpy as np

from .utils.geometry import clamp, distance
from .utils.logging import get_logger
from .utils.smoothing import EmaFilter

if TYPE_CHECKING:  # pragma: no cover - avoids a circular import at runtime
    from .detectors.base import FaceObservation

__all__ = [
    "EXPRESSIONS",
    "EXPRESSION_ALIASES",
    "ExpressionClassifier",
    "ExpressionDefinition",
    "ExpressionResult",
    "expression_catalog",
    "expression_display",
]

log = get_logger("expressions")


@dataclass(frozen=True)
class ExpressionDefinition:
    """A recognisable facial expression."""

    name: str
    label: str
    label_es: str
    emoji: str
    category: str = "emotion"
    description: str = ""


EXPRESSIONS: Dict[str, ExpressionDefinition] = {}


def _register(
    name: str, label: str, label_es: str, emoji: str, category: str = "emotion", description: str = ""
) -> ExpressionDefinition:
    definition = ExpressionDefinition(name, label, label_es, emoji, category, description)
    EXPRESSIONS[name] = definition
    return definition


_register("neutral", "Neutral", "Neutral", "😐", "state", "Relaxed face, no strong muscle activation.")
_register("happy", "Happy", "Feliz", "😊", "emotion", "Genuine smile: mouth corners pulled up and back.")
_register("laugh", "Laughing", "Riendo", "😄", "emotion", "Wide smile plus an open jaw.")
_register("sad", "Sad", "Triste", "😢", "emotion", "Mouth corners down, inner brows raised.")
_register("angry", "Angry", "Enojo", "😠", "emotion", "Brows pulled down and together, lips pressed.")
_register("surprised", "Surprised", "Sorpresa", "😲", "emotion", "Jaw dropped and eyes wide open.")
_register("fear", "Fear", "Miedo", "😨", "emotion", "Brows raised and pulled together, eyes wide.")
_register("disgust", "Disgust", "Disgusto", "🤢", "emotion", "Nose wrinkled, upper lip raised.")
_register("contempt", "Contempt", "Desprecio", "😏", "emotion", "One-sided smirk.")
_register("kiss", "Kiss", "Beso", "😘", "gesture", "Lips pursed forward.")
_register("wink", "Wink", "Guiño", "😉", "gesture", "One eye closed, the other open.")
_register("blink", "Blink", "Parpadeo", "😑", "state", "Both eyes closed.")
_register("brow_raise", "Brow raise", "Cejas arriba", "🤨", "gesture", "Both eyebrows lifted.")
_register("squint", "Squint", "Entrecerrar ojos", "😑", "gesture", "Eyes narrowed, cheeks raised.")
_register("thinking", "Thinking", "Pensando", "🤔", "gesture", "Eyes up, lips pressed, brow furrowed.")
_register("yawn", "Yawn", "Bostezo", "🥱", "gesture", "Jaw wide open with squinted eyes.")
_register("puff", "Cheek puff", "Mejillas infladas", "😗", "gesture", "Cheeks inflated with air.")
_register("unknown", "Unknown", "Desconocido", "❔", "state", "No face, or no usable signal.")


EXPRESSION_ALIASES: Dict[str, str] = {
    "smile": "happy",
    "smiling": "happy",
    "feliz": "happy",
    "sonrisa": "happy",
    "laughing": "laugh",
    "sadness": "sad",
    "tristeza": "sad",
    "anger": "angry",
    "enojo": "angry",
    "surprise": "surprised",
    "sorpresa": "surprised",
    "winking": "wink",
    "guiño": "wink",
    "kissing": "kiss",
    "beso": "kiss",
    "neutral_face": "neutral",
}


def resolve_expression_name(name: str) -> str:
    key = (name or "").strip().lower().replace("-", "_").replace(" ", "_")
    return EXPRESSION_ALIASES.get(key, key)


def expression_display(name: str, spanish: bool = True) -> str:
    definition = EXPRESSIONS.get(resolve_expression_name(name))
    if definition is None:
        return name
    return f"{definition.emoji} {definition.label_es if spanish else definition.label}"


def expression_catalog() -> List[dict]:
    return [
        {
            "name": d.name,
            "label": d.label,
            "label_es": d.label_es,
            "emoji": d.emoji,
            "category": d.category,
            "description": d.description,
        }
        for d in EXPRESSIONS.values()
    ]


@dataclass
class ExpressionResult:
    """The classifier's verdict for one frame."""

    name: str = "unknown"
    score: float = 0.0
    scores: Dict[str, float] = field(default_factory=dict)
    method: str = "none"  # "blendshapes" | "geometry" | "none"
    blendshapes: Dict[str, float] = field(default_factory=dict)

    @property
    def definition(self) -> Optional[ExpressionDefinition]:
        return EXPRESSIONS.get(self.name)

    @property
    def emoji(self) -> str:
        definition = self.definition
        return definition.emoji if definition else "❔"

    @property
    def label(self) -> str:
        definition = self.definition
        return definition.label if definition else self.name

    @property
    def label_es(self) -> str:
        definition = self.definition
        return definition.label_es if definition else self.name

    def display(self, spanish: bool = True) -> str:
        return f"{self.emoji} {self.label_es if spanish else self.label}"

    def top(self, count: int = 3) -> List[Tuple[str, float]]:
        return sorted(self.scores.items(), key=lambda kv: -kv[1])[:count]


# --------------------------------------------------------------------------- #
# Blendshape helpers
# --------------------------------------------------------------------------- #
def _bs(blends: Dict[str, float], name: str) -> float:
    return float(blends.get(name, 0.0))


def _mean(blends: Dict[str, float], *names: str) -> float:
    values = [_bs(blends, n) for n in names]
    return sum(values) / len(values) if values else 0.0


def _pair(blends: Dict[str, float], base: str) -> float:
    return _mean(blends, f"{base}Left", f"{base}Right")


def _asymmetry(blends: Dict[str, float], base: str) -> float:
    return abs(_bs(blends, f"{base}Left") - _bs(blends, f"{base}Right"))


# --------------------------------------------------------------------------- #
# Blendshape scorers
# --------------------------------------------------------------------------- #
class _BlendshapeScorers:
    """Expression scorers that read the 52 MediaPipe blendshape channels."""

    @staticmethod
    def happy(b: Dict[str, float]) -> float:
        smile = _pair(b, "mouthSmile")
        dimple = _pair(b, "mouthDimple")
        return clamp(0.85 * smile + 0.15 * dimple)

    @staticmethod
    def laugh(b: Dict[str, float]) -> float:
        jaw = _bs(b, "jawOpen")
        smile = _pair(b, "mouthSmile")
        return clamp(smile * clamp(jaw / 0.35) * 0.9 + smile * 0.35 * clamp(jaw / 0.6))

    @staticmethod
    def sad(b: Dict[str, float]) -> float:
        frown = _pair(b, "mouthFrown")
        inner_brow = _bs(b, "browInnerUp")
        lower = _pair(b, "mouthLowerDown")
        return clamp(0.5 * frown + 0.3 * inner_brow + 0.2 * lower)

    @staticmethod
    def angry(b: Dict[str, float]) -> float:
        brow_down = _pair(b, "browDown")
        press = _pair(b, "mouthPress")
        sneer = _pair(b, "noseSneer")
        stretch = _pair(b, "mouthStretch")
        return clamp(0.45 * brow_down + 0.2 * press + 0.2 * sneer + 0.15 * stretch)

    @staticmethod
    def surprised(b: Dict[str, float]) -> float:
        jaw = _bs(b, "jawOpen")
        wide = _pair(b, "eyeWide")
        outer_brow = _pair(b, "browOuterUp")
        return clamp(0.5 * clamp(jaw / 0.45) + 0.3 * wide + 0.2 * outer_brow)

    @staticmethod
    def fear(b: Dict[str, float]) -> float:
        inner = _bs(b, "browInnerUp")
        wide = _pair(b, "eyeWide")
        stretch = _pair(b, "mouthStretch")
        return clamp(0.4 * inner + 0.35 * wide + 0.25 * stretch)

    @staticmethod
    def disgust(b: Dict[str, float]) -> float:
        sneer = _pair(b, "noseSneer")
        upper = _pair(b, "mouthUpperUp")
        return clamp(0.65 * sneer + 0.35 * upper)

    @staticmethod
    def contempt(b: Dict[str, float]) -> float:
        left = _bs(b, "mouthSmileLeft") + _bs(b, "mouthDimpleLeft")
        right = _bs(b, "mouthSmileRight") + _bs(b, "mouthDimpleRight")
        return clamp(abs(left - right) * 0.9)

    @staticmethod
    def kiss(b: Dict[str, float]) -> float:
        pucker = _bs(b, "mouthPucker")
        funnel = _bs(b, "mouthFunnel")
        return clamp(0.6 * pucker + 0.4 * funnel)

    @staticmethod
    def wink(b: Dict[str, float]) -> float:
        left, right = _bs(b, "eyeBlinkLeft"), _bs(b, "eyeBlinkRight")
        # A wink is *asymmetric*: one lid shut, the other clearly open. Getting
        # these the wrong way round makes every blink read as a wink.
        closed, open_ = max(left, right), min(left, right)
        if open_ > 0.45:
            return 0.0
        return clamp((closed - 0.4) / 0.5)

    @staticmethod
    def blink(b: Dict[str, float]) -> float:
        return clamp((min(_bs(b, "eyeBlinkLeft"), _bs(b, "eyeBlinkRight")) - 0.45) / 0.4)

    @staticmethod
    def brow_raise(b: Dict[str, float]) -> float:
        inner = _bs(b, "browInnerUp")
        outer = _pair(b, "browOuterUp")
        down = _pair(b, "browDown")
        return clamp((0.5 * inner + 0.5 * outer) - down)

    @staticmethod
    def squint(b: Dict[str, float]) -> float:
        squint = _pair(b, "eyeSquint")
        smile = _pair(b, "mouthSmile")
        return clamp(squint * (1.0 - 0.5 * smile))

    @staticmethod
    def thinking(b: Dict[str, float]) -> float:
        look_up = _pair(b, "eyeLookUp")
        press = _pair(b, "mouthPress")
        inner = _bs(b, "browInnerUp")
        return clamp(0.45 * look_up + 0.3 * press + 0.25 * inner)

    @staticmethod
    def yawn(b: Dict[str, float]) -> float:
        jaw = _bs(b, "jawOpen")
        squint = _pair(b, "eyeSquint")
        smile = _pair(b, "mouthSmile")
        return clamp(clamp((jaw - 0.55) / 0.35) * (0.5 + 0.5 * squint) * (1.0 - 0.6 * smile))

    @staticmethod
    def puff(b: Dict[str, float]) -> float:
        # `cheekPuff` is one of the few blendshapes with no Left/Right pair.
        return clamp(_bs(b, "cheekPuff") * 1.4)

    @staticmethod
    def neutral(b: Dict[str, float]) -> float:
        """Neutral is the *absence* of the expressive channels."""
        channels = (
            _pair(b, "mouthSmile"),
            _pair(b, "mouthFrown"),
            _pair(b, "browDown"),
            _bs(b, "browInnerUp"),
            _pair(b, "browOuterUp"),
            _bs(b, "jawOpen"),
            _pair(b, "eyeWide"),
            _pair(b, "eyeSquint"),
            _bs(b, "mouthPucker"),
            _pair(b, "noseSneer"),
            _bs(b, "cheekPuff"),
        )
        total = sum(channels)
        dominant = max(channels)
        # Two independent signals, whichever is more confident: the *sum* of
        # activity (many small movements) and the *peak* channel (one strong
        # movement). Using only the sum lets a single 0.5 smile still read as
        # 62 % neutral, which swallows genuine expressions.
        return clamp(min(1.0 - total / 2.6, 1.0 - dominant * 1.35))

    #: name -> scorer, in evaluation order.
    ALL: ClassVar[Dict[str, Callable[[Dict[str, float]], float]]] = {}


_BlendshapeScorers.ALL = {
    "happy": _BlendshapeScorers.happy,
    "laugh": _BlendshapeScorers.laugh,
    "sad": _BlendshapeScorers.sad,
    "angry": _BlendshapeScorers.angry,
    "surprised": _BlendshapeScorers.surprised,
    "fear": _BlendshapeScorers.fear,
    "disgust": _BlendshapeScorers.disgust,
    "contempt": _BlendshapeScorers.contempt,
    "kiss": _BlendshapeScorers.kiss,
    "wink": _BlendshapeScorers.wink,
    "blink": _BlendshapeScorers.blink,
    "brow_raise": _BlendshapeScorers.brow_raise,
    "squint": _BlendshapeScorers.squint,
    "thinking": _BlendshapeScorers.thinking,
    "yawn": _BlendshapeScorers.yawn,
    "puff": _BlendshapeScorers.puff,
    "neutral": _BlendshapeScorers.neutral,
}

#: Expressions that take precedence when scores are close, because they are
#: either rarer (and therefore more informative) or deliberately triggered.
_PRIORITY: Tuple[str, ...] = (
    "wink",
    "blink",
    "laugh",
    "yawn",
    "kiss",
    "puff",
    "disgust",
    "surprised",
    "angry",
    "sad",
    "fear",
    "contempt",
    "thinking",
    "squint",
    "brow_raise",
    "happy",
    "neutral",
)


# --------------------------------------------------------------------------- #
# Geometric fallback (no blendshapes available)
# --------------------------------------------------------------------------- #
_FALLBACK_ANCHORS = {
    "right_eye_outer": 33,
    "right_eye_inner": 133,
    "left_eye_inner": 362,
    "left_eye_outer": 263,
    "mouth_right": 61,
    "mouth_left": 291,
    "upper_lip": 13,
    "lower_lip": 14,
    "upper_lip_inner": 12,
    "lower_lip_inner": 15,
    "right_brow": 105,
    "left_brow": 334,
    "nose_tip": 1,
    "chin": 152,
    "forehead": 10,
}


def _geometric_scores(landmarks: np.ndarray) -> Dict[str, float]:
    """Estimate expressions from landmark ratios alone.

    Used with the legacy Solutions backend or the YuNet fallback. It reads four
    classic measurements:

    * **MAR** — mouth aspect ratio, for jaw opening;
    * **Smile curve** — how far the mouth corners sit above the lip midline;
    * **EAR** — eye aspect ratio, for blinks and wide eyes;
    * **Brow lift** — eyebrow height relative to the eyes.
    """
    scores = dict.fromkeys(_BlendshapeScorers.ALL, 0.0)

    if landmarks is None or landmarks.shape[0] <= max(_FALLBACK_ANCHORS.values()):
        return scores
    anchor = {key: landmarks[index, :2] for key, index in _FALLBACK_ANCHORS.items()}

    mouth_width = max(distance(anchor["mouth_left"], anchor["mouth_right"]), 1e-6)
    mouth_height = distance(anchor["upper_lip_inner"], anchor["lower_lip_inner"])
    mar = mouth_height / mouth_width

    lip_mid_y = (anchor["upper_lip"][1] + anchor["lower_lip"][1]) / 2.0
    corner_lift = (lip_mid_y - (anchor["mouth_left"][1] + anchor["mouth_right"][1]) / 2.0) / mouth_width

    face_height = max(distance(anchor["forehead"], anchor["chin"]), 1e-6)
    right_ear = distance(anchor["right_eye_outer"], anchor["right_eye_inner"]) / face_height
    left_ear = distance(anchor["left_eye_outer"], anchor["left_eye_inner"]) / face_height
    ear = (right_ear + left_ear) / 2.0

    brow_gap = (
        distance(anchor["right_brow"], anchor["right_eye_outer"])
        + distance(anchor["left_brow"], anchor["left_eye_outer"])
    ) / (2.0 * face_height)

    smile = clamp((corner_lift - 0.02) / 0.10)
    jaw_open = clamp((mar - 0.06) / 0.34)
    eyes_wide = clamp((ear - 0.055) / 0.05)
    frown = clamp((-corner_lift - 0.01) / 0.08)
    brow_up = clamp((brow_gap - 0.055) / 0.05)

    scores["happy"] = clamp(0.9 * smile)
    scores["laugh"] = clamp(smile * jaw_open * 1.1)
    scores["sad"] = clamp(0.7 * frown + 0.3 * brow_up)
    scores["surprised"] = clamp(0.55 * jaw_open + 0.45 * eyes_wide)
    scores["angry"] = clamp(0.6 * clamp((0.055 - brow_gap) / 0.05) + 0.4 * clamp((0.09 - mar) / 0.09))
    scores["brow_raise"] = brow_up
    scores["kiss"] = clamp((0.05 - mar) / 0.05 * 0.7 * smile)
    scores["yawn"] = clamp((mar - 0.45) / 0.3)
    scores["blink"] = clamp((0.045 - ear) / 0.03)
    scores["neutral"] = clamp(1.0 - (smile + jaw_open + frown + eyes_wide + brow_up) / 2.2)
    return scores


# --------------------------------------------------------------------------- #
# Classifier
# --------------------------------------------------------------------------- #
class ExpressionClassifier:
    """Turn per-frame face observations into a stable expression label.

    Args:
        smoothing: EMA weight applied to each expression score across frames.
            ``0`` disables smoothing; ``0.35`` (default) is a good balance
            between responsiveness and stability.
        min_score: Minimum score for a non-neutral expression to win.
        priority: Override the precedence order used to break near-ties.

    Example:
        >>> classifier = ExpressionClassifier()          # doctest: +SKIP
        >>> result = classifier.classify(face)           # doctest: +SKIP
        >>> result.display()                             # doctest: +SKIP
        '😊 Feliz'
    """

    def __init__(
        self,
        smoothing: float = 0.35,
        min_score: float = 0.28,
        priority: Optional[Tuple[str, ...]] = None,
    ) -> None:
        self.smoothing = float(clamp(smoothing, 0.0, 1.0))
        self.min_score = float(min_score)
        self.priority = priority or _PRIORITY
        self._filters: Dict[str, EmaFilter] = {}
        self._hold_frames = 0

    def reset(self) -> None:
        self._filters.clear()
        self._hold_frames = 0

    def classify(self, face: Optional["FaceObservation"]) -> ExpressionResult:
        """Classify one face, or return ``unknown`` when there is no face."""
        if face is None:
            self.reset()
            return ExpressionResult(name="unknown", score=0.0, method="none")

        if face.has_blendshapes:
            raw = {name: float(scorer(face.blendshapes)) for name, scorer in _BlendshapeScorers.ALL.items()}
            method = "blendshapes"
        elif face.landmarks is not None and face.landmarks.size:
            raw = _geometric_scores(face.landmarks)
            method = "geometry"
        else:
            # Haar fallback: a face box with no landmarks at all.
            return ExpressionResult(name="unknown", score=0.0, method="none")

        smoothed = self._smooth(raw)
        name, score = self._pick(smoothed)
        return ExpressionResult(
            name=name,
            score=score,
            scores=smoothed,
            method=method,
            blendshapes=dict(face.blendshapes),
        )

    # -- internals --------------------------------------------------------- #
    def _smooth(self, raw: Dict[str, float]) -> Dict[str, float]:
        if self.smoothing <= 0.0:
            return dict(raw)
        out: Dict[str, float] = {}
        for name, value in raw.items():
            filt = self._filters.get(name)
            if filt is None:
                filt = EmaFilter(self.smoothing)
                self._filters[name] = filt
            out[name] = filt(value)
        return out

    def _pick(self, scores: Dict[str, float]) -> Tuple[str, float]:
        """Choose a winner, letting deliberate expressions beat ``neutral``."""
        best_name, best_score = "neutral", float(scores.get("neutral", 0.0))
        for name in self.priority:
            if name == "neutral":
                continue
            score = float(scores.get(name, 0.0))
            if score < self.min_score:
                continue
            # A deliberate expression wins unless neutral is clearly stronger,
            # which keeps a resting face from flickering into micro-expressions.
            if score >= best_score * 0.92:
                best_name, best_score = name, score
        return best_name, best_score
