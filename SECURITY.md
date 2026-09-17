# Security policy

> [English](SECURITY.md) · [README](README.md) · [Español](README.es.md) · [Contributing](CONTRIBUTING.md) · [Code of Conduct](CODE_OF_CONDUCT.md) · [Third-party licences](THIRD_PARTY_LICENSES.md)

## Supported versions

| Version | Supported | Notes |
| --- | --- | --- |
| `2.0.x` | ✅ | Current release. Security fixes land here first. |
| `2.x` (pre-release) | ⚠️ | Fixes are backported only when the change is trivial. |
| `1.x` / `legacy/` | ❌ | The original single-file prototype, kept for reference. Unsupported and not installed by the package. |
| `web/` demo | ✅ | Static browser build; report issues here and they are treated as `2.0.x`. |

MirrorLab 2.x tracks Python 3.9–3.12. A vulnerability that only reproduces on an
end-of-life Python or on a version outside the tested dependency matrix (see
[CROSS_PLATFORM.md](docs/CROSS_PLATFORM.md#tested-matrix)) will be triaged, but may be
closed as "upgrade required".

---

## Reporting a vulnerability

**Please do not open a public issue for a security problem.**

Report privately through GitHub Security Advisories:

**<https://github.com/TrinaxCode/mirrorlab/security/advisories/new>**

That channel is private between you and the maintainers until an advisory is published.

Helpful reports include:

* the version (`mirrorlab --version`) and the output of `mirrorlab doctor --json`
* the OS, Python, OpenCV and MediaPipe versions
* a minimal reproduction — a snippet, a config file, or a command line
* the impact you believe it has, and whether you consider it exploitable by a remote party
  or only by someone who already runs code on the machine

What to expect:

| Stage | Target |
| --- | --- |
| Acknowledgement | within 3 days |
| Initial assessment (severity, affected versions) | within 7 days |
| Fix or mitigation plan | within 30 days for high severity |
| Public advisory | after a fix ships, coordinated with you |

You will be credited in the advisory unless you ask not to be. Please give us a reasonable
window to ship a fix before publishing.

---

## The privacy model

This is the part of MirrorLab that is most worth stating precisely, because a webcam
project that is vague about it deserves to be distrusted.

**Camera frames are processed entirely in-process and never transmitted.** There is no
upload path in the codebase. Frames are read into a NumPy array by OpenCV, passed through
local MediaPipe and OpenCV calls, drawn on, and shown in a window or dropped. Nothing calls
a network API with pixel data. There is no server component. There is no cloud service.

**The only outbound request the application can make is a model download**, and only when
the model is not already cached:

| Model | Source |
| --- | --- |
| `face_landmarker.task`, `hand_landmarker.task`, `gesture_recognizer.task`, `pose_landmarker_lite.task`, `selfie_segmenter.tflite`, `selfie_multiclass_256x256.tflite` | `https://storage.googleapis.com/mediapipe-models/…` |
| `face_detection_yunet_2023mar.onnx` | `https://github.com/opencv/opencv_zoo/raw/main/models/…` |

Two honest notes about that table:

* Six of the seven models come from `storage.googleapis.com`. **YuNet is fetched from
  GitHub** (`opencv_zoo`), so if you are auditing egress in a locked-down environment,
  allow-list both hosts — or pre-seed the cache and run with `--no-download`.
* The request carries a `User-Agent: mirrorlab` header and nothing else. No machine
  identifier, no version string, no usage data.

The download path is deliberately defensive: it streams to a temporary file in the target
directory, checks the `Content-Length` header and rejects a truncated body, verifies the
result is not an HTML error page, and only then atomically replaces the destination. A
failed download degrades to a lighter detector backend rather than crashing.

**No telemetry. No analytics. No crash reporting. No "anonymous usage statistics".** Not
even opt-in — there is no code for it. If you want to know what MirrorLab phones home with,
the answer is: the model files, when they are missing.

**Nothing is written to disk unless you ask.** The only files MirrorLab creates are:

* the model cache (`mirrorlab models --download`, or first run)
* snapshots and recordings in `output_dir` (default `captures/`), when you press `s` or `r`
* the per-frame statistics CSV, when you pass `--stats-csv`

Your configuration file is read from the standard per-user location
([CROSS_PLATFORM.md](docs/CROSS_PLATFORM.md#platform-matrix)) and never uploaded. The
`--stats-csv` file contains expression names, gesture names and frame timings — no images —
and stays wherever you pointed it.

### Verifying the claim yourself

You do not have to take this on faith. The whole network surface is one module:

```bash
grep -rn "urllib\|requests\|socket\|http" src/mirrorlab/
```

You will find `detectors/models.py` and nothing else. To confirm at runtime, run with the
network disabled — with the models already cached, every feature still works:

```bash
mirrorlab models --download          # once, while you have a connection
# then disconnect, and:
mirrorlab run --no-download
```

`--no-download` makes `ensure_model` return `None` instead of fetching, so the detector
ladder falls through to whatever is available offline.

---

## The camera-permission model

MirrorLab does not request permissions itself; the operating system gates access to the
capture device and OpenCV's `VideoCapture` is the thing that triggers the prompt.

* **macOS** grants camera access to the *host application* — Terminal, iTerm2, VS Code —
  not to Python. The first `mirrorlab run` triggers the system prompt; until it is accepted,
  `open_camera` fails with a `CameraError` and the platform checklist. The app never retries
  silently and never asks for more than camera access.
* **Windows** has a global "let desktop apps use your camera" setting plus a per-app
  toggle. MirrorLab reads the camera and nothing else.
* **Linux** has no prompt: access is file permissions on `/dev/video*` plus membership in
  the `video` group. Running in a container requires passing the device through
  explicitly (`--device /dev/video0`), which is a deliberate action by whoever starts the
  container.

MirrorLab has no microphone code, no screen-capture code, no location code and no
filesystem-wide scanning. The one thing it reads outside the camera is its own config file
and the model cache.

---

## Threat model and non-issues

Worth being explicit about what MirrorLab does **not** defend against.

* **A filter, effect or gesture matcher is arbitrary Python.** Installing a third-party
  filter from an untrusted source is equivalent to running that person's code. There is no
  sandbox and no plugin isolation — see the "plugin API" item in the [roadmap](ROADMAP.md),
  which will have to address exactly this before it ships.
* **Model integrity is checked by size, not by hash.** `_is_probably_valid()` confirms the
  file exists, is above a minimum size, is at least 25 % of the expected size, and does not
  begin with `<` (an HTML error page). There is no checksum or signature verification. If
  you fetch models over an untrusted network, verify them yourself — the expected URLs and
  sizes are in the `MODELS` table, and pinning a SHA-256 per model is a welcome pull
  request.
* **The environment is trusted.** `MIRRORLAB_*` environment variables and the config file
  can point the model cache anywhere. `MIRRORLAB_MODELS` on a world-writable directory is a
  local privilege issue, not a remote one.
* **Recordings are as sensitive as your room.** An MP4 or a snapshot in `captures/` is a
  file like any other — MirrorLab sets no special permissions on it and does not encrypt
  it.
* **The hosted browser demo is a separate trust boundary.** `mirrorlab-demo.vercel.app` runs the
  vision models in your browser via WebAssembly and WebGL; your camera stream is read by the
  page locally and never uploaded. Its `Permissions-Policy` header requests `camera=(self)`
  and denies microphone and geolocation. If you do not trust the hosted page, run the demo
  from `web/` yourself with `npm run dev`.

## Dependency and supply-chain notes

MirrorLab's runtime dependencies are deliberately few — NumPy, OpenCV, MediaPipe — plus
optional `rich` and `PyYAML`. Licences and what each one obliges you to do are listed in
[THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).

The tested install pins (`mediapipe>=0.10.9,<0.11`, `numpy<2`, `opencv-python<5`) exist for
compatibility reasons documented in
[CROSS_PLATFORM.md](docs/CROSS_PLATFORM.md#the-dependency-pins), not security ones. If a
security advisory lands against a pinned version, installing the patched build inside a
compatible range is the right response — open an issue and we will widen or re-test the
range rather than leave a known-vulnerable pin in place.

Thanks for helping keep MirrorLab and its users safe.
