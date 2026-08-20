"""
Route d'import des résultats Agent BI (Lot 8).

  POST /reviews/{review_id}/agent-results

Reçoit l'enveloppe JSON produite par `Agent_BI/03_PYTHON/main.py` (via le
pont local `Agent_BI/05_NODE`) et l'applique à une revue existante.

Traitement synchrone (contrairement à /import-answers) : pas de fournisseur
externe à attendre, le rapprochement règle <-> item est déterministe via
`rules.code`. Voir app/services/agent_results.py pour les invariants
(conflit humain, idempotence par empreinte de projet).
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rate_limit import rate_limit
from app.auth.deps import get_current_user
from app.models.user import User
from app.models.enums import UserRole
from app.models.review import Review
from app.schemas.agent_results import AgentEnvelopeIn, AgentImportResultOut
from app.services.agent_results import apply_agent_envelope

router = APIRouter(prefix="/reviews", tags=["agent bi"])


@router.post(
    "/{review_id}/agent-results",
    response_model=AgentImportResultOut,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(rate_limit(10, 60))],
)
def import_agent_results(
    review_id: uuid.UUID,
    envelope: AgentEnvelopeIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    review = db.get(Review, review_id)
    if review is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Revue introuvable.")
    if review.author_id != user.id and user.role != UserRole.admin:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Seul l'auteur peut importer des résultats Agent BI.",
        )

    try:
        result = apply_agent_envelope(db, review=review, envelope=envelope)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    db.commit()
    return result
