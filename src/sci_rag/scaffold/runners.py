"""One profile per environment manager.

The kit is wired to a dependency manager in five places: the Makefile, the CI
workflow, the Dockerfile, the dev container, and every command in the docs. If
those five disagree the generated project is broken on its first run, so they
are all rendered from a single :class:`RunnerProfile`. **Nothing else in the
scaffold may hardcode a manager's name**, which is what
``test_scaffold_runner_coherence.py`` checks by generating a project per
manager and looking for a sibling's commands anywhere in the tree.

Four managers ship, and the reasons matter for anyone considering a fifth:

* **uv** is the default and what the template itself uses.
* **pixi** carries conda-forge and PyPI in one manifest, produces a
  multi-platform lock, and its tasks map one to one onto the Makefile targets.
* **conda** is still the default in many academic and national-lab
  environments, where ``environment.yml`` is what institutional setups expect.
* **venv + pip** is the universal fallback for HPC, air-gapped, and
  locked-down images where neither uv nor pixi can be installed.

Poetry, pipenv, and hatch are deliberately excluded. Poetry and pipenv both
fight the PEP 735 ``[dependency-groups]`` this project already uses, and
hatchling is already only the build backend here. Each additional manager
multiplies the generated-project test matrix, so a fifth needs someone to ask
for it. Adding one is a new entry in :data:`PROFILES`, not a redesign.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from string import Template

# Everything below the manager-specific build stage is identical across
# images: the package, the domain profile, and the migrations, so
# `sci-rag db upgrade` can run from a job using this same image.
_DOCKER_RUNTIME_TRAILER = """\
WORKDIR /app
COPY src ./src
COPY domain ./domain
COPY alembic.ini ./
COPY migrations ./migrations
ENV PYTHONUNBUFFERED=1 \\
    SCI_RAG_SERVER_HOST=0.0.0.0
EXPOSE 8080
# Cloud Run injects PORT; sci-rag serve honors it.
CMD ["sci-rag", "serve"]
"""

_DOCKER_HEADER = """\
# Container image for the sci-rag server (Cloud Run friendly).
#
#   docker build -t $SLUG .
#   docker run -p 8080:8080 --env-file .env $SLUG
#
# The image deliberately does NOT include the docling extra; PDF-heavy
# ingestion is better run where you can afford the larger image, or with the
# pypdf fallback.

"""


@dataclass(frozen=True)
class RunnerProfile:
    """Everything manager-specific about a generated project.

    ``run_prefix`` is empty for managers that expect an already-activated
    environment, so always build commands with :meth:`run` rather than by
    concatenating; otherwise those projects get a stray leading space in every
    Makefile recipe.
    """

    key: str
    label: str
    run_prefix: str
    sync_command: str
    manifest: str
    lockfile: str | None
    ci_setup_action: str
    ci_setup_inputs: tuple[tuple[str, str], ...] = ()
    devcontainer_feature: str | None = None
    tool_run_prefix: str = ""
    docker_template: Template = field(default_factory=lambda: Template(""))
    install_url: str = ""
    version_command: str = ""
    interpreter_path: str = ""
    # Extras go in the manifest for manifest-first managers, and on the sync
    # command line for the two that resolve from pyproject at install time.
    extras_on_command_line: bool = False
    # Substrings that identify this manager in rendered output. The coherence
    # test looks for a sibling's tokens; keep them specific enough that a
    # sibling cannot match them by accident.
    tokens: tuple[str, ...] = ()

    def run(self, command: str, *, project_slug: str = "") -> str:
        prefix = self.run_prefix.replace("$SLUG", project_slug or "sci-rag")
        return f"{prefix} {command}".strip()

    def sync(self, *, extras: Sequence[str] = (), groups: Sequence[str] = ()) -> str:
        if not self.extras_on_command_line:
            return self.sync_command
        command = self.sync_command
        if self.key == "uv":
            command += "".join(f" --extra {extra}" for extra in extras)
            command += "".join(f" --group {group}" for group in groups)
            return command
        # venv+pip resolves the whole extra set in one editable install.
        wanted = ["dev", *extras, *groups]
        return command.replace('".[dev]"', f'".[{",".join(dict.fromkeys(wanted))}]"')

    def command_tokens(self) -> tuple[str, ...]:
        return self.tokens

    def tool_run(self, command: str) -> str:
        """Run a one-off tool that is not a project dependency."""
        return f"{self.tool_run_prefix} {command}".strip()

    def ci_setup_yaml(self, *, python_version: str) -> str:
        """The workflow steps that install this manager, ready to splice in."""
        lines = [f"      - uses: {self.ci_setup_action}"]
        if self.ci_setup_inputs:
            lines.append("        with:")
            for name, value in self.ci_setup_inputs:
                lines.append(f"          {name}: {value.replace('$PYTHON', python_version)}")
        return "\n".join(lines)

    def dockerfile(self, *, python_version: str, project_slug: str) -> str:
        header = Template(_DOCKER_HEADER).substitute(SLUG=project_slug)
        body = self.docker_template.substitute(PYTHON=python_version, SLUG=project_slug)
        return header + body + _DOCKER_RUNTIME_TRAILER

    def substitutions_from_uv(self, *, project_slug: str) -> tuple[tuple[str, str], ...]:
        """Ordered text rewrites that turn the uv-wired template into this one.

        Every manager-specific string in a generated project comes from here.
        Order matters: the longest, most specific form has to be replaced
        before its prefix, or `uv sync --extra docling` becomes
        `pixi install --extra docling`.
        """
        if self.key == "uv":
            return ()
        run = self.run("", project_slug=project_slug)
        prefix = f"{run} " if run else ""
        return (
            ("uv sync --group docs", self.sync(groups=("docs",))),
            ("uv sync --all-extras", self.sync(extras=("docling", "tokenizers", "rerank"))),
            ("uv sync --frozen --no-dev", self.sync()),
            ("uv run --directory /path/to/your/repo ", self.mcp_prefix(project_slug=project_slug)),
            ("uv run ", prefix),
            ("uvx ", f"{self.tool_run('')} " if self.tool_run_prefix else ""),
            ("uv --version", self.version_command),
            ("uv.lock", self.lockfile or self.manifest),
            ("astral-sh/setup-uv@v7", self.ci_setup_action),
            ("`uv`", f"`{self.label}`"),
            ("uv sync", self.sync()),
        )

    def mcp_prefix(self, *, project_slug: str) -> str:
        """How an external agent launches this project's MCP server.

        `uv run --directory <path>` has no direct equivalent everywhere: conda
        addresses the environment by name instead of by path, and an activated
        venv addresses it by the interpreter's own path.
        """
        if self.key == "conda":
            return f"conda run -n {project_slug} "
        if self.key == "pixi":
            return "pixi run --manifest-path /path/to/your/repo/pyproject.toml "
        if self.key == "venv+pip":
            return "/path/to/your/repo/.venv/bin/"
        return "uv run --directory /path/to/your/repo "

    def devcontainer_interpreter(self, *, project_slug: str) -> str:
        return self.interpreter_path.replace("$SLUG", project_slug)

    def devcontainer_post_create(self, *, project_slug: str = "") -> str:
        upgrade = self.run("sci-rag db upgrade", project_slug=project_slug)
        return f"{self.sync()} && {upgrade}"


_UV_DOCKER = Template("""\
FROM ghcr.io/astral-sh/uv:python$PYTHON-bookworm-slim AS builder
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev

FROM python:$PYTHON-slim-bookworm
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$$PATH"
""")

# pixi and conda pin the interpreter in their manifest, not in the image tag,
# so $PYTHON is unused here on purpose: repeating the pin in two places is how
# they drift.
_PIXI_DOCKER = Template("""\
FROM ghcr.io/prefix-dev/pixi:bookworm-slim AS builder
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
# Commit pixi.lock and add --locked here once you have one; the lock does not
# exist until the first `pixi install`, so a fresh project could not build.
RUN pixi install --environment default

FROM debian:bookworm-slim
COPY --from=builder /app/.pixi/envs/default /app/.pixi/envs/default
ENV PATH="/app/.pixi/envs/default/bin:$$PATH"
""")

_CONDA_DOCKER = Template("""\
FROM mambaorg/micromamba:1.5-bookworm-slim AS builder
WORKDIR /app
COPY environment.yml README.md ./
COPY src ./src
RUN micromamba create -y -n $SLUG -f environment.yml && micromamba clean --all --yes

FROM mambaorg/micromamba:1.5-bookworm-slim
COPY --from=builder /opt/conda/envs/$SLUG /opt/conda/envs/$SLUG
ENV PATH="/opt/conda/envs/$SLUG/bin:$$PATH"
""")

_VENV_DOCKER = Template("""\
FROM python:$PYTHON-slim-bookworm AS builder
WORKDIR /app
COPY requirements.txt pyproject.toml README.md ./
COPY src ./src
RUN python -m venv /app/.venv \\
    && /app/.venv/bin/pip install --no-cache-dir -r requirements.txt \\
    && /app/.venv/bin/pip install --no-cache-dir --no-deps .

FROM python:$PYTHON-slim-bookworm
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$$PATH"
""")


PROFILES: dict[str, RunnerProfile] = {
    "uv": RunnerProfile(
        key="uv",
        label="uv",
        run_prefix="uv run",
        sync_command="uv sync",
        manifest="pyproject.toml",
        lockfile="uv.lock",
        ci_setup_action="astral-sh/setup-uv@v7",
        ci_setup_inputs=(("python-version", "$PYTHON"), ("enable-cache", "true")),
        devcontainer_feature="ghcr.io/va-h/devcontainers-features/uv:1",
        tool_run_prefix="uvx",
        docker_template=_UV_DOCKER,
        install_url="https://docs.astral.sh/uv/getting-started/installation/",
        version_command="uv --version",
        interpreter_path="${containerWorkspaceFolder}/.venv/bin/python",
        extras_on_command_line=True,
        tokens=("uv run", "uv sync", "uvx", "astral-sh/setup-uv", "uv.lock"),
    ),
    "pixi": RunnerProfile(
        key="pixi",
        label="pixi",
        run_prefix="pixi run",
        sync_command="pixi install",
        manifest="pyproject.toml",
        lockfile="pixi.lock",
        ci_setup_action="prefix-dev/setup-pixi@v0",
        ci_setup_inputs=(("environments", "default"), ("cache", "true")),
        devcontainer_feature="ghcr.io/prefix-dev/devcontainer-features/pixi:0",
        tool_run_prefix="pixi exec",
        docker_template=_PIXI_DOCKER,
        install_url="https://pixi.sh/latest/#installation",
        version_command="pixi --version",
        interpreter_path="${containerWorkspaceFolder}/.pixi/envs/default/bin/python",
        tokens=("pixi run", "pixi install", "pixi exec", "prefix-dev/setup-pixi", "pixi.lock"),
    ),
    "conda": RunnerProfile(
        key="conda",
        label="conda",
        run_prefix="conda run -n $SLUG",
        sync_command="conda env create -f environment.yml",
        manifest="environment.yml",
        lockfile=None,
        ci_setup_action="conda-incubator/setup-miniconda@v3",
        ci_setup_inputs=(
            ("environment-file", "environment.yml"),
            ("python-version", "$PYTHON"),
            ("auto-activate-base", "false"),
        ),
        devcontainer_feature="ghcr.io/devcontainers/features/conda:1",
        tool_run_prefix="conda run -n $SLUG",
        docker_template=_CONDA_DOCKER,
        install_url="https://docs.conda.io/projects/conda/en/latest/user-guide/install/",
        version_command="conda --version",
        interpreter_path="/opt/conda/envs/$SLUG/bin/python",
        tokens=("conda run", "conda env create", "setup-miniconda", "environment.yml"),
    ),
    "venv+pip": RunnerProfile(
        key="venv+pip",
        label="venv + pip",
        run_prefix="",
        sync_command='python -m venv .venv && .venv/bin/pip install -e ".[dev]"',
        manifest="requirements.txt",
        lockfile=None,
        ci_setup_action="actions/setup-python@v5",
        ci_setup_inputs=(("python-version", "$PYTHON"), ("cache", "pip")),
        devcontainer_feature=None,
        tool_run_prefix="",
        docker_template=_VENV_DOCKER,
        install_url="https://packaging.python.org/en/latest/guides/installing-using-pip-and-virtual-environments/",
        version_command="python -m pip --version",
        interpreter_path="${containerWorkspaceFolder}/.venv/bin/python",
        extras_on_command_line=True,
        tokens=("python -m venv", "pip install -e", "actions/setup-python", "requirements.txt"),
    ),
}


def runner_keys() -> list[str]:
    return list(PROFILES)


def get_runner(key: str) -> RunnerProfile:
    try:
        return PROFILES[key]
    except KeyError:
        raise KeyError(
            f"Unknown environment manager {key!r}. Known: {', '.join(PROFILES)}."
        ) from None
