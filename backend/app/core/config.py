from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://poker:poker@localhost:5432/poker_club"
    cors_origins: list[str] = ["http://localhost:5173"]

    # PROTOTYPE ONLY (path B): in-memory playable table. No authentication, persistence or
    # idempotency, so it is off unless PROTOTYPE_ENABLED=true. The rule values below are
    # prototype settings, NOT approved product policy (blinds, starting points, burning).
    prototype_enabled: bool = False
    big_two_prototype_enabled: bool = False
    prototype_small_blind: int = 5
    prototype_big_blind: int = 10
    prototype_starting_points: int = 1000
    prototype_burn_cards: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
