"""The homepage session has to be what the wizard actually asks.

The example on `docs/index.md` is the first thing a new user reads, and it is
the one place a stale document is invisible: a question added to
`questions.py` would simply not appear, and nothing would complain. So the page
is generated from the question list, and these tests assert the committed page
and cast still match a fresh render.
"""

from __future__ import annotations

import json
from pathlib import Path
from runpy import run_path

REPO_ROOT = Path(__file__).parents[2]
_MODULE = run_path(str(REPO_ROOT / "scripts" / "render_cast.py"))


def _quick_transcript() -> str:
    return _MODULE["render_transcript"](quick=True)


def _advanced_transcript() -> str:
    return _MODULE["render_transcript"](quick=False)


def test_the_committed_page_matches_a_fresh_render() -> None:
    index = (REPO_ROOT / "docs" / "index.md").read_text(encoding="utf-8")
    assert index == _MODULE["render_index"](index, _quick_transcript(), _advanced_transcript()), (
        "stale page; run make cast"
    )


def test_the_committed_casts_match_fresh_renders() -> None:
    casts = {
        "sci-rag-new.cast": _quick_transcript(),
        "sci-rag-new-advanced.cast": _advanced_transcript(),
    }
    for name, transcript in casts.items():
        cast = (REPO_ROOT / "docs" / "assets" / "casts" / name).read_text(encoding="utf-8")
        assert cast == _MODULE["render_cast"](transcript), f"stale {name}; run make cast"


def test_every_question_appears_in_the_transcript() -> None:
    """The guard that catches a question added without updating the homepage."""
    from sci_rag.scaffold.questions import QUESTIONS, default_answers

    transcript = _advanced_transcript()
    asked = set(default_answers()) | {"openalex_topic", "max_results", "dependency_file"}
    for question in QUESTIONS:
        if question.name in asked:
            assert question.name in transcript, question.name


def test_the_transcript_shows_the_result_not_just_the_questions() -> None:
    transcript = _quick_transcript()
    assert "Writing membrane-materials-kb/" in transcript
    assert "domain/domain.yaml" in transcript
    assert "LICENSE" in transcript
    assert "Done. Membrane Materials KB is yours." in transcript


def test_the_transcript_is_rendered_for_the_manager_it_selected() -> None:
    """The scripted session picks pixi, so no uv command may appear in it."""
    transcript = _advanced_transcript()
    assert "pixi install" in transcript
    assert "pixi run sci-rag doctor" in transcript
    assert "uv run" not in transcript


def test_the_transcript_has_no_trailing_whitespace() -> None:
    """The pre-commit hook strips it, which would make --check fail forever."""
    for transcript in (_quick_transcript(), _advanced_transcript()):
        for line in transcript.splitlines():
            assert line == line.rstrip(), repr(line)


def test_quick_transcript_asks_exactly_the_six_quick_questions() -> None:
    from sci_rag.scaffold.questions import QUESTIONS

    transcript = _quick_transcript()
    for question in QUESTIONS:
        if question.quick:
            assert question.prompt in transcript
        else:
            assert f"Select {question.prompt}\n" not in transcript
            assert f"{question.prompt} (" not in transcript


def test_the_cast_is_valid_asciicast_v2() -> None:
    for transcript in (_quick_transcript(), _advanced_transcript()):
        lines = _MODULE["render_cast"](transcript).splitlines()
        header = json.loads(lines[0])
        assert header["version"] == 2
        assert header["width"] >= 80

        previous = -1.0
        for line in lines[1:]:
            timestamp, code, _ = json.loads(line)
            assert code == "o"
            assert timestamp > previous, "event timestamps must increase"
            previous = timestamp


def test_the_player_assets_are_vendored_not_fetched() -> None:
    """A CDN reference would break the hermetic build and the offline link check."""
    vendor = REPO_ROOT / "docs" / "assets" / "vendor" / "asciinema-player"
    assert (vendor / "asciinema-player.min.js").exists()
    assert (vendor / "asciinema-player.css").exists()
    assert (vendor / "LICENSE").exists()

    mkdocs = (REPO_ROOT / "mkdocs.yml").read_text(encoding="utf-8")
    assert "assets/vendor/asciinema-player/asciinema-player.min.js" in mkdocs
    assert "assets/vendor/asciinema-player/asciinema-player.css" in mkdocs
    assert "cdn.jsdelivr.net" not in (REPO_ROOT / "docs" / "javascripts" / "cast.js").read_text(
        encoding="utf-8"
    )


def test_the_player_mounts_every_cast_on_the_page() -> None:
    script = (REPO_ROOT / "docs" / "javascripts" / "cast.js").read_text(encoding="utf-8")

    assert 'querySelectorAll(".srag-cast")' in script
    assert 'getElementById("srag-cast")' not in script
