"""
Sécurité : hachage de mot de passe (Argon2id) et jetons JWT applicatifs.

Note : l'authentification nominale est Entra ID (OIDC). Le hachage de mot de
passe ne sert qu'au repli local (comptes de service / tests). Les jetons JWT
émis ici sont les jetons *applicatifs*, distincts des jetons Entra.
"""
from datetime import datetime, timedelta, timezone
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from jose import jwt, JWTError

from app.core.config import settings

_ph = PasswordHasher()  # paramètres Argon2id par défaut (sûrs)


# --- Mots de passe (repli local) -------------------------------------------
def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    # VerificationError couvre VerifyMismatchError ; InvalidHashError se produit
    # quand le hachage stocké n'est pas un hachage Argon2 lisible (compte migré
    # depuis un autre système, valeur tronquée en base). Dans les deux cas c'est
    # un échec d'authentification — jamais une erreur 500.
    try:
        return _ph.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


# --- Jetons JWT applicatifs -------------------------------------------------
def _create_token(subject: str, role: str, expires: timedelta, token_type: str) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,          # user id
        "role": role,
        "type": token_type,      # "access" | "refresh"
        "iat": now,
        "exp": now + expires,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_access_token(user_id: str, role: str) -> str:
    return _create_token(
        user_id, role,
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        "access",
    )


def create_refresh_token(user_id: str, role: str) -> str:
    return _create_token(
        user_id, role,
        timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        "refresh",
    )


def decode_token(token: str) -> dict[str, Any] | None:
    """Retourne le payload si valide, None sinon."""
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None
