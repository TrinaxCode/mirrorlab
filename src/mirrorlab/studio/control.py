"""Local control channel: drive a running session from another terminal.

``mirrorlab ctl privacy`` has to reach a different process, so a running session
opens a small control server. Because that is a network listener, it is built to
be boring and hard to misuse:

* it binds **127.0.0.1 only**, on an OS-assigned port;
* every request must carry a random **token** (24 bytes from :mod:`secrets`)
  stored in a file readable only by the current user (``0600``); tokens are
  compared in constant time;
* the protocol is one JSON object per line, not HTTP, so a web page cannot
  drive it with ``fetch()``: the first line of a browser request is not valid JSON;
* requests are capped at 4 KiB and must arrive within two seconds;
* the only things it can do are the actions in :mod:`mirrorlab.studio.state`
  plus ``status`` and ``quit``. It cannot read files, run commands or change
  settings that are not already runtime toggles.

Requests::

    {"token": "...", "cmd": "status"}
    {"token": "...", "cmd": "action", "action": "background:blur"}
    {"token": "...", "cmd": "quit"}
"""

from __future__ import annotations

import hmac
import json
import os
import secrets
import socket
import socketserver
import sys
import tempfile
import threading
from contextlib import suppress
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from ..utils.logging import get_logger
from .state import StudioState

__all__ = ["ControlClientError", "ControlServer", "runtime_file", "send_command"]

log = get_logger("studio.control")

MAX_REQUEST_BYTES = 4096
REQUEST_TIMEOUT = 2.0


class ControlClientError(RuntimeError):
    """The client could not talk to a running session."""


def runtime_file() -> Path:
    """Where a running session advertises its port and token."""
    override = os.environ.get("MIRRORLAB_RUNTIME_DIR")
    if override:
        base = Path(override).expanduser()
    elif sys.platform == "win32":  # pragma: no cover - windows only
        base = Path(os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()) / "mirrorlab"
    else:
        runtime = os.environ.get("XDG_RUNTIME_DIR")
        base = (
            Path(runtime) / "mirrorlab"
            if runtime
            else Path(tempfile.gettempdir()) / f"mirrorlab-{os.getuid()}"
        )
    return base / "control.json"


def _write_private(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if sys.platform != "win32":
        os.chmod(path.parent, 0o700)
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(payload, handle)
    if sys.platform != "win32":
        os.chmod(path, 0o600)


class _Handler(socketserver.StreamRequestHandler):
    server: "_Server"

    def handle(self) -> None:
        self.request.settimeout(REQUEST_TIMEOUT)
        try:
            raw = self.rfile.readline(MAX_REQUEST_BYTES + 1)
        except (OSError, socket.timeout):
            return
        if len(raw) > MAX_REQUEST_BYTES:
            self._reply({"ok": False, "error": "request too large"})
            return
        try:
            request = json.loads(raw.decode("utf-8"))
            if not isinstance(request, dict):
                raise ValueError("request must be a JSON object")
        except (ValueError, UnicodeDecodeError):
            self._reply({"ok": False, "error": "invalid request"})
            return

        supplied = str(request.get("token", ""))
        if not hmac.compare_digest(supplied.encode("utf-8"), self.server.token.encode("utf-8")):
            self._reply({"ok": False, "error": "unauthorized"})
            return
        self._reply(self.server.dispatch(request))

    def _reply(self, payload: Dict[str, Any]) -> None:
        with suppress(OSError):  # the client may already have gone away
            self.wfile.write((json.dumps(payload) + "\n").encode("utf-8"))


class _Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, token: str, dispatch: Callable[[Dict[str, Any]], Dict[str, Any]]) -> None:
        super().__init__(("127.0.0.1", 0), _Handler)
        self.token = token
        self.dispatch = dispatch


class ControlServer:
    """Serves the control protocol for one session.

    Args:
        state: The session's :class:`StudioState`; actions are applied to it.
        status: Callable returning extra status fields (fps, device, ...).
        on_quit: Called (from a server thread) when a client asks to quit.
        path: Where to advertise the port and token. Defaults to :func:`runtime_file`.
    """

    def __init__(
        self,
        state: StudioState,
        status: Optional[Callable[[], Dict[str, Any]]] = None,
        on_quit: Optional[Callable[[], None]] = None,
        path: Optional[Path] = None,
    ) -> None:
        self.state = state
        self._status = status
        self._on_quit = on_quit
        self.path = path or runtime_file()
        self.token = secrets.token_urlsafe(24)
        self._server: Optional[_Server] = None
        self._thread: Optional[threading.Thread] = None

    @property
    def port(self) -> int:
        return int(self._server.server_address[1]) if self._server else 0

    def start(self) -> int:
        self._server = _Server(self.token, self._dispatch)
        self._thread = threading.Thread(
            target=self._server.serve_forever, name="mirrorlab-control", daemon=True
        )
        self._thread.start()
        _write_private(
            self.path, {"host": "127.0.0.1", "port": self.port, "token": self.token, "pid": os.getpid()}
        )
        log.info("control channel on 127.0.0.1:%d", self.port)
        return self.port

    def stop(self) -> None:
        server, self._server = self._server, None
        if server is not None:
            server.shutdown()
            server.server_close()
        try:
            advertised = json.loads(self.path.read_text(encoding="utf-8"))
            if advertised.get("pid") == os.getpid():
                self.path.unlink()
        except (OSError, ValueError):
            pass

    # ------------------------------------------------------------------ #
    def _dispatch(self, request: Dict[str, Any]) -> Dict[str, Any]:
        command = request.get("cmd")
        if command == "status":
            payload: Dict[str, Any] = dict(self.state.snapshot())
            if self._status is not None:
                payload.update(self._status())
            return {"ok": True, "status": payload}
        if command == "action":
            action = request.get("action")
            if not isinstance(action, str) or not action or len(action) > 64:
                return {"ok": False, "error": "'action' must be a short string"}
            result = self.state.apply_action(action)
            return {"ok": result.ok, "message": result.message, "status": self.state.snapshot()}
        if command == "quit":
            if self._on_quit is not None:
                threading.Thread(target=self._on_quit, daemon=True).start()
            return {"ok": True, "message": "stopping"}
        return {"ok": False, "error": f"unknown command {command!r}"}

    def __enter__(self) -> "ControlServer":
        self.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.stop()


def send_command(
    command: Dict[str, Any], path: Optional[Path] = None, timeout: float = 3.0
) -> Dict[str, Any]:
    """Send one command to the running session and return its reply."""
    target = path or runtime_file()
    try:
        info = json.loads(target.read_text(encoding="utf-8"))
        host, port, token = str(info["host"]), int(info["port"]), str(info["token"])
    except (OSError, ValueError, KeyError) as exc:
        raise ControlClientError(
            "No running MirrorLab session found. Start one with `mirrorlab cam` first."
        ) from exc

    message = dict(command)
    message["token"] = token
    try:
        with socket.create_connection((host, port), timeout=timeout) as connection:
            connection.sendall((json.dumps(message) + "\n").encode("utf-8"))
            connection.settimeout(timeout)
            buffer = b""
            while not buffer.endswith(b"\n"):
                chunk = connection.recv(4096)
                if not chunk:
                    break
                buffer += chunk
                if len(buffer) > 65536:
                    raise ControlClientError("reply too large")
    except (OSError, socket.timeout) as exc:
        raise ControlClientError(
            f"The session advertised in {target} is not answering ({exc}). "
            "It probably exited without cleaning up; start a new one with `mirrorlab cam`."
        ) from exc
    try:
        return dict(json.loads(buffer.decode("utf-8")))
    except ValueError as exc:
        raise ControlClientError("the session sent an unreadable reply") from exc
