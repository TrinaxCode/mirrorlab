# MirrorLab filters

> [English](FILTERS.md) · [README](../README.md) · [Español](../README.es.md) · [Architecture](ARCHITECTURE.md) · [Gestures](GESTURES.md) · [Expressions](EXPRESSIONS.md) · [Cross-platform](CROSS_PLATFORM.md) · [FAQ](FAQ.md)

54 filters, all pure `frame → frame` stages that run on the CPU. This document lists
every one, grouped by the category the registry assigns, with the technique the code
actually uses.

List them from the terminal:

```bash
mirrorlab filters                      # grouped by category
mirrorlab filters --category artistic  # one category
mirrorlab filters --json               # machine-readable catalog
mirrorlab filters --presets            # the curated multi-filter looks
```

---

## Contents

- [How filters work](#how-filters-work)
- [Cost labels](#cost-labels)
- [Basic (9)](#basic-9)
- [Colour (6)](#colour-6)
- [Artistic (13)](#artistic-13)
- [Stylised (9)](#stylised-9)
- [Glitch and retro (9)](#glitch-and-retro-9)
- [Utility (8)](#utility-8)
- [Chaining filters](#chaining-filters)
- [Presets](#presets)
- [Writing a new filter](#writing-a-new-filter)

---

## How filters work

A filter subclasses `mirrorlab.filters.base.Filter`, declares metadata as class
attributes, and implements `apply(frame, ctx)`:

```python
class Filter:
    name: str = "filter"          # the CLI token
    label: str = "Filter"         # HUD label (English)
    label_es: str = "Filtro"      # HUD label (Spanish)
    emoji: str = "🎨"
    category: str = "basic"       # one of CATEGORIES
    description: str = ""
    description_es: str = ""
    cost: str = "cheap"           # cheap | medium | heavy
    needs_mask: bool = False      # True when it consumes ctx.state["person_mask"]

    def apply(self, frame: np.ndarray, ctx: FilterContext) -> np.ndarray:
        raise NotImplementedError

    def reset(self) -> None:
        self.state.clear()
```

`FilterContext` carries the per-frame information a filter may need:

| Field | Meaning |
| --- | --- |
| `frame_index` | monotonic frame counter |
| `time` | seconds since the session started |
| `delta` | seconds since the previous frame (`1/fps` in practice) |
| `width`, `height` | frame size in pixels (`aspect` is derived) |
| `state` | mutable scratch dict, shared between the frames of one filter instance |

`ctx.state["person_mask"]` is a float mask in `[0, 1]` where `1` means "person". It is
only present when segmentation is enabled (`--segment`). The app also publishes
`ctx.state["face_bbox"]` — `(x0, y0, x1, y1)` in pixels, padded by 15 % — which is what
`face_crop` consumes.

Registration is a side effect of import: each of the five filter modules calls
`register_filter(instance)` at module scope, and `filters/__init__.py` imports all five.
`get_filter(name)` normalises case, dashes and spaces, so `--filter skin-smooth`,
`--filter "Skin Smooth"` and `--filter skin_smooth` are the same filter. `build_filter`
raises `KeyError` with `difflib` close matches, which is why a typo prints
`Unknown filter 'caroon'. Did you mean: cartoon, cartoon, ...`.

## Cost labels

The `cost` attribute is a rough guide, and the benchmark agrees with it:

| Cost | Meaning | Measured at 640×480 |
| --- | --- | --- |
| `cheap` | one or two OpenCV calls; comfortably under 2 ms | 0.01 – 1.9 ms |
| `medium` | blur pyramids, remaps, per-pixel float maths | 0.03 – 17 ms |
| `heavy` | neighbourhood search, downscale + re-upscale | 14.4 ms (`oil`) |

Two caveats on that table. The `medium` range is wide because a mask-dependent filter
(`bg_replace`) returns early when no person mask is present, which is why it measures
0.03 ms — cost is a property of the algorithm, not of the benchmark's cheapest path. And
`FilterChain.cost` returns the **worst** cost of its stages, so `--filter oil+blur` reports
`heavy`, which is the number a user needs.

Reproduce the numbers on your own machine:

```bash
mirrorlab benchmark --all --frames 30 --width 640 --height 480
mirrorlab benchmark --filter oil --filter pointillism --json
```

---

## Basic (9)

Category emoji 🎛️. The filters every project needs, and the ones worth chaining.

| Name | Label | Emoji | Cost | Technique |
| --- | --- | --- | --- | --- |
| `original` | Original | 🎥 | cheap | Returns the frame unchanged — a pure passthrough with no copy, so `--filter original` costs nothing. |
| `grayscale` | Grayscale | ⚫ | cheap | `cv2.cvtColor(BGR2GRAY)` then `cv2.convertScaleAbs(alpha=1.08, beta=4)` for a slight contrast lift, expanded back to 3 channels. |
| `sepia` | Sepia | 🟤 | cheap | Float32 frame through `cv2.transform` with a fixed 3×3 BGR matrix (`[[0.131,0.534,0.272],[0.168,0.686,0.349],[0.189,0.769,0.393]]`), then clipped to `uint8`. |
| `invert` | Negative | 🔳 | cheap | `cv2.bitwise_not(frame)` — per-channel `255 − x`. |
| `posterize` | Posterize | 🧱 | cheap | A 256-entry `uint8` LUT built once from `levels=6`: `(arange(256)//step*step + step//2)`. `apply` is a single `cv2.LUT`. |
| `sharpen` | Sharpen | 🔪 | cheap | Unsharp mask: `cv2.addWeighted(frame, 1+amount, GaussianBlur(frame, (5,5), 0), -amount, 0)` with `amount=0.8`. |
| `blur` | Soft focus | 💧 | cheap | One `cv2.GaussianBlur(frame, (0,0), 4.0)`; sigma-driven, so the kernel scales with the frame. |
| `vignette` | Vignette | ⭕ | cheap | A radial mask cached per frame size: normalised distance from centre, `mask = clip(1 − 1.35·clip(d/0.78 − 0.35)¹·⁶, 0, 1)`, multiplied into the float frame. |
| `emboss` | Emboss | 🗿 | cheap | Grayscale through `cv2.filter2D` with the fixed 3×3 kernel `[[-2,-1,0],[-1,1,1],[0,1,2]]`, then `convertScaleAbs(beta=110)`. |

## Colour (6)

Category emoji 🌈. Grading and colour-science looks.

| Name | Label | Emoji | Cost | Technique |
| --- | --- | --- | --- | --- |
| `warmth` | Golden hour | 🌅 | cheap | Per-channel float gains `B×0.88, G×1.02, R×1.12` plus a constant lift `[-6, +4, +12]` — warm light with slightly raised shadows. |
| `saturation` | Vivid | 🎨 | cheap | `BGR2HSV` in float, `S ×= 1.45`, `V ×= 1.04`, back through `HSV2BGR`. |
| `duotone` | Duotone | 🎭 | cheap | A 256×1×3 LUT interpolating `shadow·(1−t) + light·t` between BGR `(120,40,20)` and `(90,220,250)`; applied to the grayscale frame with one `cv2.LUT`. |
| `cyberpunk` | Cyberpunk | 🌆 | medium | Per-pixel tint mix `shadow_tint·(1−lum) + light_tint·lum` in float, then an additive bloom: pixels above 0.72 are isolated, blurred with sigma 9 and added back at 0.55. |
| `infrared` | Infrared | 🩻 | medium | Aerochrome false colour by channel re-mixing: `B = 0.55b + 0.45g`, `G = 0.80g + 0.10r`, `R = 0.35r + 1.05g` — green bleeds into red so foliage goes pink — blended 0.9 with the source. |
| `lomo` | Lomo | 📷 | medium | HSV saturation `×1.75`, then `convertScaleAbs(alpha=1.15, beta=-18)` to crush blacks, multiplied by the radial vignette `clip(1.35 − 0.95·(x²+y²), 0, 1)`. |

## Artistic (13)

Category emoji 🖌️. The expensive, opinionated half of the catalogue.

| Name | Label | Emoji | Cost | Technique |
| --- | --- | --- | --- | --- |
| `cartoon` | Cartoon | 🖍️ | medium | Three `cv2.bilateralFilter` passes (9,75,75 then 2× 9,60,60), flat colour quantisation to 8 levels, and ink lines from `medianBlur(gray,5)` + `cv2.adaptiveThreshold(MEAN_C, BINARY, 9, 9)` eroded by a 5×5 kernel. |
| `sketch` | Pencil sketch | ✏️ | medium | Colour dodge — `cv2.divide(gray, 255 − GaussianBlur(bitwise_not(gray), sigma 12), scale=256)` — then `convertScaleAbs(1.05, 2)`. `color=True` multiplies a lightened `bilateralFilter(frame,9,90,90)` wash into the result. |
| `ink` | Ink | 🖊️ | medium | Difference of Gaussians: `absdiff(GaussianBlur(gray, 1.0), GaussianBlur(gray, 3.5))`, min-max normalised, inverted-thresholded at `0.55·255`, closed with a 2×2 kernel. |
| `oil` | Oil painting | 🖼️ | heavy | Hertzmann-style binning written from scratch: the frame is downscaled to 480 px, the grey level quantised into 10 bins, and ten `cv2.boxFilter` passes over a 7×7 window count each bin and sum its colour; `argmax` picks the winning bin and the mean colour is written back. Finished with `bilateralFilter(5,40,40)`. **Not** `cv2.oilPainting` — see the note below. |
| `watercolor` | Watercolor | 🎐 | medium | Downscale to 640 px, `cv2.edgePreservingFilter(RECURS_FILTER, sigma_s=60, sigma_r=0.42)` (falling back to `bilateralFilter(9,80,80)` if the build lacks it), blended 0.82 with paper white 245, then `adaptiveThreshold` edges re-applied with `bitwise_and`. |
| `halftone` | Halftone | 🔵 | medium | The grey frame is rotated 15° with `getRotationMatrix2D` + `warpAffine`, a rotated dot lattice is generated from `np.mgrid` modulo a 6 px cell with dot radius `sqrt(1 − value)` so dark areas grow bigger dots, and the field is rotated back with `invertAffineTransform`. |
| `ascii` | ASCII art | 🔤 | medium | The frame is resized to `width//10` columns (characters are ~2× taller), each cell maps to a glyph in `"@%#*+=-:. "` via `value*11//256`, and `cv2.putText` stamps them in the sampled colour on a black canvas. |
| `pixelate` | Pixelate | 🟦 | cheap | `cv2.resize` down to `(w//blocks, h//blocks)` with `INTER_AREA`, back up with `INTER_NEAREST`. `animate=True` breathes the block count as `blocks + 4·sin(time·1.5)`. |
| `glass` | Stained glass | 🪟 | medium | Posterise to a fixed step of 36 (`(frame//36)*36 + 18`), `medianBlur(5)`, then `cv2.Canny(…, 60, 140)` dilated by 3×3; the lead lines are `255 − edges` multiplied into the flat colour with `cv2.multiply(..., scale=1/255)`. |
| `pointillism` | Pointillism | 🔴 | medium | The frame is downsampled by 5, a fixed-seed `default_rng(7)` jitters each dot centre by ±0.35, and `cv2.circle(radius ≈ 0.62·dot)` paints each sampled colour on a canvas pre-filled with 245. |
| `kaleidoscope` | Kaleidoscope | 🔮 | medium | Analytic inverse polar mapping with `np.mgrid`: the angle is wrapped into one wedge and folded by `where(θ > wedge/2, wedge − θ, θ)`, then `cv2.remap(INTER_LINEAR, BORDER_REFLECT)`. Spin is driven by `ctx.time`. |
| `fisheye` | Fisheye | 🐟 | medium | Barrel distortion with a remap table cached per frame size: `factor = 1 + 0.35·(nx²+ny²)`, mapped with `cv2.remap(INTER_LINEAR, BORDER_REPLICATE)`. |
| `comic` | Comic book | 💥 | medium | Runs an internal `CartoonFilter(levels=5, edge_thickness=3)` and `HalftoneFilter(cell=4, angle=45)` and multiplies the two with `cv2.multiply(..., scale=1/255)` — heavy ink plus Ben-Day dots. |

**Engineering note — `oil` does not use contrib.** OpenCV's `cv2.oilPainting` lives in
`opencv-contrib-python`, and MirrorLab's own dependency list is deliberately just
`opencv-python`. The `oil` filter is therefore a from-scratch implementation of the same
histogram-binning algorithm (A. Hertzmann, *Painterly rendering with curved brush strokes*,
SIGGRAPH 1998) built on `cv2.boxFilter`.

Worth knowing: `mediapipe` 0.10.x declares `opencv-contrib-python` as one of its own
requirements, so a normal install usually *does* have `cv2.oilPainting` available. The
filter is written not to care either way — the implementation is identical with or without
contrib, which is why `oil` behaves the same in a minimal `opencv-python` install and in a
full MediaPipe one.

## Stylised (9)

Category emoji ✨. Looks built around edges, glow and false colour.

| Name | Label | Emoji | Cost | Technique |
| --- | --- | --- | --- | --- |
| `neon` | Neon glow | 💡 | medium | `cv2.Canny(…, 40, 120)` masks the frame's own hue (rotated by `time·12 + hue_shift`, forced to S=V=255), which is blurred with sigma 7 and added to the sharp edges at 1.6× over black. |
| `thermal` | Thermal | 🌡️ | cheap | Grey → `GaussianBlur(7,7)` → `bitwise_not` → `equalizeHist` → `cv2.applyColorMap(COLORMAP_INFERNO)`, blended 0.92 over the source. Palette and inversion are constructor arguments. |
| `night_vision` | Night vision | 🌙 | medium | Grey normalised to full range and gained 1.35×, Gaussian sensor noise from a per-frame seed, a sigma-6 bloom, and synthetic channels (G gets the most, B and R barely any) multiplied by a radial vignette. |
| `xray` | X-ray | 🦴 | medium | `sobel_magnitude` edges mixed with the grey image at `0.55/0.75`, inverted, mapped through `cv2.applyColorMap(COLORMAP_BONE)`, blue channel lifted 12 %. |
| `hologram` | Hologram | 🔷 | medium | `cv2.Canny(…, 30, 90)` drawn as cyan (`B=edges, G=0.85·edges, R=0.15·edges`), a sigma-5 glow added at 0.9, scanlines every 3rd row at 0.72, and a 24-row band `np.roll`-ed horizontally for 3 frames out of every 47. |
| `dream` | Dream | ☁️ | medium | Orton-style screen blend `255 − (255−f)·(255−blur)/255` with sigma 9, mixed 0.42/0.58 with the source, lifted toward 236, then `convertScaleAbs(0.94, 14)`. |
| `orton` | Orton | 🌤️ | medium | `convertScaleAbs(frame, 1.0, beta=18)` brightened, blurred with sigma 14, and averaged 50/50 with the source — the classic landscape-photography glow. |
| `solarize` | Solarize | 🔆 | cheap | The Sabattier effect as a 256-entry LUT: `255 − i if i > 128 else i`, applied with `cv2.LUT`. |
| `anaglyph` | 3D anaglyph | 🕶️ | cheap | Two `np.roll` shifts of ±6 px; the output takes blue from the left-shifted copy and green/red from the right-shifted copy. Works with red/cyan cardboard glasses. |

## Glitch and retro (9)

Category emoji 📺. Damage as an aesthetic. Four of these keep temporal state.

| Name | Label | Emoji | Cost | Technique |
| --- | --- | --- | --- | --- |
| `glitch` | Glitch | ⚡ | medium | A per-frame deterministic RNG (`seed + frame_index·2654435761 mod 2³²`) drives four passes: random horizontal bands `np.roll`-ed by a Gaussian offset, an RGB channel shear (B `+shear`, R `−shear`), rectangles copied from elsewhere in the frame (databend), and white speckle. |
| `chromatic` | Chromatic aberration | 🔴 | cheap | Each channel is remapped radially with its own scale, `1 + direction·amount·0.004` for direction `+1 / 0 / −1`, using `cv2.remap(INTER_LINEAR, BORDER_REPLICATE)`; `amount` breathes with `sin(time·0.7)`. Fringing is strongest at the edges, like a real lens. |
| `vhs` | VHS | 📼 | medium | Tape wobble (`remap` with `sin(y·0.06 + time·6)·1.6` on x), colour bleed by blurring **only** the chroma channels `Cr`/`Cb` with a `(13,3)` kernel in YCrCb, random tracking streaks, additive Gaussian noise, a 14 % blend toward the frame's own grayscale, and a drawn `PLAY ▶` / `REC mm:ss:ff` stamp. |
| `crt` | CRT monitor | 🖥️ | medium | Barrel curvature by remap, an aperture-grille mask that keeps only one of every three subpixel columns at full gain, scanlines every 2nd row at 0.78, a rolling brightness bar as a Gaussian in y, and a sigma-3 phosphor bloom added at 0.35. |
| `datamosh` | Datamosh | 🧬 | medium | **Stateful.** Quarter-resolution grays go through `cv2.calcOpticalFlowFarneback(0.5, 3, 15, 3, 5, 1.2, 0)`; the upscaled flow warps the *previous output* with `cv2.remap`, then blends 0.72 previous / 0.28 current. Broken P-frames, exactly like a corrupted codec. |
| `scanlines` | Scanlines | 〰️ | cheap | A pure-translation `cv2.warpAffine` drifting horizontally with `sin(time·2)·1.2`, then every 2nd row multiplied by 0.68. |
| `trails` | Echo trails | 👻 | cheap | **Stateful.** `np.roll(previous, 3, axis=1)` blended with the current frame at `decay=0.78`, and the *result* is written back into the buffer — exponential feedback that leaves ghosts of movement. |
| `matrix` | Matrix rain | 🟩 | medium | **Stateful.** Per-column drop positions and speeds live in `self.state`; each frame advances them by `speed·delta·12` and respawns fallen columns. Eight trailing glyphs per column fade from 1 to 0 over a green-tinted base. |
| `slitscan` | Slit-scan | 🌌 | cheap | **Stateful.** A persistent canvas receives exactly 3 columns of the current frame per frame, at `(frame_index·3) % width`. Time becomes space: a still subject smears to nothing, motion draws a streak. |

On resize, every stateful filter re-initialises its buffer instead of failing — `trails`,
`datamosh` and `slitscan` compare `state["buffer"].shape` (or the stored width) against the
incoming frame and restart cleanly.

## Utility (8)

Category emoji 🛠️. These are the filters that need information beyond pixels.

| Name | Label | Emoji | Cost | Mask | Technique |
| --- | --- | --- | --- | --- | --- |
| `bg_blur` | Background blur | 🌀 | medium | **yes** | `apply_mask_blur(frame, ctx.state["person_mask"], strength=31)`: a full-frame `GaussianBlur` with a 31×31 kernel, blended through the mask feathered by `GaussianBlur(mask, (15,15), 0)` so the cut-out edge does not shimmer. Without a mask it blurs the whole frame. |
| `bg_replace` | Background replace | 🏞️ | medium | **yes** | Background cached per frame size: `mode="solid"` fills with BGR `(60,30,18)`, otherwise a vertical teal→violet gradient `(90,40,20) → (150,70,120)`. Blended behind the feathered person mask. With no mask it returns the frame untouched. |
| `privacy` | Privacy | 🕵️ | medium | — | With a mask, a 45×45 background blur through the feathered mask. Without one it degrades to whole-frame pixelation (`resize` to 1/24 with `INTER_AREA`, back up with `INTER_NEAREST`) rather than showing nothing. Safe screen sharing either way. |
| `face_crop` | Auto face frame | 🙂 | cheap | — | Reads `ctx.state["face_bbox"]`; if absent, returns the frame unchanged. Otherwise `scale = clip(0.32·width/face_w, 1.0, 2.2)`, crops around the bbox centre (shifted up by 18 % of the face height) and resizes back — auto-framing, not a literal cutout. |
| `skin_smooth` | Skin smooth | 🧖 | medium | — | Frequency separation: two chained `bilateralFilter` passes (9,60,60 then 9,45,45) form the low-frequency layer, `cv2.subtract` extracts the detail, and the detail is re-added at 35 % (`strength=0.65`). Softens texture while keeping pores and edges. |
| `mirror` | Kaleido mirror | 🪞 | cheap | — | Overwrites one half with a `cv2.flip` of the other. `axis="vertical"` (default) mirrors the left half onto the right; `axis="horizontal"` mirrors top onto bottom. |
| `zoom` | Punch-in | 🔍 | cheap | — | Centre crops `width/1.35 × height/1.35` and resizes back with `INTER_LINEAR`. `animate=True` breathes the factor by ±8 %. |
| `grid` | Rule of thirds | 📐 | cheap | — | A frame copy with `cv2.line` guides at 1/3 and 2/3 of each axis plus a 12 px centre circle. Composition guides for framing a shot. |

---

## Chaining filters

`--filter` accepts a `+`-separated chain. Each stage receives the previous stage's
output, and the chain shares one `FilterContext`, so a stateful filter in the middle of a
chain still sees a monotonic `frame_index`.

```bash
mirrorlab run --filter cartoon+vignette+glitch
mirrorlab run --filter sketch+saturation
mirrorlab run --filter grayscale+vignette+sharpen
```

Commas work too, because the parser normalises them: `--filter cartoon,vignette` is the
same chain as `--filter cartoon+vignette`.

Three things worth knowing:

* **Order matters.** `cartoon+vignette` darkens the corners of an already-flattened
  image; `vignette+cartoon` feeds the darkened frame into the edge detector and produces
  a different outline. Both are valid looks.
* **Cost adds up.** `FilterChain.cost` reports the worst stage, but the *time* is the sum.
  Three `medium` filters at ~10 ms each is 30 ms of a 33 ms budget. Use
  `mirrorlab benchmark` before shipping a chain.
* **Each stage is a fresh instance.** `build_filter` calls `type(found)()` per name, so
  two chains never share particle positions or feedback buffers — but `trails+trails`
  would create two independent buffers that each see the other's output.

Unknown names fail loudly with suggestions rather than silently rendering an unchanged
frame:

```console
$ mirrorlab run --filter caroon
KeyError: Unknown filter 'caroon'. Did you mean: cartoon?
Run `mirrorlab filters` to list them all.
```

## Presets

A preset is a name for a chain that someone tuned. `--preset` is mutually exclusive with
`--filter` in spirit — the preset wins, because `_cmd_run` applies it after the filter
override:

| Preset | Filter chain | Look |
| --- | --- | --- |
| `cinema` | `warmth+vignette+sharpen` | Warm highlights, soft corners, crisp detail |
| `anime` | `cartoon+saturation` | Flat cel colours with a vivid palette |
| `noir` | `grayscale+vignette+sharpen` | High-contrast monochrome, heavy vignette |
| `retro80s` | `cyberpunk+chromatic+scanlines` | Neon grade, colour fringing, CRT lines |
| `broken` | `glitch+trails` | Databend blocks with echo trails |
| `toon` | `comic+halftone` | Ben-Day dots and heavy ink |
| `ghost` | `xray+glitch` | Radiograph look with signal dropouts |
| `studio` | `skin_smooth+warmth+bg_blur` | Retouched skin, warm light, blurred background (needs `--segment`) |
| `paper` | `sketch+saturation` | Graphite linework with a colour wash |
| `vhs` | `vhs+scanlines` | Tape wobble, tracking noise, scanlines |

```bash
mirrorlab run --preset noir
mirrorlab run --preset studio --segment    # bg_blur needs the person mask
mirrorlab filters --presets                # list them from the CLI
```

`[` and `]` cycle presets at runtime, and `swipe_up` / `swipe_down` do the same by
gesture.

---

## Writing a new filter

1. Pick the module that matches the category: `classic.py` (basic/colour),
   `artistic.py`, `stylize.py`, `glitch.py`, `utility.py`.
2. Subclass `Filter`, fill in the metadata, implement `apply`.
3. Register an instance at module scope.
4. Add a benchmark line to your PR description (the `benchmark` command makes this one
   command).

A complete filter, ready to paste into `src/mirrorlab/filters/classic.py`:

```python
class CyanotypeFilter(Filter):
    """Blueprint print: iron-blue shadows on paper white.

    The trick is that a cyanotype is not a tint — it is a tone curve. The
    luminance ramp is pushed into the shadows first, then mapped onto a
    two-colour line, so highlights stay paper and only mid-tones go blue.
    """

    name = "cyanotype"
    label = "Cyanotype"
    label_es = "Cianotipo"
    emoji = "🧪"
    category = "color"
    description = "Blueprint print: iron-blue shadows on paper white."
    description_es = "Copia heliográfica: sombras azul hierro sobre papel."
    cost = "cheap"
    needs_mask = False

    PAPER = np.array([238, 242, 245], dtype=np.float32)   # BGR
    IRON = np.array([120, 70, 22], dtype=np.float32)

    def apply(self, frame: np.ndarray, ctx: FilterContext) -> np.ndarray:
        gray, _ = to_gray_bgr(frame)
        # Push the ramp into the shadows so highlights read as bare paper.
        ramp = np.clip(gray.astype(np.float32) / 255.0, 0.0, 1.0) ** 1.45
        mapped = self.PAPER + (self.IRON - self.PAPER) * ramp[..., None]
        return np.clip(mapped, 0, 255).astype(np.uint8)


register_filter(CyanotypeFilter())
```

Checklist before opening a pull request:

- [ ] `name` is unique, `snake_case`, and does not collide with an existing filter.
- [ ] `label_es` and `description_es` are filled in — the CLI and HUD are bilingual.
- [ ] `cost` matches reality: run `mirrorlab benchmark --filter <name> --frames 50`.
- [ ] `needs_mask = True` if you read `ctx.state["person_mask"]`, and you handle a missing
      mask by degrading (see `apply_mask_blur`).
- [ ] `apply` returns a new array and never mutates `frame`.
- [ ] Temporal state lives in `self.state` and survives `reset()`.
- [ ] The filter returns `uint8` BGR of the same height and width as its input. The app
      resizes mismatches, but a filter that changes size is a bug, not a feature.
- [ ] A test in `tests/` runs it over `SyntheticSource.render(0)` and asserts dtype, shape
      and value range.

See [ARCHITECTURE.md](ARCHITECTURE.md#9-adding-a-filter) for how the registry, the chain
and the testing strategy fit together.
