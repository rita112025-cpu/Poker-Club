from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text

from app.core.config import get_settings
from app.db.base import Base
from app.db.models import GameType  # noqa: F401


def test_migration_round_trip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """SQLite smoke test only; does not certify PostgreSQL behavior."""
    run_round_trip(f"sqlite:///{tmp_path / 'migration.db'}", monkeypatch)


@pytest.mark.postgres
def test_postgres_migration_round_trip(postgres_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    run_round_trip(postgres_url, monkeypatch)


def run_round_trip(url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    engine = create_engine(url)
    try:
        if inspect(engine).get_table_names():
            pytest.fail("Migration test requires an empty disposable database")
        monkeypatch.setenv("DATABASE_URL", url)
        get_settings.cache_clear()
        config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
        command.upgrade(config, "head")
        with engine.connect() as connection:
            rows = connection.execute(text("SELECT code, enabled FROM game_types")).all()
            assert len(rows) == 4
            assert all(not row.enabled for row in rows)
            assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
        command.downgrade(config, "base")
        assert "game_types" not in inspect(engine).get_table_names()
        command.upgrade(config, "head")
        assert "game_types" in inspect(engine).get_table_names()
    finally:
        engine.dispose()
        get_settings.cache_clear()
