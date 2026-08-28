---
title: Reference
description: Look up the exact Sci RAG Kit command, configuration field, API contract, benchmark, or term.
---

# Reference

Generated pages derive from the current Typer and Pydantic definitions. Human-written pages explain contracts that need more context than a signature can provide.

<div class="srag-rows" markdown>

[<span class="srag-row__title">CLI</span><span class="srag-row__copy">Every command, subgroup, argument, option, type, and default exposed by the `sci-rag` Typer application. Generated.</span>](cli.md){ .srag-row }

[<span class="srag-row__title">Configuration</span><span class="srag-row__copy">Runtime environment variables and the validated `domain/domain.yaml` schema, rendered from source models. Generated.</span>](configuration.md){ .srag-row }

[<span class="srag-row__title">REST, MCP, and Python API</span><span class="srag-row__copy">Authentication scopes, endpoint shapes, streaming events, agent tools, errors, and importable entry points.</span>](api.md){ .srag-row }

[<span class="srag-row__title">Benchmarks</span><span class="srag-row__copy">Demo-corpus results with confidence intervals, snapshot provenance, model identifiers, and a reproduction command.</span>](benchmarks.md){ .srag-row }

[<span class="srag-row__title">Glossary</span><span class="srag-row__copy">Project-specific meanings for retrieval, graph, evidence, evaluation, and deployment vocabulary.</span>](glossary.md){ .srag-row }

</div>

If you are looking something up and do not know where it lives: commands are in
[CLI](cli.md), anything with an `SCI_RAG_` prefix or a `domain.yaml` key is in
[Configuration](configuration.md), and request and response shapes are in
[REST, MCP, and Python API](api.md). A word you do not recognize is probably in
the [Glossary](glossary.md).
