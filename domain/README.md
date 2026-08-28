# The domain folder

Everything domain-specific lives here, and only here; specializing the
kit to a new field does not involve editing Python.

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
| `prompts/judge_grounding.md`, `prompts/judge_correctness.md` | How the evaluation judge grades (keep the blindness rules intact) |
| `prompts/ontology_from_corpus.md`, `prompts/manifest_metadata.md`, `prompts/seed_questions.md`, `prompts/prompt_localization.md` | How `sci-rag draft` asks a model for a first pass at the files above |
| `eval_seed_questions.jsonl` | Your ground truth: the questions the harness scores against |

Prompts are plain Markdown with `$UPPER_CASE` slots filled at runtime
(`$DOMAIN_NAME`, `$QUERY`, `$ENTITY_TYPES`, and so on). Edit the words
around the slots freely.

As shipped, this folder is configured for the demo domain (agricultural
residues) so everything works out of the box. To make it yours, start
with `uv run python scripts/init_domain.py --help`, then follow
[docs/bring-your-own-domain.md](../docs/bring-your-own-domain.md).

## You do not have to type these files

`sci-rag draft` does a first pass at every file above, grounded in the
documents you already have:

```
uv run sci-rag draft manifest --folder data/raw   # data/corpus.jsonl
uv run sci-rag draft ontology --from-corpus       # domain.yaml
uv run sci-rag draft questions --count 10         # eval_seed_questions.jsonl
uv run sci-rag draft prompts entity_extraction    # prompts/*.md
```

Each proposes a `.proposed` file for you to review rather than writing one, and
each also prints its prompt (`--print-prompt`) so you can paste it into any
assistant and feed the reply back with `--from-file`, no API key required.

Two things stay yours. `license_class` is never set by a model, and drafted
seed questions carry a `drafted` tag that every evaluation report repeats until
a domain expert removes it. `eval_calibration_labels.jsonl` is not drafted at
all: it exists to calibrate the judge against human judgment, so generating it
would defeat the measurement.

See [docs/llm-assisted-setup.md](../docs/llm-assisted-setup.md).
