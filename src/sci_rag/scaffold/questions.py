"""The question list: one declaration, used by the wizard and by the docs.

Order is the user-visible contract. It mirrors the shape a scientist expects
when starting a project: identity, then credentials and models, then the
domain itself, then the corpus, then stack choices, then licensing and git.

Every question has a default, so pressing Enter through the whole session
produces a working project rather than a half-configured one. Questions that
only make sense after an earlier answer carry an ``asked_when`` gate instead
of being asked unconditionally and then ignored.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from sci_rag.scaffold.naming import slugify
from sci_rag.scaffold.runners import runner_keys

Answers = Mapping[str, str]

SUPPORTED_PYTHON_VERSIONS = ("3.11", "3.12")


@dataclass(frozen=True)
class Question:
    """One prompt.

    ``default`` may be a callable so a question can derive its suggestion from
    an earlier answer (``repo_name`` from ``project_name``). ``validator``
    returns the normalized value or raises :class:`ValueError` with a message
    the wizard shows before asking again.
    """

    name: str
    prompt: str
    default: str | Callable[[Answers], str]
    choices: tuple[str, ...] | None = None
    help: str = ""
    asked_when: Callable[[Answers], bool] | None = None
    validator: Callable[[str], str] | None = None


def _validate_python_version(value: str) -> str:
    if value not in SUPPORTED_PYTHON_VERSIONS:
        raise ValueError(
            f"Python {value} is not supported. Choose one of "
            f"{' or '.join(SUPPORTED_PYTHON_VERSIONS)}."
        )
    return value


def _validate_positive_int(value: str) -> str:
    try:
        parsed = int(value)
    except ValueError:
        raise ValueError(f"{value!r} is not a whole number.") from None
    if parsed <= 0:
        raise ValueError("Must be greater than zero.")
    return str(parsed)


def _validate_email(value: str) -> str:
    if value and ("@" not in value or value.startswith("@") or value.endswith("@")):
        raise ValueError(f"{value!r} does not look like an email address.")
    return value


QUESTIONS: tuple[Question, ...] = (
    Question("project_name", "project_name", "My Scientific KB"),
    Question("repo_name", "repo_name", lambda a: slugify(a.get("project_name", ""))),
    Question("description", "description", "A short description of your domain."),
    Question("author_name", "author_name", "Your name, lab, or organization"),
    Question(
        "contact_email",
        "contact_email",
        "Sent to OpenAlex, Crossref, and Unpaywall",
        validator=_validate_email,
        help="Polite-pool identification for the metadata APIs. Blank is allowed.",
    ),
    Question("python_version", "python_version", "3.12", validator=_validate_python_version),
    Question(
        "environment_manager",
        "environment_manager",
        # Derived, so registering a profile can never leave this list stale.
        lambda _a: runner_keys()[0],
        choices=tuple(runner_keys()),
    ),
    Question(
        "dependency_file",
        "dependency_file",
        "pyproject.toml",
        choices=("pyproject.toml", "pixi.toml"),
        asked_when=lambda a: a.get("environment_manager") == "pixi",
    ),
    Question(
        "credentials",
        "credentials",
        "google_ai_studio",
        choices=("google_ai_studio", "vertex_ai", "offline"),
    ),
    Question(
        "embedding_provider",
        "embedding_provider",
        "google",
        choices=("google", "local-hash"),
        # Offline projects have no provider to choose; answers.py forces it.
        asked_when=lambda a: a.get("credentials") != "offline",
    ),
    Question("llm_model", "llm_model", "gemini-2.5-flash"),
    Question("embedding_model", "embedding_model", "gemini-embedding-001"),
    Question("embedding_dim", "embedding_dim", "1536", validator=_validate_positive_int),
    Question(
        "ontology",
        "ontology",
        "draft_with_llm",
        choices=("draft_with_llm", "keep_demo_example", "blank"),
    ),
    Question(
        "corpus_source",
        "corpus_source",
        "local_files",
        choices=("local_files", "openalex_topic", "doi_list", "demo_only"),
    ),
    Question(
        "openalex_topic",
        "openalex_topic",
        "your topic",
        asked_when=lambda a: a.get("corpus_source") == "openalex_topic",
    ),
    Question(
        "max_results",
        "max_results",
        "100",
        validator=_validate_positive_int,
        asked_when=lambda a: a.get("corpus_source") == "openalex_topic",
    ),
    Question("pdf_parser", "pdf_parser", "pypdf", choices=("pypdf", "docling")),
    Question("reranker", "reranker", "none", choices=("none", "llm", "local_cross_encoder")),
    Question("include_terraform", "include_terraform", "Yes", choices=("Yes", "No")),
    Question("include_demo_corpus", "include_demo_corpus", "Yes", choices=("Yes", "No")),
    Question(
        "open_source_license",
        "open_source_license",
        "BSD-3-Clause",
        choices=("BSD-3-Clause", "MIT", "Apache-2.0", "No license file"),
    ),
    Question("initialize_git", "initialize_git", "Yes", choices=("Yes", "No")),
)


def default_for(question: Question, answers: Answers) -> str:
    if callable(question.default):
        return question.default(answers)
    return question.default


def is_asked(question: Question, answers: Answers) -> bool:
    return question.asked_when is None or question.asked_when(answers)


def default_answers() -> dict[str, str]:
    """Walk the list applying every default, honouring the gates.

    This is what ``--defaults`` answers with, and it is the base an answers
    file overrides, so a partial file still produces a complete answer set.
    """
    answers: dict[str, str] = {}
    for question in QUESTIONS:
        if is_asked(question, answers):
            answers[question.name] = default_for(question, answers)
    return answers
