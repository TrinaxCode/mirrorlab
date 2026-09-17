"""Gesture-driven control: turn recognised poses into actions.

The hard part of gesture control is not recognising a pose — it is stopping the
app from firing the same action thirty times a second while your hand is still
in frame. MirrorLab solves it with a small, explicit state machine:

1. **Majority vote** over the last few frames removes single-frame misreads.
2. **Dwell** — the pose must be held for ``dwell`` seconds before it fires, and
   the wait is drawn as a filling ring so the confirmation is visible. That
   ring is what makes gesture control feel intentional instead of twitchy.
3. **Refractory period** after firing stops a held pose from repeating.
4. **Release** — the hand must leave the pose before the same action can fire
   again, so a "thumbs up" is one snapshot, not a burst.
"""

from __future__ import annotations

import time
from collections import Counter, deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np

from .gestures import DynamicGesture, GestureMatch, GestureTracker
from .utils.logging import get_logger

__all__ = ["DEFAULT_BINDINGS", "ActionEvent", "GestureController", "action_catalog"]

log = get_logger("actions")


@dataclass
class ActionEvent:
    """Something the user asked for, by gesture or by key."""

    action: str
    source: str = "gesture"  # "gesture" | "key" | "dynamic"
    gesture: str = ""
    label: str = ""
    value: Optional[float] = None
    timestamp: float = field(default_factory=time.perf_counter)
    payload: Dict[str, object] = field(default_factory=dict)

    def describe(self) -> str:
        if self.label:
            return f"{self.label} → {self.action}"
        return self.action


#: Gesture → action. Chosen so the most useful actions have the easiest poses.
DEFAULT_BINDINGS: Dict[str, str] = {
    "peace": "next_filter",
    "three": "prev_filter",
    "open_palm": "toggle_landmarks",
    "fist": "toggle_freeze",
    "thumbs_up": "snapshot",
    "thumbs_down": "discard",
    "ok": "toggle_hud",
    "rock": "toggle_glitch",
    "ily": "filter:love",
    "pointing": "air_draw",
    "pinch": "pinch",
    "call_me": "toggle_mirror",
    "gun": "toggle_hud",
    "four": "toggle_effects",
    "spock": "cycle_theme",
    "one": "filter:original",
    "six": "filter:cartoon",
    "seven": "filter:sketch",
    "eight": "filter:thermal",
    "swipe_left": "prev_filter",
    "swipe_right": "next_filter",
    "swipe_up": "next_preset",
    "swipe_down": "prev_preset",
    "wave": "snapshot",
    "circle": "cycle_theme",
}


class _Dwell:
    """Tracks how long one gesture has been held, with hysteresis."""

    __slots__ = ("armed", "name", "progress", "started")

    def __init__(self) -> None:
        self.name = ""
        self.started = 0.0
        self.progress = 0.0
        self.armed = False

    def reset(self) -> None:
        self.name = ""
        self.started = 0.0
        self.progress = 0.0
        self.armed = False


class GestureController:
    """Turns a stream of gesture matches into a stream of :class:`ActionEvent`.

    Args:
        bindings: Gesture name → action name. Defaults to :data:`DEFAULT_BINDINGS`.
        dwell: Seconds a pose must be held before its action fires.
        refractory: Seconds to ignore a gesture after it fires.
        history: Number of frames in the majority-vote window.
        enabled: Master switch (``--no-gesture-control`` disables it).

    Example:
        >>> controller = GestureController()                       # doctest: +SKIP
        >>> for event in controller.update(result.gestures, result.dynamic):
        ...     apply(event)                                       # doctest: +SKIP
    """

    def __init__(
        self,
        bindings: Optional[Dict[str, str]] = None,
        dwell: float = 0.6,
        refractory: float = 0.9,
        history: int = 5,
        enabled: bool = True,
    ) -> None:
        self.bindings = dict(bindings or DEFAULT_BINDINGS)
        self.dwell = float(max(0.0, dwell))
        self.refractory = float(max(0.0, refractory))
        self.enabled = bool(enabled)

        self._votes: Deque[str] = deque(maxlen=max(1, int(history)))
        self._dwell = _Dwell()
        self._last_fire: Dict[str, float] = {}
        self._held: str = ""
        self._released = True
        self.last_progress = 0.0
        self.last_gesture = ""
        self.history: List[ActionEvent] = []

    # ------------------------------------------------------------------ #
    def update(
        self,
        matches: Sequence[GestureMatch],
        dynamic: Sequence[DynamicGesture] = (),
        timestamp: Optional[float] = None,
    ) -> List[ActionEvent]:
        """Feed this frame's gestures; returns the actions that fired."""
        if not self.enabled:
            return []
        now = time.perf_counter() if timestamp is None else float(timestamp)
        events: List[ActionEvent] = []

        # --- dynamic (motion) gestures fire immediately -------------------- #
        for event in dynamic:
            action = self.bindings.get(event.name)
            if action and self._ready(event.name, now):
                self._last_fire[event.name] = now
                events.append(
                    ActionEvent(
                        action=action,
                        source="dynamic",
                        gesture=event.name,
                        label=event.display(),
                        value=event.strength,
                        timestamp=now,
                    )
                )

        # --- static gestures need a stable vote and a dwell ---------------- #
        best = max(matches, key=lambda m: m.score) if matches else None
        candidate = best.name if (best and best.name != "none") else "none"
        self._votes.append(candidate)
        stable = self._majority()

        # Release on the *raw* frame, not on the vote. If we waited for the
        # vote window to drain, a one-shot latch could never re-arm after the
        # hand left the pose — the majority would still hold the old gesture
        # and `armed` would stay False forever.
        if candidate == "none":
            self._dwell.reset()
            self._held = ""
            self._released = True
            self.last_progress = 0.0
            self.last_gesture = ""
            return events

        if stable == "none":
            # The current frame has a pose but the vote is inconclusive: stop
            # progressing, yet keep the latch so a brief flicker is survivable.
            # Restarting the clock is what makes the dwell mean *held
            # continuously* — otherwise an alternating pose could accumulate
            # enough wall-clock time to fire.
            self._dwell.started = now
            self.last_progress = 0.0
            return events

        self.last_gesture = stable
        binding = self.bindings.get(stable)

        if stable != self._held:
            # A new pose re-arms the machine, but only after a real release.
            self._held = stable
            self._dwell.reset()
            self._dwell.name = stable
            self._dwell.started = now
            self._dwell.armed = True
            self.last_progress = 0.0

        if not binding or not self._dwell.armed:
            self.last_progress = 0.0
            return events

        if self.dwell <= 0.0:
            self._dwell.progress = 1.0
        else:
            self._dwell.progress = min(1.0, (now - self._dwell.started) / self.dwell)
        self.last_progress = self._dwell.progress

        if self._dwell.progress >= 1.0 and self._ready(stable, now):
            self._last_fire[stable] = now
            self._dwell.armed = False  # one shot until the pose is released
            label = best.display() if best else stable
            event = ActionEvent(
                action=binding,
                source="gesture",
                gesture=stable,
                label=label,
                value=best.score if best else 0.0,
                timestamp=now,
            )
            events.append(event)
            self.history.append(event)
            del self.history[:-50]

        return events

    # ------------------------------------------------------------------ #
    def _majority(self) -> str:
        if not self._votes:
            return "none"
        counts = Counter(self._votes)
        top, count = counts.most_common(1)[0]
        # Require a real majority so a flicker never triggers a dwell.
        return top if count * 2 > len(self._votes) else "none"

    def _ready(self, gesture: str, now: float) -> bool:
        return (now - self._last_fire.get(gesture, -1e9)) >= self.refractory

    def reset(self) -> None:
        self._votes.clear()
        self._dwell.reset()
        self._held = ""
        self._released = True
        self.last_progress = 0.0
        self.last_gesture = ""

    # ------------------------------------------------------------------ #
    @property
    def pending(self) -> str:
        """Gesture currently being held, if any."""
        return self._held

    def draw_ring(
        self,
        frame: np.ndarray,
        centre: Tuple[int, int],
        radius: int,
        colour: Tuple[int, int, int] = (120, 250, 200),
        thickness: int = 5,
        label: str = "",
    ) -> None:
        """Draw the hold-to-confirm progress ring.

        This is the single most important piece of affordance in the whole
        gesture system: without it users cannot tell whether the app saw them,
        whether they need to hold longer, or whether it already fired.
        """
        progress = self.last_progress
        if progress <= 0.0 or not self._held:
            return
        cv2.circle(frame, centre, radius, (70, 70, 75), max(1, thickness // 2), cv2.LINE_AA)
        start = -90.0
        end = start + 360.0 * progress
        cv2.ellipse(
            frame,
            centre,
            (radius, radius),
            0,
            start,
            end,
            colour,
            thickness,
            cv2.LINE_AA,
        )
        if progress >= 1.0:
            cv2.circle(frame, centre, radius + thickness, colour, 2, cv2.LINE_AA)
        if label:
            font = cv2.FONT_HERSHEY_DUPLEX
            scale = max(0.4, radius / 60.0)
            size = cv2.getTextSize(label, font, scale, 1)[0]
            cv2.putText(
                frame,
                label,
                (centre[0] - size[0] // 2, centre[1] + radius + int(22 * scale)),
                font,
                scale,
                colour,
                1,
                cv2.LINE_AA,
            )


def action_catalog() -> List[dict]:
    """Every gesture→action binding, for the CLI and the website.

    Covers both the static poses in :data:`~mirrorlab.gestures.GESTURES` and the
    motion gestures detected by :class:`~mirrorlab.gestures.GestureTracker`, so
    the published catalog and the bindings table can never drift apart.
    """
    from .gestures import GESTURES

    rows = []
    for gesture, action in DEFAULT_BINDINGS.items():
        definition = GESTURES.get(gesture)
        if definition is not None:
            rows.append(
                {
                    "gesture": gesture,
                    "emoji": definition.emoji,
                    "label": definition.label,
                    "label_es": definition.label_es,
                    "action": action,
                    "kind": "static",
                    "description": definition.description,
                }
            )
            continue
        motion = GestureTracker.SWIPES.get(gesture)
        if motion is not None:
            label, label_es, emoji = motion
            rows.append(
                {
                    "gesture": gesture,
                    "emoji": emoji,
                    "label": label,
                    "label_es": label_es,
                    "action": action,
                    "kind": "dynamic",
                    "description": "Se detecta por el movimiento de la mano, no por la postura.",
                }
            )
    return rows
