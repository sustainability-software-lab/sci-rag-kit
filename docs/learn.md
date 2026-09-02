---
title: How it works
description: What happens between a document and a cited answer, with links to the full reasoning behind each part.
---

# How it works

This page is the ten-minute version of the design, for a reader who has not built a retrieval system before. The pages linked at the end hold the full reasoning, the measurements, and the decisions we would reverse and under what conditions.

## The idea

A language model on its own answers from memory. For scientific questions that fails in predictable ways: it invents a number, cites a paper that does not exist, or repeats a textbook consensus when your documents say otherwise. Retrieval-augmented generation (RAG) changes the order of operations. First find the passages in your documents that bear on the question. Then give the model exactly those passages and ask it to answer from them, citing each one by number. If nothing relevant was found, say so. The model writes the prose; your documents supply the facts.

## What happens to a document

1. **Parse.** A PDF, HTML page, Markdown file, or text file becomes headings, paragraphs, and tables. Tables stay whole, because in scientific writing the answer is often a table row.
2. **Chunk.** The text is cut into pieces of about 800 tokens. Each chunk keeps its section heading, so a table in "Results" is still labeled as such when it is retrieved on its own.
3. **Embed.** Each chunk becomes a vector, a list of numbers that places similar meanings near each other. This is what lets a question find a passage that uses different words.
4. **Store.** Chunks, vectors, a full-text index, and the document's metadata and license class go into one Postgres database.
5. **Build the graph.** With a model credential, the kit reads each chunk and extracts the concepts your field cares about (the entity types you declared) and how they relate. Related concepts are clustered, and each cluster gets a short summary. This step is optional. It is what makes questions that span several documents work.

## What happens to a question

Five searches run at once. Each finds candidate passages a different way.

| Layer | Finds passages by | Good at |
|---|---|---|
| Vector | closeness of meaning | questions phrased differently from the documents |
| Keyword | exact words and phrases | identifiers, chemical names, units |
| Graph | walking from the concepts in the question to passages that mention related concepts | answers that span documents |
| Community | matching against the cluster summaries | big-picture questions no single passage covers |
| Hypothetical answer | writing a guess at what an answering passage would say, then searching near it | bridging question wording and document wording |

The five ranked lists merge by rank: a passage several layers agree on outranks one that a single layer scored highly. The top passages are numbered, and the model writes an answer that cites those numbers. Two profiles control how many layers run. `interactive` uses vector and keyword only, for a person waiting at a prompt. `deep` runs all five, for agents, batch jobs, and evaluation. A layer that is slow or fails contributes nothing, is reported as such, and the request still completes.

Rights are enforced inside every search, before ranking. Each document carries a license class, and a request that restricts rights never sees passages outside its scope. A shared endpoint cannot leak a paywalled PDF you hold internally.

## How you know it works

Every project keeps a file of test questions with known answers. Two commands measure the system against them. One scores whether the right passages came back, layer by layer. The other has a model grade the generated answers for grounding, citation accuracy, and correctness. The grader never sees the reference answer while it judges grounding, so it cannot reward an answer for matching the reference while citing passages that say something else. Every report records the documents and models that produced its numbers.

## Read next

<div class="srag-rows" markdown>

[<span class="srag-row__title">FAQ</span><span class="srag-row__copy">Short answers to what this is, who it is for, and why each design decision went the way it did.</span>](faq.md){ .srag-row }

[<span class="srag-row__title">Choosing Sci RAG Kit</span><span class="srag-row__copy">A comparison with LightRAG, PaperQA2, LlamaIndex, and Microsoft GraphRAG.</span>](choosing-sci-rag-kit.md){ .srag-row }

[<span class="srag-row__title">Architecture</span><span class="srag-row__copy">What each package owns, how storage and concurrency work, and the five places built to be extended.</span>](architecture.md){ .srag-row }

[<span class="srag-row__title">Methodology</span><span class="srag-row__copy">The full specification: chunking, graph extraction, fusion, rights, answering, and evaluation, with the reasoning for each choice.</span>](methodology.md){ .srag-row }

</div>

A word you do not recognize is in the [glossary](glossary.md). Start with the [FAQ](faq.md) if you are deciding whether the kit fits, [Architecture](architecture.md) if you want to modify code, and [Methodology](methodology.md) if you need to defend the approach in a review.
