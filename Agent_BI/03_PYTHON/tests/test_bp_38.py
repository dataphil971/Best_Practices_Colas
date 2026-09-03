"""Tests de non-régression pour BP-38.

Scénarios alignés sur Agent_BI/01_ALGORITHMES/38_EliminateVisualInteractions.md,
sous-contrôle de COHÉRENCE TECHNIQUE uniquement (§1 : « La première est
déterministe » ; la pertinence fonctionnelle exige une policy absente ici).
"""

from pathlib import Path

from engine.context import AnalysisContext
from rules import bp_38

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "bp_38"


def _context_for(scenario: str) -> AnalysisContext:
    return AnalysisContext.load(FIXTURES / scenario)


def test_ok_when_every_interaction_references_existing_visuals():
    result = bp_38.check(_context_for("ok"))

    assert result.rule_status == "OK"
    assert result.summary["total_interactions"] == 1
    assert result.summary["broken_interactions"] == 0


def test_ko_when_an_interaction_targets_a_missing_visual():
    result = bp_38.check(_context_for("ko"))

    assert result.rule_status == "KO"
    assert result.summary["broken_interactions"] == 1
    ko = result.summary["ko_details"][0]
    assert ko["evidence"]["missing"] == ["target"]


def test_na_when_no_interaction_is_serialized(tmp_path):
    # §3 : l'absence d'entrée ne prouve rien — ni « interaction inutile »,
    # ni « interaction non revue ».
    (tmp_path / "M.SemanticModel" / "definition" / "tables").mkdir(parents=True)
    page = tmp_path / "R.Report" / "definition" / "pages" / "p1"
    page.mkdir(parents=True)
    (page / "page.json").write_text('{"name":"p1"}', encoding="utf-8")

    result = bp_38.check(AnalysisContext.load(tmp_path))

    assert result.rule_status == "NA"
    assert result.summary["total_interactions"] == 0


def test_na_when_no_report_is_available():
    context = AnalysisContext.from_semantic_model_path(FIXTURES / "ok" / "M.SemanticModel")
    result = bp_38.check(context)

    assert result.rule_status == "NA"
    assert result.execution_status == "PARTIAL"


def test_the_raw_interaction_type_is_preserved_in_the_evidence():
    # §5 : conserver la valeur brute, ne jamais la normaliser silencieusement.
    result = bp_38.check(_context_for("ok"))

    assert result.findings[0].evidence["type"] == "DataFilter"
