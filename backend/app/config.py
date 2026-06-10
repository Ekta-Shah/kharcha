from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://kharcha:kharcha@localhost:5432/kharcha"
    anthropic_api_key: str = ""
    llm_model: str = "claude-sonnet-4-5"
    cors_origins: str = "http://localhost:5173"
    auth_token: str = ""  # if empty, auth is disabled (dev mode)

    model_config = {"env_file": ".env"}


settings = Settings()
