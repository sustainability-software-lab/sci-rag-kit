"""Drift in a published benchmark has to be shown, not absorbed.

`make benchmark` rendered straight over `docs/benchmarks.md`. A run whose
graph came out with 93 entities instead of 83 and whose mean correctness moved
from 1.3 to 1.9 left exactly the same trace as a run that reproduced: a
rewritten file. Whether those numbers are expected model variance or a changed
input is a scientific question, and it cannot be asked if nobody is shown the
move.

So the renderer compares before writing, states the tolerance it is judging
against, and `--check` exits nonzero when a published number has moved outside
it.
"""

from __future__ import annotations

from pathlib import Path
from runpy import run_path

import pytest

# The renderers are scripts rather than package modules, so they are loaded
# the way `test_doc_renderers.py` loads them.
_MODULE: dict | None = None


def _renderer() -> dict:  # type: ignore[type-arg]
    global _MODULE
    if _MODULE is None:
        _MODULE = run_path("scripts/render_benchmarks.py")
    return _MODULE


TOLERANCES = _renderer()["TOLERANCES"]
GRAPH_COUNT_CAVEAT = _renderer()["GRAPH_COUNT_CAVEAT"]
compare_pages = _renderer()["compare_pages"]


def _page(**numbers: object) -> str:
    return (
        "# Benchmarks\n\n"
        f"- Corpus: {numbers.get('documents', 5)} documents, {numbers.get('chunks', 34)} chunks, "
        f"{numbers.get('entities', 83)} entities, {numbers.get('relationships', 79)} "
        f"relationships, {numbers.get('communities', 7)} communities\n"
        "\n| Config | hit@5 |\n|---|---:|\n"
        f"| full_deep | {numbers.get('hit', '0.89')} |\n"
    )


def test_an_identical_render_reports_no_drift() -> None:
    assert compare_pages(_page(), _page()) == []


def test_a_metric_inside_the_tolerance_is_reported_but_not_a_failure() -> None:
    """Small movement on nine questions is noise, and saying so is the point."""
    moved = compare_pages(_page(), _page(hit="0.90"))

    assert moved, "a change always gets reported"
    assert all(not entry.material for entry in moved)


def test_a_graph_that_grew_by_twelve_percent_is_material() -> None:
    """83 to 93 entities is the movement the audit measured."""
    moved = compare_pages(_page(), _page(entities=93))

    material = [entry for entry in moved if entry.material]
    assert material, "the audit's own drift has to fail this"
    assert any("entities" in entry.label for entry in material)


def test_the_tolerances_are_declared_rather_than_implied() -> None:
    """A tolerance nobody can read is not a scientific tolerance."""
    assert set(TOLERANCES) == {"metric", "count"}
    assert 0 < TOLERANCES["metric"] < 0.2
    assert 0 < TOLERANCES["count"] < 0.2


def test_check_mode_exits_nonzero_when_a_published_number_moved(tmp_path: Path) -> None:
    check_against_committed = _renderer()["check_against_committed"]

    committed = tmp_path / "benchmarks.md"
    committed.write_text(_page(), encoding="utf-8")

    with pytest.raises(SystemExit) as caught:
        check_against_committed(_page(entities=93), committed)

    assert caught.value.code != 0


def test_check_mode_passes_when_nothing_material_moved(tmp_path: Path) -> None:
    check_against_committed = _renderer()["check_against_committed"]

    committed = tmp_path / "benchmarks.md"
    committed.write_text(_page(), encoding="utf-8")

    check_against_committed(_page(hit="0.90"), committed)


def test_the_published_page_states_the_tolerance_the_renderer_judges_against() -> None:
    """The page is generated, but only a credentialed run regenerates it.

    `eval_results/` is ignored, so nothing in the repository can re-render this
    page offline. That makes the statement of the tolerance the one part a
    reader can check here, and holding it to the renderer's own constant is
    what stops the two from drifting between benchmark runs.
    """
    page = Path("docs/benchmarks.md").read_text(encoding="utf-8")

    assert f"{TOLERANCES['metric']} absolute on a metric" in page
    assert f"{TOLERANCES['count']:.0%} on a count" in page
    assert "a finding, not a refresh" in page


def test_the_published_page_names_the_graph_counts_as_the_known_exception() -> None:
    """The tolerance claim has a documented counterexample, so the page says so.

    Two reruns from identical recorded inputs moved the entity count 13% down
    and 12% up, both outside the 10% count tolerance the paragraph above
    promises. A reader who runs the command and sees a different entity count
    has reproduced the documented behavior, and the page has to tell them that
    before they go hunting for what they broke.

    Held against the renderer's own constant, the way the tolerance is, so a
    later re-render cannot keep the numbers and drop the caveat.
    """
    page = Path("docs/benchmarks.md").read_text(encoding="utf-8")

    assert GRAPH_COUNT_CAVEAT in page
    assert "does not make the extractor deterministic" in GRAPH_COUNT_CAVEAT
    assert "one draw from a distribution" in GRAPH_COUNT_CAVEAT
