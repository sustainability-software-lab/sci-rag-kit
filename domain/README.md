# The domain folder

Everything domain-specific lives here, and only here; specializing the
kit to a new field does not involve editing Python.

| File | What it controls |
|------|------------------|
| `domain.yaml` | Your name and description, the ontology (entity and relationship types the graph extractor looks for), HyDE query classes, and retrieval tuning (fusion weights, candidate limits) |
| `prompts/entity_extraction.md` | How chunks become graph entities and relationships |
| `prompts/query_entities.md` | How a question's entities are spotted for graph traversal |
| `prompts/hyde.md` | How the hypothetical-answer search probe is written |
| `prompts/answer.md` | How answers are written and cited |
| `prompts/community_summary.md` | How graph clusters are summarized |
| `prompts/judge_grounding.md`, `prompts/judge_correctness.md` | How the evaluation judge grades (keep the blindness rules intact) |
| `eval_seed_questions.jsonl` | Your ground truth: the questions the harness scores against |

Prompts are plain Markdown with `$UPPER_CASE` slots filled at runtime
(`$DOMAIN_NAME`, `$QUERY`, `$ENTITY_TYPES`, and so on). Edit the words
around the slots freely.

As shipped, this folder is configured for the demo domain (agricultural
residues) so everything works out of the box. To make it yours, start
with `uv run python scripts/init_domain.py --help`, then follow
[docs/bring-your-own-domain.md](../docs/bring-your-own-domain.md).
