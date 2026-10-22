import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.config import settings
from app.database.models import Base

database_url = settings.DATABASE_URL
if database_url.startswith("postgres://"):
    database_url = "postgresql+psycopg://" + database_url.removeprefix("postgres://")
elif database_url.startswith("postgresql://"):
    database_url = "postgresql+psycopg://" + database_url.removeprefix("postgresql://")

if os.getenv("VERCEL") and database_url.startswith("sqlite:"):
    raise RuntimeError(
        "Vercel requires a persistent PostgreSQL database. Set DATABASE_URL in the project environment."
    )

engine = create_engine(
    database_url,
    connect_args={"check_same_thread": False} if database_url.startswith("sqlite:") else {}
)

# Sessionmaker pour la gestion des transactions
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Initialisation des tables de la base de données
def init_db():
    Base.metadata.create_all(bind=engine)

# Dépendance FastAPI pour injecter la session de base de données
def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
