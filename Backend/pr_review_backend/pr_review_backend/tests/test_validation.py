"""
Tests de la validation tierce (Lot 4).

Vérifient :
  - la génération d'un lien de partage ciblé (token, expiration, cibles) ;
  - la validité d'un token (actif / révoqué / expiré) ;
  - la politique de visibilité : un reviewer ne voit une revue que si un lien
    actif le cible ; sinon non ; l'admin voit tout ;
  - l'approbation → `validated` (+ validated_at) et le refus →
    `changes_requested`, avec commentaires par point ;
  - le garde-fou : les commentaires visant un item hors revue sont ignorés.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models.category import Category
from app.models.review import ReviewItem
from app.models.share import ShareLink, ShareTarget, ValidationItemComment
from app.models.enums import ChecklistType, Criticality, ReviewStatus
from app.services import referential as ref_svc
from app.services import review as rev_svc
from app.services import validation as val_svc


def _seed_review(db, admin, n_rules=3):
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
    review = rev_svc.create_review(
        db, author=admin, report_name="Rapport", checklist_type=ChecklistType.powerbi
    )
    db.commit()
    return review


# --- Partage ---------------------------------------------------------------
def test_create_share_link_targets_reviewer(db, admin, reviewer):
    review = _seed_review(db, admin)
    link = val_svc.create_share_link(
        db, review=review, creator=admin, reviewer_ids=[reviewer.id], ttl_days=7
    )
    db.commit()
    assert link.token and len(link.token) >= 40      # ~256 bits base64url
    assert link.revoked is False
    # SQLite renvoie un datetime naïf ; on normalise pour comparer (en prod :
    # TIMESTAMPTZ, donc déjà tz-aware). L'invariant testé : expiration future.
    exp = link.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    assert exp > datetime.now(timezone.utc)
    targets = db.scalars(
        select(ShareTarget).where(ShareTarget.share_link_id == link.id)
    ).all()
    assert [t.reviewer_id for t in targets] == [reviewer.id]


def test_token_validity_active_revoked_expired(db, admin, reviewer):
    review = _seed_review(db, admin)
    link = val_svc.create_share_link(
        db, review=review, creator=admin, reviewer_ids=[reviewer.id]
    )
    db.commit()
    # actif
    assert val_svc.get_active_link_by_token(db, link.token) is not None
    # révoqué
    val_svc.revoke_share_link(db, link=link)
    db.commit()
    assert val_svc.get_active_link_by_token(db, link.token) is None
    # expiré
    link.revoked = False
    link.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
    db.commit()
    assert val_svc.get_active_link_by_token(db, link.token) is None


# --- Visibilité ------------------------------------------------------------
def test_reviewer_visibility_requires_active_share(db, admin, reviewer, contributor):
    review = _seed_review(db, admin)
    # sans partage : le reviewer ne voit pas
    assert val_svc.can_user_view_review(db, review=review, user=reviewer) is False
    # avec partage actif ciblant le reviewer : il voit
    val_svc.create_share_link(db, review=review, creator=admin, reviewer_ids=[reviewer.id])
    db.commit()
    assert val_svc.can_user_view_review(db, review=review, user=reviewer) is True
    # un autre utilisateur non ciblé ne voit pas
    assert val_svc.can_user_view_review(db, review=review, user=contributor) is False
    # l'admin voit toujours
    assert val_svc.can_user_view_review(db, review=review, user=admin) is True


def test_list_visible_ids_for_reviewer(db, admin, reviewer):
    r1 = _seed_review(db, admin)
    val_svc.create_share_link(db, review=r1, creator=admin, reviewer_ids=[reviewer.id])
    db.commit()
    ids = val_svc.list_visible_review_ids_for_reviewer(db, reviewer)
    assert r1.id in ids


# --- Validation ------------------------------------------------------------
def test_approval_sets_validated(db, admin, reviewer):
    review = _seed_review(db, admin)
    val_svc.submit_validation(
        db, review=review, reviewer=reviewer, decision="approved",
        global_comment="Bon travail", item_comments={},
    )
    db.commit()
    assert review.status == ReviewStatus.validated
    assert review.validated_at is not None


def test_rejection_sets_changes_requested_with_item_comments(db, admin, reviewer):
    review = _seed_review(db, admin, n_rules=3)
    items = db.scalars(
        select(ReviewItem).where(ReviewItem.review_id == review.id)
    ).all()
    target_item = items[0]
    validation = val_svc.submit_validation(
        db, review=review, reviewer=reviewer, decision="rejected",
        global_comment="À revoir",
        item_comments={target_item.id: "Ce point n'est pas conforme."},
    )
    db.commit()
    assert review.status == ReviewStatus.changes_requested
    comments = db.scalars(
        select(ValidationItemComment).where(
            ValidationItemComment.validation_id == validation.id
        )
    ).all()
    assert len(comments) == 1
    assert comments[0].review_item_id == target_item.id


def test_item_comment_for_foreign_item_is_ignored(db, admin, reviewer):
    import uuid
    review = _seed_review(db, admin)
    validation = val_svc.submit_validation(
        db, review=review, reviewer=reviewer, decision="rejected",
        global_comment=None,
        item_comments={uuid.uuid4(): "Commentaire sur un item étranger"},
    )
    db.commit()
    comments = db.scalars(
        select(ValidationItemComment).where(
            ValidationItemComment.validation_id == validation.id
        )
    ).all()
    assert comments == []  # garde-fou d'intégrité : ignoré


def test_resubmit_cycle_after_changes_requested(db, admin, reviewer):
    review = _seed_review(db, admin)
    val_svc.submit_validation(
        db, review=review, reviewer=reviewer, decision="rejected",
        global_comment=None, item_comments={},
    )
    db.commit()
    assert review.status == ReviewStatus.changes_requested
    # l'auteur corrige et resoumet
    rev_svc.set_status(db, review=review, new_status=ReviewStatus.submitted)
    db.commit()
    assert review.status == ReviewStatus.submitted
