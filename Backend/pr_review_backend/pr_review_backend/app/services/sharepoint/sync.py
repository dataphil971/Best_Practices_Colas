"""
Service de synchronisation SharePoint (Lot 6, §7.3).

Flux, déclenché manuellement (endpoint admin) ou par planification (Celery beat) :

    Pour chaque source configurée :
      → liste les fichiers correspondant au motif via Graph
      → pour chaque fichier nouveau/modifié :
          - télécharge le contenu
          - le stocke via le connecteur de stockage actif
          - crée ou met à jour la revue cible (par nom de rapport)
          - pré-remplit les statuts en RÉUTILISANT le moteur d'import (§6)
          - trace un import_job (source='sharepoint')

Le parsing et le matching sont **partagés** avec l'import manuel : un seul moteur,
deux sources d'entrée. On ne réimporte pas un fichier déjà traité à la même date
de modification (déduplication via les `import_jobs` précédents).
"""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import ChecklistType
from app.models.user import User
from app.models.review import Review
from app.models.integration import IntegrationConfig, ImportJob
from app.services import integrations as integ
from app.services.sharepoint.graph_client import GraphClient, RemoteFile
from app.services.import_runner import run_import_job
from app.services.review import create_review


def _get_graph_client(db: Session) -> tuple[GraphClient, dict]:
    """Construit le client Graph depuis la config sharepoint active."""
    cfg = db.scalar(
        select(IntegrationConfig).where(
            IntegrationConfig.kind == "sharepoint",
            IntegrationConfig.is_active.is_(True),
        )
    )
    settings = (cfg.settings if cfg else {}) or {}
    secret = integ._resolve_secret(cfg.secret_ref) if cfg else None
    client = GraphClient(
        tenant_id=settings.get("tenant_id"),
        client_id=settings.get("client_id"),
        client_secret=secret,
    )
    return client, settings


def _already_imported(db: Session, file_ref_tag: str) -> bool:
    """
    Vrai si un import SharePoint pour ce fichier+date a déjà réussi.

    On encode `<remote_id>@<last_modified>` dans le file_ref pour dédupliquer
    sans table supplémentaire.
    """
    existing = db.scalar(
        select(ImportJob.id).where(
            ImportJob.source == "sharepoint",
            ImportJob.status == "done",
            ImportJob.file_ref.like(f"%#sp={file_ref_tag}"),
        )
    )
    return existing is not None


def _find_or_create_review(
    db: Session, *, report_name: str, checklist_type: ChecklistType, actor: User
) -> Review:
    """Retrouve une revue cible par nom + type, ou la crée (snapshot figé)."""
    review = db.scalar(
        select(Review).where(
            Review.report_name == report_name,
            Review.checklist_type == checklist_type,
        )
    )
    if review is None:
        review = create_review(
            db, author=actor, report_name=report_name, checklist_type=checklist_type
        )
        db.flush()
    return review


def sync_sources(db: Session, *, actor: User) -> dict:
    """
    Synchronise toutes les sources configurées. Retourne une synthèse :
    {operational, sources, listed, imported, skipped, jobs[]}.
    """
    client, settings = _get_graph_client(db)
    sources = settings.get("sources", [])

    summary = {
        "operational": client.is_operational(),
        "sources": len(sources),
        "listed": 0,
        "imported": 0,
        "skipped": 0,
        "jobs": [],
    }
    if not client.is_operational() or not sources:
        return summary

    storage = integ.get_active_storage_provider(db)

    for source in sources:
        try:
            target_type = ChecklistType(source.get("target_checklist", "powerbi"))
        except ValueError:
            continue

        remote_files = client.list_files(
            site_url=source.get("site", ""),
            drive=source.get("drive", "Documents"),
            folder=source.get("folder", "/"),
            pattern=source.get("pattern", "*.xlsx"),
        )
        summary["listed"] += len(remote_files)

        for rf in remote_files:
            tag = f"{rf.id}@{rf.last_modified}"
            if _already_imported(db, tag):
                summary["skipped"] += 1
                continue

            # Nom de revue dérivé du fichier (sans extension).
            report_name = rf.name.rsplit(".", 1)[0]
            review = _find_or_create_review(
                db, report_name=report_name, checklist_type=target_type, actor=actor
            )

            content = client.download(rf)
            key = f"sharepoint/{target_type.value}/{rf.id}"
            base_ref = storage.put(key, content, "application/octet-stream")
            # On marque la référence avec le tag de dédup.
            file_ref = f"{base_ref}#sp={tag}"

            job = ImportJob(
                review_id=review.id,
                source="sharepoint",
                file_ref=file_ref,
                status="queued",
                created_by=actor.id,
            )
            db.add(job)
            db.flush()

            run_import_job(db, job)
            summary["imported"] += 1
            summary["jobs"].append(
                {"job_id": str(job.id), "review_id": str(review.id),
                 "file": rf.name, "status": job.status}
            )

    db.flush()
    return summary
