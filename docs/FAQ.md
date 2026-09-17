# MirrorLab FAQ

> [English](FAQ.md) · [README](../README.md) · [Español](../README.es.md) · [Architecture](ARCHITECTURE.md) · [Filters](FILTERS.md) · [Gestures](GESTURES.md) · [Expressions](EXPRESSIONS.md) · [Cross-platform](CROSS_PLATFORM.md)

Twenty-two questions that come up often, answered with what the code actually does.

---

## Privacy and network

### Does it upload my video?

**No.** Frames never leave the machine. There is no server, no account, no telemetry and no
analytics. Every pixel is processed in-process by OpenCV and MediaPipe, on the CPU.

The only outbound request MirrorLab can make is a one-time HTTPS GET for a model file,
from `storage.googleapis.com`, and only when the model is not already cached. You can
prove it to yourself: `--no-download` disables the download entirely (`ensure_model` returns
`None` and the detector ladder falls through to whatever works offline), and the app runs
fine with no network if the models are cached. See [SECURITY.md](../SECURITY.md) for the
full model.

### Where exactly do the models go?

Into a per-user cache, never into the repository and never into a wheel:

| OS | Path |
| --- | --- |
| macOS | `~/Library/Caches/mirrorlab/models` |
| Linux | `~/.cache/mirrorlab/models` (or `$XDG_CACHE_HOME`) |
| Windows | `%LOCALAPPDATA%\mirrorlab\models` |

Set `MIRRORLAB_MODELS=/some/path` to override the location — that is the standard way to
run air-gapped. `mirrorlab models --status` prints the resolved directory and what is
already there.

### Why is there a 230 KB ONNX file next to the MediaPipe models?

That is `face_detection_yunet_2023mar.onnx`, OpenCV's YuNet face detector. It is the
fallback rung of the [backend ladder](ARCHITECTURE.md#4-the-backend-fallback-ladder): when
MediaPipe is missing or unusable, YuNet still finds faces and five landmarks, so expressions
degrade to the geometric estimator instead of disappearing.

---

## Installation and dependencies

### Why is MediaPipe pinned below 0.11?

Because of two independent facts, both verified:

1. **MediaPipe 1.0 removed `mp.solutions`.** The namespace every pre-2025 tutorial uses no
   longer exists. MirrorLab's primary backend is the Tasks API
   (`mediapipe.tasks.python.vision`), which 1.x ships — but the legacy Solutions backend is
   still probed as a fallback rung, and it only exists below 1.0.
2. **MediaPipe 1.0.1 hard-crashes on some macOS builds** inside Apple's Metal helper:
   `DrishtiMetalHelper ... Check failed: service_ Service is unavailable`. That is a native
   abort, not a Python exception — you cannot catch it, and it takes the process down.

The tested combination:

```bash
pip install "mediapipe>=0.10.9,<0.11" "numpy<2" "opencv-python<5"
```

`numpy<2` matters because MediaPipe 0.10.x was built against NumPy 1.x's C ABI
(`_ARRAY_API not found` under NumPy 2). `opencv-python<5` keeps the 4.x APIs the filters use.
`mirrorlab doctor` prints the tested one-liner whenever no face engine can start.

### Do I need a GPU?

No, and there is no GPU path. MirrorLab is CPU-only by design: MediaPipe's Tasks graphs run
on XNNPACK, the filters are OpenCV CPU kernels, and the effects are OpenCV primitives. A
modern laptop runs 720p at 30 fps with detection on. On a very slow machine, see
[How do I get more FPS?](#how-do-i-get-more-fps)

### Does it work on Python 3.13?

Not yet. `requires-python = ">=3.9"` and the classifiers list 3.9 through 3.12. The
constraint is MediaPipe 0.10.x, which publishes no 3.13 wheels — and 1.x is exactly what the
pin avoids. Use 3.11 or 3.12.

### Can I install it with pip from PyPI?

Not yet — the PyPI release is on the [roadmap](../ROADMAP.md). Install from source:

```bash
git clone https://github.com/TrinaxCode/mirrorlab.git
cd mirrorlab
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

---

## Cameras and permissions

### The camera will not open. What do I check?

Run `mirrorlab doctor` first, then `mirrorlab cameras`. The likely causes, in order of
frequency:

* **macOS permission.** System Settings → Privacy & Security → Camera → enable the *host
  application* (Terminal, iTerm2, VS Code). Keep in mind the permission is per host app,
  not per Python.
* **Another app holds the camera.** Zoom, Teams, OBS, Photo Booth. Quit them.
* **Wrong index.** A phone on Continuity Camera or a virtual device can occupy index 0; try
  `--camera 1`.
* **Wrong backend on Windows.** Try `--backend msmf`, then `--backend dshow`.
* **Linux group membership.** `sudo usermod -aG video "$USER"`, then start a new session —
  group changes are read at login.
* **The device is not there.** `ls -l /dev/video*` on Linux.

`open_camera` raises `CameraError` with the platform's own checklist appended, so the error
message in your terminal already contains these steps.

### Does it work with an external or USB camera?

Yes — it is just another index. Probe for it:

```bash
mirrorlab cameras --max-index 5
mirrorlab run --camera 1
```

### Can I use my phone as a webcam?

Yes, in two ways:

* **macOS:** Continuity Camera exposes the iPhone as a regular capture device, usually at
  index 1 (`mirrorlab run --camera 1`).
* **Any OS:** most phone-as-webcam apps (Camo, Iriun, DroidCam, EpocCam) install a virtual
  camera driver, which MirrorLab sees as another index. Verify with `mirrorlab cameras`.

A phone camera is often higher quality than a laptop's, and the extra distance is
genuinely useful for hand gestures — you need your hand fully in frame.

### Can I point it at a video file instead of a camera?

Yes. `--input clip.mp4` opens the file through the same `CameraStream` interface, paced to
the file's fps and looped:

```bash
mirrorlab run --input clip.mp4 --filter cartoon
```

That is the sane way to compare filters: same input every time.

---

## Detection quality

### Hands are not detected at all.

Hand tracking **requires MediaPipe**. There is no OpenCV hand-landmark model, so when
MediaPipe is missing the hand backend is `none` and gestures are disabled — by design, and
the app keeps running. Check with:

```bash
mirrorlab doctor          # "hand backend" must not be "none"
```

If the backend is fine but your hand is still invisible:

* **Get the whole hand in frame,** wrist to fingertips. MediaPipe needs the palm base.
* **Light your hand from the front.** Backlighting turns a hand into a silhouette.
* **Do not move fast.** Motion blur destroys landmark quality.
* **Mind the background.** A hand against a similarly coloured wall is harder than against
  contrast.
* **Use `--camera 1`** if a virtual camera is feeding a low-resolution stream; some drivers
  cap at 320×240, which is below what the palm detector wants.

### Why is the detection jittery?

Raw MediaPipe landmarks move by a pixel or two every frame, and drawing them directly gives
the classic shaky-AR look. MirrorLab already applies a One-Euro filter per landmark per
coordinate. If it is still too jittery:

* **Lower `smoothing_min_cutoff`** (default `1.7`). Lower = smoother, slightly laggier at
  rest; fast motion is unaffected because the filter adapts to speed.
* **Lower `smoothing_beta`** (default `0.35`) to trade responsiveness for stability.
* **Raise `expression_smoothing`** (default `0.35`) if the *expression label* is what
  flickers rather than the mesh.
* **Check the light.** Jitter is mostly sensor noise, and sensor noise is mostly gain. A
  brighter room lets the camera drop its gain and the landmarks settle.

Both knobs are config keys, so you can set them without touching code:

```bash
MIRRORLAB_SMOOTHING_MIN_CUTOFF=1.0 mirrorlab run
```

### The expression label flickers between two expressions.

The pipeline already smooths scores with an EMA and then applies a 7-frame majority vote
requiring 4 agreeing frames. If it still flickers, the two expressions genuinely score close
together — usually `happy` versus `neutral` on a resting face. Options:

* Raise `expression_smoothing` toward `0.6`.
* Raise `min_score` above its `0.28` default, so only confident expressions are reported at
  all.
* Reorder `_PRIORITY` per instance to make the expression you care about stickier. See
  [EXPRESSIONS.md](EXPRESSIONS.md#how-a-winner-is-picked).

### Which expressions are unavailable without MediaPipe Tasks?

With the geometric fallback (Solutions or YuNet) only `happy`, `laugh`, `sad`, `surprised`,
`angry`, `brow_raise`, `kiss`, `yawn`, `blink` and `neutral` are computed. `wink`, `fear`,
`disgust`, `contempt`, `thinking`, `squint` and `puff` stay at zero, because there is no
landmark ratio that reads a one-sided smirk or a nose sneer reliably. `ExpressionResult.method`
tells you which path is active.

### A gesture fires when I do not want it to.

Three fixes, easiest first:

* **Hold it longer.** Actions require a 0.6 s dwell and the on-screen ring shows the
  progress, so nothing fires by accident if you move through a pose.
* **Turn off the ones you do not use.** Gesture control is a mapping table
  (`actions.DEFAULT_BINDINGS`), and `--no-gesture-control` disables all bindings while still
  detecting and displaying gestures.
* **Raise the threshold** of the offending gesture in `gestures.py`, using the score table
  (`GestureMatch.scores`) to see how much headroom you have. See
  [GESTURES.md](GESTURES.md#debugging-a-gesture-that-will-not-fire).

---

## Output and integration

### How do I record a video, and how do I make my own GIF?

Press `r` while the app is running. That starts recording; press `r` again to stop. You get
an **MP4 and a GIF** from the same session: `Recorder(gif=True)` buffers every Nth frame
(stride `record_fps / 12`) and writes a looping GIF next to the MP4 on stop.

* Output directory: `--output captures` (or `output_dir` in config).
* Video codec: `--record-codec mp4v` (falls back to `XVID`, then `MJPG`, if the build cannot
  open your choice).
* GIF export needs **Pillow**. Without it, the MP4 still saves and a warning is logged:
  `pip install pillow`.
* GIFs are written at 12 fps and capped at 640 px wide on purpose — that is the sweet spot
  where a webcam clip stays legible and lands under a few megabytes, which is what you want
  for a README or a chat message.

For a GIF of a *specific* filter, the honest workflow is: `--filter <name>`, press `r`, do
the thing, press `r` again, then trim the MP4 with `ffmpeg` if you need it shorter.

### How do I take a snapshot?

Press `s`, or hold a 👍 (thumbs up) for 0.6 s. The snapshot is the **composited** frame —
filters, effects and HUD included, exactly what you saw. Format comes from
`snapshot_format` (`png`, `jpg`, `jpeg`, `webp`) with `jpeg_quality` for the lossy ones.
Wrong shot? 👎 (thumbs down) deletes the most recent capture.

### Can I use this as a virtual camera in Zoom, OBS or Meet?

**Not yet** — it is on the [roadmap](../ROADMAP.md), not in 2.0.0. The reason it is a
roadmap item rather than a feature is licensing: the standard Python answer is
`pyvirtualcam`, which is **GPLv2**. MirrorLab is MIT, and linking a GPL library into the
default install would relicense the whole project. So when it lands it will be an
**optional extra** — `pip install "mirrorlab[virtualcam]"` — that you opt into, keeping the
core MIT and dependency-light.

Until then, the workaround is the usual one: run MirrorLab fullscreen and use OBS's
Window Capture, or share the window directly.

### Can I run it on a server with no camera and no screen?

Yes. Use the synthetic source and headless mode:

```bash
mirrorlab demo --frames 120                          # synthetic, headless, terminates
mirrorlab run --headless --frames 300 --stats-csv stats.csv
mirrorlab run --input clip.mp4 --headless --output captures
```

For a machine with no display libraries at all, install `opencv-python-headless` instead of
`opencv-python` and always pass `--headless`. See
[CROSS_PLATFORM.md](CROSS_PLATFORM.md#headless-and-ci).

### How do I get more FPS?

In order of how much they help:

1. **Downscale detection.** `--camera-width 640 --camera-height 480`. Inference cost scales
   with input area, and detection does not need 720p.
2. **Turn off hands.** `--no-hands`. The hand landmarker is the most expensive model in the
   pipeline; dropping it is the single biggest win if you do not need gestures.
3. **Turn off face.** `--no-face`, if you only want filters.
4. **Pick a cheaper filter.** `mirrorlab benchmark --all` shows ms/frame per filter; the
   slowest (`pointillism`, `watercolor`, `oil`) cost 14–17 ms at 640×480 while
   `grayscale` costs 0.10 ms.
5. **Do not chain three `medium` filters.** Costs add up even though `cost` reports the
   worst stage.
6. **Leave segmentation off.** `--segment` runs an extra model; `bg_blur`, `bg_replace` and
   `privacy` need it, nothing else does.

### Why does the window not close on macOS?

Because Cocoa needs a few event-loop iterations after `destroyAllWindows()` before the
window disappears. Without pumping the loop the window stays painted on screen and the
process *looks* hung even though it has exited. MirrorLab pumps `cv2.waitKey(1)` four times
on exit for exactly this reason. If you see the window linger, you are running something
that calls `destroyAllWindows()` itself before `run()` returns.

---

## Extending it

### Can I train my own gestures?

Not as a trained model, no — and that is a deliberate design choice, not a missing feature.
Gestures are **declarative geometric rules** over a normalised `HandPose`, which is why the
engine needs no extra model download, runs in microseconds, and can be extended in about ten
lines. Adding a gesture means writing a matcher and registering it:

```python
def _match_l_shape(pose: HandPose) -> float:
    if not (pose.is_extended("thumb") and pose.is_extended("index")):
        return 0.0
    if not all(pose.is_folded(n) for n in ("middle", "ring", "pinky")):
        return 0.0
    return 0.6 + 0.4 * _confidence(pose, ["middle", "ring", "pinky"], False)

GESTURES["l_shape"] = GestureDefinition(
    "l_shape", "L shape", "Forma de L", "🫰", _match_l_shape, 0.68, "symbol",
    "Thumb and index at a right angle.", action="snapshot",
)
```

Full walkthrough: [GESTURES.md](GESTURES.md#adding-your-own-gesture). An MLP trainer that
learns thresholds from your own examples is on the roadmap as a separate, optional tool.

### How do I add a filter or an effect?

Both are documented with complete, working examples:

* [FILTERS.md](FILTERS.md#writing-a-new-filter) — subclass `Filter`, implement
  `apply(frame, ctx)`, call `register_filter`.
* [ARCHITECTURE.md](ARCHITECTURE.md#10-adding-an-effect) — subclass `FaceEffect` or
  `HandEffect`, implement `apply(frame, observation, ctx)`, call `register_face_effect` or
  `register_hand_effect`.

A filter is ~30 lines; an effect is ~40. Neither requires touching the CLI: the catalogs,
the HUD and `--filter`/`--effect` all read the registries.

### How do I configure it without editing code?

Four layers, lowest priority first: built-in defaults → a config file → `MIRRORLAB_*`
environment variables → explicit CLI flags.

```bash
mirrorlab config --list                     # every key and its default
mirrorlab config --show                     # the resolved configuration
mirrorlab config --init mirrorlab.json      # write a commented config file

MIRRORLAB_FILTER="cartoon+vignette" mirrorlab run
MIRRORLAB_THEME=magma mirrorlab run
MIRRORLAB_SMOOTHING_MIN_CUTOFF=1.0 mirrorlab run
```

Config files are discovered as `mirrorlab.json`, `mirrorlab.yaml` or `mirrorlab.yml` in the
current directory, then in `~/.config/mirrorlab` (or `%APPDATA%\mirrorlab` on Windows).
Unknown keys are a hard error with a hint, so a typo surfaces instead of silently doing
nothing.

---

## Licensing

### Can I use it commercially?

**Yes.** MirrorLab is MIT licensed — use it at work, ship it inside a product, sell a
service built on it. The only obligations are the usual MIT ones: keep the copyright notice
and the licence text.

Two things to read before you ship, though:

* **The models are not covered by MirrorLab's MIT licence.** The `.task` bundles are
  downloaded at runtime, not redistributed, and each is governed by its own model card.
  MediaPipe's models are generally Apache-2.0, but check the specific card for the model
  you ship. Details in [THIRD_PARTY_LICENSES.md](../THIRD_PARTY_LICENSES.md).
* **Do not market it as a "Snapchat filter" or "Instagram filter".** Those are trademarks.
  "AR-style face filters" is the accurate, safe description.

### What if I want a virtual camera, which is GPL-licensed?

That is precisely why it will only ever be an optional extra. `pyvirtualcam` is GPLv2;
putting it in the default dependency set would relicense MirrorLab. As an opt-in extra
(`pip install "mirrorlab[virtualcam]"`) the core stays MIT and you make the GPL choice
yourself. This is documented in [THIRD_PARTY_LICENSES.md](../THIRD_PARTY_LICENSES.md) so the
decision is explicit rather than accidental.

---

Still stuck? Run `mirrorlab doctor --json` and
`mirrorlab cameras --json`, and open an issue at
<https://github.com/TrinaxCode/mirrorlab/issues> with both attached. The JSON has the OS,
Python, OpenCV, MediaPipe, the capability probes and the model cache state, which is
usually enough to answer without a round trip.
