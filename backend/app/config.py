from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://kharcha:kharcha@localhost:5432/kharcha"
    llm_provider: str = "gemini"          # "gemini" | "groq" | "ollama"
    gemini_api_key: str = ""
    llm_model: str = "gemini-2.5-flash"
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_model: str = "llama3.1:8b"
    cors_origins: str = "http://localhost:5173"
    auth_token: str = ""  # if empty, auth is disabled (dev mode)

    model_config = {"env_file": ".env"}


settings = Settings()
