"""Rendered-geometry guards for documentation code snippets.

The sibling guard in ``tests/unit/test_docs_code_snippets.py`` reads Markdown, so
it can check what a snippet header *says* but not what the page *looks like*. The
three defects fixed in PR #85 were all invisible to it: two blocks touching with
no gap, a filename bar padded to nearly twice the height its label needs, and a
label indented out of line with the code beneath it. Each of those is a number
you can only get from a browser that has resolved the whole cascade, ours layered
over the theme's.

So this tier renders the built site and measures it. It is deliberately optional:
it needs ``site/`` and a browser, and it skips with instructions when either is
missing, the way the integration tier skips without Postgres. CI runs it in the
job that already builds the site.

The thresholds are loose on purpose. They sit between the broken values and the
current ones so that a deliberate design tweak does not trip them, but a rule
being dropped from the stylesheet does. Current values are in the comments beside
each one.
"""

from __future__ import annotations

import functools
import http.server
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "site"

pytestmark = pytest.mark.docs_render

# Broken was 0px, current is 17px. Anything under this reads as one block with a
# stray divider through it.
MIN_ADJACENT_GAP_PX = 8

# Broken was 56.6px (42.5px tall plus a 14.1px margin that could not collapse
# out of the overflow-hidden wrapper), current is 32.7px.
MAX_FILENAME_BAR_PX = 40

# The label and the first character of code should start on the same vertical
# line. Setting the bar's padding with a shorthand instead of the vertical
# longhands silently pushed the label 8.5px right of the code.
MAX_LABEL_CODE_OFFSET_PX = 4

# Reads every block on the page in one pass so a page costs one round trip.
MEASURE_JS = """
() => {
  const wrappers = [...document.querySelectorAll('.md-typeset .highlight')];
  const boxes = wrappers.map(w => w.getBoundingClientRect());
  return {
    blocks: wrappers.length,
    // Only pairs close enough to be visually adjacent; anything further apart
    // has prose between it and is not what this guards.
    gaps: boxes.slice(1)
      .map((box, i) => Math.round(box.top - boxes[i].bottom))
      .filter(gap => gap >= 0 && gap < 80),
    bars: wrappers.flatMap(wrapper => {
      const label = wrapper.querySelector('.filename');
      if (!label) return [];
      const code = wrapper.querySelector('pre > code');
      const labelStyle = getComputedStyle(label);
      const textLeft = element => {
        const style = getComputedStyle(element);
        return element.getBoundingClientRect().left + parseFloat(style.paddingLeft);
      };
      return [{
        text: label.textContent,
        // The margin renders as empty bar, so the bar is margin plus box.
        height: parseFloat(labelStyle.marginTop) + label.getBoundingClientRect().height,
        labelTextX: textLeft(label),
        codeTextX: code ? textLeft(code) : null,
      }];
    }),
  };
}
"""


def _built_pages() -> list[Path]:
    return sorted(SITE.rglob("*.html"))


@pytest.fixture(scope="module")
def site_origin() -> Iterator[str]:
    """Serve the built site, because file:// resolves the stylesheets differently."""
    if not SITE.is_dir() or not _built_pages():
        pytest.skip(f"no built site at {SITE}; run `make docs` first")

    handler = functools.partial(_QuietHandler, directory=str(SITE))
    # Threading matters: the browser opens several keep-alive connections per
    # page, and a single-threaded server serialises them into a stall.
    with http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler) as server:
        server.daemon_threads = True
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{server.server_address[1]}"
        finally:
            server.shutdown()
            thread.join(timeout=5)


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    """The default handler logs every asset to stderr, which buries test output."""

    def log_message(self, format: str, *args: Any) -> None:
        return


@pytest.fixture(scope="module")
def measurements(site_origin: str) -> list[tuple[str, dict[str, Any]]]:
    """Every page's snippet geometry, measured once and shared by the assertions."""
    playwright = pytest.importorskip(
        "playwright.sync_api",
        reason="playwright is not installed; `uv sync --group docs-test`",
    )

    collected: list[tuple[str, dict[str, Any]]] = []
    with playwright.sync_playwright() as driver:
        try:
            browser = driver.chromium.launch()
        except Exception as exc:  # pragma: no cover - environment guard
            pytest.skip(
                f"no Playwright browser ({type(exc).__name__}); run `playwright install chromium`"
            )
        page = browser.new_page(viewport={"width": 1200, "height": 900})
        for path in _built_pages():
            relative = path.relative_to(SITE).as_posix()
            page.goto(f"{site_origin}/{relative}", wait_until="domcontentloaded")
            collected.append((relative, page.evaluate(MEASURE_JS)))
        browser.close()

    return collected


def test_the_measured_site_is_not_silently_empty(
    measurements: list[tuple[str, dict[str, Any]]],
) -> None:
    """Every assertion below is vacuous if nothing was found, so prove it was."""
    blocks = sum(page["blocks"] for _, page in measurements)
    bars = sum(len(page["bars"]) for _, page in measurements)

    assert len(measurements) > 20, (
        f"expected the full built site, measured {len(measurements)} pages"
    )
    assert blocks > 50, f"expected the documentation's code blocks, measured {blocks}"
    assert bars > 5, f"expected the titled snippets, measured {bars}"


def test_adjacent_code_blocks_stay_visually_separated(
    measurements: list[tuple[str, dict[str, Any]]],
) -> None:
    """Two blocks in a row must not touch, or they read as one block."""
    offenders = [
        f"{name}: {gap}px between adjacent blocks"
        for name, page in measurements
        for gap in page["gaps"]
        if gap < MIN_ADJACENT_GAP_PX
    ]

    assert not offenders, (
        f"adjacent code blocks need at least {MIN_ADJACENT_GAP_PX}px between them: {offenders}"
    )


def test_the_filename_bar_stays_trimmed(
    measurements: list[tuple[str, dict[str, Any]]],
) -> None:
    """The bar holds one short label and should be sized for one short label."""
    offenders = [
        f"{name}: {bar['text']!r} bar is {bar['height']:.1f}px"
        for name, page in measurements
        for bar in page["bars"]
        if bar["height"] > MAX_FILENAME_BAR_PX
    ]

    assert not offenders, (
        f"a filename bar should stay under {MAX_FILENAME_BAR_PX}px tall: {offenders}"
    )


def test_the_filename_label_lines_up_with_the_code_below_it(
    measurements: list[tuple[str, dict[str, Any]]],
) -> None:
    """The label and the code share a left edge; only vertical padding is ours to set."""
    offenders = [
        f"{name}: {bar['text']!r} label starts {bar['labelTextX'] - bar['codeTextX']:.1f}px from the code"
        for name, page in measurements
        for bar in page["bars"]
        if bar["codeTextX"] is not None
        and abs(bar["labelTextX"] - bar["codeTextX"]) > MAX_LABEL_CODE_OFFSET_PX
    ]

    assert not offenders, (
        f"the filename label should start within {MAX_LABEL_CODE_OFFSET_PX}px of the code: {offenders}"
    )
