## What does this change?

<!-- One or two sentences. Link the issue it closes, if any: "Closes #12". -->

## Type of change

- [ ] Bug fix
- [ ] New filter / gesture / expression / effect
- [ ] Performance improvement
- [ ] Documentation
- [ ] Refactor (no behaviour change)
- [ ] Build / CI / packaging

## How was it verified?

<!-- Be specific. "Ran the app" is not enough — say what you ran and what you saw. -->

- [ ] `python -m pytest` passes locally
- [ ] `python -m ruff check src tests` and `python -m black --check src tests` pass
- [ ] `mirrorlab demo --frames 30` runs clean (headless, no camera needed)
- [ ] Tried it with a real camera on: <!-- macOS / Windows / Linux -->

## Checklist

- [ ] Public functions and classes have docstrings explaining **why**, not just what.
- [ ] New filters/gestures/effects are registered and appear in `mirrorlab filters|gestures|effects`.
- [ ] No new required dependency was added without updating `pyproject.toml` and `THIRD_PARTY_LICENSES.md`.
- [ ] No model weights, large binaries or personal captures were committed.
- [ ] If this changes behaviour, `CHANGELOG.md` was updated under `## [Unreleased]`.

## Screenshots / GIF

<!-- For anything visual, a short GIF is worth more than a paragraph. -->
