---
title: LLM-assisted setup
description: Draft your ontology, corpus manifest, seed questions, and prompts with a model, or by copy-paste with no credentials at all.
---

# LLM-assisted setup

Pointing the kit at your field means writing four files: the ontology in
`domain/domain.yaml`, the corpus manifest, the seed questions in
`domain/eval_seed_questions.jsonl`, and the prompt wording in
`domain/prompts/`. Written cold, that is an afternoon of typing before you can
tell whether anything works.

The `sci-rag draft` commands do the first pass for you, grounded in the
documents you already have. What they produce is a draft, never ground truth,
and the kit is built to keep that distinction visible so you cannot forget it.

<div class="srag-meta-strip">
  <div><strong>You'll build</strong>Four drafted domain files, ready to review</div>
  <div><strong>You'll need</strong>Your documents on disk</div>
  <div><strong>Time</strong>About 30 minutes, plus review</div>
  <div><strong>Credentials</strong>Optional, there is a copy-paste path</div>
  <div><strong>Tested with</strong>v0.4</div>
</div>

## Before you start

| Requirement | Why | Check |
|---|---|---|
| Documents on disk, usually `data/raw/` | Every drafter reads them; none invents a field from its name | `ls data/raw` |
| A database, for the corpus-grounded drafters | Ontology and question drafting sample real ingested passages | `uv run sci-rag doctor` |
| A model credential, or an assistant you can paste into | `--print-prompt` and `--from-file` cover the second case completely | `grep SCI_RAG_GOOGLE .env` |
| A domain expert who will read the output | The drafters mark their work provisional until a person signs it off | |

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
    uv run sci-rag draft questions --count 10 --from-file reply.json
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

The example above repeats `--count 10` on both commands even though ten is the
default. Relying on the default would make the pair agree by coincidence, and
the coincidence would end the first time somebody changed one of them.

## What the drafters ask you for

Nothing the repository already knows.

| Command | Asks you for | Works out for itself |
|---|---|---|
| `draft ontology` | nothing | the name and description from `domain.yaml`; real passages from your corpus, or files in `data/raw/` |
| `draft manifest` | nothing (the folder defaults to `data/raw`) | each document's filename and opening pages, through the existing parsers |
| `draft questions` | nothing | the ontology, plus real passages and document titles from your corpus |
| `draft prompts` | which prompt to reword | the current template, its required slots, and the ontology |

More drafters land alongside this page as they ship; each one follows the same
rule.

## Drafting the ontology against your corpus

`sci-rag new` and `sci-rag init` can draft an ontology from a one-sentence
description, before any document exists. That is the best guess available at
that moment, and it is a guess. Only `sci-rag new` checks the credential with a
small live request first; `sci-rag init` uses the key or project captured in the
session without that preflight. Once documents are ingested you can ask a better
question: what do these documents actually talk about?

=== "Redraft from the corpus"

    Samples real passages and proposes a whole ontology in the vocabulary they
    use.

    ```bash title="Terminal"
    uv run sci-rag draft ontology --from-corpus
    ```

=== "Refine what you have"

    Shows the model your current ontology and asks only what it would add and
    what it would remove, with a reason for every removal that points at the
    passages. Types nobody questioned survive untouched.

    ```bash title="Terminal"
    uv run sci-rag draft ontology --refine
    ```

=== "Cold, from the description"

    The wizard's behavior, available on its own. Reads no documents at all.

    ```bash title="Terminal"
    uv run sci-rag draft ontology --cold
    ```

This is the assisted fix for the symptom the tutorial describes: near zero
entities after `sci-rag graph extract` means the ontology and the corpus are
talking past each other.

Two things it will not do. The `retrieval:` and `compression:` blocks are tuned
numbers an ablation earned, and not domain semantics, so they are carried over
untouched. And a refinement that would leave no entity type at all is rejected: a
model asking to remove everything is a bad refinement, not an instruction.

Redrafting the ontology changes what the graph extractor looks for, so re-run
`sci-rag graph extract` after you apply one.

## Drafting the corpus manifest, without drafting your rights

`sci-rag campaign build` already writes a manifest for DOI-addressable literature,
where rights come from Unpaywall and Crossref. Local PDFs get none of that.

```bash title="Terminal"
uv run sci-rag draft manifest --folder data/raw
```

Each document's opening pages go through the same parsers ingestion uses, and the
model reports title, authors, year, DOI, journal, and a source bucket. Buckets are
chosen across the whole batch, so a sixty-document folder converges on a handful
of shared sources, and not sixty.

**`license_class` is never guessed.** Every drafted row is written `unknown`,
which is the fail-closed default, and the command tells you how many documents
need a rights decision. If the text contains an explicit license sentence, it is
quoted into `license_source` as evidence for you, and only if it appears verbatim
in the document; a sentence the model composed is dropped.

That is not caution for its own sake. `license_class` is the input to a scoping
boundary that decides what a public endpoint may quote, and
[Evidence and rights](evidence-and-rights.md) is where you decide it.

For documents that carry a DOI, `sci-rag corpus enrich` fills journal, citation
counts, and retraction status from Crossref afterwards.

## Nothing is overwritten

A drafting run writes `<file>.proposed` and prints a summary. Reviewing that
file and moving it into place is your step, not the tool's. `--apply` skips the
proposal, and for seed questions it appends, never replaces, so a question
a human wrote is never displaced by one a model wrote.

`--dry-run` shows you the whole result and writes nothing at all.

## Drafted ground truth is labeled, everywhere

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

## When the questions are already yours

`draft questions` invents the questions. The questions worth evaluating against
are usually the ones real users asked, especially the ones the assistant
fumbled, and those cannot be invented from the corpus. So there is a second
command for the opposite direction:

```bash
uv run sci-rag draft seed-from-answers questions.txt
```

One question per line. The kit answers each one, then proposes ground truth
from the evidence that answer cited: the reference answer is what the assistant
said, and the evidence phrases are extracted from the retrieved chunk text.

It has one lane, not three. There is no prompt to print, because the model is
not being asked to draft anything: it is answering, and the drafting is the
Python that reads its citations back.

The checks are stricter here than the wording suggests, because the model's own
prose is the one thing that must never become ground truth. A phrase is kept
only when it appears verbatim in **both** the answer and a chunk that answer
cited: a span only in the answer is the model's words, and a span only in the
chunk is evidence the answer did not use. Every finished row is then run
through the same relevance predicate the evaluation itself uses, and a row that
would score zero against its own evidence is dropped with a reason and not
proposed.

Two things get dropped, and neither is guessed at. A question whose answer cited
nothing has no evidence to propose, so it is reported for you to write by hand
or tag `unanswerable`. So is a question whose answer paraphrased rather than
quoted.

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

## Rewording the prompts, narrowly

Most of `domain/prompts/` is wording. An extraction prompt written for
agricultural residues reads oddly to a membrane chemist, and rewording it is
exactly the kind of tedious, low-risk edit a model is good at.

```bash title="Terminal"
uv run sci-rag draft prompts entity_extraction
uv run sci-rag draft prompts answer
```

Those are the only two prompts this command will touch. Four are refused by
name, each with a reason:

| Prompt | Why not |
|---|---|
| `judge_grounding.md` | Blind to the reference answer on purpose. Rewording risks merging it with the correctness pass, which would change what every judged number means without breaking anything visibly. |
| `judge_correctness.md` | The separate reference-based pass that grounding is kept blind to. |
| `snippet_compression.md` | Decides which evidence reaches the answer at all, and is gated on paired judged-answer measurements, so its wording is an experimental condition. |
| `ontology_draft.md` | The drafting machinery itself; rewriting it would change how future drafts are made with nothing left to compare against. |

The subtler risk is a rewrite that reads beautifully and drops a `$SLOT`. That
template loads fine and fails in the middle of a pipeline run, so the rewrite is
re-rendered against dummy values and rejected if a slot went missing, if one was
invented, or if a stray dollar sign makes it unrenderable.

Prompt wording moves every downstream number. Re-run
`sci-rag eval retrieval --ablation` after applying a rewrite and compare.

## Checking the result

`sci-rag doctor` reports domain coherence beside its usual rows:

- the ontology is large enough to be worth extracting against, names are unique,
  and relations read as `source RELATION target`;
- every answerable seed question cites something, and at least one is an
  `unanswerable` honesty probe;
- how many seed questions are still tagged `drafted`;
- once a corpus is ingested, whether every reference title resolves to a real
  document, because one that does not scores zero forever and reads as a
  retrieval failure;
- manifest paths that still exist, and how many rows nobody has classified.

## What is not drafted

`domain/eval_calibration_labels.jsonl` stays hand-labeled. Those labels exist
to calibrate the LLM judge against human judgment; generating them with an LLM
would be circular and would destroy the only measurement they provide. See
[Evaluate your pipeline](evaluation.md).

<div class="srag-checkpoint" markdown>
**Checkpoint: the drafts are yours now**

`uv run sci-rag doctor` reports domain coherence: ontology size, questions
grounded against the ingested corpus, and how many rows still carry the
`drafted` tag. Every one of those tags is a question nobody has vouched for
yet, and the evaluation reports will keep saying so.
</div>

## Next steps

- Work the drafts into a finished domain: [Bring your own domain](bring-your-own-domain.md)
- Sign off on the seed questions and measure: [Evaluate your pipeline](evaluation.md)
- See what a drafted manifest does and does not decide: [Evidence and rights](evidence-and-rights.md)
