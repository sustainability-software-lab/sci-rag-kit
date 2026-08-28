# The domain folder

This is where your field lives. Everything the kit knows about your science is
in this folder, and pointing it at a new field never means editing Python.

| File | What it controls |
|------|------------------|
| `domain.yaml` | Your name and description, ontology, HyDE query classes, retrieval tuning, and optional answer compression tuning |
| `prompts/entity_extraction.md` | How chunks become graph entities and relationships |
| `prompts/query_entities.md` | How a question's entities are spotted for graph traversal |
| `prompts/hyde.md` | How the hypothetical-answer search probe is written |
| `prompts/answer.md` | How answers are written and cited |
| `prompts/snippet_compression.md` | How retrieved chunks are relevance-scored and compressed before answering |
| `prompts/community_summary.md` | How graph clusters are summarized |
| `prompts/screening.md` | How campaign abstracts are screened against operator-stated criteria |
| `prompts/judge_grounding.md`, `prompts/judge_correctness.md` | How the evaluation judge grades. Keep the blindness rules intact |
| `prompts/ontology_from_corpus.md`, `prompts/manifest_metadata.md`, `prompts/seed_questions.md`, `prompts/prompt_localization.md` | How `sci-rag draft` asks a model for a first pass at the files above |
| `eval_seed_questions.jsonl` | Your ground truth: the questions the harness scores against |

Prompts are plain Markdown with `$UPPER_CASE` slots filled at runtime
(`$DOMAIN_NAME`, `$QUERY`, `$ENTITY_TYPES`, and so on). Edit the words around
the slots freely. Keep every slot, because a template that lost one loads fine
and fails mid-run.

As shipped, this folder is configured for the demo domain, agricultural
residues, so everything works before you change anything. To make it yours,
run `uv run sci-rag init` and then follow
[Bring your own domain](../docs/bring-your-own-domain.md).

## Start with a draft, not a blank file

`sci-rag draft` does a first pass at every file above, grounded in the
documents you already have. It is faster than typing them, and more importantly
it reads your corpus, so the ontology it proposes is about what your documents
actually discuss.

```
uv run sci-rag draft manifest --folder data/raw   # data/corpus.jsonl
uv run sci-rag draft ontology --from-corpus       # domain.yaml
uv run sci-rag draft questions --count 10         # eval_seed_questions.jsonl
uv run sci-rag draft prompts entity_extraction    # prompts/*.md
```

Each one writes a `.proposed` file for you to review, and each prints its
prompt with `--print-prompt` so you can paste it into any assistant and feed
the reply back with `--from-file`. That path needs no API key and runs through
identical validation.

## Two things stay yours

**Rights.** `license_class` is never set by a model. Every drafted manifest row
says `unknown`, which retrieval treats as unsafe, and a rights decision is
yours to make and record.

**Ground truth.** Drafted seed questions carry a `drafted` tag, and every
evaluation report repeats it until a domain expert removes it. Deleting that
tag is your sign-off. `eval_calibration_labels.jsonl` is not drafted at all: it
exists to calibrate the judge against human judgment, so generating it with a
model would destroy the only measurement it provides.

See [LLM-assisted setup](../docs/llm-assisted-setup.md) for the full workflow.
