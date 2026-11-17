from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_session

app = FastAPI(title="Poker Club", version="0.1.0")
if get_settings().prototype_enabled:
    from app.prototype.routes import build_router

    app.include_router(build_router(get_settings()))
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["Content-Type"],
)


@app.get("/api/health/live")
def liveness() -> dict[str, str]:
    return {"status": "ok", "phase": "1"}


@app.get("/api/health/ready")
def readiness(session: Annotated[Session, Depends(get_session)]) -> dict[str, str]:
    try:
        revision = session.execute(text("SELECT version_num FROM alembic_version")).scalar()
        count = session.execute(text("SELECT count(*) FROM game_types")).scalar()
        if revision != "0001_game_types" or count != 4:
            raise HTTPException(status_code=503, detail="Database migration is not ready")
    except SQLAlchemyError:
        # Never expose connection strings or SQL parameters in responses/logs.
        raise HTTPException(status_code=503, detail="Database is unavailable") from None
    return {"status": "ready"}
