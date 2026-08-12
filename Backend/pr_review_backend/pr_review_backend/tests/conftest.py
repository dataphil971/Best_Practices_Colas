"""
Fixtures de test pour la couche référentiel (Lot 2).

Le schéma de production cible PostgreSQL (types UUID/JSONB, index partiels). Pour
tester la LOGIQUE métier (versionnement immuable, journal, transitions de cycle
de vie) sans dépendre d'un PostgreSQL réel, on monte une base SQLite en mémoire
et on neutralise les spécificités PG au niveau des types de colonnes :

  * UUID  -> CHAR(36) (SQLAlchemy sait convertir avec as_uuid via un TypeDecorator) ;
  * JSONB -> JSON générique.

On ne teste PAS ici les index partiels PG (`uniq_current_version`) : l'invariant
« une seule version courante » est garanti par le service ET par l'index en prod.
"""
import uuid

import pytest
from sqlalchemy import create_engine, types
from sqlalchemy.dialects.sqlite import insert  # noqa: F401  (présence du dialecte)
from sqlalchemy.orm import sessionmaker

# --- Neutralisation des types PG pour SQLite -------------------------------
# On patche AVANT d'importer les modèles pour que leurs colonnes utilisent des
# types compatibles SQLite.
import sqlalchemy.dialects.postgresql as pg


class _UUIDString(types.TypeDecorator):
    """UUID stocké en texte, exposé comme uuid.UUID côté Python."""
    impl = types.String(36)
    cache_ok = True

    def __init__(self, *args, as_uuid=True, **kwargs):
        super().__init__()

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return uuid.UUID(value) if not isinstance(value, uuid.UUID) else value


# Rediriger UUID et JSONB vers des équivalents SQLite avant import des modèles.
pg.UUID = _UUIDString
pg.JSONB = types.JSON
pg.INET = types.String  # INET → texte en SQLite

# En SQLite, seule une colonne INTEGER PRIMARY KEY s'auto-incrémente (alias ROWID).
# On compile donc BIGINT en INTEGER pour ce dialecte (en prod : Identity Postgres).
from sqlalchemy.ext.compiler import compiles as _compiles  # noqa: E402
from sqlalchemy import BigInteger as _BigInteger  # noqa: E402


@_compiles(_BigInteger, "sqlite")
def _bigint_as_integer(element, compiler, **kw):  # noqa: ANN001
    return "INTEGER"

from app.core.database import Base  # noqa: E402
from app.models import user, category, rule, rule_activity, review, share, integration, audit  # noqa: E402,F401
from app.models.user import User  # noqa: E402
from app.models.enums import UserRole  # noqa: E402


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = TestSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


@pytest.fixture()
def admin(db):
    u = User(
        email="admin@test.local",
        display_name="Admin Test",
        role=UserRole.admin,
        is_active=True,
        email_verified=True,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@pytest.fixture()
def contributor(db):
    u = User(
        email="user@test.local",
        display_name="Utilisateur Test",
        role=UserRole.user,
        is_active=True,
        email_verified=True,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@pytest.fixture()
def reviewer(db):
    u = User(
        email="reviewer@test.local",
        display_name="Reviewer Test",
        role=UserRole.reviewer,
        is_active=True,
        email_verified=True,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u
