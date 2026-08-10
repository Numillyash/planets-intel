from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Planets.nu Intel Client"
    environment: str = "development"

    database_url: str = (
        "postgresql+psycopg://planets:planets@postgres:5432/planets_intel"
    )

    planetsnu_api_base_url: str = "http://api.planets.nu"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
