import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class GameType(Base):
    __tablename__ = "game_types"
    __table_args__ = (
        CheckConstraint("min_players >= 2", name="min_players"),
        CheckConstraint("max_players >= min_players", name="player_range"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(64))
    min_players: Mapped[int]
    max_players: Mapped[int]
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
