"""
Tests du monitoring et du durcissement (Lot 7).

Couvrent :
  - l'écriture d'audit (immuable côté service) ;
  - les paramètres (rétention, mapping de rôles) ;
  - la purge de rétention (fichiers + import_jobs expirés, revues préservées) ;
  - les agrégats de monitoring (portefeuille, avancement) ;
  - le rate limiter à fenêtre glissante.
"""
import io
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models.category import Category
from app.models.review import Review, ReviewItem
from app.models.integration import ImportJob, IntegrationConfig
from app.models.audit import AuditLog, AppSetting
from app.models.enums import (
    ChecklistType, Criticality, ItemStatus, ProgressState, ReviewStatus,
)
from app.services import referential as ref_svc
from app.services import review as rev_svc
from app.services import audit as audit_svc
from app.services import settings as settings_svc
from app.services import monitoring as mon_svc
from app.services import retention as retention_svc


# --- Audit -----------------------------------------------------------------
def test_audit_record_writes_entry(db, admin):
    entry = audit_svc.record(
        db, action="rule.approve", entity="rule_versions",
        user_id=admin.id, metadata={"k": "v"}, ip="10.0.0.1",
    )
    db.commit()
    assert entry is not None
    rows = db.scalars(select(AuditLog)).all()
    assert len(rows) == 1
    assert rows[0].action == "rule.approve"
    assert rows[0].audit_metadata == {"k": "v"}


# --- Paramètres ------------------------------------------------------------
def test_retention_default_and_update(db, admin):
    # Défaut si absent.
    assert settings_svc.get_retention_days(db) == 30
    settings_svc.set_retention_days(db, days=45, updated_by=admin.id)
    db.commit()
    assert settings_svc.get_retention_days(db) == 45


def test_role_mapping_keeps_valid_roles_only(db, admin):
    mapping = settings_svc.set_role_mapping(
        db, mapping={"BI-Reviewers": "reviewer", "Bad": "superadmin"},
        updated_by=admin.id,
    )
    db.commit()
    assert mapping == {"BI-Reviewers": "reviewer"}  # rôle invalide écarté


# --- Rétention -------------------------------------------------------------
def _make_xlsx():
    from openpyxl import Workbook
    wb = Workbook(); ws = wb.active
    ws.append(["Règle", "Statut"]); ws.append(["Une règle", "OK"])
    buf = io.BytesIO(); wb.save(buf); return buf.getvalue()


def test_retention_purge_removes_old_jobs_keeps_reviews(db, admin, tmp_path):
    from app.services.storage.providers import InternalStorageProvider

    # Config stockage interne sur tmp.
    db.add(IntegrationConfig(kind="storage", provider="internal",
                             settings={"base_path": str(tmp_path)}, is_active=True))
    settings_svc.set_retention_days(db, days=30, updated_by=admin.id)
    db.commit()

    # Une revue (ne doit jamais être purgée).
    cat = Category(checklist_type=ChecklistType.powerbi, name="M", order_index=0)
    db.add(cat); db.commit(); db.refresh(cat)
    ref_svc.create_rule(db, actor=admin, checklist_type=ChecklistType.powerbi,
                        category=cat, text="R", subs=[], criticality=Criticality.recommended)
    db.commit()
    review = rev_svc.create_review(db, author=admin, report_name="Rap",
                                   checklist_type=ChecklistType.powerbi)
    db.commit()

    provider = InternalStorageProvider(base_path=str(tmp_path))
    ref = provider.put("imports/old.xlsx", _make_xlsx(), "application/octet-stream")

    # Un job ANCIEN (au-delà de la rétention) et un job RÉCENT.
    old_job = ImportJob(review_id=review.id, source="upload", file_ref=ref, status="done")
    new_job = ImportJob(review_id=review.id, source="upload", file_ref=ref, status="done")
    db.add_all([old_job, new_job]); db.commit()
    # Force la date de création de old_job dans le passé.
    old_job.created_at = datetime.now(timezone.utc) - timedelta(days=40)
    db.commit()

    result = retention_svc.run_retention_purge(db)
    db.commit()

    assert result["purged_jobs"] == 1
    remaining = db.scalars(select(ImportJob)).all()
    assert len(remaining) == 1 and remaining[0].id == new_job.id
    # La revue est toujours là.
    assert db.get(Review, review.id) is not None
    # Une entrée d'audit de purge a été écrite.
    assert db.scalar(select(AuditLog).where(AuditLog.action == "retention.purge")) is not None


# --- Monitoring ------------------------------------------------------------
def _seed_scored_review(db, admin, statuses):
    cat = Category(checklist_type=ChecklistType.powerbi, name="Modèle", order_index=0)
    db.add(cat); db.commit(); db.refresh(cat)
    for i in range(len(statuses)):
        ref_svc.create_rule(db, actor=admin, checklist_type=ChecklistType.powerbi,
                            category=cat, text=f"R{i}", subs=[],
                            criticality=Criticality.blocking)
    db.commit()
    review = rev_svc.create_review(db, author=admin, report_name="Rap",
                                   checklist_type=ChecklistType.powerbi)
    db.commit()
    items = db.scalars(select(ReviewItem).where(ReviewItem.review_id == review.id)).all()
    for it, st in zip(items, statuses):
        rev_svc.update_item(db, review=review, item=it, patch={"status": st})
    db.commit()
    return review


def test_portfolio_aggregates(db, admin):
    _seed_scored_review(db, admin, [ItemStatus.ok, ItemStatus.ko, ItemStatus.ok])
    p = mon_svc.portfolio(db, user=admin)
    assert p["total_reviews"] == 1
    assert p["average_score"] is not None
    # 1 item KO de criticité blocking → 1 bloquant ouvert.
    assert p["blocking_open"] == 1


def test_review_progress_by_category(db, admin):
    review = _seed_scored_review(db, admin, [ItemStatus.ok, ItemStatus.ko])
    prog = mon_svc.review_progress(db, review=review)
    assert prog["review_id"] == str(review.id)
    assert len(prog["by_category"]) == 1
    assert prog["blocking_open"] == 1


# --- Rate limiter ----------------------------------------------------------
def test_sliding_window_limiter():
    from app.core.rate_limit import SlidingWindowLimiter

    limiter = SlidingWindowLimiter(max_requests=2, window_seconds=60)
    assert limiter.check("k") is True
    assert limiter.check("k") is True
    assert limiter.check("k") is False   # 3e refusée
    assert limiter.check("autre") is True  # clé distincte non affectée
