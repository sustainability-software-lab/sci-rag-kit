"""Guards for the block at the top of every documentation page.

Every page opens with the same three things in the same order: a clickable
breadcrumb trail, the page title, and a one-line grey lede. A reader moving
between pages should see those three land in the same place every time, so
this module pins both halves of that promise. The source-level tests pin the
inputs (the theme feature, the template override, the stylesheet, and the
Markdown shape of each page). The build test at the end pins the output, by
rendering the real site and looking at what MkDocs actually emitted.
"""

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
MKDOCS = ROOT / "mkdocs.yml"
DOCS = ROOT / "docs"
PATH_PARTIAL = DOCS / "overrides" / "partials" / "path.html"
COMPONENTS_CSS = DOCS / "stylesheets" / "components.css"

# The landing page draws its own masthead and deliberately has no breadcrumb.
HOME = "index.md"

# The theme error page has no place in the nav, and the override templates are
# copied into the build verbatim because custom_dir sits inside docs_dir.
NOT_PAGES = ("404.html", "overrides/")


def _config() -> dict:
    # MkDocs config uses Python-specific YAML tags, so load it as plain strings.
    return yaml.load(MKDOCS.read_text(), Loader=yaml.BaseLoader)


def _nav_pages(nav: object, ancestors: tuple[str, ...] = ()) -> list[tuple[str, tuple[str, ...]]]:
    """Flatten the configured nav into (page path, section titles above it)."""
    found: list[tuple[str, tuple[str, ...]]] = []
    if isinstance(nav, str):
        found.append((nav, ancestors))
    elif isinstance(nav, list):
        for entry in nav:
            found.extend(_nav_pages(entry, ancestors))
    elif isinstance(nav, dict):
        for title, child in nav.items():
            if isinstance(child, str):
                found.append((child, ancestors))
            else:
                found.extend(_nav_pages(child, (*ancestors, title)))
    return found


def _body(page: Path) -> str:
    """Return the page's Markdown with any YAML front matter stripped."""
    text = page.read_text()
    if text.startswith("---\n"):
        _, _, rest = text.partition("---\n")
        _, _, body = rest.partition("---\n")
        return body
    return text


def _resolve_snippets(body: str) -> str:
    """Inline pymdownx snippet includes so the shared root files are checked too."""
    lines = []
    for line in body.splitlines():
        include = re.fullmatch(r'\s*--8<--\s*"(.+)"\s*', line)
        lines.append(_body(ROOT / include.group(1)) if include else line)
    return "\n".join(lines)


def test_breadcrumbs_are_enabled_in_the_theme() -> None:
    features = _config()["theme"]["features"]

    assert "navigation.path" in features, "breadcrumbs are the navigation.path feature"


def test_the_breadcrumb_override_renders_for_a_single_ancestor() -> None:
    """The stock partial hides the trail unless a page is two sections deep."""
    assert PATH_PARTIAL.is_file(), "docs/overrides/partials/path.html should override the theme"
    partial = PATH_PARTIAL.read_text()

    assert "depth > 1" not in partial, "the stock depth gate leaves most pages without a trail"
    assert re.search(r"depth\s*>\s*0", partial), "the trail should render from one ancestor up"
    assert "md-path__list" in partial, "the override should keep the theme's markup contract"


def test_every_navigable_page_has_a_section_above_it() -> None:
    """A page with no ancestor section has nothing to put in its breadcrumb."""
    pages = _nav_pages(_config()["nav"])
    assert pages, "the nav should be discoverable"

    orphans = sorted(page for page, ancestors in pages if not ancestors)

    assert orphans == [], f"these nav pages would render an empty breadcrumb: {orphans}"


# Anything that opens a block other than a paragraph: a heading, an admonition
# or collapsible, a list, a table, a fence, a quote, a tab, or raw HTML. Bold
# lead-ins such as the decision records' "**Status:**" are paragraphs, so the
# list markers have to be the spaced form rather than a bare asterisk.
NOT_A_PARAGRAPH = re.compile(r"(#|!!!|\?\?\?|[-*+]\s|\d+\.\s|\||```|>|<|===\s)")


def test_every_page_opens_with_a_title_and_a_lede_paragraph() -> None:
    """The grey lede is styled as p:first-of-type, so it has to come first."""
    pages = sorted(DOCS.rglob("*.md"))
    assert pages, "documentation sources should be discoverable"

    offenders = []
    for page in pages:
        relative = page.relative_to(DOCS).as_posix()
        if relative == HOME or relative.startswith(("planning/", "assets/")):
            continue
        blocks = [
            block.strip()
            for block in re.split(r"\n\s*\n", _resolve_snippets(_body(page)))
            # Comments render to nothing, so they do not move the visible lede.
            if block.strip() and not block.strip().startswith("<!--")
        ]
        opening = blocks[:2]
        if len(opening) < 2 or not opening[0].startswith("# ") or NOT_A_PARAGRAPH.match(opening[1]):
            offenders.append(relative)

    assert offenders == [], f"these pages do not open with a title then a lede: {offenders}"


def test_the_breadcrumb_row_is_pinned_to_the_content_column() -> None:
    """Without a fixed height the title below the trail drifts between pages."""
    rules = COMPONENTS_CSS.read_text()
    block = re.search(r"^\.md-path\s*\{(.+?)\}", rules, re.DOTALL | re.MULTILINE)

    assert block is not None, "components.css should style .md-path"
    declarations = block.group(1)
    assert "height:" in declarations, "the row needs a fixed height so the title cannot drift"
    assert "max-width:" in declarations, "the row should share the article column's measure"
    assert "margin-inline:" in declarations, "the row should be centred like the article is"
    # Below this breakpoint the theme centres the article; above it the article
    # is anchored beside the docked sidebar, and the trail has to follow or it
    # ends up centred over a left-anchored title.
    assert re.search(
        r"@media[^{]*76\.25em[^{]*\{[^}]*md-sidebar--primary[^}]*\.md-path\s*\{[^}]*"
        r"margin-inline-start:",
        rules,
        re.DOTALL,
    ), "the row needs the theme's docked-sidebar inset too"


def test_the_built_site_puts_a_breadcrumb_on_every_page() -> None:
    """Render the real site and check the emitted HTML, not just its inputs."""
    pytest.importorskip("mkdocs", reason="the docs dependency group is not installed")
    import tempfile

    from mkdocs.commands.build import build
    from mkdocs.config import load_config

    with tempfile.TemporaryDirectory() as out:
        build(load_config(str(MKDOCS), site_dir=out, site_url=""))
        rendered = sorted(Path(out).rglob("*.html"))
        assert rendered, "the build should emit pages"

        missing, unlinked = [], []
        for page in rendered:
            relative = page.relative_to(out).as_posix()
            if relative == "index.html" or relative.startswith(NOT_PAGES):
                continue
            html = page.read_text()
            trail = re.search(r'<nav class="md-path".*?</nav>', html, re.DOTALL)
            if trail is None:
                missing.append(relative)
            elif 'class="md-path__link"' not in trail.group(0):
                unlinked.append(relative)

    assert missing == [], f"these built pages have no breadcrumb: {missing}"
    assert unlinked == [], f"these breadcrumbs are not clickable: {unlinked}"
