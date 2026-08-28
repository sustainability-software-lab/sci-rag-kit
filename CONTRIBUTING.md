# Contributing

Contributions are welcome! Thanks for helping us improve sci-rag-kit. These may take one of two forms:

* **Improvements to the kit itself**: the pipeline, retrieval layers,
  evaluation harness, server, docs. Very welcome.
* **Your domain specialization**: that belongs in **your** copy of the
  template, not here. If you built something reusable while
  specializing (a parser, a collector, an eval pattern), extract the
  reusable part and bring that.

## Development setup

```bash
uv sync --group docs
docker compose up -d --wait
make check          # ruff + mypy + the full test suite
make docs           # generated references + strict build + public-artifact guard
uvx pre-commit install   # optional: run the same lint hooks on every commit
```

The whole suite runs offline (deterministic local embedder, mock LLMs)
against the docker-compose Postgres. If Postgres is not reachable,
integration tests skip with instructions rather than failing.

## The bar for changes

* **Tests come with the change.** Offline by default; anything needing
  real credentials is marked `cloud` and skipped in CI.
* **`make check` is green**: ruff (lint and format), mypy, pytest. CI also
  enforces a coverage floor (see ci.yml), builds the Docker image, checks
  Terraform formatting and validity, and verifies internal doc links. A
  change that lowers coverage below the floor needs tests, not a floor
  edit.
* **Retrieval or eval behavior changes bring receipts**: run
  `sci-rag eval retrieval --ablation` on the demo corpus before and
  after, and put both tables in the PR description. The CI smoke eval
  enforces a floor, but the PR should show the delta.
* **Docs move with behavior.** If a user-visible behavior changed and
  no file in `docs/` changed, the PR is not done.
* **Honest degradation over silent failure**, everywhere: new failure
  modes must be visible in traces, reports, or logs.

## Style notes

Follow what is already here (ruff enforces most of it). Docstrings
explain **why** a module is shaped the way it is, in plain language; write
for the scientist reading this codebase for the first time. No em
dashes in prose. Keep prompts and docs free of unexplained jargon.

## Decision records

Anything that changes an architectural decision, or adds one, gets an ADR
in `docs/adr/`. Follow the existing format: context, decision,
consequences, and the conditions under which we would reverse it.
