"""
Dépendances FastAPI pour l'authentification et le contrôle d'accès (RBAC).

Principe clé : le rôle n'est JAMAIS décidé par le client. Il est lu depuis le
jeton applicatif signé, puis re-vérifié en base. Chaque endpoint protégé déclare
le rôle minimum requis via `require_role(...)`.
"""
import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token
from app.models.user import User
from app.models.enums import UserRole

_bearer = HTTPBearer(auto_error=False)

# Hiérarchie des rôles : un rôle supérieur satisfait l'exigence d'un rôle inférieur.
_ROLE_LEVEL = {UserRole.user: 0, UserRole.reviewer: 1, UserRole.admin: 2}


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Jeton manquant")

    payload = decode_token(creds.credentials)
    if not payload or payload.get("type") != "access":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Jeton invalide")

    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Jeton malformé")

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Compte introuvable ou désactivé")
    return user


def require_role(minimum: UserRole):
    """Fabrique une dépendance exigeant AU MOINS le rôle donné."""
    def _checker(user: User = Depends(get_current_user)) -> User:
        if _ROLE_LEVEL[user.role] < _ROLE_LEVEL[minimum]:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"Rôle insuffisant : '{minimum.value}' requis.",
            )
        return user
    return _checker


# Raccourcis prêts à l'emploi
require_user = require_role(UserRole.user)
require_reviewer = require_role(UserRole.reviewer)
require_admin = require_role(UserRole.admin)
