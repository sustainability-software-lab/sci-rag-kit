---
title: Generate typed API clients
description: Generate and run Python and TypeScript clients from a live Sci RAG Kit OpenAPI schema.
---

# Generate typed API clients

Generate Python and TypeScript clients from your running server, then make an
authenticated request with a typed response.

<div class="srag-meta-strip">
  <div><strong>You'll build</strong>A Python package and a typed TypeScript client</div>
  <div><strong>You'll need</strong>A running server, uv, Node.js, and npm</div>
  <div><strong>Time</strong>Package download time plus two client runs</div>
  <div><strong>Tested with</strong>v0.3.0 and the generator versions below</div>
</div>

## Before you start

| Requirement | Why | Check |
|---|---|---|
| A configured Sci RAG Kit checkout | The server needs its database and migrations | `uv run sci-rag doctor` |
| Python 3.11 or 3.12 with uv | `openapi-python-client` generates an installable Python package | `uv --version` |
| Node.js with npm | `openapi-typescript` and the example runner use npm packages | `node --version` |
| A server API key with `corpus:read` | The examples call protected `GET /v1/status` | Ask the server operator for a scoped key |

The commands below use `client-demo-key` for a loopback-only exercise. Never use
that literal value in a deployed service.

## Start the server and expose its schema

Apply the migrations first:

```console title="Terminal"
$ make setup
```

Start the server with one static key that can read corpus status:

```console title="Terminal"
$ SCI_RAG_EMBEDDING_PROVIDER=local-hash \
    SCI_RAG_API_KEYS='{"client-demo-key":{"scopes":["corpus:read"]}}' \
    uv run sci-rag serve --host 127.0.0.1 --port 8000
```

Keep that process running. In a second terminal, set the values both examples
will read and check the server:

```console title="Terminal"
$ export SCI_RAG_URL=http://127.0.0.1:8000
$ export SCI_RAG_API_KEY=client-demo-key
$ curl --fail --silent --show-error "$SCI_RAG_URL/health"
```

The generator input is now available at `$SCI_RAG_URL/openapi.json`. FastAPI
builds it from the request and response models in
`src/sci_rag/server/schemas.py`.

<div class="srag-checkpoint" markdown>
**Checkpoint: the schema is live**

The health response should contain `"status":"ok"` and `"database":true`.
If it reports a degraded database, run `uv run sci-rag db upgrade` and check
`SCI_RAG_DATABASE_URL` before generating a client.
</div>

## Generate the Python client

Give the generated distribution and import package stable names. Without these
overrides, the generator derives both names from your domain profile's title.

```yaml title="~/openapi-python-client.yaml"
project_name_override: sci-rag-client
package_name_override: sci_rag_client
```

Generate the package directly from the live schema:

```console
$ mkdir -p generated
$ uvx --from openapi-python-client==0.29.0 \
    openapi-python-client generate \
    --url "$SCI_RAG_URL/openapi.json" \
    --config openapi-python-client.yaml \
    --output-path generated/python \
    --overwrite
```

Create one typed status request:

```python title="~/python-status.py"
import os

from sci_rag_client import AuthenticatedClient
from sci_rag_client.api.meta import status_v1_status_get


with AuthenticatedClient(
    base_url=os.environ.get("SCI_RAG_URL", "http://127.0.0.1:8000"),
    token=os.environ["SCI_RAG_API_KEY"],
    raise_on_unexpected_status=True,
) as client:
    status = status_v1_status_get.sync(client=client)

if status is None:
    raise RuntimeError("The server returned no status document.")

print(f"documents={status.documents}")
```

Run it with the generated package as a temporary dependency:

```console
$ uv run --with ./generated/python python python-status.py
```

<div class="srag-checkpoint" markdown>
**Checkpoint: Python parsed the typed response**

The command prints `documents=` followed by the live corpus count. A 401 means
the key is missing or unknown. A 403 means the key lacks `corpus:read`.
</div>

## Generate the TypeScript client

Install the type generator, its supported TypeScript major version, a typed
fetch client, and the example runner in your TypeScript project:

```console
$ npm install openapi-fetch@0.17.0
$ npm install --save-dev openapi-typescript@7.13.0 typescript@5.9.3 \
    tsx@4.23.12 @types/node
```

Generate the path and component types from the same live schema:

```console
$ mkdir -p generated/typescript
$ npx openapi-typescript "$SCI_RAG_URL/openapi.json" \
    -o generated/typescript/schema.d.ts
```

Use those types with `openapi-fetch`:

```typescript title="generated/typescript/status.ts"
import createClient from "openapi-fetch";
import type { paths } from "./schema";

const apiKey = process.env.SCI_RAG_API_KEY;
if (!apiKey) {
  throw new Error("Set SCI_RAG_API_KEY before running this example.");
}

async function main() {
  const client = createClient<paths>({
    baseUrl: process.env.SCI_RAG_URL ?? "http://127.0.0.1:8000",
    headers: { Authorization: `Bearer ${apiKey}` },
  });
  const { data, error } = await client.GET("/v1/status");
  if (error) {
    throw new Error(JSON.stringify(error));
  }

  console.log(`documents=${data.documents}`);
}

main().catch((error: unknown) => {
  console.error(error);
  process.exit(1);
});
```

Type-check and run the example:

```console
$ npx tsc --noEmit --strict --module ESNext --moduleResolution Bundler \
    --target ES2022 --types node generated/typescript/status.ts
$ npx tsx generated/typescript/status.ts
```

<div class="srag-checkpoint" markdown>
**Checkpoint: TypeScript parsed the typed response**

Both commands should exit successfully, and the second prints `documents=`
followed by the same live corpus count as the Python example.
</div>

## Keep authentication and versions explicit

Static keys travel in `Authorization: Bearer <key>`. Grant each key only the
scopes its client needs:

| Scope | Protected operations |
|---|---|
| `retrieval:query` | `POST /v1/query` and the MCP mount |
| `retrieval:answer` | `POST /v1/answer` |
| `corpus:read` | `/v1/documents`, document detail, and `/v1/status` |
| `byo_llm` | Requests that supply `llm_api_key` |

The current OpenAPI document describes the request and response models, but it
does not declare the custom bearer dependency or its scopes. Keep the header in
your client wrapper and handle the stable 401 and 403 error codes documented in
[REST, MCP, and Python API](api.md#authentication).

Treat generated methods under `/v1` as the public REST contract. During 0.x,
minor releases may announce breaking changes with migration notes; patch
releases do not break the contract. Regenerate the client after a server upgrade
and review its diff. The unversioned `/health` method can appear in generated
output, but it is outside the `/v1` compatibility promise. See
[Versioning](VERSIONING.md#what-is-public-api) for the full policy.

## Next steps

- Choose endpoints and error codes in [REST, MCP, and Python API](api.md)
- Review the release rules in [Versioning](VERSIONING.md)
- Configure production access in [Deploy on Google Cloud](deploy-gcp.md)
