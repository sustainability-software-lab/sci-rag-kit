"""The appliers: answers in, files out.

Each function takes the validated answers and a project root and returns a
change log describing what it did. They are ordinary functions over text, so
every one of them is testable offline against a copy of the real template.

There is no templating engine and no placeholder syntax here. The kit stays a
runnable repository; these functions rewrite its configuration in place, which
is why `sci-rag init` can run inside a checkout the user already has.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import yaml

from sci_rag.domain import DomainConfig, RetrievalTuning, load_domain
from sci_rag.scaffold.answers import ProjectAnswers
from sci_rag.scaffold.licenses import render_license

SEED_TEMPLATE = """\
# Ground-truth questions for the evaluation harness (one JSON object per line).
# Write 10 to 20 questions a domain expert can vouch for. Format:
#
# {"id": "unique-slug",
#  "question": "As a user would ask it",
#  "reference_answer": "What a correct answer must say",
#  "reference_titles": ["Exact document title that contains the answer"],
#  "evidence_phrases": ["a distinctive string from the answering passage", "42.7 g/L"],
#  "tags": ["your-label"]}
#
# Include one question the corpus canNOT answer, tagged "unanswerable",
# as an honesty probe. See docs/evaluation.md for advice on writing these.
"""

CORPUS_MANIFEST_TEMPLATE = """\
# Your corpus manifest: one JSON object per line, blank and # lines ignored.
# Only "path" is required; the kit does something sensible with the rest.
#
# {"path": "data/raw/paper.pdf",
#  "title": "Exact document title",
#  "authors": ["Family, Given"],
#  "year": 2024,
#  "doi": "10.0000/example",
#  "journal": "Journal Name",
#  "url": "https://example.org/paper.pdf",
#  "license_class": "public",
#  "source": "my-collection"}
#
# license_class is a rights boundary, not a label: "unknown" is treated as
# unsafe to redistribute. See docs/evidence-and-rights.md.
"""

DOI_FILE_TEMPLATE = """\
# One DOI per line. Blank lines and lines starting with # are ignored.
# Build the corpus from these with `make corpus`.
#
# 10.1016/j.memsci.2023.121000
"""

DOMAIN_YAML_HEADER = """\
# ---------------------------------------------------------------------------
# The domain profile. This file, the prompts/ folder next to it, and
# eval_seed_questions.jsonl are the ONLY things you edit to point the kit at
# a new scientific field. See domain/README.md for a guided walkthrough.
#
# Written by the sci-rag setup wizard. Re-run it with `sci-rag init`, or just
# edit this file: it is validated by the same model the kit reads it with.
# ---------------------------------------------------------------------------
"""

_KIT_URL = "https://github.com/sustainability-software-lab/sci-rag-kit"

# Only these two extras are driven by an answer. tokenizers is orthogonal, so
# it stays in a generated project either way.
_ANSWER_DRIVEN_EXTRAS = ("docling", "rerank")


# The change log is shown to the user and is the example on the docs homepage,
# so the label column is fixed rather than hand-aligned per call site.
_LOG_COLUMN = 23


def _log(label: str, detail: str) -> str:
    # A label wider than the column keeps a minimum gap rather than running
    # into its detail, which is how the documented transcript reads.
    padded = label.ljust(_LOG_COLUMN) if len(label) < _LOG_COLUMN else f"{label}   "
    return f"{padded}{detail}"


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# --- domain profile ---------------------------------------------------------


def _domain_config(answers: ProjectAnswers, root: Path) -> DomainConfig:
    """The ontology the answers ask for, as a validated model.

    Serializing a :class:`DomainConfig` rather than patching YAML text means a
    generated ``domain.yaml`` cannot be something ``load_domain()`` rejects.
    The cost is the demo file's inline commentary, which the header above
    replaces with a pointer to the walkthrough.
    """
    retrieval = RetrievalTuning(reranker=answers.reranker_tuning())

    if answers.ontology == "draft_with_llm" and answers.drafted_ontology is not None:
        drafted = answers.drafted_ontology
        return DomainConfig(
            name=answers.project_name,
            description=answers.description,
            entity_types=drafted.entity_types,
            relation_types=drafted.relation_types,
            query_classes=drafted.query_classes,
            retrieval=retrieval,
        )

    if answers.ontology == "blank":
        return DomainConfig(
            name=answers.project_name, description=answers.description, retrieval=retrieval
        )

    existing = load_domain(root / "domain").config
    return DomainConfig(
        name=answers.project_name,
        description=answers.description,
        entity_types=existing.entity_types,
        relation_types=existing.relation_types,
        query_classes=existing.query_classes,
        retrieval=retrieval,
    )


def apply_domain_yaml(answers: ProjectAnswers, root: Path) -> list[str]:
    config = _domain_config(answers, root)
    body = yaml.safe_dump(
        config.model_dump(mode="json"), sort_keys=False, allow_unicode=True, width=88
    )
    _write(root / "domain" / "domain.yaml", DOMAIN_YAML_HEADER + "\n" + body)
    return [
        _log(
            "domain/domain.yaml",
            f"{len(config.entity_types)} entity types, "
            f"{len(config.relation_types)} relation types, "
            f"{len(config.query_classes)} query classes",
        )
    ]


def apply_seed_questions(answers: ProjectAnswers, root: Path) -> list[str]:
    _write(root / "domain" / "eval_seed_questions.jsonl", SEED_TEMPLATE)
    return [_log("domain/eval_seed_questions.jsonl", "guided blank")]


# --- .env -------------------------------------------------------------------

_ENV_LINE = re.compile(r"^(?P<comment>#\s*)?(?P<key>[A-Z][A-Z0-9_]*)=(?P<value>.*)$")


def apply_env_file(answers: ProjectAnswers, root: Path) -> list[str]:
    """Generate `.env` from `.env.example`, keeping its guided comments.

    The example file is the documentation for these settings, so the generated
    file is the example with values filled in and the credential option the
    user did not choose left commented out, rather than a fresh minimal file.
    """
    api_key = answers.credentials == "google_ai_studio"
    vertex = answers.credentials == "vertex_ai"
    overrides: dict[str, tuple[str, bool]] = {
        "SCI_RAG_GOOGLE_API_KEY": ("", api_key),
        "SCI_RAG_GCP_PROJECT": ("", vertex),
        "SCI_RAG_GCP_LOCATION": ("us-central1", vertex),
        "SCI_RAG_EMBEDDING_PROVIDER": (answers.embedding_provider, True),
        "SCI_RAG_EMBEDDING_MODEL": (answers.embedding_model, True),
        "SCI_RAG_EMBEDDING_DIM": (str(answers.embedding_dim), True),
        "SCI_RAG_LLM_MODEL": (answers.llm_model, True),
    }

    lines: list[str] = []
    substituted: set[str] = set()
    for line in (root / ".env.example").read_text(encoding="utf-8").splitlines():
        match = _ENV_LINE.match(line)
        key = match.group("key") if match else None
        if key in overrides and key not in substituted:
            value, enabled = overrides[key]
            prefix = "" if enabled else "# "
            lines.append(f"{prefix}{key}={value}")
            substituted.add(key)
        else:
            # Only the first assignment of a key is the setting; later ones are
            # illustrative, like the commented "provider:model" examples. They
            # must survive verbatim -- rewriting them with the chosen value
            # turns worked examples into confidently wrong advice.
            lines.append(line)

    if answers.contact_email:
        lines += [
            "",
            "# --- Campaigns (OpenAlex, Crossref, Unpaywall polite pool) ------------------",
            "# Sent as the mailto identifying you to the metadata APIs. They rate-limit",
            "# anonymous traffic harder, so this makes campaigns faster and better behaved.",
            f"SCI_RAG_CAMPAIGN_MAILTO={answers.contact_email}",
            "# An OpenAlex premium key, if your institution has one.",
            "# OPENALEX_API_KEY=",
        ]

    _write(root / ".env", "\n".join(lines) + "\n")
    return [
        _log(
            ".env",
            f"{answers.credentials}, {answers.llm_model}, {answers.embedding_model}",
        )
    ]


# --- pyproject.toml ---------------------------------------------------------


def _drop_block_with_leading_comments(lines: list[str], predicate) -> list[str]:  # type: ignore[no-untyped-def]
    """Remove a line and the comment block that introduces it.

    Configuration files in this repo document each entry with a comment
    directly above it. Dropping the entry without its comment leaves prose
    describing something that is no longer there.
    """
    keep = list(lines)
    for index in range(len(keep) - 1, -1, -1):
        if not predicate(keep[index]):
            continue
        start = index
        while start > 0 and keep[start - 1].lstrip().startswith("#"):
            start -= 1
        del keep[start : index + 1]
    return keep


def apply_pyproject(answers: ProjectAnswers, root: Path) -> list[str]:
    path = root / "pyproject.toml"
    text = path.read_text(encoding="utf-8")

    text = re.sub(r'(?m)^name = ".*"$', f'name = "{answers.repo_name}"', text, count=1)
    text = re.sub(
        r'(?m)^description = ".*"$', f'description = "{answers.description}"', text, count=1
    )
    text = re.sub(
        r'(?m)^requires-python = ">=.*"$',
        f'requires-python = ">={answers.python_version}"',
        text,
        count=1,
    )

    lines = text.splitlines()
    # A project pinned to 3.12 should not advertise 3.11 support.
    dropped = [version for version in ("3.11", "3.12") if version < answers.python_version]
    for version in dropped:
        lines = [
            line
            for line in lines
            if line.strip() != f'"Programming Language :: Python :: {version}",'
        ]

    unwanted = [extra for extra in _ANSWER_DRIVEN_EXTRAS if extra not in answers.extras]
    for extra in unwanted:
        lines = _drop_block_with_leading_comments(
            lines, lambda line, extra=extra: line.startswith(f"{extra} = [")
        )

    _write(path, "\n".join(lines) + "\n")
    kept = ", ".join(answers.extras) or "none"
    return [_log("pyproject.toml", f"name, description, extras: {kept}")]


# --- README -----------------------------------------------------------------


def apply_readme(answers: ProjectAnswers, root: Path) -> list[str]:
    """Replace the kit's opening with the project's, keeping the rest.

    Everything from the first section heading down describes capabilities the
    generated project still has, so only the pitch above it is rewritten.
    """
    path = root / "README.md"
    text = path.read_text(encoding="utf-8")
    match = re.search(r"(?m)^## ", text)
    body = text[match.start() :] if match else ""

    opening = (
        f"# {answers.project_name}\n"
        "\n"
        f"{answers.description}\n"
        "\n"
        f"Built from [Sci-RAG Kit]({_KIT_URL}): hybrid GraphRAG retrieval on PostgreSQL,\n"
        "grounded answers with citations, an evaluation harness, and REST plus MCP\n"
        "endpoints. What makes it this project rather than the kit lives in `domain/`.\n"
        "\n"
    )
    _write(path, opening + body)
    return [_log("README.md", "rewritten opening")]


# --- corpus scaffold --------------------------------------------------------

_CORPUS_TARGET_MARKER = "## corpus: build the document corpus this project was set up for."


def _append_make_target(root: Path, block: str) -> None:
    path = root / "Makefile"
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"(?m)^\.PHONY: (.*)$", lambda m: f".PHONY: {m.group(1)} corpus", text, count=1)
    _write(path, text.rstrip("\n") + "\n\n" + block)


def apply_corpus_scaffold(answers: ProjectAnswers, root: Path) -> list[str]:
    run = answers.runner.run

    if answers.corpus_source == "local_files":
        _write(root / "data" / "raw" / ".gitkeep", "")
        _write(root / "data" / "corpus.jsonl", CORPUS_MANIFEST_TEMPLATE)
        return [_log("data/corpus.jsonl", "commented field shape, ready for your documents")]

    if answers.corpus_source == "openalex_topic":
        command = (
            f'sci-rag campaign build --topic "{answers.openalex_topic}" '
            f"--max-results {answers.max_results}"
        )
        _append_make_target(
            root,
            f"{_CORPUS_TARGET_MARKER}\ncorpus:\n\t{run(command)}\n",
        )
        return [_log("data/campaigns/", f'openalex topic "{answers.openalex_topic}"')]

    if answers.corpus_source == "doi_list":
        _write(root / "data" / "dois.txt", DOI_FILE_TEMPLATE)
        command = "sci-rag campaign build --doi-file data/dois.txt"
        _append_make_target(
            root,
            f"{_CORPUS_TARGET_MARKER}\ncorpus:\n\t{run(command)}\n",
        )
        return [_log("data/dois.txt", "commented header, one DOI per line")]

    return [_log("data/demo/", "kept as the corpus; next step is `make demo`")]


# --- Makefile ---------------------------------------------------------------


def _remove_make_target(text: str, name: str) -> str:
    """Drop a target, its recipe, and the comment and variables above it."""
    lines = text.splitlines()
    start = next(
        (i for i, line in enumerate(lines) if re.match(rf"^{re.escape(name)}:( |$)", line)), None
    )
    if start is None:
        return text

    end = start + 1
    while end < len(lines) and (lines[end].startswith("\t") or not lines[end].strip()):
        end += 1
    # Trailing blanks belong to the separator, not the target; keep exactly one.
    while end > start + 1 and not lines[end - 1].strip():
        end -= 1

    while start > 0 and (
        lines[start - 1].lstrip().startswith("#") or re.match(r"^[A-Z_]+ *:?=", lines[start - 1])
    ):
        start -= 1
    while start > 0 and not lines[start - 1].strip():
        start -= 1
        break

    del lines[start:end]
    return "\n".join(lines) + "\n"


def apply_makefile(answers: ProjectAnswers, root: Path) -> list[str]:
    """Point the task commands at the chosen environment manager.

    Every command comes from the runner profile, so a project generated for a
    different manager cannot end up with another manager's commands here.
    """
    path = root / "Makefile"
    text = path.read_text(encoding="utf-8")

    sync = answers.runner.sync_command
    if answers.extras:
        sync = sync + "".join(f" --extra {extra}" for extra in answers.extras)
    text = re.sub(rf"(?m)^\t{re.escape(answers.runner.sync_command)}$", f"\t{sync}", text, count=1)

    _write(path, text)
    return [_log("Makefile", f"commands prefixed with `{answers.runner.run_prefix}`")]


# --- license ----------------------------------------------------------------


def apply_license(answers: ProjectAnswers, root: Path, *, year: int | None = None) -> list[str]:
    path = root / "LICENSE"
    resolved_year = year if year is not None else datetime.now(tz=UTC).year
    text = render_license(
        answers.open_source_license, author=answers.author_name, year=resolved_year
    )
    if text is None:
        path.unlink(missing_ok=True)
        return [_log("LICENSE", "removed (no license file)")]
    _write(path, text)
    return [_log("LICENSE", answers.open_source_license)]


# --- pruning ----------------------------------------------------------------


def _remove_yaml_job(text: str, name: str) -> str:
    """Drop one job from a GitHub Actions workflow.

    A generated repository whose first CI run fails on a directory the wizard
    deleted is worse than no CI at all, so declining a feature has to take its
    job with it.
    """
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if line == f"  {name}:"), None)
    if start is None:
        return text
    end = start + 1
    while end < len(lines) and not re.match(r"^  \S", lines[end]):
        end += 1
    while end > start + 1 and not lines[end - 1].strip():
        end -= 1
    while start > 0 and not lines[start - 1].strip():
        start -= 1
        break
    del lines[start:end]
    return "\n".join(lines) + "\n"


def _drop_lint_path(text: str, path_name: str) -> str:
    """Remove a directory from every ruff invocation.

    ``ruff check src tests examples scripts`` exits non-zero on a path that
    does not exist, so pruning a tree has to prune it from the lint command in
    both the Makefile and the workflow.
    """
    return re.sub(
        rf"(?m)(ruff (?:check|format --check)[^\n]*?) {re.escape(path_name)}\b", r"\1", text
    )


def apply_pruning(answers: ProjectAnswers, root: Path) -> list[str]:
    removed: list[str] = []

    if not answers.include_terraform:
        shutil.rmtree(root / "infra" / "terraform", ignore_errors=True)
        infra = root / "infra"
        if infra.is_dir() and not any(infra.iterdir()):
            infra.rmdir()
        workflow = root / ".github" / "workflows" / "ci.yml"
        if workflow.exists():
            _write(workflow, _remove_yaml_job(workflow.read_text(encoding="utf-8"), "terraform"))
        removed.append("infra/terraform/")

    if not answers.include_demo_corpus:
        shutil.rmtree(root / "data" / "demo", ignore_errors=True)
        shutil.rmtree(root / "examples", ignore_errors=True)
        makefile = root / "Makefile"
        if makefile.exists():
            text = makefile.read_text(encoding="utf-8")
            for target in ("demo", "demo-cloud", "benchmark"):
                text = _remove_make_target(text, target)
            text = re.sub(r"(?m)^(\.PHONY:.*)$", lambda m: _drop_phony(m.group(1)), text, count=1)
            text = _drop_lint_path(text, "examples")
            _write(makefile, text)
        workflow = root / ".github" / "workflows" / "ci.yml"
        if workflow.exists():
            _write(workflow, _drop_lint_path(workflow.read_text(encoding="utf-8"), "examples"))
        removed.extend(["data/demo/", "examples/"])

    if not removed:
        return []
    return [_log("removed", ", ".join(removed))]


_PRUNED_PHONY = {"demo", "demo-cloud", "benchmark", "clean-demo"}


def _drop_phony(line: str) -> str:
    prefix, _, names = line.partition(":")
    kept = [name for name in names.split() if name not in _PRUNED_PHONY]
    return f"{prefix}: {' '.join(kept)}"


# --- git --------------------------------------------------------------------


def apply_git(answers: ProjectAnswers, root: Path) -> list[str]:
    """Initialize a repository, but never touch one that already exists.

    `sci-rag init` runs inside a checkout the user already has, so re-running
    `git init` there would be, at best, surprising.
    """
    if not answers.initialize_git or (root / ".git").exists():
        return []
    try:
        for command in (["init"], ["add", "-A"], ["commit", "-m", "Initial commit"]):
            subprocess.run(["git", *command], cwd=root, check=True, capture_output=True, text=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        return [_log("git", f"not initialized ({type(exc).__name__})")]
    return [_log("git", "initialized, 1 commit")]


# --- the whole run ----------------------------------------------------------


def apply_all(
    answers: ProjectAnswers, root: Path, *, year: int | None = None, allow_git: bool = True
) -> list[str]:
    """Run every applier in dependency order and return the combined log.

    Pruning goes first so the later writers never touch a file that is about
    to be deleted, and the corpus scaffold goes after the Makefile writer so
    its new target lands at the end.

    ``allow_git`` is off for `sci-rag init`, which specializes a checkout the
    user already has. The ``initialize_git`` answer belongs to a run that
    creates the directory, and honouring it in an existing repository would
    mean initializing on top of the user's own history.
    """
    changes: list[str] = []
    changes += apply_pruning(answers, root)
    changes += apply_domain_yaml(answers, root)
    changes += apply_seed_questions(answers, root)
    changes += apply_env_file(answers, root)
    changes += apply_pyproject(answers, root)
    changes += apply_makefile(answers, root)
    changes += apply_corpus_scaffold(answers, root)
    changes += apply_license(answers, root, year=year)
    changes += apply_readme(answers, root)
    if allow_git:
        changes += apply_git(answers, root)
    changes += [_log("note", note) for note in answers.coercions]
    return changes
