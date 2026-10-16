from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "TaskBoard API"
    app_version: str = "1.0.0"
    database_url: str = "postgresql+psycopg://taskboard:taskboard@localhost:5432/taskboard"
    log_level: str = "info"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
