"""
Tests de la gestion des revues (Lot 3).

Vérifient :
  - la FORMULE du score de conformité (héritée du prototype) : na et unset exclus
    du dénominateur, partial compté pour moitié ;
  - le SNAPSHOT : une revue crée un item par règle active, figé sur la version
    courante — et reste inchangé si le référentiel évolue ensuite ;
  - la mise à jour d'item recalcule et met en cache le score ;
  - l'horodatage de soumission.
"""
from datetime import datetime, timezone

from sqlalchemy import select

from app.models.category import Category
from app.models.rule import RuleVersion
from app.models.review import ReviewItem
from app.models.enums import (
    ChecklistType,
    Criticality,
    ItemStatus,
    ProgressState,
    ReviewStatus,
)
from app.services import referential as ref_svc
from app.services import review as rev_svc


def _seed_referential(db, admin, n_rules=4) -> Category:
    cat = Category(checklist_type=ChecklistType.powerbi, name="Modèle", order_index=0)
    db.add(cat)
    db.commit()
    db.refresh(cat)
    for i in range(n_rules):
        ref_svc.create_rule(
            db, actor=admin, checklist_type=ChecklistType.powerbi, category=cat,
            text=f"Règle {i}", subs=[], criticality=Criticality.recommended,
        )
    db.commit()
    return cat


# --- Formule du score (pur, sans DB) ---------------------------------------
def _fake_items(statuses):
    return [ReviewItem(status=s) for s in statuses]


def test_score_excludes_na_and_unset():
    S = ItemStatus
    items = _fake_items([S.ok, S.ok, S.ko, S.partial, S.na, S.unset])
    r = rev_svc.compute_score(items)
    # évalués = ok(2)+ko(1)+partial(1) = 4 ; score = (2 + 0.5) / 4 * 100 = 62.5 → 62
    assert r["evaluated"] == 4
    assert r["na"] == 1 and r["unset"] == 1
    assert r["score"] == 62
    assert r["total"] == 6


def test_score_all_ok_is_100_and_empty_is_zero():
    S = ItemStatus
    assert rev_svc.compute_score(_fake_items([S.ok, S.ok]))["score"] == 100
    # que des na/unset → aucun évalué → score 0 (pas de division par zéro)
    assert rev_svc.compute_score(_fake_items([S.na, S.unset]))["score"] == 0


# --- Snapshot à la création ------------------------------------------------
def test_create_review_snapshots_current_versions(db, admin):
    _seed_referential(db, admin, n_rules=4)
    review = rev_svc.create_review(
        db, author=admin, report_name="Mon rapport", checklist_type=ChecklistType.powerbi
    )
    db.commit()
    items = db.scalars(
        select(ReviewItem).where(ReviewItem.review_id == review.id)
    ).all()
    assert len(items) == 4
    assert all(it.status == ItemStatus.unset for it in items)
    assert review.compliance_score == 0


def test_snapshot_is_immutable_when_referential_changes(db, admin):
    cat = _seed_referential(db, admin, n_rules=2)
    review = rev_svc.create_review(
        db, author=admin, report_name="R", checklist_type=ChecklistType.powerbi
    )
    db.commit()
    snap_ids = {
        it.rule_version_id
        for it in db.scalars(select(ReviewItem).where(ReviewItem.review_id == review.id)).all()
    }

    # On reformule une règle : nouvelle version courante côté référentiel.
    first_rule = db.scalars(select(RuleVersion)).first().rule
    ref_svc.revise_rule(
        db, actor=admin, rule=first_rule, text="Texte v2", subs=[],
        criticality=Criticality.blocking,
    )
    db.commit()

    # La revue continue de pointer vers les versions figées (inchangées).
    still = {
        it.rule_version_id
        for it in db.scalars(select(ReviewItem).where(ReviewItem.review_id == review.id)).all()
    }
    assert still == snap_ids


# --- Mise à jour d'item + recalcul -----------------------------------------
def test_update_item_recomputes_score(db, admin):
    _seed_referential(db, admin, n_rules=2)
    review = rev_svc.create_review(
        db, author=admin, report_name="R", checklist_type=ChecklistType.powerbi
    )
    db.commit()
    items = db.scalars(select(ReviewItem).where(ReviewItem.review_id == review.id)).all()

    rev_svc.update_item(db, review=review, item=items[0],
                        patch={"status": ItemStatus.ok, "progress": ProgressState.done})
    db.commit()
    # 1 ok, 1 unset → évalués = 1 → score 100
    assert review.compliance_score == 100

    rev_svc.update_item(db, review=review, item=items[1], patch={"status": ItemStatus.ko})
    db.commit()
    # 1 ok, 1 ko → évalués = 2 → score 50
    assert review.compliance_score == 50


def test_submit_sets_timestamp(db, admin):
    _seed_referential(db, admin, n_rules=1)
    review = rev_svc.create_review(
        db, author=admin, report_name="R", checklist_type=ChecklistType.powerbi
    )
    db.commit()
    assert review.submitted_at is None
    rev_svc.set_status(db, review=review, new_status=ReviewStatus.submitted)
    db.commit()
    assert review.submitted_at is not None
    assert review.status == ReviewStatus.submitted
