"""
Service des paramètres applicatifs (Lot 7).

Gère les entrées de `app_settings`, notamment :
  - `retention_days` : durée de rétention des fichiers importés (défaut 30) ;
  - `role_mapping`   : correspondance groupes Entra ID → rôles applicatifs
    (ex. {"BI-Reviewers": "reviewer"}). Le rôle n'est jamais dérivé aveuglément
    d'Entra : ce mapping, défini par l'admin, est la seule passerelle, et il est
    audité.
"""
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit import AppSetting

RETENTION_KEY = "retention_days"
ROLE_MAPPING_KEY = "role_mapping"
DEFAULT_RETENTION_DAYS = 30


def get_setting(db: Session, key: str, default: Any = None) -> Any:
    row = db.get(AppSetting, key)
    return row.value if row is not None else default


def set_setting(
    db: Session, *, key: str, value: Any, updated_by: uuid.UUID | None = None
) -> AppSetting:
    row = db.get(AppSetting, key)
    if row is None:
        row = AppSetting(key=key, value=value, updated_by=updated_by)
        db.add(row)
    else:
        row.value = value
        row.updated_by = updated_by
    db.flush()
    return row


def get_retention_days(db: Session) -> int:
    value = get_setting(db, RETENTION_KEY, DEFAULT_RETENTION_DAYS)
    try:
        return int(value)
    except (TypeError, ValueError):
        return DEFAULT_RETENTION_DAYS


def set_retention_days(db: Session, *, days: int, updated_by: uuid.UUID | None = None) -> int:
    if days < 1:
        raise ValueError("La rétention doit être d'au moins 1 jour.")
    set_setting(db, key=RETENTION_KEY, value=days, updated_by=updated_by)
    return days


def get_role_mapping(db: Session) -> dict[str, str]:
    return get_setting(db, ROLE_MAPPING_KEY, {}) or {}


def set_role_mapping(
    db: Session, *, mapping: dict[str, str], updated_by: uuid.UUID | None = None
) -> dict[str, str]:
    # Ne conserve que des rôles valides.
    from app.models.enums import UserRole

    valid = {r.value for r in UserRole}
    cleaned = {str(g): role for g, role in mapping.items() if role in valid}
    set_setting(db, key=ROLE_MAPPING_KEY, value=cleaned, updated_by=updated_by)
    return cleaned
