# Versioning

sci-rag-kit follows [Semantic Versioning](https://semver.org/) with the
0.x rules spelled out, because "semver" alone promises nothing before
1.0 and users deserve to know what actually holds.

## While we are 0.x

- **Minor releases (0.2 -> 0.3) may break APIs**, and the CHANGELOG
  says so explicitly under a "Breaking" heading with a migration note.
  We break deliberately and loudly, never silently.
- **Patch releases (0.2.0 -> 0.2.1) do not break anything**: fixes,
  docs, and additive features only.
- **The database schema is versioned by Alembic migrations**
  (`migrations/versions/`), and every release's migrations run forward
  from any prior release's schema. Skipping releases is fine;
  downgrades are best-effort.
- **Eval report JSON is additive**: new keys may appear in
  `report.json`/`calibration.json`; existing keys do not change meaning
  or type within 0.x. External tooling (the UW SSEC evaluation platform
  seam) can rely on that.
- **Domain profiles are forward-compatible**: a `domain/` directory
  written for an older 0.x keeps working; new capabilities arrive as
  optional keys with safe defaults (the reranker block is the model:
  absent means off).

## What is public API

The compatibility promise covers:

1. The `sci_rag` Python package's documented top-level exports
   (`docs/api.md`)
2. The CLI command surface (`sci-rag ...`)
3. The REST contract under `/v1` and the MCP tool names/schemas
4. The `domain/` directory format
5. Eval report JSON keys

Internal module paths (anything not in `docs/api.md`) may move in any
minor release.

## Deprecation

Within 0.x: deprecated surface keeps working for one minor release with
a visible warning, then goes. The CHANGELOG lists every deprecation the
release it starts and the release it lands.

## Criteria for 1.0

1.0 is a promise, so it waits for evidence the promise can be kept:

- At least two production deployments outside the maintainers' own
  (ADOPTERS.md is the register; BioCirV is the flagship candidate)
- One full minor-release cycle with no breaking change needed to the
  five public surfaces above
- The benchmark page reproducible by an outside party from a clean
  clone (`make benchmark`)
- Judge calibration against domain-expert labels (not the shipped
  non-expert seed set) published for at least one real corpus
- Security review of the serving layer since the last surface change

After 1.0: breaking changes only in major releases, with migration
guides.

## Release mechanics

Releases are tagged `vX.Y.Z` from `main` with CI green, a CHANGELOG
entry, and (once the maintainer enables it; see the launch-gated list in
[ROADMAP.md](ROADMAP.md)) an archival DOI per release.
