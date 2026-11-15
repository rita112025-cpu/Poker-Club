"""Verify Phase 1 against real containers in an isolated, disposable Compose project.

Run with the repository .venv Python. Requires Docker engine, Compose and the
installed backend dev dependencies. Never touches the default project's volumes.
"""

import argparse
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--compose", help="Path to standalone Compose; otherwise use docker compose"
    )
    args = parser.parse_args()
    executable = (
        str(Path(args.compose).resolve()) if args.compose else shutil.which("docker")
    )
    if not executable:
        print(
            "BLOCKED: Docker CLI/engine not available; no container acceptance performed."
        )
        return 2
    base = [executable] if args.compose else [executable, "compose"]
    project = f"poker-p1-verify-{uuid.uuid4().hex[:12]}"
    password = secrets.token_urlsafe(32)
    db_port, app_port = free_port(), free_port()
    while app_port == db_port:
        app_port = free_port()
    started = False
    result = 1

    def run(command: list[str], *, env: dict[str, str] | None = None) -> str:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if completed.returncode:
            message = (completed.stdout + completed.stderr).replace(
                password, "[REDACTED]"
            )
            raise RuntimeError(message)
        return completed.stdout

    def check_http(route: str, expected: dict[str, str] | None = None) -> None:
        deadline = time.monotonic() + 30
        while True:
            try:
                with urlopen(
                    f"http://127.0.0.1:{app_port}{route}", timeout=5
                ) as response:
                    body = response.read().decode("utf-8")
                    if expected is not None:
                        assert json.loads(body) == expected
                    else:
                        assert "Poker Club" in body
                return
            except (OSError, AssertionError):
                if time.monotonic() >= deadline:
                    raise
                time.sleep(1)

    with tempfile.TemporaryDirectory(prefix="poker-p1-verify-") as temporary:
        env_file = Path(temporary) / ".env"
        env_file.write_text(
            f"POSTGRES_USER=poker\nPOSTGRES_PASSWORD={password}\nPOSTGRES_DB=poker_club\n"
            f"DB_PORT={db_port}\nAPP_PORT={app_port}\n",
            encoding="utf-8",
        )
        # Shell variables override --env-file; explicitly isolate this project's settings.
        environment = os.environ.copy()
        for name in (
            "POSTGRES_USER",
            "POSTGRES_PASSWORD",
            "POSTGRES_DB",
            "DB_PORT",
            "APP_PORT",
        ):
            environment.pop(name, None)
        compose = [
            *base,
            "--project-name",
            project,
            "--env-file",
            str(env_file),
            "--file",
            str(ROOT / "compose.yaml"),
        ]

        def invoke(*arguments: str) -> str:
            return run([*compose, *arguments], env=environment)

        def sql(statement: str) -> str:
            return invoke(
                "exec",
                "-T",
                "db",
                "psql",
                "-U",
                "poker",
                "-d",
                "poker_club",
                "-v",
                "ON_ERROR_STOP=1",
                "-Atc",
                statement,
            ).strip()

        try:
            invoke("config", "--quiet")
            print("PASS: Compose configuration", flush=True)
            invoke("ls", "--format", "json")
            print("PASS: Docker engine reachable", flush=True)
            started = True
            print(
                "RUN: build and start isolated containers (may take several minutes)",
                flush=True,
            )
            invoke("up", "--build", "--detach", "--wait", "--wait-timeout", "180")
            invoke("exec", "-T", "web", "nginx", "-t")
            print("PASS: container startup and nginx -t", flush=True)
            check_http("/")
            check_http("/api/health/live", {"status": "ok", "phase": "1"})
            check_http("/api/health/ready", {"status": "ready"})
            assert sql("SELECT version_num FROM alembic_version") == "0001_game_types"
            assert sql("SELECT count(*) FROM game_types WHERE NOT enabled") == "4"
            print("PASS: frontend, proxy, API readiness and migration", flush=True)

            test_environment = environment.copy()
            test_environment["TEST_DATABASE_URL"] = (
                f"postgresql+psycopg://poker:{password}@127.0.0.1:{db_port}/poker_club"
            )
            output = run(
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "backend/tests",
                    "-m",
                    "postgres",
                    "-q",
                ],
                env=test_environment,
            )
            if "skipped" in output:
                raise RuntimeError(
                    "PostgreSQL acceptance must not contain skipped tests"
                )
            print(output, flush=True)

            marker = str(uuid.uuid4())
            sql("CREATE TABLE acceptance_probe (id uuid PRIMARY KEY)")
            sql(f"INSERT INTO acceptance_probe VALUES ('{marker}')")
            invoke("restart", "db")
            invoke("up", "--detach", "--wait", "--wait-timeout", "120")
            assert sql("SELECT id FROM acceptance_probe") == marker
            check_http("/api/health/ready", {"status": "ready"})
            print("PASS: PostgreSQL restart persistence and API reconnect", flush=True)
            result = 0
        except (RuntimeError, OSError, AssertionError) as error:
            print(f"FAIL/BLOCKED: {error}", file=sys.stderr, flush=True)
        finally:
            if started:
                try:
                    invoke("down", "--volumes", "--remove-orphans")
                    print(
                        f"CLEANUP: removed only disposable project {project}",
                        flush=True,
                    )
                except RuntimeError as error:
                    print(f"CLEANUP FAILED for {project}: {error}", file=sys.stderr)
                    result = 1
    if result == 0:
        print(
            "PASS: Phase 1 Docker acceptance checks completed; not production acceptance."
        )
    return result


if __name__ == "__main__":
    raise SystemExit(main())
