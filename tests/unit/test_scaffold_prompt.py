"""Prompt adapter selection and user-visible terminal behavior."""

from __future__ import annotations

import io
import sys
from types import SimpleNamespace

import pytest

from sci_rag.scaffold.prompt import (
    PlainPrompter,
    PromptAborted,
    QuestionaryPrompter,
    make_prompter,
)
from sci_rag.scaffold.questions import Question


class _TTY(io.StringIO):
    def isatty(self) -> bool:
        return True


def test_injected_streams_use_the_plain_prompt_contract() -> None:
    """Scripted callers must never enter a terminal UI event loop."""
    prompter = make_prompter(input_stream=io.StringIO(), output_stream=io.StringIO())

    assert isinstance(prompter, PlainPrompter)


def test_plain_text_prompt_preserves_echo_and_validation_output() -> None:
    """The script-friendly prompt remains an exact line-oriented contract."""

    def validate(value: str) -> str:
        if value != "accepted":
            raise ValueError("use the accepted value")
        return value

    output = io.StringIO()
    prompter = PlainPrompter(io.StringIO("wrong\naccepted\n"), output)

    answer = prompter.text(Question("field", "field", "default", validator=validate), "default")

    assert answer == "accepted"
    assert output.getvalue() == (
        "field (default): wrong\n  use the accepted value\nfield (default): accepted\n"
    )


def test_plain_choice_prompt_preserves_numbered_menu_and_retry_output() -> None:
    output = io.StringIO()
    prompter = PlainPrompter(io.StringIO("9\n2\n"), output)
    question = Question("mode", "mode", "quick", choices=("quick", "advanced"))

    answer = prompter.choice(question, "quick")

    assert answer == "advanced"
    assert output.getvalue() == (
        "Select mode\n"
        "1 - quick\n"
        "2 - advanced\n"
        "Choose from [1/2] (1): 9\n"
        "  '9' is not one of quick, advanced.\n"
        "Select mode\n"
        "1 - quick\n"
        "2 - advanced\n"
        "Choose from [1/2] (1): 2\n"
    )


def test_supported_tty_uses_the_interactive_prompt_adapter(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(sys, "stdin", _TTY())
    monkeypatch.setattr(sys, "stdout", _TTY())
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "xterm-256color")

    assert isinstance(make_prompter(), QuestionaryPrompter)


def _supported_tty(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(sys, "stdin", _TTY())
    monkeypatch.setattr(sys, "stdout", _TTY())
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "xterm-256color")


def test_explicit_plain_mode_overrides_a_supported_tty(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _supported_tty(monkeypatch)

    assert isinstance(make_prompter(plain=True), PlainPrompter)


def test_non_tty_standard_streams_use_plain_prompts(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(sys, "stdin", io.StringIO())
    monkeypatch.setattr(sys, "stdout", io.StringIO())
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "xterm-256color")

    assert isinstance(make_prompter(), PlainPrompter)


def test_no_color_uses_plain_prompts(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _supported_tty(monkeypatch)
    monkeypatch.setenv("NO_COLOR", "1")

    assert isinstance(make_prompter(), PlainPrompter)


@pytest.mark.parametrize("term", ["", "dumb"])
def test_unsupported_term_uses_plain_prompts(monkeypatch, term: str) -> None:  # type: ignore[no-untyped-def]
    _supported_tty(monkeypatch)
    monkeypatch.setenv("TERM", term)

    assert isinstance(make_prompter(), PlainPrompter)


def test_missing_questionary_falls_back_to_plain_prompts(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _supported_tty(monkeypatch)

    def missing(_name: str) -> None:
        raise ImportError("questionary is unavailable")

    monkeypatch.setattr("sci_rag.scaffold.prompt.import_module", missing)

    assert isinstance(make_prompter(), PlainPrompter)


def test_cancelling_an_interactive_question_aborts(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    fake = SimpleNamespace(
        Style=lambda rules: rules,
        text=lambda *_args, **_kwargs: SimpleNamespace(ask=lambda: None),
    )
    monkeypatch.setattr("sci_rag.scaffold.prompt.import_module", lambda _name: fake)
    prompter = QuestionaryPrompter()

    with pytest.raises(PromptAborted, match="Setup cancelled"):
        prompter.text(Question("project", "project", "Default"), "Default")


def test_interactive_choices_show_labels_help_and_recommendation(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    shown: dict[str, object] = {}

    class Choice:
        def __init__(self, title: str, value: str) -> None:
            self.title = title
            self.value = value

    def select(message: str, **kwargs):  # type: ignore[no-untyped-def]
        shown["message"] = message
        shown.update(kwargs)
        return SimpleNamespace(ask=lambda: "vertex_ai")

    fake = SimpleNamespace(Choice=Choice, Style=lambda rules: rules, select=select)
    monkeypatch.setattr("sci_rag.scaffold.prompt.import_module", lambda _name: fake)
    prompter = QuestionaryPrompter()
    question = Question(
        "credentials",
        "credentials",
        "google_ai_studio",
        choices=("google_ai_studio", "vertex_ai", "offline"),
        label="How will you reach a model?",
        choice_help={
            "google_ai_studio": "One free key, no cloud project",
            "vertex_ai": "Billed through a Google Cloud project",
            "offline": "No model calls",
        },
        help="Choose the access mode for this project.",
    )

    assert prompter.choice(question, "google_ai_studio") == "vertex_ai"
    assert shown["message"] == "How will you reach a model?"
    choices = shown["choices"]
    assert isinstance(choices, list)
    assert "One free key, no cloud project" in choices[0].title
    assert "(recommended)" in choices[0].title
    assert "(recommended)" not in choices[1].title
    assert shown["instruction"] == "Choose the access mode for this project."


def test_interactive_text_and_secret_prompts_use_the_right_input_kind(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    shown: list[tuple[str, str, dict[str, object]]] = []

    def prompt(kind: str, answer: str):  # type: ignore[no-untyped-def]
        def build(message: str, **kwargs):  # type: ignore[no-untyped-def]
            shown.append((kind, message, kwargs))
            return SimpleNamespace(ask=lambda: answer)

        return build

    fake = SimpleNamespace(
        Style=lambda rules: rules,
        text=prompt("text", "Membrane KB"),
        password=prompt("password", "not-printed"),
    )
    monkeypatch.setattr("sci_rag.scaffold.prompt.import_module", lambda _name: fake)
    prompter = QuestionaryPrompter()

    assert (
        prompter.text(
            Question("project", "project", "Default", label="Project name", help="Be concise."),
            "Default",
        )
        == "Membrane KB"
    )
    assert (
        prompter.secret(
            Question("key", "key", "", label="API key", secret=True),
            "",
        )
        == "not-printed"
    )
    assert [kind for kind, _message, _kwargs in shown] == ["text", "password"]
    assert shown[0][1] == "Project name"
    assert shown[0][2]["instruction"] == "Be concise."


def test_interactive_menu_returns_machine_value_and_marks_its_default(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    shown: dict[str, object] = {}

    class Choice:
        def __init__(self, title: str, value: str) -> None:
            self.title = title
            self.value = value

    def select(message: str, **kwargs):  # type: ignore[no-untyped-def]
        shown["message"] = message
        shown.update(kwargs)
        return SimpleNamespace(ask=lambda: "quick")

    fake = SimpleNamespace(Choice=Choice, Style=lambda rules: rules, select=select)
    monkeypatch.setattr("sci_rag.scaffold.prompt.import_module", lambda _name: fake)
    prompter = QuestionaryPrompter()

    assert (
        prompter.menu(
            "Setup",
            (("quick", "Quick - Six questions"), ("advanced", "Advanced - Every option")),
            "quick",
        )
        == "quick"
    )
    assert shown["message"] == "Setup"
    choices = shown["choices"]
    assert isinstance(choices, list)
    assert choices[0].value == "quick"
    assert "(recommended)" in choices[0].title


def test_interactive_banner_notes_errors_and_confirmation_are_styled(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    printed: list[tuple[str, object]] = []
    confirmed: dict[str, object] = {}

    def confirm(message: str, **kwargs):  # type: ignore[no-untyped-def]
        confirmed["message"] = message
        confirmed.update(kwargs)
        return SimpleNamespace(ask=lambda: True)

    fake = SimpleNamespace(
        Style=lambda rules: rules,
        print=lambda message, style=None: printed.append((message, style)),
        confirm=confirm,
    )
    monkeypatch.setattr("sci_rag.scaffold.prompt.import_module", lambda _name: fake)
    prompter = QuestionaryPrompter()

    prompter.banner()
    prompter.note("Detected uv on PATH.")
    prompter.error("The key was rejected.")

    assert prompter.confirm("Continue?", default=False) is True
    assert any("Sci RAG Kit" in message for message, _style in printed)
    assert any("Detected uv" in message for message, _style in printed)
    assert any("key was rejected" in message for message, _style in printed)
    assert confirmed["message"] == "Continue?"
    assert confirmed["default"] is False
