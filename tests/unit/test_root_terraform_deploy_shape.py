"""The deploy module has to apply on a project that has never seen Cloud SQL.

`terraform apply` with this module's own defaults failed on a fresh project:

    Error 400: Invalid request: Invalid Tier (db-g1-small) for
    (ENTERPRISE_PLUS) Edition. Use a predefined Tier like
    db-perf-optimized-N-* instead.

The module names a tier and never names an edition, so it inherits whatever
Cloud SQL defaults new instances to. That default moved to `ENTERPRISE_PLUS`,
which rejects the shared-core tiers this module deliberately chooses.

The sibling `dev-database` module already pins `edition = "ENTERPRISE"` and
has a test saying so. This is the same lesson, arriving at the module a
reader of `docs/deploy-gcp.md` actually runs.

Why it went unnoticed: a project with an existing Cloud SQL instance often
resolves differently, so the defaults work nearly everywhere except on the
empty project the deploy guide is written for.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]
MAIN = REPO_ROOT / "infra" / "terraform" / "main.tf"
VARIABLES = REPO_ROOT / "infra" / "terraform" / "variables.tf"

# Tiers Cloud SQL will not accept under ENTERPRISE_PLUS. Named from the
# provider's own rejection rather than from a docs page.
SHARED_CORE_TIERS = ("db-f1-micro", "db-g1-small")


def test_the_deploy_instance_pins_its_edition() -> None:
    """Inheriting the edition means inheriting a default that moves.

    Pinning it is what keeps the cheap tier below valid, and keeps a reader
    from being silently placed on the much more expensive edition.
    """
    text = MAIN.read_text(encoding="utf-8")

    assert re.search(r'edition\s*=\s*"ENTERPRISE"', text), (
        "infra/terraform/main.tf must pin edition, or a moving Cloud SQL "
        "default decides it and rejects the tier this module ships"
    )


def test_the_default_tier_is_one_the_pinned_edition_accepts() -> None:
    """The two settings only make sense together.

    A shared-core tier is correct for a deploy guide's default, and it is
    only valid on ENTERPRISE. If someone raises the edition later, this
    fails rather than letting the pair drift into a 400 at apply time.
    """
    default = re.search(
        r'variable "db_tier".*?default\s*=\s*"([^"]+)"',
        VARIABLES.read_text(encoding="utf-8"),
        re.S,
    )
    assert default, "db_tier must declare a default"

    if default.group(1) in SHARED_CORE_TIERS:
        assert re.search(r'edition\s*=\s*"ENTERPRISE"', MAIN.read_text(encoding="utf-8")), (
            f"{default.group(1)} is a shared-core tier, valid only on ENTERPRISE"
        )


def test_the_seeded_api_keys_value_is_one_the_server_can_boot_on() -> None:
    """The module seeds this secret and the server parses it. They must agree.

    `terraform apply` created every resource and then failed, because the
    seed was `"{}"` and `auth.py` refuses an empty allowlist:

        RuntimeError: SCI_RAG_API_KEYS must be a non-empty JSON object
        Container called exit(1).

    Neither side was individually wrong. The server is right to refuse an
    empty allowlist rather than serve open, and the module is right to want
    a first version so the service has something to mount. Nothing tested
    them together, and `terraform validate` cannot: it is a runtime contract
    between a seeded string and a parser.
    """
    text = MAIN.read_text(encoding="utf-8")

    seed = re.search(
        r'resource "google_secret_manager_secret_version" "api_keys_seed"\s*\{(.*?)\n\}',
        text,
        re.S,
    )
    assert seed, "the module must seed a first api_keys version"

    value = seed.group(1)
    assert value not in ('"{}"', "'{}'"), (
        "seeding an empty object deploys a service that cannot start; "
        "seed a generated key so the deploy comes up secured"
    )
    assert "random_password" in value, (
        "seed a generated key, the way the database password already is, "
        f"rather than a literal: {value}"
    )


def test_every_protectable_resource_honours_the_deletion_protection_input() -> None:
    """A deploy you cannot tear down is not a deploy you should ship.

    `deletion_protection` was written for the database, and reads that way:
    "Protect the database from accidental terraform destroy." The Cloud Run
    provider later grew its own `deletion_protection`, defaulting to true, and
    the service resource never opted in. So a `terraform destroy` with the
    documented `-var deletion_protection=false` removed the database and
    refused the service:

        cannot destroy service without setting deletion_protection=false

    An operator who follows the teardown instructions is left with a running
    service and no documented way to remove it, which matters most for anyone
    evaluating the kit on a project they intend to delete afterwards.
    """
    text = MAIN.read_text(encoding="utf-8")

    missing = []
    for kind, label in (
        ("google_cloud_run_v2_service", "api"),
        ("google_cloud_run_v2_job", "ops"),
    ):
        block = re.search(rf'resource "{kind}" "{label}"\s*\{{(.*?)\n\}}', text, re.S)
        assert block, f"the module must define {kind}.{label}"
        if not re.search(r"deletion_protection\s*=\s*var\.deletion_protection", block.group(1)):
            missing.append(f"{kind}.{label}")

    assert missing == [], (
        f"these must honour var.deletion_protection or terraform destroy cannot "
        f"remove them: {missing}"
    )


# APIs the documented deploy steps call, beyond the ones the module declares.
# `gcloud builds submit` needs both, and neither was listed, so Step 1 failed
# on a project where they were genuinely off:
#   PERMISSION_DENIED: Identity and Access Management (IAM) API has not been
#   used in project <project> before or it is disabled.
REQUIRED_DEPLOY_APIS = (
    "run.googleapis.com",
    "sqladmin.googleapis.com",
    "secretmanager.googleapis.com",
    "artifactregistry.googleapis.com",
    "aiplatform.googleapis.com",
    "cloudbuild.googleapis.com",
    "iam.googleapis.com",
)


def test_the_deploy_guide_enables_every_api_its_own_steps_need() -> None:
    """The prerequisite list has to cover the commands that follow it.

    This is only reachable on a project where the APIs start disabled. Most
    projects have `iam` and `cloudbuild` on incidentally, so the documented
    list worked nearly everywhere and failed for exactly the reader the page
    is written for: someone starting from an empty project.
    """
    guide = (REPO_ROOT / "docs" / "deploy-gcp.md").read_text(encoding="utf-8")

    missing = [api for api in REQUIRED_DEPLOY_APIS if api not in guide]

    assert missing == [], (
        f"docs/deploy-gcp.md must enable every API its steps call; missing: {missing}"
    )


def test_the_ops_job_example_names_a_path_the_image_contains() -> None:
    """An example that always fails is worse than no example.

    `run_ingest_example` printed
    `--args='ingest,--manifest,data/demo/manifest.jsonl'`, and `data/` is
    deliberately excluded from the build context so a private corpus cannot
    be uploaded into an image. Running it verbatim gave:

        FileNotFoundError: 'data/demo/manifest.jsonl'

    `load_manifest` takes a `Path` and calls `read_text`, so pointing the
    example at the corpus bucket is not available either without teaching
    ingest to read `gs://`, which is a feature rather than a fix.

    So the example has to be a command the shipped image can actually run,
    and the corpus precondition has to be stated rather than implied.
    """
    raw = (REPO_ROOT / "infra" / "terraform" / "outputs.tf").read_text(encoding="utf-8")
    # Comments may name the bad path while explaining it. What Terraform
    # actually prints is what a reader copies, so judge only that.
    emitted = "\n".join(line for line in raw.splitlines() if not line.lstrip().startswith("#"))

    assert "data/demo/manifest.jsonl" not in emitted, (
        "the image has no data/ directory; an example naming it always fails"
    )
    assert "corpus" in emitted.lower(), "the corpus bucket's purpose must be documented somewhere"
