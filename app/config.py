"""
Central configuration for the Interview Prep application.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- LLM provider settings (Google Gemini) ----------------------------------
    gemini_api_key: str = ""
    # Default model — override in .env if you want a different Gemini model.
    gemini_model: str = "gemini-3.6-flash"
    llm_max_tokens: int = 2200
    llm_temperature: float = 0.4

    # --- App settings ------------------------------------------------------------
    app_name: str = "AI Interview Coach"
    max_upload_mb: int = 8
    allowed_resume_types: tuple = (".pdf", ".docx", ".txt")

    # --- CORS ----------------------------------------------------------------------
    cors_origins: list[str] = ["*"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
