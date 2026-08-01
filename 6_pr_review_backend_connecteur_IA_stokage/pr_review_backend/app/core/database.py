"""
Connexion à la base de données et gestion des sessions SQLAlchemy 2.x.
"""
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session

from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,   # évite les connexions mortes
    echo=False,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    """Classe de base pour tous les modèles ORM."""
    pass


def get_db() -> Generator[Session, None, None]:
    """Dépendance FastAPI : fournit une session par requête, fermée à la fin."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
