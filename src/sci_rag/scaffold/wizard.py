"""The question and answer session.

Three ways in, one answer set out: an interactive session, ``--defaults`` for
a straight-through run, and ``--answers-file`` for reproducible generation in
CI and in the documentation. All three walk the same list in
:mod:`sci_rag.scaffold.questions`, so a question added there is asked by all
three without further wiring.

Prompts are written to the output stream directly rather than through Rich's
prompt helpers. The session transcript is a documented artifact (it is the
example on the homepage), so its exact shape is part of the contract and is
worth more here than styled output.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TextIO

import yaml

from sci_rag.scaffold.answers import ProjectAnswers
from sci_rag.scaffold.questions import QUESTIONS, Question, default_for, is_asked

# Enough re-asks to correct a typo, few enough that a piped stdin cannot spin.
_MAX_ATTEMPTS = 5


class AnswerFileError(ValueError):
    """An answers file named something the wizard does not ask about."""


def _load_answer_file(path: Path) -> dict[str, str]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise AnswerFileError(f"{path} must contain a mapping of question name to answer.")
    known = {question.name for question in QUESTIONS}
    unknown = sorted(set(raw) - known)
    if unknown:
        raise AnswerFileError(
            f"{path} names questions the wizard does not ask: {', '.join(unknown)}. "
            f"Known questions: {', '.join(q.name for q in QUESTIONS)}."
        )
    return {key: str(value) for key, value in raw.items()}


def _read(stream: TextIO) -> str | None:
    """One answer, or ``None`` at end of input."""
    line = stream.readline()
    if line == "":
        return None
    return line.strip()


def _ask_text(question: Question, default: str, stdin: TextIO, stdout: TextIO) -> str:
    for _ in range(_MAX_ATTEMPTS):
        stdout.write(f"{question.prompt} ({default}): ")
        raw = _read(stdin)
        if raw is None:
            return default
        stdout.write(f"{raw}\n" if raw else "\n")
        # An empty answer accepts the default, which questions.py declares and
        # answers.py interprets. Only what the user actually typed is checked;
        # validating the default would re-ask on hints like the contact_email
        # placeholder, silently eating the next answer.
        if not raw:
            return default
        if question.validator is None:
            return raw
        try:
            return question.validator(raw)
        except ValueError as exc:
            stdout.write(f"  {exc}\n")
    return default


def _ask_choice(question: Question, default: str, stdin: TextIO, stdout: TextIO) -> str:
    choices = list(question.choices or ())
    default_index = choices.index(default) + 1 if default in choices else 1
    menu = "/".join(str(i) for i in range(1, len(choices) + 1))

    for _ in range(_MAX_ATTEMPTS):
        stdout.write(f"Select {question.prompt}\n")
        for index, choice in enumerate(choices, start=1):
            stdout.write(f"{index} - {choice}\n")
        stdout.write(f"Choose from [{menu}] ({default_index}): ")
        raw = _read(stdin)
        if raw is None:
            return default
        stdout.write(f"{raw}\n" if raw else "\n")
        if not raw:
            return default
        if raw in choices:
            return raw
        if raw.isdigit() and 1 <= int(raw) <= len(choices):
            return choices[int(raw) - 1]
        stdout.write(f"  {raw!r} is not one of {', '.join(choices)}.\n")
    return default


def collect_answers(
    *,
    defaults: bool = False,
    answers_file: Path | None = None,
    input_stream: TextIO | None = None,
    output_stream: TextIO | None = None,
) -> dict[str, str]:
    """Walk the question list and return the raw string answers.

    Gates are evaluated against the answers gathered so far, which is why this
    is a single ordered pass rather than a dictionary comprehension: whether a
    question is asked at all can depend on the answer above it.
    """
    preset = _load_answer_file(answers_file) if answers_file is not None else {}
    non_interactive = defaults or answers_file is not None
    stdin = input_stream if input_stream is not None else sys.stdin
    stdout = output_stream if output_stream is not None else sys.stdout

    answers: dict[str, str] = {}
    for question in QUESTIONS:
        if not is_asked(question, answers):
            continue
        default = default_for(question, answers)
        if question.name in preset:
            answers[question.name] = preset[question.name]
        elif non_interactive:
            answers[question.name] = default
        elif question.choices:
            answers[question.name] = _ask_choice(question, default, stdin, stdout)
        else:
            answers[question.name] = _ask_text(question, default, stdin, stdout)
    return answers


def run_wizard(
    *,
    defaults: bool = False,
    answers_file: Path | None = None,
    input_stream: TextIO | None = None,
    output_stream: TextIO | None = None,
) -> ProjectAnswers:
    raw = collect_answers(
        defaults=defaults,
        answers_file=answers_file,
        input_stream=input_stream,
        output_stream=output_stream,
    )
    return ProjectAnswers.from_raw(raw)
