"""Tests de non-régression pour BP-03.

Scénarios alignés sur Agent_BI/01_ALGORITHMES/03_AvoidBidirectional.md :
si un de ces tests doit changer, l'algorithme doit changer en premier.
"""

from pathlib import Path

from engine.context import AnalysisContext
from rules import bp_03

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "bp_03"


def _context_for(scenario: str) -> AnalysisContext:
    return AnalysisContext.from_semantic_model_path(FIXTURES / scenario)


def test_ok_for_a_standard_one_to_many_relationship_with_defaults_omitted():
    # Aucune des trois propriétés (cardinalité, filtrage croisé) n'est écrite
    # dans le TMDL : c'est l'état réel d'une relation *:1 standard (cf.
    # l'extrait réel documenté au §3.2 de 21_ConciseNames.md, qui n'écrit
    # aucune de ces propriétés). Les défauts résolus doivent donner OK.
    result = bp_03.check(_context_for("ok"))

    assert result.rule_status == "OK"
    assert result.summary["total_relationships"] == 1
    assert result.findings[0].status == "OK"


def test_ko_for_an_explicit_many_to_many_relationship():
    result = bp_03.check(_context_for("ko_m2m"))

    assert result.rule_status == "KO"
    assert result.summary["ko_details"][0]["actual"] == "MANY_TO_MANY"
    assert result.summary["ko_details"][0]["reason"] == "Relation many-to-many directe"


def test_ko_for_an_explicit_bidirectional_relationship():
    result = bp_03.check(_context_for("ko_bidir"))

    assert result.rule_status == "KO"
    assert result.summary["ko_details"][0]["actual"] == "BOTH_DIRECTIONS"


def test_na_when_no_relationship_exists():
    result = bp_03.check(_context_for("na"))

    assert result.rule_status == "NA"
    assert result.summary["total_relationships"] == 0


def test_na_when_cross_filtering_behavior_is_unreadable(tmp_path):
    semantic_model = tmp_path / "T.SemanticModel"
    (semantic_model / "definition" / "tables").mkdir(parents=True)
    (semantic_model / "definition" / "relationships.tmdl").write_text(
        "relationship aaaaaaaa-0000-0000-0000-000000000000\n"
        "\tfromColumn: F_A.CLE\n"
        "\ttoColumn: D_B.CLE\n"
        "\tcrossFilteringBehavior: uneValeurInconnue\n",
        encoding="utf-8",
    )

    result = bp_03.check(AnalysisContext.from_semantic_model_path(semantic_model))

    assert result.rule_status == "NA"
    assert result.findings[0].reason == "crossFilteringBehavior non résolu"


def test_ko_for_a_one_to_one_relationship_regardless_of_cross_filter_value(tmp_path):
    # §9 : Power BI filtre dans les deux sens sur une relation 1:1, quelle
    # que soit la valeur littérale de crossFilteringBehavior.
    semantic_model = tmp_path / "T.SemanticModel"
    (semantic_model / "definition" / "tables").mkdir(parents=True)
    (semantic_model / "definition" / "relationships.tmdl").write_text(
        "relationship bbbbbbbb-0000-0000-0000-000000000000\n"
        "\tfromColumn: D_A.CLE\n"
        "\ttoColumn: D_B.CLE\n"
        "\tfromCardinality: one\n",
        encoding="utf-8",
    )

    result = bp_03.check(AnalysisContext.from_semantic_model_path(semantic_model))

    assert result.rule_status == "KO"
    assert result.findings[0].actual == "ONE_TO_ONE"
