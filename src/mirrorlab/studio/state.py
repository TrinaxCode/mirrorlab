"""Runtime state and the action vocabulary.

Three different things want to change the camera while it runs: a hand gesture,
a key in the preview window, and ``mirrorlab ctl`` from another terminal. They
all speak the same small language of *actions* and all go through
:meth:`StudioState.apply_action`, so a gesture and a script can never disagree
about what ``privacy`` means.

Action grammar (``name`` or ``name:argument``):

====================  ==========================================================
``privacy``           toggle the privacy shutter (``privacy:on`` / ``privacy:off``)
``background:MODE``   set the background mode (``off`` ``blur`` ``replace`` ``green`` ``black``)
``background_next``   cycle through the modes that are currently usable
``framing``           toggle auto-framing (``framing:on`` / ``framing:off``)
``light``             toggle studio light (``light:on`` / ``light:off``)
``reaction:NAME``     float a reaction icon (``love`` ``thumbs_up`` ``ok`` ``star``)
``snapshot``          ask the session to save a still
``noop``              do nothing (lets a gesture be explicitly unbound)
====================  ==========================================================
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from .reactions import REACTIONS
from .settings import BACKGROUND_MODES, StudioSettings

__all__ = ["ActionResult", "StudioState", "parse_action"]


@dataclass(frozen=True)
class ActionResult:
    ok: bool
    message: str


def parse_action(action: str) -> Tuple[str, str]:
    """Split ``name:argument`` into ``(name, argument)``; the argument may be empty."""
    name, _, argument = action.strip().partition(":")
    return name.strip().lower(), argument.strip().lower()


def _parse_switch(argument: str, current: bool) -> Tuple[bool, bool]:
    """Return ``(valid, new_value)`` for an optional ``on``/``off`` argument."""
    if argument == "":
        return True, not current
    if argument in {"on", "true", "1", "yes"}:
        return True, True
    if argument in {"off", "false", "0", "no"}:
        return True, False
    return False, current


@dataclass
class StudioState:
    """The mutable part of a session. Everything else is immutable settings."""

    background: str = "off"
    auto_frame: bool = False
    studio_light: bool = False
    privacy: bool = False
    #: Whether ``replace`` is usable (an image was supplied and loaded).
    has_replace_image: bool = False
    pending_reactions: List[str] = field(default_factory=list)
    snapshot_requested: bool = False
    changes: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    @classmethod
    def from_settings(cls, settings: StudioSettings, has_replace_image: bool = False) -> "StudioState":
        background = settings.background
        if background == "replace" and not has_replace_image:
            # Replace without an image is a blur (BackgroundProcessor does the same);
            # reflect that honestly in the state instead of claiming "replace".
            background = "blur"
        return cls(
            background=background,
            auto_frame=settings.auto_frame,
            studio_light=settings.studio_light,
            privacy=settings.privacy_on_start,
            has_replace_image=has_replace_image,
        )

    # ------------------------------------------------------------------ #
    def usable_backgrounds(self) -> List[str]:
        modes = ["off", "blur"]
        if self.has_replace_image:
            modes.append("replace")
        return modes

    def snapshot(self) -> Dict[str, object]:
        with self._lock:
            return {
                "background": self.background,
                "auto_frame": self.auto_frame,
                "studio_light": self.studio_light,
                "privacy": self.privacy,
            }

    def drain_reactions(self) -> List[str]:
        with self._lock:
            drained, self.pending_reactions = self.pending_reactions, []
        return drained

    def take_snapshot_request(self) -> bool:
        with self._lock:
            requested, self.snapshot_requested = self.snapshot_requested, False
        return requested

    # ------------------------------------------------------------------ #
    def apply_action(self, action: str) -> ActionResult:
        """Apply one action. Never raises: bad input returns ``ok=False`` with a reason."""
        name, argument = parse_action(action)
        with self._lock:
            result = self._apply(name, argument)
            if result.ok and name != "noop":
                self.changes += 1
            return result

    def _apply(self, name: str, argument: str) -> ActionResult:
        if name == "noop":
            return ActionResult(True, "no action")

        if name == "privacy":
            valid, value = _parse_switch(argument, self.privacy)
            if not valid:
                return ActionResult(False, f"privacy takes 'on' or 'off', not {argument!r}")
            self.privacy = value
            return ActionResult(True, "privacy shutter " + ("closed" if value else "open"))

        if name == "background":
            if argument not in BACKGROUND_MODES:
                return ActionResult(False, f"background must be one of {', '.join(BACKGROUND_MODES)}")
            if argument == "replace" and not self.has_replace_image:
                return ActionResult(False, "replace needs an image: start with --bg-image PATH")
            self.background = argument
            return ActionResult(True, f"background: {argument}")

        if name == "background_next":
            modes = self.usable_backgrounds()
            index = modes.index(self.background) if self.background in modes else -1
            self.background = modes[(index + 1) % len(modes)]
            return ActionResult(True, f"background: {self.background}")

        if name in {"framing", "light"}:
            attribute = "auto_frame" if name == "framing" else "studio_light"
            valid, value = _parse_switch(argument, getattr(self, attribute))
            if not valid:
                return ActionResult(False, f"{name} takes 'on' or 'off', not {argument!r}")
            setattr(self, attribute, value)
            return ActionResult(True, f"{name}: {'on' if value else 'off'}")

        if name == "reaction":
            if argument not in REACTIONS:
                return ActionResult(
                    False, f"unknown reaction {argument!r}; choose from {', '.join(sorted(REACTIONS))}"
                )
            self.pending_reactions.append(argument)
            del self.pending_reactions[:-8]
            return ActionResult(True, f"reaction: {argument}")

        if name == "snapshot":
            self.snapshot_requested = True
            return ActionResult(True, "snapshot requested")

        return ActionResult(False, f"unknown action {name!r}")
