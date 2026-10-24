import os
from sqlalchemy import create_engine, inspect
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

connect_args = {"check_same_thread": False} if database_url.startswith("sqlite:") else {}
if database_url.startswith("postgresql+psycopg://"):
    connect_args["prepare_threshold"] = None

engine = create_engine(
    database_url,
    connect_args=connect_args,
)

# Sessionmaker pour la gestion des transactions
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Initialisation des tables de la base de données
def init_db():
    Base.metadata.create_all(bind=engine)
    columns = {column["name"] for column in inspect(engine).get_columns("conversations")}
    if "user_id" not in columns:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "ALTER TABLE conversations ADD COLUMN user_id INTEGER REFERENCES users(id)"
            )
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_conversations_user_id ON conversations (user_id)"
        )

# Dépendance FastAPI pour injecter la session de base de données
def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
