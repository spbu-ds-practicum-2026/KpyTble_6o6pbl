from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="ROOM_",
        extra="ignore",
    )

    database_url: str = "postgresql+asyncpg://room:room@localhost:5432/roomdb"
    host: str = "0.0.0.0"
    port: int = 8000

    # Prototype: one service instance, in-memory locks and timers.
    host_disconnect_grace_seconds: float = 10.0

    # Event delivery to API Gateway: "http" (default), "logging" or "null".
    event_publisher: str = "http"
    api_events_url: str = "http://api-gateway:8080/internal/room-events"
    api_events_timeout_seconds: float = 2.0

    invite_base_url: str = "http://localhost:3000/rooms"

    auto_create_tables: bool = True
    sql_echo: bool = False


def get_settings() -> Settings:
    return Settings()
