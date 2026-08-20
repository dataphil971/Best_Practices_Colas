"""
Exécution d'un job d'import de réponses (Lot 5, §6.4).

Orchestration (idéalement dans un worker Celery ; ici exécutable en synchrone
pour les tests et le mode dégradé) :

  1. Récupère le fichier depuis le stockage actif.
  2. Le parse de façon robuste (colonne texte + statut).
  3. Construit le référentiel de la revue (versions figées des items).
  4. Associe chaque ligne importée à un item via le provider de matching actif.
  5. Détecte le statut de chaque ligne.
  6. APPLIQUE les statuts au-dessus du seuil ; marque les cas AMBIGUS pour
     confirmation par l'utilisateur (jamais appliqués silencieusement).
  7. Écrit le résultat dans `import_jobs.result` et recalcule le score.

Le résultat renvoyé : {filled, ambiguous, matched, total, details[]}.
"""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.review import Review, ReviewItem
from app.models.rule import RuleVersion
from app.models.integration import ImportJob
from app.services.excel_parser import parse_workbook
from app.services.matching.base import RuleRef
from app.services.matching.local import AMBIGUOUS_MIN, PREFILL_STRONG, PREFILL_MARGIN_MIN
from app.services import integrations as integ
from app.services.review import recompute_and_cache_score


def run_import_job(db: Session, job: ImportJob) -> ImportJob:
    """Exécute le job d'import de bout en bout et met à jour son statut."""
    job.status = "running"
    db.flush()

    try:
        review = db.get(Review, job.review_id) if job.review_id else None
        if review is None:
            raise ValueError("Revue associée introuvable.")

        storage = integ.get_active_storage_provider(db)
        matcher = integ.get_active_match_provider(db)

        # 1-2. Récupération + parsing robuste.
        # Un import SharePoint marque le file_ref d'un suffixe de déduplication
        # (#sp=<id>@<date>) : on le retire pour résoudre la vraie référence.
        real_ref = job.file_ref.split("#sp=")[0] if job.file_ref else job.file_ref
        raw = storage.get(real_ref)
        parsed_rows = parse_workbook(raw, status_detector=matcher.detect_status)

        # 3. Référentiel de la revue : items + leur version figée.
        item_rows = db.execute(
            select(ReviewItem, RuleVersion)
            .join(RuleVersion, RuleVersion.id == ReviewItem.rule_version_id)
            .where(ReviewItem.review_id == review.id)
        ).all()
        referential = [
            RuleRef(rule_version_id=str(rv.id), text=rv.text) for _it, rv in item_rows
        ]
        item_by_version = {str(rv.id): it for it, rv in item_rows}

        imported_texts = [row.text for row in parsed_rows]

        # 4. Matching.
        matches = matcher.match_rules(imported_texts, referential) if imported_texts else []

        filled = ambiguous = matched = 0
        details = []

        for m in matches:
            row = parsed_rows[m.imported_index]
            detected = matcher.detect_status(row.status_raw) if row.status_raw else None

            record = {
                "imported_index": m.imported_index,
                "imported_text": row.text[:200],
                "rule_version_id": m.rule_version_id,
                "confidence": m.confidence,
                "verdict": m.verdict,
                "detected_status": detected.value if detected else None,
                "applied": False,
                "ambiguous": False,
            }

            if m.rule_version_id:
                matched += 1

            # 6. Application vs ambiguïté.
            strong = m.confidence >= PREFILL_STRONG
            probable_enough = m.confidence >= PREFILL_MARGIN_MIN and m.verdict != "new"
            if m.rule_version_id and detected and (strong or probable_enough):
                item = item_by_version.get(m.rule_version_id)
                if item is not None:
                    item.status = detected
                    item.last_update = datetime.now(timezone.utc)
                    filled += 1
                    record["applied"] = True
            elif m.rule_version_id and m.confidence >= AMBIGUOUS_MIN:
                ambiguous += 1
                record["ambiguous"] = True

            details.append(record)

        db.flush()

        # 7. Recalcule le score et clôt le job.
        recompute_and_cache_score(db, review)
        job.result = {
            "filled": filled,
            "ambiguous": ambiguous,
            "matched": matched,
            "total": len(parsed_rows),
            "details": details,
        }
        job.status = "done"
        job.finished_at = datetime.now(timezone.utc)
        db.flush()
        return job

    except Exception as exc:  # noqa: BLE001
        job.status = "failed"
        job.error = str(exc)[:2000]
        job.finished_at = datetime.now(timezone.utc)
        db.flush()
        return job
