"""
Routes d'import de réponses (Lot 5, §6.4).

  - POST /reviews/{id}/import-answers : l'auteur téléverse un .xlsx. Le fichier
    est stocké via le connecteur actif, un `import_job` (queued) est créé, puis le
    traitement est lancé en tâche de fond. Réponse 202 + job_id.
  - GET /import-jobs/{id} : suivi du job (statut + résultat).

En production, le traitement s'exécute dans un worker Celery (cf. import_runner).
Ici, on l'exécute via BackgroundTasks pour conserver le contrat asynchrone
(202 Accepted + polling) sans dépendance d'infrastructure.
"""
import uuid

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    UploadFile,
    File,
    BackgroundTasks,
    status,
)
from sqlalchemy.orm import Session

from app.core.database import get_db, SessionLocal
from app.core.rate_limit import rate_limit
from app.auth.deps import get_current_user
from app.models.user import User
from app.models.enums import UserRole
from app.models.review import Review
from app.models.integration import ImportJob
from app.schemas.integration import ImportJobOut
from app.services import integrations as integ
from app.services.storage.providers import make_object_key
from app.services.import_runner import run_import_job

_XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


# ==========================================================================
# Import sous /reviews/{id}/import-answers
# ==========================================================================
review_import_router = APIRouter(prefix="/reviews", tags=["import intelligent"])


def _process_job_in_background(job_id: uuid.UUID) -> None:
    """Exécute le job dans sa propre session (hors requête HTTP)."""
    db = SessionLocal()
    try:
        job = db.get(ImportJob, job_id)
        if job is None:
            return
        run_import_job(db, job)
        db.commit()
    finally:
        db.close()


@review_import_router.post(
    "/{review_id}/import-answers",
    response_model=ImportJobOut,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(rate_limit(10, 60))],
)
async def import_answers(
    review_id: uuid.UUID,
    background: BackgroundTasks,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Téléverse un fichier de réponses et lance le pré-remplissage asynchrone."""
    review = db.get(Review, review_id)
    if review is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Revue introuvable.")
    if review.author_id != user.id and user.role != UserRole.admin:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Seul l'auteur peut importer des réponses."
        )

    content = await file.read()
    if not content:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Fichier vide.")

    # Stocke le fichier via le connecteur actif (référence opaque).
    storage = integ.get_active_storage_provider(db)
    key = make_object_key(prefix=f"imports/{review_id}", filename=file.filename or "import.xlsx")
    file_ref = storage.put(key, content, file.content_type or _XLSX_MIME)

    job = ImportJob(
        review_id=review.id,
        source="upload",
        file_ref=file_ref,
        status="queued",
        created_by=user.id,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # Lance le traitement en tâche de fond (Celery en prod).
    background.add_task(_process_job_in_background, job.id)
    return job


# ==========================================================================
# Suivi de job sous /import-jobs/{id}
# ==========================================================================
import_jobs_router = APIRouter(prefix="/import-jobs", tags=["import intelligent"])


@import_jobs_router.get("/{job_id}", response_model=ImportJobOut)
def get_import_job(
    job_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Suivi d'un job d'import (statut + résultat)."""
    job = db.get(ImportJob, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job introuvable.")
    # Accès : créateur du job, auteur de la revue, ou admin.
    if job.created_by != user.id and user.role != UserRole.admin:
        review = db.get(Review, job.review_id) if job.review_id else None
        if review is None or review.author_id != user.id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Accès non autorisé.")
    return job
