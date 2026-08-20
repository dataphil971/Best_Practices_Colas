"""Tests de non-régression pour BP-41.

Scénarios alignés sur Agent_BI/01_ALGORITHMES/41_RemoveRedundantVisuals.md.

Ces tests protègent surtout l'INVARIANT de la règle hybride : un candidat
n'est jamais une violation. Une régression qui ferait passer BP-41 en KO
sur la seule égalité des signatures contredirait à la fois le §2 de
l'algorithme et le skill `agent-bi-context-review`.
"""

from pathlib import Path

from engine.context import AnalysisContext
from rules import bp_41

FIXTURES = Path(__file__).parent / "fixtures" / "bp_41"


def _context_for(scenario: str) -> AnalysisContext:
    return AnalysisContext.load(FIXTURES / scenario)


def test_identical_signatures_produce_a_candidate_never_a_ko():
    # §2 : « Le checker Python ne doit jamais transformer seul un candidat
    # en KO sur la simple égalité des signatures. »
    result = bp_41.check(_context_for("candidats"))

    assert result.rule_status != "KO"
    assert result.rule_status == "NA"
    assert result.summary["duplicate_candidates"] == 1
    assert result.summary["requires_context_review"] is True


def test_the_candidate_carries_the_contract_expected_by_the_review_skill():
    result = bp_41.check(_context_for("candidats"))
    candidate = result.candidates[0].to_dict()

    # Contrat d'entrée de `.github/skills/agent-bi-context-review`.
    assert candidate["rule_id"] == "BP-41"
    assert candidate["candidate_id"].startswith("DUP-")
    assert candidate["candidate_type"] == "DUPLICATE_VISUAL"
    assert len(candidate["objects"]) == 2
    assert candidate["technical_evidence"]["occurrence_count"] == 2
    # §8 : le reviewer doit savoir si la répétition est intra ou inter-pages.
    assert candidate["review_context"]["same_page"] is False
    assert candidate["review_context"]["distinct_page_count"] == 2


def test_candidate_ids_are_stable_across_runs():
    # Une décision de revue déjà rendue doit rester rattachable à son
    # candidat : l'identifiant ne peut pas dépendre de l'ordre de parcours.
    first = bp_41.check(_context_for("candidats")).candidates[0].candidate_id
    second = bp_41.check(_context_for("candidats")).candidates[0].candidate_id

    assert first == second


def test_ok_when_no_two_visuals_share_a_signature():
    result = bp_41.check(_context_for("aucun_doublon"))

    assert result.rule_status == "OK"
    assert result.summary["duplicate_candidates"] == 0
    assert result.candidates == []


def test_decorative_visuals_are_out_of_scope():
    # §4 : textbox/image/shape/actionButton ne participent pas à la
    # recherche de doublons analytiques.
    result = bp_41.check(_context_for("aucun_doublon"))

    assert result.summary["out_of_scope_visuals"] == 1


def test_na_when_no_report_is_available():
    context = AnalysisContext.from_semantic_model_path(
        FIXTURES / "candidats" / "M.SemanticModel"
    )
    result = bp_41.check(context)

    assert result.rule_status == "NA"
    assert result.summary["duplicate_candidates"] == 0


def test_candidates_are_serialised_into_the_json_contract():
    # Un consommateur externe (LLM, backend) ne voit que to_dict().
    result = bp_41.check(_context_for("candidats")).to_dict()

    assert "candidates" in result
    assert result["candidates"][0]["candidate_type"] == "DUPLICATE_VISUAL"


def test_a_purely_deterministic_rule_exposes_no_candidates_key():
    # Ne pas laisser croire qu'une revue est attendue là où le moteur a
    # tranché seul.
    from rules import bp_22

    result = bp_22.check(
        AnalysisContext.from_semantic_model_path(
            Path(__file__).parent / "fixtures" / "bp_22" / "ko"
        )
    ).to_dict()

    assert "candidates" not in result
