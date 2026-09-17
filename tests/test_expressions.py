"""Expression recognition from blendshapes and from the geometric fallback."""

from __future__ import annotations

import numpy as np

from mirrorlab.detectors.base import BLENDSHAPE_NAMES, FaceObservation
from mirrorlab.expressions import (
    EXPRESSIONS,
    ExpressionClassifier,
    expression_catalog,
    expression_display,
    resolve_expression_name,
)

ALL_ZERO = dict.fromkeys(BLENDSHAPE_NAMES, 0.0)


def make_face(**blendshapes: float) -> FaceObservation:
    """A face carrying only the blendshape channels a test cares about."""
    channels = dict(ALL_ZERO)
    channels.update(blendshapes)
    landmarks = np.zeros((478, 3), dtype=np.float64)
    return FaceObservation(landmarks=landmarks, blendshapes=channels)


def classifier() -> ExpressionClassifier:
    """No smoothing: these tests assert on a single frame's verdict."""
    return ExpressionClassifier(smoothing=0.0, min_score=0.05)


# --------------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------------- #
def test_expression_registry_is_complete():
    assert len(EXPRESSIONS) >= 15
    for name, definition in EXPRESSIONS.items():
        assert definition.name == name
        assert definition.label and definition.label_es and definition.emoji


def test_blendshape_names_match_mediapipe_exactly():
    """The real list is 52 channels: `_neutral` plus 51 ARKit-style names."""
    assert len(BLENDSHAPE_NAMES) == 52
    assert BLENDSHAPE_NAMES[0] == "_neutral"
    assert "mouthSmileLeft" in BLENDSHAPE_NAMES
    assert "eyeBlinkRight" in BLENDSHAPE_NAMES
    assert "tongueOut" not in BLENDSHAPE_NAMES, "MediaPipe has no tongueOut channel"
    assert len(set(BLENDSHAPE_NAMES)) == 52


def test_aliases_resolve():
    assert resolve_expression_name("smile") == "happy"
    assert resolve_expression_name("Smiling") == "happy"
    assert resolve_expression_name("surprise") == "surprised"
    assert resolve_expression_name("nonexistent") == "nonexistent"
    assert "Feliz" in expression_display("smile")
    assert "Happy" in expression_display("smile", spanish=False)


def test_catalog_is_json_ready():
    import json

    catalog = expression_catalog()
    json.dumps(catalog)
    assert len(catalog) == len(EXPRESSIONS)


# --------------------------------------------------------------------------- #
# Classification
# --------------------------------------------------------------------------- #
def test_no_face_is_unknown():
    result = classifier().classify(None)
    assert result.name == "unknown"
    assert result.method == "none"
    assert result.emoji == "❔"


def test_neutral_resting_face():
    result = classifier().classify(make_face())
    assert result.name == "neutral"
    assert result.method == "blendshapes"


def test_smile_is_happy():
    face = make_face(mouthSmileLeft=0.95, mouthSmileRight=0.92, mouthDimpleLeft=0.7, mouthDimpleRight=0.7)
    result = classifier().classify(face)
    assert result.name == "happy", result.top(5)
    assert result.score > 0.7
    assert "😊" in result.display()


def test_smile_plus_open_jaw_is_laughing():
    face = make_face(mouthSmileLeft=0.9, mouthSmileRight=0.9, jawOpen=0.6)
    assert classifier().classify(face).name == "laugh"


def test_frown_and_inner_brow_is_sad():
    face = make_face(mouthFrownLeft=0.8, mouthFrownRight=0.8, browInnerUp=0.7)
    assert classifier().classify(face).name == "sad"


def test_brow_down_and_pressed_lips_is_angry():
    face = make_face(browDownLeft=0.9, browDownRight=0.9, mouthPressLeft=0.8, mouthPressRight=0.8)
    assert classifier().classify(face).name == "angry"


def test_open_jaw_and_wide_eyes_is_surprised():
    face = make_face(
        jawOpen=0.85, eyeWideLeft=0.8, eyeWideRight=0.8, browOuterUpLeft=0.6, browOuterUpRight=0.6
    )
    assert classifier().classify(face).name == "surprised"


def test_one_eye_closed_is_a_wink():
    face = make_face(eyeBlinkLeft=0.9, eyeBlinkRight=0.02)
    result = classifier().classify(face)
    assert result.name == "wink", result.top(5)


def test_both_eyes_closed_is_not_a_wink():
    face = make_face(eyeBlinkLeft=0.9, eyeBlinkRight=0.9)
    assert classifier().classify(face).name != "wink"


def test_pursed_lips_is_a_kiss():
    face = make_face(mouthPucker=0.9, mouthFunnel=0.7)
    assert classifier().classify(face).name == "kiss"


def test_raised_brows():
    face = make_face(browInnerUp=0.9, browOuterUpLeft=0.9, browOuterUpRight=0.9)
    assert classifier().classify(face).name == "brow_raise"


def test_cheek_puff():
    face = make_face(cheekPuff=0.95)
    assert classifier().classify(face).name == "puff"


def test_scores_are_bounded_and_the_winner_is_in_the_table():
    face = make_face(mouthSmileLeft=0.6, mouthSmileRight=0.6, jawOpen=0.3)
    result = classifier().classify(face)
    assert all(0.0 <= value <= 1.0 for value in result.scores.values())
    assert result.name in result.scores
    assert len(result.top(3)) == 3


def test_a_deliberate_expression_beats_a_resting_face():
    """A small but real smile must not be swallowed by `neutral`."""
    face = make_face(mouthSmileLeft=0.5, mouthSmileRight=0.5)
    assert classifier().classify(face).name == "happy"


# --------------------------------------------------------------------------- #
# Smoothing / voting
# --------------------------------------------------------------------------- #
def test_smoothing_prevents_single_frame_flips():
    smooth = ExpressionClassifier(smoothing=0.4, min_score=0.05)
    happy = make_face(mouthSmileLeft=0.95, mouthSmileRight=0.95)
    for _ in range(12):
        smooth.classify(happy)
    # A single anomalous frame must not change a well-established verdict.
    result = smooth.classify(make_face(browDownLeft=0.5, browDownRight=0.5))
    assert result.name == "happy"


def test_reset_clears_smoothing_state():
    smooth = ExpressionClassifier(smoothing=0.4)
    smooth.classify(make_face(mouthSmileLeft=0.9, mouthSmileRight=0.9))
    assert smooth._filters
    smooth.reset()
    assert not smooth._filters


# --------------------------------------------------------------------------- #
# Geometric fallback
# --------------------------------------------------------------------------- #
def test_face_without_blendshapes_uses_the_geometric_fallback():
    landmarks = np.zeros((478, 3), dtype=np.float64)

    def put(index: int, x: float, y: float) -> None:
        landmarks[index, 0] = x
        landmarks[index, 1] = y

    # A neutral-ish face layout in normalized coordinates.
    put(33, 0.40, 0.42)
    put(133, 0.45, 0.42)  # right eye
    put(362, 0.55, 0.42)
    put(263, 0.60, 0.42)  # left eye
    put(61, 0.44, 0.62)
    put(291, 0.56, 0.62)  # mouth corners
    put(13, 0.50, 0.60)
    put(14, 0.50, 0.64)  # lips
    put(12, 0.50, 0.605)
    put(15, 0.50, 0.635)  # inner lips
    put(105, 0.42, 0.36)
    put(334, 0.58, 0.36)  # brows
    put(1, 0.50, 0.52)  # nose
    put(152, 0.50, 0.78)
    put(10, 0.50, 0.16)  # chin, forehead

    face = FaceObservation(landmarks=landmarks, blendshapes={})
    result = classifier().classify(face)
    assert result.method == "geometry"
    assert result.name in EXPRESSIONS


def test_face_with_no_landmarks_and_no_blendshapes_is_unknown():
    face = FaceObservation(landmarks=np.zeros((0, 3)), blendshapes={})
    assert classifier().classify(face).name == "unknown"


def test_blank_landmarks_do_not_raise():
    face = FaceObservation(landmarks=np.zeros((478, 3)), blendshapes={})
    result = classifier().classify(face)
    assert isinstance(result.name, str)
