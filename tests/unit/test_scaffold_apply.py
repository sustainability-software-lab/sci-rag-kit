"""The appliers: answers in, file content out.

Each applier is a pure ``(ProjectAnswers, Path) -> list[str]`` over a copy of
the template, so these run offline against real repository files rather than
against a hand-written fixture that could drift from what ships.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest

from sci_rag.domain import DomainConfig, EntityTypeSpec, QueryClassSpec, RelationTypeSpec
from sci_rag.ingest.manifest import load_manifest
from sci_rag.scaffold import apply
from sci_rag.scaffold.answers import ProjectAnswers
from sci_rag.scaffold.questions import default_answers

REPO_ROOT = Path(__file__).parents[2]

# The files an applier reads or rewrites. Copied from the real repository so a
# change to any of them shows up here rather than in a user's generated project.
_TEMPLATE_FILES = (
    "pyproject.toml",
    "Makefile",
    ".env.example",
    "README.md",
    ".github/workflows/ci.yml",
)


@pytest.fixture
def template(tmp_path: Path) -> Path:
    root = tmp_path / "template"
    for relative in _TEMPLATE_FILES:
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(REPO_ROOT / relative, destination)
    shutil.copytree(REPO_ROOT / "domain", root / "domain")
    # Stand-ins for the prunable trees: pruning cares that they disappear,
    # not what is inside them.
    (root / "infra" / "terraform").mkdir(parents=True)
    (root / "infra" / "terraform" / "main.tf").write_text("# terraform\n", encoding="utf-8")
    (root / "data" / "demo").mkdir(parents=True)
    (root / "data" / "demo" / "manifest.jsonl").write_text("{}\n", encoding="utf-8")
    (root / "examples").mkdir()
    (root / "examples" / "library_quickstart.py").write_text("# example\n", encoding="utf-8")
    return root


def _answers(**overrides: object) -> ProjectAnswers:
    raw = dict(default_answers())
    raw.update({k: str(v) for k, v in overrides.items()})
    return ProjectAnswers.from_raw(raw)


# --- domain.yaml ------------------------------------------------------------


def test_domain_yaml_round_trips_when_keeping_the_demo_ontology(template: Path) -> None:
    from sci_rag.domain import load_domain

    apply.apply_domain_yaml(
        _answers(project_name="Membrane KB", description="Membranes", ontology="keep_demo_example"),
        template,
    )
    profile = load_domain(template / "domain")
    assert profile.name == "Membrane KB"
    assert profile.config.description == "Membranes"
    # The demo ontology survives as a worked example.
    assert "Feedstock" in profile.entity_type_names


def test_domain_yaml_round_trips_when_blank(template: Path) -> None:
    from sci_rag.domain import load_domain

    apply.apply_domain_yaml(_answers(project_name="Blank KB", ontology="blank"), template)
    profile = load_domain(template / "domain")
    assert profile.name == "Blank KB"
    assert profile.entity_type_names == []
    assert profile.relation_type_names == []


def test_domain_yaml_round_trips_a_drafted_ontology(template: Path) -> None:
    from sci_rag.domain import load_domain

    drafted = DomainConfig(
        name="ignored",
        entity_types=[EntityTypeSpec(name="Membrane", description="A separation layer")],
        relation_types=[RelationTypeSpec(name="REMOVES")],
        query_classes=[QueryClassSpec(name="performance", keywords=["flux"])],
    )
    raw = dict(default_answers())
    raw.update({"project_name": "Membrane KB", "ontology": "draft_with_llm"})
    answers = ProjectAnswers.from_raw(raw, drafted_ontology=drafted)

    apply.apply_domain_yaml(answers, template)
    profile = load_domain(template / "domain")
    # The project name wins over whatever the model called the domain.
    assert profile.name == "Membrane KB"
    assert profile.entity_type_names == ["Membrane"]
    assert profile.relation_type_names == ["REMOVES"]


def test_domain_yaml_carries_the_reranker_answer(template: Path) -> None:
    from sci_rag.domain import load_domain

    apply.apply_domain_yaml(_answers(reranker="local_cross_encoder"), template)
    reranker = load_domain(template / "domain").config.retrieval.reranker
    assert reranker.enabled is True
    assert reranker.adapter == "local"


# --- seed questions ---------------------------------------------------------


def test_seed_questions_are_reset_to_a_guided_blank(template: Path) -> None:
    apply.apply_seed_questions(_answers(), template)
    seeds = (template / "domain" / "eval_seed_questions.jsonl").read_text(encoding="utf-8")
    assert seeds.startswith("# Ground-truth questions")
    assert "rice straw" not in seeds


# --- .env -------------------------------------------------------------------


def test_env_keeps_the_guided_comments_from_the_example(template: Path) -> None:
    apply.apply_env_file(_answers(), template)
    env = (template / ".env").read_text(encoding="utf-8")
    assert "# sci-rag-kit configuration" in env
    assert "# --- Embeddings" in env


def test_env_leaves_illustrative_examples_alone(template: Path) -> None:
    # .env.example documents the provider settings with commented
    # "provider:model" examples. Only the first assignment of a key is the
    # setting; rewriting the later ones with the chosen value would turn a
    # worked example into confidently wrong advice.
    apply.apply_env_file(_answers(llm_model="gemini-2.5-flash"), template)
    env = (template / ".env").read_text(encoding="utf-8")

    assignments = [line for line in env.splitlines() if line.startswith("SCI_RAG_LLM_MODEL=")]
    assert assignments == ["SCI_RAG_LLM_MODEL=gemini-2.5-flash"]
    assert "#   SCI_RAG_LLM_MODEL=anthropic:claude-haiku-4-5" in env


def test_env_for_an_ai_studio_key_enables_only_that_option(template: Path) -> None:
    apply.apply_env_file(_answers(credentials="google_ai_studio"), template)
    env = (template / ".env").read_text(encoding="utf-8")
    assert "\nSCI_RAG_GOOGLE_API_KEY=" in env
    assert "\nSCI_RAG_GCP_PROJECT=" not in env


def test_env_for_vertex_enables_the_project_and_location(template: Path) -> None:
    apply.apply_env_file(_answers(credentials="vertex_ai"), template)
    env = (template / ".env").read_text(encoding="utf-8")
    assert "\nSCI_RAG_GCP_PROJECT=" in env
    assert "\nSCI_RAG_GCP_LOCATION=us-central1" in env
    assert "\nSCI_RAG_GOOGLE_API_KEY=" not in env


def test_env_offline_leaves_both_credential_options_commented(template: Path) -> None:
    apply.apply_env_file(_answers(credentials="offline"), template)
    env = (template / ".env").read_text(encoding="utf-8")
    assert "\nSCI_RAG_GOOGLE_API_KEY=" not in env
    assert "\nSCI_RAG_GCP_PROJECT=" not in env
    assert "\nSCI_RAG_EMBEDDING_PROVIDER=local-hash" in env


def test_env_carries_the_model_answers(template: Path) -> None:
    apply.apply_env_file(_answers(llm_model="gemini-3-pro", embedding_dim="768"), template)
    env = (template / ".env").read_text(encoding="utf-8")
    assert "\nSCI_RAG_LLM_MODEL=gemini-3-pro" in env
    assert "\nSCI_RAG_EMBEDDING_DIM=768" in env


def test_env_writes_the_campaign_mailto_from_the_contact_email(template: Path) -> None:
    apply.apply_env_file(_answers(contact_email="you@lbl.gov"), template)
    env = (template / ".env").read_text(encoding="utf-8")
    assert "\nSCI_RAG_CAMPAIGN_MAILTO=you@lbl.gov" in env


def test_env_omits_the_mailto_when_no_email_was_given(template: Path) -> None:
    apply.apply_env_file(_answers(contact_email=""), template)
    assert "SCI_RAG_CAMPAIGN_MAILTO" not in (template / ".env").read_text(encoding="utf-8")


# --- pyproject.toml ---------------------------------------------------------


def test_pyproject_takes_the_name_and_description(template: Path) -> None:
    apply.apply_pyproject(
        _answers(repo_name="membrane-materials-kb", description="Membrane chemistry"), template
    )
    text = (template / "pyproject.toml").read_text(encoding="utf-8")
    assert 'name = "membrane-materials-kb"' in text
    assert 'description = "Membrane chemistry"' in text


def test_pyproject_drops_extras_the_answers_did_not_select(template: Path) -> None:
    apply.apply_pyproject(_answers(pdf_parser="pypdf", reranker="none"), template)
    text = (template / "pyproject.toml").read_text(encoding="utf-8")
    assert "docling = [" not in text
    assert "rerank = [" not in text
    # Token counting is not driven by any answer, so it always survives.
    assert "tokenizers = [" in text


def test_pyproject_keeps_the_extras_the_answers_selected(template: Path) -> None:
    apply.apply_pyproject(_answers(pdf_parser="docling", reranker="local_cross_encoder"), template)
    text = (template / "pyproject.toml").read_text(encoding="utf-8")
    assert "docling = [" in text
    assert "rerank = [" in text


def test_pyproject_pins_the_answered_python_version(template: Path) -> None:
    apply.apply_pyproject(_answers(python_version="3.11"), template)
    text = (template / "pyproject.toml").read_text(encoding="utf-8")
    assert 'requires-python = ">=3.11"' in text


# --- corpus scaffold --------------------------------------------------------


def test_local_files_corpus_manifest_parses_as_an_empty_manifest(template: Path) -> None:
    apply.apply_corpus_scaffold(_answers(corpus_source="local_files"), template)
    assert (template / "data" / "raw" / ".gitkeep").exists()
    manifest = template / "data" / "corpus.jsonl"
    assert manifest.exists()
    # Every line is a comment, so load_manifest sees a valid, empty manifest.
    assert load_manifest(manifest) == []


def test_doi_list_corpus_writes_a_commented_header(template: Path) -> None:
    apply.apply_corpus_scaffold(_answers(corpus_source="doi_list"), template)
    dois = (template / "data" / "dois.txt").read_text(encoding="utf-8")
    assert dois.lstrip().startswith("#")
    assert "10." in dois


def test_openalex_corpus_writes_a_make_target_with_the_topic(template: Path) -> None:
    apply.apply_corpus_scaffold(
        _answers(
            corpus_source="openalex_topic", openalex_topic="polyamide fouling", max_results=250
        ),
        template,
    )
    makefile = (template / "Makefile").read_text(encoding="utf-8")
    assert "corpus:" in makefile
    assert 'sci-rag campaign build --topic "polyamide fouling" --max-results 250' in makefile


def test_doi_list_make_target_points_at_the_doi_file(template: Path) -> None:
    apply.apply_corpus_scaffold(_answers(corpus_source="doi_list"), template)
    makefile = (template / "Makefile").read_text(encoding="utf-8")
    assert "--doi-file data/dois.txt" in makefile


def test_demo_only_corpus_adds_no_corpus_target(template: Path) -> None:
    apply.apply_corpus_scaffold(_answers(corpus_source="demo_only"), template)
    assert "corpus:" not in (template / "Makefile").read_text(encoding="utf-8")


# --- pruning ----------------------------------------------------------------


def test_declining_terraform_removes_the_tree_and_the_ci_job(template: Path) -> None:
    apply.apply_pruning(_answers(include_terraform="No"), template)
    assert not (template / "infra" / "terraform").exists()
    ci = (template / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "terraform:" not in ci
    assert "hashicorp/setup-terraform" not in ci
    # The jobs after it must survive.
    assert "docs-links:" in ci
    assert "docs:" in ci


def test_keeping_terraform_leaves_the_ci_job_alone(template: Path) -> None:
    apply.apply_pruning(_answers(include_terraform="Yes"), template)
    assert (template / "infra" / "terraform").exists()
    assert "terraform:" in (template / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )


def test_declining_the_demo_corpus_removes_the_demo_and_the_examples(template: Path) -> None:
    """examples/library_quickstart.py reads data/demo, so they go together."""
    apply.apply_pruning(_answers(include_demo_corpus="No"), template)
    assert not (template / "data" / "demo").exists()
    assert not (template / "examples").exists()


def test_pruned_paths_are_not_referenced_by_the_generated_build(template: Path) -> None:
    """The class of bug that breaks a generated repo's very first CI run."""
    apply.apply_pruning(_answers(include_terraform="No", include_demo_corpus="No"), template)
    makefile = (template / "Makefile").read_text(encoding="utf-8")
    ci = (template / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    for surface in (makefile, ci):
        assert "examples" not in surface
        assert "data/demo" not in surface
        assert "infra/terraform" not in surface
    # And the targets that only made sense with a demo corpus are gone.
    assert "demo:" not in makefile
    assert "demo-cloud:" not in makefile
    assert "benchmark:" not in makefile


# --- license ----------------------------------------------------------------


def test_license_is_written_with_the_author_and_year(template: Path) -> None:
    apply.apply_license(
        _answers(author_name="Berkeley Lab", open_source_license="MIT"), template, year=2026
    )
    text = (template / "LICENSE").read_text(encoding="utf-8")
    assert "MIT License" in text
    assert "2026 Berkeley Lab" in text


def test_declining_a_license_removes_the_file(template: Path) -> None:
    (template / "LICENSE").write_text("BSD-3-Clause ...\n", encoding="utf-8")
    apply.apply_license(_answers(open_source_license="No license file"), template, year=2026)
    assert not (template / "LICENSE").exists()


# --- README -----------------------------------------------------------------


def test_readme_opening_is_rewritten_for_the_project(template: Path) -> None:
    apply.apply_readme(
        _answers(project_name="Membrane Materials KB", description="Membrane chemistry"), template
    )
    readme = (template / "README.md").read_text(encoding="utf-8")
    assert readme.startswith("# Membrane Materials KB")
    assert "Membrane chemistry" in readme
    # The kit's own opening is gone.
    assert "A template repository for retrieval-augmented generation" not in readme
    # Everything from the first section heading onward survives.
    assert "## Components" in readme


def test_readme_attribution_uses_the_unhyphenated_display_name(template: Path) -> None:
    """A generated project inherits this line, so the kit's name is spelled once here."""
    apply.apply_readme(_answers(), template)
    readme = (template / "README.md").read_text(encoding="utf-8")
    assert "[Sci RAG Kit](" in readme
    assert "Sci-RAG Kit" not in readme


# --- Makefile ---------------------------------------------------------------


def test_setup_target_installs_the_selected_extras(template: Path) -> None:
    apply.apply_makefile(_answers(pdf_parser="docling", reranker="local_cross_encoder"), template)
    makefile = (template / "Makefile").read_text(encoding="utf-8")
    assert "uv sync --extra docling --extra rerank" in makefile


def test_setup_target_stays_plain_without_extras(template: Path) -> None:
    apply.apply_makefile(_answers(pdf_parser="pypdf", reranker="none"), template)
    makefile = (template / "Makefile").read_text(encoding="utf-8")
    assert "\tuv sync\n" in makefile


# --- the whole run ----------------------------------------------------------


def test_apply_all_reports_every_file_it_touched(template: Path) -> None:
    changes = apply.apply_all(_answers(initialize_git="No"), template, year=2026)
    joined = "\n".join(changes)
    for expected in ("domain/domain.yaml", ".env", "pyproject.toml", "README.md", "LICENSE"):
        assert expected in joined


def test_apply_all_leaves_no_template_placeholder_behind(template: Path) -> None:
    """ADR 0004's constraint, asserted: this is an applier, not a template.

    GitHub Actions expressions (``${{ ... }}``) are real workflow syntax and
    stay; a bare ``{{`` would mean a placeholder leaked into the output.
    """
    apply.apply_all(_answers(initialize_git="No"), template, year=2026)
    placeholder = re.compile(r"(?<!\$)\{\{")
    for path in template.rglob("*"):
        if path.is_file() and path.suffix in {".md", ".toml", ".yaml", ".yml", ".jsonl"}:
            assert not placeholder.search(path.read_text(encoding="utf-8", errors="ignore")), path


def test_git_init_works_where_git_has_no_configured_identity(template: Path) -> None:
    """A fresh machine, a container, and a CI runner all often have none.

    `git commit` refuses to run without a user.email, so without a fallback the
    first commit of a generated project silently does not happen.
    """
    import subprocess

    changes = apply.apply_git(_answers(initialize_git="Yes", author_name="Berkeley Lab"), template)

    assert changes == [apply._log("git", "initialized, 1 commit")]
    log = subprocess.run(
        ["git", "log", "-1", "--format=%an <%ae>"],
        cwd=template,
        capture_output=True,
        text=True,
        check=True,
    )
    assert log.stdout.strip()


def test_a_configured_git_identity_is_not_overridden(template: Path) -> None:
    import subprocess

    subprocess.run(["git", "init"], cwd=template, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "mine@example.org"], cwd=template, check=True)
    subprocess.run(["git", "config", "user.name", "Mine"], cwd=template, check=True)

    identity = apply._git_identity(template, _answers(author_name="Someone Else"))

    assert identity == []
