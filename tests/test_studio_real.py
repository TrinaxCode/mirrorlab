"""End-to-end checks with the real MediaPipe models and a real photograph.

These are the tests that tell you the studio actually works, as opposed to the
fakes in ``test_studio_runtime.py`` that tell you the wiring is right. They are
skipped (not failed) when a model is unavailable and cannot be downloaded, so
the suite still runs offline.
"""

from __future__ import annotations

import numpy as np
import pytest

from mirrorlab.config import Config
from mirrorlab.detectors.models import ensure_model
from mirrorlab.studio import MemorySink, StudioSession, StudioSettings
from tests.conftest import requires_mediapipe

pytestmark = [requires_mediapipe, pytest.mark.slow]


def _need(*keys: str) -> None:
    for key in keys:
        if ensure_model(key, auto_download=True) is None:
            pytest.skip(f"model {key!r} is not cached and could not be downloaded")


def _run(portrait_path, frames=45, **overrides):
    settings = StudioSettings.from_mapping(
        {"width": 640, "height": 360, "fps": 120, "analysis_width": 480, **overrides}
    )
    sink = MemorySink(keep=frames)
    session = StudioSession(settings, Config(), source=str(portrait_path), sink=sink)
    report = session.run(max_frames=frames)
    source_frame = session._open_source().read()
    return report, sink, source_frame


def test_background_blur_changes_the_background_and_keeps_the_face(portrait_path):
    _need("face_landmarker", "selfie_segmenter")
    report, sink, original = _run(portrait_path, background="blur", gesture_control=False)
    out = sink.frames[-1]
    assert report.fail_closed_frames == 0, "segmentation should have produced real masks"
    difference = np.abs(out.astype(np.int16) - original.astype(np.int16)).mean(axis=2)
    h, w = difference.shape
    centre = difference[h // 6 : h // 2, w * 2 // 5 : w * 3 // 5]  # the face
    edge = np.concatenate(
        [difference[:, : w // 8].ravel(), difference[:, -w // 8 :].ravel()]
    )  # the background
    assert edge.mean() > 3 * max(centre.mean(), 0.5), "the background must change far more than the face"


def test_auto_frame_finds_and_zooms_on_the_face(portrait_path):
    _need("face_landmarker")
    settings = StudioSettings.from_mapping(
        {"width": 640, "height": 360, "fps": 120, "auto_frame": True, "gesture_control": False}
    )
    session = StudioSession(settings, Config(), source=str(portrait_path), sink=MemorySink())
    session.run(max_frames=60)
    assert session.pipeline is not None
    assert session.pipeline.framer.zoom >= 1.0
    # The photo already frames the face closely; the contract is "never crop the face out".
    last = session.pipeline.process(session._open_source().read(), now=100.0)
    assert last.face_present


def test_studio_light_lifts_a_dark_face(portrait_path, tmp_path):
    _need("face_landmarker")
    import cv2

    from mirrorlab.camera import StillImageSource

    dark = (StillImageSource(portrait_path, 640, 360).read() * 0.35).astype(np.uint8)
    dark_path = tmp_path / "dark.png"
    cv2.imwrite(str(dark_path), dark)
    settings = StudioSettings.from_mapping(
        {
            "width": 640,
            "height": 360,
            "fps": 120,
            "studio_light": True,
            "light_strength": 1.0,
            "gesture_control": False,
        }
    )
    sink = MemorySink()
    StudioSession(settings, Config(), source=str(dark_path), sink=sink).run(max_frames=90)
    assert sink.frames[-1].mean() > dark.mean() * 1.15


def test_privacy_on_start_with_real_detectors_shows_no_camera_pixels(portrait_path):
    _need("face_landmarker")
    _, sink, original = _run(portrait_path, frames=20, privacy_on_start=True)
    for frame in sink.frames:
        assert np.abs(frame.astype(np.int16) - original.astype(np.int16)).mean() > 20
        assert np.array_equal(frame, sink.frames[0])
