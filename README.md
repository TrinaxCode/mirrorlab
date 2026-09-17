# MirrorLab — real-time webcam filters, face expressions and hand gestures, one command, no GPU

Turn your webcam into a computer-vision playground: 54 video filters, 18 facial expressions read from 52 blendshape channels, 22 hand gestures, 15 AR effects — CPU only, fully local.

[English](README.md) | [Español](README.es.md)

[![License: MIT](https://img.shields.io/badge/license-MIT-3da639?style=flat-square)](LICENSE)
[![Python 3.9–3.12](https://img.shields.io/badge/python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12-3776ab?style=flat-square)](pyproject.toml)
[![Platforms: macOS, Windows, Linux](https://img.shields.io/badge/platform-macOS%20%7C%20Windows%20%7C%20Linux-4c4c4c?style=flat-square)](#install)
[![CPU only](https://img.shields.io/badge/CPU-only-8957e5?style=flat-square)](#performance)
[![Live demo](https://img.shields.io/badge/demo-live-ff4b4b?style=flat-square)](https://mirrorlab-demo.vercel.app)
[![PRs welcome](https://img.shields.io/badge/PRs-welcome-brightgreen?style=flat-square)](CONTRIBUTING.md)
[![GitHub](https://img.shields.io/badge/GitHub-TrinaxCode%2Fmirrorlab-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/TrinaxCode/mirrorlab)

---

## Demo

<!-- TODO: replace with assets/demo.gif after recording the hero GIF -->

*The hero GIF should show one uninterrupted take: a neutral face, then a smile lighting up the expression badge, a peace sign switching the filter to `cartoon`, a swipe changing the preset, and a thumbs-up firing a snapshot — with the hold-to-confirm ring filling before the action lands. Record it with `mirrorlab run --filter cartoon`, press `r`, perform the sequence, press `r` again, and the MP4 and GIF land in `captures/`.*

There is also a **browser demo** with no install at all: **[mirrorlab-demo.vercel.app](https://mirrorlab-demo.vercel.app)**. It runs the vision models in your browser with WebAssembly and WebGL. Your camera stream never leaves the page.

---

## Why this exists

Webcam CV demos usually fall into one of two camps: a 200-line script that detects one thing badly, or a research repo that needs a GPU and a conda environment. MirrorLab is the missing middle — a real package you can `pip install`, that reads faces and hands properly, and that still works when a model or a runtime is unavailable.

It also exists to solve a specific 2025 problem: **MediaPipe 1.0 removed `mp.solutions`**, and **1.0.1 aborts inside Apple's Metal helper on some macOS builds**. MirrorLab probes what actually works on your machine and degrades instead of crashing. See [the pinned install](#known-good-install).

## Feature highlights

- **54 video filters** — chainable, categorised, benchmarked, with 10 curated presets
- **22 hand gestures** — 21 static poses matched by explainable geometric rules plus swipes, a wave and a circle
- **18 facial expressions** — read from MediaPipe's 52 ARKit-style blendshape channels, not landmark ratios
- **15 AR effects** — 11 face overlays anchored to the eye line, 4 hand effects, all drawn procedurally
- **5 detector backends** — a fallback ladder so the app degrades instead of refusing to start
- **CPU only** — no GPU, no CUDA, no driver matrix; 720p at 30 fps on a modern laptop
- **Records MP4 + GIF** — one keypress, plus snapshots, a stats CSV and a session summary
- **Browser demo** — the same perception ideas, running client-side at [mirrorlab-demo.vercel.app](https://mirrorlab-demo.vercel.app)
- **100% local** — camera frames never leave your machine; the only network access is the one-time model download

---

## Install

### From source (primary, works today)

```bash
git clone https://github.com/TrinaxCode/mirrorlab.git
cd mirrorlab

python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -e ".[dev]"
mirrorlab run
```

That is the whole install. The first `mirrorlab run` downloads about 12 MB of models into a per-user cache and starts the preview.

Prefer `make`? `make install` creates the virtualenv and installs the dev extras, and `make run` starts the app.

### From PyPI (coming soon)

```bash
pip install mirrorlab
mirrorlab run
```

> **Not published yet.** MirrorLab is not on PyPI. Use the source install above. The PyPI release is tracked in [ROADMAP.md](ROADMAP.md).

### Known-good install

> **Pin these if you hit a MediaPipe problem.** MediaPipe 1.0 removed `mp.solutions`, and MediaPipe 1.0.1 **hard-crashes on some macOS builds** inside Apple's Metal helper (`DrishtiMetalHelper ... Check failed: service_ Service is unavailable`). This combination is tested and known-good:
>
> ```bash
> pip install "mediapipe>=0.10.9,<0.11" "numpy<2" "opencv-python<5"
> ```
>
> `numpy<2` is required because MediaPipe 0.10.x was built against NumPy 1.x's C ABI. Full explanation in [docs/CROSS_PLATFORM.md](docs/CROSS_PLATFORM.md#the-dependency-pins).

Verify the result before you run anything:

```bash
mirrorlab doctor
```

It prints your Python, OpenCV and MediaPipe versions, which detector backends initialised, which models are cached, and the exact `pip install` line to fix a missing MediaPipe.

### Platform notes

<details>
<summary><b>macOS</b></summary>

- Your terminal needs camera access: **System Settings → Privacy & Security → Camera** → enable Terminal / iTerm2 / VS Code.
- The permission is granted **per host application**, not per Python interpreter — granting it to Terminal does nothing for a script started from an IDE.
- The first run triggers a system prompt. Accept it, then run again; macOS does not grant access mid-process.
- A Continuity Camera iPhone can occupy index 0. If the wrong camera opens: `mirrorlab run --camera 1`.
- The window needs a few event-loop iterations to close. MirrorLab pumps them for you; see [the FAQ](docs/FAQ.md#why-does-the-window-not-close-on-macos).

</details>

<details>
<summary><b>Windows</b></summary>

- **Settings → Privacy → Camera** → *Let desktop apps access your camera*.
- If the preview is black or the device never opens, switch capture backend:
  ```powershell
  mirrorlab run --backend dshow     # DirectShow
  mirrorlab run --backend msmf      # Media Foundation
  ```
  DSHOW will happily report an open device that never delivers pixels, so MirrorLab reads one frame as its acceptance test — but when a driver misbehaves, the other backend usually works.
- Use `py -3.11 -m venv .venv` if `python3` is not on your PATH.

</details>

<details>
<summary><b>Linux</b></summary>

```bash
sudo usermod -aG video "$USER"     # then log out and back in — group changes apply at login
ls -l /dev/video*                  # the device node must exist
mirrorlab run
```

- In Docker or WSL2 you must pass the device through: `--device /dev/video0` (Docker) or `usbipd attach` (WSL2). See [docs/CROSS_PLATFORM.md](docs/CROSS_PLATFORM.md#docker).
- On a server with no display, install `opencv-python-headless` and use `mirrorlab run --headless`.

</details>

---

## Usage

### Common commands

```bash
mirrorlab                                  # run with defaults (same as `mirrorlab run`)
mirrorlab run --filter cartoon+vignette    # chain filters with `+`
mirrorlab run --preset noir                # a curated multi-filter look
mirrorlab run --effect sunglasses --effect fire
mirrorlab run --no-hands                   # faster: skip hand tracking
mirrorlab run --segment                    # enable the person mask (background blur/replace)

mirrorlab filters                          # list all 54, grouped by category
mirrorlab filters --category artistic      # one category
mirrorlab filters --presets                # the 10 curated presets
mirrorlab gestures                         # every gesture and its bound action
mirrorlab expressions                      # every detectable expression
mirrorlab effects                          # every AR effect

mirrorlab doctor                           # is this machine ready?
mirrorlab cameras --max-index 5            # which indices and backends deliver frames
mirrorlab models --status                  # what is in the model cache
mirrorlab models --download                 # fetch any missing model bundles
mirrorlab benchmark --all --frames 30      # ms/frame for all 54 filters
mirrorlab config --list                    # every config key and its default
mirrorlab config --init mirrorlab.json     # write a config file you can edit
mirrorlab gallery --output assets/filter-gallery.png   # contact sheet of all filters
mirrorlab demo --frames 120                # offline, synthetic source, no camera
```

`mirrorlab` with no arguments is `mirrorlab run`. Every subcommand supports `--help`, and
most support `--json` for machine-readable output — which is what the website's catalog
generator consumes.

### Configuration

Configuration resolves in four layers, lowest priority first: built-in defaults → a config
file (`mirrorlab.json` / `mirrorlab.yaml`, discovered in the current directory or
`~/.config/mirrorlab`) → `MIRRORLAB_*` environment variables → CLI flags. Unknown keys are a
hard error with a pointer to `mirrorlab config --list`, so a typo never silently does
nothing.

```bash
MIRRORLAB_FILTER="cartoon+vignette" MIRRORLAB_THEME=magma mirrorlab run
MIRRORLAB_SMOOTHING_MIN_CUTOFF=1.0 mirrorlab run      # smoother landmarks
```

Every key, with its type and default:

#### Camera

| Key | Type | Default | Description |
| --- | --- | --- | --- |
| `camera_index` | int | `0` | Camera device index (`--camera`, `-c`) |
| `camera_width` | int | `1280` | Requested capture width (`--camera-width`); lower it for speed |
| `camera_height` | int | `720` | Requested capture height (`--camera-height`) |
| `camera_fps` | int | `30` | Requested capture frame rate, 1–240 (`--camera-fps`) |
| `camera_backend` | str | `"auto"` | `auto`, `avfoundation`, `dshow`, `msmf`, `v4l2` or `any` (`--backend`) |
| `mirror` | bool | `true` | Flip horizontally so the preview behaves like a mirror (`--no-mirror`) |

#### Detectors

| Key | Type | Default | Description |
| --- | --- | --- | --- |
| `enable_face` | bool | `true` | Face detection and expression recognition (`--no-face`) |
| `enable_hands` | bool | `true` | Hand tracking and gestures. Needs MediaPipe (`--hand` / `--no-hands`) |
| `enable_segmentation` | bool | `false` | Person mask for `bg_blur`, `bg_replace`, `privacy` (`--segment`) |
| `max_faces` | int | `1` | Maximum faces to track (`--max-faces`) |
| `max_hands` | int | `2` | Maximum hands to track (`--max-hands`) |
| `min_face_confidence` | float | `0.5` | Face detection threshold, 0–1 |
| `min_hand_confidence` | float | `0.5` | Hand detection threshold, 0–1 |
| `min_tracking_confidence` | float | `0.5` | Tracking threshold for both models, 0–1 |
| `model_complexity` | int | `1` | `0` = fastest, `1` = balanced. Applies to the legacy Solutions hand backend; the Tasks bundle is fixed |

#### Pipeline

| Key | Type | Default | Description |
| --- | --- | --- | --- |
| `filter` | str | `"original"` | Filter or `+`-chain, e.g. `cartoon+vignette+glitch` (`--filter`, `-f`) |
| `effects` | list | `[]` | AR effect names, e.g. `["sunglasses","dog"]` (`--effect`, repeatable) |
| `gesture_control` | bool | `true` | Let gestures trigger actions (`--no-gesture-control` detects without acting) |
| `air_draw` | bool | `false` | Start with air-draw enabled (`--air-draw`). Also toggled at runtime with `d`, `i` or the ☝️ `pointing` gesture |
| `smooth_landmarks` | bool | `true` | One-Euro landmark smoothing. Off also disables expression EMA |
| `smoothing_min_cutoff` | float | `1.7` | One-Euro cutoff at rest: lower = smoother, slightly laggier |
| `smoothing_beta` | float | `0.35` | One-Euro speed coefficient: higher = more responsive to fast motion |
| `expression_smoothing` | float | `0.35` | EMA weight for expression scores, 0–1; `0` disables smoothing |

#### Window and HUD

| Key | Type | Default | Description |
| --- | --- | --- | --- |
| `window_name` | str | `"MirrorLab"` | Preview window title |
| `window_width` | int | `1280` | Preview window width |
| `window_height` | int | `720` | Preview window height |
| `fullscreen` | bool | `false` | Start fullscreen (`--fullscreen`) |
| `show_hud` | bool | `true` | Draw the HUD panels and badges (`--no-hud`, or `h`) |
| `show_landmarks` | bool | `true` | Draw the face mesh and hand skeletons (`--no-landmarks`, or `l`) |
| `show_fps` | bool | `true` | Draw the FPS / frame-time / inference-time panel |
| `reactions_dir` | str | `"assets/reactions"` | Directory searched for reaction images (`happy.png`, `sad.png`, …). Missing files are fine |
| `show_reactions` | bool | `false` | Show a reaction image per expression (`--reactions`, toggled at runtime with `i`) |

#### Output

| Key | Type | Default | Description |
| --- | --- | --- | --- |
| `output_dir` | str | `"captures"` | Directory for snapshots and recordings (`--output`) |
| `record_fps` | float | `30.0` | Frame rate written to recordings |
| `record_codec` | str | `"mp4v"` | FourCC for the video writer (`--record-codec`); falls back to `XVID`, then `MJPG` |
| `snapshot_format` | str | `"png"` | `png`, `jpg`, `jpeg` or `webp` |
| `jpeg_quality` | int | `95` | Quality for lossy snapshot formats |

#### Runtime

| Key | Type | Default | Description |
| --- | --- | --- | --- |
| `headless` | bool | `false` | No preview window; for servers, CI and batch runs (`--headless`) |
| `max_frames` | int | `0` | Stop after N frames; `0` = unlimited (`--frames`) |
| `stats_csv` | str | `""` | Append per-frame statistics to this CSV; empty = disabled (`--stats-csv`) |
| `log_level` | str | `"INFO"` | Logging level. `--verbose` / `-v` overrides it for one run |
| `theme` | str | `"aurora"` | HUD palette: `aurora`, `magma`, `mono` or `candy` (`--theme`, or `t` at runtime) |

### Filters

54 filters in six categories. Pass one with `--filter`, or chain them with `+`:
`--filter cartoon+vignette+glitch`. The CLI token is the name in the first column.

`cost` is a rough guide — `cheap` is under 2 ms at 640×480, `medium` up to ~20 ms, `heavy` above that. Measured numbers are in [Performance](#performance).

<details>
<summary><b>🎛️ Basic — 9 filters</b></summary>

| Name | Emoji | Description |
| --- | --- | --- |
| `original` | 🎥 | The untouched camera feed |
| `grayscale` | ⚫ | Luminance-only rendering with a slight contrast lift |
| `sepia` | 🟤 | Warm antique tone via a fixed colour matrix |
| `invert` | 🔳 | Photographic negative |
| `posterize` | 🧱 | Quantises each channel to a few flat levels — a screen-print look |
| `sharpen` | 🔪 | Unsharp mask that lifts local detail without halos |
| `blur` | 💧 | Gaussian dream blur |
| `vignette` | ⭕ | Darkened corners that pull the eye to the centre of frame |
| `emboss` | 🗿 | Bas-relief edge shading that makes the image look carved |

</details>

<details>
<summary><b>🌈 Colour — 6 filters</b></summary>

| Name | Emoji | Description |
| --- | --- | --- |
| `warmth` | 🌅 | Warm, slightly lifted shadows — flattering on every skin tone |
| `saturation` | 🎨 | Punchy saturation boost in HSV space |
| `duotone` | 🎭 | Maps luminance onto a two-colour ramp |
| `cyberpunk` | 🌆 | Teal shadows, orange highlights and a neon bloom |
| `infrared` | 🩻 | Aerochrome-style false colour: foliage glows pink, skin goes porcelain |
| `lomo` | 📷 | Saturated toy-camera look with crushed blacks and heavy vignette |

</details>

<details>
<summary><b>🖌️ Artistic — 13 filters</b></summary>

| Name | Emoji | Description |
| --- | --- | --- |
| `cartoon` | 🖍️ | Flat colour regions plus bold ink outlines — the classic cel look |
| `sketch` | ✏️ | Dodge-blend graphite drawing with an optional colour wash |
| `ink` | 🖊️ | High-contrast line art, like a brush pen drawing |
| `oil` | 🖼️ | Histogram-based brush strokes: each pixel takes the dominant colour of its neighbourhood |
| `watercolor` | 🎐 | Soft washes with paper-like edges and lifted highlights |
| `halftone` | 🔵 | Newspaper dot screen, generated with a rotated dot lattice |
| `ascii` | 🔤 | Renders the frame as text glyphs — yes, in real time |
| `pixelate` | 🟦 | Chunky 8-bit mosaic, with an animated block size option |
| `glass` | 🪟 | Colour cells separated by dark lead lines |
| `pointillism` | 🔴 | Seurat-style dots of pure colour that blend in your eye |
| `kaleidoscope` | 🔮 | Mirrors the frame into N rotating wedges — pure wallpaper material |
| `fisheye` | 🐟 | Barrel distortion straight out of a skate video |
| `comic` | 💥 | Ben-Day dots, halftone gradients and heavy ink — a printed page |

</details>

<details>
<summary><b>✨ Stylised — 9 filters</b></summary>

| Name | Emoji | Description |
| --- | --- | --- |
| `neon` | 💡 | Edges only, blooming in electric colour over black |
| `thermal` | 🌡️ | False-colour heat map driven by inverted luminance |
| `night_vision` | 🌙 | Gen-II image intensifier: green phosphor, gain noise and a soft bloom |
| `xray` | 🦴 | Inverted radiograph with bone-bright edges |
| `hologram` | 🔷 | Cyan wireframe projection with scanline flicker and a glitch bar |
| `dream` | ☁️ | Soft-focus bloom with lifted blacks and pastel colour |
| `orton` | 🌤️ | Landscape photographer's glow: blurred copy at 50 % screen |
| `solarize` | 🔆 | Sabattier effect: tones past the midpoint invert |
| `anaglyph` | 🕶️ | Red/cyan stereo split — grab some cardboard glasses |

</details>

<details>
<summary><b>📺 Glitch &amp; retro — 9 filters</b></summary>

| Name | Emoji | Description |
| --- | --- | --- |
| `glitch` | ⚡ | Databend-style block displacement, RGB shear and dropout noise |
| `chromatic` | 🔴 | Lens-style radial colour fringing, strongest at the edges |
| `vhs` | 📼 | Tracking noise, colour bleed, tape wobble and a timecode stamp |
| `crt` | 🖥️ | Aperture-grille subpixels, scanlines, barrel glass and a rolling bar |
| `datamosh` | 🧬 | Motion vectors smear the previous frame's pixels — broken P-frames |
| `scanlines` | 〰️ | Subtle interlacing plus a light horizontal drift |
| `trails` | 👻 | Feedback delay that leaves ghosts of everything that moves |
| `matrix` | 🟩 | Falling katakana columns composited over a green-tinted feed |
| `slitscan` | 🌌 | Each frame contributes one column — time becomes space |

</details>

<details>
<summary><b>🛠️ Utility — 8 filters</b></summary>

| Name | Emoji | Description |
| --- | --- | --- |
| `bg_blur` | 🌀 | Portrait-mode separation. Needs `--segment` to build the person mask |
| `bg_replace` | 🏞️ | Swaps the background for a gradient or a solid colour. Needs `--segment` |
| `privacy` | 🕵️ | Blurs the background so only you are readable — safe screen sharing |
| `face_crop` | 🙂 | Keeps your face centred and correctly sized in frame |
| `skin_smooth` | 🧖 | Frequency-separation retouching: softens texture, keeps detail |
| `mirror` | 🪞 | Mirrors the left half onto the right — instant symmetry |
| `zoom` | 🔍 | Digital zoom with a smooth breathing motion |
| `grid` | 📐 | Composition guides for framing a shot |

</details>

Every filter's algorithm — the actual OpenCV calls and formulas — is documented in
[docs/FILTERS.md](docs/FILTERS.md).

### Presets

A preset is a tuned filter chain behind one name. `[` and `]` cycle them at runtime, and
`swipe_up` / `swipe_down` do the same by gesture.

| Preset | Chain | Look |
| --- | --- | --- |
| `cinema` | `warmth+vignette+sharpen` | Warm highlights, soft corners, crisp detail |
| `anime` | `cartoon+saturation` | Flat cel colours with a vivid palette |
| `noir` | `grayscale+vignette+sharpen` | High-contrast monochrome with a heavy vignette |
| `retro80s` | `cyberpunk+chromatic+scanlines` | Neon grade, colour fringing and CRT lines |
| `broken` | `glitch+trails` | Databend blocks with echo trails |
| `toon` | `comic+halftone` | Ben-Day dots and heavy ink |
| `ghost` | `xray+glitch` | Radiograph look with signal dropouts |
| `studio` | `skin_smooth+warmth+bg_blur` | Retouched skin, warm light, blurred background (needs `--segment`) |
| `paper` | `sketch+saturation` | Graphite linework with a colour wash |
| `vhs` | `vhs+scanlines` | Tape wobble, tracking noise and scanlines |

```bash
mirrorlab run --preset noir
mirrorlab run --preset studio --segment
mirrorlab filters --presets
```

### AR effects

15 effects, passed with `--effect` (repeatable): `mirrorlab run --effect sunglasses --effect fire`.
Face effects are anchored to the eye line, so they scale with the inter-ocular distance and
rotate with head roll. Everything is drawn procedurally with OpenCV primitives — no PNG
assets, no binary artwork in the repository.

**Face effects (11)**

| Name | Emoji | Description |
| --- | --- | --- |
| `sunglasses` | 🕶️ | Wayfarers locked to the eye line — tilt your head and they follow |
| `laser_eyes` | 🔴 | Twin beams from your irises, with an animated flicker |
| `dog` | 🐶 | Flappy ears, a boopable nose and a tongue that tracks your jaw |
| `crown` | 👑 | A gold crown, because you are the main character |
| `halo` | 😇 | A floating ring of light that bobs above your head |
| `mustache` | 🥸 | A handlebar mustache anchored to your upper lip |
| `blush` | 😊 | Soft rosy cheeks that intensify when you smile |
| `visor` | 🤖 | A scanning HUD bar across your eyes, with a live readout |
| `mask` | 😷 | A surgical mask fitted to your face oval |
| `big_eyes` | 👀 | Local lens warp that enlarges both eyes — anime mode |
| `googly` | 🙃 | Two wobbling paper eyes stuck over yours |

**Hand effects (4)**

| Name | Emoji | Description |
| --- | --- | --- |
| `trails` | 🌈 | Glowing ribbons that follow your fingertips and fade out |
| `fire` | 🔥 | Flames rising off every fingertip, brighter when you spread your hand |
| `sparkles` | ✨ | A four-point star twinkles at each fingertip |
| `skeleton` | 🦾 | Draws the 21-point skeleton with joint dots and a bone glow |

Two of them react to what your face is doing: `dog` grows its tongue with `jawOpen`, and
`blush` intensifies with `mouthSmile`. Effects that react to expressions feel alive; static
stickers do not.

---

## Keyboard and gesture shortcuts

### Keyboard

| Key | Action |
| --- | --- |
| `q` / `Q` | Quit |
| `s` | Save a snapshot of exactly what you see |
| `r` | Start/stop recording (MP4 + GIF) |
| `1`–`9` | Jump to the Nth filter (alphabetical) |
| `n` / `p` | Next / previous filter |
| `]` / `[` | Next / previous preset |
| `f` | Freeze the frame |
| `h` | Toggle the HUD |
| `l` | Toggle landmarks (face mesh and hand skeletons) |
| `m` | Toggle mirror mode |
| `e` / `Esc` | Toggle AR effects |
| `d` | Toggle air-draw |
| `b` | Before/after comparison strip |
| `t` | Cycle the HUD theme |
| `c` | Clear the air-draw canvas |
| `x` | Reset all temporal state (smoothing, votes, counters) |

### Gestures

Gestures are detected, shown in the HUD, and — when `gesture_control` is on — bound to
actions. **A gesture that fires an action must be held for ~0.6 s,** and the wait is drawn as
a filling ring around your hand, labelled with the pending action. That ring is what makes
gesture control feel intentional instead of twitchy: you can see the app has recognised you,
see how long is left, and see the moment it fires. A refractory period and a release
requirement mean one thumbs-up is one snapshot, not a burst.

| Gesture | Name | Action |
| --- | --- | --- |
| 🖐️ | `open_palm` | Toggle landmarks |
| ✊ | `fist` | Freeze the frame |
| ☝️ | `pointing` | Toggle air-draw |
| ✌️ | `peace` | Next filter |
| 3️⃣ | `three` | Previous filter |
| 4️⃣ | `four` | Toggle AR effects |
| 👍 | `thumbs_up` | Save a snapshot |
| 👎 | `thumbs_down` | Delete the last capture |
| 👌 | `ok` | Toggle the HUD |
| 🤏 | `pinch` | Precision input (eraser while air-drawing) |
| 🤘 | `rock` | Toggle the `glitch` filter |
| 🤙 | `call_me` | Toggle mirror mode |
| 🤟 | `ily` | Jump to the `love` filter |
| 🖖 | `spock` | Cycle the HUD theme |
| 🔫 | `gun` | Toggle the HUD |
| 1️⃣ | `one` | Jump to `original` |
| 6️⃣ | `six` | Jump to `cartoon` |
| 7️⃣ | `seven` | Jump to `sketch` |
| 8️⃣ | `eight` | Jump to `thermal` |
| ➡️ | `swipe_right` | Next filter |
| ⬅️ | `swipe_left` | Previous filter |
| ⬆️ | `swipe_up` | Next preset |
| ⬇️ | `swipe_down` | Previous preset |
| 👋 | `wave` | Save a snapshot |
| 🔄 | `circle` | Cycle the HUD theme |

Also recognised but not bound to an action: `claw` 🫳 and `pinch_zoom` 🔍 (two-hand zoom is
a [roadmap](ROADMAP.md) item). Every gesture above is defined by a readable geometric rule —
the exact matcher and its thresholds are in [docs/GESTURES.md](docs/GESTURES.md).

Run `mirrorlab gestures` for the live table, and `--no-gesture-control` to detect gestures
without letting them act.

---

## How it works

```
   camera.py                 detectors/                  perception
 ┌────────────┐          ┌──────────────────┐      ┌───────────────────────┐
 │ capture    │  frame   │ backend ladder   │      │ ExpressionClassifier  │
 │ thread     │ ───────► │  tasks → solut.  │ ───► │  52 blendshapes → 18  │
 │ (drop-     │          │  → yunet → haar  │      │ GestureTracker        │
 │  latest    │          │  → none          │      │  21 landmarks → poses │
 │  slot)     │          │ One-Euro smoother│      │ classify_hands()      │
 └────────────┘          └──────────────────┘      └───────────┬───────────┘
                                                               │ frame + faces + hands
                                                               ▼
   render/                  effects/                   filters/
 ┌────────────┐          ┌──────────────┐          ┌───────────────────────┐
 │ Hud        │ ◄─────── │ 15 AR        │ ◄─────── │ FilterChain           │
 │ Transition │          │ overlays     │          │  cartoon+vignette+…   │
 │ imshow     │          │ air-draw     │          │  54 registered stages │
 └────────────┘          └──────────────┘          └───────────────────────┘
        │
        └──► recording.py (MP4 + GIF), snapshots, stats CSV
```

The per-frame order is: **capture thread → drop-latest frame slot → MediaPipe Tasks detection → One-Euro landmark smoothing → expression and gesture classification with EMA and majority vote → filter chain → AR overlays → HUD → `imshow` → recorder → key handling.**

Two design decisions are worth explaining, because they are what make the results stable.

**Why blendshapes beat landmark ratios for expressions.** A ratio between two landmarks is a proxy for a muscle: it moves when the muscle moves, but also when you turn your head, change distance, or when the detector jitters by a pixel. The classic smile detector (`mouth_width / face_width > 0.42`) fires on a wide face, a yawn, and a bad frame. A blendshape is the muscle activation itself — MediaPipe regresses 52 ARKit-style coefficients from the face mesh, so `mouthSmileLeft` rising *is* the zygomaticus major contracting. Classification becomes readable arithmetic on named channels (`happy = clamp(0.85·mouthSmile + 0.15·mouthDimple)`) instead of a tuning problem, and it stops caring how far away you are sitting. The trade-off is honest: blendshapes need the Tasks backend, so there is a documented geometric fallback and `ExpressionResult.method` always tells you which path produced the answer.

**Why gesture distances are normalised by hand scale.** A pose that scores 0.9 at 40 cm must score 0.9 at 1.5 m. Every gesture measurement is divided by `hand_scale()` — the mean wrist-to-knuckle distance of the four long fingers, which is invariant to rotation and stable when fingers are folded. Without it, every threshold would need a distance calibration and gesture control would only work if you sat still. This single normalisation is the reason a rule-based classifier is viable at all.

Landmarks are additionally smoothed by a **One-Euro filter** per point per coordinate (Casiez et al., CHI 2012): the cutoff frequency rises with the estimated velocity, so a stationary face stops vibrating while a fast fingertip stays responsive. Expression scores get an EMA, and a final 7-frame majority vote (4 agreeing frames) decides the reported label, so a blink cannot take over the HUD.

Full details: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Performance

CPU only, no GPU, no CUDA. All numbers below are measured on an Apple M5 (arm64), Python 3.11.16, OpenCV 4.11.0, MediaPipe 0.10.21, at 640×480 — reproduce them with the commands given.

**Filter stage** (`mirrorlab benchmark --all --frames 20 --width 640 --height 480`):

| Metric | Measured |
| --- | --- |
| Median filter cost | **1.41 ms** (≈709 fps of headroom for the filter stage) |
| Slowest filter | `pointillism` at **17.06 ms** |
| Next slowest | `watercolor` 15.75 ms, `oil` 14.39 ms, `comic` 13.45 ms, `cyberpunk` 10.68 ms |
| All 54 filters | **under 33 ms** — every one fits inside a 30 fps budget, most with room to spare |
| Fastest filters | `original` 0.01 ms, `invert` 0.03 ms, `grid` 0.04 ms, `grayscale` 0.10 ms |

**Detection stage**, measured by running `PerceptionEngine.process()` over 40 frames after the two-frame warm-up:

| Scenario | Median | p95 |
| --- | --- | --- |
| Face + hand models running, nothing in frame | **11.9 ms** | 18.3 ms |
| Face + hand models with two hands detected and classified | **21.7 ms** | 42.7 ms |

Face and hand inference in the same frame share one CPU budget, which is why the `--no-hands` flag is the single biggest speed lever available.

About the first frame: MediaPipe lazily allocates its graphs and XNNPACK delegates, so the very first user-visible frame can take up to ~300 ms and the preview visibly hitches. MirrorLab runs a two-frame warm-up before the first `imshow` (`PerceptionEngine.warm_up`), which absorbs that cost into start-up.

### Tuning advice

```bash
mirrorlab run --camera-width 640 --camera-height 480   # biggest win: detection cost scales with area
mirrorlab run --no-hands                               # drop the most expensive model
mirrorlab run --no-face                                # filters only
mirrorlab run --filter grayscale                       # cheapest filter
mirrorlab benchmark --filter oil --frames 50           # measure before you ship a chain
```

- **Do not chain three `medium` filters.** `cost` reports the worst stage, but the *time* is the sum: three 10 ms filters is 30 ms of a 33 ms budget.
- **Leave `--segment` off** unless you are using `bg_blur`, `bg_replace` or `privacy`. It runs an extra model.
- **Lower `smoothing_min_cutoff`** if landmarks jitter; it does not slow anything down.
- **Set `MIRRORLAB_SMOOTHING_MIN_CUTOFF=1.0`** instead of editing code — see [Configuration](#configuration).

---

## Troubleshooting

Run these two commands first; between them they answer most questions:

```bash
mirrorlab doctor           # backends, models, capability probes
mirrorlab cameras          # which indices and capture backends deliver frames
```

### The camera will not open

<details>
<summary><b>Per-OS fixes</b></summary>

- **macOS:** System Settings → Privacy & Security → Camera → enable the *terminal you launched from*. The permission is per host app, not per Python. The first run triggers the prompt; accept it and retry. A Continuity Camera iPhone may hold index 0 — try `--camera 1`.
- **Windows:** Settings → Privacy → Camera → let desktop apps use the camera. Then try `--backend msmf`, and if that fails `--backend dshow`.
- **Linux:** `sudo usermod -aG video "$USER"` and **log back in** (group membership is read at login). Check `ls -l /dev/video*`. In Docker/WSL2, pass the device through.

Also: close other apps that hold the camera (Zoom, Teams, OBS, Photo Booth). `open_camera` raises `CameraError` with the platform checklist appended, so the terminal message already contains these steps. `mirrorlab cameras --max-index 5` tells you whether the problem is the index or the backend.

</details>

### It crashes on macOS with `DrishtiMetalHelper ... service is unavailable`

That is the MediaPipe 1.0.1 Metal bug. It is a native abort, not a catchable Python exception. Install the tested combination:

```bash
pip install "mediapipe>=0.10.9,<0.11" "numpy<2" "opencv-python<5"
mirrorlab doctor
```

`mirrorlab doctor` prints exactly this line whenever no face engine can start. Full explanation in [docs/CROSS_PLATFORM.md](docs/CROSS_PLATFORM.md#the-dependency-pins).

### Low FPS

See [Tuning advice](#tuning-advice). In order of impact: lower the capture resolution, `--no-hands`, avoid `--segment`, and pick a cheaper filter. The HUD's performance panel shows FPS, frame time and inference time separately, so you can tell whether detection or filtering is the bottleneck.

### Hands are not detected

Hand tracking **requires MediaPipe** — there is no OpenCV hand-landmark model, so without it the hand backend is `none` and gestures are disabled *by design* while the app keeps running. Check `mirrorlab doctor`. If the backend is fine:

- Get your **whole hand** in frame, wrist to fingertips. MediaPipe needs the palm base.
- Light your hand from the front; backlighting turns it into a silhouette.
- Do not move fast — motion blur destroys landmark quality.
- Use a real camera index, not a virtual one capped at 320×240.

### A model download failed

The app keeps working with reduced features and logs a warning; it does not crash. To fix it:

```bash
mirrorlab models --status             # what is cached, and where
mirrorlab models --download           # fetch everything missing
mirrorlab doctor --download           # same, plus a full environment report
```

If you are behind a proxy or offline, download the file by hand into the cache directory shown by `mirrorlab models --status` and re-run — MirrorLab works fully offline once a model is present. `MIRRORLAB_MODELS=/some/path` overrides the cache location, which is the standard air-gapped setup. Use `--no-download` to guarantee that nothing is ever fetched.

### `AttributeError: module 'mediapipe' has no attribute 'solutions'`

You have MediaPipe ≥ 1.0. MirrorLab handles this — the Solutions backend is one rung of the ladder, not a requirement — so this error means third-party code (or a pre-2025 tutorial) is calling `mp.solutions` directly. MirrorLab's own primary backend is the Tasks API and does not use that namespace. If you want the legacy rung available, use the [known-good pin](#known-good-install).

### `--air-draw` and `--reactions`

Both are wired end to end.

`--air-draw` (or `--air-draw false` to start off) creates the drawing canvas before the
first frame, so the flag alone is enough — you no longer need to press `d` as well. Point
with your index finger to draw, pinch to erase, `c` to clear.

`--reactions` looks up an image per expression in `--reactions-dir`
(`assets/reactions` by default) and draws it as a picture-in-picture. Lookup is forgiving:
`happy` also matches `smile.png`, `kiss` also matches `love.png`, and a missing directory
or missing file simply shows nothing. Six of the eighteen expressions ship with an image;
drop your own PNGs in to fill the rest. Press `i` to toggle it at runtime.


### `doctor` says `display: headless (no window)`

That line reports whether a GUI window *can* be opened, not whether your machine has a
display. It is correct when you run from a shell with no `DISPLAY`/`WAYLAND_DISPLAY`
(SSH, Docker, a CI runner, some IDE terminals) — MirrorLab then runs headless by design.
On a normal desktop session it reads `available`. Force either behaviour with `--headless`
or by unsetting `headless` in your config.

If the capability counters ever print `0`, that is a bug worth reporting — they are read
from the live registries.

### The window will not close on macOS

Cocoa needs a few event-loop iterations after `destroyAllWindows()`; MirrorLab pumps them on exit, so the window may linger for a fraction of a second and then go. If it stays on screen and the process looks hung, you are calling `destroyAllWindows()` yourself before `run()` returns.

More answers — privacy, commercial use, virtual cameras, custom gestures, Docker, WSL2 — in **[docs/FAQ.md](docs/FAQ.md)**.

---

## Project structure

```
mirrorlab/
├── src/mirrorlab/
│   ├── __init__.py              # lazy package facade (PEP 562), keeps import cheap
│   ├── __main__.py              # `python -m mirrorlab` entry point
│   ├── version.py               # __version_info__, CODENAME
│   ├── config.py                # frozen Config dataclass, DEFAULTS, 4-layer resolution
│   ├── camera.py                # per-OS backends, threaded drop-latest capture, synthetic source
│   ├── app.py                   # the frame loop: perception → filters → effects → HUD
│   ├── cli.py                   # twelve subcommands, argparse, --json output
│   ├── actions.py               # gesture→action bindings, dwell state machine, hold ring
│   ├── airdraw.py               # persistent drawing canvas driven by the index fingertip
│   ├── recording.py             # threaded MP4 writer, GIF export, snapshots
│   ├── expressions.py           # 18 expressions, blendshape scorers, geometric fallback
│   ├── gestures.py              # HandPose, 22 gestures, declarative matchers, motion tracker
│   ├── detectors/
│   │   ├── base.py              # FaceObservation, HandObservation, FrameAnalysis, index tables
│   │   ├── backends.py          # the five-rung ladder: tasks → solutions → yunet → haar → none
│   │   ├── engine.py            # PerceptionEngine: one call per frame, everything derived
│   │   ├── face.py              # FaceDetector: backend + One-Euro landmark smoothing
│   │   ├── hands.py             # HandDetector: faster cutoff, handedness-stable tracks
│   │   ├── models.py            # MODELS table, cache paths, atomic verified downloads
│   │   └── segmentation.py      # SelfieSegmenter + mask refinement (largest blob, feather)
│   ├── filters/
│   │   ├── base.py              # Filter, FilterContext, FilterChain, registry, CATEGORIES
│   │   ├── classic.py           # basic + colour filters
│   │   ├── artistic.py          # cartoon, sketch, oil, halftone, ascii…
│   │   ├── stylize.py           # neon, thermal, x-ray, hologram, dream…
│   │   ├── glitch.py            # glitch, vhs, crt, datamosh, trails, slitscan…
│   │   ├── utility.py           # background blur/replace, privacy, face crop, skin smooth
│   │   └── __init__.py          # PRESETS, filter_names(), filters_by_category()
│   ├── effects/
│   │   ├── face.py              # 11 face effects + 4 hand effects, drawn procedurally
│   │   └── __init__.py          # effect registry re-exports
│   ├── render/
│   │   ├── hud.py               # Hud, HudState, panels, badges, skeletons, reticle
│   │   └── composition.py       # blend, letterbox, side-by-side, tile grid, Transition
│   └── utils/
│       ├── geometry.py          # distance, angle, hand_scale, finger_curl, clamp…
│       ├── smoothing.py         # OneEuroFilter, EmaFilter, SlidingWindow, LandmarkSmoother
│       ├── timing.py            # FpsMeter with per-stage profiling, Stopwatch
│       ├── colors.py            # Palette and the four HUD themes
│       └── logging.py           # get_logger / setup_logging
├── docs/                        # ARCHITECTURE, FILTERS, GESTURES, EXPRESSIONS, CROSS_PLATFORM, FAQ
├── tests/                       # pure-logic tests + image fixtures (no camera in CI)
├── web/                         # Vite + React browser demo (TypeScript, WebAssembly vision)
├── legacy/                      # the 1.x single-file prototype, kept for reference only
├── assets/reactions/            # reaction images (present, not yet rendered — see the roadmap)
├── pyproject.toml               # packaging, extras, console script, tool config
├── Makefile                     # make install / test / lint / check / run / demo / benchmark
├── CITATION.cff                 # how to cite this software
└── LICENSE                      # MIT
```

---

## Roadmap

**Shipped in 2.0**

- [x] Modular package replacing the single-file prototype (now in `legacy/`)
- [x] MediaPipe **Tasks** migration: 478 landmarks, 52 blendshapes, facial transformation matrix
- [x] Five-rung detector fallback ladder — the app degrades instead of crashing
- [x] 54 chainable filters across six categories, plus 10 curated presets
- [x] Hand tracking with 21 static gestures and 6 dynamic ones, all geometrically explainable
- [x] Gesture control with a dwell state machine and an on-screen hold-to-confirm ring
- [x] Cross-platform capture: AVFoundation, DSHOW, MSMF, V4L2, video files, synthetic source
- [x] Browser demo with the classifier logic ported to TypeScript

**Next**

- [ ] **PyPI release** so `pip install mirrorlab` works
- [ ] **Homebrew formula** for macOS
- [ ] **Virtual camera output** for Zoom/OBS/Meet — `pyvirtualcam` is GPLv2, so it stays an optional extra
- [ ] **Head-pose parallax** using the 4×4 transformation matrix the API already returns
- [ ] **3D mask rendering** with correct occlusion, same matrix plus a hair mask
- [ ] **Gaze tracking** from the currently-unused `eyeLook*` blendshape channels
- [ ] **Rock–Paper–Scissors game mode** — the three poses already classify
- [ ] **Plugin API** for third-party filters, with a designed trust model
- [ ] **Preset sharing** as a portable file and a shareable link
- [ ] **MLP gesture trainer** for hands the geometric rules serve badly

The full milestone list, plus what is explicitly *not* planned and why, is in [ROADMAP.md](ROADMAP.md).

---

## Contributing

Three things worth knowing before you open a PR: run `make check` (black, ruff, mypy,
pytest) before pushing; CI has no camera and no network, so pure logic must be testable
without hardware; and commit messages follow [Conventional Commits](https://www.conventionalcommits.org/).
The easiest first contribution is a new filter (~30 lines) or a new gesture (~10 lines) —
the registries do all the wiring, so you never touch the CLI.

Read [CONTRIBUTING.md](CONTRIBUTING.md) for setup, style, the PR checklist and how to add a
filter, gesture or effect. Issues labelled **`good first issue`** are scoped to be
self-contained. Everyone participating agrees to the
[Code of Conduct](CODE_OF_CONDUCT.md).

---

## Model licences and credits

MirrorLab's own code is MIT. The models are not — they are downloaded at runtime, never
redistributed, and each is governed by its own model card.

| Component | Licence | Notes |
| --- | --- | --- |
| [MediaPipe](https://ai.google.dev/edge/mediapipe/solutions/guide) | Apache-2.0 | Tasks API: FaceLandmarker, HandLandmarker, ImageSegmenter |
| [OpenCV](https://opencv.org/) (`opencv-python`) | Apache-2.0 | Capture, every image operation, the HUD, video encoding |
| [NumPy](https://numpy.org/) | BSD-3-Clause | Every array in the pipeline |
| [rich](https://github.com/Textualize/rich) | MIT | Optional: nicer CLI output |
| [PyYAML](https://pyyaml.org/) | MIT | Optional: `.yaml` config files |
| `face_landmarker.task` | [model card](https://ai.google.dev/edge/mediapipe/solutions/vision/face_landmarker) | 478 landmarks, 52 blendshapes, 4×4 matrix — 3.7 MB, downloaded |
| `hand_landmarker.task` | [model card](https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker) | 21 landmarks per hand + handedness — 7.8 MB, downloaded |
| `selfie_segmenter.tflite` | [model card](https://ai.google.dev/edge/mediapipe/solutions/vision/image_segmenter) | Person mask for background effects — 0.25 MB, downloaded |
| `face_detection_yunet_2023mar.onnx` | [OpenCV Model Zoo](https://github.com/opencv/opencv_zoo) | 5-landmark fallback detector — 0.23 MB, downloaded |

Everything else, including `gesture_recognizer.task`, `pose_landmarker_lite.task` and
`selfie_multiclass_256x256.tflite`, is optional and off the default path.

Two consequences worth stating plainly: **the model weights are downloaded at runtime and
are not redistributed by this project**, and their terms are their publishers' — check the
model card before shipping a model inside your own product. The full inventory, including
transitive dependencies and the GPL boundary around virtual-camera support, is in
[THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).

---

## Citation

If you use MirrorLab in academic work, cite it via [CITATION.cff](CITATION.cff) or with:

```bibtex
@software{mirrorlab2026,
  title        = {MirrorLab: real-time webcam filters, facial expressions and hand
                  gestures on the CPU},
  author       = {Trinidad Arguello, Huascar Ignacio D and {TrinaxCode}},
  year         = {2026},
  version      = {2.0.0},
  license      = {MIT},
  url          = {https://github.com/TrinaxCode/mirrorlab},
  repository   = {https://github.com/TrinaxCode/mirrorlab},
  keywords     = {computer-vision, webcam, mediapipe, opencv, hand-tracking,
                  gesture-recognition, facial-expression-recognition, blendshapes}
}
```

## License

MIT — © 2026 TrinaxCode (Huascar Ignacio D Trinidad Arguello). See [LICENSE](LICENSE). Use it
at work, ship it inside a product, sell a service built on it; keep the copyright notice and
the licence text. The third-party terms above still apply to the third-party parts.

---

If MirrorLab is useful to you, a ⭐ on [GitHub](https://github.com/TrinaxCode/mirrorlab) helps other people find it.
