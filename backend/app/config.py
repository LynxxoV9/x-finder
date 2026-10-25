import os
from pathlib import Path
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Recherche explicite du fichier .env dans le dossier backend ou à la racine
ENV_BACKEND = Path(__file__).resolve().parent.parent / ".env"
ENV_ROOT = Path(__file__).resolve().parent.parent.parent / ".env"

if ENV_ROOT.exists():
    load_dotenv(ENV_ROOT)
if ENV_BACKEND.exists():
    load_dotenv(ENV_BACKEND, override=False)
if not ENV_ROOT.exists() and not ENV_BACKEND.exists():
    load_dotenv()

class Settings(BaseSettings):
    # Fournisseur LLM RodiumAI
    RODIUMAI_API_KEY: str = os.getenv("RODIUMAI_API_KEY", "")
    BASE_URL: str = os.getenv("BASE_URL", "https://api.rodiumai.io/v1").rstrip("/")
    ALLOWED_MODELS: str = os.getenv(
        "ALLOWED_MODELS",
        "google/gemini-3.8-flash,anthropic/claude-sonnet-4-5-20250929,google/gemini-3.5-flash",
    )
    DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", "google/gemini-3.8-flash")

    # Moteur de recherche web
    TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")

    # Météo (OpenWeatherMap et WeatherAPI)
    WEATHER_API_KEY: str = os.getenv("WEATHER_API_KEY", "")
    OPENWEATHER_API_KEY: str = os.getenv("OPENWEATHER_API_KEY", os.getenv("WEATHER_API_KEY", ""))

    # Google Workspace (Calendar & Drive)
    GOOGLE_CLIENT_SECRETS_FILE: str = os.getenv("GOOGLE_CLIENT_SECRETS_FILE", "credentials.json")
    GOOGLE_TOKEN_FILE: str = os.getenv("GOOGLE_TOKEN_FILE", "token.json")

    # Notion
    NOTION_API_KEY: str = os.getenv("NOTION_API_KEY", "")
    NOTION_DEFAULT_PARENT_PAGE_ID: str = os.getenv("NOTION_DEFAULT_PARENT_PAGE_ID", "")

    # Envoi email SMTP
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp-relay.brevo.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "bfe9be001@smtp-brevo.com")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM_EMAIL: str = os.getenv("SMTP_FROM_EMAIL", os.getenv("EMAIL_SENDER", ""))
    SMTP_USE_TLS: bool = os.getenv("SMTP_USE_TLS", "true").lower() == "true"

    # Base de données & RAG
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./chat.db")
    RAG_DATA_DIR: str = os.getenv("RAG_DATA_DIR", "./data/knowledge")
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "./data/uploads")

    # Serveur
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development").lower()
    FRONTEND_ORIGIN: str = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173").rstrip("/")
    PUBLIC_BASE_URL: str = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
    SESSION_COOKIE_NAME: str = os.getenv("SESSION_COOKIE_NAME", "xfinder_session")
    SESSION_TTL_HOURS: int = int(os.getenv("SESSION_TTL_HOURS", "720"))
    APP_HOST: str = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT: int = int(os.getenv("APP_PORT", "8000"))
    SECRET_KEY: str = os.getenv("SECRET_KEY", "development-only-change-me")

    # Connexion OAuth
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    GITHUB_CLIENT_ID: str = os.getenv("GITHUB_CLIENT_ID", "")
    GITHUB_CLIENT_SECRET: str = os.getenv("GITHUB_CLIENT_SECRET", "")

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()

if settings.ENVIRONMENT == "production" and (
    settings.SECRET_KEY == "development-only-change-me"
    or len(settings.SECRET_KEY) < 32
):
    raise RuntimeError("SECRET_KEY doit contenir au moins 32 caractères aléatoires en production.")
if settings.SESSION_TTL_HOURS < 1:
    raise RuntimeError("SESSION_TTL_HOURS doit être supérieur ou égal à 1.")
