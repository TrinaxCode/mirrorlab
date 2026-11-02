"""Runs a studio session on a worker thread and hands a window what it needs.

The window lives on the main thread and the camera loop must never block it, so
the two only meet here: the loop deposits its newest output frame, the window
picks it up on its own timer, and actions travel the other way through the same
:meth:`StudioState.apply_action` that gestures and ``mirrorlab ctl`` use.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np

from ..camera import CameraError
from ..config import Config
from ..studio.session import StudioSession
from ..studio.settings import StudioSettings
from ..studio.state import ActionResult
from ..studio.vcam import FrameSink, OutputError, open_sink
from ..utils.logging import get_logger

__all__ = ["StudioRunner"]

log = get_logger("desktop.runner")


class StudioRunner:
    """One camera session at a time, started and stopped from the UI thread."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._session: Optional[StudioSession] = None
        self._frame: Optional[np.ndarray] = None
        self._sequence = 0
        self._error: Optional[str] = None
        self._error_kind = ""

    # ------------------------------------------------------------------ #
    @property
    def running(self) -> bool:
        thread = self._thread
        return thread is not None and thread.is_alive()

    @property
    def error(self) -> Optional[str]:
        """The reason the last session ended badly, or ``None``."""
        return self._error

    @property
    def error_kind(self) -> str:
        """``"camera"``, ``"output"`` or ``"unexpected"`` for the last error, else ``""``."""
        return self._error_kind

    @property
    def has_frame(self) -> bool:
        return self._frame is not None

    def latest_frame(self) -> Tuple[int, Optional[np.ndarray]]:
        """The newest output frame with a counter that changes whenever it does."""
        with self._lock:
            return self._sequence, self._frame

    # ------------------------------------------------------------------ #
    def start(
        self,
        settings: StudioSettings,
        *,
        camera: int = 0,
        output: str = "vcam",
        snapshot_dir: "str | Path" = "captures",
        synthetic: bool = False,
        source: "int | str | Path | None" = None,
        sink: Optional[FrameSink] = None,
        **injected: Any,
    ) -> None:
        """Begin a session in the background. Errors arrive through :attr:`error`.

        ``source`` replaces the camera with a video or image file, which is how the
        documentation screenshots are made without pointing a webcam at anyone.
        """
        if self.running:
            raise RuntimeError("a session is already running")
        self._error = None
        self._error_kind = ""
        with self._lock:
            self._frame = None
            self._sequence = 0

        config = Config.load(overrides={"camera_index": camera, "headless": True})
        session = StudioSession(
            settings,
            config,
            source=camera if source is None else source,
            sink=sink or (open_sink("none") if output == "none" else open_sink("vcam")),
            control=False,
            synthetic=synthetic,
            snapshot_dir=snapshot_dir,
            frame_callback=self._deposit,
            **injected,
        )
        self._session = session
        self._thread = threading.Thread(
            target=self._run, args=(session,), name="mirrorlab-studio", daemon=True
        )
        self._thread.start()

    def request_stop(self) -> None:
        """Ask the session to end without waiting, for callers that must not block."""
        session = self._session
        if session is not None:
            session.stop()

    def stop(self, timeout: float = 6.0) -> bool:
        """Ask the session to end and wait for it. Returns ``True`` once it has."""
        session, thread = self._session, self._thread
        if session is not None:
            session.stop()
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout)
        return not self.running

    # ------------------------------------------------------------------ #
    def apply(self, action: str) -> ActionResult:
        session = self._session
        if session is None or not self.running:
            return ActionResult(False, "the camera is off")
        return session.state.apply_action(action)

    def state(self) -> Dict[str, object]:
        session = self._session
        if session is None:
            return {}
        return session.state.snapshot()

    def status(self) -> Dict[str, Any]:
        session = self._session
        if session is None or not self.running:
            return {}
        return session._status()

    # ------------------------------------------------------------------ #
    def _deposit(self, frame: np.ndarray) -> None:
        with self._lock:
            if frame is not self._frame:
                self._frame = frame
                self._sequence += 1

    def _run(self, session: StudioSession) -> None:
        try:
            session.run()
        except CameraError as exc:
            self._fail("camera", str(exc))
        except OutputError as exc:
            self._fail("output", str(exc))
        except Exception as exc:  # the window must survive whatever the pipeline throws
            log.exception("studio session crashed")
            self._fail("unexpected", f"{type(exc).__name__}: {exc}")

    def _fail(self, kind: str, message: str) -> None:
        self._error_kind = kind
        self._error = message
