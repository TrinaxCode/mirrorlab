"""Landmark geometry helpers.

Every detector in MirrorLab speaks the same language: a list of normalized
``(x, y)`` (and optionally ``z``) points. These helpers do the vector math that
the gesture and expression classifiers need.

Conventions
-----------
* Coordinates are **normalized** to ``[0, 1]`` relative to the frame, matching
  MediaPipe. ``x`` grows to the right, ``y`` grows downward.
* All helpers accept either :class:`~mirrorlab.detectors.base.Landmark`
  instances, ``(x, y)`` / ``(x, y, z)`` tuples or NumPy arrays.
"""

from __future__ import annotations

import math
from typing import Iterable, List, Sequence, Tuple

import numpy as np

__all__ = [
    "angle",
    "angle_between",
    "as_array",
    "bounding_box",
    "centroid",
    "clamp",
    "curvature",
    "distance",
    "distance_3d",
    "finger_curl",
    "hand_scale",
    "lerp",
    "midpoint",
    "normalize_vector",
    "palm_normal",
    "point_in_polygon",
    "polygon_area",
    "to_pixel",
    "to_pixels",
]

PointLike = Sequence[float]

# MediaPipe landmark indices used for scale normalisation.
WRIST = 0
INDEX_MCP = 5
MIDDLE_MCP = 9
RING_MCP = 13
PINKY_MCP = 17


def as_array(points: Iterable[PointLike]) -> np.ndarray:
    """Convert an iterable of points into an ``(N, D)`` float array.

    Accepts objects exposing ``x``/``y``/``z`` attributes (duck-typed
    landmarks), plain sequences, or an existing array.
    """
    if isinstance(points, np.ndarray):
        return points.astype(np.float64, copy=False)
    rows: List[List[float]] = []
    for point in points:
        if hasattr(point, "x"):
            row = [float(point.x), float(point.y)]
            z = getattr(point, "z", None)
            if z is not None:
                row.append(float(z))
            rows.append(row)
        else:
            rows.append([float(v) for v in point])
    if not rows:
        return np.zeros((0, 2), dtype=np.float64)
    width = max(len(row) for row in rows)
    for row in rows:
        while len(row) < width:
            row.append(0.0)
    return np.asarray(rows, dtype=np.float64)


def to_pixel(point: PointLike, width: int, height: int) -> Tuple[int, int]:
    """Map a normalized point to integer pixel coordinates (unclipped)."""
    return round(point[0] * width), round(point[1] * height)


def to_pixels(points: Iterable[PointLike], width: int, height: int) -> np.ndarray:
    """Map many normalized points to pixel coordinates as an ``(N, 2)`` int array."""
    array = as_array(points)
    if array.size == 0:
        return np.zeros((0, 2), dtype=np.int32)
    scaled = np.empty((array.shape[0], 2), dtype=np.int32)
    scaled[:, 0] = np.round(array[:, 0] * width)
    scaled[:, 1] = np.round(array[:, 1] * height)
    return scaled


def distance(a: PointLike, b: PointLike) -> float:
    """Euclidean distance in normalized 2-D space."""
    return math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))


def distance_3d(a: PointLike, b: PointLike) -> float:
    """Euclidean distance using ``x``, ``y`` and (when present) ``z``."""
    dx = float(a[0]) - float(b[0])
    dy = float(a[1]) - float(b[1])
    dz = float(a[2]) - float(b[2]) if len(a) > 2 and len(b) > 2 else 0.0
    return math.sqrt(dx * dx + dy * dy + dz * dz)


def midpoint(a: PointLike, b: PointLike) -> np.ndarray:
    """Component-wise midpoint of two points."""
    return (as_array([a, b])[0] + as_array([b])[0]) / 2.0


def centroid(points: Iterable[PointLike]) -> np.ndarray:
    """Mean position of a point cloud (``[0, 0]`` when empty)."""
    array = as_array(points)
    if array.size == 0:
        return np.zeros(2, dtype=np.float64)
    return array[:, :2].mean(axis=0)


def bounding_box(points: Iterable[PointLike], pad: float = 0.0) -> Tuple[float, float, float, float]:
    """Axis-aligned bounding box as ``(x_min, y_min, x_max, y_max)``.

    ``pad`` is an **absolute** offset in normalized units. Use
    :meth:`~mirrorlab.detectors.base.FaceObservation.bbox_pixels` when you want
    padding expressed as a fraction of the box size.
    """
    array = as_array(points)
    if array.size == 0:
        return (0.0, 0.0, 0.0, 0.0)
    xs, ys = array[:, 0], array[:, 1]
    return (
        float(xs.min()) - pad,
        float(ys.min()) - pad,
        float(xs.max()) + pad,
        float(ys.max()) + pad,
    )


def normalize_vector(vector: Sequence[float]) -> np.ndarray:
    """Return ``vector`` scaled to unit length (zero vector stays zero)."""
    array = np.asarray(vector, dtype=np.float64)
    norm = float(np.linalg.norm(array))
    if norm < 1e-9:
        return np.zeros_like(array)
    return array / norm


def angle(a: PointLike, b: PointLike, c: PointLike) -> float:
    """Interior angle at ``b`` formed by ``a-b-c``, in degrees ``[0, 180]``.

    This is the workhorse for finger-extension tests: a straight finger has an
    angle near ``180`` while a curled one drops below ``90``.
    """
    ba = np.asarray([float(a[0]) - float(b[0]), float(a[1]) - float(b[1])])
    bc = np.asarray([float(c[0]) - float(b[0]), float(c[1]) - float(b[1])])
    na, nc = float(np.linalg.norm(ba)), float(np.linalg.norm(bc))
    if na < 1e-9 or nc < 1e-9:
        return 180.0
    cosine = float(np.dot(ba, bc) / (na * nc))
    return math.degrees(math.acos(max(-1.0, min(1.0, cosine))))


def angle_between(v1: Sequence[float], v2: Sequence[float]) -> float:
    """Angle between two vectors, in degrees ``[0, 180]``."""
    a = np.asarray(v1, dtype=np.float64)
    b = np.asarray(v2, dtype=np.float64)
    na, nb = float(np.linalg.norm(a)), float(np.linalg.norm(b))
    if na < 1e-9 or nb < 1e-9:
        return 0.0
    cosine = float(np.dot(a, b) / (na * nb))
    return math.degrees(math.acos(max(-1.0, min(1.0, cosine))))


def hand_scale(points: Iterable[PointLike]) -> float:
    """A rotation-invariant size estimate for a hand.

    Defined as the mean distance from the wrist to the four finger MCP joints.
    Dividing distances by this value makes gesture thresholds work at any
    distance from the camera — the single most important trick for robust
    gesture recognition.
    """
    array = as_array(points)
    if array.shape[0] <= PINKY_MCP:
        return 1.0
    wrist = array[WRIST, :2]
    mcp = array[[INDEX_MCP, MIDDLE_MCP, RING_MCP, PINKY_MCP], :2]
    scale = float(np.linalg.norm(mcp - wrist, axis=1).mean())
    return scale if scale > 1e-6 else 1e-6


def palm_normal(points: Iterable[PointLike]) -> np.ndarray:
    """Unit normal of the palm plane, from world landmarks when available."""
    array = as_array(points)
    if array.shape[1] < 3 or array.shape[0] <= PINKY_MCP:
        return np.array([0.0, 0.0, 1.0])
    v1 = array[MIDDLE_MCP, :3] - array[WRIST, :3]
    v2 = array[PINKY_MCP, :3] - array[INDEX_MCP, :3]
    return normalize_vector(np.cross(v1, v2))


def finger_curl(
    points: Iterable[PointLike],
    mcp: int,
    pip: int,
    dip: int,
    tip: int,
) -> float:
    """How curled a finger is, as a normalized ``0..1`` score.

    ``0`` means perfectly straight, ``1`` means fully folded. The score is the
    mean of two complementary signals:

    * the joint angle at the PIP, mapped from ``180°`` (straight) to ``60°`` (folded);
    * how far the tip sits from the wrist relative to the MCP, normalized by hand size.

    Combining both makes the classifier resilient to noisy landmarks and to
    hands that are rotated or tilted towards the camera.
    """
    array = as_array(points)
    if array.shape[0] <= max(mcp, pip, dip, tip):
        return 0.0
    straightness = angle(array[mcp], array[pip], array[dip])
    angle_score = clamp((180.0 - straightness) / 120.0, 0.0, 1.0)

    scale = hand_scale(array)
    wrist = array[WRIST, :2]
    reach = distance(wrist, array[tip, :2]) / scale
    mcp_reach = distance(wrist, array[mcp, :2]) / scale
    # A straight finger reaches ~2.0 hand-scales from the wrist, a folded one ~1.0.
    reach_score = clamp((1.6 - (reach - mcp_reach)) / 1.0, 0.0, 1.0)
    return clamp(0.65 * angle_score + 0.35 * reach_score, 0.0, 1.0)


def curvature(a: PointLike, b: PointLike, c: PointLike) -> float:
    """Turn sharpness at ``b``: ``0`` = straight, ``1`` = right angle or sharper."""
    return clamp((180.0 - angle(a, b, c)) / 90.0, 0.0, 1.0)


def point_in_polygon(point: PointLike, polygon: Sequence[PointLike]) -> bool:
    """Ray-casting point-in-polygon test (works for concave polygons)."""
    x, y = float(point[0]), float(point[1])
    inside = False
    n = len(polygon)
    if n < 3:
        return False
    j = n - 1
    for i in range(n):
        xi, yi = float(polygon[i][0]), float(polygon[i][1])
        xj, yj = float(polygon[j][0]), float(polygon[j][1])
        if (yi > y) != (yj > y):
            slope = (xj - xi) / ((yj - yi) if abs(yj - yi) > 1e-12 else 1e-12)
            if x < xi + slope * (y - yi):
                inside = not inside
        j = i
    return inside


def polygon_area(polygon: Sequence[PointLike]) -> float:
    """Signed area of a polygon (shoelace formula)."""
    array = as_array(polygon)
    if array.shape[0] < 3:
        return 0.0
    x, y = array[:, 0], array[:, 1]
    return 0.5 * float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def lerp(a: float, b: float, t: float) -> float:
    """Linear interpolation between ``a`` and ``b``."""
    return a + (b - a) * t


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    """Constrain ``value`` to the ``[low, high]`` interval."""
    return low if value < low else high if value > high else value
