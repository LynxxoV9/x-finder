import os
from pathlib import Path
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Recherche explicite du fichier .env dans le dossier backend ou à la racine
ENV_BACKEND = Path(__file__).resolve().parent.parent / ".env"
ENV_ROOT = Path(__file__).resolve().parent.parent.parent / ".env"

if ENV_BACKEND.exists():
    load_dotenv(ENV_BACKEND)
elif ENV_ROOT.exists():
    load_dotenv(ENV_ROOT)
else:
    load_dotenv()

class Settings(BaseSettings):
    # Fournisseur LLM RodiumAI
    RODIUMAI_API_KEY: str = os.getenv("RODIUMAI_API_KEY", "")
    BASE_URL: str = os.getenv("BASE_URL", "https://api.rodiumai.io/v1").rstrip("/")
    ALLOWED_MODELS: str = os.getenv(
        "ALLOWED_MODELS",
        "google/gemini-2.5-flash-lite,google/gemini-3.8-flash,anthropic/claude-sonnet-4-5-20250929",
    )
    DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", "google/gemini-2.5-flash-lite")

    # Moteur de recherche web
    TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")

    # Météo
    WEATHER_API_KEY: str = os.getenv("WEATHER_API_KEY", "")
    OPENWEATHER_API_KEY: str = os.getenv("OPENWEATHER_API_KEY", "")

    # Google Workspace (Calendar & Drive)
    GOOGLE_CLIENT_SECRETS_FILE: str = os.getenv("GOOGLE_CLIENT_SECRETS_FILE", "credentials.json")
    GOOGLE_TOKEN_FILE: str = os.getenv("GOOGLE_TOKEN_FILE", "token.json")

    # Notion
    NOTION_API_KEY: str = os.getenv("NOTION_API_KEY", "")
    NOTION_DEFAULT_PARENT_PAGE_ID: str = os.getenv("NOTION_DEFAULT_PARENT_PAGE_ID", "")

    # Envoi email SMTP
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM_EMAIL: str = os.getenv("SMTP_FROM_EMAIL", "")
    SMTP_USE_TLS: bool = os.getenv("SMTP_USE_TLS", "true").lower() == "true"

    # Base de données & RAG
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./chat.db")
    RAG_DATA_DIR: str = os.getenv("RAG_DATA_DIR", "./data/knowledge")
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "./data/uploads")

    # Serveur
    APP_HOST: str = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT: int = int(os.getenv("APP_PORT", "8000"))
    SECRET_KEY: str = os.getenv("SECRET_KEY", "default-xfinder-secret-key")

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
