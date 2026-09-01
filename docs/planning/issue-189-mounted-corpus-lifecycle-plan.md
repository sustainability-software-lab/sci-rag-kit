<!-- Plan doc for issue #189. Excluded from the documentation site (mkdocs
     exclude_docs: planning/); it is a working record, not a user guide. -->

> Authored and approved 2026-09-01.

# Complete the isolated GCP lifecycle with a mounted corpus

Issue: https://github.com/sustainability-software-lab/sci-rag-kit/issues/189

Delivery unit: one existing issue, one implementation pull request. The
Terraform, guide, and live qualification are one atomic contract. The pull
request must remain open until the populated deploy and ordinary Terraform
teardown both pass.

### Context Alignment

Anchor: issue #189 was filed on 2026-08-29. Against `origin/main` at
`81c4106`:

- The isolated deployment ran against `biositing-docs-pub`. Required services,
  a clean image push, root apply, migrations, Secret Manager integration, the
  deployed REST smoke test, and the final inventory all passed.
- PRs #262, #263, and #265 landed the six fixes discovered by that run. The
  service and job now honor deletion protection, the deploy prerequisites are
  accurate, the impossible ingest output is no longer printed, and Cloud Run
  callers can use `X-API-Key`.
- Criterion 5 is still unmet. `load_manifest()` and every parser consume local
  `Path` objects, while the versioned corpus bucket is not mounted and the
  image contexts deliberately exclude `data/`.
- The guide still demonstrates the excluded `data/demo/manifest.jsonl` path,
  still describes baking a corpus into the image, and later sends the deployed
  query key in the header that Cloud Run consumes.
- A populated database still exposes an unproved destroy race. The database
  and user are sibling Terraform resources, and the first qualification needed
  direct instance deletion after the role and database removals failed.
- The corpus bucket has no explicit `force_destroy` or soft-delete policy. A
  populated versioned bucket therefore cannot complete the documented destroy,
  while Google's default seven-day soft delete would make an apparently absent
  bucket recoverable and billable after deletion.
- The local provider is 8.0.0, but the declared floor is 5.30. Provider 5 and 6
  documented job GCS volumes as preview features requiring a preview launch
  stage; provider 7 documents the same block as GA.

Classification: Partially done.

Reframed scope: preserve filesystem-based ingestion, mount the existing corpus
bucket read-only into the ops job, make both populated teardown paths explicit
and deterministic, correct the deployment guide, and rerun only the residual
live lifecycle needed to prove ingest, graph construction, and ordinary
Terraform destruction against the captured baseline.

## Context

The previous qualification proved seven of eight observable behaviors and found
real deployment defects. It did not prove a deployed corpus path. The current
Terraform creates a bucket and grants `roles/storage.objectViewer`, but nothing
inside the job can read the bucket. At the same time, the private-corpus safety
boundary in `.dockerignore` and `.gcloudignore` correctly keeps `data/` out of
every image.

The smallest complete solution is to make the existing bucket appear as a
read-only filesystem at `/corpus` in the Cloud Run ops job. A manifest staged at
`/corpus/manifest.jsonl` keeps its existing relative-path semantics, so an entry
such as `fixture/example.md` resolves to `/corpus/fixture/example.md`. No product
API, package dependency, credential resolver, or parser changes.

Populating that bucket turns teardown from a theoretical concern into part of
the public contract. Object versioning, soft delete, Terraform force deletion,
Cloud Run connections, database ownership, and local state credentials all have
to be treated explicitly. A normal successful run must not need a direct
`gcloud sql instances delete` escape hatch.

## Approved decisions

1. **Keep ingestion filesystem-based.** Do not teach `sci-rag ingest` to accept
   `gs://`. Mount the Terraform corpus bucket read-only at `/corpus` in the Cloud
   Run ops job and invoke the existing CLI with
   `--manifest /corpus/manifest.jsonl`.
2. **Keep corpora out of images.** Preserve both build-context allowlists. The
   operator uploads a manifest and its referenced files to the bucket with the
   same relative layout.
3. **Fail closed for real corpus deletion.** Add `force_destroy_corpus`, default
   `false`. Terraform can remove live and noncurrent objects only after a
   reviewed update explicitly sets it to `true`.
4. **Keep soft-delete recovery by default.** Add
   `corpus_soft_delete_retention_seconds`, default `604800`. Accept `0` or the
   provider-supported 7-to-90-day range. Only a deliberately disposable run
   sets it to `0` before uploading data.
5. **Prove populated database teardown in this issue.** Establish an explicit
   service/job, secret version, database, user, and instance dependency chain,
   then require the ordinary reviewed Terraform destroy to pass without direct
   Cloud SQL deletion.

These decisions approve the plan architecture only. They do not authorize a
billed apply, data upload, migration, graph build, destroy, API disablement, or
credential-file deletion.

## Scope

- Add a read-only GCS volume to the Cloud Run ops job at `/corpus`.
- Raise the Google provider floor to the first major whose job GCS mount is GA.
- Preserve `roles/storage.objectViewer`; grant no write or delete permission to
  the runtime service account.
- Make the existing ops example invoke ingest through the mounted manifest.
- Add safe, explicit Terraform controls for force deletion and soft-delete
  retention.
- Make database ownership and active-consumer teardown ordering deterministic.
- Correct the deployment guide's upload, ingest, graph, authentication, provider
  upgrade, and teardown procedures.
- Add static regression tests for every cross-file Terraform and guide contract.
- Validate the residual path in `biositing-docs-pub` with the tracked synthetic
  CC0 demo, then return the project to its recorded baseline.
- Record live job execution IDs, non-secret counts, reviewed plan summaries,
  inventory, and final absence evidence on the implementation pull request and
  issue #189.

## Out of scope

- A native `gs://` manifest or document API in package code.
- A Google Cloud Storage SDK dependency, local staging downloader, streaming
  parser abstraction, or change to `CorpusEntry.path`.
- Baking any corpus, manifest, credential, Terraform state, or downloaded paper
  into the container image.
- Mounting the corpus bucket into the REST/MCP service.
- Granting the runtime service account `storage.objectCreator`,
  `storage.objectUser`, `storage.admin`, or any delete permission.
- Replacing PostgreSQL, changing schemas, changing retrieval behavior, or running
  retrieval ablations. This change affects deployment transport only.
- Reopening the already-passed qualification criteria unless the residual rerun
  produces contradictory evidence.
- Diagnosing the organization-level Cloud Build denial. Use the previously
  proven local `linux/amd64` build and registry push route.
- Deleting the `biositing-docs-pub` project or its audit labels. The final state
  is the captured empty-project baseline, not project deletion.
- Any mutation of the shared Cloud SQL development instance or another
  workspace's proxy.

## Architecture and lifecycle

### Mounted corpus contract

The operator stages one self-contained directory tree in the Terraform bucket:

```text
gs://<corpus-bucket>/
  manifest.jsonl
  fixture/
    document-a.md
    document-b.pdf
```

The ops job mounts the bucket as:

```text
/corpus/
  manifest.jsonl
  fixture/
    document-a.md
    document-b.pdf
```

`load_manifest(Path("/corpus/manifest.jsonl"))` resolves relative document paths
against `/corpus`, exactly as it does on a laptop. The mount is on the ops job
only and is read-only at the volume definition. GCS FUSE remains untrusted as a
perfect POSIX filesystem, so the live qualification must read the actual
Markdown demo through the mount rather than treating a successful apply as
proof.

### Provider contract

Set the Google provider constraint to `>= 7.0`. Provider 5.30 and 6.0 describe
job GCS volumes as preview features requiring `launch_stage = "BETA"`; provider
[7 describes them as GA](https://github.com/hashicorp/terraform-provider-google/blob/v7.0.0/website/docs/r/cloud_run_v2_job.html.markdown).
The module should use the GA resource without a preview launch stage. Existing
users with an older local provider lock run `terraform init -upgrade`. Google's
[Cloud Run job mount procedure](https://cloud.google.com/run/docs/configuring/jobs/cloud-storage-volume-mounts)
is the live platform contract.

Do not commit the root module's generated `.terraform.lock.hcl`, `.terraform/`,
plans, or state. The provider constraint is the distributable compatibility
contract.

### Database destroy graph

Build the database URL from the concrete Terraform database and user resource
names rather than duplicate string literals. Make the database explicitly
depend on the user, and make both Cloud Run consumers depend on the database URL
secret version.

The resulting order is:

```text
create: instance -> user -> database -> database URL secret -> service and job
destroy: service and job -> database URL secret -> database -> user -> instance
```

Deleting the database before its owning role removes the migrated objects that
blocked the first qualification. Removing the service and job before the
database closes the Terraform-managed consumers before database deletion.

### Bucket protection and disposable runs

The normal module posture is:

```text
force_destroy_corpus = false
corpus_soft_delete_retention_seconds = 604800
versioning = enabled
```

For the named disposable qualification only, the create plan sets soft delete
to `0` before any object exists while keeping force destroy `false`. Immediately
before teardown, a separately reviewed update plan sets
`deletion_protection=false` and `force_destroy_corpus=true`. A second saved plan
then describes the actual destroy.

This sequencing prevents an ordinary early `terraform destroy` from erasing the
corpus while another protected resource refuses deletion. It also avoids the
false absence result produced when a deleted bucket remains soft-deleted for
[seven days by default](https://cloud.google.com/storage/docs/soft-delete). The
final inventory checks both live and soft-deleted buckets.

### Public outputs and guide contract

Keep the existing `run_ops_job_example` output name for compatibility, but make
its value the now-working ingest invocation. Update `corpus_bucket_purpose` to
state that the bucket is mounted read-only at `/corpus` in the ops job. Do not
emit credentials or object contents in Terraform output.

The guide stages the corpus after apply and before ingest, preserves relative
layout, then runs migrations, ingest, graph extraction, graph communities, and
`stats`. It uses `X-API-Key` for deployed authenticated requests, says that the
runtime identity can read the corpus bucket, and no longer asks readers to
rebuild an image when a manifest changes.

## Workstreams

### Workstream 1: Pin the Terraform lifecycle contracts  [Tier: T0]

Add failing shape tests first, then implement the mount, provider floor, bucket
controls, and dependency graph.

**Files:**

- `tests/unit/test_root_terraform_deploy_shape.py` - pin the GA provider floor,
  job-only read-only mount, mounted ingest output, safe variable defaults,
  explicit bucket wiring, and deterministic database destroy edges.
- `infra/terraform/main.tf` - mount the bucket, wire deletion and soft-delete
  controls, reference database/user names in the URL, and establish the
  dependency chain.
- `infra/terraform/variables.tf` - add and validate the two corpus lifecycle
  inputs and make the existing deletion-protection description include the job.
- `infra/terraform/outputs.tf` - replace the doctor placeholder with the working
  mounted ingest command and describe the bucket accurately.

**Implementation approach:**

- Raise only the Google provider minimum; do not introduce `google-beta` or a
  preview launch stage.
- Add `volume_mounts { name = "corpus" mount_path = "/corpus" }` beside the
  Cloud SQL mount in the ops container.
- Add a job volume whose GCS bucket is
  `google_storage_bucket.corpus.name` and whose `read_only` value is explicit.
- Do not add the volume to `google_cloud_run_v2_service.api`.
- Wire `force_destroy` directly to `var.force_destroy_corpus`.
- Add an explicit soft-delete block whose retention is the validated variable.
- Keep bucket versioning enabled and object access read-only.
- Make `google_sql_database.sci_rag` depend on
  `google_sql_user.sci_rag`; interpolate both names in `local.database_url`.
- Keep the service dependency on the database secret version and add the same
  dependency to the ops job.
- Preserve all resource names and outputs other than the changed example value.

**TDD contract:**

- Name: `test_the_ops_job_mounts_the_corpus_bucket_read_only`
- Tier: unit shape test.
- Asserts: the ops job alone references the Terraform bucket as a GCS volume,
  declares `read_only = true`, and mounts it at `/corpus`.
- Red trigger: the current job has only the Cloud SQL volume.

- Name: `test_the_ingest_example_uses_the_mounted_manifest`
- Tier: unit shape test.
- Asserts: the emitted command uses
  `ingest,--manifest,/corpus/manifest.jsonl` and contains no image-only
  `data/demo` path or `gs://` product URI.
- Red trigger: the current output runs `doctor` because no corpus path works.

- Name: `test_corpus_deletion_is_explicit_and_safe_by_default`
- Tier: unit shape test.
- Asserts: force destroy defaults false, soft delete defaults seven days, the
  allowed retention range includes only zero or 7-to-90 days, versioning stays
  enabled, and the bucket references both inputs.
- Red trigger: neither lifecycle input exists.

- Name: `test_populated_database_destroy_order_is_deterministic`
- Tier: unit shape test.
- Asserts: database depends on user, the URL references both resource names,
  and service plus job depend on the database secret version.
- Red trigger: database and user are siblings and the job lacks the secret
  version edge.

**Acceptance criteria:**

- [ ] `terraform validate` accepts the GA GCS volume on the declared provider
      range.
- [ ] The runtime service account remains read-only on corpus objects.
- [ ] The REST/MCP service has no corpus mount.
- [ ] The output names a path guaranteed to exist after documented staging.
- [ ] Normal configuration cannot force-delete a populated bucket.
- [ ] Normal configuration retains seven days of soft-delete recovery.
- [ ] A populated database has one unambiguous Terraform destroy order.
- [ ] No package source, public CLI/API, dependency, schema, or build-context
      allowlist changes.

### Workstream 2: Make the deployment guide executable and honest  [Tier: T1]

Update the guide in the same change so every command matches the Terraform and
the Cloud Run authentication boundary.

**Files:**

- `docs/deploy-gcp.md` - add provider upgrade, corpus upload and mounted ingest,
  correct runtime permissions and `X-API-Key` commands, and document the
  two-stage protected teardown.
- `tests/unit/test_root_terraform_deploy_shape.py` - extend the cross-file guide
  assertions so the stale baked path and deployed bearer-key example cannot
  return.

**Implementation approach:**

- Keep the build-context warning and state that corpus changes do not require an
  image rebuild.
- After apply, obtain `corpus_bucket` from Terraform and upload a directory tree
  without `--delete-unmatched-destination-objects`. Show the tracked demo as the
  safe example and explain that every manifest path stays relative to the
  manifest's bucket location.
- Run the exact mounted ingest output, followed by the existing graph commands
  and `sci-rag stats` through the ops job.
- Explain that Cloud Run provides the mount. Do not tell users to install GCS
  FUSE or copy the full corpus into writable container storage.
- Replace the active deployed query example's `Authorization: Bearer` header
  with `X-API-Key`; keep the generic REST behavior in `docs/api.md` unchanged.
- Name all three independent protections: database/service/job deletion
  protection, bucket force deletion, and bucket soft-delete retention.
- Require a verified backup for a real corpus before setting either protection
  to its destructive value. Explain that disabling soft delete does not purge
  objects already soft-deleted under an earlier policy.
- Show a reviewed update plan before the reviewed destroy plan. State that a
  failed destroy keeps state and produces an inventory, rather than inviting a
  direct Cloud SQL deletion.
- Add the provider 7 migration note and `terraform init -upgrade` for older
  local locks.

**TDD contract:**

- Name: `test_the_deploy_guide_stages_the_path_its_ingest_command_reads`
- Tier: unit cross-file test.
- Asserts: the guide uploads `manifest.jsonl` plus referenced files, invokes
  `/corpus/manifest.jsonl`, preserves the build-context exclusion, and does not
  call the corpus baked into the image.
- Red trigger: the current Step 3 invokes a file that the image cannot contain.

- Name: `test_cloud_run_examples_use_the_platform_safe_api_key_header`
- Tier: unit documentation contract test.
- Asserts: deployed authenticated curl examples use `X-API-Key`, and no active
  Cloud Run command uses the kit key as an `Authorization` bearer token.
- Red trigger: the current query command contradicts the warning immediately
  above it.

**Acceptance criteria:**

- [ ] A reader can stage a local corpus tree without changing the image.
- [ ] Every documented ops command corresponds to a Terraform output or mounted
      path that exists.
- [ ] The guide preserves least privilege and the private-corpus build boundary.
- [ ] The deployed auth example reaches the application rather than stopping at
      Google's frontend.
- [ ] Teardown language distinguishes recoverable protection from permanent
      corpus deletion.
- [ ] Documentation never implies that a normal successful destroy may need a
      direct instance deletion.

### Workstream 3: Qualify the residual live lifecycle  [Tier: T2]

Run this only from the reviewed implementation pull request after offline,
Cloud SQL, documentation, and Terraform checks pass. The target is
`biositing-docs-pub`, region `us-central1`, with resource prefix
`sci-rag-route-20260831`. Every `gcloud` command names `--project` explicitly.

**Preflight, read-only:**

- Reconfirm the active identity, billing status, audit labels, enabled APIs,
  live resources, IAM delta, live buckets, and soft-deleted buckets.
- Compare the new inventory with the baseline in issue comment
  `5483638738`. Stop on any unexpected project use or resource.
- Record the workspace proxy PID and shared development instance identity
  without printing a database URL or credential. Do not refresh setup, pause an
  instance, or stop any proxy.
- Record the implementation commit, image tag, Terraform/provider versions,
  local demo corpus digest, and exact build-context inventory. Stop if a secret,
  state file, private corpus, or ignored artifact is in the upload context.

**Fresh CREATE authorization:**

Ask immediately before mutation, naming the project, API set, Artifact Registry
repository, image tag, Terraform resource prefix, region, estimated billed
duration, and saved create-plan path.

After approval:

1. Enable only the declared APIs that are currently off and create the uniquely
   prefixed Artifact Registry repository.
2. Build the reviewed commit locally for `linux/amd64`, push the exact tag, and
   record its digest. Do not retry the organization-blocked Cloud Build route.
3. Initialize Terraform, run format and validation checks, then save a create
   plan with `corpus_soft_delete_retention_seconds=0`,
   `force_destroy_corpus=false`, deletion protection enabled, and the exact
   target variables.
4. Review resource names, target project, mounted bucket, protection values, and
   plan summary. Apply only that saved plan.
5. Inventory the created resources and prove the bucket is empty, versioned,
   soft delete is disabled, and runtime IAM remains read-only.

**Fresh SEED authorization:**

Ask immediately before persistent data mutation, naming the target bucket,
database, synthetic manifest digest, upload layout, migration command, ingest
command, and graph commands.

After approval:

1. Dry-run the additive upload, then stage only `data/demo/manifest.jsonl` and
   `data/demo/fixture/` at the bucket root. Do not use a mirror-delete flag.
2. Upload the identical manifest a second time so at least one noncurrent
   generation exists. Record generations and hashes, never document contents
   beyond the tracked CC0 fixture.
3. Run migrations through the ops job and require a successful execution.
4. Run ingest with `/corpus/manifest.jsonl`; record the execution ID and require
   five documents with no failed ingest item.
5. Run `graph extract`, require a successful execution and zero failed batches,
   then run `graph communities` and `stats`.
6. Require positive document, chunk, entity, and relationship counts. Record
   community count without inventing a threshold that the command does not
   promise.
7. Verify `/health`, `/v1/corpus-manifest`, and authenticated `/v1/status` or
   `/v1/query` using `X-API-Key`. Read the generated key without echoing or
   logging it. Recheck the RFC 9457 error envelope and `X-Request-ID` as a
   regression smoke, while treating the earlier run as the primary criterion 7
   evidence.

**Fresh DELETE authorization:**

Ask immediately before protection changes or deletion, naming the exact
Terraform resources, noncurrent object generations, Artifact Registry
repository, APIs to restore to baseline, saved update/destroy plan paths, and
local credential-state files slated for removal.

After approval:

1. Save and review an update plan setting `deletion_protection=false` and
   `force_destroy_corpus=true`, with soft delete still `0`. Apply only that
   saved update plan.
2. Save a separate destroy plan with the same explicit variables. Review its
   project, names, and resource count, then apply only that saved plan.
3. Require database, user, and instance deletion to succeed through Terraform.
   No direct Cloud SQL deletion counts as a pass.
4. Delete the named Artifact Registry repository and disable only APIs proven
   off at the preflight baseline.
5. Compare live resource, IAM, API, and billing-relevant inventories to the
   captured baseline. Query the exact bucket name in both normal and
   soft-deleted bucket listings; both must be absent.
6. Reconfirm that the shared development instance and every observed proxy are
   unchanged.
7. Only after final absence, enumerate and delete the exact saved plans,
   Terraform state, timestamped state backups, and any temporary file that held
   a credential. Do not use a broad recursive cleanup target.

If any live step fails, stop, preserve Terraform state, post the exact surviving
resource inventory, and request a new decision for any recovery action outside
the approved saved plans. An authorization error is BLOCKED, never PASS.

**Live acceptance criteria:**

- [ ] The mounted manifest and every relative document path are readable in the
      deployed ops job.
- [ ] Migrations, synthetic ingest, graph extraction, and community construction
      finish successfully on the deployed database.
- [ ] The database contains the five demo documents plus positive chunk, entity,
      and relationship counts.
- [ ] The service reports the populated corpus through its normal REST contract.
- [ ] The bucket contains both live and noncurrent synthetic object generations
      before teardown.
- [ ] Reviewed Terraform update and destroy plans remove the populated database,
      role, instance, versioned objects, and bucket without a direct provider
      escape hatch.
- [ ] Neither a live nor soft-deleted corpus bucket remains.
- [ ] Registry, Cloud Run, Cloud SQL, Secret Manager, runtime IAM, and enabled APIs
      match the captured project baseline after cleanup.
- [ ] Shared development Cloud SQL and sibling proxies are demonstrably unchanged.
- [ ] State, backups, plans, keys, and other credential-bearing local artifacts
      are absent after verified teardown.

## Delivery and gating

This remains one existing issue and one implementation pull request. Splitting
Terraform from documentation would temporarily publish a module and guide that
disagree. Splitting live proof from the implementation would permit issue #189
to close on another unqualified plan-only change.

The implementation pull request may be opened before the billed run, but it does
not merge until all three authorization-gated phases and final absence pass. Its
body may resolve #189 only after that evidence exists. The separate planning
pull request must say that it does not resolve #189 and must not use a GitHub
closing keyword.

No ADR is required. This preserves the existing filesystem ingestion contract,
uses a provider-native mount on an already-provisioned bucket, and adds explicit
operational safety inputs. It creates no new package boundary, data model, or
hard-to-reverse product architecture. The guide and Terraform variable
descriptions are the correct durable record.

## Verification

Write and run the focused regression tests first through the workspace runner:

```bash
"$CONDUCTOR_ROOT_PATH/.conductor/run-cloud-tests.sh" \
  tests/unit/test_root_terraform_deploy_shape.py -q
```

Run Terraform and documentation checks:

```bash
terraform -chdir=infra/terraform fmt -check -diff -recursive
terraform -chdir=infra/terraform init -backend=false -input=false -upgrade
terraform -chdir=infra/terraform validate
make docs
```

Then run repository CI parity. Keep the database suite as one Cloud SQL-backed
invocation and treat any database skip as a failure of evidence:

```bash
uv lock --check
uv run ruff check src tests examples scripts
uv run ruff format --check src tests examples scripts
uv run mypy
uvx pre-commit run --all-files --show-diff-on-failure
"$CONDUCTOR_ROOT_PATH/.conductor/run-cloud-tests.sh" \
  -q --cov=sci_rag --cov-report=term --cov-fail-under=78
```

No `docs-geometry` run is required because no stylesheet changes. Do not use
Docker for the local database or test suite. The later local Docker image build
is part of the separately authorized deployment qualification, not workspace
database setup.

Review the final diff for build-context changes, provider preview fields,
write-capable bucket IAM, `gs://` package behavior, secret values, state, saved
plans, generated caches, direct Cloud SQL deletion instructions, and changes
outside #189.

## Rollback and failure handling

- Before live mutation, discard or revise the unmerged implementation diff; no
  migration or data rollback exists.
- During CREATE or SEED failure, keep state and inventory every surviving named
  resource. Do not improvise cleanup under an earlier approval.
- During DELETE failure, keep state, the reviewed plans, and the exact inventory
  until a corrected reviewed path is approved. Do not delete the instance
  directly and do not delete state while resources survive.
- After a successful teardown and verified absence, revert code with one pull
  request if the mounted route itself must be withdrawn. The bucket remains
  protected by default for existing users.
- Never change or stop the shared development Cloud SQL instance as recovery for
  this isolated deployment.

## Definition of done

- The five approved decisions are implemented without changing the public
  filesystem ingestion contract or build-context boundary.
- Focused tests, Terraform validation, docs build, full CI parity, and Cloud SQL
  database-backed tests pass with no database skips.
- A reviewed deployment from the implementation commit reads the tracked demo
  through `/corpus`, ingests five documents, builds a nonempty graph, and exposes
  the populated service contract.
- A reviewed Terraform teardown removes the populated database and versioned
  bucket naturally, with no live or soft-deleted bucket and no direct Cloud SQL
  deletion.
- Final inventories match the captured `biositing-docs-pub` baseline, the shared
  development backend and proxies are unchanged, and all credential-bearing
  local state is removed.
- The implementation pull request carries non-secret execution and absence
  receipts, merges through the repository's actual landing path, and resolves
  issue #189 only after every residual acceptance criterion is proven.
