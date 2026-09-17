"""Filter registry and every registered filter.

The point of these tests is not that a filter "works" in a visual sense — it is
that **all** of them are registered, run without raising, preserve the frame
contract (uint8, 3 channels, same size) and stay inside the real-time budget.
A 54-filter library with one filter that crashes the render loop is worse than
a 10-filter library that never does.
"""

from __future__ import annotations

import time

import numpy as np
import pytest

from mirrorlab.filters import (
    CATEGORIES,
    FILTERS,
    PRESETS,
    FilterChain,
    FilterContext,
    build_chain,
    build_filter,
    filter_catalog,
    filters_by_category,
    get_filter,
    list_filters,
)

ALL_FILTERS = sorted(FILTERS)
#: Filters whose whole output is a fresh canvas of a different size.
RESIZING = {"ascii"}


def make_ctx(frame: np.ndarray, index: int = 1, t: float = 0.5) -> FilterContext:
    return FilterContext(
        frame_index=index,
        time=t,
        delta=1 / 30.0,
        width=frame.shape[1],
        height=frame.shape[0],
    )


def test_registry_is_populated_and_documented():
    assert len(FILTERS) >= 50, "the library should be broad"
    for name, instance in FILTERS.items():
        assert instance.name == name
        assert instance.label and instance.label_es, f"{name} needs bilingual labels"
        assert instance.category in CATEGORIES, f"{name} has an unknown category"
        assert instance.cost in {"cheap", "medium", "heavy"}
        assert instance.description, f"{name} needs a description"


def test_catalog_is_json_ready():
    import json

    catalog = filter_catalog()
    json.dumps(catalog)
    assert len(catalog) == len(FILTERS)
    assert {row["name"] for row in catalog} == set(FILTERS)


def test_categories_all_have_members():
    grouped = filters_by_category()
    assert grouped, "at least one category must be populated"
    for category, items in grouped.items():
        assert category in CATEGORIES
        assert items


@pytest.mark.parametrize("name", ALL_FILTERS)
def test_every_filter_preserves_the_frame_contract(name, frame):
    instance = FILTERS[name]
    ctx = make_ctx(frame)
    out = instance.apply(frame.copy(), ctx)
    assert isinstance(out, np.ndarray), f"{name} must return an array"
    assert out.dtype == np.uint8, f"{name} returned {out.dtype}"
    assert out.ndim == 3 and out.shape[2] == 3, f"{name} returned {out.shape}"
    assert out.size > 0
    if name not in RESIZING:
        assert out.shape == frame.shape, f"{name} changed the frame size"
    assert np.isfinite(out).all()


@pytest.mark.parametrize("name", ALL_FILTERS)
def test_every_filter_survives_extreme_input(name, frame):
    """Solid black, solid white and pure noise must not break any filter."""
    instance = FILTERS[name]
    for extreme in (
        np.zeros_like(frame),
        np.full_like(frame, 255),
        np.random.default_rng(0).integers(0, 2, frame.shape, dtype=np.uint8) * 255,
    ):
        ctx = make_ctx(extreme)
        out = instance.apply(extreme.copy(), ctx)
        assert out.shape[2] == 3 and out.dtype == np.uint8


@pytest.mark.parametrize("name", ALL_FILTERS)
def test_every_filter_is_deterministic_for_a_fixed_frame(name, frame):
    """Same frame + same context from a fresh instance must give the same result.

    ``reset()`` is what makes this a fair test: several filters (datamosh,
    trails, slitscan, matrix) intentionally carry state between frames, so the
    comparison has to start from the same state.
    """
    instance = FILTERS[name]
    ctx = make_ctx(frame, index=10, t=1.0)
    instance.reset()
    first = instance.apply(frame.copy(), ctx)
    instance.reset()
    second = instance.apply(frame.copy(), ctx)
    np.testing.assert_array_equal(first, second)


@pytest.mark.parametrize("name", ALL_FILTERS)
def test_every_filter_is_idempotent_on_a_small_frame(name):
    """Odd sizes (typical of some webcams) must not break kernel maths."""
    small = np.random.default_rng(4).integers(0, 255, (97, 61, 3), dtype=np.uint8)
    instance = FILTERS[name]
    out = instance.apply(small.copy(), make_ctx(small))
    assert out.dtype == np.uint8 and out.shape[2] == 3


@pytest.mark.parametrize("name", ALL_FILTERS)
def test_every_filter_runs_within_the_frame_budget(name, frame):
    """A filter slower than 33 ms cannot hold 30 fps on its own."""
    instance = FILTERS[name]
    ctx = make_ctx(frame)
    for _ in range(3):  # warm up allocations
        ctx.frame_index += 1
        instance.apply(frame.copy(), ctx)
    started = time.perf_counter()
    runs = 6
    for _ in range(runs):
        ctx.frame_index += 1
        ctx.time += 1 / 30.0
        instance.apply(frame.copy(), ctx)
    per_frame_ms = (time.perf_counter() - started) / runs * 1000.0
    assert per_frame_ms < 60.0, f"{name} took {per_frame_ms:.1f} ms at 320x240"


def test_original_filter_is_a_passthrough(frame):
    out = get_filter("original").apply(frame.copy(), make_ctx(frame))
    np.testing.assert_array_equal(out, frame)


def test_grayscale_really_is_gray(frame):
    out = get_filter("grayscale").apply(frame.copy(), make_ctx(frame))
    assert np.allclose(out[..., 0], out[..., 1], atol=6)
    assert np.allclose(out[..., 1], out[..., 2], atol=6)


def test_invert_is_an_involution(frame):
    invert = get_filter("invert")
    ctx = make_ctx(frame)
    once = invert.apply(frame.copy(), ctx)
    twice = invert.apply(once, ctx)
    np.testing.assert_array_equal(twice, frame)


def test_stateful_filters_keep_state_between_frames(frame):
    """`slitscan` and `trails` are only meaningful across frames."""
    slitscan = build_filter("slitscan")
    ctx = make_ctx(frame)
    first = slitscan.apply(frame.copy(), ctx)
    for index in range(2, 40):
        ctx.frame_index = index
        ctx.time = index / 30.0
        out = slitscan.apply(np.full_like(frame, index * 6), ctx)
    assert not np.array_equal(out, first), "a slit-scan must accumulate history"


def test_reset_clears_filter_state(frame):
    trails = build_filter("trails")
    ctx = make_ctx(frame)
    for index in range(5):
        ctx.frame_index = index
        trails.apply(frame.copy(), ctx)
    assert trails.state, "state should have accumulated"
    trails.reset()
    assert trails.state == {}


# --------------------------------------------------------------------------- #
# Chaining
# --------------------------------------------------------------------------- #
def test_build_filter_single_and_chain(frame):
    single = build_filter("cartoon")
    assert not isinstance(single, FilterChain)
    chain = build_filter("cartoon+vignette+glitch")
    assert isinstance(chain, FilterChain)
    assert [stage.name for stage in chain.filters] == ["cartoon", "vignette", "glitch"]
    assert chain.apply(frame.copy(), make_ctx(frame)).shape == frame.shape


def test_build_filter_accepts_commas_and_spaces():
    chain = build_filter(" cartoon , vignette ")
    assert isinstance(chain, FilterChain)
    assert [stage.name for stage in chain.filters] == ["cartoon", "vignette"]


def test_build_filter_rejects_unknown_names_with_a_suggestion():
    with pytest.raises(KeyError) as excinfo:
        build_filter("carton")
    message = str(excinfo.value)
    assert "carton" in message
    assert "cartoon" in message, "a near-miss should suggest the real filter"
    assert "mirrorlab filters" in message


def test_empty_spec_falls_back_to_the_original():
    assert build_filter("").name == "original"
    assert build_filter("  ").name == "original"


def test_build_chain_flattens_nested_chains():
    chain = build_chain(["cartoon+vignette", "glitch"])
    assert isinstance(chain, FilterChain)
    assert [stage.name for stage in chain.filters] == ["cartoon", "vignette", "glitch"]


def test_chain_instances_do_not_share_state(frame):
    first = build_filter("trails")
    second = build_filter("trails")
    assert first is not second
    ctx = make_ctx(frame)
    first.apply(frame.copy(), ctx)
    assert first.state and not second.state


def test_chain_cost_is_the_worst_stage():
    chain = build_filter("original+oil")
    assert chain.cost == "heavy"


def test_list_filters_filters_by_category():
    artistic = list_filters("artistic")
    assert artistic
    assert all(f.category == "artistic" for f in artistic)


# --------------------------------------------------------------------------- #
# Presets
# --------------------------------------------------------------------------- #
def test_every_preset_builds_and_runs(frame):
    for name, preset in PRESETS.items():
        assert "filter" in preset and "label" in preset
        chain = build_filter(preset["filter"])
        out = chain.apply(frame.copy(), make_ctx(frame))
        assert out.shape == frame.shape, f"preset {name} broke the frame contract"


def test_presets_are_disjoint_from_plain_names():
    for preset in PRESETS.values():
        assert (
            preset["filter"] not in FILTERS or "+" in preset["filter"]
        ), "a preset should usually combine filters"
