# MirrorLab roadmap

> [English](ROADMAP.md) · [README](README.md) · [Español](README.es.md) · [Changelog](CHANGELOG.md) · [Contributing](CONTRIBUTING.md)

What is done, what is next, and — just as usefully — what is deliberately not planned.
Dates are targets, not promises: this is a small project and correctness beats schedule.

Legend: `[x]` shipped · `[ ]` planned · `[~]` in progress

---

## v2.0 — the rewrite

Released 2026-01-15. Details in [CHANGELOG.md](CHANGELOG.md#200---2026-01-15).

- [x] Modular package replacing the single-file prototype (now in `legacy/`)
- [x] MediaPipe **Tasks** migration: 478 landmarks, 52 blendshapes, facial transformation matrix
- [x] Five-rung detector fallback ladder, so the app degrades instead of crashing
- [x] 54 chainable video filters across six categories, plus 10 curated presets
- [x] Hand tracking with 21 static gestures and 6 dynamic ones, all geometrically explainable
- [x] 15 procedural AR effects (11 face, 4 hand) anchored to landmarks
- [x] Gesture control with a dwell state machine and an on-screen hold-to-confirm ring
- [x] Cross-platform camera handling: AVFoundation, DSHOW, MSMF, V4L2, plus video files
- [x] Threaded capture with a drop-latest slot, and a drop-oldest encoder queue
- [x] 18 expressions from blendshapes, with a documented geometric fallback
- [x] Air drawing, recording (MP4 + GIF), snapshots, stats CSV and a session summary
- [x] Twelve-command CLI with `doctor`, `benchmark`, `cameras` and machine-readable output
- [x] Layered, validated, frozen configuration with `MIRRORLAB_*` env overrides
- [x] Browser demo (Vite + React + WebAssembly vision) deployed to Vercel
- [x] Documentation set: English and Spanish READMEs plus seven deep-dive documents

---

## v2.1 — polish and reach

Goal: make the released thing easier to install, easier to trust and easier to embed. No
new perception models — this milestone is about the edges around what already works.

- [ ] **PyPI release.** Publish `mirrorlab` so `pip install mirrorlab` works, with wheels
      built for 3.9–3.12 on all three platforms. Update the README's install section to put
      the package first and the source build second.
- [ ] **Homebrew formula.** `brew install trinaxcode/tap/mirrorlab` for macOS, including the
      Python dependency set as a formula resource so the pinned MediaPipe/NumPy/OpenCV
      combination is reproduced exactly.
- [x] **Wire up `--air-draw`.** The flag and the `air_draw` config key now create the canvas
      before the first frame, so `mirrorlab run --air-draw` works without also pressing `d`.
- [x] **Wire up `--reactions`.** `show_reactions` / `reactions_dir` are now read by the app,
      which draws a matching picture-in-picture from `assets/reactions/` and toggles it with `i`.
- [x] **Wire up `model_complexity` and `log_level`.** `model_complexity` reaches the legacy
      Solutions hand backend, and a `"log_level": "DEBUG"` in config is honoured unless
      `--verbose` overrides it.
- [x] **Fix `mirrorlab doctor`'s capability section.** `_cmd_doctor` now imports the filter and
      effect registries before counting, so the three counters report 54 / 11 / 4.
- [x] **Reachability audit.** `blink` was added to the blendshape scorer table and the
      priority list so it can actually win, and the inert `push`/`pull` entries were removed
      from `GestureTracker.SWIPES`. The registries now only advertise what fires.
- [ ] **Model integrity hashes.** `_is_probably_valid()` checks size and rejects HTML, but
      there is no checksum. Publish a SHA-256 per model in the `MODELS` table and verify it
      after download.
- [x] **Test suite.** 441 pure-logic tests across config, geometry, gestures, expressions,
      filters, effects, the CLI and the end-to-end pipeline. No camera, no network, no display.
- [ ] **Recording quality pass.** Expose `gif_fps`, `gif_max_frames` and `max_queue` as
      config keys instead of constructor-only arguments, and add an audio-toggle stub that
      clearly states audio is unsupported.
- [ ] **`web/` parity table.** The browser build ships a subset of the 54 filters and 22
      gestures (WebGL shaders rather than OpenCV, and hand-only geometry). Document the
      overlap explicitly so the demo does not silently under-promise.

---

## v2.2 — perception depth

Goal: use the signals the Tasks API already produces but MirrorLab ignores today. No new
model downloads — this is about reading what is already there.

- [ ] **Head-pose parallax.** The 4×4 facial transformation matrix is already captured in
      `FaceObservation.transformation_matrix` and never read. Derive yaw/pitch/roll and shift
      the HUD and the AR overlays against it, so the UI feels attached to the head rather
      than pasted on the frame.
- [ ] **3D mask rendering.** Use the same matrix plus the 478-point mesh to render a face
      model with correct occlusion (the `selfie_multiclass` model can supply a hair mask for
      the depth test). This is the prerequisite for any mask that should pass behind the
      nose.
- [ ] **Gaze tracking.** The `eyeLookIn/Out/Up/Down` blendshape channels are already in
      `BLENDSHAPE_NAMES` and currently unused. A gaze estimate enables look-to-select for
      menus and a "look at the camera" nudge for video calls.
- [ ] **Two-hand gestures.** `pinch_zoom` is declared but scores the same single-hand pinch
      as `pinch`; the docstring says the engine should handle the two-hand span. Implement
      it: distance between both hands' pinches drives zoom, rotation drives filter cycling.
- [ ] **`push` / `pull` dynamic gestures.** Removed from `GestureTracker.SWIPES` in 2.0.0 so the
      registry only advertises what actually fires; re-add them together with the z-axis detector. (Previously declared and never
      emitted. `HandObservation.world_landmarks` gives metric depth, so a push is a falling
      mean `z` over a short window — see [GESTURES.md](docs/GESTURES.md#adding-a-dynamic-gesture).
- [ ] **Blink as a first-class signal.** The scorer is correct but excluded from `_PRIORITY`
      because a 150 ms event would flicker the HUD. Expose blink rate and eye-aspect-ratio
      over time as a stats stream instead of a label.
- [ ] **Per-region skin smoothing.** `skin_smooth` is global today. Drive it from the person
      mask (or a skin-tone mask) so it does not soften hair, eyes and background.
- [ ] **Calibration mode.** A short guided flow that records your neutral face and resting
      hand and adapts `min_score` and the gesture thresholds to you, instead of asking users
      to edit constants.

---

## v3.0 — platform and ecosystem

Goal: turn MirrorLab from an application into something other things are built on. Both
items here need an interface agreed before code is written; open an issue to discuss.

- [ ] **Virtual camera output.** Publish the rendered frame as a system camera so Zoom,
      Meet, Teams, Discord and OBS can use it directly. The blocker is licensing, not
      engineering: `pyvirtualcam` is **GPLv2** and MirrorLab is MIT, so this ships as an
      opt-in extra (`pip install "mirrorlab[virtualcam]"`) and never as a default
      dependency. Investigate a subprocess-based bridge as an alternative that keeps the
      licence boundary clean.
- [ ] **Plugin API.** A documented, versioned extension point so third-party filters,
      effects and gestures can be installed as packages. This has a security dimension that
      must be designed in, not bolted on: a plugin is arbitrary Python, so the API needs an
      explicit trust model, a declared capability surface, and clear documentation that
      installing a plugin is equivalent to running its author's code.
- [ ] **Preset sharing.** Export and import looks as a single portable file, with a URL
      scheme for the browser demo so a preset can be linked. Needs a schema version and a
      validation path before anything is published.
- [ ] **MLP gesture trainer.** An optional tool that learns a small classifier from your own
      recorded poses, as a *complement* to the geometric rules — not a replacement. The rules
      stay as the default because they need no data and are debuggable; the trainer is for
      users whose hands the rules serve badly.
- [ ] **Rock–Paper–Scissors game mode.** The three poses are already classifiable (`fist`,
      `open_palm`, and a V-shape variant). A best-of-five game against the machine makes an
      excellent demo of the whole gesture stack, and it is the kind of thing that surfaces
      real latency problems immediately.
- [ ] **Live streaming integrations.** RTMP/WebRTC output, and an OBS scene collection. Pairs
      with the virtual-camera work; the same licence boundary applies.
- [ ] **Headless server mode.** A documented, tested path for running MirrorLab as a
      long-lived process that ingests frames and emits detections, with a stable JSON
      protocol.
- [ ] **Accessibility.** Full keyboard-only operation (partially present: every filter is
      reachable by number key), a high-contrast HUD theme, and audio cues for gesture
      confirmation so the ring is not the only feedback channel.

---

## Explicitly not planned

Saying no is part of a roadmap. These come up often and the answer is no, with a reason.

- **GPU/CUDA acceleration.** MirrorLab is a CPU-first project on purpose. A GPU path would
  add a driver matrix, a build matrix and a whole class of "works on my machine" bugs to
  save milliseconds that a smaller capture resolution saves for free.
- **A trained deep-learning expression classifier.** The blendshape scorer set is
  explainable, testable without a dataset, and tunable by the user. A CNN would be more
  accurate on a benchmark and less useful in a playground.
- **Cloud processing, accounts, or a hosted API.** The privacy model is that frames never
  leave the machine. There is no version of this project where that is negotiable.
- **Bundling the model weights in the wheel.** It would triple the download size, mix
  licences that are not ours into our distribution, and break the offline story for anyone
  who already has the cache. Models are downloaded, never redistributed.
- **A "Snapchat filter" / "Instagram filter" feature or description.** Beyond the trademark
  problem, the accurate description — AR-style face filters — is what we build.
- **A mobile app.** MediaPipe has mobile SDKs, but a Python desktop pipeline does not port
  to them, and the browser demo already covers the "show someone on their phone" use case.

---

## How to influence this list

Open an issue. Items move fastest when they come with a concrete use case, and the
[`good first issue`](CONTRIBUTING.md#good-first-issues) label marks the ones that are
genuinely self-contained. The v2.1 list is deliberately full of small, independent fixes —
if you want to contribute something useful in an afternoon, that is where to look.
