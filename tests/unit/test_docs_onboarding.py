"""The public onboarding path recommends one command before listing alternatives."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_readme_and_homepage_lead_with_pipx_and_the_main_cli() -> None:
    readme_lead = _read("README.md").partition("## Components")[0]
    homepage = _read("docs/index.md")
    start = homepage.partition("## Start a project")[2].partition("<!-- END KIT ONBOARDING -->")[0]

    assert "pipx install sci-rag-kit" in readme_lead
    assert "`sci-rag new`" in readme_lead
    assert "`sci-rag-new`" not in readme_lead

    assert "Install with pipx." in homepage
    assert "$ pipx install sci-rag-kit\n$ sci-rag new" in start
    assert "quickstart.md#other-ways-in" in start
    assert "Install with pipx, the GitHub template, or a clone." not in homepage


def test_quickstart_puts_the_wizard_before_all_other_routes() -> None:
    quickstart = _read("docs/quickstart.md")
    wizard_at = quickstart.index("### The wizard")
    alternatives_at = quickstart.index("### Other ways in")
    wizard = quickstart[wizard_at:alternatives_at]
    alternatives = quickstart[alternatives_at:].partition("## 2.")[0]

    assert wizard_at < alternatives_at
    assert "$ pipx install sci-rag-kit\n$ sci-rag new" in wizard
    assert "git clone" not in wizard
    assert "git clone" in alternatives
    assert "Use this template" in alternatives
    assert "`sci-rag init`" in alternatives
    assert "dev container" in alternatives


def test_get_started_opens_with_the_install_and_wizard_route() -> None:
    page = _read("docs/get-started.md")
    opening = page.partition("# Get started")[2].partition('<div class="srag-rows"')[0]

    assert "`pipx install sci-rag-kit`" in opening
    assert "`sci-rag new`" in opening
    assert "clean clone" not in opening

    assert "live template repository rather than a generator" not in page
    assert "generator configures the live template" in page
    assert "choose Offline" in page


def test_troubleshooting_explains_all_three_credential_recovery_choices() -> None:
    page = _read("docs/troubleshooting.md")
    credentials = page.partition("## A command needs model credentials")[2].partition(
        "## Retrieval is empty"
    )[0]

    assert "Try a different credential" in credentials
    assert "Switch to an AI Studio key" in credentials
    assert "Continue without a model" in credentials
    assert "keeps your chosen credential mode" in credentials
    assert "worked example ontology" in credentials


def test_generated_projects_strip_the_kit_onboarding_and_both_casts() -> None:
    from sci_rag.scaffold.apply import _strip_marked_regions

    stripped = _strip_marked_regions(_read("docs/index.md"))

    assert "pipx install sci-rag-kit" not in stripped
    assert "sci-rag-new.cast" not in stripped
    assert "sci-rag-new-advanced.cast" not in stripped
    assert "## Components" in stripped


def test_current_guides_name_the_main_project_command() -> None:
    for path in (
        "docs/faq.md",
        "docs/bring-your-own-domain.md",
        "docs/choosing-sci-rag-kit.md",
    ):
        page = _read(path)

        assert "`sci-rag new`" in page, path
        assert "`sci-rag-new`" not in page, path

    readme = _read("README.md")
    assert "| `sci-rag new` |" in readme

    faq = _read("docs/faq.md")
    assert "**Use this template** or cloning" in faq
    assert "same appliers" in faq
    assert "All three leave you with the same tree" not in faq


def test_quick_mode_docs_distinguish_setup_decisions_from_credential_input() -> None:
    homepage = _read("docs/index.md")
    homepage_start = homepage.partition("## Start a project")[2].partition(
        "<!-- END KIT ONBOARDING -->"
    )[0]
    quickstart = _read("docs/quickstart.md")
    quickstart_wizard = quickstart.partition("### The wizard")[2].partition("### Other ways in")[0]

    for section in (homepage_start, quickstart_wizard):
        assert "six setup decisions" in section
        assert "credential value" in section
        assert "Offline" in section

    assert "holding down Enter" not in homepage_start
    assert "pressing Enter" not in _read("docs/faq.md")


def test_quickstart_documents_tty_conveniences_without_changing_defaults() -> None:
    quickstart = _read("docs/quickstart.md")
    wizard = quickstart.partition("### The wizard")[2].partition("### Other ways in")[0]

    assert "first supported environment manager found on `PATH`" in wizard
    assert "`--defaults` or an answers file" in wizard
    assert "`SCI_RAG_GOOGLE_API_KEY`" in wizard
    assert "`GOOGLE_API_KEY`" in wizard
    assert "without displaying its value" in wizard
    assert "masked" in wizard


def test_checkout_setup_documents_modes_and_preflight_boundary() -> None:
    tutorial = _read("docs/bring-your-own-domain.md")
    setup = tutorial.partition("## Step 0: run the setup wizard")[2].partition(
        "## Step 1: collect your documents"
    )[0]

    assert "uv run sci-rag init --advanced" in setup
    assert "`--quick`" in setup
    assert "`--no-tty`" in setup
    assert "does not run the live credential check" in setup
    assert "pressing Enter" not in setup
    assert "| Setup area | Where to review it |" in tutorial
    assert "| Setup area | Quick | Advanced | Where it went |" not in tutorial

    assisted = _read("docs/llm-assisted-setup.md")
    ontology = assisted.partition("## Drafting the ontology against your corpus")[2].partition(
        "## Drafting the corpus manifest"
    )[0]
    assert "`sci-rag new` and `sci-rag init`" in ontology
    assert "Only `sci-rag new` checks the credential" in ontology


def test_advanced_only_project_choices_are_labeled_as_advanced() -> None:
    tour = _read("docs/tour.md")
    postgres = _read("docs/run-postgres.md")
    deploy = _read("docs/deploy-gcp.md")

    assert "`sci-rag new --advanced`" in tour
    assert "`sci-rag new --advanced`" in postgres
    assert "`sci-rag new --advanced`" in deploy
    assert "Quick keeps the default" in postgres
    assert "Quick keeps Terraform" in deploy


def test_troubleshooting_documents_prompt_and_preflight_escape_hatches() -> None:
    page = _read("docs/troubleshooting.md")
    normalized = " ".join(page.split())

    assert "`--no-tty`" in page
    assert "`NO_COLOR`" in page
    assert "`TERM=dumb`" in page
    assert "`--no-preflight`" in page
    assert "only available on `sci-rag new`" in normalized
    assert "does not validate the credential" in normalized
    assert "15-second deadline" in normalized
    assert "never prints the raw provider exception or credential value" in normalized


def test_current_records_describe_the_main_command_and_compatibility_alias() -> None:
    adr = _read("docs/adr/0007-interactive-project-generator.md")
    versioning = _read("docs/VERSIONING.md")
    roadmap = _read("docs/ROADMAP.md")

    assert "**Amended:** 2026-08-28" in adr
    assert "`sci-rag new` is the primary command" in adr
    assert "compatibility alias" in adr
    assert "probe/bin/sci-rag new --defaults" in versioning
    assert "probe/bin/sci-rag-new --help" in versioning
    assert "main `sci-rag new` command" in roadmap


def test_unreleased_changelog_records_the_guided_onboarding_batch() -> None:
    unreleased = _read("CHANGELOG.md").partition("## [Unreleased]")[2].partition("## [0.3.0]")[0]

    assert "`sci-rag new`" in unreleased
    assert "Quick and Advanced" in unreleased
    assert "credential preflight" in unreleased
    assert "plain numbered fallback" in unreleased
    assert "environment manager found on `PATH`" in unreleased
    assert "existing environment key" in unreleased
    assert "shared completion report" in unreleased


def test_wizard_environment_file_is_owner_readable() -> None:
    quickstart = _read("docs/quickstart.md")
    assert "owner-only mode `0600`" in quickstart
