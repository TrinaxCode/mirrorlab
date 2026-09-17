"""The MirrorLab application: the frame loop that ties everything together.

Pipeline per frame::

    capture (own thread, drop-oldest)
        │
        ▼
    PerceptionEngine ──► faces + blendshapes + hands + landmarks
        │                 └─► expressions, gestures, dynamic gestures
        ▼
    GestureController ──► actions (switch filter, snapshot, freeze…)
        │
        ▼
    FilterChain ──► the visual effect
        │
        ▼
    AR effects (face overlays, hand effects) + air-draw layer
        │
        ▼
    HUD ──► imshow / headless sink

The render loop stays on the **main thread** on purpose: Cocoa on macOS
requires UI calls from the main thread, and pushing them to a worker is the
usual cause of "the window freezes but the video keeps running".
"""

from __future__ import annotations

import csv
import platform
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, ClassVar, Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np

from .actions import ActionEvent, GestureController
from .airdraw import AirCanvas
from .camera import CameraError, SyntheticSource, open_source, platform_summary
from .config import Config
from .detectors.engine import PerceptionEngine, PerceptionResult
from .detectors.segmentation import SelfieSegmenter
from .effects.face import FACE_EFFECTS, HAND_EFFECTS, EffectContext, build_effects, build_hand_effects
from .filters import PRESETS, Filter, FilterContext, build_filter
from .filters.base import FILTERS
from .reactions import ReactionLibrary
from .recording import Recorder, SaveResult, save_snapshot
from .render.composition import Transition, stack_side_by_side
from .render.hud import Hud, HudState, draw_reticle
from .utils.colors import get_palette
from .utils.logging import get_logger
from .utils.timing import FpsMeter
from .version import CODENAME, __version__

__all__ = ["MirrorLab", "run_session"]

log = get_logger("app")


@dataclass
class SessionStats:
    """Running totals shown at the end of a session."""

    frames: int = 0
    started: float = field(default_factory=time.perf_counter)
    expression_counts: Dict[str, int] = field(default_factory=dict)
    gesture_counts: Dict[str, int] = field(default_factory=dict)
    snapshots: List[SaveResult] = field(default_factory=list)

    @property
    def elapsed(self) -> float:
        return time.perf_counter() - self.started

    @property
    def average_fps(self) -> float:
        elapsed = self.elapsed
        return self.frames / elapsed if elapsed > 0 else 0.0

    def observe(self, result: PerceptionResult) -> None:
        self.frames += 1
        name = result.expression.name
        if name and name != "unknown":
            self.expression_counts[name] = self.expression_counts.get(name, 0) + 1
        for match in result.gestures:
            if match.name != "none":
                self.gesture_counts[match.name] = self.gesture_counts.get(match.name, 0) + 1

    def summary(self) -> str:
        lines = [
            "",
            "─" * 62,
            f"  Session summary · {self.frames} frames in {self.elapsed:.1f}s "
            f"({self.average_fps:.1f} fps average)",
            "─" * 62,
        ]
        if self.expression_counts:
            top = sorted(self.expression_counts.items(), key=lambda kv: -kv[1])[:5]
            total = sum(self.expression_counts.values()) or 1
            lines.append("  Expressions:")
            for name, count in top:
                bar = "█" * int(28 * count / total)
                lines.append(f"    {name:<12} {bar:<28} {100 * count / total:5.1f}%")
        if self.gesture_counts:
            lines.append("  Gestures:")
            for name, count in sorted(self.gesture_counts.items(), key=lambda kv: -kv[1])[:8]:
                lines.append(f"    {name:<12} {count}")
        if self.snapshots:
            lines.append("  Saved:")
            for item in self.snapshots[-5:]:
                lines.append(f"    {item.describe()}")
        lines.append("─" * 62)
        return "\n".join(lines)


class MirrorLab:
    """The application object.

    Args:
        config: A :class:`~mirrorlab.config.Config`. Defaults to the layered
            config (file → environment → defaults).
        source: Camera index, video path, or ``None`` for the default camera.
        synthetic: Use the offline test-pattern source instead of a camera.

    Example:
        >>> app = MirrorLab()                     # doctest: +SKIP
        >>> app.run()                             # doctest: +SKIP
    """

    def __init__(
        self,
        config: Optional[Config] = None,
        source: Optional[int | str] = None,
        synthetic: bool = False,
        face_backend: str = "auto",
        hand_backend: str = "auto",
        auto_download: bool = True,
    ) -> None:
        self.config = config or Config()
        self.palette = get_palette(self.config.theme)
        self.source = source
        self.synthetic = bool(synthetic)
        self.stats = SessionStats()
        self.fps = FpsMeter()

        # -- pipeline pieces ------------------------------------------------ #
        self.engine = PerceptionEngine(
            self.config,
            face_backend=face_backend,
            hand_backend=hand_backend,
            auto_download=auto_download,
        )
        self.segmenter: Optional[SelfieSegmenter] = None
        if self.config.enable_segmentation:
            self.segmenter = SelfieSegmenter(auto_download=auto_download)

        self.filter: Filter = build_filter(self.config.filter)
        self.effects = build_effects(self.config.effects)
        self.hand_effects = build_hand_effects(self.config.effects)
        self.hud = Hud(
            palette=self.config.theme,
            show_landmarks=self.config.show_landmarks,
            show_fps=self.config.show_fps,
            compact=False,
        )
        self.controller = GestureController(dwell=0.6, refractory=0.9, enabled=self.config.gesture_control)
        self.air_canvas: Optional[AirCanvas] = None
        self.reactions: Optional[ReactionLibrary] = None
        if self.config.show_reactions:
            self.reactions = ReactionLibrary(self.config.reactions_dir)
        self.transition = Transition(duration=0.16)

        # -- runtime state -------------------------------------------------- #
        self.running = False
        self.frozen = False
        self.frozen_frame: Optional[np.ndarray] = None
        self.recorder: Optional[Recorder] = None
        self.show_effects = True
        self.before_after = False
        self._fired: List[Tuple[str, float]] = []
        self._last_result: Optional[PerceptionResult] = None
        self._stats_writer = None
        self._stats_file = None
        self._filter_index = max(
            0, sorted(FILTERS).index(self.filter.name) if self.filter.name in FILTERS else 0
        )
        self._preset_names = list(PRESETS)
        self._preset_index = 0
        self._theme_names = ["aurora", "magma", "mono", "candy"]
        self._theme_index = (
            self._theme_names.index(self.config.theme) if self.config.theme in self._theme_names else 0
        )

    # ------------------------------------------------------------------ #
    # Properties
    # ------------------------------------------------------------------ #
    @property
    def filter_label(self) -> str:
        return self.filter.describe() if hasattr(self.filter, "describe") else self.filter.label

    @property
    def filter_title(self) -> str:
        if hasattr(self.filter, "filters"):
            return " + ".join(stage.label for stage in self.filter.filters)  # type: ignore[attr-defined]
        return self.filter.label

    # ------------------------------------------------------------------ #
    # Setup / teardown
    # ------------------------------------------------------------------ #
    def _open_source(self):
        if self.synthetic:
            return SyntheticSource(
                width=self.config.camera_width,
                height=self.config.camera_height,
                fps=float(self.config.camera_fps),
                frame_limit=self.config.max_frames,
            )
        return open_source(
            self.source,
            width=self.config.camera_width,
            height=self.config.camera_height,
            fps=self.config.camera_fps,
            backend=self.config.camera_backend,
            mirror=self.config.mirror,
        )

    def _open_stats(self) -> None:
        if not self.config.stats_csv:
            return
        path = Path(self.config.stats_csv)
        path.parent.mkdir(parents=True, exist_ok=True)
        new = not path.exists()
        self._stats_file = path.open("a", newline="", encoding="utf-8")
        self._stats_writer = csv.writer(self._stats_file)
        if new:
            self._stats_writer.writerow(
                ["timestamp", "frame", "fps", "inference_ms", "expression", "score", "gestures", "filter"]
            )

    def _record_stats(self, result: PerceptionResult, fps: float) -> None:
        if self._stats_writer is None:
            return
        self._stats_writer.writerow(
            [
                f"{time.time():.3f}",
                result.analysis.frame_index,
                f"{fps:.2f}",
                f"{result.total_ms:.2f}",
                result.expression.name,
                f"{result.expression.score:.3f}",
                "|".join(result.gesture_names()),
                self.filter_title,
            ]
        )
        if result.analysis.frame_index % 60 == 0 and self._stats_file is not None:
            self._stats_file.flush()

    # ------------------------------------------------------------------ #
    # Main loop
    # ------------------------------------------------------------------ #
    def run(
        self,
        max_frames: Optional[int] = None,
        on_frame: Optional[Callable[[np.ndarray, PerceptionResult], None]] = None,
    ) -> SessionStats:
        """Run the application until the user quits.

        Args:
            max_frames: Stop after this many frames (overrides config).
            on_frame: Optional callback receiving every rendered frame — used
                by tests and by the recording/streaming integrations.

        Returns:
            The :class:`SessionStats` for the session.
        """
        limit = int(max_frames if max_frames is not None else self.config.max_frames)
        headless = self.config.headless or not _display_available()

        try:
            source = self._open_source()
        except CameraError as exc:
            log.error("%s", exc)
            raise

        self._open_stats()
        log.info(
            "MirrorLab %s “%s” · %s · %s",
            __version__,
            CODENAME,
            platform.system(),
            self.engine.backend_summary,
        )
        log.info("Filter: %s", self.filter_title)
        if self.config.effects:
            log.info("Effects: %s", ", ".join(self.config.effects))
        if headless:
            log.info("Running headless (no preview window).")

        window = self.config.window_name
        if not headless:
            cv2.namedWindow(window, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(window, self.config.window_width, self.config.window_height)
            if self.config.fullscreen:
                cv2.setWindowProperty(window, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

        # Honour the flags the config already carries: a `--air-draw` run must
        # not require the user to press `d` as well.
        if self.config.air_draw and self.air_canvas is None:
            self.air_canvas = AirCanvas(self.config.camera_width, self.config.camera_height)
            log.info("Air draw enabled from configuration.")
        if self.reactions is not None:
            log.info("%s", self.reactions.describe())

        # Warm up so the first visible frame is not the slow one.
        if self.engine.face_available or self.engine.hand_available:
            self.engine.warm_up(frames=2)

        self.running = True
        last_time = time.perf_counter()
        frame_index = 0
        result: Optional[PerceptionResult] = None
        original: Optional[np.ndarray] = None

        try:
            while self.running:
                frame = source.read(timeout=2.0)
                if frame is None:
                    log.info("Video source ended.")
                    break

                now = time.perf_counter()
                delta = max(1e-4, now - last_time)
                last_time = now

                self.fps.begin("detect")
                if self.frozen and self.frozen_frame is not None:
                    frame = self.frozen_frame.copy()
                    result = self._last_result
                else:
                    result = self.engine.process(frame, frame_index, int(now * 1000) % (2**31))
                    self._last_result = result
                self.fps.end("detect")

                original = frame.copy()

                # -- gesture actions ---------------------------------------- #
                self.fps.begin("actions")
                events = self.controller.update(result.gestures, result.dynamic, now)
                for event in events:
                    self._handle_event(event)
                self.fps.end("actions")

                # -- segmentation mask (optional) --------------------------- #
                mask = None
                if self.segmenter is not None and self.segmenter.available:
                    self.fps.begin("segment")
                    mask = self.segmenter.process(frame, result.timestamp_ms)
                    self.fps.end("segment")

                # -- filters ------------------------------------------------ #
                self.fps.begin("filter")
                ctx = FilterContext(
                    frame_index=frame_index,
                    time=now - self.stats.started,
                    delta=delta,
                    width=frame.shape[1],
                    height=frame.shape[0],
                    state=self._filter_state(result, mask),
                )
                filtered = self.filter.apply(frame, ctx)
                if filtered.shape != frame.shape:
                    filtered = cv2.resize(filtered, (frame.shape[1], frame.shape[0]))
                self.fps.end("filter")

                rendered = self.transition.update(filtered, delta)

                # -- AR effects --------------------------------------------- #
                self.fps.begin("effects")
                if self.show_effects:
                    rendered = self._apply_effects(rendered, result, ctx)
                if self.air_canvas is not None:
                    rendered = self._apply_air_draw(rendered, result)
                if self.reactions is not None:
                    rendered = self._apply_reaction(rendered, result)
                self.fps.end("effects")

                # -- HUD ---------------------------------------------------- #
                self.fps.begin("hud")
                fps_value = self.fps.tick()
                if self.config.show_hud:
                    rendered = self.hud.render(
                        rendered,
                        self._hud_state(result, fps_value, events),
                        result.faces,
                        result.hands,
                    )
                    self._draw_hold_ring(rendered, result)
                self.fps.end("hud")

                if self.before_after and original is not None:
                    rendered = stack_side_by_side(original, rendered)

                # Remember the composited frame: snapshots must capture exactly
                # what the user sees, including HUD and effects.
                self._last_rendered = rendered

                self.stats.observe(result)
                self._record_stats(result, fps_value)
                if self.recorder is not None:
                    self.recorder.write(rendered)
                if on_frame is not None:
                    on_frame(rendered, result)

                if not headless:
                    cv2.imshow(window, rendered)
                    if not self._handle_key(cv2.waitKey(1) & 0xFF):
                        break

                frame_index += 1
                if limit and frame_index >= limit:
                    log.info("Reached the frame limit (%d).", limit)
                    break

        except KeyboardInterrupt:
            log.info("Interrupted by the user.")
        finally:
            self.running = False
            if self.recorder is not None:
                try:
                    self.recorder.stop()
                except Exception as exc:  # pragma: no cover - defensive
                    log.warning("Could not finalise the recording: %s", exc)
                self.recorder = None
            if self._stats_file is not None:
                self._stats_file.close()
                self._stats_file = None
                self._stats_writer = None
            source.release()
            self.engine.close()
            if self.segmenter is not None:
                self.segmenter.close()
            if not headless:
                cv2.destroyAllWindows()
                # On macOS the window only disappears after a few event-loop
                # iterations; without this the process looks hung on exit.
                for _ in range(4):
                    cv2.waitKey(1)

        summary = self.stats.summary()
        print(summary)
        return self.stats

    # ------------------------------------------------------------------ #
    # Per-frame helpers
    # ------------------------------------------------------------------ #
    def _filter_state(self, result: PerceptionResult, mask: Optional[np.ndarray]) -> Dict[str, object]:
        """Context values consumed by mask-aware and face-aware filters."""
        state: Dict[str, object] = {}
        if mask is not None:
            state["person_mask"] = mask
        face = result.face
        if face is not None and face.landmarks is not None and face.landmarks.size:
            height, width = (
                (mask.shape[0], mask.shape[1])
                if mask is not None
                else (self.config.camera_height, self.config.camera_width)
            )
            state["face_bbox"] = face.bbox_pixels(width, height, pad=0.15)
        return state

    def _apply_effects(self, frame: np.ndarray, result: PerceptionResult, ctx: FilterContext) -> np.ndarray:
        effect_ctx = EffectContext(
            frame_index=ctx.frame_index,
            time=ctx.time,
            delta=ctx.delta,
            width=frame.shape[1],
            height=frame.shape[0],
            state={},
        )
        for effect in self.effects:
            face = result.face
            if face is None:
                continue
            if effect.requires_landmarks and face.count < 300:
                continue
            frame = effect.apply(frame, face, effect_ctx)
        for effect in self.hand_effects:
            for hand in result.hands:
                frame = effect.apply(frame, hand, effect_ctx)
        return frame

    def _apply_air_draw(self, frame: np.ndarray, result: PerceptionResult) -> np.ndarray:
        canvas = self.air_canvas
        if canvas is None:
            return frame
        canvas.resize(frame.shape[1], frame.shape[0])
        hand = result.hand
        pose = result.pose
        canvas.update(hand, pose, time.perf_counter())
        frame = canvas.composite(frame)
        cursor = canvas.cursor()
        if cursor is not None:
            draw_reticle(
                frame,
                cursor,
                max(10, frame.shape[0] // 48),
                self.palette.primary if canvas.active else self.palette.text_dim,
                phase=time.perf_counter(),
            )
        return frame

    def _apply_reaction(self, frame: np.ndarray, result: PerceptionResult) -> np.ndarray:
        """Show a picture matching the current expression, if one is available."""
        library = self.reactions
        if library is None:
            return frame
        overlay = library.overlay_for(result.expression.name, result.expression.score)
        if overlay is None:
            return frame
        return overlay.draw(frame)

    def _hud_state(self, result: PerceptionResult, fps: float, events: Sequence[ActionEvent]) -> HudState:
        now = time.perf_counter()
        for event in events:
            self._fired.append((event.describe(), now))
        self._fired = [(text, at) for text, at in self._fired if now - at < 2.0]

        gesture = result.gesture
        return HudState(
            fps=fps,
            frame_time_ms=1000.0 / fps if fps > 0 else 0.0,
            inference_ms=result.total_ms,
            filter_name=self.filter.name,
            filter_label=self.filter_title,
            effect_names=[effect.label for effect in self.effects] + [e.label for e in self.hand_effects],
            expression=result.expression.name,
            expression_label=result.expression.display(spanish=True),
            expression_score=result.expression.score,
            expression_scores=result.expression.scores,
            gesture=gesture.name,
            gesture_label=gesture.display(spanish=True) if gesture.name != "none" else "",
            gesture_score=gesture.score,
            recording=self.recorder is not None and self.recorder.running,
            frozen=self.frozen,
            air_draw=self.air_canvas is not None,
            hands=len(result.hands),
            faces=len(result.faces),
            messages=[(text, now - at) for text, at in self._fired],
        )

    def _draw_hold_ring(self, frame: np.ndarray, result: PerceptionResult) -> None:
        if not self.controller.pending or self.controller.last_progress <= 0.0:
            return
        hand = result.hand
        if hand is None:
            return
        centre = (
            int(hand.landmarks[:, 0].mean() * frame.shape[1]),
            int(hand.landmarks[:, 1].mean() * frame.shape[0]),
        )
        action = self.controller.bindings.get(self.controller.pending, "")
        self.controller.draw_ring(
            frame,
            centre,
            max(26, frame.shape[0] // 18),
            self.palette.primary,
            thickness=max(3, frame.shape[0] // 240),
            label=f"{self.controller.pending} -> {action}",
        )

    # ------------------------------------------------------------------ #
    # Commands
    # ------------------------------------------------------------------ #
    def _handle_event(self, event: ActionEvent) -> None:
        log.info("Action: %s (%s)", event.describe(), event.source)
        self.apply_action(event.action)

    def toggle_reactions(self) -> None:
        """Turn the expression reaction images on or off at runtime."""
        if self.reactions is None:
            self.reactions = ReactionLibrary(self.config.reactions_dir)
            log.info("%s", self.reactions.describe())
        else:
            self.reactions = None
            log.info("Reaction images off.")

    def apply_action(self, action: str) -> None:
        """Execute a named action. Shared by gestures and keyboard shortcuts."""
        if action.startswith("filter:"):
            self.set_filter(action.split(":", 1)[1])
            return
        handler = {
            "next_filter": self.next_filter,
            "prev_filter": self.prev_filter,
            "next_preset": self.next_preset,
            "prev_preset": self.prev_preset,
            "snapshot": self.snapshot,
            "discard": self.discard_last,
            "toggle_freeze": self.toggle_freeze,
            "toggle_hud": self.toggle_hud,
            "toggle_landmarks": self.toggle_landmarks,
            "toggle_mirror": self.toggle_mirror,
            "toggle_effects": self.toggle_effects,
            "toggle_air_draw": self.toggle_air_draw,
            "air_draw": self.toggle_air_draw,
            "toggle_record": self.toggle_recording,
            "toggle_before_after": self.toggle_before_after,
            "toggle_reactions": self.toggle_reactions,
            "toggle_glitch": lambda: self.set_filter(
                "glitch" if self.filter.name != "glitch" else "original"
            ),
            "cycle_theme": self.cycle_theme,
            "clear_canvas": self.clear_canvas,
            "reset": self.reset,
            "quit": self.quit,
            "freeze": self.toggle_freeze,
        }.get(action)
        if handler is None:
            log.debug("Unbound action %r", action)
            return
        handler()

    # -- filters -------------------------------------------------------- #
    def set_filter(self, spec: str, transition: bool = True) -> None:
        """Switch the active filter (or chain), cross-fading from the previous look."""
        try:
            new_filter = build_filter(spec)
        except KeyError as exc:
            log.warning("%s", exc)
            return
        if transition and self._last_rendered is not None:
            # Fade from the frame the user is currently looking at, so the
            # change reads as a deliberate cut rather than a glitch.
            self.transition.trigger(self._last_rendered)
        self.filter = new_filter
        log.info("Filter → %s", self.filter_title)

    def next_filter(self) -> None:
        names = sorted(FILTERS)
        self._filter_index = (self._filter_index + 1) % len(names)
        self.set_filter(names[self._filter_index])

    def prev_filter(self) -> None:
        names = sorted(FILTERS)
        self._filter_index = (self._filter_index - 1) % len(names)
        self.set_filter(names[self._filter_index])

    def next_preset(self) -> None:
        self._preset_index = (self._preset_index + 1) % len(self._preset_names)
        name = self._preset_names[self._preset_index]
        self.set_filter(PRESETS[name]["filter"])
        log.info("Preset → %s", PRESETS[name]["label"])

    def prev_preset(self) -> None:
        self._preset_index = (self._preset_index - 1) % len(self._preset_names)
        name = self._preset_names[self._preset_index]
        self.set_filter(PRESETS[name]["filter"])
        log.info("Preset → %s", PRESETS[name]["label"])

    def cycle_theme(self) -> None:
        self._theme_index = (self._theme_index + 1) % len(self._theme_names)
        self.palette = get_palette(self._theme_names[self._theme_index])
        self.hud.palette = self.palette
        log.info("Theme → %s", self._theme_names[self._theme_index])

    # -- toggles -------------------------------------------------------- #
    def toggle_freeze(self) -> None:
        self.frozen = not self.frozen
        self.frozen_frame = None
        log.info("Freeze %s", "on" if self.frozen else "off")

    def toggle_hud(self) -> None:
        self.config = self.config.with_overrides(show_hud=not self.config.show_hud)
        log.info("HUD %s", "on" if self.config.show_hud else "off")

    def toggle_landmarks(self) -> None:
        self.config = self.config.with_overrides(show_landmarks=not self.config.show_landmarks)
        self.hud.show_landmarks = self.config.show_landmarks
        log.info("Landmarks %s", "on" if self.config.show_landmarks else "off")

    def toggle_mirror(self) -> None:
        self.config = self.config.with_overrides(mirror=not self.config.mirror)
        log.info("Mirror %s", "on" if self.config.mirror else "off")

    def toggle_effects(self) -> None:
        self.show_effects = not self.show_effects
        log.info("AR effects %s", "on" if self.show_effects else "off")

    def toggle_air_draw(self) -> None:
        if self.air_canvas is None:
            self.air_canvas = AirCanvas(self.config.camera_width, self.config.camera_height)
            log.info("Air draw on — point with your index finger to draw.")
        else:
            self.air_canvas = None
            log.info("Air draw off.")

    def clear_canvas(self) -> None:
        if self.air_canvas is not None:
            self.air_canvas.clear()

    def toggle_before_after(self) -> None:
        self.before_after = not self.before_after

    def toggle_recording(self) -> None:
        if self.recorder is not None and self.recorder.running:
            result = self.recorder.stop()
            self.stats.snapshots.append(result)
            log.info("Recording saved: %s", result.describe())
            self.recorder = None
            return
        from .recording import snapshot_path

        path = snapshot_path(self.config.output_dir, "mp4", prefix="mirrorlab_clip")
        try:
            self.recorder = Recorder(
                path,
                fps=self.config.record_fps or float(self.config.camera_fps),
                size=(self.config.camera_width, self.config.camera_height),
                codec=self.config.record_codec,
                gif=True,
            ).start()
        except OSError as exc:
            log.error("%s", exc)
            self.recorder = None

    # -- outputs -------------------------------------------------------- #
    def snapshot(self) -> Optional[SaveResult]:
        """Save the current composited frame. Returns ``None`` if nothing to save."""
        frame = self._current_frame()
        if frame is None:
            log.warning("Nothing to capture yet.")
            return None
        try:
            result = save_snapshot(
                frame, self.config.output_dir, self.config.snapshot_format, self.config.jpeg_quality
            )
        except OSError as exc:
            log.error("%s", exc)
            return None
        self.stats.snapshots.append(result)
        log.info("Snapshot saved: %s", result.describe())
        return result

    def discard_last(self) -> None:
        """Delete the most recent capture — the 'undo' for a bad shot."""
        if not self.stats.snapshots:
            log.info("Nothing to discard.")
            return
        last = self.stats.snapshots.pop()
        try:
            last.path.unlink(missing_ok=True)
            log.info("Discarded %s", last.path.name)
        except OSError as exc:  # pragma: no cover - permissions
            log.warning("Could not delete %s: %s", last.path, exc)

    _last_rendered: Optional[np.ndarray] = None

    def _current_frame(self) -> Optional[np.ndarray]:
        return self._last_rendered

    def reset(self) -> None:
        """Clear all temporal state — smoothing, votes, canvas, counters."""
        self.engine.reset()
        self.controller.reset()
        self.transition.reset()
        if self.air_canvas is not None:
            self.air_canvas.clear()
        self.fps.reset()
        log.info("State reset.")

    def quit(self) -> None:
        self.running = False

    # ------------------------------------------------------------------ #
    # Keyboard
    # ------------------------------------------------------------------ #
    KEYMAP: ClassVar[Dict[int, str]] = {
        ord("q"): "quit",
        ord("Q"): "quit",
        ord("s"): "snapshot",
        ord("f"): "toggle_freeze",
        ord("h"): "toggle_hud",
        ord("l"): "toggle_landmarks",
        ord("m"): "toggle_mirror",
        ord("e"): "toggle_effects",
        ord("d"): "toggle_air_draw",
        ord("r"): "toggle_record",
        ord("b"): "toggle_before_after",
        ord("t"): "cycle_theme",
        ord("c"): "clear_canvas",
        ord("x"): "reset",
        ord("i"): "toggle_reactions",
        ord("n"): "next_filter",
        ord("p"): "prev_filter",
        ord("]"): "next_preset",
        ord("["): "prev_preset",
        27: "toggle_effects",  # ESC
    }

    def _handle_key(self, key: int) -> bool:
        """Returns ``False`` when the user asked to quit."""
        if key == 255:
            return True
        # Number keys jump straight to the first nine filters.
        if ord("1") <= key <= ord("9"):
            names = sorted(FILTERS)
            index = key - ord("1")
            if index < len(names):
                self.set_filter(names[index])
            return True
        action = self.KEYMAP.get(key)
        if action is None:
            return True
        if action == "quit":
            log.info("Bye.")
            return False
        self.apply_action(action)
        return True

    # ------------------------------------------------------------------ #
    def keymap_help(self) -> List[Tuple[str, str]]:
        """Human-readable shortcut table for the CLI and the docs."""
        descriptions = {
            "quit": "Salir / Quit",
            "snapshot": "Guardar captura / Save snapshot",
            "toggle_freeze": "Congelar imagen / Freeze frame",
            "toggle_hud": "Mostrar u ocultar el HUD / Toggle HUD",
            "toggle_landmarks": "Puntos faciales y de mano / Landmarks",
            "toggle_mirror": "Modo espejo / Mirror mode",
            "toggle_effects": "Efectos AR / AR effects",
            "toggle_air_draw": "Dibujar en el aire / Air draw",
            "toggle_record": "Grabar vídeo + GIF / Record video",
            "toggle_before_after": "Comparar original / Before-after",
            "cycle_theme": "Cambiar tema / Cycle theme",
            "clear_canvas": "Borrar el dibujo / Clear drawing",
            "toggle_reactions": "Imágenes de reacción / Reaction images",
            "reset": "Reiniciar el estado / Reset state",
            "next_filter": "Siguiente filtro / Next filter",
            "prev_filter": "Filtro anterior / Previous filter",
            "next_preset": "Siguiente preset / Next preset",
            "prev_preset": "Preset anterior / Previous preset",
        }
        rows = []
        for key, action in self.KEYMAP.items():
            if key == 27:
                label = "ESC"
            elif 32 <= key < 127:
                label = chr(key)
            else:
                continue
            rows.append((label, descriptions.get(action, action)))
        rows.append(("1-9", "Filtros 1-9 / Quick filter select"))
        seen = set()
        unique = []
        for label, text in rows:
            if label in seen:
                continue
            seen.add(label)
            unique.append((label, text))
        return unique

    # ------------------------------------------------------------------ #
    def capability_report(self) -> Dict[str, object]:
        """What this machine can actually do — surfaced by ``mirrorlab doctor``."""
        from .detectors.backends import probe_environment

        report = platform_summary()
        report.update(probe_environment(auto_download=False))
        report["filters"] = len(FILTERS)
        report["face_effects"] = len(FACE_EFFECTS)
        report["hand_effects"] = len(HAND_EFFECTS)
        report["segmentation"] = bool(self.segmenter and self.segmenter.available)
        report["display"] = _display_available()
        return report


def _display_available() -> bool:
    """Whether a GUI window can actually be shown in this environment."""
    if platform.system() in {"Linux", "FreeBSD"}:
        import os

        if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
            return False
    try:
        return bool(cv2.getBuildInformation())
    except Exception:  # pragma: no cover - headless builds
        return False


def run_session(**kwargs) -> SessionStats:
    """Convenience wrapper: build an app and run it."""
    app = MirrorLab(
        config=kwargs.pop("config", None),
        source=kwargs.pop("source", None),
        synthetic=kwargs.pop("synthetic", False),
    )
    return app.run(**kwargs)
