---
title: Governance
description: See who decides what, how a proposal becomes a decision, and what any reviewer is empowered to block.
---

# Governance

Lightweight on purpose. This page says who decides what, how decisions
get recorded, and how those answers change as the project grows.

## Roles

**Maintainers** merge to `main`, cut releases, own the roadmap and the launch-gated decisions, and are the escalation point for conduct issues (see CODE_OF_CONDUCT.md). Current maintainers: the Sustainability Software Lab (LBL) team that builds the kit.

**Reviewers** are regular contributors invited by a maintainer after a track record of quality reviews and merged work. Reviews from reviewers count toward merging; maintainers still land the merge while the project is 0.x.

**Contributors** are everyone who opens an issue, improves a doc, or sends a pull request. CONTRIBUTING.md covers the mechanics. The short version: tests and `make check` green, honest claims, no fabricated numbers.

## How decisions are made

- **Code-level decisions** happen in pull requests. Disagreements resolve by evidence (an ablation, a benchmark, a failing test) over opinion. The ablation-first house rule applies to maintainers too.
- **Architecture decisions** get an ADR in `docs/adr/` (numbered, short, stating context, decision, consequences). Existing ADRs are the format reference. A change that contradicts an ADR updates or supersedes the ADR in the same pull request.
- **Direction-level proposals** start as an RFC. That covers new subsystems, roadmap changes, and anything touching the five public surfaces in [VERSIONING.md](VERSIONING.md). An RFC is a GitHub Discussion in the "Ideas" category, titled "RFC: ...", laying out the problem, the proposal, and the alternatives considered. When an RFC converges, it becomes an ADR plus issues. When it does not, the Discussion records why, which is worth as much.
- **Tie-breaks**: maintainers decide, in the open, with the reasoning written down where the discussion happened.

## What we optimize for

Correct over clever, honest over impressive, evidence over authority.
An eval harness project that fudged its own numbers would be worse than
no project; reviewers are explicitly empowered to block anything that
publishes an unmeasured claim.

## Changing this document

Governance changes are direction-level: RFC Discussion first, then a
pull request updating this page. While the project is 0.x, expect this
page to stay short; roles get added when there are people to fill them,
not before.
