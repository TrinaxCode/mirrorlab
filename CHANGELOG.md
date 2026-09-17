# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> [English](CHANGELOG.md) · [README](README.md) · [Español](README.es.md) · [Roadmap](ROADMAP.md) · [Contributing](CONTRIBUTING.md)

## [Unreleased]

### Added

- Nothing yet. New work lands here before it is released.

### Changed

- Nothing yet.

### Fixed

- Nothing yet.

## [2.0.0] - 2026-01-15

The rewrite. 1.x was a single-file Haar-cascade demo that showed a reaction image for each
of five expressions; 2.0 is a package with a real perception pipeline, a filter library, an
AR effect system and a browser build. The prototype is kept in `legacy/` for reference and
is no longer installed, imported or supported.

### Rewritten

- **Single file → modular package.** `face_expression_detector.py` became
  `src/mirrorlab/`, split into nine layers: `camera`, `detectors`, `expressions`, `gestures`,
  `filters`, `effects`, `render`, `recording`, `utils`. The old script is preserved in
  `legacy/` and excluded from the distribution.
- **MediaPipe Solutions → MediaPipe Tasks.** The prototype called `mp.solutions.face_mesh`.
  MediaPipe 1.0 removed that namespace entirely, so the primary backend is now the Tasks API
  (`mediapipe.tasks.python.vision`): 478 landmarks, 52 blendshape channels and a 4×4 facial
  transformation matrix. The legacy Solutions backend is still probed as a fallback rung,
  which is why the tested pin is `mediapipe>=0.10.9,<0.11`.
- **Haar cascades → a five-rung backend ladder.** `tasks` → `solutions` → OpenCV YuNet
  (5 landmarks, 230 KB ONNX) → OpenCV Haar (bounding box only) → `none`. The application
  degrades instead of refusing to start, which also means "no MediaPipe" is a supported
  configuration.
- **Five ratio heuristics → 18 expressions.** Expression recognition now reads muscle
  activation from blendshapes rather than mouth-width ratios, with a documented geometric
  fallback for backends that provide landmarks but no blendshapes.
- **Reaction images → 15 procedural AR effects.** Face overlays anchor to the eye line
  (inter-ocular distance for scale, eye-line angle for roll) and are drawn with OpenCV
  primitives instead of composited from PNG assets, so nothing binary ships and every
  overlay is resolution-independent.
- **One camera path → cross-platform capture.** Per-OS backend priority
  (AVFoundation / DSHOW→MSMF / V4L2), a threaded drop-latest capture slot, video-file input,
  and a deterministic synthetic source for CI.
- **A local script → a browser demo.** `web/` is a Vite + React playground running the same
  classifier logic in TypeScript with WebAssembly vision models, deployed at
  <https://mirrorlab-demo.vercel.app>.

### Added

- **54 video filters** across six categories (`basic`, `color`, `artistic`, `stylize`,
  `glitch`, `utility`), all chainable with `--filter cartoon+vignette+glitch`.
- **10 curated presets** (`cinema`, `anime`, `noir`, `retro80s`, `broken`, `toon`, `ghost`,
  `studio`, `paper`, `vhs`), cycleable at runtime.
- **Hand tracking and 22 gestures** from 21 landmarks: 21 static poses matched by
  declarative geometric rules, plus swipes, a wave and a circle detected from trajectory.
  Every measurement is normalised by `hand_scale()`, so thresholds work at any distance.
- **Gesture-driven control** with an explicit dwell state machine: majority vote → 0.6 s
  hold → refractory period → release, with the hold drawn as an on-screen confirmation ring.
- **Air drawing** (`--air-draw`, or point with your index finger): a persistent canvas
  driven by the index tip with its own One-Euro pen filter, pinch to erase, open palm to
  clear.
- **A real CLI** with twelve subcommands: `run`, `demo`, `doctor`, `filters`, `gestures`,
  `expressions`, `effects`, `models`, `benchmark`, `config`, `cameras`, `gallery`.
- **A benchmark command** that measures every filter and prints median ms/frame.
- **Recording** to MP4 with a bounded drop-oldest encoder queue, plus a simultaneous GIF
  export at 12 fps / 640 px for sharing.
- **Layered configuration**: defaults → config file (`mirrorlab.json` / `.yaml`) →
  `MIRRORLAB_*` environment variables → CLI flags, resolved into a frozen, validated
  `Config`. Unknown keys are a hard error instead of a silent no-op.
- **Model cache management** (`mirrorlab models --status` / `--download`) with a per-user
  cache, atomic downloads, and `MIRRORLAB_MODELS` for air-gapped installs. Models are
  downloaded on first run and never committed or redistributed.
- **Smoothing stack**: One-Euro filters per landmark per coordinate (Casiez et al., CHI
  2012), an EMA per expression score, and a 7-frame majority vote before a label is
  reported.
- **Person segmentation** (`--segment`) powering background blur, background replace and a
  privacy filter, with `refine_mask` doing largest-blob selection, morphological closing and
  edge feathering.
- **Four HUD themes** (`aurora`, `magma`, `mono`, `candy`) and a resolution-independent HUD
  that scales every size from `height / 720`.
- **Per-frame statistics CSV** (`--stats-csv`) and a session summary printed on exit.
- **Documentation set**: README (English and Spanish), architecture, filters, gestures,
  expressions, cross-platform notes, FAQ, this changelog, a roadmap, contribution and
  security policies, and third-party licence inventory.

### Changed

- `Config` is a **frozen dataclass**. Settings are resolved once and never mutated
  mid-session; `with_overrides()` returns a modified copy.
- Timestamps handed to MediaPipe are now **strictly increasing**, enforced by
  `_TimestampGuard`, because VIDEO mode misbehaves on duplicate stamps.
- Model selection is driven by **capability probes**, not version strings: the code asks
  whether the Tasks API exists, whether `cv2.FaceDetectorYN` exists, and whether the Haar
  cascades are present.
- The HUD keeps labels **text-only** because OpenCV's Hershey fonts cannot render emoji;
  `_emoji_safe()` documents that decision in code.
- Effects that react to expressions (`DogEffect` scales the tongue with `jawOpen`;
  `BlushEffect` scales intensity with `mouthSmile`) replaced the prototype's static
  per-expression images.
- Filter metadata is the interface: every filter declares `name`, bilingual labels, emoji,
  category, cost and `needs_mask`, and the CLI, HUD and website all read the same registry.

### Fixed

- **Windows cameras that open but never deliver pixels.** `_open_raw` performs a one-frame
  read as the acceptance test, because DSHOW will happily report an open device that
  produces nothing.
- **Capture latency growth.** A single-slot buffer replaces any queueing, so a detector
  slower than the camera drops stale frames instead of accumulating delay until the preview
  feels like a laggy mirror.
- **Left/right hand filter cross-talk.** The landmark smoother keys hand tracks by
  handedness (`index + 2` for right hands, `+ 100` for world landmarks) so a left hand never
  inherits the right hand's filter state when detection order swaps.
- **Rebuilding remap tables every frame.** `vignette`, `fisheye`, `crt` and `bg_replace`
  cache their maps and backgrounds per frame size.
- **"The window does not close on macOS."** Four `cv2.waitKey(1)` pumps after
  `destroyAllWindows()` let Cocoa finish the teardown, so the process stops looking hung.
- **"Unknown filter" typos.** `build_filter` now raises with `difflib` close matches, and
  `Config.from_mapping` rejects unknown keys with a pointer to `mirrorlab config --list`.
- **The OK sign was unreachable.** A generic `pinch` always outscored it, so
  `classify_gesture` now applies an explicit tie-break in favour of `ok` when the other
  fingers are raised.
- **Expression flicker.** Scores are smoothed with an EMA and a winner requires 4 of the
  last 7 frames, so a blink no longer takes over the label.

### Removed

- `mp.solutions` as the primary detection path.
- The prototype's Haar-cascade smile detector and its five-expression set.
- The `images/` reaction-image display pipeline and the `config.json` schema that drove it.
  The 18 expressions are now reported by the classifier; visual reactions are AR effects.
- The `install_dependencies.sh` / `run.sh` shell wrappers, replaced by
  `pip install -e ".[dev]"` and the `mirrorlab` console script.
- Committed model binaries. Every `.task` / `.tflite` / `.onnx` file is downloaded into a
  user cache at runtime.

### Known limitations

- Virtual-camera output is **not** in 2.0. `pyvirtualcam` is GPLv2, so it can only ever be
  an optional extra; see the [roadmap](ROADMAP.md).
- `blink` has a working blendshape scorer but is excluded from `_PRIORITY`, so it is a raw
  signal rather than a reported expression.
- There is no `tongueOut` blendshape channel in MediaPipe, so no tongue expression exists.
- `push` / `pull` are declared in `GestureTracker.SWIPES` but no code path emits them.
- `--air-draw`, `--reactions`, `model_complexity` and `log_level` are accepted by the CLI and
  config but are not yet wired into the running application.

## [1.0.0] - 2024

The original prototype, preserved in `legacy/`.

### Added

- Haar-cascade face and smile detection on a webcam feed.
- Five recognised states — `smile`, `surprised`, `tongue`, `peace`, `neutral` — each mapped
  to a reaction image.
- Optional landmark display via an experimental `mp.solutions.face_mesh` variant
  (`legacy/advanced_detector.py`).
- A `config.json` with the image directory, display size and confidence thresholds.
- Spanish-language documentation, example images and setup scripts.

[Unreleased]: https://github.com/TrinaxCode/mirrorlab/compare/v2.0.0...HEAD
[2.0.0]: https://github.com/TrinaxCode/mirrorlab/releases/tag/v2.0.0
[1.0.0]: https://github.com/TrinaxCode/mirrorlab/releases/tag/v1.0.0
