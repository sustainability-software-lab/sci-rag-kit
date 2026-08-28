"""Rendered-geometry guard for the block at the top of every page.

The sibling guard in ``tests/unit/test_docs_page_head.py`` reads the template
and the stylesheet, so it can check what the breadcrumb trail *says* but not
where it *lands*. The promise the page head makes is a promise about pixels:
the trail and the title start at the same height on every page, so moving
between pages does not shift the words under the reader's eye.

Nothing at the Markdown level can see a break in that promise. The two ways it
breaks are both cascade defects. A row that collapses when it has no crumbs
lets the title ride up on the section hub pages, and a row that does not follow
the article when the sidebar docks sits centred over a left-anchored title. The
second one shipped once already and was only caught by measuring.

So this asserts the invariant directly: across every built page, the row and
the title each take exactly one position. It runs at two widths, one either
side of the breakpoint where the theme stops centring the article, because that
breakpoint is where the defect hid last time.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import pytest

pytestmark = pytest.mark.docs_render

# 76.25em is where the theme docks the sidebar and anchors the article beside
# it instead of centring it. The trail has to make the same move.
WIDTHS = (1200, 1440)

# The landing page draws its own masthead, and the theme's error page and the
# copied override templates are not documentation pages.
NOT_PAGES = ("index.html", "404.html", "overrides/")

MEASURE_JS = """
() => {
  const box = element => {
    if (!element) return null;
    const rect = element.getBoundingClientRect();
    return {
      top: Math.round(rect.top),
      left: Math.round(rect.left),
      height: Math.round(rect.height),
    };
  };
  return {
    row: box(document.querySelector('.md-path')),
    title: box(document.querySelector('.md-content h1')),
    crumbs: [...document.querySelectorAll('.md-path__item')].length,
  };
}
"""


@pytest.fixture(scope="module")
def head_measurements(
    measure_pages: Any, built_pages: list[str]
) -> dict[int, list[tuple[str, dict[str, Any]]]]:
    """The page head of every documentation page, at each width, measured once."""
    pages = [page for page in built_pages if not page.startswith(NOT_PAGES)]

    return measure_pages(MEASURE_JS, WIDTHS, pages)


def test_the_measured_pages_are_not_silently_empty(
    head_measurements: dict[int, list[tuple[str, dict[str, Any]]]],
) -> None:
    """Every assertion below is vacuous if nothing was found, so prove it was."""
    for width, pages in head_measurements.items():
        assert len(pages) > 30, f"at {width}px, measured only {len(pages)} pages"
        with_crumbs = sum(1 for _, head in pages if head["crumbs"])
        assert with_crumbs > 25, f"at {width}px, only {with_crumbs} pages rendered any crumb"


def test_every_page_has_a_breadcrumb_row_and_a_title(
    head_measurements: dict[int, list[tuple[str, dict[str, Any]]]],
) -> None:
    """A missing row is the failure mode that lets the title ride up."""
    missing = [
        f"{name} at {width}px is missing its {part}"
        for width, pages in head_measurements.items()
        for name, head in pages
        for part in ("row", "title")
        if head[part] is None
    ]

    assert missing == [], f"the page head is incomplete on these pages: {missing}"


def test_the_breadcrumb_row_lands_in_one_place_on_every_page(
    head_measurements: dict[int, list[tuple[str, dict[str, Any]]]],
) -> None:
    """Including the hub pages, whose row is empty but still occupies its height."""
    drifted = _drift(head_measurements, "row", ("top", "left", "height"))

    assert drifted == {}, f"the breadcrumb row is not at one position: {drifted}"


def test_the_page_title_lands_in_one_place_on_every_page(
    head_measurements: dict[int, list[tuple[str, dict[str, Any]]]],
) -> None:
    """The title's own height varies with wrapping; where it starts must not."""
    drifted = _drift(head_measurements, "title", ("top", "left"))

    assert drifted == {}, f"the page title is not at one position: {drifted}"


def _drift(
    head_measurements: dict[int, list[tuple[str, dict[str, Any]]]],
    part: str,
    dimensions: tuple[str, ...],
) -> dict[str, list[str]]:
    """Report every dimension that took more than one value at a given width."""
    found: dict[str, list[str]] = {}
    for width, pages in head_measurements.items():
        for dimension in dimensions:
            seen = defaultdict(list)
            for name, head in pages:
                seen[head[part][dimension]].append(name)
            if len(seen) > 1:
                found[f"{part}.{dimension} at {width}px"] = [
                    f"{value}px on {len(names)} pages, including {names[0]}"
                    for value, names in sorted(seen.items())
                ]
    return found
