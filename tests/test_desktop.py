"""The desktop app: its preferences, its strings and the thread that runs the camera.

The window itself needs a display and is covered by ``-m gui`` tests; everything
that decides behaviour lives outside Tk so it can run on any machine.
"""

from __future__ import annotations

import json
import os
import time

import numpy as np
import pytest

from mirrorlab.desktop.prefs import DesktopPrefs
from mirrorlab.desktop.runner import StudioRunner
from mirrorlab.desktop.strings import LANGUAGES, STRINGS, detect_language, translate
from mirrorlab.studio.settings import StudioSettings
from mirrorlab.studio.vcam import MemorySink
from tests.test_studio_runtime import FakePerception, FakeSegmenter, make_settings


# --------------------------------------------------------------------------- #
# strings
# --------------------------------------------------------------------------- #
class TestStrings:
    def test_every_language_has_the_same_keys(self):
        reference = set(STRINGS["en"])
        for language in LANGUAGES:
            assert set(STRINGS[language]) == reference, language

    def test_no_string_is_empty(self):
        assert all(text.strip() for table in STRINGS.values() for text in table.values())

    def test_placeholders_match_between_languages(self):
        import string

        def fields(text: str) -> set:
            return {name for _, name, _, _ in string.Formatter().parse(text) if name}

        for key, english in STRINGS["en"].items():
            assert fields(STRINGS["es"][key]) == fields(english), key

    def test_translate_formats_values_and_falls_back(self):
        assert translate("es", "camera.n", n=2) == "Cámara 2"
        assert translate("xx", "camera.n", n=2) == "Camera 2"
        assert translate("en", "does.not.exist") == "does.not.exist"

    @pytest.mark.parametrize(
        ("value", "expected"), [("es_PE.UTF-8", "es"), ("en_US.UTF-8", "en"), ("fr_FR", "en")]
    )
    def test_language_follows_the_environment(self, monkeypatch, value, expected):
        for name in ("LC_ALL", "LC_MESSAGES", "LANGUAGE"):
            monkeypatch.delenv(name, raising=False)
        monkeypatch.setenv("LANG", value)
        assert detect_language() == expected


# --------------------------------------------------------------------------- #
# preferences
# --------------------------------------------------------------------------- #
class TestPrefs:
    def test_round_trip(self, tmp_path):
        path = tmp_path / "desktop.json"
        prefs = DesktopPrefs(language="en", camera=2, background="green", auto_frame=False, output="none")
        assert prefs.save(path)
        assert DesktopPrefs.load(path) == prefs

    def test_missing_file_means_defaults(self, tmp_path):
        assert DesktopPrefs.load(tmp_path / "nope.json") == DesktopPrefs()

    @pytest.mark.parametrize("content", ["", "{", "[]", "null", '"text"', "\x00\x01"])
    def test_corrupt_file_means_defaults(self, tmp_path, content):
        path = tmp_path / "desktop.json"
        path.write_text(content, encoding="utf-8")
        assert DesktopPrefs.load(path) == DesktopPrefs()

    def test_invalid_values_are_dropped_one_by_one(self, tmp_path):
        path = tmp_path / "desktop.json"
        path.write_text(
            json.dumps(
                {"camera": -1, "background": "rainbow", "auto_frame": "yes", "output": "tv", "language": "fr"}
            ),
            encoding="utf-8",
        )
        assert DesktopPrefs.load(path) == DesktopPrefs()

    def test_valid_fields_survive_next_to_invalid_ones(self, tmp_path):
        path = tmp_path / "desktop.json"
        path.write_text(
            json.dumps({"background": "green", "camera": "x", "studio_light": False}), encoding="utf-8"
        )
        loaded = DesktopPrefs.load(path)
        assert (loaded.background, loaded.studio_light, loaded.camera) == ("green", False, 0)

    def test_replace_without_an_image_falls_back_to_blur(self):
        assert DesktopPrefs.from_mapping({"background": "replace"}).background == "blur"
        kept = DesktopPrefs.from_mapping({"background": "replace", "background_image": "/tmp/a.png"})
        assert kept.background == "replace"

    def test_bool_is_not_accepted_as_a_camera_index(self):
        assert DesktopPrefs.from_mapping({"camera": True}).camera == 0

    def test_save_reports_failure_instead_of_raising(self, tmp_path):
        blocker = tmp_path / "file"
        blocker.write_text("x")
        assert DesktopPrefs().save(blocker / "desktop.json") is False

    def test_save_leaves_no_temp_files(self, tmp_path):
        DesktopPrefs().save(tmp_path / "desktop.json")
        assert sorted(p.name for p in tmp_path.iterdir()) == ["desktop.json"]

    @pytest.mark.skipif(os.name == "nt", reason="POSIX env var")
    def test_default_location_honours_xdg(self, tmp_path, monkeypatch):
        from mirrorlab.desktop.prefs import prefs_path

        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        assert prefs_path() == tmp_path / "mirrorlab" / "desktop.json"


# --------------------------------------------------------------------------- #
# runner
# --------------------------------------------------------------------------- #
def wait_for(predicate, timeout=8.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False


@pytest.fixture
def runner():
    instance = StudioRunner()
    yield instance
    instance.stop(timeout=5.0)


def start_fake(runner: StudioRunner, **kwargs):
    runner.start(
        make_settings(background="blur"),
        synthetic=True,
        sink=MemorySink(),
        perception=FakePerception(),
        segmenter=FakeSegmenter(),
        **kwargs,
    )


class TestRunner:
    def test_idle_runner_reports_nothing(self):
        idle = StudioRunner()
        assert not idle.running
        assert idle.latest_frame() == (0, None)
        assert idle.state() == {}
        assert idle.status() == {}
        assert idle.apply("privacy").ok is False

    def test_delivers_frames_and_stops_cleanly(self, runner):
        start_fake(runner)
        assert wait_for(lambda: runner.has_frame)
        sequence, frame = runner.latest_frame()
        assert isinstance(frame, np.ndarray) and frame.shape == (180, 320, 3)
        assert wait_for(lambda: runner.latest_frame()[0] > sequence)
        assert runner.stop(timeout=5.0)
        assert not runner.running
        assert runner.error is None

    def test_actions_reach_the_running_session(self, runner):
        start_fake(runner)
        assert wait_for(lambda: runner.has_frame)
        assert runner.apply("privacy").ok
        assert runner.state()["privacy"] is True
        assert wait_for(lambda: bool(runner.status()))
        assert runner.apply("background:green").ok
        assert runner.state()["background"] == "green"
        assert runner.apply("nonsense").ok is False

    def test_cannot_start_twice(self, runner):
        start_fake(runner)
        assert wait_for(lambda: runner.has_frame)
        with pytest.raises(RuntimeError):
            start_fake(runner)

    def test_can_start_again_after_stopping(self, runner):
        start_fake(runner)
        assert wait_for(lambda: runner.has_frame)
        assert runner.stop(timeout=5.0)
        start_fake(runner)
        assert wait_for(lambda: runner.has_frame)

    def test_a_missing_camera_surfaces_as_an_error_not_a_crash(self, runner, tmp_path):
        runner.start(
            make_settings(),
            camera=7,
            output="none",
            sink=MemorySink(),
            perception=FakePerception(),
            segmenter=FakeSegmenter(),
        )
        assert wait_for(lambda: not runner.running, timeout=20.0)
        assert runner.error
        assert runner.error_kind in {"camera", "unexpected"}

    def test_an_unopenable_output_is_reported_as_an_output_error(self, runner):
        from mirrorlab.studio.vcam import OutputError

        class BrokenSink:
            device = "broken"

            def open(self, width, height, fps):
                raise OutputError("no virtual camera device")

            def send(self, frame):  # pragma: no cover - never reached
                pass

            def close(self):
                pass

        runner.start(
            make_settings(),
            synthetic=True,
            sink=BrokenSink(),
            perception=FakePerception(),
            segmenter=FakeSegmenter(),
        )
        assert wait_for(lambda: not runner.running)
        assert runner.error_kind == "output"
        assert "no virtual camera device" in (runner.error or "")

    def test_a_starting_session_clears_the_previous_error(self, runner):
        from mirrorlab.studio.vcam import OutputError

        class BrokenSink:
            device = "broken"

            def open(self, width, height, fps):
                raise OutputError("nope")

            def send(self, frame):  # pragma: no cover
                pass

            def close(self):
                pass

        runner.start(
            make_settings(),
            synthetic=True,
            sink=BrokenSink(),
            perception=FakePerception(),
            segmenter=FakeSegmenter(),
        )
        assert wait_for(lambda: not runner.running)
        assert runner.error
        start_fake(runner)
        assert runner.error is None


def test_settings_built_by_the_window_are_valid():
    settings = StudioSettings.from_mapping(
        {"background": "green", "auto_frame": True, "studio_light": False, "gesture_control": False}
    )
    assert settings.background == "green" and settings.gesture_control is False


def test_the_cli_knows_the_desktop_command():
    from mirrorlab.cli import build_parser

    args = build_parser().parse_args(["desktop"])
    assert args.command == "desktop"
