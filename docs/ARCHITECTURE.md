# MirrorLab architecture

> [English](ARCHITECTURE.md) · [README](../README.md) · [Guía en español](../README.es.md) · [Filters](FILTERS.md) · [Gestures](GESTURES.md) · [Expressions](EXPRESSIONS.md) · [Cross-platform](CROSS_PLATFORM.md) · [FAQ](FAQ.md)

This document explains how MirrorLab is put together: the layers, the modules, the
data model, the threading model and the extension points. It is written for someone
who wants to modify the pipeline, not just run it.

Everything here is derived from the source in `src/mirrorlab/`. When this document and
the code disagree, the code wins.

---

## 1. Design goals

Four constraints shaped every decision in this codebase.

1. **Degrade, never crash.** A webcam project that refuses to start because one
   optional model is missing is a bad webcam project. Every detector sits behind a
   fallback ladder, and every consumer of detector output handles "no detections".
2. **Pure logic must be testable without a camera.** Classifiers, matchers, geometry
   and filter maths are pure functions over NumPy arrays. CI runs them with no camera,
   no network and no MediaPipe.
3. **Latency beats throughput.** The preview must feel like a mirror. A dropped frame is
   invisible; 200 ms of accumulated lag is not.
4. **Explainable beats clever.** Gestures are declarative geometric rules, not a trained
   classifier, because a user can read `_match_spock` and fix it in five lines.

---

## 2. Layered design

Data flows in one direction. Each layer only knows about the layer below it.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ application          mirrorlab.app  ·  mirrorlab.cli                     │
│                      run loop, key handling, gesture→action binding      │
├──────────────────────────────────────────────────────────────────────────┤
│ render               render/hud.py · render/composition.py · recording   │
│                      HUD panels, skeletons, transitions, MP4/GIF output  │
├──────────────────────────────────────────────────────────────────────────┤
│ effects              effects/face.py                                     │
│                      landmark-anchored AR overlays (11 face, 4 hand)     │
├──────────────────────────────────────────────────────────────────────────┤
│ filters              filters/{base,classic,color,artistic,stylize,       │
│                      glitch,utility}.py — chainable frame→frame stages   │
├──────────────────────────────────────────────────────────────────────────┤
│ perception           detectors/engine.py · expressions.py · gestures.py  │
│                      FrameAnalysis → ExpressionResult + GestureMatch[]   │
├──────────────────────────────────────────────────────────────────────────┤
│ detectors            detectors/{backends,face,hands,segmentation,models} │
│                      backend ladder, landmark smoothing, model cache     │
├──────────────────────────────────────────────────────────────────────────┤
│ camera               camera.py                                           │
│                      capture thread, drop-latest slot, synthetic source  │
└──────────────────────────────────────────────────────────────────────────┘
        ▲                                                          │
        └────────────────── NumPy BGR frame ◄───────────────────────┘
```

The dependency rule: **nothing below `perception` imports anything above it**, and
`utils/` imports nothing from the package except `utils/`. That keeps
`expressions.py` and `gestures.py` importable in a bare Python session with only
NumPy installed, which is what makes the test suite fast.

---

## 3. Module map

| Module | Responsibility |
| --- | --- |
| `mirrorlab/__init__.py` | Lazy package facade. PEP 562 `__getattr__` keeps `import mirrorlab` cheap — OpenCV and MediaPipe are only imported when you actually touch `MirrorLab`, `Config` or `get_config`. |
| `mirrorlab/version.py` | `__version_info__`, `__version__`, `CODENAME`. Single source of truth for the version string. |
| `mirrorlab/config.py` | The frozen `Config` dataclass, `DEFAULTS`, layered resolution (defaults → file → `MIRRORLAB_*` env → explicit overrides), validation in `__post_init__`. |
| `mirrorlab/camera.py` | Backend selection per OS, `CameraStream` (threaded drop-latest), `SyntheticSource`, `VideoFileSource`, `open_camera`, `list_cameras`, `probe_backends`, `camera_troubleshooting`, `platform_summary`. |
| `mirrorlab/detectors/base.py` | Backend-independent result types: `Landmark`, `FaceObservation`, `HandObservation`, `FrameAnalysis`, plus the `BLENDSHAPE_NAMES` (52), `HAND_CONNECTIONS`, `FACE_OVAL` and `FACE_TESSELLATION_EDGES` tables. |
| `mirrorlab/detectors/backends.py` | The five face engines and three hand engines, the capability probes (`mediapipe_version`, `_tasks_api`, `_solutions_api`), `probe_environment` and the factories `create_face_backend` / `create_hand_backend`. |
| `mirrorlab/detectors/face.py` | `FaceDetector`: wraps a backend and applies One-Euro landmark smoothing. |
| `mirrorlab/detectors/hands.py` | `HandDetector`: same, with a faster cutoff and handedness-stable track ids. |
| `mirrorlab/detectors/engine.py` | `PerceptionEngine` / `PerceptionResult`: one call per frame returns faces, hands, expression and gestures. |
| `mirrorlab/detectors/models.py` | `MODELS` table (key, filename, URL, size, purpose), cache-directory resolution, atomic download, `find_model`, `ensure_model`, `list_model_status`. |
| `mirrorlab/detectors/segmentation.py` | `SelfieSegmenter` wrapper over MediaPipe `ImageSegmenter` plus `refine_mask` (largest-blob, morphological close, feather). Powers `bg_blur`, `bg_replace` and `privacy`. |
| `mirrorlab/expressions.py` | `EXPRESSIONS` catalogue, `_BlendshapeScorers`, the geometric fallback, `_PRIORITY`, `ExpressionClassifier`. |
| `mirrorlab/gestures.py` | `HandPose` / `FingerState`, the matcher library, `GESTURES`, `GESTURE_ALIASES`, `classify_gesture`, `GestureTracker` for dynamic gestures. |
| `mirrorlab/filters/base.py` | `Filter`, `FilterContext`, `FilterChain`, the `FILTERS` registry, `CATEGORIES`, `build_filter`, shared helpers (`apply_mask_blur`, `tint`, `to_gray_bgr`, `sobel_magnitude`). |
| `mirrorlab/filters/{classic,artistic,stylize,glitch,utility}.py` | The 54 registered filters, grouped by module. Importing the package is what registers them. |
| `mirrorlab/filters/__init__.py` | Re-exports the framework and the `PRESETS` table, and exposes `filter_names()` / `filters_by_category()`. |
| `mirrorlab/effects/face.py` | `FaceEffect` / `HandEffect` base classes, `EffectContext`, the 15 procedural overlays, and the `FACE_EFFECTS` / `HAND_EFFECTS` registries. |
| `mirrorlab/render/hud.py` | `Hud`, `HudState`, and the free functions `draw_hand`, `draw_face`, `draw_badge`, `draw_bar`, `draw_reticle`. Resolution-independent: every size is scaled from `height / 720`. |
| `mirrorlab/render/composition.py` | `blend`, `crossfade`, `letterbox`, `stack_side_by_side`, `tile_grid`, and the `Transition` cross-fade state machine. |
| `mirrorlab/recording.py` | `save_snapshot`, `save_gif`, `Recorder` (threaded `cv2.VideoWriter` with a bounded drop-oldest queue), `SaveResult`. |
| `mirrorlab/airdraw.py` | `AirCanvas` and `Brush`: a persistent drawing layer driven by the index fingertip, with its own One-Euro pen filter. |
| `mirrorlab/utils/geometry.py` | Vector maths: `distance`, `angle`, `hand_scale`, `finger_curl`, `palm_normal`, `polygon_area`, `clamp`, and friends. |
| `mirrorlab/utils/smoothing.py` | `OneEuroFilter`, `EmaFilter`, `SlidingWindow`, `LandmarkSmoother`. |
| `mirrorlab/utils/timing.py` | `FpsMeter` (rolling window plus per-stage profiling) and `Stopwatch`. |
| `mirrorlab/utils/colors.py` | `Palette` and the four HUD themes (`aurora`, `magma`, `mono`, `candy`). |
| `mirrorlab/utils/logging.py` | `get_logger` / `setup_logging`, one namespace per module (`mirrorlab.camera`, `mirrorlab.gestures`, …). |

---

## 4. The backend fallback ladder

### 4.1 Why it exists

Two things are true at the same time:

* **MediaPipe 1.0 removed `mp.solutions`.** Every tutorial written before 2025 uses
  `mp.solutions.face_mesh`, and that namespace no longer exists. A project pinned to it
  is a project that cannot be installed.
* **MediaPipe 1.0.1 aborts on some macOS builds** inside Apple's Metal helper
  (`DrishtiMetalHelper ... Check failed: service_ Service is unavailable`). The Tasks
  API is the right primary backend, but it is not universally safe to install.

MirrorLab resolves this by *probing the host at runtime* instead of trusting a version
number, then walking a quality ladder until something initialises. `backends.py` is
explicit about the trade-offs:

| Backend | Requires | Provides |
| --- | --- | --- |
| `tasks` | `mediapipe>=0.10.9`, Tasks API | 478 landmarks, **52 blendshapes**, 4×4 transformation matrix |
| `solutions` | `mediapipe<1.0`, `mp.solutions` | 468 landmarks, no blendshapes |
| `yunet` | OpenCV `FaceDetectorYN` + a 230 KB ONNX file | 5 landmarks (eyes, nose, mouth corners) |
| `haar` | OpenCV's bundled cascade only | bounding box, no landmarks |
| `none` | — | nothing; face features are disabled |

Hands have a shorter ladder — `tasks` → `solutions` → `none` — because there is no
OpenCV hand-landmark model to fall back to. **Without MediaPipe, hand gestures are
disabled and the app still runs.** That is a designed behaviour, not a failure.

### 4.2 How selection actually works

```python
# src/mirrorlab/detectors/backends.py
builders = {
    "tasks": lambda: TasksFaceBackend(...),
    "solutions": lambda: SolutionsFaceBackend(...),
    "yunet": lambda: YuNetFaceBackend(...),
    "haar": lambda: HaarFaceBackend(...),
}
order = [preferred] if preferred in builders else ["tasks", "solutions", "yunet", "haar"]
for name in order:
    try:
        return builders[name]()
    except Exception as exc:
        log.debug("Face backend %s unavailable: %s", name, exc)
```

Notes that matter when you debug this:

* `preferred="auto"` is the default. Any other value pins that engine — but a *failed*
  pin still falls through to the full ladder, because the exception handler is the same.
* `preferred="none"`, or `max_faces <= 0`, returns `NullFaceBackend` immediately. That is
  how `--no-face` disables the feature without branching anywhere else.
* Failures are logged at `DEBUG`, so `MIRRORLAB_LOG_LEVEL=DEBUG` is how you see which
  rung was tried and why it failed. `mirrorlab doctor` prints the verdict without the
  log noise.
* A backend only "wins" if its constructor succeeds. `TasksFaceBackend.__init__` raises
  when the Tasks API is missing *or* when `ensure_model("face_landmarker")` returns
  `None` — so a machine with no network and no cached model drops to `yunet`, then
  `haar`, then `none`.

### 4.3 What the rest of the code promises

Because `FaceObservation` is a plain dataclass, no backend-specific object ever escapes
`detectors/`. That is the whole trick. Consumers ask *capability* questions:

```python
face.has_blendshapes          # True only for tasks-face
face.count                    # 478 / 468 / 0 (haar returns an empty array)
detector.provides_blendshapes # read by the expression classifier
```

The expression classifier reads `has_blendshapes` and picks a strategy; the UI reads
`face.count < 400` and skips effects that need anchors. Nobody writes
`if backend == "tasks"`.

---

## 5. Data model

All four types live in `detectors/base.py` and `detectors/engine.py`. They are mutable
dataclasses of plain NumPy arrays and dicts — no locks, no back-references to detectors.

### `FaceObservation`

```python
@dataclass
class FaceObservation:
    landmarks: np.ndarray                              # (N, 3) normalized, N = 478/468/0
    blendshapes: Dict[str, float] = field(default_factory=dict)
    transformation_matrix: Optional[np.ndarray] = None  # (4, 4) camera-space pose
    bbox: Optional[Tuple[float, float, float, float]] = None  # x_min, y_min, x_max, y_max
    confidence: float = 1.0
```

Helper methods you should use instead of indexing arrays by hand:

| Member | Meaning |
| --- | --- |
| `has_blendshapes` | `bool(self.blendshapes)` — the capability flag the classifier branches on |
| `count` | number of landmarks, `0` for Haar boxes |
| `point(i)` | landmark `i` as an `(x, y)` float64 array |
| `blend(name, default=0.0)` | one blendshape score, tolerant of a missing channel |
| `pair(left, right)` | mean of a left/right pair — the usual way to read symmetry |
| `bbox_pixels(w, h, pad=0.0)` | integer pixel box, optionally padded by a fraction of its size |

### `HandObservation`

```python
@dataclass
class HandObservation:
    landmarks: np.ndarray                        # (21, 3) normalized image coords
    world_landmarks: Optional[np.ndarray] = None # (21, 3) metric, wrist-centred
    handedness: str = "Unknown"                  # "Left" | "Right" | "Unknown"
    score: float = 1.0
    gesture: str = ""                            # filled in by classify_hands()
    gesture_score: float = 0.0
```

`is_right` is `handedness.lower().startswith("r")` — deliberately tolerant, because the
Solutions and Tasks backends spell the label differently. `classify_hands(hands)` writes
`gesture` and `gesture_score` back onto the observations, which is how the HUD gets
labels without a second lookup.

### `FrameAnalysis`

```python
@dataclass
class FrameAnalysis:
    faces: List[FaceObservation] = field(default_factory=list)
    hands: List[HandObservation] = field(default_factory=list)
    frame_index: int = 0
    timestamp_ms: int = 0
    inference_ms: float = 0.0
    backend: str = ""
```

Convenience accessors: `primary_face` (the **largest** face by bounding-box area, not the
first one), `primary_hand` (index 0), `has_face`, `has_hands`, `hand_by_side("left")`.

### `PerceptionResult`

`PerceptionResult` is the single object the application layer consumes per frame:

```python
@dataclass
class PerceptionResult:
    analysis: FrameAnalysis
    expression: ExpressionResult = field(default_factory=ExpressionResult)
    gestures: List[GestureMatch] = field(default_factory=list)
    dynamic: List[DynamicGesture] = field(default_factory=list)
    timestamp_ms: int = 0
    total_ms: float = 0.0
```

It adds `face`, `hand`, `pose` and `gesture` properties (the most confident match across
all visible hands) plus `gesture_names()` and `describe()`.

Two design details worth copying:

* `ExpressionResult.method` is `"blendshapes"`, `"geometry"` or `"none"`. The UI can tell
  the user *why* a face is being read the way it is, instead of silently degrading.
* `GestureMatch.scores` keeps the **full score table**, sorted descending, not just the
  winner. That is what lets the HUD show runner-up gestures and makes threshold tuning
  a data problem instead of guesswork.

---

## 6. Threading model

MirrorLab runs exactly two threads in steady state, plus one short-lived writer thread
while recording.

### 6.1 Capture thread: drop-latest, not queue

`CameraStream` starts a daemon thread named `mirrorlab-capture` that loops on
`cap.read()` and stores the newest frame behind a lock:

```python
with self._lock:
    self._frame = frame
    self._seq += 1
```

`read()` polls that slot and returns `self._frame.copy()`. There is **no queue**. That is
the entire point.

Consider a 30 fps camera (33 ms per frame) and a detector that takes 40 ms. With a queue,
the consumer falls 7 ms behind every frame and the backlog grows without bound: ten
seconds later you are looking at a ten-second-old image of yourself. With a single slot,
the producer overwrites the frame nobody consumed and the preview stays *live*, just at
40 ms of granularity. Latency stays flat; only smoothness degrades.

Three supporting details:

* `read(timeout=2.0)` returns `None` if no frame arrived in time, so a dead camera cannot
  hang the loop forever.
* `sequence` exposes the frame counter, so a consumer can skip work when the slot has not
  advanced.
* The pump gives up after 30 consecutive failed reads and logs a warning, which is how
  you tell "camera unplugged" apart from "camera slow".

The `Recorder` uses a different policy on purpose: a **bounded drop-oldest queue** of four
frames. Encoding is not perception — losing the newest frame would truncate the clip,
while dropping the oldest only shortens it. Both choices exist to keep the *preview*
honest; the difference is which end of the recording is expendable.

### 6.2 Main thread: detection, filters, effects, render

Everything else happens on the calling thread, in this order:

```
frame ──► cv2.cvtColor(BGR→RGB) ──► face detector ──► hand detector
      ──► expression classifier ──► gesture classifier ──► dynamic tracker
      ──► motion/segmentation (optional) ──► filter chain ──► AR effects
      ──► HUD ──► cv2.imshow ──► recorder.write() ──► key handling
```

This is not laziness. **On macOS, `cv2.imshow` and `cv2.waitKey` must be called from the
main thread**, because Cocoa requires UI work on the main run loop. Pushing the window to
a worker thread produces a hang or an immediate crash. Keeping render on the caller's
thread is the portable choice across all three platforms.

`PerceptionResult.timestamp_ms` is derived from a monotonic `time.perf_counter()` origin
captured in `PerceptionEngine.__init__`, and `_TimestampGuard` (in `backends.py`) forces
strictly increasing stamps, because MediaPipe's VIDEO mode rejects or misbehaves on
duplicate timestamps.

### 6.3 Shutdown

`CameraStream.release()` sets a `threading.Event`, joins the pump with a 1 s timeout and
releases the `VideoCapture`. `Recorder.stop()` pushes a `None` sentinel, joins with a
10 s timeout, releases the writer and then exports the GIF. Both are idempotent enough to
be called from `__exit__`.

---

## 7. Smoothing strategy

Raw MediaPipe landmarks jitter by a pixel or two per frame. Drawing them directly gives
the classic shaky-AR look. MirrorLab uses three complementary techniques, each aimed at a
different signal.

### 7.1 One-Euro filter for landmarks

From Casiez, Roussel & Vogel, *1€ Filter* (CHI 2012). The implementation in
`utils/smoothing.py` is short enough to read in full:

```python
def _alpha(cutoff: float, dt: float) -> float:
    tau = 1.0 / (2.0 * math.pi * max(cutoff, 1e-6))
    return 1.0 / (1.0 + tau / max(dt, 1e-6))
```

Per sample, with `dt` the time since the previous sample:

1. Estimate the derivative: `dx = (x - x_prev) / dt`.
2. Low-pass the derivative with a fixed `d_cutoff` (default `1.0`):
   `dx_hat = a_d·dx + (1 − a_d)·dx_prev`.
3. Make the cutoff **speed-dependent**: `cutoff = min_cutoff + beta·|dx_hat|`.
4. Low-pass the value with that cutoff:
   `x_hat = a·x + (1 − a)·x_prev`, where `a = _alpha(cutoff, dt)`.

A signal at rest has `dx_hat ≈ 0`, so `cutoff ≈ min_cutoff` (default `1.7`) and the output
is heavily smoothed. A fast-moving fingertip raises `cutoff`, which raises `a`, which
tracks the motion with almost no lag. Steady-state jitter and motion response stop being
a trade-off — that is the whole reason this filter exists.

Config exposes the two knobs: `smoothing_min_cutoff` (lower = smoother, laggier) and
`smoothing_beta` (higher = more responsive).

`LandmarkSmoother` applies **one filter per landmark per coordinate**, keyed by a track
id, so 478 face landmarks get 478×3 independent filters — not one shared filter. A shared
filter would couple unrelated points and produce visible warping.

| Caller | track key | cutoff |
| --- | --- | --- |
| `FaceDetector` | face index | `smoothing_min_cutoff` |
| `HandDetector` (image landmarks) | `index + (2 if is_right else 0)` | `smoothing_min_cutoff * 1.3` |
| `HandDetector` (world landmarks) | the above `+ 100` | `smoothing_min_cutoff * 1.3` |
| `AirCanvas` pen | two filters, x and y | `3.2`, `beta=0.9` |

Hands get a 30 % higher cutoff because they move faster than heads. The handedness offset
exists so that when MediaPipe swaps detection order between frames, the left hand does not
inherit the right hand's filter state. The air-draw pen runs at `3.2` because a drawing
cursor that lags feels broken, while a *slightly* shaky line feels hand-drawn.

### 7.2 EMA for scalar scores

`EmaFilter(alpha)` is `value = alpha·new + (1 − alpha)·old`, seeded with the first sample.
`ExpressionClassifier` holds one EMA per expression name, with
`alpha = config.expression_smoothing` (default `0.35`). Setting it to `0` disables
smoothing entirely — which is what `smooth_landmarks = False` does, so the "raw" mode is a
single switch rather than a special case.

EMA on *scores* rather than on the *winner* is deliberate: smoothing a label would need a
history of labels and would add a frame of latency to every change. Smoothing the scores
keeps the decision instant while killing single-frame spikes.

### 7.3 Majority vote for the final label

Smoothing scores is not enough — two expressions can hover near each other and alternate.
`PerceptionEngine` keeps a `SlidingWindow(maxlen=7)` of recent labels and overrides the
per-frame winner only when a different label appears **at least 4 times** in the window:

```python
self._expression_votes.push(result.name)
stable = self._expression_votes.majority(result.name)
if stable and stable != result.name and self._expression_votes.items.count(stable) >= 4:
    result.name = str(stable)
    result.score = float(result.scores.get(result.name, result.score))
```

Seven frames at 30 fps is 233 ms of context — long enough to outvote a blink, short enough
that a deliberate expression still reads as immediate. `SlidingWindow.majority()` breaks
ties by the most recent occurrence, so the newest evidence wins.

### 7.4 Not smoothed: gestures

Gesture scores are **not** temporally smoothed, and that is intentional. Gesture state is
already binary and normalised by `hand_scale`, so it is far less noisy than landmark
positions. Filtering it would only add latency to filter switching. The anti-twitch
mechanism lives one level up, in the application layer: a gesture that fires an action
must be held for roughly 0.6 s, shown by an on-screen ring.

---

## 8. The gesture classifier

### 8.1 Three stages

```
21 landmarks
   │  analyze_hand()          geometry, all normalised by hand_scale()
   ▼
HandPose                    5× FingerState + pinch/spread/rotation/palm facing
   │  matcher(pose) -> float in [0, 1]      declarative rules in GESTURES
   ▼
score table                 {"peace": 0.9, "three": 0.75, "pointing": 0.5, …}
   │  threshold + argmax + tie-break
   ▼
GestureMatch                name, score, definition, full sorted score table, pose
```

`analyze_hand` computes, once per hand per frame:

| Quantity | Definition |
| --- | --- |
| `scale` | `hand_scale()`: mean wrist→MCP distance of the four long fingers, rotation-invariant |
| per-finger `curl` | `finger_curl()`: `0.65·angle_score + 0.35·reach_score` |
| per-finger `extended` | `curl < 0.45 and reach_ratio > 1.02` |
| per-finger `pip_angle` | interior angle at the PIP joint, degrees |
| per-finger `reach_ratio` | wrist→tip distance ÷ wrist→PIP distance |
| `pinch_ratio` | thumb-tip→index-tip distance ÷ scale |
| `thumb_index_gap` | alias of `pinch_ratio` |
| `spread` | mean pairwise fingertip distance ÷ scale |
| `fingers_together` | mean adjacent fingertip gap ÷ scale |
| `palm_facing_camera` | sign of the 2-D cross product of `index_mcp − wrist` and `pinky_mcp − wrist`, flipped by handedness |
| `rotation_deg` | `atan2` of the index-MCP→pinky-MCP line |
| `ok_ring_ratio` | thumb-tip→middle-tip distance ÷ scale |

### 8.2 Why `hand_scale` matters

Every threshold in `GESTURES` is expressed in *hand units*, never in pixels or normalised
image units. A pose that scores 0.9 at 40 cm from the lens scores 0.9 at 1.5 m, because
`hand_scale()` divides out the apparent size. Without it you would need one threshold set
per distance, and gesture control would only work if you sat still.

`hand_scale` is defined as the mean distance from the wrist (landmark 0) to the four MCP
joints (5, 9, 13, 17). That choice is rotation-invariant — unlike, say, palm width, which
collapses when the hand turns edge-on — and it is stable even when fingers are folded.

### 8.3 The matcher library

Two families:

* **`_pattern(extended, folded)`** returns `hits / total` over the named fingers. Cheap,
  readable, and the right tool for counting gestures (`peace`, `three`, `four`, `rock`,
  `call_me`, `ily`, `one`, `six`, `seven`, `eight`, `pointing`).
* **Hand-written matchers** for poses where finger state alone is not enough. `_match_ok`
  blends pinch proximity with the number of other extended fingers; `_match_thumbs_up`
  requires the thumb tip to sit clearly *above* the other fingertips and blends that lift
  with folded-finger confidence; `_match_spock` compares the middle/ring gap against the
  outer gaps; `_match_claw` looks for partial curl in `(0.405, 0.95)` on at least three
  fingers.

`_confidence(pose, names, wanted)` is the shared sharpener: it converts a binary
`extended`/`folded` flag into a graded confidence from the underlying curl value, so a
barely-folded finger contributes less than a fully-folded one.

Every matcher is wrapped by `GestureDefinition.match()`, which clamps the result to
`[0, 1]` and **swallows exceptions**, returning `0.0`. A broken custom rule must not take
down the render loop. `classify_gesture` skips any definition scoring `<= 0.0`, so the
score table stays meaningful.

### 8.4 Tie-breaking

`classify_gesture` takes the highest score that clears its own threshold, then applies one
explicit correction:

```python
# Generic pinch must not shadow OK: OK requires the other fingers up.
if best_name == "pinch" and scores.get("ok", 0.0) >= GESTURES["ok"].threshold:
    best_name, best_score = "ok", scores["ok"]
```

Without it, `pinch` (a strict subset of the OK pose) wins every OK and the OK gesture is
unreachable. This is the kind of rule you only discover by watching your own classifier
fail, and it is worth keeping visible rather than hiding inside matcher weights.

When nothing clears the bar the result is `GestureMatch(name="none", score=0.0,
definition=None)` — an explicit sentinel, so callers can distinguish "no hand" from
"hand doing something unrecognised".

### 8.5 Adding a gesture

Add an entry to `GESTURES` with a matcher and a threshold. That is the whole API — the
catalog, the CLI listing, the aliases and the HUD pick it up automatically.

```python
# src/mirrorlab/gestures.py
def _match_gun(pose: HandPose) -> float:  # already exists — shown for shape
    good = pose.is_extended("thumb") and pose.is_extended("index")
    folded = all(pose.is_folded(n) for n in ("middle", "ring", "pinky"))
    if not (good and folded):
        return 0.0
    return 0.6 + 0.4 * _confidence(pose, ["middle", "ring", "pinky"], False)
```

A new one, defined entirely from `HandPose` queries:

```python
from mirrorlab.gestures import GESTURES, GestureDefinition, _pattern

GESTURES["shaka_sign"] = GestureDefinition(
    name="shaka_sign",
    label="Shaka",
    label_es="Shaka",
    emoji="🤙",
    matcher=_pattern(["thumb", "pinky"], ["index", "middle", "ring"]),
    threshold=0.7,
    category="symbol",
    description="Thumb and pinky out, three middle fingers folded.",
    action="snapshot",
)
```

Guidance that saves time:

* Match `HandPose` accessors only (`is_extended`, `is_folded`, `pinch`, `spread`,
  `rotation_deg`, `palm_facing_camera`). Never index `pose.landmarks` in a matcher — you
  would be re-deriving something the pose already normalised.
* Prefer a `_pattern()` rule unless it genuinely fails. Hand-written matchers are harder
  to reason about and easier to overfit to your own hand.
* Set the threshold from the **score table**, not by feel: log `match.scores` while
  performing the pose and pick a value above the noise floor of the confusable gestures.
* If a new gesture shadows an existing one, add an explicit tie-break in
  `classify_gesture` the way `pinch`/`ok` does, and leave a comment explaining why.
* Add an alias to `GESTURE_ALIASES` for every name a user might reasonably type, and a
  Spanish label (`label_es`) — the HUD and the CLI are bilingual.

---

## 9. Adding a filter

A filter is a `Filter` subclass with metadata and an `apply(frame, ctx) -> frame` method.
It must not mutate the input. Registering an *instance* is what makes it visible to
`mirrorlab filters`, `--filter name`, the HUD and the preset table.

`filters/base.py` provides `FilterContext` (frame index, time, delta, width, height and a
`state` dict for per-instance scratch space) and the shared helpers `to_gray_bgr`,
`sobel_magnitude`, `tint`, `apply_mask_blur`.

A complete, working filter — a real one would live in `filters/stylize.py`:

```python
# src/mirrorlab/filters/stylize.py
from __future__ import annotations

import cv2
import numpy as np

from .base import Filter, FilterContext, register_filter, to_gray_bgr


class DuotoneInkFilter(Filter):
    """Two-colour ink wash with a paper lift.

    The technique: flatten luminance into a soft ramp, then map it onto a
    shadow→highlight colour line instead of the greyscale axis. Multiplying the
    ramp back over the paper tone keeps highlights from blowing out.
    """

    name = "duotone_ink"
    label = "Duotone ink"
    label_es = "Tinta a dos tonos"
    emoji = "🖋️"
    category = "stylize"
    description = "Ink wash between two colours with a lifted paper tone."
    description_es = "Aguada de tinta entre dos colores sobre papel claro."
    cost = "cheap"
    needs_mask = False

    SHADOW = np.array([70, 40, 30], dtype=np.float32)     # BGR
    HIGHLIGHT = np.array([215, 235, 245], dtype=np.float32)
    PAPER = 0.92

    def apply(self, frame: np.ndarray, ctx: FilterContext) -> np.ndarray:
        gray, _ = to_gray_bgr(frame)
        # Soft ramp: keeps mid-tones instead of hard-thresholding them.
        ramp = cv2.GaussianBlur(gray, (0, 0), 3.0).astype(np.float32) / 255.0
        ramp = cv2.pow(ramp, 0.85)[..., None]
        mapped = self.SHADOW + (self.HIGHLIGHT - self.SHADOW) * ramp
        out = mapped * self.PAPER
        return np.clip(out, 0, 255).astype(np.uint8)


register_filter(DuotoneInkFilter())
```

Then add `register_filter(...)` — or, for a whole new module, import it from
`filters/__init__.py` alongside `artistic, classic, glitch, stylize, utility`.

Rules that keep the catalogue honest:

* **Metadata is the interface.** `name` is the CLI token (`snake_case`; `get_filter`
  normalises dashes and spaces, so `--filter duotone-ink` also works). `label` and
  `label_es` are what the HUD shows. `cost` (`cheap` / `medium` / `heavy`) is what users
  read before chaining three of them. `needs_mask` tells the app to run segmentation.
* **Set `needs_mask = True`** if you consume the person mask, and accept a `None` mask by
  degrading gracefully — see `apply_mask_blur`, which falls back to a whole-frame blur.
* **Never mutate `frame`.** Return a new array. `FilterChain` feeds your output into the
  next stage, and in-place edits corrupt the caller's frame.
* **State goes in `self.state`** (or an instance attribute set in `__init__`) and must be
  resettable via `reset()`. `build_filter` instantiates a fresh object per chain, so two
  chains never share particle positions — but the *same* filter object is reused across
  frames, which is exactly what temporal effects like `trails` and `datamosh` need.
* **Contribute to `PRESETS`** if your filter pairs well with others; the preset table in
  `filters/__init__.py` is a one-line change.

---

## 10. Adding an effect

Effects differ from filters in one way: they need landmarks. `FaceEffect.apply(frame,
face, ctx)` receives a `FaceObservation`, `HandEffect.apply(frame, hand, ctx)` receives a
`HandObservation`. Both return the frame. `EffectContext` carries `frame_index`, `time`,
`delta`, `width`, `height` and a shared `state` dict.

Effects are drawn **procedurally** with OpenCV primitives, not composited from PNG assets.
That keeps the repository free of binary artwork, makes every overlay
resolution-independent, and lets each one be parameterised (size, colour, tilt).

Two helpers in `effects/face.py` do the heavy lifting for face anchors:

* `_face_frame(face, width, height)` → `(centre, interocular_px, roll_degrees)`. Anchoring
  to the eye line is what makes overlays stick through head tilts: the inter-ocular
  distance sets scale, the eye-line angle sets rotation.
* `_rotate(points, origin, angle_deg)` → integer points rotated about the face centre, and
  `_blend_poly(frame, polygon, colour, alpha)` → alpha-filled polygon that does not mutate
  the source.

A complete face effect:

```python
# src/mirrorlab/effects/face.py
class MonocleEffect(FaceEffect):
    """A brass monocle over the right eye, with a chain that swings on movement."""

    name = "monocle"
    label = "Monocle"
    label_es = "Monóculo"
    emoji = "🧐"
    description = "A brass rim over one eye with a dangling chain."
    description_es = "Un aro de latón sobre un ojo con cadena colgante."

    RIM = (60, 170, 220)  # BGR

    def apply(self, frame: np.ndarray, face: FaceObservation, ctx: EffectContext) -> np.ndarray:
        # Guard first: Haar gives 0 landmarks, YuNet gives sparse ones.
        if face.count < 400:
            return frame

        centre, interocular, roll = _face_frame(face, ctx.width, ctx.height)
        eye = _px(face.point(RIGHT_EYE_OUTER), ctx.width, ctx.height)
        radius = max(6, int(interocular * 0.46))

        rim = _rotate(_ellipse_pts(eye, (radius, radius), 36), centre, roll)
        cv2.polylines(frame, [rim], True, self.RIM, max(2, int(interocular * 0.07)), cv2.LINE_AA)

        # Chain: a short catenary swinging with the frame clock.
        swing = math.sin(ctx.time * 2.1) * interocular * 0.12
        start = (eye[0] + int(radius * 0.9), eye[1] + int(radius * 0.5))
        end = (int(start[0] + interocular * 0.35 + swing), int(start[1] + interocular * 0.85))
        cv2.line(frame, start, end, self.RIM, max(1, int(interocular * 0.035)), cv2.LINE_AA)
        cv2.circle(frame, end, max(2, int(interocular * 0.06)), self.RIM, -1, cv2.LINE_AA)
        return frame


register_face_effect(MonocleEffect())
```

And a hand effect:

```python
class PulseEffect(HandEffect):
    name = "pulse"
    label = "Energy pulse"
    label_es = "Pulso de energía"
    emoji = "💫"
    description = "Concentric rings expanding from the palm centre."

    def apply(self, frame: np.ndarray, hand: HandObservation, ctx: EffectContext) -> np.ndarray:
        points = hand.landmarks
        if points is None or points.shape[0] < 21:
            return frame
        centre = (int(points[:, 0].mean() * ctx.width), int(points[:, 1].mean() * ctx.height))
        scale = hand_scale(points) * ctx.height
        for ring in range(3):
            phase = (ctx.time * 1.6 + ring / 3.0) % 1.0
            radius = int(scale * (0.3 + phase * 1.6))
            alpha = 1.0 - phase
            layer = frame.copy()
            cv2.circle(layer, centre, max(2, radius), (250, 200, 90), 2, cv2.LINE_AA)
            cv2.addWeighted(layer, alpha, frame, 1.0 - alpha, 0, dst=frame)
        return frame


register_hand_effect(PulseEffect())
```

The same discipline as filters applies — guard on landmark count, return a fresh array,
keep animation state in `ctx.state` when the app shares one context across effects, and
keep the drawing scaled from `interocular` or `hand_scale` so it survives a resolution
change.

Two things worth stealing from the shipped effects: `DogEffect` reads
`face.blend("jawOpen")` to drive tongue length, and `BlushEffect` reads
`face.pair("mouthSmileLeft", "mouthSmileRight")` to drive intensity. **Effects that react
to expressions feel alive; static stickers do not.**

---

## 11. Extension points

| You want to… | Touch this | Cost |
| --- | --- | --- |
| Add a filter | subclass `Filter`, `register_filter(instance)` | ~30 lines |
| Add an AR effect | subclass `FaceEffect` / `HandEffect`, register | ~40 lines |
| Add a gesture | append a `GestureDefinition` to `GESTURES` | ~10 lines |
| Add a dynamic gesture | add to `GestureTracker.SWIPES` and fire it from `update()` | ~15 lines |
| Add an expression | add an `ExpressionDefinition`, a scorer in `_BlendshapeScorers.ALL`, and a `_PRIORITY` slot | ~15 lines |
| Add a filter preset | append to `PRESETS` | 5 lines |
| Add a HUD theme | append a `Palette` to `utils/colors.py` | ~10 lines |
| Add a config key | add to `DEFAULTS`, add the field to `Config`, add validation if needed | 3 lines |
| Add a detector backend | subclass `FaceBackend` / `HandBackend`, add to the `builders` dict | ~60 lines |
| Add a model | append a `ModelSpec` to `MODELS` | 8 lines |

Adding a config key automatically extends the layered resolution: `MIRRORLAB_<KEY>` env
override, config-file support, `mirrorlab config --list`, and the CLI's flag plumbing.
`Config.from_mapping` rejects unknown keys with a hint pointing at `mirrorlab config
--list`, so a typo in a config file is an error rather than a silent no-op.

---

## 12. Testing strategy

The test suite has no camera, no network and no MediaPipe in CI. That is possible because
of the layering: everything that decides *what a frame means* is pure.

**Test the pure logic directly.**

* Geometry and smoothing — feed known inputs, assert known outputs. `OneEuroFilter` with
  a constant input must converge to that constant; `hand_scale` must be invariant under
  translation and uniform scaling.
* Filter maths — run every registered filter over a synthetic frame and assert dtype,
  shape and range, plus a per-filter assertion on a known pixel. This is the cheapest
  possible smoke test for 54 filters, and it catches the classic "returns float64" bug.
* Gesture matchers — synthesise landmark arrays for each pose from the index constants in
  `gestures.py`, then assert `classify_gesture()` returns the expected name. Include the
  negative case: a relaxed hand must classify as `none`, not as the nearest gesture.
* Expression scorers — call the entry in `_BlendshapeScorers.ALL` for a name with a
  hand-built blendshape dict. Each scorer is a pure function of a dict, so this needs no
  model.
* Config — `Config.from_mapping` rejects unknown keys, `__post_init__` rejects
  out-of-range values, `MIRRORLAB_FILTER` env overrides work, `with_overrides` returns a
  new object.

**Use the synthetic source instead of a camera.** `SyntheticSource.render(index)` is a
*pure function of the frame index* — a gradient background, scrolling colour bars, a
bouncing ball, a frame counter and a focus cross. Snapshot tests over `render(0)`,
`render(1)`, `render(2)` cover the whole render path with no hardware. `frame_limit` makes
it terminate, which is what `mirrorlab demo` and the headless smoke test use.

**Use the offline image fixtures.** `tests/assets/portrait.jpg` and
`tests/assets/woman_hands.jpg` are committed so detection tests can run against real
pixels without a camera. When MediaPipe is unavailable, those tests should skip rather
than fail — the ladder means "no MediaPipe" is a supported configuration, not an error.

**Mark hardware and network tests.** `pyproject.toml` declares the markers:

```toml
markers = [
    "slow: marks tests as slow",
    "gpu: marks tests that need a GPU",
    "camera: marks tests that need a physical camera",
]
```

Run `pytest -q` for the default suite, `pytest -m camera` when you actually have a webcam
attached, and `pytest -m "not slow"` while iterating.

**Rules for new tests.** No `time.sleep` to "wait for" anything — inject timestamps.
No test may download a model (pass `auto_download=False`). No test may open a window
unless it is marked `camera`. A test that passes only on the machine of the person who
wrote it is worse than no test.

---

## 13. Further reading

* [README](../README.md) — install, usage, configuration and troubleshooting
* [FILTERS.md](FILTERS.md) — every filter, its category, cost and algorithm
* [GESTURES.md](GESTURES.md) — every gesture and its exact geometric rule
* [EXPRESSIONS.md](EXPRESSIONS.md) — the 52 blendshape channels and every scorer formula
* [CROSS_PLATFORM.md](CROSS_PLATFORM.md) — capture backends, permissions, Docker and WSL2
* [FAQ.md](FAQ.md) — the questions that come up most
