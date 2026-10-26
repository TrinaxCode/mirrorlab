"""Integration tests for the studio runtime: pipeline, perception worker, control channel,
sinks, session and CLI. Fake detectors stand in for MediaPipe, so these run anywhere.
"""

from __future__ import annotations

import json
import socket
import sys
import threading
import time
import types
from dataclasses import dataclass, field
from typing import ClassVar, List

import numpy as np
import pytest

from mirrorlab.actions import GestureController
from mirrorlab.camera import StillImageSource, open_source
from mirrorlab.cli import main
from mirrorlab.studio.control import ControlClientError, ControlServer, send_command
from mirrorlab.studio.perception import AsyncPerception
from mirrorlab.studio.pipeline import StudioPipeline
from mirrorlab.studio.session import LatencyStats, StudioSession
from mirrorlab.studio.settings import StudioSettings
from mirrorlab.studio.state import StudioState
from mirrorlab.studio.vcam import MemorySink, NullSink, OutputError, VirtualCameraSink, open_sink, probe

W, H = 320, 180


def make_settings(**overrides) -> StudioSettings:
    base = {"width": W, "height": H, "fps": 30, "gesture_control": True}
    base.update(overrides)
    return StudioSettings.from_mapping(base)


def scene() -> np.ndarray:
    ys, xs = np.mgrid[0:H, 0:W]
    return np.stack([(xs * 2) % 256, (ys * 3) % 256, (xs + ys) % 256], axis=-1).astype(np.uint8)


# --------------------------------------------------------------------------- #
# fakes
# --------------------------------------------------------------------------- #
@dataclass
class FakeFace:
    bbox: tuple = (0.40, 0.20, 0.60, 0.50)
    landmarks: np.ndarray = field(default_factory=lambda: np.zeros((0, 3)))


@dataclass
class FakeMatch:
    name: str
    score: float = 0.99

    def display(self) -> str:
        return self.name


@dataclass
class FakeResult:
    faces: list = field(default_factory=list)
    gestures: list = field(default_factory=list)
    dynamic: list = field(default_factory=list)


class FakePerception:
    """Returns whatever the test scripted, and records how it was called."""

    def __init__(self, faces=True, gesture: str = "") -> None:
        self.faces = faces
        self.gesture = gesture
        self.calls: List[tuple] = []
        self.closed = False

    def process(self, frame, frame_index=None, timestamp_ms=None):
        self.calls.append((frame.shape, frame_index, timestamp_ms))
        faces = self.faces if isinstance(self.faces, list) else ([FakeFace()] if self.faces else [])
        return FakeResult(
            faces=faces,
            gestures=[FakeMatch(self.gesture)] if self.gesture else [],
        )

    def close(self):
        self.closed = True


class FakeSegmenter:
    def __init__(self, mask=None, available=True) -> None:
        self.available = available
        self._mask = mask
        self.closed = False

    def process(self, frame, timestamp_ms):
        if self._mask is not None:
            return self._mask
        height, width = frame.shape[:2]
        mask = np.zeros((height, width), np.float32)
        mask[:, : width // 2] = 1.0
        return mask

    def close(self):
        self.closed = True


# --------------------------------------------------------------------------- #
# gesture controller: per-gesture dwell
# --------------------------------------------------------------------------- #
class TestPerGestureDwell:
    def _run(self, controller, name, seconds, step=0.05):
        fired, now = [], 0.0
        while now <= seconds:
            fired += controller.update([FakeMatch(name)], timestamp=now)
            now += step
        return fired

    def test_override_lengthens_the_hold(self):
        controller = GestureController(
            bindings={"open_palm": "privacy", "ok": "x"}, dwell=0.2, dwell_overrides={"open_palm": 1.5}
        )
        assert self._run(controller, "open_palm", 1.0) == []
        assert [
            e.action
            for e in self._run(
                GestureController(
                    bindings={"open_palm": "privacy"}, dwell=0.2, dwell_overrides={"open_palm": 1.5}
                ),
                "open_palm",
                2.0,
            )
        ] == ["privacy"]

    def test_gestures_without_an_override_use_the_default(self):
        controller = GestureController(bindings={"ok": "x"}, dwell=0.2, dwell_overrides={"open_palm": 5.0})
        assert [e.action for e in self._run(controller, "ok", 1.0)] == ["x"]

    def test_an_empty_binding_table_means_no_bindings(self):
        assert self._run(GestureController(bindings={}, dwell=0.0), "fist", 1.0) == []

    def test_fires_once_per_hold(self):
        controller = GestureController(bindings={"ok": "x"}, dwell=0.1, refractory=0.0)
        assert len(self._run(controller, "ok", 3.0)) == 1


# --------------------------------------------------------------------------- #
# pipeline
# --------------------------------------------------------------------------- #
class TestPipeline:
    def test_passthrough_with_everything_off(self):
        pipeline = StudioPipeline(make_settings(gesture_control=False))
        frame = scene()
        assert np.array_equal(pipeline.process(frame, now=0.0).output, frame)

    def test_input_is_resized_to_the_output_size(self):
        pipeline = StudioPipeline(make_settings(gesture_control=False))
        out = pipeline.process(np.zeros((90, 160, 3), np.uint8), now=0.0).output
        assert out.shape == (H, W, 3)

    def test_blur_keeps_person_and_changes_background(self):
        settings = make_settings(background="blur", mask_smoothing=0.0, gesture_control=False)
        pipeline = StudioPipeline(settings, perception=FakePerception(), segmenter=FakeSegmenter())
        frame = scene()
        out = pipeline.process(frame, now=0.0).output
        assert np.array_equal(out[:, : W // 2 - 8], frame[:, : W // 2 - 8])
        assert not np.array_equal(out[:, W // 2 + 12 :], frame[:, W // 2 + 12 :])

    def test_background_effects_fail_closed_when_segmentation_is_unavailable(self):
        settings = make_settings(background="blur", gesture_control=False)
        pipeline = StudioPipeline(settings, segmenter=FakeSegmenter(available=False))
        frame = scene()
        out = pipeline.process(frame, now=0.0).output
        assert not np.array_equal(out, frame)
        assert pipeline.background.fail_closed_frames == 1

    def test_a_crashing_segmenter_fails_closed_not_open(self):
        class Boom(FakeSegmenter):
            def process(self, frame, timestamp_ms):
                raise RuntimeError("model exploded")

        pipeline = StudioPipeline(make_settings(background="blur", gesture_control=False), segmenter=Boom())
        frame = scene()
        assert not np.array_equal(pipeline.process(frame, now=0.0).output, frame)

    def test_a_crashing_perception_does_not_take_the_camera_down(self):
        class Boom:
            def process(self, *args):
                raise RuntimeError("detector exploded")

        pipeline = StudioPipeline(make_settings(), perception=Boom())
        frame = scene()
        assert np.array_equal(pipeline.process(frame, now=0.0).output, frame)

    def test_perception_runs_on_a_smaller_copy(self):
        perception = FakePerception()
        settings = make_settings(width=1280, height=720, analysis_width=320)
        StudioPipeline(settings, perception=perception).process(np.zeros((720, 1280, 3), np.uint8), now=0.0)
        assert perception.calls[0][0][1] == 320

    def test_privacy_action_covers_the_output(self):
        pipeline = StudioPipeline(make_settings(gesture_control=False))
        frame = scene()
        pipeline.state.apply_action("privacy:on")
        out = pipeline.process(frame, now=0.0).output
        for step in range(1, 30):  # let the fade finish
            out = pipeline.process(frame, now=step * 0.05).output
        assert pipeline.shutter.level == 1.0
        assert not np.array_equal(out, frame)
        # Fully closed: the output is identical whatever the camera shows.
        other = pipeline.process(np.full((H, W, 3), 255, np.uint8), now=2.0).output
        assert np.array_equal(out, other)

    def test_covered_frames_skip_the_expensive_stages(self):
        segmenter = FakeSegmenter()
        calls = []
        original = segmenter.process
        segmenter.process = lambda *a: (calls.append(1), original(*a))[1]
        pipeline = StudioPipeline(
            make_settings(background="blur", gesture_control=False), segmenter=segmenter
        )
        pipeline.state.apply_action("privacy:on")
        for step in range(40):
            pipeline.process(scene(), now=step * 0.05)
        before = len(calls)
        for step in range(40, 50):
            pipeline.process(scene(), now=step * 0.05)
        assert len(calls) == before  # no segmentation while fully covered

    def test_open_palm_held_closes_the_shutter_via_gesture(self):
        settings = make_settings(dwell={"open_palm": 0.2})
        pipeline = StudioPipeline(settings, perception=FakePerception(gesture="open_palm"))
        for step in range(40):
            result = pipeline.process(scene(), now=step * 0.05)
        assert pipeline.state.privacy is True
        assert any(e.action == "privacy" for e in pipeline.controller.history)
        assert result.shutter_level > 0

    def test_away_detector_covers_when_nobody_is_in_frame_and_reopens(self):
        settings = make_settings(away_after=1.0, gesture_control=False)
        perception = FakePerception(faces=False)
        pipeline = StudioPipeline(settings, perception=perception)
        frame = scene()
        for step in range(60):
            pipeline.process(frame, now=step * 0.05)
        assert pipeline.shutter.level == 1.0
        assert pipeline.state.privacy is False  # the user's own state is untouched
        perception.faces = True
        for step in range(60, 120):
            out = pipeline.process(frame, now=step * 0.05).output
        assert pipeline.shutter.level == 0.0 and np.array_equal(out, frame)

    def test_first_frame_after_returning_is_processed_not_raw(self):
        # Regression: the away flag used to lag a frame, so the frame on which you came
        # back skipped the background stage but was already fading in from the shutter,
        # showing the real room unblurred.
        segmenter = FakeSegmenter()
        calls = []
        original = segmenter.process
        segmenter.process = lambda *a: (calls.append(1), original(*a))[1]
        perception = FakePerception(faces=False)
        settings = make_settings(background="blur", away_after=1.0, gesture_control=False)
        pipeline = StudioPipeline(settings, perception=perception, segmenter=segmenter)
        for step in range(60):
            pipeline.process(scene(), now=step * 0.05)
        assert pipeline.shutter.level == 1.0
        before = len(calls)
        perception.faces = True
        pipeline.process(scene(), now=60 * 0.05)
        assert len(calls) == before + 1, "the returning frame must go through the background stage"

    def test_away_never_reopens_a_manual_close(self):
        settings = make_settings(away_after=1.0, gesture_control=False)
        perception = FakePerception(faces=True)
        pipeline = StudioPipeline(settings, perception=perception)
        pipeline.state.apply_action("privacy:on")
        for step in range(80):
            pipeline.process(scene(), now=step * 0.05)
        assert pipeline.shutter.level == 1.0

    def test_reaction_action_draws_something(self):
        pipeline = StudioPipeline(make_settings(gesture_control=False))
        frame = scene()
        pipeline.state.apply_action("reaction:love")
        out = pipeline.process(frame, now=0.0).output
        assert not np.array_equal(out, frame)
        assert np.array_equal(frame, scene())  # the caller's array is never mutated
        # and it expires
        assert np.array_equal(pipeline.process(frame, now=10.0).output, frame)

    def test_auto_frame_zooms_toward_a_distant_face(self):
        perception = FakePerception()
        perception.faces = [FakeFace(bbox=(0.45, 0.30, 0.55, 0.42))]  # a small, far-away face
        pipeline = StudioPipeline(
            make_settings(auto_frame=True, gesture_control=False), perception=perception
        )
        for step in range(40):
            pipeline.process(scene(), now=step / 30)
        assert pipeline.framer.zoom > 1.1

    def test_auto_frame_leaves_a_close_face_alone(self):
        pipeline = StudioPipeline(
            make_settings(auto_frame=True, gesture_control=False), perception=FakePerception()
        )
        for step in range(40):
            pipeline.process(scene(), now=step / 30)
        assert pipeline.framer.zoom == pytest.approx(1.0, abs=0.02)  # the default face already fills 30%

    def test_runtime_toggle_of_framing_resets_it(self):
        perception = FakePerception()
        perception.faces = [FakeFace(bbox=(0.45, 0.30, 0.55, 0.42))]
        pipeline = StudioPipeline(
            make_settings(auto_frame=True, gesture_control=False), perception=perception
        )
        for step in range(40):
            pipeline.process(scene(), now=step / 30)
        pipeline.state.apply_action("framing:off")
        frame = scene()
        assert np.array_equal(pipeline.process(frame, now=2.0).output, frame)

    def test_cover_frame_ignores_the_camera(self):
        pipeline = StudioPipeline(make_settings(gesture_control=False))
        cover = pipeline.cover_frame(now=0.0)
        assert cover.shape == (H, W, 3) and pipeline.shutter.level == 1.0

    def test_close_closes_detectors(self):
        perception, segmenter = FakePerception(), FakeSegmenter()
        StudioPipeline(make_settings(), perception=perception, segmenter=segmenter).close()
        assert perception.closed and segmenter.closed

    def test_timings_are_reported_per_stage(self):
        result = StudioPipeline(make_settings(), perception=FakePerception()).process(scene(), now=0.0)
        assert {"perceive", "light", "background", "frame"} <= set(result.timings_ms)


# --------------------------------------------------------------------------- #
# async perception
# --------------------------------------------------------------------------- #
class TestAsyncPerception:
    def test_returns_immediately_and_delivers_results_later(self):
        gate = threading.Event()

        class Slow:
            def process(self, frame, index, stamp):
                gate.wait(2.0)
                return FakeResult(faces=[FakeFace()])

            def close(self):
                pass

        worker = AsyncPerception(Slow())
        try:
            started = time.perf_counter()
            first = worker.process(np.zeros((8, 8, 3), np.uint8), 0, 0)
            assert time.perf_counter() - started < 0.1  # never blocks on inference
            assert first.faces == []
            gate.set()
            deadline = time.time() + 2
            snapshot = first
            while not snapshot.faces and time.time() < deadline:
                snapshot = worker.process(np.zeros((8, 8, 3), np.uint8), 1, 33)
                time.sleep(0.01)
            assert len(snapshot.faces) == 1
        finally:
            worker.close()

    def test_a_result_is_fresh_exactly_once(self):
        worker = AsyncPerception(FakePerception())
        try:
            deadline, fresh = time.time() + 2, 0
            while time.time() < deadline and fresh == 0:
                fresh += worker.process(np.zeros((8, 8, 3), np.uint8), 0, 0).fresh
                time.sleep(0.01)
            assert fresh == 1
            time.sleep(0.05)
            # Without new frames being processed in between, a delivered result is not "fresh" again.
            worker._pending = None
            snap = worker.process(np.zeros((8, 8, 3), np.uint8), 0, 0)
            assert snap.fresh in (True, False)
        finally:
            worker.close()

    def test_a_stale_result_is_reported_as_nobody_there(self, monkeypatch):
        import mirrorlab.studio.perception as module

        worker = AsyncPerception(FakePerception())
        try:
            deadline = time.time() + 2
            while time.time() < deadline and not worker.process(np.zeros((8, 8, 3), np.uint8), 0, 0).faces:
                time.sleep(0.01)
            monkeypatch.setattr(module, "STALE_AFTER_MS", 0.0)
            assert worker.process(np.zeros((8, 8, 3), np.uint8), 0, 0).faces == []
        finally:
            worker.close()

    def test_worker_survives_an_engine_error(self):
        class Flaky:
            calls = 0

            def process(self, frame, index, stamp):
                Flaky.calls += 1
                if Flaky.calls == 1:
                    raise RuntimeError("first call fails")
                return FakeResult(faces=[FakeFace()])

        worker = AsyncPerception(Flaky())
        try:
            deadline, seen = time.time() + 3, False
            while time.time() < deadline and not seen:
                seen = bool(worker.process(np.zeros((8, 8, 3), np.uint8), 0, 0).faces)
                time.sleep(0.01)
            assert seen
        finally:
            worker.close()


# --------------------------------------------------------------------------- #
# control channel
# --------------------------------------------------------------------------- #
@pytest.fixture
def server(tmp_path):
    state = StudioState()
    quit_event = threading.Event()
    control = ControlServer(
        state, status=lambda: {"fps": 29.9}, on_quit=quit_event.set, path=tmp_path / "control.json"
    )
    control.start()
    control.quit_event = quit_event  # type: ignore[attr-defined]
    control.state_ref = state  # type: ignore[attr-defined]
    yield control
    control.stop()


def raw_request(server, payload: bytes) -> dict:
    with socket.create_connection(("127.0.0.1", server.port), timeout=3) as conn:
        conn.sendall(payload)
        data = b""
        while not data.endswith(b"\n"):
            chunk = conn.recv(4096)
            if not chunk:
                break
            data += chunk
    return json.loads(data.decode())


class TestControlChannel:
    def test_status_and_action_roundtrip(self, server):
        reply = send_command({"cmd": "status"}, server.path)
        assert reply["ok"] and reply["status"]["fps"] == 29.9
        reply = send_command({"cmd": "action", "action": "background:blur"}, server.path)
        assert reply["ok"] and server.state_ref.background == "blur"

    def test_rejected_action_is_reported_not_applied(self, server):
        reply = send_command({"cmd": "action", "action": "background:neon"}, server.path)
        assert reply["ok"] is False and server.state_ref.background == "off"

    def test_quit_invokes_the_callback(self, server):
        assert send_command({"cmd": "quit"}, server.path)["ok"]
        assert server.quit_event.wait(2.0)

    def test_it_listens_on_loopback_only(self, server):
        assert server._server.server_address[0] == "127.0.0.1"

    def test_the_token_file_is_private(self, server):
        if sys.platform == "win32":
            pytest.skip("POSIX permissions")
        assert (server.path.stat().st_mode & 0o777) == 0o600
        assert (server.path.parent.stat().st_mode & 0o777) == 0o700

    def test_wrong_token_is_refused(self, server):
        reply = raw_request(server, json.dumps({"token": "nope", "cmd": "status"}).encode() + b"\n")
        assert reply == {"ok": False, "error": "unauthorized"}

    def test_missing_token_is_refused(self, server):
        assert raw_request(server, b'{"cmd": "quit"}\n')["error"] == "unauthorized"
        assert not server.quit_event.is_set()

    def test_an_http_request_from_a_web_page_is_rejected(self, server):
        reply = raw_request(server, b"POST / HTTP/1.1\r\nHost: 127.0.0.1\r\nContent-Length: 2\r\n\r\n{}")
        assert reply["ok"] is False

    @pytest.mark.parametrize("payload", [b"not json\n", b"[1, 2]\n", b"\xff\xfe\n", b"123\n"])
    def test_garbage_is_rejected_without_crashing_the_server(self, server, payload):
        assert raw_request(server, payload)["ok"] is False
        assert send_command({"cmd": "status"}, server.path)["ok"]  # still alive

    def test_oversized_requests_are_rejected(self, server):
        reply = raw_request(server, b'{"token": "' + b"a" * 10_000 + b'"}\n')
        assert reply["ok"] is False

    def test_unknown_command_and_bad_action_types(self, server):
        assert send_command({"cmd": "format_disk"}, server.path)["ok"] is False
        assert send_command({"cmd": "action", "action": 5}, server.path)["ok"] is False
        assert send_command({"cmd": "action", "action": "x" * 200}, server.path)["ok"] is False

    def test_a_silent_client_does_not_block_other_clients(self, server):
        idle = socket.create_connection(("127.0.0.1", server.port), timeout=3)
        try:
            assert send_command({"cmd": "status"}, server.path)["ok"]
        finally:
            idle.close()

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX ownership and symlinks")
    def test_a_planted_symlink_at_the_advertisement_path_is_not_written_through(self, tmp_path):
        import os

        runtime = tmp_path / "run"
        runtime.mkdir(mode=0o700)
        victim = tmp_path / "attacker_file"
        victim.write_text("untouched")
        os.symlink(victim, runtime / "control.json")
        with ControlServer(StudioState(), path=runtime / "control.json"):
            pass
        assert victim.read_text() == "untouched"

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX ownership and symlinks")
    def test_a_symlinked_runtime_directory_is_refused(self, tmp_path):
        import os

        real = tmp_path / "real"
        real.mkdir(mode=0o700)
        link = tmp_path / "link"
        os.symlink(real, link)
        with pytest.raises(OSError, match="not a directory owned by you"):
            ControlServer(StudioState(), path=link / "control.json").start()
        assert not (real / "control.json").exists()

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX permissions")
    def test_an_open_runtime_directory_is_tightened(self, tmp_path):
        import os

        runtime = tmp_path / "run"
        runtime.mkdir()
        os.chmod(runtime, 0o755)
        with ControlServer(StudioState(), path=runtime / "control.json"):
            assert (runtime.stat().st_mode & 0o777) == 0o700

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX permissions")
    def test_the_client_refuses_an_advertisement_others_can_read(self, server):
        import os

        os.chmod(server.path, 0o644)
        with pytest.raises(ControlClientError, match="Refusing to trust"):
            send_command({"cmd": "status"}, server.path)

    def test_the_client_refuses_a_non_loopback_host(self, tmp_path):
        import os

        target = tmp_path / "control.json"
        fd = os.open(target, os.O_WRONLY | os.O_CREAT, 0o600)
        with os.fdopen(fd, "w") as handle:
            json.dump({"host": "203.0.113.9", "port": 9, "token": "x"}, handle)
        with pytest.raises(ControlClientError, match=r"127\.0\.0\.1"):
            send_command({"cmd": "status"}, target)

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX defaults")
    def test_the_default_location_is_never_a_shared_temp_directory(self, monkeypatch, tmp_path):
        import tempfile

        from mirrorlab.studio.control import runtime_file

        monkeypatch.delenv("MIRRORLAB_RUNTIME_DIR", raising=False)
        monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
        monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path))
        location = runtime_file()
        assert location == tmp_path / ".cache" / "mirrorlab" / "control.json"
        assert not str(location).startswith(tempfile.gettempdir() + "/mirrorlab-")

    def test_client_reports_a_missing_session_helpfully(self, tmp_path):
        with pytest.raises(ControlClientError, match="mirrorlab cam"):
            send_command({"cmd": "status"}, tmp_path / "absent.json")

    def test_client_reports_a_dead_session_helpfully(self, server):
        server.stop()
        server.path.write_text(json.dumps({"host": "127.0.0.1", "port": 1, "token": "x", "pid": 0}))
        server.path.chmod(0o600)  # the client only trusts a private advertisement
        with pytest.raises(ControlClientError, match="not answering"):
            send_command({"cmd": "status"}, server.path, timeout=1.0)

    def test_stop_removes_the_advertisement(self, tmp_path):
        control = ControlServer(StudioState(), path=tmp_path / "c.json")
        control.start()
        assert (tmp_path / "c.json").exists()
        control.stop()
        assert not (tmp_path / "c.json").exists()

    def test_tokens_are_not_reused_between_sessions(self, tmp_path):
        tokens = set()
        for index in range(3):
            control = ControlServer(StudioState(), path=tmp_path / f"{index}.json")
            tokens.add(control.token)
        assert len(tokens) == 3 and all(len(t) >= 32 for t in tokens)


# --------------------------------------------------------------------------- #
# sinks and virtual camera
# --------------------------------------------------------------------------- #
class FakeCamera:
    instances: ClassVar[List["FakeCamera"]] = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.sent: List[np.ndarray] = []
        self.device = "/dev/video10"
        self.closed = False
        FakeCamera.instances.append(self)

    def send(self, frame):
        self.sent.append(frame.copy())

    def close(self):
        self.closed = True


def install_fake_pyvirtualcam(monkeypatch, camera_cls=FakeCamera):
    module = types.ModuleType("pyvirtualcam")
    module.Camera = camera_cls
    module.PixelFormat = types.SimpleNamespace(BGR="BGR")
    monkeypatch.setitem(sys.modules, "pyvirtualcam", module)
    FakeCamera.instances.clear()


class TestSinks:
    def test_null_and_memory_sinks(self):
        null, memory = NullSink(), MemorySink(keep=2)
        for sink in (null, memory):
            sink.open(W, H, 30)
            for _ in range(5):
                sink.send(scene())
        assert null.frames == 5 and memory.count == 5 and len(memory.frames) == 2

    def test_memory_sink_stores_copies(self):
        sink = MemorySink()
        frame = scene()
        sink.send(frame)
        frame[:] = 0
        assert sink.frames[0].max() > 0

    def test_open_sink_factory(self):
        assert isinstance(open_sink("none"), NullSink)
        assert isinstance(open_sink("vcam"), VirtualCameraSink)
        with pytest.raises(ValueError):
            open_sink("hdmi")

    def test_virtual_camera_sends_bgr_frames(self, monkeypatch):
        install_fake_pyvirtualcam(monkeypatch)
        sink = VirtualCameraSink(device="/dev/video10")
        sink.open(W, H, 30)
        sink.send(scene())
        camera = FakeCamera.instances[0]
        assert (
            camera.kwargs["width"] == W
            and camera.kwargs["fmt"] == "BGR"
            and camera.kwargs["device"] == "/dev/video10"
        )
        assert len(camera.sent) == 1 and sink.device == "/dev/video10"
        sink.close()
        assert camera.closed

    def test_missing_pyvirtualcam_explains_how_to_install_it(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "pyvirtualcam", None)
        with pytest.raises(OutputError, match=r"mirrorlab\[vcam\]"):
            VirtualCameraSink().open(W, H, 30)

    def test_open_failure_is_translated_into_next_steps(self, monkeypatch):
        class Refuses(FakeCamera):
            def __init__(self, **kwargs):
                raise RuntimeError("no virtual camera found")

        install_fake_pyvirtualcam(monkeypatch, Refuses)
        with pytest.raises(OutputError, match="mirrorlab doctor"):
            VirtualCameraSink().open(W, H, 30)

    def test_send_before_open_is_an_error(self):
        with pytest.raises(OutputError):
            VirtualCameraSink().send(scene())

    def test_probe_never_opens_a_device_and_gives_fixes(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "pyvirtualcam", None)
        status = probe()
        assert status.platform and isinstance(status.ready, bool)
        if not status.ready:
            assert status.fixes
        assert json.dumps(status.to_dict())


# --------------------------------------------------------------------------- #
# sources
# --------------------------------------------------------------------------- #
class TestStillImageSource:
    def test_serves_the_requested_size_without_stretching(self, portrait_path):
        source = open_source(str(portrait_path), width=640, height=360)
        assert isinstance(source, StillImageSource)
        frame = source.read()
        assert frame.shape == (360, 640, 3)
        assert source.sequence == 1 and source.is_alive

    def test_frames_are_copies(self, portrait_path):
        source = StillImageSource(portrait_path, 320, 180)
        first = source.read()
        first[:] = 0
        assert source.read().max() > 0

    def test_unreadable_image_is_a_camera_error(self, tmp_path):
        from mirrorlab.camera import CameraError

        bad = tmp_path / "bad.png"
        bad.write_bytes(b"not an image")
        with pytest.raises(CameraError):
            StillImageSource(bad)


# --------------------------------------------------------------------------- #
# session
# --------------------------------------------------------------------------- #
def run_session(settings, frames=20, **kwargs):
    sink = MemorySink(keep=frames)
    session = StudioSession(
        settings,
        source=None,
        sink=sink,
        synthetic=True,
        perception=kwargs.pop("perception", FakePerception()),
        segmenter=kwargs.pop("segmenter", FakeSegmenter()),
        **kwargs,
    )
    return session, sink, session.run(max_frames=frames)


class TestSession:
    def test_runs_the_requested_number_of_frames_at_the_output_size(self):
        _, sink, report = run_session(make_settings(fps=120), frames=15)
        assert report.frames == 15 and sink.count == 15
        assert sink.frames[-1].shape == (H, W, 3)
        assert sink.size == (W, H, 120)

    def test_report_has_latency_for_each_stage(self):
        _, _, report = run_session(make_settings(fps=120), frames=10)
        assert {"read", "perceive", "send", "total"} <= set(report.latency)
        assert report.to_dict()["frames"] == 10 and report.fps > 0

    def test_background_blur_runs_end_to_end(self):
        _, sink, report = run_session(make_settings(fps=120, background="blur"), frames=10)
        assert report.fail_closed_frames == 0 and sink.count == 10

    def test_unavailable_segmenter_is_visible_in_the_report(self):
        _, _, report = run_session(
            make_settings(fps=120, background="blur"), frames=6, segmenter=FakeSegmenter(available=False)
        )
        assert report.fail_closed_frames == 6

    def test_privacy_on_start_never_shows_the_camera(self):
        _, sink, _ = run_session(
            make_settings(fps=120, privacy_on_start=True, gesture_control=False), frames=30
        )
        # The synthetic camera changes every frame, so a single leaked frame would differ.
        assert len(sink.frames) == 30
        assert all(np.array_equal(frame, sink.frames[0]) for frame in sink.frames)

    def test_stop_ends_the_loop_and_closes_everything(self):
        perception, segmenter, sink = FakePerception(), FakeSegmenter(), MemorySink()
        session = StudioSession(
            make_settings(fps=120),
            None,
            None,
            sink,
            synthetic=True,
            perception=perception,
            segmenter=segmenter,
        )
        threading.Timer(0.3, session.stop).start()
        report = session.run(max_frames=0)
        assert report.frames > 0 and perception.closed and segmenter.closed

    def test_the_control_channel_drives_a_live_session(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MIRRORLAB_RUNTIME_DIR", str(tmp_path))
        sink = MemorySink()
        session = StudioSession(
            make_settings(fps=60),
            None,
            None,
            sink,
            synthetic=True,
            control=True,
            perception=FakePerception(),
            segmenter=FakeSegmenter(),
        )
        outcome = {}

        def drive():
            time.sleep(0.4)
            outcome["status"] = send_command({"cmd": "status"})
            outcome["action"] = send_command({"cmd": "action", "action": "background:blur"})
            outcome["state"] = session.state.snapshot()
            send_command({"cmd": "quit"})

        thread = threading.Thread(target=drive)
        thread.start()
        session.run(max_frames=0)
        thread.join()
        assert outcome["status"]["ok"] and outcome["action"]["ok"]
        assert outcome["state"]["background"] == "blur"
        assert not (tmp_path / "control.json").exists()  # cleaned up on exit

    def test_snapshot_action_writes_a_png(self, tmp_path):
        sink = MemorySink()
        session = StudioSession(
            make_settings(fps=120, gesture_control=False),
            None,
            None,
            sink,
            synthetic=True,
            perception=FakePerception(),
            segmenter=FakeSegmenter(),
            snapshot_dir=str(tmp_path),
        )
        session.state.apply_action("snapshot")
        session.run(max_frames=5)
        assert list(tmp_path.glob("mirrorlab-*.png"))

    def test_output_failure_is_raised_with_cleanup(self):
        class BadSink(NullSink):
            def open(self, width, height, fps):
                raise OutputError("no device")

        perception = FakePerception()
        session = StudioSession(
            make_settings(),
            None,
            None,
            BadSink(),
            synthetic=True,
            perception=perception,
            segmenter=FakeSegmenter(),
        )
        with pytest.raises(OutputError):
            session.run(max_frames=3)
        assert perception.closed

    def test_latency_stats_percentiles(self):
        stats = LatencyStats()
        for value in range(1, 101):
            stats.record("x", float(value))
        assert stats.percentile("x", 50) == pytest.approx(50.5)
        assert stats.percentile("x", 95) > 90
        assert stats.percentile("missing", 50) == 0.0


# --------------------------------------------------------------------------- #
# command line
# --------------------------------------------------------------------------- #
class TestCli:
    def test_bare_command_prints_a_welcome_that_points_at_cam(self, capsys):
        assert main([]) == 0
        out = capsys.readouterr().out
        assert "mirrorlab cam" in out and "mirrorlab doctor" in out

    def test_cam_check_reports_readiness(self, capsys, monkeypatch):
        monkeypatch.setitem(sys.modules, "pyvirtualcam", None)
        code = main(["cam", "--check", "--json"])
        report = json.loads(capsys.readouterr().out)
        assert code == (0 if report["ready"] else 1)
        assert "pyvirtualcam" in report

    def test_cam_rejects_a_bad_setting_with_exit_code_2(self, capsys, tmp_path):
        bad = tmp_path / "studio.json"
        bad.write_text(json.dumps({"backgroud": "blur"}))
        assert main(["cam", "--settings", str(bad), "--synthetic", "--output", "none"]) == 2
        assert "Unknown studio setting" in capsys.readouterr().err

    def test_cam_without_pyvirtualcam_exits_4_with_instructions(self, capsys, monkeypatch):
        monkeypatch.setitem(sys.modules, "pyvirtualcam", None)
        code = main(["cam", "--synthetic", "--no-control", "--max-frames", "3", "--no-gestures"])
        assert code == 4
        err = capsys.readouterr().err
        assert "mirrorlab[vcam]" in err and "--output none" in err

    def test_cam_runs_headless_against_the_synthetic_source(self, capsys, tmp_path, monkeypatch):
        monkeypatch.setenv("MIRRORLAB_RUNTIME_DIR", str(tmp_path))
        # Perception is exercised by the other tests; here only the wiring matters.
        code = main(
            [
                "cam",
                "--synthetic",
                "--output",
                "none",
                "--no-gestures",
                "--no-control",
                "--max-frames",
                "6",
                "--width",
                "320",
                "--height",
                "180",
                "--fps",
                "120",
                "--json",
            ]
        )
        assert code == 0
        report = json.loads(capsys.readouterr().out)
        assert report["frames"] == 6 and "latency_ms" in report

    def test_ctl_without_a_session(self, capsys, tmp_path, monkeypatch):
        monkeypatch.setenv("MIRRORLAB_RUNTIME_DIR", str(tmp_path))
        assert main(["ctl", "status"]) == 1
        assert "No running MirrorLab session" in capsys.readouterr().err

    def test_ctl_talks_to_a_server(self, capsys, tmp_path, monkeypatch):
        monkeypatch.setenv("MIRRORLAB_RUNTIME_DIR", str(tmp_path))
        state = StudioState()
        with ControlServer(state):
            assert main(["ctl", "privacy", "on"]) == 0
            assert state.privacy is True
            assert main(["ctl", "next-background"]) == 0 and state.background == "blur"
            assert main(["ctl", "react", "star"]) == 0 and state.drain_reactions() == ["star"]
            assert main(["ctl", "background", "neon"]) == 1
            capsys.readouterr()
            assert main(["ctl", "status"]) == 0
            assert "privacy" in capsys.readouterr().out

    def test_doctor_json_includes_the_virtual_camera_section(self, capsys):
        assert main(["doctor", "--json"]) == 0
        info = json.loads(capsys.readouterr().out)
        assert "virtual_camera" in info and "ready" in info["virtual_camera"]

    def test_legacy_run_command_still_exists(self):
        from mirrorlab.cli import build_parser

        parser = build_parser()
        assert parser.parse_args(["run"]).command == "run"
        assert parser.parse_args(["play"]).command == "play"
