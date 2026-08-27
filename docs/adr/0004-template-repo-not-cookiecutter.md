# ADR 0004: A runnable GitHub template repo, not a cookiecutter

**Status:** accepted

## Context

The classic way to ship a project factory is cookiecutter: a repository
full of `{{ cookiecutter.project_slug }}` placeholders, rendered by a
generator into a real project. It parameterizes everything, but the
template itself is dead code: it cannot be browsed comfortably, cannot
run, and cannot be CI-tested as-is, and template bugs are only found by
generating.

## Decision

sci-rag-kit is a **GitHub template repository that is itself a working
application**: real code, a real demo corpus, green CI, "Use this
template" to copy it. Specialization happens in data and configuration
(the `domain/` folder, the corpus manifest, `.env`), not in renamed
Python packages, and a small `scripts/init_domain.py` handles the
cosmetic rebranding (project name, description, seed-question reset).

The Python package deliberately stays `sci_rag` in every derived
project. Renaming an import path buys nothing functional and breaks the
ability to diff against, and pull improvements from, the upstream
template.

## Consequences

* A newcomer evaluates the kit by reading and running it, before
  committing to it; the demo IS the documentation of behavior.
* Template quality is enforced by the same CI as any app.
* We give up cookiecutter-style deep parameterization (license choice,
  layout variants). Acceptable: this template has opinions, and the
  cost of disagreeing with one is a normal code change in your copy.
* A cookiecutter wrapper could be generated mechanically later if a
  downstream community wants one; nothing in this decision blocks it.
