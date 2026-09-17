# MirrorLab gestures

> [English](GESTURES.md) · [README](../README.md) · [Español](../README.es.md) · [Architecture](ARCHITECTURE.md) · [Filters](FILTERS.md) · [Expressions](EXPRESSIONS.md) · [Cross-platform](CROSS_PLATFORM.md) · [FAQ](FAQ.md)

22 hand gestures, recognised from 21 landmarks by geometric rules — no trained
classifier, no extra model download, no GPU. This document gives the exact matcher for
every one.

List them from the terminal:

```bash
mirrorlab gestures            # emoji, name, Spanish label, bound action
mirrorlab gestures --json     # machine-readable catalog
```

---

## Contents

- [Why geometric instead of learned](#why-geometric-instead-of-learned)
- [The pose model](#the-pose-model)
- [How a gesture wins](#how-a-gesture-wins)
- [Static gestures (21)](#static-gestures-21)
- [Dynamic gestures (6)](#dynamic-gestures-6)
- [Gesture → action bindings](#gesture--action-bindings)
- [The hold-to-confirm ring](#the-hold-to-confirm-ring)
- [Aliases](#aliases)
- [Adding your own gesture](#adding-your-own-gesture)
- [Debugging a gesture that will not fire](#debugging-a-gesture-that-will-not-fire)

---

## Why geometric instead of learned

A trained classifier would buy maybe a fraction of a percent of accuracy on a benchmark
nobody runs on their own webcam, and would cost a model download, an inference pass and
the ability for a user to fix a false negative. The rule-based engine in `gestures.py`:

* needs no extra model — it runs in microseconds on one CPU core;
* is invariant to hand size and distance, because every measurement is normalised by
  `hand_scale()`;
* is readable: `_match_spock` says exactly what a Vulcan salute is, so when it
  misfires you can see why;
* is extensible in about ten lines, which matters more for a playground than a
  leaderboard.

## The pose model

`analyze_hand(hand)` turns raw landmarks into a `HandPose` — a backend-independent
description of one hand. Everything downstream reads that, never the raw array.

| Field | How it is computed |
| --- | --- |
| `scale` | `hand_scale()`: mean distance from the wrist (0) to the four MCP joints (5, 9, 13, 17). Rotation-invariant and stable when fingers are folded. |
| `fingers[name].curl` | `finger_curl()`: `0.65·angle_score + 0.35·reach_score`, where `angle_score = clamp((180 − ∠MCP,PIP,DIP)/120)` and `reach_score = clamp((1.6 − (reach − mcp_reach))/1.0)`, both in hand-scale units. `0` = straight, `1` = fully folded. |
| `fingers[name].extended` | `curl < 0.45` **and** `reach_ratio > 1.02`. Two independent signals must agree. |
| `fingers[name].pip_angle` | interior angle at the PIP joint, in degrees. |
| `fingers[name].reach_ratio` | `distance(wrist, tip) / distance(wrist, pip)` (dimensionless). |
| `fingers["thumb"]` | Its own geometry, because a thumb folds *across* the palm: `thumb_curl = 0.6·clamp((1.05 − thumb_away)/0.7) + 0.4·clamp((150 − thumb_angle)/90)`, extended when `thumb_curl < 0.5 and thumb_away > 0.62`. |
| `pinch_ratio` | `distance(thumb_tip, index_tip) / scale`. Also exposed as `thumb_index_gap`. |
| `pinch` | `pinch_ratio < 0.42` — the boolean form used by air-draw. |
| `spread` | mean **pairwise** fingertip distance ÷ scale. Large for an open palm. |
| `fingers_together` | mean **adjacent** fingertip gap ÷ scale. |
| `ok_ring_ratio` | `distance(thumb_tip, middle_tip) / scale`. |
| `palm_facing_camera` | Sign of the 2-D cross product of `index_mcp − wrist` and `pinky_mcp − wrist`, flipped by handedness. |
| `rotation_deg` | `atan2` of the index-MCP → pinky-MCP line. |
| `extended_count` / `extended_names` / `folded_names` | derived helpers. |
| `describe()` | `"T↑0.21 I↑0.12 M↓0.88 R↓0.91 P↓0.86"` — the fastest way to debug a matcher. |

**Why normalise by hand scale.** A pose that scores 0.9 at 40 cm from the lens must score
0.9 at 1.5 m. Every threshold in this document is expressed in *hand units* — `hand_scale`
divides the apparent size out. Without it, gesture control would only work if you sat
still, and you would need one threshold set per distance.

### The two matcher families

**`_pattern(extended, folded)`** returns `hits / total` over the named fingers:

```python
def _pattern(extended, folded):
    def matcher(pose):
        total = len(extended) + len(folded)
        if total == 0:
            return 0.0
        hits = sum(1 for name in extended if pose.is_extended(name))
        hits += sum(1 for name in folded if pose.is_folded(name))
        return hits / total
    return matcher
```

**`_confidence(pose, names, wanted_extended)`** converts a binary flag into a graded
score from the underlying curl value, so a barely-folded finger contributes less than a
fully-folded one:

```python
# wanted_extended=True  -> (0.45 - curl) / 0.45
# wanted_extended=False -> (curl - 0.55) / 0.45
```

It is used to sharpen the hand-written matchers. Every matcher is wrapped by
`GestureDefinition.match()`, which clamps to `[0, 1]` and **swallows exceptions**,
returning `0.0` — a broken custom rule cannot take down the render loop.

## How a gesture wins

`classify_gesture(pose)` evaluates every definition, skips anything scoring `<= 0.0`,
keeps a sorted score table, and picks the highest score that clears its **own** threshold.
One explicit correction is applied afterwards:

```python
# Generic pinch must not shadow OK: OK requires the other fingers up.
if best_name == "pinch" and scores.get("ok", 0.0) >= GESTURES["ok"].threshold:
    best_name, best_score = "ok", scores["ok"]
```

When nothing clears the bar the result is `GestureMatch(name="none", score=0.0,
definition=None)`, so callers can tell "no hand" apart from "hand doing something
unrecognised". `GestureMatch.scores` carries the full table, sorted descending.

---

## Static gestures (21)

`Act` is the effective binding from `actions.DEFAULT_BINDINGS` — see
[Gesture → action bindings](#gesture--action-bindings).

### Counting gestures

| Emoji | Name | Español | English | Threshold | Exact rule | Demo |
| --- | --- | --- | --- | --- | --- | --- |
| 🖐️ | `open_palm` | Palma abierta | Open palm | 0.60 | `extended_count >= 5`, then `0.65 + 0.35·clamp((spread − 0.55)/0.55)`. Requires all five fingers extended and rewards a wide spread. | Spread your hand wide at the camera to reset the state. |
| ✊ | `fist` | Puño | Fist | 0.55 | `extended_count == 0`, then `0.55 + 0.45·confidence(all five fingers folded)`. | Close your hand to freeze the frame. |
| ☝️ | `pointing` | Señalando | Pointing | 0.75 | `_pattern(["index"], ["middle","ring","pinky"])` — index extended, three folded. Thumb is ignored. | Point to turn on air-draw, then draw in the air. |
| ✌️ | `peace` | Victoria | Peace | 0.70 | `_pattern(["index","middle"], ["ring","pinky"])` — a 4-finger pattern, thumb ignored. | Flash a peace sign to cycle to the next filter. |
| 3️⃣ | `three` | Tres | Three | 0.70 | `_pattern(["index","middle","ring"], ["pinky"])`. | Three fingers to step back a filter. |
| 4️⃣ | `four` | Cuatro | Four | 0.72 | `_pattern(["index","middle","ring","pinky"], [])` — all four long fingers up; the thumb is not consulted, so a raised or tucked thumb both pass. | Four fingers to toggle AR effects on and off. |
| 🤏 | `pinch` | Pellizco | Pinch | 0.60 | `clamp((0.45 − pinch_ratio)/0.28)` — thumb and index tips close together. | Hold a pinch as the precision control / zoom input. |
| 🫳 | `claw` | Garra | Claw | 0.60 | At least 3 of the 4 long fingers must have `0.405 < curl < 0.95` (partial curl); returns `(count/4)·0.9`. | Half-close your hand into a claw to "grab". |
| 1️⃣ | `one` | Uno | One | 0.75 | `_pattern(["thumb"], ["index","middle","ring","pinky"])` — only the thumb out, all four long fingers folded. | Thumb-only jumps straight to `original`. |

### Number and symbol gestures

| Emoji | Name | Español | English | Threshold | Exact rule | Demo |
| --- | --- | --- | --- | --- | --- | --- |
| 6️⃣ | `six` | Seis | Six | 0.72 | `_pattern(["thumb","index"], ["middle","ring","pinky"])` — also reads as an "L". | Thumb + index jumps to `cartoon`. |
| 7️⃣ | `seven` | Siete | Seven | 0.72 | `_pattern(["thumb","index","middle"], ["ring","pinky"])`. | Thumb + two fingers jumps to `sketch`. |
| 8️⃣ | `eight` | Ocho | Eight | 0.72 | `_pattern(["thumb","index","middle","ring"], ["pinky"])`. | Thumb + three fingers jumps to `thermal`. |
| 👍 | `thumbs_up` | Pulgar arriba | Thumbs up | 0.60 | Thumb extended **and** all four long fingers folded (hard gate, returns `0` otherwise), then `0.5·confidence(4 folded) + 0.5·clip((others_y − thumb_y)/(0.9·scale))`. The thumb tip must sit clearly **above** the other fingertips — smaller `y`. | Thumbs up saves a snapshot. |
| 👎 | `thumbs_down` | Pulgar abajo | Thumbs down | 0.60 | Mirror of the above: `0.5·confidence(4 folded) + 0.5·clip((thumb_y − others_y)/(0.9·scale))` — the thumb tip must sit below the other fingertips. | Thumbs down deletes the last capture. |
| 👌 | `ok` | Señal OK | OK sign | 0.62 | `0.65·clip((0.55 − pinch_ratio)/0.30) + 0.35·(extended middle+ring+pinky)/3`. The pinch supplies most of the score; the raised fingers confirm it is an OK and not a plain pinch. | OK toggles the HUD. |
| 🤘 | `rock` | Rock | Rock | 0.75 | `_pattern(["index","pinky"], ["middle","ring"])` — horns. Thumb ignored. | Rock on toggles the `glitch` filter. |
| 🤙 | `call_me` | Llamada | Call me | 0.70 | `_pattern(["thumb","pinky"], ["index","middle","ring"])` — "hang loose". | Shaka toggles mirror mode. |
| 🤟 | `ily` | Te quiero | I love you | 0.72 | `_pattern(["thumb","index","pinky"], ["middle","ring"])` — the ASL sign. | The love sign jumps to the `love` filter. |
| 🖖 | `spock` | Saludo vulcano | Vulcan salute | 0.55 | Hard gate: all four long fingers extended **and** thumb folded, then `clamp((middle_gap − max(inner_gap, outer_gap))/0.45)`, where the gaps are fingertips distances ÷ scale. The middle/ring split must exceed both outer gaps. | Live long and prosper — cycles the HUD theme. |
| 🔫 | `gun` | Pistola | Gun | 0.68 | Thumb **and** index extended, middle/ring/pinky folded (hard gate), then `0.6 + 0.4·confidence(3 folded)`. | Finger gun toggles the HUD. |
| 🔍 | `pinch_zoom` | Zoom con pinza | Pinch zoom | 0.60 | Calls the same function as `pinch`. The intent is a two-hand pinch whose span drives zoom; the single-hand case is what the matcher actually scores. | Two-handed zoom is a roadmap item — see [ROADMAP.md](../ROADMAP.md). |
| • | `none` | Sin gesto | No gesture | 2.00 | `lambda pose: 0.0`. The threshold is deliberately unreachable, so `none` can never win a match — it exists so the HUD can render "searching…". | — |

`none` is included in the catalog because `mirrorlab gestures --json` and the website both
iterate `GESTURES`; `mirrorlab gestures` skips it when printing.

---

## Dynamic gestures (6)

`GestureTracker` watches the **centre** of the largest hand over time and fires motion
events. Static gestures need a pose; dynamic ones need a trajectory. It keeps a deque of
`(timestamp, x, y)` in normalised coordinates (`history=18`) and applies a cooldown per
event name (`0.8 s`).

| Emoji | Name | Español | English | Exact rule | Demo |
| --- | --- | --- | --- | --- | --- |
| 👋 | `wave` | Saludo | Wave | Over the last 8 horizontal steps larger than `0.012`, at least **4 direction flips** out of ≥ 5 samples. Strength is `min(1, flips/5)`. | Wave at the camera to save a snapshot. |
| 🔄 | `circle` | Círculo | Circle | Within a `0.65 s` window: chord `≥ 0.16`, path efficiency `chord/path_length < 0.6`, and maximum deviation from the chord `> 0.06`. A curved path fails the straightness test in a measurable way, which is how a circle is separated from a swipe. | Draw a circle in the air to cycle the HUD theme. |
| ➡️ | `swipe_right` | Deslizar derecha | Swipe right | In the window, `chord ≥ 0.16`, `|dx| ≥ |dy|`, `dx > 0`, and `speed = chord/duration` gives `strength = clamp((speed − 0.25)/1.4) > 0`. | Swipe right for the next filter. |
| ⬅️ | `swipe_left` | Deslizar izquierda | Swipe left | Same, with `dx < 0`. | Swipe left for the previous filter. |
| ⬇️ | `swipe_down` | Deslizar abajo | Swipe down | Same, but `|dy| > |dx|` and `dy > 0`. | Swipe down for the previous preset. |
| ⬆️ | `swipe_up` | Deslizar arriba | Swipe up | Same, with `dy < 0`. | Swipe up for the next preset. |

Swipe direction uses the **dominant axis**, so a diagonal flick still resolves to exactly
one direction instead of being rejected. After a swipe fires, the history is cleared, so
one motion cannot fire twice. Dynamic gestures fire **immediately** — they do not go
through the dwell state machine, because the motion *is* the confirmation.

`GestureTracker.SWIPES` lists exactly the six motion gestures the tracker can emit:
`swipe_left`, `swipe_right`, `swipe_up`, `swipe_down`, `circle` and `wave`. There is no
`push`/`pull`: an earlier draft declared them, but no code path ever constructed the
events, and advertising a gesture that can never fire is worse than not having it. The
recipe for adding them for real is at the end of this document.

---

## Gesture → action bindings

`actions.DEFAULT_BINDINGS` is the table the running app actually uses. It is a superset of
the `action` field declared on each `GestureDefinition`, and it is what `mirrorlab
gestures` prints.

| Gesture | Action | What happens |
| --- | --- | --- |
| ✌️ `peace` | `next_filter` | Next filter in alphabetical order |
| 3️⃣ `three` | `prev_filter` | Previous filter |
| 🖐️ `open_palm` | `toggle_landmarks` | Show/hide the face mesh and hand skeletons |
| ✊ `fist` | `toggle_freeze` | Freeze the frame |
| 👍 `thumbs_up` | `snapshot` | Save a PNG/JPG of exactly what you see |
| 👎 `thumbs_down` | `discard` | Delete the most recent capture |
| 👌 `ok` | `toggle_hud` | Show/hide the HUD |
| 🤘 `rock` | `toggle_glitch` | Switch to `glitch`, or back to `original` |
| 🤟 `ily` | `filter:love` | Jump to the `love` filter |
| ☝️ `pointing` | `air_draw` | Turn air-draw on or off |
| 🤏 `pinch` | `pinch` | Precision input (used by air-draw as the eraser) |
| 🤙 `call_me` | `toggle_mirror` | Mirror mode on/off |
| 🔫 `gun` | `toggle_hud` | Show/hide the HUD |
| 4️⃣ `four` | `toggle_effects` | AR effects on/off |
| 🖖 `spock` | `cycle_theme` | Next HUD palette |
| 1️⃣ `one` | `filter:original` | Straight to `original` |
| 6️⃣ `six` | `filter:cartoon` | Straight to `cartoon` |
| 7️⃣ `seven` | `filter:sketch` | Straight to `sketch` |
| 8️⃣ `eight` | `filter:thermal` | Straight to `thermal` |
| ➡️ `swipe_right` | `next_filter` | Next filter |
| ⬅️ `swipe_left` | `prev_filter` | Previous filter |
| ⬆️ `swipe_up` | `next_preset` | Next curated preset |
| ⬇️ `swipe_down` | `prev_preset` | Previous preset |
| 👋 `wave` | `snapshot` | Save a snapshot |
| 🔄 `circle` | `cycle_theme` | Next HUD palette |

`three`, `claw`, `pinch_zoom` and `none` have no binding: they are recognised, shown in the
HUD and counted in the session summary, but they do not fire an action. Disable the whole
mechanism with `--no-gesture-control` (gestures are still detected and displayed), or turn
off hand tracking entirely with `--no-hands`.

## The hold-to-confirm ring

The hard part of gesture control is not recognising a pose — it is stopping the app from
firing the same action thirty times a second while your hand is still in frame.
`GestureController` solves it with a four-stage state machine:

1. **Majority vote.** The last `history=5` frames vote; a gesture must hold a strict
   majority (`count·2 > len`) to become the candidate. A single-frame flicker never
   reaches the next stage.
2. **Dwell.** The pose must be held for `dwell = 0.6 s`. The wait is drawn as a filling
   ring around the hand centre, labelled with the pending gesture and its action. **This
   ring is the single most important affordance in the gesture system**: without it a user
   cannot tell whether the app saw them, whether they need to hold longer, or whether it
   already fired. It is what makes gesture control feel intentional instead of twitchy.
3. **Refractory period.** After firing, the same gesture is ignored for `refractory = 0.9 s`.
4. **Release.** The dwell is disarmed after one shot and only re-armed when the pose
   changes — so one thumbs-up is one snapshot, not a burst.

`GestureController.draw_ring()` renders it: a grey guide circle, an arc sweeping from
−90° clockwise by `360°·progress`, an extra outline at 100 %, and the
`"<gesture> → <action>"` label underneath. The app draws it at the primary-hand centre
whenever `controller.pending` is set:

```python
self.controller.draw_ring(
    frame, centre, max(26, frame.shape[0] // 18), self.palette.primary,
    thickness=max(3, frame.shape[0] // 240),
    label=f"{self.controller.pending} → {action}",
)
```

To make gesture control snappier while you experiment, lower `dwell` in
`GestureController(dwell=…)`. Values below ~0.3 s start firing on gestures you were only
passing through.

---

## Aliases

`GESTURE_ALIASES` maps alternate spellings onto canonical names, and
`resolve_gesture_name()` normalises case, dashes and spaces first. So `"Thumb Up"`,
`thumb-up`, `thumb_up`, `thumbsup` and `like` all resolve to `thumbs_up`, which is what
`gesture_display()` uses to turn a name into an `"👍 Pulgar arriba"` label for the CLI and
the HUD.

Note the scope: the alias table is a **library-level helper**, not a CLI flag. There is no
`--gesture` option — gestures are bound to actions by `actions.DEFAULT_BINDINGS`, which uses
canonical names, and the only gesture-related switch on the command line is
`--no-gesture-control`. Aliases matter when you call the API yourself, or when you build a
binding table in your own code and want it forgiving.

| Alias | Canonical |
| --- | --- |
| `point`, `point_up`, `index` | `pointing` |
| `victory`, `v`, `two` | `peace` |
| `thumb_up`, `thumbsup`, `like` | `thumbs_up` |
| `thumb_down`, `thumbsdown`, `dislike` | `thumbs_down` |
| `okay`, `perfect` | `ok` |
| `horns`, `metal` | `rock` |
| `shaka`, `hang_loose` | `call_me` |
| `love`, `i_love_you` | `ily` |
| `vulcan` | `spock` |
| `palm`, `stop` | `open_palm` |
| `grab` | `claw` |
| `pinching` | `pinch` |

The same normalisation is applied to filter names by `get_filter()` and to expression
names by `resolve_expression_name()`, so the CLI is forgiving everywhere.

## Adding your own gesture

Three steps, no registry edits beyond one entry.

**1. Write a matcher.** Read the pose, return a score in `[0, 1]`:

```python
def _match_l_shape(pose: HandPose) -> float:
    """Thumb and index extended, both clearly separated (an 'L')."""
    if not (pose.is_extended("thumb") and pose.is_extended("index")):
        return 0.0
    if not all(pose.is_folded(n) for n in ("middle", "ring", "pinky")):
        return 0.0
    # The angle at the thumb-index web is what distinguishes an L from a gun:
    # an L opens to roughly 90 degrees, a gun points both fingers forward.
    web = angle(pose.landmarks[THUMB_MCP], pose.landmarks[INDEX_MCP], pose.landmarks[INDEX_PIP])
    return 0.6 + 0.4 * clamp((web - 45.0) / 45.0)
```

**2. Register it** in `gestures.py`:

```python
_register(GestureDefinition(
    name="l_shape",
    label="L shape",
    label_es="Forma de L",
    emoji="🫰",
    matcher=_match_l_shape,
    threshold=0.68,
    category="symbol",
    description="Thumb and index at a right angle, other fingers folded.",
    action="toggle_hud",
))
```

**3. Bind it** in `actions.DEFAULT_BINDINGS` if it should *do* something:

```python
"l_shape": "toggle_hud",
```

The catalog, `mirrorlab gestures`, the HUD badge and the session summary all pick it up
automatically. A gesture with a matcher but no binding is recognised and displayed, which
is a fine way to test a rule before you give it power over the UI.

Practical notes:

* **Only use `HandPose` accessors.** Indexing `pose.landmarks` directly re-derives
  something the pose already normalised, and it will not survive a rotation or a distance
  change. The one exception above uses landmarks for an *angle*, which is scale-free by
  construction — that is the pattern to copy when you need real geometry.
* **Prefer `_pattern()`** unless it genuinely fails. Hand-written matchers are harder to
  reason about and easier to overfit to your own hand.
* **Calibrate from the score table, not by feel.** Log `match.scores` while performing the
  pose, and set the threshold above the noise floor of the gestures you confuse it with.
  `GestureMatch.scores` is already sorted for exactly this.
* **Watch for shadowing.** If your new gesture is a superset of an existing one, add an
  explicit tie-break in `classify_gesture` the way `pinch`/`ok` does, with a comment.
* **Add an alias and a Spanish label.** The HUD is bilingual.

### Adding a dynamic gesture

Add an entry to `GestureTracker.SWIPES` as `(label, label_es, emoji)`, then emit it from
`update()`:

```python
SWIPES = {
    # …
    "push": ("Push", "Empujar", "🫸"),
}
```

To fire it you need a signal the tracker does not yet have — hand *depth*. `HandObservation`
carries `world_landmarks` (metric, wrist-centred), so a push is a falling mean `z` over a
short window:

```python
# inside GestureTracker.update(), after the wave check
depth = <mean z of the primary hand's world landmarks>
self._depth_history.append((now, depth))
window = [s for s in self._depth_history if now - s[0] <= self.max_duration]
if len(window) >= 4:
    dz = depth - window[0][1]
    speed = abs(dz) / max(now - window[0][0], 1e-3)
    if abs(dz) > self.min_depth and speed > 0.3 and self._ready("push" if dz < 0 else "pull", now):
        name = "push" if dz < 0 else "pull"
        self._last_fire[name] = now
        return self._make(name, clamp(speed, 0.0, 1.0), now)
```

Then bind `"push"` and `"pull"` in `DEFAULT_BINDINGS`. Until you do, they are inert.

## Debugging a gesture that will not fire

1. **Check hand tracking is alive.** `mirrorlab doctor` shows the hand backend; if it says
   `none`, MediaPipe is missing and every gesture is disabled by design.
2. **Look at `describe()`.** `HandPose.describe()` prints
   `T↑0.21 I↑0.12 M↓0.88 R↓0.91 P↓0.86` for every finger. If the finger you expect to be
   `↓` reads `↑`, the problem is the pose, not the matcher.
3. **Print the score table.** `GestureMatch.scores` holds every non-zero score, sorted.
   If your gesture is second at 0.64 against a 0.68 threshold, lower the threshold or
   sharpen the matcher — do not guess.
4. **Turn on debug logs.** `mirrorlab run -v` logs every action with the gesture that
   triggered it, plus which backend initialised.
5. **Check the dwell.** The action fires at 0.6 s, not on the first frame. If the ring
   never fills, the majority vote is failing — the pose is flickering between two
   gestures, so two similar gestures need better separation.
6. **Check the environment.** A hand partly out of frame, backlit, or moving fast enough
   to blur will drop landmarks. Good, even light and the whole hand visible is not a
   platitude — it is the difference between 0.9 and 0.4 on every matcher in this document.

See [ARCHITECTURE.md](ARCHITECTURE.md#8-the-gesture-classifier) for how the classifier fits
into the pipeline and [EXPRESSIONS.md](EXPRESSIONS.md) for the face side.
