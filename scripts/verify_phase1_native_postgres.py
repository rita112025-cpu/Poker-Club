"""Verify a real disposable PostgreSQL cluster and API without installing a service.

Requires extracted PostgreSQL binaries and backend dev dependencies. Data/logs
stay under .local-data for inspection; only processes created here are stopped.
This verifies native PostgreSQL, not Docker or Nginx.
"""

import argparse
import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo

ROOT = Path(__file__).resolve().parents[1]
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pg-bin", required=True, type=Path)
    args = parser.parse_args()
    binary = args.pg_bin.resolve()
    suffix = ".exe" if os.name == "nt" else ""
    for name in ("initdb", "pg_ctl", "postgres"):
        if not (binary / f"{name}{suffix}").is_file():
            parser.error(f"Missing PostgreSQL binary: {name}")
    local_root = (ROOT / ".local-data").resolve()
    work = local_root / f"p1-native-{uuid.uuid4().hex[:12]}"
    assert work.resolve().is_relative_to(local_root)
    work.mkdir(parents=True)
    data = work / "data"
    password = secrets.token_urlsafe(32)
    password_file = work / "postgres.pw"
    password_file.write_text(password, encoding="ascii")
    db_port, api_port = free_port(), free_port()
    while api_port == db_port:
        api_port = free_port()
    database = "poker_club_acceptance"
    environment = os.environ.copy()
    environment["PYTHONUTF8"] = "1"
    database_url = (
        f"postgresql+psycopg://poker:{password}@127.0.0.1:{db_port}/{database}"
    )
    environment["DATABASE_URL"] = database_url
    environment["TEST_DATABASE_URL"] = database_url
    cluster_started = False
    api: subprocess.Popen[str] | None = None
    checks: list[str] = []

    def run(command: list[str], cwd: Path = ROOT) -> str:
        # pg_ctl's Windows descendants can inherit pipe handles. A file avoids
        # communicate() waiting for a running server to close inherited pipes.
        with tempfile.TemporaryFile(
            mode="w+", encoding="utf-8", errors="replace"
        ) as output:
            completed = subprocess.run(
                command,
                cwd=cwd,
                env=environment,
                stdout=output,
                stderr=subprocess.STDOUT,
                creationflags=NO_WINDOW,
                timeout=120,
                check=False,
            )
            output.seek(0)
            captured = output.read()
        if completed.returncode:
            raise RuntimeError(captured.replace(password, "[REDACTED]"))
        return captured

    def control(action: str) -> None:
        options = [
            str(binary / f"pg_ctl{suffix}"),
            action,
            "-D",
            str(data),
            "-w",
            "-t",
            "30",
        ]
        if action == "start":
            options += [
                "-l",
                str(work / "postgres.log"),
                "-o",
                f"-h 127.0.0.1 -p {db_port} -c timezone=UTC",
            ]
        else:
            options += ["-m", "fast"]
        run(options)

    def http(route: str, status: int, body: dict[str, str] | None = None) -> None:
        deadline = time.monotonic() + 20
        while True:
            try:
                try:
                    response = urlopen(f"http://127.0.0.1:{api_port}{route}", timeout=5)
                except HTTPError as error:
                    response = error
                with response:
                    assert response.status == status
                    if body is not None:
                        assert json.load(response) == body
                return
            except (OSError, AssertionError):
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.5)

    connection_info = make_conninfo(
        host="127.0.0.1",
        port=db_port,
        user="poker",
        password=password,
        connect_timeout=5,
    )
    result = 1
    with (work / "api.log").open("w", encoding="utf-8") as api_log:
        try:
            version = run([str(binary / f"postgres{suffix}"), "--version"]).strip()
            print(version, flush=True)
            run(
                [
                    str(binary / f"initdb{suffix}"),
                    "-D",
                    str(data),
                    "-U",
                    "poker",
                    "--auth-host=scram-sha-256",
                    "--auth-local=scram-sha-256",
                    f"--pwfile={password_file}",
                    "--encoding=UTF8",
                    "--locale=C",
                ]
            )
            # Set before launch so cleanup also covers a startup timeout.
            cluster_started = True
            control("start")
            with psycopg.connect(
                connection_info, dbname="postgres", autocommit=True
            ) as conn:
                conn.execute(
                    sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database))
                )
            output = run([sys.executable, "-m", "pytest", "backend/tests", "-q"])
            print(output, flush=True)
            if "skipped" in output:
                raise RuntimeError("Native PostgreSQL acceptance must not skip tests")
            checks.append("pytest passed without skips")
            run([sys.executable, "-m", "alembic", "upgrade", "head"], ROOT / "backend")
            marker = uuid.uuid4()
            with psycopg.connect(connection_info, dbname=database) as conn:
                conn.execute("CREATE TABLE acceptance_probe (id uuid PRIMARY KEY)")
                conn.execute("INSERT INTO acceptance_probe VALUES (%s)", (marker,))
            api = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "app.main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(api_port),
                    "--no-access-log",
                ],
                cwd=ROOT / "backend",
                env=environment,
                stdout=api_log,
                stderr=api_log,
                text=True,
                creationflags=NO_WINDOW,
            )
            http("/api/health/live", 200, {"status": "ok", "phase": "1"})
            http("/api/health/ready", 200, {"status": "ready"})
            checks.append("real HTTP: live=200, ready=200")
            control("stop")
            cluster_started = False
            http("/api/health/live", 200, {"status": "ok", "phase": "1"})
            http("/api/health/ready", 503, {"detail": "Database is unavailable"})
            checks.append(
                "database stopped: live=200, ready=503 without secret details"
            )
            cluster_started = True
            control("start")
            with psycopg.connect(connection_info, dbname=database) as conn:
                row = conn.execute("SELECT id FROM acceptance_probe").fetchone()
                assert row is not None and row[0] == marker
            http("/api/health/ready", 200, {"status": "ready"})
            checks.append(
                "database restart: marker persisted, API recovered to ready=200"
            )
            result = 0
        except (
            RuntimeError,
            OSError,
            AssertionError,
            psycopg.Error,
            subprocess.TimeoutExpired,
        ) as error:
            print(
                f"FAIL: {str(error).replace(password, '[REDACTED]')}", file=sys.stderr
            )
        finally:
            if api is not None:
                api.terminate()
                try:
                    api.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    api.kill()
                    api.wait(timeout=10)
            if cluster_started:
                try:
                    control("stop")
                except (RuntimeError, subprocess.TimeoutExpired) as error:
                    print(f"CLEANUP FAILED: {error}", file=sys.stderr)
                    result = 1
    evidence = {
        "scope": "native PostgreSQL only; Docker/Nginx not validated",
        "passed": result == 0,
        "checks": checks,
        "data_directory": str(work.relative_to(ROOT)),
    }
    (work / "result.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(evidence, ensure_ascii=False, indent=2), flush=True)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
