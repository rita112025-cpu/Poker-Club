from collections.abc import Iterator
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.main import app


def test_liveness_does_not_need_database() -> None:
    with TestClient(app) as client:
        response = client.get("/api/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "phase": "1"}


def test_readiness_unavailable_does_not_leak_details() -> None:
    session = MagicMock(spec=Session)
    session.execute.side_effect = OperationalError("secret SQL", {}, Exception("secret password"))

    def override() -> Iterator[Session]:
        yield session

    app.dependency_overrides[get_session] = override
    try:
        with TestClient(app) as client:
            response = client.get("/api/health/ready")
        assert response.status_code == 503
        assert response.json() == {"detail": "Database is unavailable"}
        assert "secret" not in response.text
    finally:
        app.dependency_overrides.clear()


def test_readiness_requires_current_schema() -> None:
    session = MagicMock(spec=Session)

    def override() -> Iterator[Session]:
        yield session

    app.dependency_overrides[get_session] = override
    try:
        with TestClient(app) as client:
            session.execute.return_value.scalar.side_effect = ["old_revision", 4]
            assert client.get("/api/health/ready").status_code == 503
            session.execute.return_value.scalar.side_effect = ["0001_game_types", 4]
            assert client.get("/api/health/ready").json() == {"status": "ready"}
    finally:
        app.dependency_overrides.clear()
