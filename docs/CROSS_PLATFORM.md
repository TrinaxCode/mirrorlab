# MirrorLab on macOS, Windows and Linux

> [English](CROSS_PLATFORM.md) · [README](../README.md) · [Español](../README.es.md) · [Architecture](ARCHITECTURE.md) · [Filters](FILTERS.md) · [Gestures](GESTURES.md) · [Expressions](EXPRESSIONS.md) · [FAQ](FAQ.md)

Opening a webcam is the single most platform-dependent thing a computer-vision project
does. This document covers what MirrorLab does about it: capture backends, permissions,
window caveats, headless and container runs, and the dependency pins that keep MediaPipe
from aborting on some macOS builds.

---

## Contents

- [Platform matrix](#platform-matrix)
- [Install notes per OS](#install-notes-per-os)
- [Camera permissions](#camera-permissions)
- [Capture backends in detail](#capture-backends-in-detail)
- [Window and GUI caveats](#window-and-gui-caveats)
- [Headless and CI](#headless-and-ci)
- [Docker](#docker)
- [WSL2](#wsl2)
- [The dependency pins](#the-dependency-pins)
- [Diagnosing a machine](#diagnosing-a-machine)

---

## Platform matrix

| | macOS | Windows | Linux |
| --- | --- | --- | --- |
| Backends tried, in order | `avfoundation` → `any` | `dshow` → `msmf` → `any` | `v4l2` → `gstreamer` → `any` |
| Fallback if the first fails | automatic, verified by a test read | automatic, verified by a test read | automatic, verified by a test read |
| Force one backend | `--backend avfoundation` | `--backend dshow` / `--backend msmf` | `--backend v4l2` |
| Camera permission | System Settings → Privacy & Security → Camera | Settings → Privacy → Camera | `video` group membership |
| Model cache | `~/Library/Caches/mirrorlab/models` | `%LOCALAPPDATA%\mirrorlab\models` | `~/.cache/mirrorlab/models` |
| Config file | `~/.config/mirrorlab/mirrorlab.json` | `%APPDATA%\mirrorlab\mirrorlab.json` | `~/.config/mirrorlab/mirrorlab.json` (or `$XDG_CONFIG_HOME`) |
| Video writer | `mp4v` (OpenCV's own muxer) | `mp4v`, falls back to `XVID` then `MJPG` | `mp4v` |
| Window backend | Cocoa — **main thread required** | Win32 | GTK/Qt via OpenCV |
| GUI from a container | not applicable | not applicable | needs an X11/Wayland socket |

`gstreamer` only appears on Linux if the OpenCV build was compiled with it;
`opencv-python` wheels are not, so in practice Linux is `v4l2` → `any`.
`available_backends()` reports exactly what your build supports, and `mirrorlab cameras`
prints it.

---

## Install notes per OS

### macOS

```bash
git clone https://github.com/TrinaxCode/mirrorlab.git
cd mirrorlab
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
mirrorlab doctor
mirrorlab run
```

The first `mirrorlab run` triggers the camera permission prompt. Accept it, then run again
— macOS does not grant access mid-process. Apple Silicon and Intel both work; there is no
GPU requirement and no Metal dependency in the supported configuration.

### Windows

```powershell
git clone https://github.com/TrinaxCode/mirrorlab.git
cd mirrorlab
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
mirrorlab doctor
mirrorlab run
```

If the preview is black or the camera never opens, switch backend:

```powershell
mirrorlab run --backend msmf      # if DSHOW misbehaves
mirrorlab run --backend dshow     # if MSMF misbehaves
mirrorlab cameras                 # which indices actually deliver frames?
```

`camera.py` reads exactly one frame at open time as its "is this thing real?" test,
precisely because DSHOW will happily report an open device that never delivers pixels.

### Linux

```bash
sudo usermod -aG video "$USER"     # then log out and back in
ls -l /dev/video*                  # the device node must exist
git clone https://github.com/TrinaxCode/mirrorlab.git
cd mirrorlab
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
mirrorlab doctor
mirrorlab run
```

Group membership is read at login, so `usermod` alone is not enough — you need a new
session. `mirrorlab cameras` will list indices and probe each backend if you are unsure
which node is which.

---

## Camera permissions

### macOS

System Settings → **Privacy & Security → Camera** → enable the app that runs Python
(Terminal, iTerm2, VS Code, PyCharm). Two details that cost people an hour:

* The permission is granted **per host application**, not per Python interpreter. Granting
  it to Terminal does nothing for a script launched from VS Code.
* The prompt appears on the first run only. If it was dismissed, the app never appears in
  the list until you relaunch it from the offending terminal — and if the camera is
  already open in another app (Zoom, Teams, Photo Booth, OBS), the open attempt fails
  silently rather than erroring.

Continuity Camera means an iPhone can occupy index 0. `mirrorlab run --camera 1` is the
usual fix.

### Windows

Settings → **Privacy → Camera** → *Let desktop apps access your camera*. The per-app
toggle below it also applies. On managed machines, group policy can disable camera access
entirely; `mirrorlab doctor` will show `face backend: none` in that case only if
MediaPipe also failed, so check the OS setting first.

### Linux

There is no permission prompt — access is file permissions on `/dev/video*` plus `video`
group membership. In a container you must pass the device through *and* grant the group.
Flatpak and Snap packages of your terminal may not expose the camera at all; run from a
plain shell if in doubt.

---

## Capture backends in detail

`backend_priority(override)` returns the list of names to try:

```python
if system == "Darwin":     order = ["avfoundation", "any"]
elif system == "Windows":  order = ["dshow", "msmf", "any"]
else:                      order = ["v4l2", "gstreamer", "any"]
return [name for name in order if name in BACKENDS]
```

Passing `--backend X` returns exactly `[X]` — no fallback. That is intentional: when you
force a backend you are debugging, and you want the failure, not a silent substitution.
`Config.__post_init__` accepts `auto`, `avfoundation`, `dshow`, `msmf`, `v4l2` and `any`;
anything else is a validation error listing the accepted values.

`open_camera()` tries each name in turn, and a candidate only counts as success after
`cap.read()` returns a frame. On total failure it raises `CameraError` with the platform's
own checklist appended, which is what you see in the terminal:

```console
$ mirrorlab run --camera 3
Camera error
Could not open camera #3 (tried: avfoundation, any).
  • Run `mirrorlab doctor` to list detected devices and backends.
  • Try a different index: `mirrorlab run --camera 1`.
  • Close other apps that may hold the camera (Zoom, Teams, OBS, Photo Booth).
  • macOS: System Settings → Privacy & Security → Camera → enable your terminal.
  • macOS: the first run triggers a permission prompt — accept it and retry.
  • macOS: Continuity Camera / iPhone may occupy index 0; try --camera 1.
```

`mirrorlab cameras --max-index 5` probes indices `0..4` and then reports which backends
deliver a frame on camera #0 — the fastest way to tell "wrong index" apart from "wrong
backend".

**Video files work too.** `--input clip.mp4` opens the file through the same
`CameraStream` interface, paced to the file's own fps, looped, and with mirroring off by
default. That is also how you test filters on a repeatable clip instead of waving at a
webcam.

### Resolution and frame rate

`--camera-width`, `--camera-height` and `--camera-fps` are *requests*, not guarantees. The
device picks the nearest mode it supports, and MirrorLab reports what it actually got:

```
Camera opened: camera #0 via avfoundation @ 1280x720 30fps
```

Detection and filtering then run at the frame size the camera delivered. If you asked for
720p and got 640×480, that is the driver, not MirrorLab.

---

## Window and GUI caveats

**macOS requires `cv2.imshow` and `cv2.waitKey` on the main thread.** Cocoa's UI work must
happen on the main run loop; calling them from a worker thread produces a hang or an
immediate crash. This is why `MirrorLab.run()` keeps the render loop on the caller's
thread and pushes only capture and encoding to background threads. If you embed MirrorLab
in your own application, call `run()` from the main thread — or use `headless=True` with
the `on_frame` callback and render the frames yourself.

**"Why does the window not close on macOS?"** `cv2.destroyAllWindows()` posts a Cocoa
teardown that only completes after a few event-loop iterations. Without pumping the loop,
the window stays painted on screen and the process *looks* hung even though it has already
exited. MirrorLab handles it explicitly:

```python
cv2.destroyAllWindows()
# On macOS the window only disappears after a few event-loop iterations;
# without this the process looks hung on exit.
for _ in range(4):
    cv2.waitKey(1)
```

If you see the window linger anyway, you are running an older build or calling
`destroyAllWindows()` yourself before `run()` returns.

**Fullscreen** is requested with `cv2.setWindowProperty(…, cv2.WND_PROP_FULLSCREEN, …)`
after `namedWindow(…, cv2.WINDOW_NORMAL)`. It is a start-up flag (`--fullscreen`) only —
there is no keyboard toggle for it, and `f` is bound to freeze, not fullscreen. On some
Linux window managers the property is advisory and the WM wins.

**HUD fonts.** OpenCV's Hershey fonts cannot render emoji. The HUD deliberately keeps
labels text-only (`_emoji_safe()` returns `False`), while the CLI and the docs use emoji
freely. A filter's emoji is metadata for listings, not something drawn on the frame.

---

## Headless and CI

Two independent things can be missing in CI: a camera and a display. Both are handled.

**No camera → the synthetic source.** `SyntheticSource` renders a moving test pattern —
vertical gradient, scrolling colour bars, a bouncing ball, a frame counter and a focus
cross — as a **pure function of the frame index**:

```python
frame = SyntheticSource(640, 480, frame_limit=1).render(0)   # deterministic
```

That makes it usable for snapshot tests, and it exercises the full render path: filters,
HUD, effects and overlays all run against it. `mirrorlab demo` is the packaged form:

```bash
mirrorlab demo --frames 120            # headless by default, synthetic source
mirrorlab demo --frames 60 --json      # {"frames": 60, "fps": ...}
mirrorlab demo --filter cartoon+vignette --effect dog
```

`_cmd_demo` forces `headless = True` and defaults to 120 frames, so it terminates on its
own — which is exactly what a smoke test needs:

```yaml
# .github/workflows/ci.yml (excerpt)
- run: pip install -e ".[dev]"
- run: pytest -q
- run: mirrorlab demo --frames 60
```

**No display → `--headless`.** `mirrorlab run --headless` skips `namedWindow`/`imshow`
entirely and still runs detection, filters, effects and recording, printing the session
summary at the end. Combined with `--frames N` and `--stats-csv`, that is a batch
processor:

```bash
mirrorlab run --headless --frames 300 --filter cartoon --stats-csv stats.csv --output captures
```

The stats CSV has one row per frame:
`timestamp, frame, fps, inference_ms, expression, score, gestures, filter`.

On Linux, MirrorLab also auto-detects the absence of a display:

```python
if platform.system() in {"Linux", "FreeBSD"}:
    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        return False
```

So a bare container without `DISPLAY` runs headless without being told. That check does not
apply to macOS or Windows.

**Servers: use `opencv-python-headless`.** The GUI-enabled wheel needs GTK/Qt/X11 libraries
(`libGL.so.1` in particular) and will fail to import on a slim server image. Install the
headless wheel instead and always pass `--headless`:

```bash
pip install "opencv-python-headless<5" "mediapipe>=0.10.9,<0.11" "numpy<2"
pip install -e . --no-deps
mirrorlab run --headless --frames 100
```

Do not install both wheels — `opencv-python` and `opencv-python-headless` overwrite each
other's `cv2` module and produce confusing import errors.

---

## Docker

There is no official image yet (see [ROADMAP.md](../ROADMAP.md)), but the pattern is
short. A CPU-only, camera-passed container:

```dockerfile
FROM python:3.11-slim

# OpenCV's GUI wheel needs these even when we never open a window.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libglib2.0-0 libgl1 libsm6 libxext6 libxrender1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -e ".[dev]" \
    && pip install --no-cache-dir "mediapipe>=0.10.9,<0.11" "numpy<2" "opencv-python<5"

# Models are cached here; mount a volume to keep them across runs.
ENV MIRRORLAB_MODELS=/models
VOLUME ["/models"]

ENTRYPOINT ["mirrorlab"]
CMD ["run", "--headless"]
```

```bash
docker build -t mirrorlab .
docker run --rm -it --device /dev/video0 --group-add video \
           -v "$PWD/captures:/app/captures" -v mirrorlab-models:/models \
           mirrorlab run --no-hud
```

Notes:

* `--device /dev/video0` passes the camera; `--group-add video` grants the group. Missing
  either one produces `Could not open camera #0`.
* To show a window from a container you must forward X11 (`-e DISPLAY=host.docker.internal:0`
  plus mounting the socket on Linux, or an X server on Windows/macOS). It is usually easier
  to run headless in the container and view the output files on the host.
* Mount `MIRRORLAB_MODELS` on a volume. Without it, every container run re-downloads
  ~12 MB of models — and in an air-gapped CI it fails outright.
* For a camera-free smoke test, skip the device flags entirely: `docker run --rm mirrorlab demo --frames 60`.

---

## WSL2

WSL2 has no direct camera access; you must attach the USB device to the WSL VM:

```powershell
# Windows, as Administrator, once
winget install usbipd
usbipd list
usbipd bind --busid 4-4          # the webcam's bus id
usbipd attach --wsl --busid 4-4
```

```bash
# inside WSL
ls -l /dev/video*                # should now exist
sudo usermod -aG video "$USER"   # then restart the WSL session
pip install -e ".[dev]"
mirrorlab doctor
mirrorlab run --backend v4l2
```

Key points:

* Prefer **WSL2 with WSLg** (Windows 11) so `cv2.imshow` has a display. On Windows 10 you
  need a third-party X server and `export DISPLAY=:0`.
* The attach does not survive a reboot or a USB re-plug; re-run `usbipd attach`.
* Integrated laptop cameras cannot be attached with `usbipd` on most machines — use a USB
  webcam, or a phone as a webcam.
* Filesystem I/O across `/mnt/c` is slow. Keep the repo in the Linux filesystem
  (`~/mirrorlab`) so `pip install -e .` and the model cache are not paying the 9p tax.
* If detection is inexplicably slow, check `mirrorlab doctor` for the detected backend and
  prefer `--camera-width 640 --camera-height 480`. WSL2's USB passthrough has more
  per-frame overhead than a native Linux install.

---

## The dependency pins

`pyproject.toml` declares deliberately loose ranges, and the *tested* combination is
tighter. Both matter.

```toml
dependencies = [
    "numpy>=1.24",
    "opencv-python>=4.8",
    "mediapipe>=0.10.9",
]
```

### Why MediaPipe is pinned below 0.11 in practice

Two independent facts:

1. **MediaPipe 1.0 removed `mp.solutions`.** The `face_mesh`, `hands` and `drawing_utils`
   namespaces that every pre-2025 tutorial uses no longer exist. Code written against them
   raises `AttributeError: module 'mediapipe' has no attribute 'solutions'`.
   MirrorLab's primary backend is the **Tasks API** (`mediapipe.tasks.python.vision`), which
   is what 1.x ships — but the legacy Solutions backend is still probed as a fallback rung,
   and it only exists below 1.0.
2. **MediaPipe 1.0.1 hard-crashes on some macOS builds**, inside Apple's Metal helper:

   ```
   DrishtiMetalHelper ... Check failed: service_ Service is unavailable
   ```

   This is an abort, not a Python exception — you cannot catch it, and it takes the process
   with it. There is no application-level workaround.

The combination that is tested and known-good:

```bash
pip install "mediapipe>=0.10.9,<0.11" "numpy<2" "opencv-python<5"
```

Why the other two pins:

* **`numpy<2`.** MediaPipe 0.10.x was built against NumPy 1.x's C ABI. Under NumPy 2 the
  import fails with `_ARRAY_API not found` / `A module that was compiled using NumPy 1.x
  cannot be run in NumPy 2.x`. Downgrading NumPy is the fix; upgrading MediaPipe is not an
  option because of the two facts above.
* **`opencv-python<5`.** OpenCV 4.x is what MediaPipe 0.10.x is built and tested against,
  and MirrorLab's filters use `cv2.legacy`-free 4.x APIs (`cv2.face.FaceDetectorYN`,
  `edgePreservingFilter`, `applyColorMap`). If OpenCV 5 changes any of those signatures the
  pin is what keeps an unrelated `pip install -U` from breaking your install.

### Tested matrix

| Component | Range in `pyproject.toml` | Known-good pin |
| --- | --- | --- |
| Python | `>=3.9`, classifiers 3.9 – 3.12 | 3.11 |
| MediaPipe | `>=0.10.9` | `>=0.10.9,<0.11` |
| NumPy | `>=1.24` | `<2` |
| OpenCV | `>=4.8` | `<5` |
| PyYAML (optional) | `>=6.0` | needed only for `.yaml` config files |
| rich (optional) | `>=13.0` | CLI extras only; the CLI degrades to plain text |

Features are not gated on these pins — they are gated on **capability probes**. If
MediaPipe is missing entirely, the face ladder drops to YuNet or Haar and hand gestures are
disabled; the app still starts. That is the design, and it is why `mirrorlab doctor` reports
capabilities rather than versions.

A minimal, no-MediaPipe install that still detects faces:

```bash
pip install "opencv-python<5" numpy
pip install -e . --no-deps        # skips the mediapipe requirement
mirrorlab models --download yunet_face
mirrorlab run --no-hands
```

---

## Diagnosing a machine

`mirrorlab doctor` answers "what can this machine actually do?" in one command:

```console
$ mirrorlab doctor

  Environment
    platform           Darwin
    platform_release   25.6.0
    machine            arm64
    python             3.11.16
    opencv             4.11.0
    backends           any, avfoundation, dshow, ffmpeg, gstreamer, msmf, v4l2
    preferred order    avfoundation → any
    display            available

  Detectors
    mediapipe          0.10.21
    tasks API          ✓
    solutions API      ✓
    opencv YuNet       ✓
    face backend       tasks-face
    hand backend       tasks-hands

  Models
    ✓ face_landmarker.task                         3.7 MB  face_landmarker
    · gesture_recognizer.task                      8.4 MB  gesture_recognizer
    ✓ hand_landmarker.task                         7.8 MB  hand_landmarker
    …

  Capabilities
    filters            54
    face effects       11
    hand effects       4
```

Add `--download` to fetch missing models while you wait, or `--json` for a
machine-readable dump (handy in a bug report). `mirrorlab cameras` covers the camera half:
which indices respond, which backends deliver frames, and the platform troubleshooting
checklist when nothing does.

> **Known gap.** In the current source, `_cmd_doctor` prints the `display` line and the
> `Capabilities` counts by reading keys from `probe_environment()` that it does not
> provide — those fields live on `MirrorLab.capability_report()` instead. Until that is
> wired up, `display` reads `headless (no window)` on every machine and the three
> capability counters read `0`. `mirrorlab doctor --json` has the same gap; the detector
> and model sections are accurate.

Reproduce the platform report on any machine with:

```bash
mirrorlab doctor --json > doctor.json
```

Attach that file to a bug report instead of prose — it has the OS, Python, OpenCV,
MediaPipe, the capability probes and the model cache state in one object.

See [FAQ.md](FAQ.md) for the questions that are not platform-specific, and
[ARCHITECTURE.md](ARCHITECTURE.md#4-the-backend-fallback-ladder) for how the detector
ladder is implemented.
