"""Guards for the documentation site's front-door copy and presentation.

The site description is written in three places that a reader compares directly:
the MkDocs metadata, the landing page heading, and the README lead. They drift
apart easily because nothing else links them. The second test keeps the retired
marketing components from being reintroduced by copy-paste, since the hub pages
repeat the same block many times over.
"""

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
MKDOCS = ROOT / "mkdocs.yml"
INDEX = ROOT / "docs" / "index.md"
README = ROOT / "README.md"

RETIRED_CLASSES = (
    "srag-card",
    "srag-kicker",
    "srag-badge",
    "srag-button",
    "srag-capability",
    "srag-pathway-grid",
    "srag-principle-grid",
    "srag-home-cta",
)


def _normalize(text: str) -> str:
    """Collapse wrapping and punctuation so prose can be compared as one line."""
    return re.sub(r"\s+", " ", text).strip().rstrip(".").casefold()


def _site_description() -> str:
    # MkDocs config uses Python-specific YAML tags, so load it as plain strings.
    config = yaml.load(MKDOCS.read_text(), Loader=yaml.BaseLoader)
    return str(config["site_description"])


def test_site_description_is_the_same_sentence_in_all_three_entry_points() -> None:
    description = _normalize(_site_description())

    assert "graphrag factory" not in description, "the description should be plain and technical"

    index_h1 = re.search(r"^#\s+(.+?)\s*(\{.*\})?$", INDEX.read_text(), re.MULTILINE)
    assert index_h1 is not None, "docs/index.md needs a level-one heading"
    assert _normalize(index_h1.group(1)) == description

    assert description in _normalize(README.read_text())


def test_retired_marketing_components_are_not_reintroduced() -> None:
    pages = sorted(ROOT.joinpath("docs").rglob("*.md"))
    stylesheets = sorted(ROOT.joinpath("docs", "stylesheets").glob("*.css"))
    assert pages and stylesheets, "documentation sources should be discoverable"

    offenders = {
        f"{path.relative_to(ROOT)}: {name}"
        for path in pages + stylesheets
        for name in RETIRED_CLASSES
        if name in path.read_text()
    }

    assert not offenders, f"retired components still referenced: {sorted(offenders)}"
