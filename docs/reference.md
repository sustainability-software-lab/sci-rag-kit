---
title: Reference
description: Look up the exact command, configuration field, file format, API contract, benchmark, or term.
---

# Reference

Three pages are generated from the source and checked by the build: the CLI page from the command definitions, the configuration page from the settings and domain models, and the benchmarks page from the evaluation reports. The others are hand-written.

<div class="srag-rows" markdown>

[<span class="srag-row__title">CLI</span><span class="srag-row__copy">Every command, argument, option, type, and default. Generated.</span>](cli.md){ .srag-row }

[<span class="srag-row__title">Configuration</span><span class="srag-row__copy">Environment variables, the `domain/domain.yaml` fields, and the row formats of the corpus manifest and the seed questions. Generated.</span>](configuration.md){ .srag-row }

[<span class="srag-row__title">REST, MCP, and Python API</span><span class="srag-row__copy">Authentication, endpoints, streaming events, agent tools, error codes, and importable entry points.</span>](api.md){ .srag-row }

[<span class="srag-row__title">Benchmarks</span><span class="srag-row__copy">Demo-corpus results with confidence intervals, snapshot provenance, model identifiers, and the reproduction command.</span>](benchmarks.md){ .srag-row }

[<span class="srag-row__title">Glossary</span><span class="srag-row__copy">What each term means in this project.</span>](glossary.md){ .srag-row }

</div>

Commands are in [CLI](cli.md). Anything with an `SCI_RAG_` prefix, a `domain.yaml` key, or a field in `data/corpus.jsonl` or `domain/eval_seed_questions.jsonl` is in [Configuration](configuration.md). Request and response shapes are in [REST, MCP, and Python API](api.md).
