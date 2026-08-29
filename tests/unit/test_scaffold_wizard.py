"""run_wizard: three ways in, one ProjectAnswers out.

--defaults and --answers-file exist so CI and the docs can generate a project
reproducibly; the interactive path is what a user actually sees.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
import yaml

from sci_rag.scaffold.wizard import AnswerFileError, run_wizard


def test_defaults_need_no_input() -> None:
    answers = run_wizard(defaults=True)
    assert answers.project_name == "My Scientific KB"
    assert answers.repo_name == "my-scientific-kb"
    assert answers.environment_manager == "uv"


def test_an_answers_file_overrides_the_defaults(tmp_path: Path) -> None:
    path = tmp_path / "answers.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "project_name": "Membrane Materials KB",
                "description": "Membrane chemistry",
                "corpus_source": "openalex_topic",
                "openalex_topic": "polyamide membrane fouling",
                "max_results": 250,
            }
        ),
        encoding="utf-8",
    )
    answers = run_wizard(answers_file=path)
    assert answers.project_name == "Membrane Materials KB"
    # repo_name still derives from the answered project name.
    assert answers.repo_name == "membrane-materials-kb"
    assert answers.openalex_topic == "polyamide membrane fouling"
    assert answers.max_results == 250


def test_an_answers_file_is_reproducible(tmp_path: Path) -> None:
    path = tmp_path / "answers.yaml"
    path.write_text(yaml.safe_dump({"project_name": "Battery KB"}), encoding="utf-8")
    assert run_wizard(answers_file=path) == run_wizard(answers_file=path)


def test_an_unknown_key_in_an_answers_file_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "answers.yaml"
    path.write_text(yaml.safe_dump({"projct_name": "typo"}), encoding="utf-8")
    with pytest.raises(AnswerFileError, match="projct_name"):
        run_wizard(answers_file=path)


def test_pressing_enter_through_everything_yields_the_defaults() -> None:
    answers = run_wizard(input_stream=io.StringIO("\n" * 40))
    assert answers == run_wizard(defaults=True)


def test_the_interactive_session_asks_in_the_documented_order() -> None:
    output = io.StringIO()
    run_wizard(input_stream=io.StringIO("\n" * 40), output_stream=output)
    transcript = output.getvalue()
    assert transcript.index("project_name") < transcript.index("credentials")
    assert transcript.index("credentials") < transcript.index("corpus_source")
    assert transcript.index("corpus_source") < transcript.index("initialize_git")


def test_choice_questions_are_numbered_like_the_documented_transcript() -> None:
    output = io.StringIO()
    run_wizard(input_stream=io.StringIO("\n" * 40), output_stream=output)
    transcript = output.getvalue()
    assert "Select credentials" in transcript
    assert "1 - google_ai_studio" in transcript
    assert "Choose from [1/2/3]" in transcript


def test_answers_are_read_where_the_gates_open_them() -> None:
    """Choosing OpenAlex opens two follow-ups the default path never asks."""
    replies = []
    for name in _ORDER_WITH_OPENALEX:
        replies.append(_REPLIES.get(name, ""))
    answers = run_wizard(input_stream=io.StringIO("\n".join(replies) + "\n"))
    assert answers.corpus_source == "openalex_topic"
    assert answers.openalex_topic == "polyamide membrane fouling"
    assert answers.max_results == 250


_ORDER_WITH_OPENALEX = [
    "project_name",
    "repo_name",
    "description",
    "author_name",
    "contact_email",
    "python_version",
    "environment_manager",
    "credentials",
    "embedding_provider",
    "llm_model",
    "embedding_model",
    "embedding_dim",
    "ontology",
    "corpus_source",
    "openalex_topic",
    "max_results",
    "pdf_parser",
    "reranker",
    "include_terraform",
    "include_cloud_database",
    "include_demo_corpus",
    "open_source_license",
    "initialize_git",
]

_REPLIES = {
    "corpus_source": "2",
    "openalex_topic": "polyamide membrane fouling",
    "max_results": "250",
    "ontology": "2",
}


def test_an_invalid_choice_is_re_asked() -> None:
    output = io.StringIO()
    # "9" is not a listed credential; the wizard must ask again rather than
    # accept it or crash.
    replies = ["\n"] * 6 + ["\n", "9\n", "3\n"] + ["\n"] * 20
    answers = run_wizard(input_stream=io.StringIO("".join(replies)), output_stream=output)
    assert answers.credentials == "offline"


def test_an_invalid_text_answer_is_re_asked() -> None:
    replies = ["\n"] * 5 + ["3.9\n", "3.11\n"] + ["\n"] * 20
    answers = run_wizard(input_stream=io.StringIO("".join(replies)))
    assert answers.python_version == "3.11"
