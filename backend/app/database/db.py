from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.config import settings
from app.database.models import Base

# Configuration du moteur SQLite ou distant
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
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
