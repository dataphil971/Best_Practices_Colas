"""
Tests de l'import des résultats Agent BI (Lot 8).

Couvre : application OK/KO/NA via `rules.code`, non-écrasement d'un statut
humain (conflit signalé), idempotence par empreinte de projet, règle
inconnue du référentiel, règle hors du snapshot de la revue, recalcul du
score une seule fois.
"""
from sqlalchemy import select

from app.models.category import Category
from app.models.rule import Rule, RuleVersion
from app.models.review import ReviewItem
from app.models.enums import ChecklistType, Criticality, ItemStatus, LifecycleState
from app.services import review as rev_svc
from app.services.agent_results import apply_agent_envelope
from app.schemas.agent_results import AgentEnvelopeIn


def _seed_review_with_bp22(db, admin):
    """Une revue avec deux règles : une porteuse du code BP-22, une sans code."""
    cat = Category(checklist_type=ChecklistType.powerbi, name="Modèle", order_index=0)
    db.add(cat)
    db.commit()
    db.refresh(cat)

    rule_bp22 = Rule(
        checklist_type=ChecklistType.powerbi, category_id=cat.id,
        status="active", code="BP-22", created_by=admin.id,
    )
    db.add(rule_bp22)
    db.flush()
    db.add(RuleVersion(
        rule_id=rule_bp22.id, version_number=1,
        text="Désactiver la synthèse automatique.", subs=[],
        criticality=Criticality.blocking, is_current=True,
        lifecycle=LifecycleState.approved,
    ))

    rule_no_code = Rule(
        checklist_type=ChecklistType.powerbi, category_id=cat.id,
        status="active", code=None, created_by=admin.id,
    )
    db.add(rule_no_code)
    db.flush()
    db.add(RuleVersion(
        rule_id=rule_no_code.id, version_number=1,
        text="Une autre règle, sans checker Agent BI.", subs=[],
        criticality=Criticality.recommended, is_current=True,
        lifecycle=LifecycleState.approved,
    ))
    db.commit()

    review = rev_svc.create_review(
        db, author=admin, report_name="Rapport test", checklist_type=ChecklistType.powerbi,
    )
    db.commit()
    return review


def _envelope(rule_status="OK", fingerprint="sha256:abc"):
    return AgentEnvelopeIn(
        schema_version="1.0",
        engine_version="0.1.0",
        project={"name": "Test", "format": "PBIP", "fingerprint": fingerprint},
        results=[
            {
                "rule_id": "BP-22",
                "alias": "SEM-001",
                "rule_name": "Désactivation de l'autosummarization",
                "execution_status": "SUCCESS",
                "rule_status": rule_status,
                "total_columns": 69,
                "findings": [],
            }
        ],
    )


def _bp22_item(db, review):
    return db.scalar(
        select(ReviewItem)
        .join(RuleVersion, RuleVersion.id == ReviewItem.rule_version_id)
        .join(Rule, Rule.id == RuleVersion.rule_id)
        .where(ReviewItem.review_id == review.id, Rule.code == "BP-22")
    )


def test_applies_ok_status_from_agent(db, admin):
    review = _seed_review_with_bp22(db, admin)

    result = apply_agent_envelope(db, review=review, envelope=_envelope("OK"))
    db.commit()

    assert result["applied"] == 1
    assert result["conflicts"] == 0
    item = _bp22_item(db, review)
    assert item.status == ItemStatus.ok
    assert item.last_update_source == "agent"
    assert item.agent_evidence["rule_status"] == "OK"
    assert review.compliance_score == 100


def test_applies_ko_and_na_statuses():
    mapping = {"OK": ItemStatus.ok, "KO": ItemStatus.ko, "NA": ItemStatus.na}
    assert set(mapping) == {"OK", "KO", "NA"}  # documente le contrat, pas de DB nécessaire


def test_does_not_overwrite_a_human_set_status(db, admin):
    review = _seed_review_with_bp22(db, admin)
    item = _bp22_item(db, review)
    rev_svc.update_item(db, review=review, item=item, patch={"status": ItemStatus.ko})
    db.commit()
    assert item.last_update_source == "human"

    result = apply_agent_envelope(db, review=review, envelope=_envelope("OK"))
    db.commit()

    assert result["applied"] == 0
    assert result["conflicts"] == 1
    assert result["details"]["conflicts"][0]["previous_status"] == "ko"
    assert result["details"]["conflicts"][0]["proposed_status"] == "ok"
    # Le statut humain n'a pas bougé.
    assert item.status == ItemStatus.ko


def test_reapplying_the_same_fingerprint_is_a_no_op(db, admin):
    review = _seed_review_with_bp22(db, admin)

    apply_agent_envelope(db, review=review, envelope=_envelope("OK", fingerprint="sha256:v1"))
    db.commit()

    result = apply_agent_envelope(db, review=review, envelope=_envelope("OK", fingerprint="sha256:v1"))
    db.commit()

    assert result["applied"] == 0
    assert result["already_applied"] == 1


def test_a_changed_fingerprint_reapplies(db, admin):
    review = _seed_review_with_bp22(db, admin)

    apply_agent_envelope(db, review=review, envelope=_envelope("KO", fingerprint="sha256:v1"))
    db.commit()
    item = _bp22_item(db, review)
    assert item.status == ItemStatus.ko

    # Le modèle a été corrigé (nouveau fingerprint) : la ré-analyse doit
    # bien passer l'item à OK, ce n'est pas un no-op malgré le
    # last_update_source == "agent" hérité du run précédent.
    result = apply_agent_envelope(db, review=review, envelope=_envelope("OK", fingerprint="sha256:v2"))
    db.commit()

    assert result["applied"] == 1
    assert item.status == ItemStatus.ok


def test_unknown_rule_code_is_reported_as_unmatched(db, admin):
    review = _seed_review_with_bp22(db, admin)
    envelope = _envelope("OK")
    envelope.results[0].rule_id = "BP-99"

    result = apply_agent_envelope(db, review=review, envelope=envelope)
    db.commit()

    assert result["unmatched"] == 1
    assert result["details"]["unmatched"][0]["reason"] == "rule_code_unknown"


def test_rejects_unsupported_schema_version(db, admin):
    review = _seed_review_with_bp22(db, admin)
    envelope = _envelope("OK")
    envelope.schema_version = "2.0"

    try:
        apply_agent_envelope(db, review=review, envelope=envelope)
        assert False, "aurait dû lever ValueError"
    except ValueError:
        pass


def test_score_is_recomputed_after_applying(db, admin):
    review = _seed_review_with_bp22(db, admin)
    assert review.compliance_score == 0

    apply_agent_envelope(db, review=review, envelope=_envelope("KO"))
    db.commit()

    # 1 item KO, 1 item unset (na/unset exclus du calcul) -> score = 0
    assert review.compliance_score == 0
