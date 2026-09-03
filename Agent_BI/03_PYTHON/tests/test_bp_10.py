"""Tests de non-régression pour BP-10.

Scénarios alignés sur Agent_BI/01_ALGORITHMES/10_SurrogateKeys.md :
si un de ces tests doit changer, l'algorithme doit changer en premier.
"""

from pathlib import Path

from engine.context import AnalysisContext
from rules import bp_10

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "bp_10"


def _context_for(scenario: str) -> AnalysisContext:
    return AnalysisContext.from_semantic_model_path(FIXTURES / scenario)


def test_ok_when_both_endpoints_are_int64():
    result = bp_10.check(_context_for("ok"))

    assert result.rule_status == "OK"
    assert result.summary["conforming_relationships"] == 1
    assert result.summary["nonconforming_relationships"] == 0


def test_ko_when_both_endpoints_are_strings():
    result = bp_10.check(_context_for("ko"))

    assert result.rule_status == "KO"
    codes = {d["object"] for d in result.summary["ko_details"]}
    assert "22222222-2222-2222-2222-222222222222" in codes


def test_ko_with_type_mismatch_diagnostic_when_the_two_sides_differ():
    # §5 : un écart de type entre les deux extrémités reste un diagnostic
    # SUPPLÉMENTAIRE — le constat principal est « type attendu non respecté ».
    result = bp_10.check(_context_for("ko"))

    mismatch = next(
        d for d in result.summary["ko_details"] if d["object"] == "33333333-3333-3333-3333-333333333333"
    )
    assert mismatch["evidence"]["diagnostics"] == ["TYPE_MISMATCH"]
    assert mismatch["actual"] == "int64 / string"


def test_na_when_a_calculated_table_column_has_no_datatype():
    # Cas réel (AI_BAROMETER_BI-CDS.SemanticModel) : une colonne de table
    # calculée n'a pas de `dataType` sérialisé — §7 impose NA, jamais un KO
    # par défaut sur une propriété simplement absente.
    result = bp_10.check(_context_for("na_calculated"))

    assert result.rule_status == "NA"
    assert result.execution_status == "PARTIAL"
    assert result.summary["na_relationships"] == 1


def test_na_when_no_relationship_exists():
    result = bp_10.check(_context_for("na_no_relationship"))

    assert result.rule_status == "NA"
    assert result.summary["total_relationships"] == 0


def test_na_when_a_referenced_column_is_not_found_in_any_table(tmp_path):
    semantic_model = tmp_path / "T.SemanticModel"
    (semantic_model / "definition" / "tables").mkdir(parents=True)
    (semantic_model / "definition" / "relationships.tmdl").write_text(
        "relationship aaaaaaaa-0000-0000-0000-000000000000\n"
        "\tfromColumn: F_INCONNUE.CLE\n"
        "\ttoColumn: D_INCONNUE.CLE\n",
        encoding="utf-8",
    )

    result = bp_10.check(AnalysisContext.from_semantic_model_path(semantic_model))

    assert result.rule_status == "NA"
    assert "non résolues" in result.findings[0].reason


def test_int32_is_not_silently_accepted(tmp_path):
    # §4 : ne pas accepter silencieusement int32/integer si ces valeurs ne
    # font pas partie du contrat TMDL analysé.
    semantic_model = tmp_path / "T.SemanticModel"
    tables_dir = semantic_model / "definition" / "tables"
    tables_dir.mkdir(parents=True)
    (semantic_model / "definition" / "relationships.tmdl").write_text(
        "relationship bbbbbbbb-0000-0000-0000-000000000000\n\tfromColumn: F_A.CLE\n\ttoColumn: D_B.CLE\n",
        encoding="utf-8",
    )
    (tables_dir / "F_A.tmdl").write_text(
        "table F_A\n\tlineageTag: x\n\n\tcolumn CLE\n\t\tdataType: int32\n",
        encoding="utf-8",
    )
    (tables_dir / "D_B.tmdl").write_text(
        "table D_B\n\tlineageTag: y\n\n\tcolumn CLE\n\t\tdataType: int64\n",
        encoding="utf-8",
    )

    result = bp_10.check(AnalysisContext.from_semantic_model_path(semantic_model))

    assert result.rule_status == "KO"
