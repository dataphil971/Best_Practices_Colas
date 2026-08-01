"""
Tests de la logique du référentiel versionné (Lot 2).

Vérifient les invariants métier centraux :
  - un admin crée une règle directement approuvée ; un contributeur crée une
    proposition en attente ;
  - reformuler crée une NOUVELLE version sans écraser l'ancienne, et bascule la
    version courante ;
  - approbation / rejet d'une proposition ;
  - retrait / restauration réversibles ;
  - chaque action laisse une trace dans le journal d'activité.
"""
from sqlalchemy import select

from app.models.category import Category
from app.models.rule import RuleVersion
from app.models.rule_activity import RuleActivity
from app.models.enums import ChecklistType, Criticality, LifecycleState
from app.services import referential as svc


def _make_category(db) -> Category:
    cat = Category(checklist_type=ChecklistType.powerbi, name="Modèle", order_index=0)
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


def test_admin_creation_is_approved(db, admin):
    cat = _make_category(db)
    rule = svc.create_rule(
        db, actor=admin, checklist_type=ChecklistType.powerbi, category=cat,
        text="Vérifier les types de données.", subs=["décimales en fixed decimal"],
        criticality=Criticality.blocking,
    )
    db.commit()
    current = svc.get_current_version(db, rule.id)
    assert current is not None
    assert current.version_number == 1
    assert current.lifecycle == LifecycleState.approved
    assert current.is_current is True
    # journal : rule_created
    acts = db.scalars(select(RuleActivity)).all()
    assert len(acts) == 1
    assert acts[0].action == "rule_created"


def test_contributor_creation_is_pending(db, contributor):
    cat = _make_category(db)
    rule = svc.create_rule(
        db, actor=contributor, checklist_type=ChecklistType.powerbi, category=cat,
        text="Proposition d'un contributeur.", subs=[], criticality=Criticality.optional,
    )
    db.commit()
    current = svc.get_current_version(db, rule.id)
    assert current.lifecycle == LifecycleState.pending
    act = db.scalar(select(RuleActivity))
    assert act.action == "rule_proposed"


def test_revision_creates_new_immutable_version(db, admin):
    cat = _make_category(db)
    rule = svc.create_rule(
        db, actor=admin, checklist_type=ChecklistType.powerbi, category=cat,
        text="Texte initial.", subs=["a"], criticality=Criticality.recommended,
    )
    db.commit()
    v1 = svc.get_current_version(db, rule.id)
    v1_id, v1_text = v1.id, v1.text

    svc.revise_rule(
        db, actor=admin, rule=rule, text="Texte reformulé.", subs=["a", "b"],
        criticality=Criticality.blocking,
    )
    db.commit()

    # L'ancienne version existe toujours, inchangée, mais n'est plus courante.
    all_versions = db.scalars(
        select(RuleVersion).where(RuleVersion.rule_id == rule.id)
    ).all()
    assert len(all_versions) == 2
    old = next(v for v in all_versions if v.id == v1_id)
    assert old.text == v1_text          # immuable : le texte n'a pas changé
    assert old.is_current is False

    current = svc.get_current_version(db, rule.id)
    assert current.version_number == 2
    assert current.text == "Texte reformulé."
    assert current.criticality == Criticality.blocking

    # Une seule version courante.
    currents = [v for v in all_versions if v.is_current]
    assert len(currents) == 1

    # Journal : création + révision.
    actions = [a.action for a in db.scalars(select(RuleActivity)).all()]
    assert actions == ["rule_created", "rule_revised"]


def test_approve_and_reject_flow(db, admin, contributor):
    cat = _make_category(db)
    # deux propositions en attente
    r1 = svc.create_rule(
        db, actor=contributor, checklist_type=ChecklistType.powerbi, category=cat,
        text="Proposition à approuver.", subs=[], criticality=Criticality.recommended,
    )
    r2 = svc.create_rule(
        db, actor=contributor, checklist_type=ChecklistType.powerbi, category=cat,
        text="Proposition à rejeter.", subs=[], criticality=Criticality.recommended,
    )
    db.commit()

    v1 = svc.get_current_version(db, r1.id)
    svc.approve_version(db, actor=admin, version=v1)
    db.commit()
    assert svc.get_current_version(db, r1.id).lifecycle == LifecycleState.approved

    v2 = svc.get_current_version(db, r2.id)
    svc.reject_version(db, actor=admin, version=v2, reason="Doublon.")
    db.commit()
    # rejetée : plus courante, motif conservé
    rejected = db.get(RuleVersion, v2.id)
    assert rejected.lifecycle == LifecycleState.rejected
    assert rejected.is_current is False
    assert rejected.review_comment == "Doublon."

    actions = {a.action for a in db.scalars(select(RuleActivity)).all()}
    assert {"rule_approved", "rule_rejected"} <= actions


def test_retire_and_restore(db, admin):
    cat = _make_category(db)
    rule = svc.create_rule(
        db, actor=admin, checklist_type=ChecklistType.powerbi, category=cat,
        text="Règle à retirer.", subs=[], criticality=Criticality.recommended,
    )
    db.commit()

    svc.retire_rule(db, actor=admin, rule=rule)
    db.commit()
    assert rule.status == "retired"

    svc.restore_rule(db, actor=admin, rule=rule)
    db.commit()
    assert rule.status == "active"

    actions = [a.action for a in db.scalars(select(RuleActivity)).all()]
    assert "rule_retired" in actions and "rule_restored" in actions
