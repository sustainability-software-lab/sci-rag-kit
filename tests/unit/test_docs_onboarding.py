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
