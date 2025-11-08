"""Application configuration using Pydantic Settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Application
    app_name: str = "PanelDash"
    debug: bool = False

    # Database - Central
    central_db_host: str = "localhost"
    central_db_port: int = 5432
    central_db_name: str = "paneldash_central"
    central_db_user: str = "postgres"
    central_db_password: str = "postgres"

    # Keycloak
    keycloak_server_url: str = "http://localhost:8080"
    keycloak_realm: str = "paneldash"
    keycloak_client_id: str = "paneldash-api"
    keycloak_client_secret: str = ""

    @property
    def central_database_url(self) -> str:
        """Get the central database URL."""
        return (
            f"postgresql+asyncpg://{self.central_db_user}:{self.central_db_password}"
            f"@{self.central_db_host}:{self.central_db_port}/{self.central_db_name}"
        )


settings = Settings()
