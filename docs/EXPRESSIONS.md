# MirrorLab expressions

> [English](EXPRESSIONS.md) · [README](../README.md) · [Español](../README.es.md) · [Architecture](ARCHITECTURE.md) · [Filters](FILTERS.md) · [Gestures](GESTURES.md) · [Cross-platform](CROSS_PLATFORM.md) · [FAQ](FAQ.md)

18 facial expressions, read from MediaPipe's 52 blendshape channels — muscle-activation
coefficients, not landmark ratios. This document gives the exact formula behind every
score.

List them from the terminal:

```bash
mirrorlab expressions            # emoji, name, Spanish label, description
mirrorlab expressions --json     # machine-readable catalog
```

---

## Contents

- [Why blendshapes beat landmark ratios](#why-blendshapes-beat-landmark-ratios)
- [The 52 channels](#the-52-channels)
- [The catalogue (18)](#the-catalogue-18)
- [Blendshape scorers](#blendshape-scorers)
- [How a winner is picked](#how-a-winner-is-picked)
- [The geometric fallback](#the-geometric-fallback)
- [Smoothing and voting](#smoothing-and-voting)
- [Adding an expression](#adding-an-expression)

---

## Why blendshapes beat landmark ratios

A ratio between two landmarks is a *proxy* for a muscle. It moves when the muscle moves —
but also when you turn your head, change distance, or when the detector jitters by a
pixel. The classic "smile detector" (`mouth_width / face_width > 0.42`) fires on a wide
face, on a yawn, and on a bad frame.

A blendshape is the muscle activation itself. MediaPipe's FaceLandmarker regresses 52
ARKit-style coefficients from the face mesh, so `mouthSmileLeft` rising *is* the
zygomaticus major contracting. The classifier becomes arithmetic on named channels
instead of a tuning problem:

```python
smile = _pair(b, "mouthSmile")          # mean of mouthSmileLeft / mouthSmileRight
dimple = _pair(b, "mouthDimple")
return clamp(0.85 * smile + 0.15 * dimple)
```

That is the whole `happy` scorer. It is readable, debuggable, and it does not care how far
away you are sitting.

The trade-off is honest: blendshapes require the MediaPipe **Tasks** backend. With the
legacy Solutions backend or an OpenCV fallback there are none, and MirrorLab falls back to
landmark geometry — see [the geometric fallback](#the-geometric-fallback). The active
strategy is always visible in `ExpressionResult.method`, which is `"blendshapes"`,
`"geometry"` or `"none"`.

## The 52 channels

`BLENDSHAPE_NAMES` in `detectors/base.py` lists every channel in the order MediaPipe emits
them. Index 0 is `_neutral`; the remaining 51 are ARKit-style muscle channels, always in
`Base` / `BaseLeft` / `BaseRight` triples where left/right exist:

| Group | Channels |
| --- | --- |
| Brow | `browDownLeft`, `browDownRight`, `browInnerUp`, `browOuterUpLeft`, `browOuterUpRight` |
| Cheek | `cheekPuff`, `cheekSquintLeft`, `cheekSquintRight` |
| Eyes | `eyeBlinkLeft`, `eyeBlinkRight`, `eyeLookDownLeft/Right`, `eyeLookInLeft/Right`, `eyeLookOutLeft/Right`, `eyeLookUpLeft/Right`, `eyeSquintLeft/Right`, `eyeWideLeft/Right` |
| Jaw | `jawForward`, `jawLeft`, `jawOpen`, `jawRight` |
| Mouth | `mouthClose`, `mouthDimpleLeft/Right`, `mouthFrownLeft/Right`, `mouthFunnel`, `mouthLeft`, `mouthLowerDownLeft/Right`, `mouthPressLeft/Right`, `mouthPucker`, `mouthRight`, `mouthRollLower`, `mouthRollUpper`, `mouthShrugLower`, `mouthShrugUpper`, `mouthSmileLeft/Right`, `mouthStretchLeft/Right`, `mouthUpperUpLeft/Right` |
| Nose | `noseSneerLeft`, `noseSneerRight` |

You can print the table:

```bash
python -c "from mirrorlab.detectors.base import BLENDSHAPE_NAMES as B; print(len(B)); print(list(enumerate(B)))"
```

### Why `_neutral` is index 0

MediaPipe emits the rest-pose coefficient first, before the muscle channels, and gives it a
leading underscore. The underscore is the convention MediaPipe uses for channels that are
not ARKit blend shapes: `_neutral` is a vendor-specific "this face is at rest" value, not a
muscle you can drive. So the customary phrase "52 ARKit blendshapes" counts a slot that is
not itself an ARKit channel — 51 muscle channels plus `_neutral`.

MirrorLab therefore **reads blendshapes by name, never by index**, and no scorer ever
touches `_neutral`. The `neutral` expression is scored from the *absence* of the expressive
channels instead:

```python
@staticmethod
def neutral(b: Dict[str, float]) -> float:
    """Neutral is the *absence* of the expressive channels."""
    expressive = (_pair(b, "mouthSmile") + _pair(b, "mouthFrown") + _pair(b, "browDown")
                  + _bs(b, "browInnerUp") + _pair(b, "browOuterUp") + _bs(b, "jawOpen")
                  + _pair(b, "eyeWide") + _pair(b, "eyeSquint") + _bs(b, "mouthPucker")
                  + _pair(b, "noseSneer"))
    return clamp(1.0 - expressive / 2.6)
```

Ten channels, one sum, one clamp. A face doing nothing scores ~1.0; a face doing anything
loses ground proportionally.

### There is no `tongueOut` channel

`"tongueOut" in BLENDSHAPE_NAMES` is `False`. MediaPipe's FaceLandmarker does not expose a
tongue channel, so MirrorLab has no tongue expression and cannot fake one from geometry —
the face mesh has no tongue landmarks either. What you *can* do is drive an overlay from
jaw opening: `DogEffect` reads `face.blend("jawOpen")` and scales the drawn tongue:

```python
jaw_open = face.blend("jawOpen", 0.0)
if jaw_open > 0.06:
    length = int(interocular * (0.45 + jaw_open * 1.3))
```

If you need real tongue detection, it is a separate model (a face-landmark model that
includes a tongue keypoint), and it is on the roadmap as a research item rather than a
feature.

## The catalogue (18)

Each entry is an `ExpressionDefinition` with an English label, a Spanish label, an emoji,
a category and a description. The registry is what `mirrorlab expressions` and the web
demo iterate.

| Emoji | Name | Español | English | Category |
| --- | --- | --- | --- | --- |
| 😐 | `neutral` | Neutral | Neutral | state |
| 😊 | `happy` | Feliz | Happy | emotion |
| 😄 | `laugh` | Riendo | Laughing | emotion |
| 😢 | `sad` | Triste | Sad | emotion |
| 😠 | `angry` | Enojo | Angry | emotion |
| 😲 | `surprised` | Sorpresa | Surprised | emotion |
| 😨 | `fear` | Miedo | Fear | emotion |
| 🤢 | `disgust` | Disgusto | Disgust | emotion |
| 😏 | `contempt` | Desprecio | Contempt | emotion |
| 😘 | `kiss` | Beso | Kiss | gesture |
| 😉 | `wink` | Guiño | Wink | gesture |
| 😑 | `blink` | Parpadeo | Blink | state |
| 🤨 | `brow_raise` | Cejas arriba | Brow raise | gesture |
| 😑 | `squint` | Entrecerrar ojos | Squint | gesture |
| 🤔 | `thinking` | Pensando | Thinking | gesture |
| 🥱 | `yawn` | Bostezo | Yawn | gesture |
| 😗 | `puff` | Mejillas infladas | Cheek puff | gesture |
| ❔ | `unknown` | Desconocido | Unknown | state |

`unknown` is the "no face, or no usable signal" sentinel — the classifier's default when
`classify(None)` is called or when the backend provides no landmarks at all (Haar). It has
no scorer. `blink` has a scorer but no entry in the priority list — see
[the blink caveat](#the-blink-caveat).

`EXPRESSION_ALIASES` accepts alternate spellings in both languages, so `smile`, `smiling`,
`feliz` and `sonrisa` all resolve to `happy`. Like the gesture alias table it is a
library-level helper used by `expression_display()` — the classifier itself always speaks
canonical names, and there is no `--expression` CLI flag. The full map:
`smile`/`smiling`/`feliz`/`sonrisa` → `happy`, `laughing` → `laugh`,
`sadness`/`tristeza` → `sad`, `anger`/`enojo` → `angry`, `surprise`/`sorpresa` →
`surprised`, `winking`/`guiño` → `wink`, `kissing`/`beso` → `kiss`, `neutral_face` →
`neutral`.

## Blendshape scorers

Every scorer lives in `_BlendshapeScorers` and takes the blendshape dict. Three helpers do
all the reading:

```python
def _bs(blends, name):        return float(blends.get(name, 0.0))
def _mean(blends, *names):    return sum(_bs(blends, n) for n in names) / len(names)
def _pair(blends, base):      return _mean(blends, f"{base}Left", f"{base}Right")
def _asymmetry(blends, base): return abs(_bs(blends, f"{base}Left") - _bs(blends, f"{base}Right"))
```

`clamp` is `mirrorlab.utils.geometry.clamp`, which defaults to `[0, 1]`.

### Emotion expressions

| Expression | Formula |
| --- | --- |
| `happy` | `clamp(0.85·mouthSmile + 0.15·mouthDimple)` — the smile channels carry it; dimples are corroboration, not a co-equal signal. |
| `laugh` | `clamp(mouthSmile · clamp(jawOpen/0.35) · 0.9 + mouthSmile · 0.35 · clamp(jawOpen/0.6))` — a *gated* smile: two jaw terms with different saturating thresholds, so a small jaw opening adds a little and a wide one adds a lot, but a closed mouth scores zero regardless of the smile. |
| `sad` | `clamp(0.5·mouthFrown + 0.3·browInnerUp + 0.2·mouthLowerDown)` — the classic sadness triangle: corners down, inner brows raised, lower lip pulled down. |
| `angry` | `clamp(0.45·browDown + 0.2·mouthPress + 0.2·noseSneer + 0.15·mouthStretch)` — brow down dominates; lip press, nose sneer and lip stretch are supporting evidence. |
| `surprised` | `clamp(0.5·clamp(jawOpen/0.45) + 0.3·eyeWide + 0.2·browOuterUp)` — jaw and eyes, each saturating so a huge yawn does not outscore surprise indefinitely. |
| `fear` | `clamp(0.4·browInnerUp + 0.35·eyeWide + 0.25·mouthStretch)` — inner brow up plus wide eyes plus a stretched mouth. Note it shares `browInnerUp` with `sad`; the wide eyes and stretched mouth are what separate them. |
| `disgust` | `clamp(0.65·noseSneer + 0.35·mouthUpperUp)` — the nose does most of the work. |
| `contempt` | `clamp(abs((mouthSmileLeft + mouthDimpleLeft) − (mouthSmileRight + mouthDimpleRight)) · 0.9)` — the only scorer that measures **asymmetry**: a one-sided smirk. Both smile and dimple are included so a fake smile that only lifts one corner still registers. |

### Gesture expressions

| Expression | Formula |
| --- | --- |
| `kiss` | `clamp(0.6·mouthPucker + 0.4·mouthFunnel)` — pursed forward, with funnel as the supporting shape. |
| `wink` | Two-sided by construction: `closed, open_ = min(eyeBlinkLeft, eyeBlinkRight), max(...)`. If `open_ > 0.45` it returns `0.0` — **one eye must stay open**, otherwise it is a blink. Otherwise `clamp((closed − 0.4)/0.5)`. The guard is what makes `wink` and `blink` mutually exclusive rather than competing. |
| `brow_raise` | `clamp((0.5·browInnerUp + 0.5·browOuterUp) − browDown)` — brows up *minus* brows down, so furrowing actively cancels the score instead of merely not contributing. |
| `squint` | `clamp(eyeSquint · (1.0 − 0.5·mouthSmile))` — squinting attenuated by smiling, because a genuine smile squints the eyes (the Duchenne marker) and would otherwise read as a squint. |
| `thinking` | `clamp(0.45·eyeLookUp + 0.3·mouthPress + 0.25·browInnerUp)` — eyes up, lips pressed, inner brow up. The `eyeLook*` channels are what make this one distinctive. |
| `yawn` | `clamp(clamp((jawOpen − 0.55)/0.35) · (0.5 + 0.5·eyeSquint) · (1.0 − 0.6·mouthSmile))` — a **product**, not a sum: a wide jaw is necessary, squinting eyes increase it, and a smile suppresses it. That is how a laugh (`smile · jaw`) and a yawn (`jaw · ¬smile`) are separated by the same two channels. |
| `puff` | `clamp(cheekPuff · 1.4)` — one channel, gained 1.4 because `cheekPuff` rarely reaches high values. |

### The neutral expression

| Expression | Formula |
| --- | --- |
| `neutral` | `clamp(1.0 − expressive/2.6)`, where `expressive` is the sum of the ten channels listed [above](#why-_neutral-is-index-0). The divisor 2.6 is the empirical point at which an active face reaches zero. |

### The blink caveat

`_BlendshapeScorers.blink` exists:

```python
@staticmethod
def blink(b: Dict[str, float]) -> float:
    return clamp((min(_bs(b, "eyeBlinkLeft"), _bs(b, "eyeBlinkRight")) - 0.45) / 0.4)
```

It is **not** in `_BlendshapeScorers.ALL`, and `blink` is **not** in `_PRIORITY`. So with a
blendshape backend the channel is never evaluated, and even if it scored it could not win a
pick. `blink` can only appear through the geometric fallback, which does compute it — but
the pick loop still only iterates `_PRIORITY`, so it cannot win there either. It is
reachable only by reading `ExpressionResult.scores["blink"]` yourself.

Treat `blink` as a **raw signal available to your own code** rather than a reported
expression. It is genuinely useful (blink rate, drowsiness, liveness) and the scorer is
correct; it is simply excluded from the winner's circle because a blink is 150 ms long and
would flicker through the HUD constantly. If you want it reported, add it to `_PRIORITY`
*after* `wink` and lower `min_score` for it — but expect flicker.

## How a winner is picked

`_pick(scores)` is deliberately not an `argmax`:

```python
best_name, best_score = "neutral", float(scores.get("neutral", 0.0))
for name in self.priority:
    if name == "neutral":
        continue
    score = float(scores.get(name, 0.0))
    if score < self.min_score:          # default 0.28
        continue
    if score >= best_score * 0.92:      # a deliberate expression wins near-ties
        best_name, best_score = name, score
return best_name, best_score
```

Two mechanisms are doing the work:

1. **`min_score = 0.28`.** A non-neutral expression must clear a floor before it is
   considered at all. Without it, the largest of sixteen tiny numbers would always win and
   a resting face would flicker between micro-expressions.
2. **The `0.92` factor and `_PRIORITY` order.** An expression wins if it is at least 92 %
   of the current best. Because the loop runs in priority order and later entries must
   beat earlier ones by the same margin, **earlier in `_PRIORITY` means stickier**:

   ```
   wink → laugh → yawn → kiss → puff → disgust → surprised → angry →
   sad → fear → contempt → thinking → squint → brow_raise → happy → neutral
   ```

   The order is roughly "rarer and more deliberate first". A wink beats a laugh because a
   wink is intentional and a laugh often is not. `happy` sits near the bottom because it is
   the most common false positive — a neutral face with slightly raised mouth corners
   should stay neutral.

`_PRIORITY` is a constructor argument, so you can supply your own order per instance:

```python
from mirrorlab.expressions import ExpressionClassifier

# A demo that cares about surprise above everything else.
classifier = ExpressionClassifier(
    smoothing=0.35,
    min_score=0.25,
    priority=("surprised", "happy", "neutral"),
)
```

## The geometric fallback

When the backend provides landmarks but no blendshapes — the legacy Solutions backend, or
OpenCV YuNet — `_geometric_scores(landmarks)` estimates the same expressions from four
classic measurements. It is used automatically; `ExpressionResult.method` becomes
`"geometry"`.

**Anchors.** Fifteen MediaPipe mesh indices (`_FALLBACK_ANCHORS`), including eye corners
(33, 133, 263, 362), mouth corners (61, 291) and lips (12, 13, 14, 15), brows (105, 334),
nose tip (1), chin (152) and forehead (10). If the landmark array has fewer than
**363 rows** (the largest anchor index is 362) the function returns an all-zero score dict
immediately.

**The four measurements:**

| Measurement | Definition |
| --- | --- |
| `mar` (mouth aspect ratio) | `distance(upper_lip_inner, lower_lip_inner) / max(distance(mouth_left, mouth_right), 1e-6)` |
| `corner_lift` | `(lip_mid_y − mean(mouth_left.y, mouth_right.y)) / mouth_width`, where `lip_mid_y = (upper_lip.y + lower_lip.y)/2`. Positive = corners above the lip midline. |
| `ear` (eye aspect ratio) | mean of `distance(eye_outer, eye_inner)/face_height` for both eyes, `face_height = max(distance(forehead, chin), 1e-6)` |
| `brow_gap` | `(distance(right_brow, right_eye_outer) + distance(left_brow, left_eye_outer)) / (2·face_height)` |

**The five derived signals**, each a linear ramp with its own dead zone:

```python
smile     = clamp((corner_lift - 0.02) / 0.10)
jaw_open  = clamp((mar - 0.06) / 0.34)
eyes_wide = clamp((ear - 0.055) / 0.05)
frown     = clamp((-corner_lift - 0.01) / 0.08)
brow_up   = clamp((brow_gap - 0.055) / 0.05)
```

**The ten scores** recomposed from those signals:

| Expression | Geometric formula |
| --- | --- |
| `happy` | `clamp(0.9·smile)` |
| `laugh` | `clamp(smile · jaw_open · 1.1)` |
| `sad` | `clamp(0.7·frown + 0.3·brow_up)` |
| `surprised` | `clamp(0.55·jaw_open + 0.45·eyes_wide)` |
| `angry` | `clamp(0.6·clamp((0.055 − brow_gap)/0.05) + 0.4·clamp((0.09 − mar)/0.09))` — lowered brows and a closed mouth |
| `brow_raise` | `brow_up` |
| `kiss` | `clamp((0.05 − mar)/0.05 · 0.7 · smile)` |
| `yawn` | `clamp((mar − 0.45)/0.3)` |
| `blink` | `clamp((0.045 − ear)/0.03)` |
| `neutral` | `clamp(1.0 − (smile + jaw_open + frown + eyes_wide + brow_up)/2.2)` |

Everything else stays at `0.0`. That means **`wink`, `fear`, `disgust`, `contempt`,
`thinking`, `squint` and `puff` are not detectable without blendshapes** — there is no
landmark ratio that reads a one-sided smirk or a nose sneer reliably, and inventing one
would produce confident nonsense. The API is honest about it: `method` says `"geometry"`
and those seven scores are zero.

The geometric path is also less trustworthy on the YuNet backend, because YuNet supplies
only five real points and `YuNetFaceBackend._expand` fills the other 463 slots with a
golden-angle spiral ellipse. Those synthetic points keep the *ratios* in a plausible range,
which is why the heuristics run at all — but they are not a face mesh. Expect `mar` and
`ear` to be roughly right and `corner_lift` to be noisy.

## Smoothing and voting

Three stages turn per-frame scores into a stable label.

**1. EMA per expression score.** `ExpressionClassifier` holds one `EmaFilter` per
expression name:

```python
value = alpha·new + (1 − alpha)·old      # alpha = config.expression_smoothing, default 0.35
```

with the first sample seeding the filter. Smoothing the *scores* rather than the winner is
deliberate: smoothing a label needs a history of labels and adds a frame of latency to
every change, while smoothing scores keeps the decision instant and still kills
single-frame spikes. Set `smoothing=0.0` (or `smooth_landmarks = False`, which the engine
translates into `0.0`) to disable it entirely.

**2. Priority pick.** The smoothed scores go through `_pick`, described above.

**3. Majority vote over the last 7 frames.** `PerceptionEngine` keeps a
`SlidingWindow(maxlen=7)` of recent labels and overrides the per-frame winner only when a
different label is genuinely dominant:

```python
self._expression_votes.push(result.name)
stable = self._expression_votes.majority(result.name)
if stable and stable != result.name and self._expression_votes.items.count(stable) >= 4:
    result.name = str(stable)
    result.score = float(result.scores.get(result.name, result.score))
```

Four out of seven frames is a real majority, not a plurality, so a two-frame blink cannot
take over the label. Seven frames at 30 fps is 233 ms of context — long enough to outvote a
flicker, short enough that a deliberate expression still reads as immediate.
`SlidingWindow.majority()` breaks ties by the most recent occurrence, so the newest
evidence wins.

When no face is present, `classify(None)` resets the classifier, clears the vote window and
returns `unknown` — so walking out of frame and back in does not inherit stale state.

## Adding an expression

Three edits, all in `expressions.py`.

**1. Register the definition:**

```python
_register("smirk", "Smirk", "Sonrisita", "😼", "emotion",
          "A small, tight, self-satisfied smile.")
```

**2. Write the scorer and add it to `ALL`:**

```python
@staticmethod
def smirk(b: Dict[str, float]) -> float:
    """A smirk is a smile with pressed lips and no dimple: the mouth corners
    lift, but the cheek does not engage, so mouthSmile rises while mouthDimple
    and mouthStretch stay flat."""
    smile = _pair(b, "mouthSmile")
    dimple = _pair(b, "mouthDimple")
    press = _pair(b, "mouthPress")
    return clamp(smile * (1.0 - 0.7 * dimple) * (0.5 + 0.5 * press))


_BlendshapeScorers.ALL = {
    # …existing entries…
    "smirk": _BlendshapeScorers.smirk,
}
```

**3. Give it a priority slot:**

```python
_PRIORITY = ("wink", "laugh", "yawn", "kiss", "smirk", "puff", "disgust", "surprised",
             "angry", "sad", "fear", "contempt", "thinking", "squint", "brow_raise",
             "happy", "neutral")
```

Placement matters more than the formula. Put a new expression where its *false-positive
cost* belongs: early if it is rare and deliberate, late if it is easy to trigger by
accident.

Two rules that save debugging time:

* **Read channels by name, never by index.** The `_neutral` slot at index 0 and the
  left/right triples make positional access a trap, and it breaks the moment you use a
  model with a different channel order.
* **Test the scorer as a pure function.** It takes a dict and returns a float, so a unit
  test is one line:

  ```python
  from mirrorlab.expressions import _BlendshapeScorers

  def test_happy_from_smile():
      score = _BlendshapeScorers.happy({"mouthSmileLeft": 0.9, "mouthSmileRight": 0.9})
      assert score > 0.7

  def test_smirk_vs_happy():
      # A smirk must not outscore a genuine smile.
      assert _BlendshapeScorers.smirk({"mouthSmileLeft": 0.6, "mouthPressLeft": 0.8}) < \
             _BlendshapeScorers.happy({"mouthSmileLeft": 0.8, "mouthSmileRight": 0.8,
                                       "mouthDimpleLeft": 0.6, "mouthDimpleRight": 0.6})
  ```

See [ARCHITECTURE.md](ARCHITECTURE.md#7-smoothing-strategy) for how the smoothing stages
compose, and [GESTURES.md](GESTURES.md) for the hand side of the perception engine.
