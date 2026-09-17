"""Gesture classification from synthetic landmark data.

These tests are the safety net for the whole hand-tracking feature: they build
21-point hands that *mean* something (a fist, a peace sign, a thumbs up) and
assert the classifier agrees. No camera, no MediaPipe, no flakiness.
"""

from __future__ import annotations

import numpy as np
import pytest

from mirrorlab.actions import GestureController
from mirrorlab.detectors.base import HandObservation
from mirrorlab.gestures import (
    GESTURE_ALIASES,
    GESTURES,
    GestureTracker,
    analyze_hand,
    classify_gesture,
    classify_hands,
    gesture_catalog,
    gesture_display,
    resolve_gesture_name,
)

# --------------------------------------------------------------------------- #
# Synthetic hands
# --------------------------------------------------------------------------- #
#: ``(MCP, PIP, DIP, TIP)`` joint chains, matching MediaPipe's hand topology.
CHAINS = {
    "index": (5, 6, 7, 8),
    "middle": (9, 10, 11, 12),
    "ring": (13, 14, 15, 16),
    "pinky": (17, 18, 19, 20),
}
#: Horizontal position of each finger's knuckle column.
COLUMNS = {"index": 0.44, "middle": 0.50, "ring": 0.56, "pinky": 0.62}


def make_hand(
    extended: tuple[str, ...] = (),
    thumb_extended: bool = False,
    thumb_across: bool = False,
    handedness: str = "Right",
    spread: float = 1.0,
) -> HandObservation:
    """Build a plausible 21-point hand in normalized coordinates.

    Args:
        extended: fingers held straight up.
        thumb_extended: whether the thumb swings away from the palm.
        thumb_across: tuck the thumb across the palm (a true fist).
        spread: horizontal fan-out multiplier for the extended fingers.
    """
    points = np.zeros((21, 3), dtype=np.float64)
    points[0] = [0.50, 0.92, 0.0]  # wrist

    # Thumb runs diagonally away from the palm when extended.
    if thumb_extended:
        points[1:5] = [[0.43, 0.86, 0.0], [0.37, 0.81, 0.0], [0.32, 0.77, 0.0], [0.27, 0.73, 0.0]]
    else:
        tip_x = 0.52 if thumb_across else 0.44
        points[1:5] = [[0.45, 0.87, 0.0], [0.45, 0.83, 0.0], [0.45, 0.80, 0.0], [tip_x, 0.78, 0.0]]

    for finger, (mcp, pip, dip, tip) in CHAINS.items():
        column = COLUMNS[finger]
        points[mcp] = [column, 0.80, 0.0]
        if finger in extended:
            # A straight finger: collinear joints reaching well above the knuckle.
            fan = (column - 0.50) * 0.30 * spread
            points[pip] = [column + fan * 0.4, 0.68, 0.0]
            points[dip] = [column + fan * 0.7, 0.60, 0.0]
            points[tip] = [column + fan, 0.50, 0.0]
        else:
            # A folded finger: joints turn back towards the palm.
            points[pip] = [column, 0.70, 0.0]
            points[dip] = [column, 0.76, 0.0]
            points[tip] = [column, 0.70, 0.0]
    return HandObservation(landmarks=points, handedness=handedness, score=0.98)


# --------------------------------------------------------------------------- #
# Pose analysis
# --------------------------------------------------------------------------- #
def test_pose_identifies_extended_fingers():
    pose = analyze_hand(make_hand(extended=("index", "middle")))
    assert pose.extended_names == ["index", "middle"]
    assert pose.extended_count == 2
    assert not pose.thumb_extended
    assert pose.scale > 0


def test_pose_detects_a_pinch():
    hand = make_hand()
    hand.landmarks[8] = hand.landmarks[4] + [0.005, 0.0, 0.0]
    assert analyze_hand(hand).pinch is True
    assert analyze_hand(make_hand(extended=("index",))).pinch is False


def test_pose_reports_spread():
    together = analyze_hand(make_hand(extended=("index", "middle", "ring", "pinky"), spread=0.2))
    apart = analyze_hand(make_hand(extended=("index", "middle", "ring", "pinky"), spread=2.5))
    assert apart.spread > together.spread


# --------------------------------------------------------------------------- #
# Static classification
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "extended, thumb, expected",
    [
        ((), False, "fist"),
        (("index", "middle", "ring", "pinky"), True, "open_palm"),
        (("index",), False, "pointing"),
        (("index", "middle"), False, "peace"),
        (("index", "middle", "ring"), False, "three"),
        (("index", "middle", "ring", "pinky"), False, "four"),
        (("index", "pinky"), False, "rock"),
        (("index", "middle", "ring", "pinky"), True, "open_palm"),
    ],
)
def test_static_gestures(extended, thumb, expected):
    hand = make_hand(extended=extended, thumb_extended=thumb)
    match = classify_gesture(hand)
    assert match.name == expected, f"got {match.name} (scores={list(match.scores)[:4]})"
    assert match.score > 0
    assert match.definition is not None


def test_thumbs_up_and_down_are_distinguished_by_direction():
    up = make_hand(thumb_extended=True)
    up.landmarks[4] = [0.50, 0.40, 0.0]
    up.landmarks[3] = [0.49, 0.55, 0.0]
    up.landmarks[2] = [0.48, 0.68, 0.0]
    assert classify_gesture(up).name == "thumbs_up"

    down = make_hand(thumb_extended=True)
    down.landmarks[4] = [0.50, 0.99, 0.0]
    down.landmarks[3] = [0.49, 0.92, 0.0]
    down.landmarks[2] = [0.48, 0.84, 0.0]
    assert classify_gesture(down).name == "thumbs_down"


def test_ok_sign_does_not_collapse_into_pinch():
    hand = make_hand(extended=("middle", "ring", "pinky"), thumb_extended=True)
    hand.landmarks[8] = hand.landmarks[4] + [0.004, 0.0, 0.0]
    match = classify_gesture(hand)
    assert match.name == "ok", f"scores={list(match.scores.items())[:4]}"


def test_no_hand_state_returns_none():
    hand = make_hand(extended=("index",))
    hand.landmarks = hand.landmarks.copy()
    match = classify_gesture(hand)
    assert match.name in GESTURES
    assert 0.0 <= match.score <= 1.0


def test_scores_are_bounded_and_sorted():
    match = classify_gesture(make_hand(extended=("index", "middle")))
    assert all(0.0 <= score <= 1.0 for score in match.scores.values())
    values = list(match.scores.values())
    assert values == sorted(values, reverse=True)


def test_classify_hands_annotates_the_observations():
    hands = [make_hand(extended=("index",)), make_hand(extended=("index", "middle"))]
    matches = classify_hands(hands, annotate=True)
    assert [m.name for m in matches] == ["pointing", "peace"]
    assert hands[0].gesture == "pointing"
    assert hands[1].gesture_score > 0


def test_malformed_landmarks_never_raise():
    """A truncated hand (some backends return fewer points) must degrade, not crash."""
    hand = HandObservation(landmarks=np.zeros((5, 3)), handedness="Unknown")
    match = classify_gesture(hand)
    assert isinstance(match.name, str)


# --------------------------------------------------------------------------- #
# Registry / catalog
# --------------------------------------------------------------------------- #
def test_registry_is_internally_consistent():
    assert len(GESTURES) >= 20
    for name, definition in GESTURES.items():
        assert definition.name == name
        assert definition.label and definition.label_es and definition.emoji
        assert 0.0 < definition.threshold <= 2.0
        assert definition.category in {"static", "count", "symbol", "dynamic"}


def test_aliases_resolve_to_real_gestures():
    for alias, target in GESTURE_ALIASES.items():
        assert target in GESTURES, f"alias {alias!r} points at unknown gesture {target!r}"
    assert resolve_gesture_name("Victory") == "peace"
    assert resolve_gesture_name("thumb-up") == "thumbs_up"
    assert resolve_gesture_name("  PALM ") == "open_palm"
    assert resolve_gesture_name("nonexistent") == "nonexistent"


def test_catalog_is_json_ready():
    import json

    catalog = gesture_catalog()
    assert len(catalog) == len(GESTURES)
    json.dumps(catalog)
    assert all("name" in row and "emoji" in row for row in catalog)


def test_display_strings():
    assert "Victoria" in gesture_display("peace")
    assert "Peace" in gesture_display("peace", spanish=False)
    assert gesture_display("unknown_gesture") == "unknown_gesture"


# --------------------------------------------------------------------------- #
# Gesture controller (hold-to-confirm)
# --------------------------------------------------------------------------- #
def _match_for(hand: HandObservation):
    return classify_gesture(hand)


def test_controller_requires_a_dwell_before_firing():
    controller = GestureController(dwell=0.5, refractory=0.5, history=3)
    peace = _match_for(make_hand(extended=("index", "middle")))

    assert controller.update([peace], timestamp=0.0) == []
    assert controller.update([peace], timestamp=0.2) == [], "0.2 s is not long enough"
    assert 0.0 < controller.last_progress < 1.0
    events = controller.update([peace], timestamp=0.7)
    assert len(events) == 1
    assert events[0].action == "next_filter"


def test_controller_is_one_shot_until_the_pose_is_released():
    controller = GestureController(dwell=0.2, refractory=0.1, history=3)
    peace = _match_for(make_hand(extended=("index", "middle")))
    fired = []
    for index in range(12):
        fired += controller.update([peace], timestamp=index * 0.1)
    assert len(fired) == 1, "holding a pose must not machine-gun the action"

    controller.update([], timestamp=1.5)  # release
    fired = []
    for index in range(6):
        fired += controller.update([peace], timestamp=2.0 + index * 0.1)
    assert len(fired) == 1, "after releasing, the gesture must be able to fire again"


def test_controller_ignores_a_flickering_gesture():
    controller = GestureController(dwell=0.2, refractory=0.1, history=5)
    peace = _match_for(make_hand(extended=("index", "middle")))
    point = _match_for(make_hand(extended=("index",)))
    fired = []
    sequence = [peace, point, peace, point, peace, point, peace, point]
    for index, match in enumerate(sequence):
        fired += controller.update([match], timestamp=index * 0.1)
    assert fired == [], "a pose that never survives the vote window must not fire"


def test_controller_can_be_disabled():
    controller = GestureController(dwell=0.0, enabled=False)
    peace = _match_for(make_hand(extended=("index", "middle")))
    assert controller.update([peace], timestamp=0.0) == []


def test_controller_progress_is_reported_for_the_ring():
    controller = GestureController(dwell=1.0, history=3)
    peace = _match_for(make_hand(extended=("index", "middle")))
    controller.update([peace], timestamp=0.0)
    controller.update([peace], timestamp=0.5)
    assert 0.4 < controller.last_progress < 0.6
    assert controller.pending == "peace"


# --------------------------------------------------------------------------- #
# Dynamic gestures (motion)
# --------------------------------------------------------------------------- #
def test_tracker_detects_a_swipe():
    tracker = GestureTracker(min_displacement=0.2, max_duration=0.6)
    events = []
    for index in range(8):
        events.append(tracker.update((0.2 + index * 0.08, 0.5), timestamp=index * 0.04))
    fired = [event for event in events if event]
    assert fired, "a fast straight displacement must register"
    assert fired[0].name in {"swipe_right", "swipe_left"}


def test_tracker_is_quiet_when_the_hand_is_still():
    tracker = GestureTracker()
    for index in range(20):
        assert tracker.update((0.5, 0.5), timestamp=index * 0.03) is None


def test_tracker_ignores_slow_motion():
    tracker = GestureTracker(min_displacement=0.3, max_duration=0.4)
    for index in range(20):
        assert tracker.update((0.5 + index * 0.002, 0.5), timestamp=index * 0.1) is None


def test_tracker_resets_on_hand_loss():
    tracker = GestureTracker()
    tracker.update((0.5, 0.5), timestamp=0.0)
    assert tracker.update(None, timestamp=0.1) is None
    # A fresh trajectory must be required after a gap.
    assert tracker.update((0.9, 0.5), timestamp=0.2) is None
