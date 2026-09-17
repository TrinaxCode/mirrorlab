# Contributing to MirrorLab

Thanks for wanting to help. MirrorLab is a small project with a high bar for correctness and
a low bar for ceremony: if you can run `pytest` and `ruff`, you can contribute.

By participating you agree to the [Code of Conduct](CODE_OF_CONDUCT.md).

---

## Setup

```bash
git clone https://github.com/TrinaxCode/mirrorlab.git
cd mirrorlab
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
mirrorlab doctor                   # tells you what this machine can actually do
```

`.[dev]` brings in `pytest`, `pytest-cov`, `ruff`, `black`, `mypy`, `rich` and `PyYAML`.

Or let the `Makefile` do it: `make install` creates `.venv` and installs the dev extras.

If MediaPipe misbehaves, use the tested dependency set:

```bash
pip install "mediapipe>=0.10.9,<0.11" "numpy<2" "opencv-python<5"
```

You do **not** need a working camera to develop. The synthetic source exercises the whole
render path deterministically:

```bash
mirrorlab demo --frames 120
```

---

## Dev workflow

The `Makefile` wraps every task, on macOS, Linux and Windows (Git Bash / WSL). `make` with no
argument lists the targets.

```bash
make install      # create .venv and install with dev extras
make test         # full suite, headless, no camera required
make test-fast    # skip the slow end-to-end cases (-m "not slow" -x -q)
make lint         # ruff check src tests
make format       # black + ruff --fix
make typecheck    # mypy
make check        # everything CI runs, locally
make run          # mirrorlab run
make demo         # mirrorlab demo --frames 120
make doctor       # mirrorlab doctor
make benchmark    # mirrorlab benchmark --all --frames 20
make gallery      # render a contact sheet of all 54 filters
make models       # download every model bundle into the cache
make clean        # drop caches and build artefacts
```

The underlying commands, if you would rather type them:

```bash
pytest -q                       # the default suite — no camera, no network, fast
pytest -m camera                # only when you actually have a webcam attached
pytest -m "not slow"            # while iterating on a single filter
pytest --cov=mirrorlab          # coverage

ruff check .                    # lint
ruff check --fix .              # lint, autofixing what is safe
black .                         # format
black --check .                 # verify formatting (what CI runs)
mypy                            # reads [tool.mypy], which targets src/mirrorlab
```

`make test` sets `PYTEST_HEADLESS=1`, the same switch CI uses. Run the full local gate
before pushing:

```bash
make check
# equivalent to: black --check . && ruff check . && mypy && pytest -q
```

### What the tools are configured to do

Everything lives in `pyproject.toml`, so there is no separate config file to keep in sync:

| Tool | Setting |
| --- | --- |
| `ruff` | `line-length = 110`, `target-version = "py39"`, rules `E, F, W, I, UP, B, C4, SIM, RUF`, ignores `E501, B008, RUF001-003` |
| `black` | `line-length = 110`, `target-version = ["py39"]` |
| `mypy` | `python_version = "3.9"`, `files = ["src/mirrorlab"]`, `ignore_missing_imports = true` |
| `pytest` | `testpaths = ["tests"]`, `addopts = "-q --strict-markers"`, markers `slow`, `gpu`, `camera` |

`--strict-markers` means an undeclared marker is an error. If you need a new category of
test, declare the marker in `pyproject.toml` rather than inventing one inline.

---

## Commit messages: Conventional Commits

Use [Conventional Commits](https://www.conventionalcommits.org/). The prefix is not
decoration — it is what makes the changelog derivable.

```
<type>(<optional scope>): <description>

<optional body>

<optional footer>
```

Common types:

| Type | Use for |
| --- | --- |
| `feat` | a new filter, gesture, effect, config key or CLI flag |
| `fix` | a bug fix |
| `perf` | a change that makes something measurably faster |
| `docs` | documentation only |
| `test` | tests only |
| `refactor` | no behaviour change |
| `build` | packaging, dependencies, CI |
| `chore` | everything else |

Examples that match how this repo actually reads:

```
feat(filters): add cyanotype two-tone print
fix(gestures): stop generic pinch from shadowing the OK sign
perf(artistic): downsample before binning in the oil filter
docs(architecture): document the drop-latest capture slot
```

Scopes worth using: `filters`, `effects`, `gestures`, `expressions`, `detectors`, `camera`,
`render`, `recording`, `config`, `cli`, `app`, `docs`, `web`.

---

## Code style

Short version: **write the code the file next to you is already written in.**

* **Type hints on every public function**, including return types. The codebase targets
  Python 3.9, so use `from __future__ import annotations` and modern syntax in annotations.
  `Dict[str, float]` in a runtime context, `dict[str, float]` in an annotation.
* **Docstrings explain WHY, not WHAT.** The code already says what it does. A docstring earns
  its place by explaining the constraint, the trade-off or the failure it prevents:

  ```python
  # Good — explains a decision
  # A 1-frame read is the only reliable "is this thing real?" test on Windows,
  # where DSHOW happily reports an open device that never delivers pixels.

  # Useless — restates the code
  # Read one frame from the capture device.
  ```

* **No `Any`.** If a value genuinely has several types, use `Union` / `|` or a `TypeVar`.
  `Any` hides exactly the bug type checking exists to catch. The one accepted exception is
  `**kwargs: Any` on a thin wrapper, and even then it should be rare.
* **Never mutate an input.** Filters and effects return a new frame. Detector observation
  dataclasses are mutated only where the code documents it (`classify_hands` writes
  `hand.gesture`).
* **Keep the layers apart.** `utils/` imports nothing from the package except `utils/`;
  nothing below `detectors/engine.py` imports the application layer. Breaking this makes the
  pure-logic tests impossible to run without a camera.
* **Numbers need a name.** A threshold in a matcher or a kernel size in a filter should be a
  module-level constant with a comment, not a literal in the middle of an expression.
* **Comments in English.** Spanish belongs in `label_es` / `description_es`, which the CLI
  and the HUD render.

---

## Testing requirements

**CI has no camera, no network and no GPU.** That is not a limitation to work around; it is
the constraint that keeps the suite fast and the architecture honest.

* **Test pure logic directly.** Scorers, matchers, geometry, smoothing, filters and config
  are all pure functions over plain data. They need no hardware and no model.
* **Use `SyntheticSource` and the committed fixtures.** `SyntheticSource.render(index)` is a
  pure function of the frame index, so it is snapshot-testable. `tests/assets/portrait.jpg`
  and `tests/assets/woman_hands.jpg` provide real pixels without a camera.
* **Never download a model in a test.** Pass `auto_download=False`.
* **Skip, do not fail, when MediaPipe is absent.** The backend ladder means "no MediaPipe" is
  a supported configuration.
* **No `time.sleep` to wait for anything.** Inject timestamps — every smoothing class and the
  gesture tracker accept them.
* **Mark hardware tests.** `@pytest.mark.camera` for anything that opens a device,
  `@pytest.mark.slow` for anything over a second, `@pytest.mark.gpu` for the (currently
  empty) GPU path.

A new filter needs a test that runs it over a synthetic frame and asserts dtype, shape and
value range. A new matcher needs a positive case *and* a negative one — a relaxed hand must
classify as `none`, not as the nearest gesture.

---

## Adding a filter, gesture or effect

Short version: the registries do all the wiring, so you never touch the CLI.

### A filter

```python
class CyanotypeFilter(Filter):
    name = "cyanotype"            # the CLI token
    label = "Cyanotype"
    label_es = "Cianotipo"
    emoji = "🧪"
    category = "color"            # one of CATEGORIES
    description = "Blueprint print: iron-blue shadows on paper white."
    description_es = "Copia heliográfica: sombras azul hierro sobre papel."
    cost = "cheap"                # cheap | medium | heavy
    needs_mask = False

    def apply(self, frame: np.ndarray, ctx: FilterContext) -> np.ndarray:
        ...


register_filter(CyanotypeFilter())
```

Then add the benchmark line to your PR:
`mirrorlab benchmark --filter cyanotype --frames 50`.

Full guide with a runnable example: [docs/FILTERS.md](docs/FILTERS.md#writing-a-new-filter).

### A gesture

```python
GESTURES["l_shape"] = GestureDefinition(
    name="l_shape", label="L shape", label_es="Forma de L", emoji="🫰",
    matcher=_match_l_shape, threshold=0.68, category="symbol",
    description="Thumb and index at a right angle, other fingers folded.",
    action="snapshot",
)
```

Bind it in `actions.DEFAULT_BINDINGS` if it should trigger something. Full guide:
[docs/GESTURES.md](docs/GESTURES.md#adding-your-own-gesture).

### An effect

```python
class MonocleEffect(FaceEffect):
    name = "monocle"
    label = "Monocle"
    label_es = "Monóculo"
    emoji = "🧐"
    description = "A brass rim over one eye with a dangling chain."
    description_es = "Un aro de latón sobre un ojo con cadena colgante."

    def apply(self, frame, face, ctx):
        if face.count < 400:      # Haar gives 0 landmarks, YuNet gives sparse ones
            return frame
        ...


register_face_effect(MonocleEffect())
```

Full guide: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#10-adding-an-effect).

---

## Pull request checklist

Before you open a PR, confirm:

- [ ] The change does one thing. Unrelated refactors go in a separate PR.
- [ ] `black --check . && ruff check . && mypy && pytest -q` passes locally.
- [ ] New pure logic has tests; new hardware paths are marked `camera` and skipped in CI.
- [ ] New public functions have type hints and a docstring that explains *why*.
- [ ] New filters/effects/gestures carry `label_es` and `description_es`, and the docs table
      is updated if you added to a catalog.
- [ ] User-visible changes are noted under `## [Unreleased]` in [CHANGELOG.md](CHANGELOG.md),
      using the Keep a Changelog headings.
- [ ] No new runtime dependency without a note in the PR explaining why the standard library
      or an existing dependency will not do.
- [ ] No `.task`, `.tflite` or `.onnx` model files committed. Models are downloaded, never
      redistributed — see [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).
- [ ] No new binary artwork. Effects are drawn procedurally with OpenCV primitives on
      purpose.
- [ ] Commit messages follow Conventional Commits.

### Review expectations

A maintainer will look for, in this order:

1. **Does it degrade?** Every new detector, model or optional feature needs a defined
   behaviour when it is unavailable.
2. **Is it testable without hardware?** If not, can the logic be split so the decision part
   is?
3. **Does it respect the layers?** No new import from `utils/` upward, no detector-specific
   object escaping `detectors/base.py`.
4. **Is the cost documented?** A `medium` filter that actually takes 40 ms should say
   `heavy`.

---

## Good first issues

New here? Look for issues labelled **`good first issue`** — they are scoped to be
self-contained and to touch one file plus its docs. The most reliable shape of a first
contribution is **a new filter** (one class, one registration, one test) or **a new
gesture** (one matcher, one registration entry).

If you want to add something larger — a new detector backend, a virtual-camera output, the
plugin API — open an issue first so we can agree on the interface before you write it. The
[roadmap](ROADMAP.md) lists what is already planned and, more usefully, what is deliberately
*not* planned.

---

## Reporting bugs

Open an issue at <https://github.com/TrinaxCode/mirrorlab/issues> and attach the output of:

```bash
mirrorlab doctor --json
mirrorlab cameras --json
```

That pair covers the OS, Python, OpenCV, MediaPipe, the capability probes and the camera
backends, which is usually everything needed to reproduce. For a security issue, do **not**
open a public issue — follow [SECURITY.md](SECURITY.md).
