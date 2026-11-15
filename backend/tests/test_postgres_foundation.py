import uuid
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_session
from app.main import app

pytestmark = pytest.mark.postgres


@pytest.fixture
def migrated_engine(postgres_url: str, monkeypatch: pytest.MonkeyPatch) -> Iterator[Engine]:
    monkeypatch.setenv("DATABASE_URL", postgres_url)
    get_settings.cache_clear()
    engine = create_engine(postgres_url)
    try:
        command.upgrade(Config(str(Path(__file__).parents[1] / "alembic.ini")), "head")
        yield engine
    finally:
        engine.dispose()
        get_settings.cache_clear()


def test_native_uuid_utc_and_disabled_catalog(migrated_engine: Engine) -> None:
    with migrated_engine.connect() as connection:
        assert connection.execute(text("SHOW TimeZone")).scalar() == "UTC"
        rows = connection.execute(
            text("SELECT id, name, enabled, created_at FROM game_types")
        ).all()
        assert len(rows) == 4
        assert {row.name for row in rows} == {"德州撲克", "大老二", "十三支", "五張抽牌"}
        for row in rows:
            assert isinstance(row.id, uuid.UUID)
            assert row.enabled is False
            assert row.created_at.utcoffset() == timedelta(0)


def test_unique_and_player_range_constraints(migrated_engine: Engine) -> None:
    insert = text(
        "INSERT INTO game_types (id, code, name, min_players, max_players) "
        "VALUES (:id, :code, 'constraint-test', :minimum, :maximum)"
    )
    for code, minimum, maximum in [
        ("texas_holdem", 2, 9),
        ("invalid_min", 1, 4),
        ("invalid_range", 4, 2),
    ]:
        with pytest.raises(IntegrityError), migrated_engine.begin() as connection:
            connection.execute(
                insert, {"id": uuid.uuid4(), "code": code, "minimum": minimum, "maximum": maximum}
            )
    with migrated_engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM game_types")).scalar() == 4


def test_write_is_rolled_back_on_failure(migrated_engine: Engine) -> None:
    with pytest.raises(RuntimeError, match="intentional rollback"):
        with migrated_engine.begin() as connection:
            connection.execute(text("UPDATE game_types SET enabled = true"))
            raise RuntimeError("intentional rollback")
    with migrated_engine.connect() as connection:
        assert (
            connection.execute(text("SELECT count(*) FROM game_types WHERE enabled")).scalar() == 0
        )


def test_readiness_against_real_postgres(migrated_engine: Engine) -> None:
    with migrated_engine.connect() as connection:
        transaction = connection.begin()
        with Session(bind=connection) as session:

            def override() -> Iterator[Session]:
                yield session

            app.dependency_overrides[get_session] = override
            try:
                with TestClient(app) as client:
                    response = client.get("/api/health/ready")
                    assert response.status_code == 200
                    assert response.json() == {"status": "ready"}
                    connection.execute(text("UPDATE alembic_version SET version_num = 'outdated'"))
                    assert client.get("/api/health/ready").status_code == 503
            finally:
                app.dependency_overrides.clear()
                transaction.rollback()
