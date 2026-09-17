"""Shared pytest configuration.

Every test in this suite must run **headless, offline and without a camera**.
Anything that needs hardware is marked and skipped automatically, so
``pytest`` works identically on a laptop, in Docker and on GitHub Actions.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

ASSETS = Path(__file__).resolve().parent / "assets"

ON_CI = os.environ.get("CI", "").lower() in {"1", "true", "yes"}
FORCE_HEADLESS = os.environ.get("PYTEST_HEADLESS") == "1"

_camera_cache: "bool | None" = None


def camera_available() -> bool:
    """True only when a camera can actually deliver a frame.

    ``pytest.importorskip``-style guarding is not enough here: a camera can be
    present as a device yet be locked by another application, which is the
    most common failure on a developer machine.
    """
    global _camera_cache
    if _camera_cache is not None:
        return _camera_cache
    if ON_CI or FORCE_HEADLESS:
        _camera_cache = False
        return False
    try:
        import cv2
    except Exception:  # pragma: no cover - headless build or missing libGL
        _camera_cache = False
        return False
    capture = None
    try:
        capture = cv2.VideoCapture(0)
        _camera_cache = bool(capture.isOpened() and capture.read()[0])
    except Exception:  # pragma: no cover - driver dependent
        _camera_cache = False
    finally:
        if capture is not None:
            capture.release()
    return _camera_cache


requires_camera = pytest.mark.skipif(not camera_available(), reason="no usable camera (headless CI)")
requires_mediapipe = pytest.mark.skipif(
    not __import__("importlib").util.find_spec("mediapipe"),
    reason="mediapipe is not installed",
)


def pytest_collection_modifyitems(config, items):
    """Defence in depth: skipping works even without ``-m "not camera"``."""
    for item in items:
        if "camera" in item.keywords and not camera_available():
            item.add_marker(pytest.mark.skip(reason="no camera / headless CI"))
        if "gui" in item.keywords and (ON_CI or FORCE_HEADLESS):
            item.add_marker(pytest.mark.skip(reason="no display / headless CI"))


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture
def frame() -> np.ndarray:
    """A deterministic 320×240 BGR frame with structure (not pure noise)."""
    rng = np.random.default_rng(1234)
    image = np.zeros((240, 320, 3), dtype=np.uint8)
    ys, xs = np.mgrid[0:240, 0:320]
    image[..., 0] = (xs % 256).astype(np.uint8)
    image[..., 1] = (ys % 256).astype(np.uint8)
    image[..., 2] = ((xs + ys) % 256).astype(np.uint8)
    image = np.clip(image.astype(np.int16) + rng.integers(-12, 12, image.shape), 0, 255).astype(np.uint8)
    return image


@pytest.fixture
def noise_frame() -> np.ndarray:
    return (np.random.default_rng(7).random((240, 320, 3)) * 255).astype(np.uint8)


@pytest.fixture
def portrait_path() -> Path:
    """A real photo with a detectable face; skipped when the asset is absent."""
    path = ASSETS / "portrait.jpg"
    if not path.exists():
        pytest.skip("tests/assets/portrait.jpg is missing")
    return path


@pytest.fixture
def hands_path() -> Path:
    path = ASSETS / "woman_hands.jpg"
    if not path.exists():
        pytest.skip("tests/assets/woman_hands.jpg is missing")
    return path
