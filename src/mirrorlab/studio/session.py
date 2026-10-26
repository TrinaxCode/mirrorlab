"""A running studio: camera in, virtual camera out, until told to stop.

The session owns everything with a lifetime: the capture source, the perception
engine, the output sink, the control channel and the optional preview window. It
is written around three operational rules:

1. **Steady output.** Video-call apps treat a virtual camera that stops sending
   as a frozen or dead camera. The session keeps sending at the target frame
   rate; if no new camera frame has arrived it repeats the last output.
2. **No silent freeze.** If the camera stalls, the output becomes the privacy
   cover (not the last picture of you), and the session tries to reopen the
   camera until it is back or the user stops it.
3. **Clean shutdown.** Ctrl-C, SIGTERM, ``ctl quit`` and ``q`` in the preview
   all end the loop through the same path, which releases the camera, closes
   the virtual device and removes the control file.
"""

from __future__ import annotations

import signal
import threading
import time
from collections import defaultdict, deque
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional, Tuple

import cv2
import numpy as np

from ..camera import CameraError, open_source
from ..config import Config
from ..utils.logging import get_logger
from .control import ControlServer
from .perception import AsyncPerception
from .pipeline import FrameResult, StudioPipeline
from .settings import StudioSettings
from .state import StudioState
from .vcam import FrameSink, NullSink, OutputError

__all__ = ["LatencyStats", "SessionReport", "StudioSession"]

log = get_logger("studio.session")

#: Seconds without a new camera frame before the output switches to the cover.
STALL_SECONDS = 1.5
#: Seconds between attempts to reopen a lost camera.
REOPEN_INTERVAL = 3.0


class LatencyStats:
    """Rolling per-stage timings with percentiles. Cheap enough to leave on."""

    def __init__(self, window: int = 600) -> None:
        self._samples: Dict[str, Deque[float]] = defaultdict(lambda: deque(maxlen=window))

    def record(self, stage: str, milliseconds: float) -> None:
        self._samples[stage].append(float(milliseconds))

    def percentile(self, stage: str, q: float) -> float:
        samples = self._samples.get(stage)
        if not samples:
            return 0.0
        return float(np.percentile(np.fromiter(samples, dtype=np.float64), q))

    def summary(self) -> Dict[str, Dict[str, float]]:
        return {
            stage: {"p50": round(self.percentile(stage, 50), 2), "p95": round(self.percentile(stage, 95), 2)}
            for stage in self._samples
        }


@dataclass
class SessionReport:
    """What happened during a session. ``mirrorlab cam --report`` prints this."""

    frames: int = 0
    seconds: float = 0.0
    repeated: int = 0
    camera_frames: int = 0
    stalls: int = 0
    fail_closed_frames: int = 0
    device: str = ""
    latency: Dict[str, Dict[str, float]] = field(default_factory=dict)

    @property
    def fps(self) -> float:
        return self.frames / self.seconds if self.seconds > 0 else 0.0

    @property
    def camera_fps(self) -> float:
        """Distinct frames the camera delivered per second (not the output rate)."""
        return self.camera_frames / self.seconds if self.seconds > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "frames": self.frames,
            "seconds": round(self.seconds, 2),
            "fps": round(self.fps, 2),
            "camera_fps": round(self.camera_fps, 2),
            "repeated_frames": self.repeated,
            "camera_stalls": self.stalls,
            "fail_closed_frames": self.fail_closed_frames,
            "device": self.device,
            "latency_ms": self.latency,
        }


class StudioSession:
    """Run the studio until stopped.

    Args:
        settings: Validated studio settings.
        config: General MirrorLab config (camera index, resolution, detector thresholds).
        source: Camera index, video file or image path. ``None`` means camera 0.
        sink: Where output frames go. Defaults to a :class:`NullSink`.
        preview: Show a local window with the output and a small status bar.
        control: Start the local control channel for ``mirrorlab ctl``.
        synthetic: Use the built-in synthetic source instead of a camera.
        perception: Inject a perception engine (tests). ``None`` builds the real one.
        segmenter: Inject a segmenter (tests). ``None`` builds the real one.
    """

    def __init__(
        self,
        settings: StudioSettings,
        config: Optional[Config] = None,
        source: "int | str | Path | None" = None,
        sink: Optional[FrameSink] = None,
        *,
        preview: bool = False,
        control: bool = False,
        synthetic: bool = False,
        perception: Any = None,
        segmenter: Any = None,
        snapshot_dir: str = "captures",
    ) -> None:
        self.settings = settings
        self.config = config or Config()
        self.source_spec = source
        self.sink: FrameSink = sink or NullSink()
        self.preview = bool(preview)
        self.control_enabled = bool(control)
        self.synthetic = bool(synthetic)
        self.snapshot_dir = snapshot_dir

        self.stats = LatencyStats()
        self.state = StudioState.from_settings(settings)
        self._stop = threading.Event()
        self._injected_perception = perception
        self._injected_segmenter = segmenter
        self._source: Any = None
        self.pipeline: Optional[StudioPipeline] = None
        self._control: Optional[ControlServer] = None
        self._fps_now = 0.0

    # ------------------------------------------------------------------ #
    def stop(self) -> None:
        self._stop.set()

    def _open_source(self) -> Any:
        return open_source(
            self.source_spec,
            width=self.settings.width,
            height=self.settings.height,
            fps=self.settings.fps,
            backend=self.config.camera_backend,
            mirror=self.config.mirror,
            synthetic=self.synthetic,
        )

    def _build_detectors(self) -> Tuple[Any, Any]:
        perception, segmenter = self._injected_perception, self._injected_segmenter
        if perception is None:
            from ..detectors.engine import PerceptionEngine

            overrides = {
                "enable_hands": self.settings.gesture_control,
                "max_faces": 4 if self.state.auto_frame else 1,
            }
            engine = PerceptionEngine(self.config.with_overrides(**overrides))
            engine.hand_idle_stride = 3
            engine.warm_up(self.settings.analysis_width, round(self.settings.analysis_width * 9 / 16))
            if not engine.face_available:
                log.warning(
                    "No face detector is available: auto-framing, studio light and the away "
                    "detector are inactive. Run `mirrorlab doctor`."
                )
            perception = AsyncPerception(engine, max_fps=self.settings.perception_fps)
        if segmenter is None:
            from ..detectors.segmentation import SelfieSegmenter

            segmenter = SelfieSegmenter(feather=3)
            if not segmenter.available:
                log.warning(
                    "Person segmentation is unavailable (%s). Background effects will blur the whole "
                    "frame instead of passing your room through.",
                    segmenter.reason,
                )
        return perception, segmenter

    # ------------------------------------------------------------------ #
    def run(self, max_frames: int = 0) -> SessionReport:
        """Process frames until stopped, the source ends, or ``max_frames`` is reached."""
        settings = self.settings
        report = SessionReport()
        self._install_signal_handlers()

        self._source = self._open_source()

        perception, segmenter = self._build_detectors()
        self.pipeline = StudioPipeline(settings, self.state, perception, segmenter)
        self.state = self.pipeline.state  # the pipeline reconciles `replace` availability

        try:
            self.sink.open(settings.width, settings.height, settings.fps)
        except OutputError:
            self._shutdown()
            raise
        report.device = getattr(self.sink, "device", "")

        if self.control_enabled:
            self._control = ControlServer(self.state, status=self._status, on_quit=self.stop)
            self._control.start()

        preview_ok = self.preview
        period = 1.0 / settings.fps
        started = time.perf_counter()
        next_tick = started
        last_seq = -1
        last_output: Optional[np.ndarray] = None
        last_frame_at = started
        next_reopen = 0.0
        was_stalled = False
        frames_in_second, second_start = 0, started

        try:
            while not self._stop.is_set():
                if max_frames and report.frames >= max_frames:
                    break
                now = time.perf_counter()
                t_read = now
                seq = getattr(self._source, "sequence", None)
                fresh = seq is None or seq != last_seq
                frame = self._source.read(timeout=period) if fresh else None

                finite = self.synthetic or isinstance(self.source_spec, (str, Path))
                if frame is None and fresh and finite and not getattr(self._source, "is_alive", True):
                    break  # a finite source ended
                if frame is not None:
                    last_frame_at = time.perf_counter()
                    if seq is not None:
                        last_seq = seq
                    self.stats.record("read", (last_frame_at - t_read) * 1000.0)

                    result = self.pipeline.process(frame)
                    for stage, ms in result.timings_ms.items():
                        self.stats.record(stage, ms)
                    last_output = result.output
                    report.camera_frames += 1
                    self.stats.record("total", (time.perf_counter() - now) * 1000.0)
                    self._after_frame(result)
                elif last_output is not None:
                    report.repeated += 1

                # Camera lost: never keep showing the last picture of the user.
                if (time.perf_counter() - last_frame_at) > STALL_SECONDS:
                    if not was_stalled:
                        report.stalls += 1
                        was_stalled = True
                    last_output = self.pipeline.cover_frame()
                    if time.perf_counter() >= next_reopen:
                        next_reopen = time.perf_counter() + REOPEN_INTERVAL
                        self._try_reopen()
                else:
                    was_stalled = False

                if last_output is not None:
                    t_send = time.perf_counter()
                    self.sink.send(last_output)
                    self.stats.record("send", (time.perf_counter() - t_send) * 1000.0)
                    report.frames += 1
                    frames_in_second += 1

                if preview_ok and last_output is not None:
                    preview_ok = self._show_preview(last_output)

                tick = time.perf_counter()
                if tick - second_start >= 1.0:
                    self._fps_now = frames_in_second / (tick - second_start)
                    frames_in_second, second_start = 0, tick

                next_tick += period
                delay = next_tick - time.perf_counter()
                if delay > 0:
                    time.sleep(delay)
                else:
                    next_tick = time.perf_counter()  # we are behind; do not try to catch up
        finally:
            report.seconds = time.perf_counter() - started
            report.latency = self.stats.summary()
            if self.pipeline is not None:
                report.fail_closed_frames = self.pipeline.background.fail_closed_frames
            self._shutdown()
        return report

    # ------------------------------------------------------------------ #
    def _after_frame(self, result: FrameResult) -> None:
        if self.state.take_snapshot_request():
            self._save_snapshot(result.output)

    def _save_snapshot(self, frame: np.ndarray) -> None:
        directory = Path(self.snapshot_dir)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / time.strftime("mirrorlab-%Y%m%d-%H%M%S.png")
        if cv2.imwrite(str(path), frame):
            log.info("snapshot saved: %s", path)
        else:  # pragma: no cover - disk full or unwritable
            log.warning("could not write snapshot to %s", path)

    def _status(self) -> Dict[str, Any]:
        return {
            "fps": round(self._fps_now, 1),
            "device": getattr(self.sink, "device", ""),
            "resolution": f"{self.settings.width}x{self.settings.height}",
        }

    def _try_reopen(self) -> None:
        log.warning("camera stalled; trying to reopen it")
        try:
            if self._source is not None:
                self._source.release()
            self._source = self._open_source()
        except CameraError as exc:
            log.warning("reopen failed: %s", exc)

    def _show_preview(self, output: np.ndarray) -> bool:
        """Draw the local preview. Returns ``False`` if no window is possible."""
        view = output.copy()
        state = self.state.snapshot()
        label = (
            f"bg:{state['background']}  frame:{'on' if state['auto_frame'] else 'off'}  "
            f"light:{'on' if state['studio_light'] else 'off'}  "
            f"{'PRIVACY' if state['privacy'] else 'live'}  {self._fps_now:4.1f} fps"
        )
        cv2.rectangle(view, (0, 0), (view.shape[1], 30), (24, 24, 24), -1)
        cv2.putText(view, label, (10, 21), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (220, 220, 220), 1, cv2.LINE_AA)
        if self.pipeline is not None and self.pipeline.controller.last_progress > 0:
            self.pipeline.controller.draw_ring(
                view, (view.shape[1] - 70, 100), 36, label=self.pipeline.controller.pending
            )
        try:
            cv2.imshow("MirrorLab Studio  (q quit, p privacy, b background, f framing, l light)", view)
            key = cv2.waitKey(1) & 0xFF
        except cv2.error as exc:
            log.warning("no preview window available (%s); continuing without one", exc)
            return False
        actions = {
            ord("p"): "privacy",
            ord("b"): "background_next",
            ord("f"): "framing",
            ord("l"): "light",
            ord("s"): "snapshot",
            ord("t"): "reaction:thumbs_up",
            ord("h"): "reaction:love",
        }
        if key in (ord("q"), 27):
            self.stop()
        elif key in actions:
            self.state.apply_action(actions[key])
        return True

    def _install_signal_handlers(self) -> None:
        def handler(signum: int, _frame: object) -> None:
            log.info("signal %d received, stopping", signum)
            self.stop()

        for name in ("SIGINT", "SIGTERM"):
            sig = getattr(signal, name, None)
            if sig is None:
                continue
            with suppress(ValueError):  # not in the main thread (tests): the caller uses stop()
                signal.signal(sig, handler)

    def _shutdown(self) -> None:
        if self._control is not None:
            self._control.stop()
            self._control = None
        if self.pipeline is not None:
            self.pipeline.close()
        for closer in (getattr(self._source, "release", None), self.sink.close):
            if callable(closer):
                try:
                    closer()
                except Exception as exc:  # pragma: no cover - teardown only
                    log.debug("shutdown step failed: %s", exc)
        if self.preview:
            with suppress(cv2.error):  # headless OpenCV builds have no windows
                cv2.destroyAllWindows()


def describe_report(report: SessionReport) -> List[str]:
    """Human-readable lines for the end-of-session summary."""
    lines = [
        f"{report.frames} frames in {report.seconds:.1f}s ({report.fps:.1f} fps)"
        + (f" -> {report.device}" if report.device else ""),
    ]
    order = ["read", "perceive", "light", "background", "frame", "send", "total"]
    for stage in order:
        stats = report.latency.get(stage)
        if stats:
            lines.append(f"  {stage:<11} p50 {stats['p50']:6.2f} ms   p95 {stats['p95']:6.2f} ms")
    if report.camera_frames and report.camera_fps < report.fps * 0.8:
        lines.append(
            f"  camera delivered {report.camera_fps:.1f} fps; {report.repeated} output frames were repeated.\n"
            "  Webcams drop their frame rate in dim light: try a brighter room, or --fps lower."
        )
    if report.stalls:
        lines.append(f"  camera stalled {report.stalls} time(s); output was covered meanwhile")
    if report.fail_closed_frames:
        lines.append(
            f"  {report.fail_closed_frames} frames blurred whole because person segmentation was unavailable"
        )
    return lines
