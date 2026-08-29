"""The Cloud SQL development helper, exercised as a real subprocess.

The fake binaries below model the Cloud SQL control plane and a listening
proxy without contacting Google. They let the unit suite prove idempotency,
workspace isolation, secret handling, and lifecycle behavior deterministically.
The credentialed counterpart lives in ``tests/cloud``.
"""

from __future__ import annotations

import json
import os
import runpy
import socket
import stat
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parents[2]
SCRIPT = REPO_ROOT / "scripts" / "cloud_postgres.py"


def _run(
    *args: str, cwd: Path, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    environment = {**os.environ, **(env or {})}
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        env=environment,
        timeout=30,
    )


def _free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _make_executable(path: Path, source: str) -> None:
    path.write_text(f"#!{sys.executable}\n{source}", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


@pytest.fixture
def fake_cloud_tools(tmp_path: Path) -> dict[str, str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    state_file = tmp_path / "instance-state"
    databases_file = tmp_path / "databases"
    command_log = tmp_path / "gcloud.jsonl"
    psql_log = tmp_path / "psql.jsonl"

    _make_executable(
        bin_dir / "gcloud",
        """import json
import os
import pathlib
import sys

args = sys.argv[1:]
with pathlib.Path(os.environ["FAKE_GCLOUD_LOG"]).open("a", encoding="utf-8") as handle:
    handle.write(json.dumps(args) + "\\n")
state_path = pathlib.Path(os.environ["FAKE_INSTANCE_STATE"])
db_path = pathlib.Path(os.environ["FAKE_DATABASES"])
state = state_path.read_text(encoding="utf-8").strip() if state_path.exists() else "STOPPED"

if args[:3] == ["sql", "instances", "describe"]:
    activation = "ALWAYS" if state == "RUNNABLE" else "NEVER"
    print(json.dumps({
        "connectionName": "pisces-476117:us-west1:sci-rag-dev",
        "state": state,
        "settings": {"activationPolicy": activation},
    }))
elif args[:3] == ["sql", "instances", "patch"]:
    policy = next(value.split("=", 1)[1] for value in args if value.startswith("--activation-policy="))
    state_path.write_text("RUNNABLE" if policy == "ALWAYS" else "STOPPED", encoding="utf-8")
elif args[:3] == ["sql", "databases", "list"]:
    if db_path.exists():
        print(db_path.read_text(encoding="utf-8"), end="")
elif args[:3] == ["sql", "databases", "create"]:
    with db_path.open("a", encoding="utf-8") as handle:
        handle.write(args[3] + "\\n")
elif args[:4] == ["secrets", "versions", "access", "latest"]:
    print("unit-test-secret")
else:
    print(f"unexpected gcloud arguments: {args}", file=sys.stderr)
    raise SystemExit(2)
""",
    )
    _make_executable(
        bin_dir / "cloud-sql-proxy",
        """import signal
import socket
import sys

args = sys.argv[1:]
port = int(args[args.index("--port") + 1])
listener = socket.socket()
listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
listener.bind(("127.0.0.1", port))
listener.listen()
running = True

def stop(_signum, _frame):
    global running
    running = False
    listener.close()

signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)
print("Ready for new connections", flush=True)
while running:
    try:
        listener.settimeout(0.1)
        connection, _address = listener.accept()
        connection.close()
    except (TimeoutError, OSError):
        pass
""",
    )
    _make_executable(
        bin_dir / "psql",
        """import json
import os
import pathlib
import sys

with pathlib.Path(os.environ["FAKE_PSQL_LOG"]).open("a", encoding="utf-8") as handle:
    handle.write(json.dumps({"args": sys.argv[1:], "pgpass": os.environ.get("PGPASSFILE")}) + "\\n")
""",
    )
    return {
        "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
        "FAKE_GCLOUD_LOG": str(command_log),
        "FAKE_INSTANCE_STATE": str(state_file),
        "FAKE_DATABASES": str(databases_file),
        "FAKE_PSQL_LOG": str(psql_log),
    }


def test_config_reports_workspace_scoped_passwordless_urls(tmp_path: Path) -> None:
    workspace = tmp_path / "Davis V3"
    workspace.mkdir()
    result = _run("config", cwd=workspace)

    assert result.returncode == 0, result.stderr
    values = dict(line.split("=", 1) for line in result.stdout.strip().splitlines())
    assert values["project"] == "pisces-476117"
    assert values["instance"] == "sci-rag-dev"
    assert values["region"] == "us-west1"
    assert values["workspace"] == "davis_v3"
    assert values["database"] == "sci_rag_davis_v3"
    assert values["test_database"] == "sci_rag_test_davis_v3"
    assert Path(values["state_dir"]) == workspace / ".cloudsql"
    assert "password" not in values["url"]
    assert "passfile=" in values["url"]
    assert values["SCI_RAG_DATABASE_URL"] == values["url"]
    assert values["SCI_RAG_TEST_DATABASE_URL"] == values["test_url"]
    assert "unit-test-secret" not in result.stdout + result.stderr


def test_config_honours_environment_overrides(tmp_path: Path) -> None:
    result = _run(
        "config",
        cwd=tmp_path,
        env={
            "SCI_RAG_CLOUD_PG_PROJECT": "other-project",
            "SCI_RAG_CLOUD_PG_INSTANCE": "other-instance",
            "SCI_RAG_CLOUD_PG_REGION": "us-east1",
            "SCI_RAG_CLOUD_PG_DIR": "state",
            "SCI_RAG_CLOUD_PG_PORT": "5999",
            "SCI_RAG_CLOUD_PG_WORKSPACE": "Experiment 42",
            "SCI_RAG_CLOUD_PG_USER": "researcher",
        },
    )

    assert result.returncode == 0, result.stderr
    values = dict(line.split("=", 1) for line in result.stdout.strip().splitlines())
    assert values["connection_name"] == "other-project:us-east1:other-instance"
    assert values["workspace"] == "experiment_42"
    assert values["database"] == "sci_rag_experiment_42"
    assert values["user"] == "researcher"
    assert values["port"] == "5999"
    assert Path(values["state_dir"]) == tmp_path / "state"


def test_config_walks_up_from_a_bound_port(tmp_path: Path) -> None:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        occupied = int(listener.getsockname()[1])
        result = _run(
            "config",
            cwd=tmp_path,
            env={"SCI_RAG_CLOUD_PG_PORT": str(occupied)},
        )

    assert result.returncode == 0, result.stderr
    values = dict(line.split("=", 1) for line in result.stdout.strip().splitlines())
    assert int(values["port"]) > occupied


def test_proxy_readiness_retries_before_ps_exposes_the_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = runpy.run_path(str(SCRIPT), run_name="cloud_postgres_test")
    config = module["Config"](
        project="pisces-476117",
        instance="sci-rag-dev",
        region="us-west1",
        state_dir=tmp_path,
        port=_free_port(),
        workspace="race",
        user="sci_rag",
    )
    config.pid_file.write_text("123\n", encoding="utf-8")
    commands = iter(["", f"cloud-sql-proxy {config.connection_name}"])

    class Connection:
        def __enter__(self) -> Connection:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

    helper_globals = module["_wait_for_proxy"].__globals__
    monkeypatch.setitem(helper_globals, "_process_command", lambda _pid: next(commands))
    monkeypatch.setattr(helper_globals["time"], "sleep", lambda _seconds: None)
    monkeypatch.setattr(
        helper_globals["socket"], "create_connection", lambda *_args, **_kwargs: Connection()
    )

    module["_wait_for_proxy"](config)


def test_pause_waits_through_transitional_instance_states(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = runpy.run_path(str(SCRIPT), run_name="cloud_postgres_test")
    config = module["Config"](
        project="pisces-476117",
        instance="sci-rag-dev",
        region="us-west1",
        state_dir=tmp_path,
        port=_free_port(),
        workspace="transition",
        user="sci_rag",
    )
    states = iter([{"state": "MAINTENANCE"}, {"state": "STOPPED"}])
    helper_globals = module["_wait_for_instance"].__globals__
    monkeypatch.setitem(helper_globals, "_instance_details", lambda _config: next(states))
    monkeypatch.setattr(helper_globals["time"], "sleep", lambda _seconds: None)

    assert module["_wait_for_instance"](config, running=False)["state"] == "STOPPED"


def test_start_without_required_tools_has_install_guidance(tmp_path: Path) -> None:
    empty_bin = tmp_path / "empty-bin"
    empty_bin.mkdir()
    result = _run("start", cwd=tmp_path, env={"PATH": str(empty_bin)})

    assert result.returncode != 0
    message = result.stdout + result.stderr
    assert "gcloud" in message
    assert "cloud-sql-proxy" in message
    assert "psql" in message
    assert not (tmp_path / ".cloudsql").exists()


def test_start_is_idempotent_and_creates_both_workspace_databases(
    tmp_path: Path, fake_cloud_tools: dict[str, str]
) -> None:
    workspace = tmp_path / "workspace-one"
    workspace.mkdir()
    env = {
        **fake_cloud_tools,
        "SCI_RAG_CLOUD_PG_PORT": str(_free_port()),
    }
    try:
        first = _run("start", cwd=workspace, env=env)
        assert first.returncode == 0, first.stdout + first.stderr
        assert "ready:" in first.stdout

        state_dir = workspace / ".cloudsql"
        password = state_dir / "password"
        pgpass = state_dir / "pgpass"
        assert password.read_text(encoding="utf-8") == "unit-test-secret"
        assert stat.S_IMODE(password.stat().st_mode) == 0o600
        assert stat.S_IMODE(pgpass.stat().st_mode) == 0o600
        assert "unit-test-secret" not in first.stdout + first.stderr

        databases = Path(env["FAKE_DATABASES"]).read_text(encoding="utf-8").splitlines()
        assert databases == ["sci_rag_workspace_one", "sci_rag_test_workspace_one"]
        psql_calls = [
            json.loads(line)
            for line in Path(env["FAKE_PSQL_LOG"]).read_text(encoding="utf-8").splitlines()
        ]
        assert len(psql_calls) == 2
        assert {call["args"][call["args"].index("-d") + 1] for call in psql_calls} == set(databases)
        assert all(call["pgpass"] == str(pgpass) for call in psql_calls)

        again = _run("start", cwd=workspace, env=env)
        assert again.returncode == 0, again.stdout + again.stderr
        assert "already running" in again.stdout.lower()
        assert Path(env["FAKE_DATABASES"]).read_text(encoding="utf-8").splitlines() == databases

        status_result = _run("status", cwd=workspace, env=env)
        assert status_result.returncode == 0, status_result.stdout + status_result.stderr
        assert "RUNNABLE" in status_result.stdout
        assert "proxy=running" in status_result.stdout
        assert "sci_rag_workspace_one" in status_result.stdout
    finally:
        stopped = _run("stop", cwd=workspace, env=env)
        assert stopped.returncode == 0, stopped.stdout + stopped.stderr

    assert "not running" in _run("stop", cwd=workspace, env=env).stdout.lower()


def test_pause_stops_only_the_workspace_proxy_and_resume_reactivates_the_instance(
    tmp_path: Path, fake_cloud_tools: dict[str, str]
) -> None:
    workspace = tmp_path / "workspace-two"
    workspace.mkdir()
    env = {
        **fake_cloud_tools,
        "SCI_RAG_CLOUD_PG_PORT": str(_free_port()),
    }
    started = _run("start", cwd=workspace, env=env)
    assert started.returncode == 0, started.stdout + started.stderr

    paused = _run("pause", cwd=workspace, env=env)
    assert paused.returncode == 0, paused.stdout + paused.stderr
    assert "NEVER" in paused.stdout
    status_result = _run("status", cwd=workspace, env=env)
    assert status_result.returncode == 1
    assert "STOPPED" in status_result.stdout
    assert "proxy=stopped" in status_result.stdout

    resumed = _run("resume", cwd=workspace, env=env)
    assert resumed.returncode == 0, resumed.stdout + resumed.stderr
    assert "ALWAYS" in resumed.stdout
    assert Path(fake_cloud_tools["FAKE_INSTANCE_STATE"]).read_text(encoding="utf-8") == "RUNNABLE"


def test_two_running_workspaces_choose_distinct_database_names_and_ports(
    tmp_path: Path, fake_cloud_tools: dict[str, str]
) -> None:
    base_port = _free_port()
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    env = {**fake_cloud_tools, "SCI_RAG_CLOUD_PG_PORT": str(base_port)}
    try:
        first_start = _run("start", cwd=first, env=env)
        assert first_start.returncode == 0, first_start.stdout + first_start.stderr
        second_start = _run("start", cwd=second, env=env)
        assert second_start.returncode == 0, second_start.stdout + second_start.stderr
        first_values = dict(
            line.split("=", 1)
            for line in _run("config", cwd=first, env=env).stdout.strip().splitlines()
        )
        second_values = dict(
            line.split("=", 1)
            for line in _run("config", cwd=second, env=env).stdout.strip().splitlines()
        )
    finally:
        _run("stop", cwd=first, env=env)
        _run("stop", cwd=second, env=env)

    assert first_values["database"] != second_values["database"]
    assert first_values["test_database"] != second_values["test_database"]
    assert first_values["port"] != second_values["port"]
