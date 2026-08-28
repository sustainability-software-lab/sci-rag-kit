"""Guards for how the documentation presents code snippets.

Readers copy these blocks into their own project, so a snippet that quotes a
project file has to say which file it came from. The header bar is the only
place that can say it, and a header naming a path that does not exist is worse
than no header at all. These tests keep both halves honest: every header that
is not one of the two environment labels resolves to a real repository path,
and every snippet written in a language this repository only ever uses to quote
a project file carries such a header.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"

# Headers that name where a command runs rather than a file it came from.
ENVIRONMENT_TITLES = frozenset({"Terminal", "Repository root"})

# Files the documentation tells the reader to create, so they are absent from a
# clean checkout. A header may name them; the guard cannot check them on disk.
READER_CREATED_PATHS = frozenset({".env", "data/corpus.jsonl"})

# Languages this repository only uses when quoting a file from the project.
FILE_QUOTING_LANGUAGES = frozenset({"dotenv", "yaml", "jsonl"})

# Planning notes are excluded from the built site, so the site conventions do
# not apply to them.
EXCLUDED_DIRS = ("planning",)

FENCE = re.compile(r"^(?P<marker>```+|~~~+)(?P<info>.*)$")
TITLE = re.compile(r'title="(?P<title>[^"]*)"')


def _site_pages() -> list[Path]:
    return sorted(
        path
        for path in DOCS.rglob("*.md")
        if not any(part in EXCLUDED_DIRS for part in path.relative_to(DOCS).parts)
    )


def _fences(page: Path) -> list[tuple[int, str, str | None]]:
    """Return (line number, language, title) for every opening fence on a page."""
    opened: list[tuple[int, str, str | None]] = []
    marker: str | None = None
    for number, line in enumerate(page.read_text().splitlines(), start=1):
        match = FENCE.match(line)
        if match is None:
            continue
        if marker is None:
            marker = match.group("marker")
            info = match.group("info")
            title = TITLE.search(info)
            opened.append(
                (number, info.split()[0] if info.split() else "", title["title"] if title else None)
            )
        elif match.group("marker").startswith(marker) and not match.group("info").strip():
            marker = None
    return opened


def test_documentation_pages_are_discoverable() -> None:
    # A silently empty scan would make both guards below pass for free.
    pages = _site_pages()
    assert len(pages) > 20, f"expected the full documentation set, found {len(pages)}"
    assert any(_fences(page) for page in pages), "expected fenced code blocks in the docs"


def test_snippet_headers_name_a_real_repository_path() -> None:
    offenders = []
    for page in _site_pages():
        for number, _language, title in _fences(page):
            if title is None or title in ENVIRONMENT_TITLES:
                continue
            # "~/" marks a file at the project root, the way a shell prompt does.
            relative = title[2:] if title.startswith("~/") else title
            if relative not in READER_CREATED_PATHS and not (ROOT / relative).exists():
                offenders.append(
                    f"{page.relative_to(ROOT)}:{number}: {title!r} is not a repository path"
                )
            elif "/" not in relative and not title.startswith("~/"):
                offenders.append(
                    f"{page.relative_to(ROOT)}:{number}: {title!r} should be '~/{relative}'"
                )

    assert not offenders, (
        f"a snippet header must be an environment label or a full repository path: {offenders}"
    )


def test_snippets_that_quote_a_project_file_carry_its_path() -> None:
    offenders = [
        f"{page.relative_to(ROOT)}:{number}: {language} block has no title"
        for page in _site_pages()
        for number, language, title in _fences(page)
        if language in FILE_QUOTING_LANGUAGES and title is None
    ]

    assert not offenders, f"these snippets quote a project file without naming it: {offenders}"
