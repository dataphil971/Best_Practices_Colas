"""
Tests de l'import intelligent et du stockage pluggable (Lot 5).

Couvrent :
  - le moteur de matching local (canonicalisation, IDF, seuils, statut) ;
  - le parsing Excel robuste (colonne texte dynamique, statuts hétérogènes) ;
  - la résolution du connecteur actif (défauts + bascule) ;
  - l'exécution d'un job d'import bout en bout (pré-remplissage + ambigus) ;
  - le stockage interne (put/get/delete).
"""
import io

from sqlalchemy import select

from app.models.category import Category
from app.models.review import ReviewItem
from app.models.integration import ImportJob, IntegrationConfig
from app.models.enums import ChecklistType, Criticality, ItemStatus
from app.services import referential as ref_svc
from app.services import review as rev_svc
from app.services.matching.local import LocalMatchProvider
from app.services.matching.base import RuleRef
from app.services.excel_parser import parse_workbook
from app.services import integrations as integ
from app.services.storage.providers import InternalStorageProvider


# --- Moteur de matching ----------------------------------------------------
def test_local_canonicalisation_and_status():
    p = LocalMatchProvider()
    assert p.detect_status("OK") == ItemStatus.ok
    assert p.detect_status("oui") == ItemStatus.ok
    assert p.detect_status("True") == ItemStatus.ok
    assert p.detect_status("KO") == ItemStatus.ko
    assert p.detect_status("non conforme") == ItemStatus.ko
    assert p.detect_status("partiel") == ItemStatus.partial
    assert p.detect_status("N/A") == ItemStatus.na
    assert p.detect_status("") is None


def test_local_matches_reformulated_rule():
    p = LocalMatchProvider()
    ref = [
        RuleRef("rv1", "Vérifiez les types de données et la précision des décimales"),
        RuleRef("rv2", "Masquer les colonnes techniques inutiles du modèle"),
        RuleRef("rv3", "Créez une table de dates dédiée pour la dimension temporelle"),
    ]
    res = p.match_rules(
        ["cacher les colonnes techniques", "table calendrier temporelle"], ref
    )
    # chaque ligne retrouve la bonne règle
    assert res[0].rule_version_id == "rv2"
    assert res[1].rule_version_id == "rv3"
    assert res[0].confidence > 0


# --- Parsing Excel ---------------------------------------------------------
def _make_xlsx(rows: list[list]) -> bytes:
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_parser_detects_text_column_not_in_a():
    p = LocalMatchProvider()
    # Texte en colonne B, statut en colonne C (cas réel du prototype).
    data = _make_xlsx([
        ["ID", "Règle", "Statut"],
        ["1", "Vérifier les types de données et la précision des décimales", "OK"],
        ["2", "Masquer les colonnes techniques inutiles", "KO"],
    ])
    rows = parse_workbook(data, status_detector=p.detect_status)
    assert len(rows) == 2
    assert "types de données" in rows[0].text
    assert rows[0].status_raw == "OK"
    assert rows[1].status_raw == "KO"


def test_parser_handles_boolean_as_text():
    p = LocalMatchProvider()
    data = _make_xlsx([
        ["Règle", "Conforme"],
        ["Créer une table de dates dédiée", "True"],
    ])
    rows = parse_workbook(data, status_detector=p.detect_status)
    assert rows[0].status_raw == "True"
    assert p.detect_status(rows[0].status_raw) == ItemStatus.ok


# --- Résolution de connecteurs ---------------------------------------------
def test_default_providers(db):
    # Sans configuration : matching local, storage interne.
    assert integ.get_active_match_provider(db).name == "local"
    assert integ.get_active_storage_provider(db).name == "internal"


def test_storage_switch_reads_active(db, admin):
    # Active un fournisseur interne explicitement configuré.
    cfg = IntegrationConfig(
        kind="storage", provider="internal",
        settings={"base_path": "/tmp/pr-review-test-store"}, is_active=True,
    )
    db.add(cfg)
    db.commit()
    provider = integ.get_active_storage_provider(db)
    assert provider.name == "internal"


# --- Stockage interne ------------------------------------------------------
def test_internal_storage_roundtrip(tmp_path):
    provider = InternalStorageProvider(base_path=str(tmp_path))
    ref = provider.put("imports/abc/file.xlsx", b"hello", "application/octet-stream")
    assert ref.startswith("internal://")
    assert provider.get(ref) == b"hello"
    provider.delete(ref)
    try:
        provider.get(ref)
        assert False, "le fichier aurait dû être supprimé"
    except FileNotFoundError:
        pass


# --- Import runner bout en bout --------------------------------------------
def _seed_review_with_rules(db, admin, texts):
    cat = Category(checklist_type=ChecklistType.powerbi, name="Modèle", order_index=0)
    db.add(cat)
    db.commit()
    db.refresh(cat)
    for t in texts:
        ref_svc.create_rule(
            db, actor=admin, checklist_type=ChecklistType.powerbi, category=cat,
            text=t, subs=[], criticality=Criticality.recommended,
        )
    db.commit()
    review = rev_svc.create_review(
        db, author=admin, report_name="R", checklist_type=ChecklistType.powerbi
    )
    db.commit()
    return review


def test_import_job_prefills_statuses(db, admin, tmp_path):
    from app.services.import_runner import run_import_job

    review = _seed_review_with_rules(db, admin, [
        "Vérifiez les types de données et la précision des décimales",
        "Masquer les colonnes techniques inutiles du modèle",
        "Créez une table de dates dédiée pour la dimension temporelle",
    ])

    # Fichier importé : libellés reformulés + statuts.
    data = _make_xlsx([
        ["Règle", "Statut"],
        ["verifier les types de donnees et la precision decimale", "OK"],
        ["cacher les colonnes techniques inutiles", "KO"],
        ["table calendrier pour la dimension temporelle", "Partiel"],
    ])

    # Stocke via le connecteur interne pointé sur tmp_path.
    cfg = IntegrationConfig(kind="storage", provider="internal",
                            settings={"base_path": str(tmp_path)}, is_active=True)
    db.add(cfg)
    db.commit()
    storage = integ.get_active_storage_provider(db)
    file_ref = storage.put("imports/r/f.xlsx", data, "application/octet-stream")

    job = ImportJob(review_id=review.id, source="upload", file_ref=file_ref, status="queued")
    db.add(job)
    db.commit()

    run_import_job(db, job)
    db.commit()

    assert job.status == "done"
    assert job.result["total"] == 3
    assert job.result["filled"] >= 1  # au moins un statut appliqué
    # Le score a été recalculé (au moins un item évalué).
    assert review.compliance_score is not None

    # Au moins un item a bien reçu un statut non-unset.
    items = db.scalars(select(ReviewItem).where(ReviewItem.review_id == review.id)).all()
    assert any(it.status != ItemStatus.unset for it in items)


def test_import_job_failure_is_captured(db, admin, tmp_path):
    from app.services.import_runner import run_import_job

    review = _seed_review_with_rules(db, admin, ["Une règle"])
    # file_ref inexistant → get() échoue → job failed proprement.
    cfg = IntegrationConfig(kind="storage", provider="internal",
                            settings={"base_path": str(tmp_path)}, is_active=True)
    db.add(cfg)
    db.commit()
    job = ImportJob(review_id=review.id, source="upload",
                    file_ref="internal://imports/does/not/exist.xlsx", status="queued")
    db.add(job)
    db.commit()
    run_import_job(db, job)
    db.commit()
    assert job.status == "failed"
    assert job.error
