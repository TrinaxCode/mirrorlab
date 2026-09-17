"""Geometry helpers and the smoothing filters — the maths everything else rests on."""

from __future__ import annotations

import math

import numpy as np
import pytest

from mirrorlab.utils.geometry import (
    angle,
    as_array,
    bounding_box,
    clamp,
    distance,
    finger_curl,
    hand_scale,
    point_in_polygon,
    polygon_area,
    to_pixels,
)
from mirrorlab.utils.smoothing import EmaFilter, LandmarkSmoother, OneEuroFilter, SlidingWindow
from mirrorlab.utils.timing import FpsMeter


# --------------------------------------------------------------------------- #
# geometry
# --------------------------------------------------------------------------- #
def test_as_array_accepts_objects_tuples_and_arrays():
    class Point:
        def __init__(self, x, y, z=0.0):
            self.x, self.y, self.z = x, y, z

    from_objects = as_array([Point(0.1, 0.2), Point(0.3, 0.4)])
    from_tuples = as_array([(0.1, 0.2), (0.3, 0.4)])
    from_array = as_array(np.array([[0.1, 0.2], [0.3, 0.4]]))
    assert from_objects.shape == (2, 3)
    assert np.allclose(from_tuples, from_array)
    assert as_array([]).shape == (0, 2)


def test_distance_and_angle():
    assert distance((0, 0), (3, 4)) == pytest.approx(5.0)
    assert angle((0, 1), (0, 0), (1, 0)) == pytest.approx(90.0)
    assert angle((0, 1), (0, 0), (0, 2)) == pytest.approx(0.0), "collinear, same side"
    assert angle((0, 1), (0, 0), (0, -1)) == pytest.approx(180.0), "collinear, opposite sides"
    assert angle((0, 0), (0, 0), (1, 0)) == pytest.approx(180.0), "degenerate input must not raise"


def test_to_pixels_scales_normalized_points():
    result = to_pixels([(0.5, 0.5), (1.0, 0.25)], 200, 100)
    assert result.tolist() == [[100, 50], [200, 25]]


def test_bounding_box_padding():
    box = bounding_box([(0.2, 0.3), (0.6, 0.7)])
    assert box == pytest.approx((0.2, 0.3, 0.6, 0.7))
    padded = bounding_box([(0.2, 0.3), (0.6, 0.7)], pad=0.1)
    assert padded[0] == pytest.approx(0.1), "pad is an absolute offset"
    assert bounding_box([]) == (0.0, 0.0, 0.0, 0.0)


def test_point_in_polygon_and_area():
    square = [(0, 0), (1, 0), (1, 1), (0, 1)]
    assert point_in_polygon((0.5, 0.5), square)
    assert not point_in_polygon((1.5, 0.5), square)
    assert abs(polygon_area(square)) == pytest.approx(1.0)


def test_clamp():
    assert clamp(5, 0, 1) == 1
    assert clamp(-5, 0, 1) == 0
    assert clamp(0.5, 0, 1) == 0.5


def _straight_finger(tip_offset: float = 0.0) -> np.ndarray:
    """A synthetic 21-point hand with one configurable finger.

    Built so the geometry helpers can be tested without MediaPipe: the
    coordinates follow the same conventions (normalized, y down, wrist at 0).
    """
    points = np.zeros((21, 3), dtype=np.float64)
    points[0] = [0.50, 0.90, 0.0]  # wrist
    points[1] = [0.44, 0.84, 0.0]  # thumb CMC
    points[2] = [0.40, 0.79, 0.0]
    points[3] = [0.37, 0.75, 0.0]
    points[4] = [0.34, 0.71, 0.0]  # thumb tip (extended, away from the palm)
    for base, x in ((5, 0.46), (9, 0.50), (13, 0.54), (17, 0.58)):
        points[base] = [x, 0.80, 0.0]  # MCP
        points[base + 1] = [x, 0.70 + tip_offset, 0.0]  # PIP
        points[base + 2] = [x, 0.62 + tip_offset, 0.0]  # DIP
        points[base + 3] = [x, 0.54 + tip_offset, 0.0]  # TIP
    return points


def test_hand_scale_is_positive_and_rotation_invariant():
    points = _straight_finger()
    scale = hand_scale(points)
    assert scale > 0
    # Rotating the hand about the wrist must not change its apparent size.
    theta = math.radians(35)
    rotation = np.array([[math.cos(theta), -math.sin(theta)], [math.sin(theta), math.cos(theta)]])
    wrist = points[0, :2]
    rotated = points.copy()
    rotated[:, :2] = (points[:, :2] - wrist) @ rotation.T + wrist
    assert hand_scale(rotated) == pytest.approx(scale, rel=1e-6)


def test_finger_curl_distinguishes_straight_from_folded():
    straight = _straight_finger()
    folded = straight.copy()
    for base in (5, 9, 13, 17):
        folded[base + 1] = [straight[base + 1][0], 0.78, 0.0]
        folded[base + 2] = [straight[base + 2][0], 0.82, 0.0]
        folded[base + 3] = [straight[base + 3][0], 0.79, 0.0]
    assert finger_curl(straight, 5, 6, 7, 8) < 0.35
    assert finger_curl(folded, 5, 6, 7, 8) > 0.55


# --------------------------------------------------------------------------- #
# smoothing
# --------------------------------------------------------------------------- #
def test_one_euro_converges_and_reduces_jitter():
    smooth = OneEuroFilter(min_cutoff=1.0, beta=0.0)
    for _ in range(60):
        smooth(1.0, 0.0)
    rng = np.random.default_rng(0)
    raw, filtered = [], []
    for index in range(120):
        noisy = 1.0 + rng.normal(0, 0.05)
        raw.append(noisy)
        filtered.append(smooth(noisy, index / 60.0))
    assert np.std(filtered[60:]) < np.std(raw[60:]) * 0.6


def test_one_euro_is_responsive_to_a_step_change():
    smooth = OneEuroFilter(min_cutoff=1.0, beta=0.5)
    for index in range(30):
        smooth(0.0, index / 60.0)
    value = 0.0
    for index in range(30, 60):
        value = smooth(1.0, index / 60.0)
    assert value > 0.8, "a fast step must not be smeared away"


def test_one_euro_reset_clears_state():
    smooth = OneEuroFilter()
    smooth(5.0, 0.0)
    smooth.reset()
    assert smooth(9.0, 1.0) == pytest.approx(9.0)


def test_ema_filter():
    ema = EmaFilter(alpha=0.5)
    assert ema(1.0) == 1.0
    assert ema(3.0) == pytest.approx(2.0)
    ema.reset()
    assert ema(7.0) == 7.0


def test_sliding_window_majority_and_mean():
    window = SlidingWindow(maxlen=5)
    for value in (1, 1, 2, 1, 1):
        window.push(value)
    assert window.majority() == 1
    assert window.mean() == pytest.approx(1.2)
    assert window.majority("fallback") == 1
    window.clear()
    assert window.majority("fallback") == "fallback"


def test_landmark_smoother_keeps_shape_and_reduces_jitter():
    smoother = LandmarkSmoother(min_cutoff=1.0, beta=0.0)
    rng = np.random.default_rng(3)
    base = np.tile(np.array([[0.5, 0.5, 0.0]]), (21, 1))
    outputs = []
    for index in range(80):
        noisy = base + rng.normal(0, 0.01, base.shape)
        outputs.append(smoother.apply(noisy, timestamp=index / 60.0))
    assert outputs[-1].shape == base.shape
    tail = np.array([o[0, 0] for o in outputs[-30:]])
    assert tail.std() < 0.01


def test_landmark_smoother_allocates_one_filter_per_landmark_and_axis():
    """Regression guard for a bug that collapsed the whole mesh onto one point.

    Sharing a single filter across all landmarks turns smoothing into a global
    average: every point converges to the first point's value and the face mesh
    degenerates into a dot. The symptom looks like a detector failure, so this
    asserts the structural property directly.
    """
    smoother = LandmarkSmoother(dimensions=3)
    points = np.zeros((21, 3), dtype=np.float64)
    smoother.apply(points, timestamp=0.0)
    assert smoother.filter_count == 21 * 3


def test_landmark_smoother_preserves_distinct_points():
    """Distinct landmarks must stay distinct — the actual user-visible contract."""
    smoother = LandmarkSmoother(min_cutoff=1.0, beta=0.0)
    points = np.zeros((21, 3), dtype=np.float64)
    points[:, 0] = np.linspace(0.1, 0.9, 21)
    points[:, 1] = np.linspace(0.2, 0.8, 21)
    for index in range(40):
        out = smoother.apply(points, timestamp=index / 60.0)
    # The spread must survive smoothing; a shared filter would flatten it to ~0.
    assert out[:, 0].ptp() > 0.7
    assert out[:, 1].ptp() > 0.5
    np.testing.assert_allclose(out[:, 0], points[:, 0], atol=1e-3)
    np.testing.assert_allclose(out[:, 1], points[:, 1], atol=1e-3)


def test_landmark_smoother_tracks_motion_without_lagging_far_behind():
    smoother = LandmarkSmoother(min_cutoff=2.0, beta=0.5)
    for index in range(30):
        smoother.apply(np.array([[0.2, 0.2, 0.0]]), timestamp=index / 60.0)
    value = None
    for index in range(30, 90):
        value = smoother.apply(np.array([[0.8, 0.2, 0.0]]), timestamp=index / 60.0)
    assert value is not None
    assert value[0, 0] > 0.75, "a held new position must be reached, not averaged away"


def test_landmark_smoother_tracks_do_not_interfere():
    """Two hands (or two faces) must not share filter state."""
    smoother = LandmarkSmoother(min_cutoff=1.0, beta=0.0)
    left = np.zeros((21, 3), dtype=np.float64)
    right = np.full((21, 3), 0.8, dtype=np.float64)
    for index in range(40):
        out_left = smoother.apply(left, track=0, timestamp=index / 60.0)
        out_right = smoother.apply(right, track=1, timestamp=index / 60.0)
    assert out_left[0, 0] < 0.1
    assert out_right[0, 0] > 0.7


def test_landmark_smoother_handles_empty_input():
    smoother = LandmarkSmoother()
    assert smoother.apply(np.zeros((0, 3))).shape == (0, 3)


# --------------------------------------------------------------------------- #
# timing
# --------------------------------------------------------------------------- #
def test_fps_meter_reports_a_rate_and_stage_timings():
    meter = FpsMeter(window=8)
    for _ in range(10):
        meter.tick()
    assert meter.fps > 0
    assert meter.frames == 10
    meter.begin("detect")
    meter.end("detect")
    assert meter.stage_mean("detect") >= 0.0
    assert "detect" in meter.stages()
    meter.reset()
    assert meter.frames == 0
    assert meter.stage_mean("detect") == 0.0
