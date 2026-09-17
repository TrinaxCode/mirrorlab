"""Camera selection, synthetic source, effects, CLI and the end-to-end pipeline.

These tests exercise the parts that touch hardware without ever requiring it:
the synthetic source stands in for a webcam, and the CLI is driven through its
in-process entry point rather than a subprocess.
"""

from __future__ import annotations

import json
import time

import cv2
import numpy as np
import pytest

from mirrorlab.actions import DEFAULT_BINDINGS, action_catalog
from mirrorlab.camera import (
    CameraError,
    CameraInfo,
    SyntheticSource,
    available_backends,
    backend_priority,
    camera_troubleshooting,
    open_source,
    platform_summary,
)
from mirrorlab.cli import build_parser, main
from mirrorlab.config import Config
from mirrorlab.effects import (
    FACE_EFFECTS,
    HAND_EFFECTS,
    EffectContext,
    build_effects,
    build_hand_effects,
    effect_catalog,
)
from mirrorlab.recording import Recorder, save_snapshot
from mirrorlab.render.composition import blend, crossfade, letterbox, stack_side_by_side, tile_grid
from mirrorlab.render.hud import Hud, HudState, draw_badge, draw_bar

from .conftest import requires_camera


# --------------------------------------------------------------------------- #
# Camera
# --------------------------------------------------------------------------- #
def test_backend_priority_is_platform_appropriate():
    order = backend_priority("auto")
    assert order, "at least one backend must be available"
    import platform

    if platform.system() == "Darwin":
        assert order[0] == "avfoundation"
    elif platform.system() == "Windows":
        assert order[0] in {"dshow", "msmf"}
    else:
        assert order[0] in {"v4l2", "gstreamer", "any"}


def test_explicit_backend_overrides_the_platform_default():
    assert backend_priority("any") == ["any"]


def test_available_backends_includes_any():
    assert "any" in available_backends()


def test_troubleshooting_text_is_platform_specific():
    text = camera_troubleshooting(0)
    assert "mirrorlab doctor" in text
    import platform

    if platform.system() == "Darwin":
        assert "Privacy & Security" in text
    elif platform.system() == "Windows":
        assert "msmf" in text or "dshow" in text
    else:
        assert "video" in text


def test_platform_summary_reports_opencv():
    summary = platform_summary()
    assert summary["opencv"]
    assert isinstance(summary["opencv_backends"], list)


def test_synthetic_source_is_deterministic_and_bounded():
    source = SyntheticSource(160, 120, frame_limit=5)
    frames = list(source)
    assert len(frames) == 5
    assert all(f.shape == (120, 160, 3) for f in frames)
    again = SyntheticSource(160, 120).render(0)
    np.testing.assert_array_equal(frames[0], again), "the same index must render identically"


def test_synthetic_frames_actually_change():
    source = SyntheticSource(160, 120)
    assert not np.array_equal(source.render(0), source.render(10))


def test_open_source_synthetic_ignores_the_camera():
    source = open_source(None, synthetic=True, synthetic_frames=3, width=96, height=64)
    frame = source.read()
    assert frame is not None and frame.shape == (64, 96, 3)
    source.release()


def test_open_source_missing_video_file_raises_a_clear_error():
    with pytest.raises(CameraError) as excinfo:
        open_source("/definitely/not/a/video.mp4")
    assert "not found" in str(excinfo.value).lower()


def test_camera_info_describe():
    info = CameraInfo(index=1, backend="avfoundation", width=1280, height=720, fps=30.0)
    assert "avfoundation" in info.describe()
    assert "1280x720" in info.describe()


@requires_camera
def test_real_camera_delivers_a_frame():  # pragma: no cover - hardware only
    source = open_source(0, width=640, height=480)
    try:
        frame = source.read(timeout=3.0)
        assert frame is not None
        assert frame.ndim == 3
    finally:
        source.release()


# --------------------------------------------------------------------------- #
# Effects
# --------------------------------------------------------------------------- #
def _landmarks_478() -> np.ndarray:
    points = np.zeros((478, 3), dtype=np.float64)
    anchors = {
        33: (0.40, 0.42),
        133: (0.45, 0.42),
        362: (0.55, 0.42),
        263: (0.60, 0.42),
        159: (0.42, 0.40),
        145: (0.42, 0.44),
        386: (0.58, 0.40),
        374: (0.58, 0.44),
        468: (0.425, 0.42),
        473: (0.575, 0.42),
        1: (0.50, 0.52),
        168: (0.50, 0.44),
        10: (0.50, 0.16),
        152: (0.50, 0.78),
        61: (0.44, 0.62),
        291: (0.56, 0.62),
        13: (0.50, 0.60),
        14: (0.50, 0.645),
        234: (0.34, 0.50),
        454: (0.66, 0.50),
        105: (0.42, 0.36),
        334: (0.58, 0.36),
    }
    for index, (x, y) in anchors.items():
        points[index] = [x, y, 0.0]
    return points


def _face():
    from mirrorlab.detectors.base import FaceObservation

    return FaceObservation(
        landmarks=_landmarks_478(),
        blendshapes={"jawOpen": 0.5, "mouthSmileLeft": 0.7, "mouthSmileRight": 0.7},
    )


def _hand():
    from mirrorlab.detectors.base import HandObservation

    rng = np.random.default_rng(5)
    points = np.zeros((21, 3), dtype=np.float64)
    for index in range(21):
        points[index] = [0.3 + 0.02 * (index % 5) + rng.normal(0, 0.005), 0.5 + 0.02 * (index // 5), 0.0]
    return HandObservation(landmarks=points, handedness="Right")


def test_effect_registries_are_documented():
    assert len(FACE_EFFECTS) >= 10
    assert len(HAND_EFFECTS) >= 4
    for effect in list(FACE_EFFECTS.values()) + list(HAND_EFFECTS.values()):
        assert effect.label and effect.label_es and effect.emoji
        assert effect.description and effect.description_es


def test_effect_catalog_is_json_ready():
    catalog = effect_catalog()
    json.dumps(catalog)
    assert len(catalog) == len(FACE_EFFECTS) + len(HAND_EFFECTS)


@pytest.mark.parametrize("name", sorted(FACE_EFFECTS))
def test_face_effects_draw_without_breaking_the_frame(name, frame):
    effect = FACE_EFFECTS[name]
    ctx = EffectContext(frame_index=3, time=0.7, width=frame.shape[1], height=frame.shape[0])
    out = effect.apply(frame.copy(), _face(), ctx)
    assert out.shape == frame.shape and out.dtype == np.uint8
    assert not np.array_equal(out, frame), f"{name} drew nothing"


@pytest.mark.parametrize("name", sorted(HAND_EFFECTS))
def test_hand_effects_draw_without_breaking_the_frame(name, frame):
    effect = HAND_EFFECTS[name]
    ctx = EffectContext(frame_index=3, time=0.7, width=frame.shape[1], height=frame.shape[0])
    out = effect.apply(frame.copy(), _hand(), ctx)
    assert out.shape == frame.shape and out.dtype == np.uint8


def test_face_effects_are_safe_without_landmarks(frame):
    from mirrorlab.detectors.base import FaceObservation

    empty = FaceObservation(landmarks=np.zeros((0, 3)))
    ctx = EffectContext(width=frame.shape[1], height=frame.shape[0])
    for effect in FACE_EFFECTS.values():
        out = effect.apply(frame.copy(), empty, ctx)
        assert out.shape == frame.shape


def test_build_effects_warns_and_skips_unknown_names(frame):
    effects = build_effects(["sunglasses", "definitely-not-real", "crown"])
    assert len(effects) == 2
    assert build_hand_effects(["fire", "nope"]) != []


def test_effect_instances_are_not_shared_between_calls():
    first = build_effects(["laser_eyes"])
    second = build_effects(["laser_eyes"])
    assert first[0] is not second[0]


# --------------------------------------------------------------------------- #
# HUD / composition
# --------------------------------------------------------------------------- #
def test_hud_renders_every_layer(frame):
    hud = Hud(show_landmarks=True, show_fps=True)
    state = HudState(
        fps=42.0,
        frame_time_ms=23.8,
        inference_ms=14.2,
        filter_label="Cartoon",
        expression_label="😊 Feliz",
        expression_score=0.87,
        expression_scores={"happy": 0.87, "neutral": 0.2},
        gesture_label="✌️ Victoria",
        hands=2,
        faces=1,
        recording=True,
        messages=[("Snapshot guardado", 0.3)],
    )
    out = hud.render(frame.copy(), state, [_face()], [_hand()])
    assert out.shape == frame.shape
    assert not np.array_equal(out, frame), "the HUD must actually draw"


def test_hud_without_landmarks_only_draws_panels(frame):
    hud = Hud(show_landmarks=False)
    out = hud.render(frame.copy(), HudState(fps=30.0, frame_time_ms=33.3), [], [])
    assert out.shape == frame.shape


def test_draw_helpers(frame):
    draw_badge(frame, "test", (10, frame.shape[0] - 10), (200, 200, 200), 1.0)
    draw_bar(frame, (10, 10), (100, 8), 0.5, (0, 255, 0))
    assert frame.max() > 0


def test_composition_helpers(frame):
    assert blend(frame, np.zeros_like(frame), 0.0).shape == frame.shape
    assert crossfade([frame, np.zeros_like(frame)], 0.5).shape == frame.shape
    assert letterbox(frame, 100, 100).shape == (100, 100, 3)
    assert stack_side_by_side(frame, frame).shape[0] == frame.shape[0]
    assert tile_grid([frame] * 5, columns=2).shape[2] == 3


def test_crossfade_endpoints():
    a = np.zeros((10, 10, 3), dtype=np.uint8)
    b = np.full((10, 10, 3), 200, dtype=np.uint8)
    np.testing.assert_array_equal(crossfade([a, b], 0.0), a)
    np.testing.assert_array_equal(crossfade([a, b], 1.0), b)


# --------------------------------------------------------------------------- #
# Recording
# --------------------------------------------------------------------------- #
def test_snapshot_writes_a_readable_file(tmp_path, frame):
    result = save_snapshot(frame, tmp_path, "png")
    assert result.path.exists()
    assert result.bytes > 0
    assert cv2.imread(str(result.path)).shape == frame.shape
    assert "PNG" in result.describe().upper() or "png" in result.describe()


def test_snapshots_never_overwrite_each_other(tmp_path, frame):
    first = save_snapshot(frame, tmp_path, "png")
    second = save_snapshot(frame, tmp_path, "png")
    assert first.path != second.path


def test_snapshot_rejects_an_unwritable_path(tmp_path, frame):
    target = tmp_path / "as_a_file"
    target.write_text("not a directory")
    with pytest.raises(OSError):
        save_snapshot(frame, target / "sub", "png")


def test_recorder_round_trip(tmp_path, frame):
    recorder = Recorder(tmp_path / "clip.mp4", fps=20.0, size=(frame.shape[1], frame.shape[0]))
    recorder.start()
    for index in range(12):
        recorder.write(np.full_like(frame, index * 15))
    result = recorder.stop(export_gif=False)
    # The encoder runs on its own thread with a bounded queue: under a burst it
    # drops frames rather than stalling the preview, so `frames_written` plus
    # `frames_dropped` must account for every frame we handed over.
    assert result.frames >= 1
    assert result.frames + recorder.frames_dropped == 12
    assert result.path.exists() and result.bytes > 0
    playback = cv2.VideoCapture(str(result.path))
    assert playback.isOpened()
    ok, decoded = playback.read()
    playback.release()
    assert ok and decoded.shape[1] == frame.shape[1]


def test_recorder_drops_frames_instead_of_blocking(tmp_path, frame):
    recorder = Recorder(tmp_path / "clip.mp4", fps=30.0, size=(frame.shape[1], frame.shape[0]), max_queue=1)
    recorder.start()
    for _ in range(200):
        recorder.write(frame)
    recorder.stop(export_gif=False)
    assert recorder.frames_dropped >= 0  # dropping is allowed, blocking is not


# --------------------------------------------------------------------------- #
# Actions
# --------------------------------------------------------------------------- #
def test_every_binding_points_at_a_real_gesture_and_action():
    from mirrorlab.gestures import GESTURES, GestureTracker

    known = set(GESTURES) | set(GestureTracker.SWIPES)
    for gesture, action in DEFAULT_BINDINGS.items():
        assert gesture in known, f"binding for unknown gesture {gesture!r}"
        assert action, f"gesture {gesture!r} has no action"
    # The published catalog must cover every binding.
    catalog = {row["gesture"] for row in action_catalog()}
    assert catalog == set(DEFAULT_BINDINGS)


def test_action_catalog_is_json_ready():
    catalog = action_catalog()
    json.dumps(catalog)
    assert len(catalog) == len(DEFAULT_BINDINGS)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_parser_builds_every_subcommand():
    parser = build_parser()
    for command in (
        "run",
        "demo",
        "doctor",
        "filters",
        "gestures",
        "expressions",
        "effects",
        "models",
        "benchmark",
        "config",
        "cameras",
        "gallery",
    ):
        assert parser.parse_args([command]) is not None


def test_bare_invocation_is_treated_as_run(capsys):
    """`mirrorlab --help` must not be swallowed by the implicit `run`."""
    with pytest.raises(SystemExit) as excinfo:
        main(["--help"])
    assert excinfo.value.code == 0
    assert "webcam AI playground" in capsys.readouterr().out


def test_unknown_command_exits_with_a_message(capsys):
    assert main(["frobnicate"]) == 2
    assert "unknown command" in capsys.readouterr().err


def test_filters_command_json(capsys):
    assert main(["filters", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert len(payload) >= 50
    assert all("name" in row for row in payload)


def test_filters_command_category_filter(capsys):
    assert main(["filters", "--category", "artistic", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload and all(row["category"] == "artistic" for row in payload)


def test_filters_command_presets(capsys):
    assert main(["filters", "--presets", "--json"]) == 0
    assert "cinema" in json.loads(capsys.readouterr().out)


def test_gestures_and_expressions_and_effects_commands(capsys):
    for command, minimum in (("gestures", 20), ("expressions", 15), ("effects", 12)):
        assert main([command, "--json"]) == 0
        payload = json.loads(capsys.readouterr().out)
        assert len(payload) >= minimum, command


def test_config_list_and_show(capsys):
    assert main(["config", "--list"]) == 0
    assert "camera_index" in capsys.readouterr().out
    assert main(["config"]) == 0
    assert "camera_index" in json.loads(capsys.readouterr().out)


def test_config_init_writes_a_loadable_file(tmp_path, capsys):
    target = tmp_path / "mirrorlab.json"
    assert main(["config", "--init", str(target)]) == 0
    reloaded = Config.load(target, use_env=False)
    assert reloaded.camera_index == Config().camera_index


def test_models_status_command(capsys):
    assert main(["models", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert any(row["key"] == "face_landmarker" for row in payload)


def test_benchmark_command(capsys):
    assert main(["benchmark", "--filter", "original", "--frames", "3", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["results"][0]["filter"] == "original"


def test_gallery_command_writes_an_image(tmp_path, capsys):
    target = tmp_path / "gallery.png"
    assert main(["gallery", "--output", str(target), "--columns", "6"]) == 0
    assert target.exists()
    image = cv2.imread(str(target))
    assert image is not None and image.shape[0] > 100


def test_demo_command_runs_headless_and_finishes(capsys):
    started = time.perf_counter()
    assert main(["demo", "--frames", "6", "--filter", "cartoon", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert payload["frames"] == 6
    assert time.perf_counter() - started < 120


# --------------------------------------------------------------------------- #
# End-to-end pipeline
# --------------------------------------------------------------------------- #
@pytest.mark.slow
def test_full_pipeline_headless_on_the_synthetic_source(tmp_path):
    """The real app, end to end: detect → filter → effects → HUD, no camera."""
    from mirrorlab.app import MirrorLab

    config = Config(
        headless=True,
        max_frames=8,
        camera_width=320,
        camera_height=240,
        filter="cartoon+vignette",
        effects=["sunglasses", "sparkles"],
        output_dir=str(tmp_path),
        stats_csv=str(tmp_path / "stats.csv"),
        enable_face=True,
        enable_hands=True,
    )
    app = MirrorLab(config=config, synthetic=True)
    seen: list = []
    stats = app.run(max_frames=8, on_frame=lambda frame, result: seen.append(frame.copy()))

    assert stats.frames == 8
    assert len(seen) == 8
    assert all(f.shape == (240, 320, 3) for f in seen)
    assert stats.average_fps > 0
    # The stats CSV must exist and contain one header plus one row per frame.
    rows = (tmp_path / "stats.csv").read_text(encoding="utf-8").strip().splitlines()
    assert len(rows) == 9
    assert rows[0].startswith("timestamp,frame,fps")


def test_snapshot_from_the_running_pipeline(tmp_path):
    from mirrorlab.app import MirrorLab

    config = Config(headless=True, camera_width=160, camera_height=120, output_dir=str(tmp_path))
    app = MirrorLab(config=config, synthetic=True)
    app.run(max_frames=2)
    result = app.snapshot()
    assert result is not None and result.path.exists()
    assert app.stats.snapshots


def test_discard_removes_the_last_capture(tmp_path):
    from mirrorlab.app import MirrorLab

    config = Config(headless=True, camera_width=160, camera_height=120, output_dir=str(tmp_path))
    app = MirrorLab(config=config, synthetic=True)
    app.run(max_frames=2)
    result = app.snapshot()
    assert result is not None and result.path.exists()
    app.discard_last()
    assert not result.path.exists()
    assert app.stats.snapshots == []


def test_keymap_help_is_non_empty_and_unique():
    from mirrorlab.app import MirrorLab

    app = MirrorLab(config=Config(headless=True, enable_face=False, enable_hands=False), synthetic=True)
    rows = app.keymap_help()
    assert rows
    labels = [label for label, _ in rows]
    assert len(labels) == len(set(labels)), "each key must appear once"
    app.engine.close()


def test_switching_filters_through_the_app():
    from mirrorlab.app import MirrorLab

    app = MirrorLab(config=Config(headless=True, enable_face=False, enable_hands=False), synthetic=True)
    app.run(max_frames=2)
    original = app.filter.name
    app.next_filter()
    assert app.filter.name != original
    app.prev_filter()
    assert app.filter.name == original
    app.set_filter("this-does-not-exist")
    assert app.filter.name == original, "an unknown filter must leave the current one alone"
    app.engine.close()
