# LLM-assisted setup

Specializing the kit to your field means writing four files: the ontology in
`domain/domain.yaml`, the corpus manifest, the seed questions in
`domain/eval_seed_questions.jsonl`, and the prompt wording in
`domain/prompts/`. Written cold, that is an afternoon of typing before you can
tell whether anything works.

The `sci-rag draft` commands do the first pass for you, grounded in the
documents you already have. What they produce is a draft, not ground truth,
and the kit is built to keep that distinction visible rather than to let you
forget it.

## Three lanes, one system

Every drafter offers the same three routes to the same validated file.

=== "Generate it"

    The configured model drafts it, and the reply is validated through the
    same pydantic model the loader uses.

    ```bash title="Terminal"
    uv run sci-rag draft questions --count 10
    ```

=== "Paste it into any assistant"

    No API key, no provider account. `--print-prompt` writes the fully
    rendered, corpus-grounded prompt to stdout. Paste it into whatever
    assistant you already use, save the reply, and feed it back.

    ```bash title="Terminal"
    uv run sci-rag draft questions --count 10 --print-prompt > prompt.txt
    # paste prompt.txt into an assistant, save the JSON reply as reply.json
    uv run sci-rag draft questions --from-file reply.json
    ```

=== "Write it yourself"

    Nothing changes. Every schema is still documented in full in
    [Bring your own domain](bring-your-own-domain.md), and a hand-written file
    is never touched by a drafter.

The two generated lanes are not two implementations. They render the same
prompt, run the same validation, and write the same bytes. A test in the suite
asserts exactly that, because the moment they drift, the no-credentials path
becomes second class.

One thing to keep steady across the pair: `--count` and `--folder` decide which
passages get sampled, so pass the same values to `--print-prompt` and to
`--from-file`. Change them in between and you are validating a reply against
passages the assistant never saw, which shows up as evidence phrases dropped
for being ungrounded.

## What the drafters ask you for

Nothing the repository already knows.

| Command | Asks you for | Works out for itself |
|---|---|---|
| `draft questions` | nothing | the ontology, plus real passages and document titles from your corpus |

More drafters land alongside this page as they ship; each one follows the same
rule.

## Nothing is overwritten

A drafting run writes `<file>.proposed` and prints a summary. Reviewing that
file and moving it into place is your step, not the tool's. `--apply` skips the
proposal, and for seed questions it appends rather than replaces, so a question
a human wrote is never displaced by one a model wrote.

`--dry-run` shows you the whole result and writes nothing at all.

## Drafted ground truth is labelled, everywhere

`sci-rag draft questions` tags every row it writes `drafted`:

```json
{"id": "straw-tonnage", "question": "...", "tags": ["availability", "drafted"]}
```

That tag is provenance, and it travels:

* the proposed file carries a header saying its rows are model-drafted and
  awaiting review;
* `sci-rag eval retrieval` and `sci-rag eval answers` count the tagged rows and
  print a warning in the report saying how many of the questions behind those
  numbers are unreviewed;
* the report JSON carries the same receipt as
  `"ground_truth": {"drafted": 7, "reviewed": 3}`.

Removing the tag is the expert sign-off. Nothing in the kit removes it for you,
and re-running the evaluation after you remove one will show the counts move.

## How the questions are checked

Grounding verification runs in Python, not in the model, because a model asked
whether it made something up is not a reliable witness.

The prompt tells the model to copy its evidence phrases character for character
out of passages it was shown. Afterwards, for each drafted question:

* every `reference_title` must name a document that is actually in the sample;
* every `evidence_phrase` must appear in a passage belonging to one of those
  documents, comparing with whitespace and case normalized so a line wrap does
  not count as an invention.

A question that fails either check is dropped and reported by id and reason. In
the model-backed lane, one repair round asks for replacements, with the
rejected rows and their reasons fed back in.

The honesty probe is the exception. A question tagged `unanswerable` is meant
to have no supporting document, so it is exempt from the evidence check, and
any citation it invents for itself is stripped. If a draft contains no probe,
the run says so: an evaluation set without one cannot tell you whether the
assistant admits a gap or fills it from model priors.

## Before you have a database

`draft questions` prefers the ingested corpus, because the chunker has already
segmented it. When nothing is ingested, or Postgres is not running, it reads
`data/raw/` directly through the same parsers ingestion uses. The run summary
says which source it used either way.

That means the drafters work on a fresh checkout, before `make setup`:

```bash title="Terminal"
uv run sci-rag draft questions --count 5 --dry-run
```

## The review discipline

The point of an evaluation set is that someone who knows the field vouches for
it. A drafter can save you the typing, and it can refuse to write a question it
cannot ground, but it cannot vouch for anything.

So the loop is:

1. Draft. Read the dropped rows; they tell you where the corpus is thin.
2. Review each surviving question against the document it cites.
3. Delete the `drafted` tag from the ones you would defend.
4. Re-run the evaluation. The warning shrinks as the reviewed count grows.

A report that still carries the warning is not a failed report. It is an honest
one, and it is fine to work with, as long as nobody quotes its numbers as
though an expert had signed them.

## What is not drafted

`domain/eval_calibration_labels.jsonl` stays hand-labelled. Those labels exist
to calibrate the LLM judge against human judgement; generating them with an LLM
would be circular and would destroy the only measurement they provide. See
[Evaluate your pipeline](evaluation.md).
