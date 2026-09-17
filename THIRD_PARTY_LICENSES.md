# Third-party licences

> [English](THIRD_PARTY_LICENSES.md) · [README](README.md) · [Español](README.es.md) · [Security policy](SECURITY.md) · [Contributing](CONTRIBUTING.md)

MirrorLab itself is [MIT licensed](LICENSE) — © 2026 TrinaxCode. This file lists what it
depends on, under what terms, and what those terms ask of you.

Short version: **everything MirrorLab links against is permissively licensed.** The one
GPL component in this space (`pyvirtualcam`) is deliberately *not* a dependency and will
only ever be an optional extra. The model weights are not distributed by this project at
all; they are downloaded at runtime and governed by their own model cards.

---

## Contents

- [Runtime dependencies](#runtime-dependencies)
- [Optional dependencies](#optional-dependencies)
- [Transitive dependencies](#transitive-dependencies)
- [Model licences](#model-licences)
- [Deliberately not a dependency: pyvirtualcam](#deliberately-not-a-dependency-pyvirtualcam)
- [Assets in this repository](#assets-in-this-repository)
- [What this means for your project](#what-this-means-for-your-project)

---

## Runtime dependencies

Declared in `pyproject.toml` under `[project.dependencies]`. These are installed by
`pip install mirrorlab`.

| Package | Licence | What MirrorLab uses it for | Obligations |
| --- | --- | --- | --- |
| **mediapipe** | Apache-2.0 | Face landmarking (478 points + 52 blendshapes), hand landmarking (21 points), person segmentation, via the Tasks API | Include the licence text and NOTICE file; state changes if you modify it |
| **opencv-python** | Apache-2.0 (see note) | Capture, every image operation, every drawn overlay, the HUD, video encoding | Include the licence text and NOTICE file |
| **numpy** | BSD-3-Clause | Every array in the pipeline, and all filter maths | Retain the copyright notice, the three conditions and the disclaimer |

**On the `opencv-python` licence.** The Python wrapper package and OpenCV itself are separate
works. OpenCV is Apache-2.0, and the current `opencv-python` wheel metadata declares
Apache-2.0 as well; historically the wrapper was distributed under the MIT licence. Either
way the obligations are the same in practice: keep the copyright notice and the licence
text, and do not use the OpenCV name to endorse your product. Both licences are compatible
with MirrorLab's MIT terms and with commercial use.

## Optional dependencies

Not installed by default; each is behind an extra.

| Package | Extra | Licence | Used for | Obligations |
| --- | --- | --- | --- | --- |
| **rich** | `cli`, `dev`, `all` | MIT | Nicer CLI output. The CLI degrades to plain text without it | Keep the notice |
| **PyYAML** | `cli`, `dev`, `all` | MIT | Reading `mirrorlab.yaml` / `.yml` config files. `.json` works without it | Keep the notice |
| **pytest** | `dev` | MIT | The test suite | Development only — not distributed |
| **pytest-cov** | `dev` | MIT | Coverage reporting | Development only |
| **ruff** | `dev` | MIT | Linting | Development only |
| **black** | `dev` | MIT | Formatting | Development only |
| **mypy** | `dev` | MIT | Static type checking | Development only |
| **mkdocs-material** | `docs` | MIT | Building the documentation site | Development only |
| **Pillow** | — | MIT-CMU (HPND) | **GIF export.** `save_gif()` imports PIL lazily and raises a clear message if it is missing | Keep the notice |

**Pillow is not currently in any extra.** GIF recording works only if Pillow happens to be
installed (`pip install pillow`). The MP4 still saves without it and a warning is logged.
Adding Pillow to a `gif` extra is on the [roadmap](ROADMAP.md).

## Transitive dependencies

Installed automatically by the packages above. They are not MirrorLab's direct
dependencies, but they end up in your environment, so they belong in an honest inventory.

| Package | Pulled in by | Licence |
| --- | --- | --- |
| absl-py | mediapipe | Apache-2.0 |
| attrs | mediapipe | MIT |
| flatbuffers | mediapipe | Apache-2.0 |
| jax, jaxlib | mediapipe | Apache-2.0 |
| matplotlib | mediapipe | PSF-based (Matplotlib licence) |
| protobuf | mediapipe | BSD-3-Clause |
| sounddevice | mediapipe | MIT |
| sentencepiece | mediapipe | Apache-2.0 |
| opencv-contrib-python | mediapipe | Apache-2.0 |
| packaging, pluggy, iniconfig | pytest | MIT / Apache-2.0 |
| coverage.py | pytest-cov | Apache-2.0 |

Two of these are worth a second look:

* **`opencv-contrib-python`** arrives because mediapipe declares it. MirrorLab never calls a
  contrib-only function — the `oil` filter in particular implements its histogram binning
  from scratch rather than calling `cv2.oilPainting` — so MirrorLab behaves identically in a
  minimal `opencv-python`-only install. See
  [FILTERS.md](docs/FILTERS.md#artistic-13).
* **`jax`/`jaxlib`** are a large download for a CPU-only project. MediaPipe declares them;
  MirrorLab does not use JAX anywhere. If install size matters to you, that is where it goes.

## Model licences

**This is the part people get wrong, so it is stated plainly.**

MirrorLab does **not** redistribute any model weights. No `.task`, `.tflite` or `.onnx`
binary is committed to this repository, included in the wheel, or shipped in a release
archive. `mirrorlab models --download` (and the automatic first-run fetch) retrieves them
from their publishers into a per-user cache, exactly as a browser downloads a web font.

| Model | Fetched from | Publisher | Purpose |
| --- | --- | --- | --- |
| `face_landmarker.task` (3.7 MB) | `storage.googleapis.com/mediapipe-models` | Google (MediaPipe) | 478 face landmarks + 52 blendshape channels + facial transformation matrix |
| `hand_landmarker.task` (7.8 MB) | `storage.googleapis.com/mediapipe-models` | Google (MediaPipe) | 21 hand landmarks per hand + handedness |
| `gesture_recognizer.task` (8.4 MB) | `storage.googleapis.com/mediapipe-models` | Google (MediaPipe) | MediaPipe's canned 7-gesture classifier (optional cross-check; not on the default path) |
| `selfie_segmenter.tflite` (0.25 MB) | `storage.googleapis.com/mediapipe-models` | Google (MediaPipe) | Person/background mask |
| `selfie_multiclass_256x256.tflite` (16 MB) | `storage.googleapis.com/mediapipe-models` | Google (MediaPipe) | 6-class segmentation (hair, skin, clothes, background) |
| `pose_landmarker_lite.task` (5.5 MB) | `storage.googleapis.com/mediapipe-models` | Google (MediaPipe) | 33 body landmarks (optional full-body mode) |
| `face_detection_yunet_2023mar.onnx` (0.23 MB) | `github.com/opencv/opencv_zoo` | OpenCV / Shiqi Yu et al. | Tiny face detector with 5 landmarks — the no-MediaPipe fallback |

What that means:

* **The MediaPipe model *code* is Apache-2.0** — the same licence as the MediaPipe library.
  The model **binaries** are published by Google under their own terms, and each has its own
  model card. The MediaPipe model cards are the authoritative source, and they are the pages
  to read before you redistribute a model or ship it inside a product:
  * Face landmarker — <https://ai.google.dev/edge/mediapipe/solutions/vision/face_landmarker>
  * Hand landmarker — <https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker>
  * Gesture recognizer — <https://ai.google.dev/edge/mediapipe/solutions/vision/gesture_recognizer>
  * Image segmenter — <https://ai.google.dev/edge/mediapipe/solutions/vision/image_segmenter>
  * Pose landmarker — <https://ai.google.dev/edge/mediapipe/solutions/vision/pose_landmarker>
* **The YuNet model** comes from the OpenCV Model Zoo (<https://github.com/opencv/opencv_zoo>),
  which publishes its models under Apache-2.0 alongside the OpenCV project. Its citation is
  the YuNet paper (Wu, W. et al., *YuNet: A Tiny Millisecond-level Face Detector*, Machine
  Intelligence Research, 2023).
* **You are responsible for the terms of the models you use.** MirrorLab's MIT licence covers
  MirrorLab's code. It cannot and does not extend to third-party weights.
* **Verify before you trust.** MirrorLab checks a downloaded model for existence, plausible
  size and the absence of an HTML error page — but it does **not** verify a cryptographic
  hash. If you fetch models over an untrusted network, check them yourself. Publishing a
  SHA-256 per model is a welcome contribution; see [SECURITY.md](SECURITY.md) and the
  [roadmap](ROADMAP.md).

## Deliberately not a dependency: pyvirtualcam

The standard way to expose a Python-rendered frame as a system camera (for Zoom, Meet, Teams,
Discord or OBS) is [`pyvirtualcam`](https://github.com/letmaik/pyvirtualcam). It is
**GPLv2**, and MirrorLab is MIT.

Linking a GPL library into the default install would relicense the entire project, so
MirrorLab does not. If virtual-camera output ships, it will be an **opt-in extra**:

```bash
pip install "mirrorlab[virtualcam]"
```

That keeps the licence boundary where it belongs — in your hands, made explicitly, rather
than imposed on every user by a default dependency. The alternative being investigated is a
subprocess bridge that talks to a separately-installed virtual camera over a pipe, which
keeps the two works independent. Both options are tracked in [ROADMAP.md](ROADMAP.md).

The same reasoning applies to any future GPL or AGPL integration: optional extra, never a
default.

## Assets in this repository

| Path | What it is | Licence |
| --- | --- | --- |
| `assets/reactions/*.png` | Eight reaction images (angry, love, neutral, peace, sad, smile, surprised, tongue) | Part of this repository, MIT — see the note below |
| `tests/assets/portrait.jpg`, `tests/assets/woman_hands.jpg` | Test fixtures used by detection tests | Part of this repository, MIT |
| `web/public/favicon.svg` | The demo's favicon | Part of this repository, MIT |
| `legacy/**` | The 1.x prototype, kept for reference. **Not installed, not imported, not supported** | Part of this repository, MIT |

Note on the reaction images: they are present in `assets/reactions/` and addressed by the
`reactions_dir` config key, but nothing in the 2.0 code path renders them yet — the
`--reactions` flag and `show_reactions` key are accepted and currently unused. See the
[roadmap](ROADMAP.md). Everything MirrorLab actually draws is generated procedurally with
OpenCV primitives, which is why there is no binary artwork in the render path.

## What this means for your project

**If you use MirrorLab as a library or an application**, including commercially:

1. Keep MirrorLab's MIT copyright notice and licence text.
2. Keep the notices for MediaPipe, OpenCV, NumPy and anything else you redistribute.
3. Read the model cards for the models you actually ship — and if you ship the weights
   inside your product, that is a redistribution you are doing, not one MirrorLab did.
4. Do not describe your product as a "Snapchat filter" or an "Instagram filter". Those are
   trademarks; "AR-style face filters" is accurate and safe.

**If you contribute to MirrorLab**: do not add a GPL/AGPL runtime dependency to the default
install, and do not commit model binaries or third-party artwork. Both are checked in review
— see the [pull request checklist](CONTRIBUTING.md#pull-request-checklist).

---

*This document is a good-faith inventory, not legal advice. If a licence question matters to
your business, read the upstream licence texts and talk to a lawyer.*
