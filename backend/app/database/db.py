import os
from sqlalchemy import Text, create_engine, inspect
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
    connect_args.update({
        "prepare_threshold": None,  # Obligatoire avec PgBouncer Neon (-pooler)
        "keepalives": 1,             # Active le TCP keepalive
        "keepalives_idle": 30,       # Premier ping après 30s d'inactivité
        "keepalives_interval": 10,   # Ping toutes les 10s
        "keepalives_count": 5,       # Déclare la connexion morte après 5 échecs
        "connect_timeout": 15,       # Laisse le temps à Neon de se réveiller
    })

engine_kwargs = {
    "connect_args": connect_args,
    "pool_pre_ping": True,
    "pool_recycle": 120,        # Recycle les connexions toutes les 2 min (avant la mise en veille Neon de 5 min)
}

if database_url.startswith("postgresql+psycopg://"):
    engine_kwargs.update({
        "pool_size": 5,
        "max_overflow": 10,
        "pool_timeout": 30,
    })

engine = create_engine(
    database_url,
    **engine_kwargs,
)

# Sessionmaker pour la gestion des transactions
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Initialisation des tables de la base de données
def init_db():
    Base.metadata.create_all(bind=engine)
    if engine.dialect.name == "postgresql":
        message_columns = inspect(engine).get_columns("messages")
        tool_call_id = next(
            column for column in message_columns if column["name"] == "tool_call_id"
        )
        if not isinstance(tool_call_id["type"], Text):
            with engine.begin() as connection:
                connection.exec_driver_sql(
                    "ALTER TABLE messages ALTER COLUMN tool_call_id TYPE TEXT"
                )
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
