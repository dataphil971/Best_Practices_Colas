"""
Routes d'authentification.

Nominal : Microsoft Entra ID (SSO OIDC).
Repli   : email + mot de passe (si ENABLE_LOCAL_AUTH), pour comptes de service/tests.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.rate_limit import rate_limit
from app.core.security import (
    create_access_token, create_refresh_token, decode_token,
    hash_password, verify_password,
)
from app.auth import entra
from app.models.user import User
from app.models.enums import UserRole
from app.schemas.user import TokenPair, LocalRegister, LocalLogin, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])

# Cache mémoire minimal des états OIDC en cours (à remplacer par Redis en prod).
_pending_states: dict[str, str] = {}   # state -> nonce

# Le cookie n'est envoyé qu'aux routes d'auth. Dérivé du préfixe configuré :
# codé en dur, un changement d'API_V1_PREFIX rendrait le cookie inatteignable
# et casserait silencieusement le renouvellement de session.
_REFRESH_COOKIE_PATH = f"{settings.API_V1_PREFIX}/auth"


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key="refresh_token",
        value=token,
        httponly=True,
        secure=settings.ENVIRONMENT == "production",
        samesite="strict",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path=_REFRESH_COOKIE_PATH,
    )


# --- Entra ID (OIDC) --------------------------------------------------------
@router.get("/login")
async def login():
    """Démarre le flux OIDC : redirige l'utilisateur vers Microsoft Entra ID."""
    if not settings.entra_configured:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "Entra ID non configuré.")
    state = entra.new_state()
    nonce = entra.new_state()
    _pending_states[state] = nonce
    return RedirectResponse(entra.build_authorization_url(state, nonce))


@router.get("/callback", response_model=TokenPair)
async def callback(code: str, state: str, response: Response, db: Session = Depends(get_db)):
    """Callback OIDC : valide, provisionne le compte, émet les jetons applicatifs."""
    if state not in _pending_states:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "État OIDC inconnu ou expiré.")
    _pending_states.pop(state, None)

    try:
        claims = await entra.exchange_code_for_claims(code)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Échec OIDC : {exc}") from exc

    user = entra.provision_user(db, claims)
    access = create_access_token(str(user.id), user.role.value)
    refresh = create_refresh_token(str(user.id), user.role.value)
    _set_refresh_cookie(response, refresh)
    return TokenPair(access_token=access)


# --- Repli local ------------------------------------------------------------
@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(rate_limit(5, 60))])
def register_local(payload: LocalRegister, db: Session = Depends(get_db)):
    if not settings.ENABLE_LOCAL_AUTH:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Inscription locale désactivée.")
    if db.query(User).filter(User.email == payload.email.lower()).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "E-mail déjà utilisé.")
    user = User(
        email=payload.email.lower(),
        display_name=payload.display_name,
        password_hash=hash_password(payload.password),
        role=UserRole.user,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login/local", response_model=TokenPair,
             dependencies=[Depends(rate_limit(10, 60))])
def login_local(payload: LocalLogin, response: Response, db: Session = Depends(get_db)):
    if not settings.ENABLE_LOCAL_AUTH:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Connexion locale désactivée.")
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if not user or not user.password_hash or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Identifiants invalides.")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Compte désactivé.")
    access = create_access_token(str(user.id), user.role.value)
    refresh = create_refresh_token(str(user.id), user.role.value)
    _set_refresh_cookie(response, refresh)
    return TokenPair(access_token=access)


# --- Commun -----------------------------------------------------------------
@router.post("/refresh", response_model=TokenPair)
def refresh_token(request: Request, response: Response, db: Session = Depends(get_db)):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token manquant.")
    payload = decode_token(token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token invalide.")
    try:
        user = db.get(User, uuid.UUID(payload["sub"]))
    except (KeyError, ValueError) as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Refresh token malformé."
        ) from exc
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Compte introuvable.")

    # Rotation du refresh token à chaque renouvellement.
    new_refresh = create_refresh_token(str(user.id), user.role.value)
    _set_refresh_cookie(response, new_refresh)
    return TokenPair(access_token=create_access_token(str(user.id), user.role.value))


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("refresh_token", path=_REFRESH_COOKIE_PATH)
    return {"detail": "Déconnecté."}
