"""Create the fresh PostgreSQL database used by one benchmark run.

Entity resolution intentionally mutates graph state. Reusing a database would
make a later run's "pre-resolution" measurement false, so the benchmark gets a
new database instead of deleting audit evidence or trying to reverse merges.
"""

from __future__ import annotations

import argparse
import asyncio
import re

from sqlalchemy import URL, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

_SAFE_DATABASE_NAME = re.compile(r"[a-z][a-z0-9_]{0,62}\Z")


def benchmark_database_urls(database_url: str, name: str) -> tuple[URL, URL]:
    """Return the admin and fresh-run URLs after validating the identifier."""
    if _SAFE_DATABASE_NAME.fullmatch(name) is None:
        raise ValueError(
            "benchmark database name must be a lowercase PostgreSQL identifier "
            "of at most 63 characters"
        )
    base = make_url(database_url)
    if not base.drivername.startswith("postgresql"):
        raise ValueError("benchmark database creation requires a PostgreSQL database URL")
    return base.set(database="postgres"), base.set(database=name)


async def create_benchmark_database(database_url: str, name: str) -> str:
    """Create ``name`` once and return its URL without masking the password."""
    admin_url, benchmark_url = benchmark_database_urls(database_url, name)
    engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as connection:
            exists = await connection.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": name}
            )
            if exists:
                raise RuntimeError(f"refusing to reuse benchmark database {name!r}")
            # The strict identifier validation above makes quoting deterministic
            # while CREATE DATABASE remains outside PostgreSQL bind parameters.
            await connection.execute(text(f'CREATE DATABASE "{name}"'))
    finally:
        await engine.dispose()
    return benchmark_url.render_as_string(hide_password=False)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True, help="Fresh database name for this run.")
    args = parser.parse_args()

    from sci_rag.config import get_settings

    try:
        url = asyncio.run(create_benchmark_database(get_settings().database_url, args.name))
    except Exception as exc:
        raise SystemExit(f"could not create the benchmark database: {exc}") from None
    # Make captures this value into an environment variable. Do not add other
    # stdout output here because the URL may contain credentials.
    print(url)


if __name__ == "__main__":
    main()
