# Changelog

Notable changes to sci-rag-kit. The format follows
[Keep a Changelog](https://keepachangelog.com/); versions follow
[Semantic Versioning](https://semver.org/) once past 1.0.

## [Unreleased]

### Added

- `sci-rag init`: an interactive setup wizard that specializes a checkout
  for your own domain. Asks about the project, credentials and models,
  ontology, corpus source, PDF parser, reranker, license, and stack, then
  writes `domain/domain.yaml`, `.env`, `pyproject.toml`, the `Makefile`,
  `README.md`, and the corpus scaffold. `--defaults` and `--answers-file`
  make generation reproducible; `--dry-run` previews it. The ontology can
  be drafted by the configured model and is validated against
  `DomainConfig` before anything is written, so a malformed draft is
  rejected rather than saved as unusable YAML.
- `domain/prompts/ontology_draft.md`: the prompt behind that draft.
- Multi-provider generation. `SCI_RAG_LLM_MODEL` and friends now accept a
  `provider:model` spec selecting `google`, `anthropic` (Claude on Vertex AI
  or the direct API), or `openai-compatible` (Vertex Model Garden partner
  models such as Grok, Llama, Mistral, and DeepSeek; also OpenAI and
  self-hosted vLLM/Ollama). New `anthropic` and `openai` extras; the SDKs are
  imported lazily so a Google-only install carries neither. See ADR 0006 for
  why the adapters are hand-written and why embeddings stay Google-only.
- `SCI_RAG_JUDGE_MODEL`, so the evaluation judge can run on a different
  provider than the generator. Answer eval reports now record which model
  answered and which graded, making cross-provider judging auditable.
- `sci-rag doctor` reports the resolved spec per role and checks credentials
  for each generation provider in use.

- Environment manager choice in the wizard: pixi, conda, and venv+pip
  alongside uv. One `RunnerProfile` renders all five uv-wired surfaces
  (task commands, CI, Dockerfile, dev container, docs), writes whatever
  manifest that manager needs (`[tool.pixi]` tables or `pixi.toml`,
  `environment.yml`, `requirements.txt` plus `requirements-dev.txt`), and
  is the only place a manager-specific string lives.
- `generated-projects.yml`: a CI matrix that generates a project per
  manager and runs that project's own lint, typecheck, and offline demo.
  uv runs on every pull request; all four run nightly, on release tags,
  and on any pull request that changes what a generated project looks
  like.

- `sci-rag-new`: the project factory as its own entry point. Runs from a
  parent directory with nothing cloned, fetches the template at the tag
  matching its own installed version, then applies the wizard's answers.
  `--template-path` generates from a local checkout with no network, and
  `--ref` overrides the tag. The LLM ontology draft is offered here and in
  `sci-rag init`, with accept, reject, and redraft.
- `.github/workflows/release.yml`: tag-driven publishing to TestPyPI and
  then PyPI over Trusted Publishing, gated on the `ci` workflow having
  passed for the tagged commit and on the tag matching the packaged
  version. The one-time maintainer setup is in `docs/VERSIONING.md`.

### Changed

- `.env` now reaches the process environment. pydantic-settings reads it
  into `Settings` but never exported it, so Typer's `envvar=` lookups and
  the `OPENALEX_API_KEY` read in `sci-rag campaign discover` could not see
  values placed there. A real environment variable still wins over the
  file.
- `scripts/init_domain.py` is now a thin shim over `sci_rag.scaffold`, so
  it and the wizard cannot disagree about what a seed-question reset looks
  like. Its command line, dry-run behavior, and output are unchanged.

- A bare model id still resolves to `SCI_RAG_LLM_PROVIDER` (default `google`),
  so existing configurations keep working unchanged.
- `GoogleLLM` moved from `sci_rag.llm.client` to `sci_rag.llm.google`, matching
  the layout of `sci_rag.embed`. `sci_rag.llm` re-exports it as before.
- Retry policy is shared across providers in `retry_async()`, and status-code
  detection no longer matches a code embedded in a longer number.

### Fixed

- `sci-rag doctor --probe` no longer warns on a healthy setup. Its generation
  probe capped output at 10 tokens, which reasoning models spend on thought
  before writing anything, so a working provider looked like it returned
  nothing.
- The Vertex Model Garden endpoint is now derived correctly for the `global`
  location, which is served by an unprefixed host. Grok is offered *only*
  globally, so the previous URL made it unreachable.
- The OpenAI-compatible adapter closes its response stream, returning the
  connection to the pool when a consumer stops early.
- `sci-rag init` no longer rewrites the commented examples in `.env.example`
  with the answers it collected. Only the first assignment of a key is the
  setting; substituting the later illustrative ones turned worked examples
  into confidently wrong advice and emitted the same key several times.


## [0.2.0] - 2026-08-27

The "Credibility" release: the gaps between what the methodology
document promised and what the code did are closed, and the launch
package (roadmap, governance, comparison, benchmarks) is in place.

### Added

- Post-fusion reranker stage: `Reranker` protocol with an LLM adapter
  (default, zero new dependencies) and a local cross-encoder adapter
  behind the new `rerank` extra; per-request `include_rerank`
  overrides on the retriever and `/v1/query`; honest `rerank` stage
  traces with fused-order fallback on any failure. Off by default
  pending ablation evidence.
- Eval statistics: bootstrap 95% confidence intervals on every
  reported mean (question-level resampling, stdlib only,
  deterministic), small-sample warnings below 10 questions, paired
  bootstrap comparisons, and nDCG@10 alongside hit@k/MRR.
- `sci-rag eval diff`: per-question rank moves (improved, regressed,
  appeared, disappeared) and paired metric deltas with significance
  between any two eval runs; answers-mode dimension diffs.
- `sci-rag eval calibrate`: Cohen's kappa per judge dimension against
  human labels, agreement matrices, calibration sections appended to
  answers reports; ships a non-expert seed label set for the demo
  corpus (`domain/eval_calibration_labels.jsonl`).
- `sci-rag embed reindex`: find and re-embed rows stamped by retired
  embedder versions, batch-committed and idempotent; refuses
  cross-dimension reindexes; community summaries now carry embedding
  version stamps (migration 0002).
- `sci-rag corpus delete` + `sci-rag graph gc`: transactional document
  deletion that scrubs graph evidence arrays, drops evidenced
  relationships and affected communities, and a garbage-collection
  sweep for evidence-less entities and dangling pointers; regression
  test proves deleted content unreachable through every retrieval
  layer.
- `sci-rag corpus snapshot`: named, immutable corpus fingerprints
  (counts, per-document content hashes, embedding versions, git
  commit, corpus digest); eval runs record the snapshot name via
  `--snapshot`.
- Adaptive routing: `--profile auto` resolves per query through
  transparent heuristics (multi-hop, overview, lookup cues) with
  reasons, an optional ambiguity-only LLM fallback, a router trace,
  and `--explain-routing`; default profile unchanged pending the
  published ablation.
- `docs/benchmarks.md`: measured demo-corpus results (all ablation
  configs including rerank and routing, judged answers, judge
  calibration) with confidence intervals, corpus snapshot, commit and
  model ids, reproducible via `make benchmark`.
- `docs/operations.md`: backup/restore runbook (pg_dump, Cloud SQL,
  restore drill, Parquet export note).
- Launch package: `docs/ROADMAP.md` (waves 2-3, UW SSEC collaboration
  seams, BioCirV flagship, launch-gated decisions),
  `docs/VERSIONING.md` (0.x rules, 1.0 criteria),
  `docs/GOVERNANCE.md`, `docs/choosing-sci-rag-kit.md` (honest
  comparison), `ADOPTERS.md`, and a runnable
  `examples/bring_your_own_domain.ipynb` (verified offline).
- Doctor: embedding-version staleness and graph-hygiene checks.

### Changed

- Retrieval eval reports state n and a 95% CI everywhere a mean
  appears; retrieval tables gained an nDCG@10 column.
- `/v1/query` accepts `profile: "auto"` and `include_rerank`.

## [0.1.0a0] - 2026-08-26

First working release of the template.

### Added

- Ingestion: Docling/pypdf/Markdown parsing, structure-aware chunking
  (section breadcrumbs, intact tables, 800/150 token defaults),
  content-hash deduplication, per-document license classes, JSONL corpus
  manifests.
- Storage: single-Postgres schema (Alembic) with pgvector HNSW and
  full-text GIN indexes; embedding version stamping.
- Embeddings: Google `gemini-embedding-001` at 1536 dimensions
  (Matryoshka, re-normalized) via AI Studio key or Vertex AI; a
  deterministic offline hash embedder for tests and dry runs.
- Knowledge graph: ontology-constrained LLM extraction with evidence
  provenance, incremental stamping, deterministic label-propagation
  communities with LLM summaries.
- Retrieval: five layers (vector, keyword, graph traversal, community
  summaries, HyDE) with weighted RRF fusion, interactive/deep profiles,
  per-stage timeouts and traces, fail-closed license/source/exclusion
  scoping inside every layer.
- Answering: numbered inline citations, refusal when nothing is in
  scope, streaming events.
- Evaluation: seed questions, hit@k/MRR with seven ablation configs, a
  two-pass blind judge (grounding never sees the reference answer),
  fingerprint-stamped JSON and Markdown reports, a CI smoke eval.
- Serving: FastAPI `/v1` (SSE answers, RFC 9457 errors, request ids,
  scoped API keys with rate limits, BYO LLM key) and an MCP server with
  seven tools and two resources, over streamable HTTP and stdio.
- Operations: `sci-rag doctor`, docker-compose Postgres, Dockerfile,
  validated Terraform for Cloud SQL + Cloud Run, GitHub Actions CI.
- Template ergonomics: `domain/` specialization surface,
  `scripts/init_domain.py`, offline synthetic demo corpus with seed
  questions and committed real-model eval reports, full documentation
  suite with ADRs.
