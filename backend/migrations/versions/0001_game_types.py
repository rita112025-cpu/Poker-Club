"""Initial game catalog; all engines remain unavailable in Phase 1."""

import uuid

import sqlalchemy as sa
from alembic import op

revision = "0001_game_types"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    catalog = op.create_table(
        "game_types",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("min_players", sa.Integer(), nullable=False),
        sa.Column("max_players", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("min_players >= 2", name=op.f("ck_game_types_min_players")),
        sa.CheckConstraint("max_players >= min_players", name=op.f("ck_game_types_player_range")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_game_types")),
        sa.UniqueConstraint("code", name=op.f("uq_game_types_code")),
    )
    op.bulk_insert(
        catalog,
        [
            {
                "id": uuid.UUID(f"00000000-0000-0000-0000-{index:012d}"),
                "code": code,
                "name": name,
                "min_players": minimum,
                "max_players": maximum,
                "enabled": False,
            }
            for index, (code, name, minimum, maximum) in enumerate(
                [
                    ("texas_holdem", "德州撲克", 2, 9),
                    ("big_two", "大老二", 2, 4),
                    ("chinese_poker", "十三支", 2, 4),
                    ("five_card_draw", "五張抽牌", 2, 6),
                ],
                start=1,
            )
        ],
    )


def downgrade() -> None:
    op.drop_table("game_types")
