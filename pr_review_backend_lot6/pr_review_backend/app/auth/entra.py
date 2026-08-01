"""
Intégration Microsoft Entra ID via OpenID Connect (authorization code + PKCE).

Flux :
  1. GET /auth/login    -> redirige vers Entra (page de connexion Microsoft)
  2. GET /auth/callback -> Entra renvoie un 'code' ; on l'échange contre les
     jetons Entra, on valide l'ID token, puis on provisionne / rapproche le
     compte applicatif et on émet NOS jetons applicatifs.

Le rôle applicatif n'est pas dérivé aveuglément d'Entra : au premier login, un
nouvel utilisateur reçoit le rôle 'user'. Le mapping optionnel groupe->rôle est
appliqué si configuré (voir services.role_mapping).
"""
import secrets

import httpx
from authlib.jose import jwt as jose_jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user import User
from app.models.enums import UserRole
from app.services.role_mapping import resolve_role_from_groups


class EntraError(Exception):
    pass


async def _discover() -> dict:
    """Récupère la configuration OIDC d'Entra (endpoints, clés)."""
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(settings.entra_discovery_url)
        r.raise_for_status()
        return r.json()


def build_authorization_url(state: str, nonce: str) -> str:
    """Construit l'URL de redirection vers la page de connexion Microsoft."""
    if not settings.entra_configured:
        raise EntraError("Entra ID non configuré (ENTRA_TENANT_ID / ENTRA_CLIENT_ID).")
    base = (
        f"https://login.microsoftonline.com/{settings.ENTRA_TENANT_ID}"
        "/oauth2/v2.0/authorize"
    )
    params = {
        "client_id": settings.ENTRA_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": settings.ENTRA_REDIRECT_URI,
        "response_mode": "query",
        "scope": "openid profile email",
        "state": state,
        "nonce": nonce,
    }
    query = "&".join(f"{k}={httpx.QueryParams({k: v})[k]}" for k, v in params.items())
    return f"{base}?{query}"


async def exchange_code_for_claims(code: str) -> dict:
    """Échange le code d'autorisation contre les claims de l'utilisateur."""
    conf = await _discover()
    token_endpoint = conf["token_endpoint"]
    jwks_uri = conf["jwks_uri"]

    async with httpx.AsyncClient(timeout=10) as client:
        token_resp = await client.post(
            token_endpoint,
            data={
                "client_id": settings.ENTRA_CLIENT_ID,
                "client_secret": settings.ENTRA_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": settings.ENTRA_REDIRECT_URI,
            },
        )
        token_resp.raise_for_status()
        tokens = token_resp.json()
        id_token = tokens.get("id_token")
        if not id_token:
            raise EntraError("Aucun id_token renvoyé par Entra.")

        jwks_resp = await client.get(jwks_uri)
        jwks_resp.raise_for_status()
        jwks = jwks_resp.json()

    # Valide la signature de l'ID token et retourne les claims.
    claims = jose_jwt.decode(id_token, jwks)
    claims.validate()
    return dict(claims)


def provision_user(db: Session, claims: dict) -> User:
    """
    Crée ou met à jour le compte applicatif à partir des claims Entra.
    Rapprochement par 'oid' (identifiant stable d'objet Entra), sinon par email.
    """
    oid = claims.get("oid")
    email = (claims.get("email") or claims.get("preferred_username") or "").lower()
    name = claims.get("name") or email.split("@")[0]
    groups = claims.get("groups", []) or []

    user: User | None = None
    if oid:
        user = db.query(User).filter(User.entra_oid == oid).first()
    if user is None and email:
        user = db.query(User).filter(User.email == email).first()

    if user is None:
        # Premier login : provisioning JIT. Rôle par défaut 'user', sauf mapping.
        role = resolve_role_from_groups(groups) or UserRole.user
        user = User(
            email=email,
            display_name=name,
            role=role,
            entra_oid=oid,
            email_verified=True,     # l'e-mail est vérifié par Entra
            password_hash=None,
        )
        db.add(user)
    else:
        # Rapprochement : on complète l'oid si absent et on rafraîchit le nom.
        if oid and not user.entra_oid:
            user.entra_oid = oid
        user.display_name = name or user.display_name
        user.email_verified = True

    db.commit()
    db.refresh(user)
    return user


def new_state() -> str:
    return secrets.token_urlsafe(24)
