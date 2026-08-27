# Convenience targets. Everything here is just the underlying command,
# spelled out; run `make <target>` or copy the command, whichever you like.

.PHONY: setup db-up db-down db-upgrade demo demo-cloud test lint typecheck check serve mcp eval eval-ablation clean-demo

## setup: install dependencies, start Postgres, create the schema
setup:
	uv sync
	docker compose up -d --wait
	uv run sci-rag db upgrade

db-up:
	docker compose up -d --wait

db-down:
	docker compose down

db-upgrade:
	uv run sci-rag db upgrade

## demo: ingest the offline demo corpus and run a scored retrieval check.
## Works with zero credentials (uses the deterministic local-hash embedder
## if you set SCI_RAG_EMBEDDING_PROVIDER=local-hash, or real embeddings if
## you configured Google credentials in .env).
demo:
	uv run sci-rag ingest --manifest data/demo/manifest.jsonl
	uv run sci-rag retrieve "How much rice straw was generated in the Colusa Basin in 2023?" --profile interactive --limit 3
	uv run sci-rag eval retrieval
	@echo ""
	@echo "Next: add Google credentials to .env (see .env.example), then run"
	@echo "'make demo-cloud' for graph extraction, deep retrieval, and answers."

## demo-cloud: the full pipeline on the demo corpus (needs Google credentials)
demo-cloud:
	uv run sci-rag graph extract
	uv run sci-rag graph communities
	uv run sci-rag answer "What conversion route suits rice straw given its ash content, and what yields should I expect?"
	uv run sci-rag eval retrieval --ablation

test:
	uv run pytest

lint:
	uv run ruff check src tests
	uv run ruff format --check src tests

typecheck:
	uv run mypy

## check: everything CI runs
check: lint typecheck test

serve:
	uv run sci-rag serve

mcp:
	uv run sci-rag mcp

eval:
	uv run sci-rag eval retrieval

eval-ablation:
	uv run sci-rag eval retrieval --ablation
