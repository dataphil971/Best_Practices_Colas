"""
Purge de rétention (Lot 7, §9).

Les fichiers Excel importés et leurs `import_jobs` sont purgés après
`retention_days` jours (défaut 30, réglable par l'admin). En production, une tâche
Celery beat quotidienne appelle `run_retention_purge`.

Principes :
  - la suppression du fichier passe par `StorageProvider.delete()` via l'interface
    — indépendante du backend actif (interne / Azure / S3) ;
  - un ancien `file_ref` peut viser un backend différent de l'actif ; on résout
    donc le backend d'après le PRÉFIXE de la référence (internal:// / azure:// /
    s3://), pas seulement le fournisseur courant ;
  - les REVUES et leur contenu ne sont JAMAIS purgés — seule la matière première
    d'import l'est ;
  - la purge est tracée dans l'audit.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.integration import ImportJob
from app.services import integrations as integ
from app.services import audit
from app.services.settings import get_retention_days
from app.services.storage.providers import (
    InternalStorageProvider,
    AzureBlobStorageProvider,
    S3StorageProvider,
)


def _provider_for_ref(db: Session, ref: str):
    """
    Choisit le backend capable de résoudre une référence, d'après son préfixe.

    Permet de purger d'anciens fichiers même après un changement de backend actif.
    Pour les backends cloud, on s'appuie sur la config active correspondante si
    disponible ; sinon on tente un provider minimal.
    """
    clean = ref.split("#sp=")[0] if ref else ref
    if clean.startswith("internal://"):
        # Reconstruit le provider interne avec son base_path configuré.
        active = integ.get_active_storage_provider(db)
        return active if isinstance(active, InternalStorageProvider) else InternalStorageProvider()
    # Pour azure:// et s3://, on réutilise le fournisseur actif s'il correspond.
    active = integ.get_active_storage_provider(db)
    if clean.startswith("azure://") and isinstance(active, AzureBlobStorageProvider):
        return active
    if clean.startswith("s3://") and isinstance(active, S3StorageProvider):
        return active
    return active  # meilleur effort


def run_retention_purge(db: Session, *, now: datetime | None = None) -> dict:
    """
    Purge les import_jobs plus vieux que la fenêtre de rétention et leurs fichiers.

    Retourne {retention_days, cutoff, purged_files, purged_jobs, errors}.
    """
    now = now or datetime.now(timezone.utc)
    days = get_retention_days(db)
    cutoff = now - timedelta(days=days)

    jobs = db.scalars(
        select(ImportJob).where(ImportJob.created_at < cutoff)
    ).all()

    purged_files = 0
    errors = 0
    for job in jobs:
        if job.file_ref:
            try:
                provider = _provider_for_ref(db, job.file_ref)
                clean = job.file_ref.split("#sp=")[0]
                provider.delete(clean)
                purged_files += 1
            except Exception:  # noqa: BLE001
                errors += 1
        db.delete(job)

    db.flush()

    audit.record(
        db,
        action="retention.purge",
        entity="import_jobs",
        metadata={
            "retention_days": days,
            "cutoff": cutoff.isoformat(),
            "purged_jobs": len(jobs),
            "purged_files": purged_files,
            "errors": errors,
        },
    )

    return {
        "retention_days": days,
        "cutoff": cutoff.isoformat(),
        "purged_files": purged_files,
        "purged_jobs": len(jobs),
        "errors": errors,
    }
