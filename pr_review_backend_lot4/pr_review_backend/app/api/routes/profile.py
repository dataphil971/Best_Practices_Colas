"""Routes de gestion du profil de l'utilisateur courant."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import hash_password, verify_password
from app.auth.deps import get_current_user
from app.models.user import User
from app.schemas.user import UserOut, ProfileUpdate, PasswordChange

router = APIRouter(tags=["profil"])


@router.get("/me", response_model=UserOut)
def read_me(user: User = Depends(get_current_user)):
    return user


@router.patch("/me", response_model=UserOut)
def update_me(
    payload: ProfileUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.display_name is not None:
        user.display_name = payload.display_name
    if payload.email is not None and payload.email.lower() != user.email:
        exists = db.query(User).filter(User.email == payload.email.lower()).first()
        if exists:
            raise HTTPException(status.HTTP_409_CONFLICT, "E-mail déjà utilisé.")
        user.email = payload.email.lower()
        user.email_verified = False   # re-vérification requise si e-mail modifié
    db.commit()
    db.refresh(user)
    return user


@router.post("/me/password")
def change_password(
    payload: PasswordChange,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Uniquement pour les comptes locaux (les comptes Entra n'ont pas de mot de passe).
    if not user.password_hash:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Compte géré par Entra ID : mot de passe non applicable.",
        )
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Mot de passe actuel incorrect.")
    user.password_hash = hash_password(payload.new_password)
    db.commit()
    return {"detail": "Mot de passe mis à jour."}
