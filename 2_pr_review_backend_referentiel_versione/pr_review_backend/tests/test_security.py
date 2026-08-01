"""
Tests unitaires de la couche sécurité (sans base de données).
Lancer avec : pytest
"""
from app.core.security import (
    hash_password, verify_password, create_access_token, decode_token,
)
from app.services.role_mapping import resolve_role_from_groups
from app.core.config import settings
from app.models.enums import UserRole


def test_password_hash_and_verify():
    h = hash_password("SuperSecret123!")
    assert h.startswith("$argon2")
    assert verify_password("SuperSecret123!", h) is True
    assert verify_password("mauvais", h) is False


def test_jwt_roundtrip_and_rejection():
    tok = create_access_token("user-123", "admin")
    payload = decode_token(tok)
    assert payload is not None
    assert payload["sub"] == "user-123"
    assert payload["role"] == "admin"
    assert payload["type"] == "access"
    assert decode_token("jeton.invalide.xxx") is None


def test_role_mapping_priority():
    settings.ENTRA_GROUP_ROLE_MAP = {"grp-admins": "admin", "grp-rev": "reviewer"}
    # rôle le plus élevé retenu si plusieurs groupes
    assert resolve_role_from_groups(["grp-rev", "grp-admins"]) == UserRole.admin
    assert resolve_role_from_groups(["grp-rev"]) == UserRole.reviewer
    # aucun groupe mappé -> None (l'appelant retombe sur 'user')
    assert resolve_role_from_groups(["grp-inconnu"]) is None
