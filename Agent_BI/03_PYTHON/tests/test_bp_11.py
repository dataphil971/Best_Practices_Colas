"""Tests de non-régression pour BP-11.

Scénarios alignés sur Agent_BI/01_ALGORITHMES/11_DataTypesPrecision.md :
si un de ces tests doit changer, l'algorithme doit changer en premier.
"""

from pathlib import Path

from engine.context import AnalysisContext
from powerbi.m_lang import parse_type_transform_list
from rules import bp_11

FIXTURES = Path(__file__).parent / "fixtures" / "bp_11"


def _context_for(scenario: str) -> AnalysisContext:
    return AnalysisContext.from_semantic_model_path(FIXTURES / scenario)


def test_ok_when_model_type_matches_the_power_query_conversion():
    result = bp_11.check(_context_for("ok"))

    assert result.rule_status == "OK"
    assert result.summary["numeric_columns"] == 1
    assert result.summary["conforming_columns"] == 1
    numeric = next(f for f in result.findings if f.status == "OK")
    assert numeric.evidence["expectation_source"] == "POWER_QUERY"


def test_ko_when_the_model_declares_double_but_power_query_declares_int64():
    # §9.1 : `expected = int64`, `actual = double` démontré par Power Query.
    result = bp_11.check(_context_for("ko"))

    assert result.rule_status == "KO"
    ko = result.summary["ko_details"][0]
    assert ko["expected"] == "int64"
    assert ko["actual"] == "double"
    assert ko["evidence"]["m_type"] == "Int64.Type"


def test_na_when_no_power_query_conversion_proves_the_intended_type():
    # §9.3 : un nom en `_AMOUNT` ne prouve rien — NA, jamais KO.
    result = bp_11.check(_context_for("na_no_proof"))

    assert result.rule_status == "NA"
    assert result.summary["nonconforming_columns"] == 0


def test_na_when_two_queries_type_the_same_column_name_differently():
    # §4 exige une conversion « explicite et RÉSOLUE » : deux conversions
    # contradictoires ne résolvent rien.
    result = bp_11.check(_context_for("na_ambiguous"))

    assert result.rule_status == "NA"
    ambiguous = [f for f in result.findings if "contradictoires" in f.reason]
    assert len(ambiguous) == 2


def test_non_numeric_columns_are_out_of_scope_and_do_not_flip_the_status():
    # §11 : les colonnes hors périmètre numérique ne comptent pas — la
    # fixture "ok" contient une colonne texte qui ne doit pas empêcher OK.
    result = bp_11.check(_context_for("ok"))

    assert result.rule_status == "OK"
    assert result.summary["total_columns"] == 2
    assert result.summary["numeric_columns"] == 1


def test_na_when_datatype_is_absent(tmp_path):
    # §9.5 + matrice §10 : « type déclaré illisible » est un NA qui COMPTE,
    # distinct de « colonne non numérique » (hors périmètre). Cas réel des
    # colonnes de table calculée, dont le type n'est pas sérialisé.
    semantic_model = tmp_path / "T.SemanticModel"
    tables_dir = semantic_model / "definition" / "tables"
    tables_dir.mkdir(parents=True)
    (tables_dir / "P_CALC.tmdl").write_text(
        "table P_CALC\n"
        "\tlineageTag: aaaaaaaa-0000-0000-0000-000000000000\n\n"
        "\tcolumn 'P_ORDER Value'\n"
        "\t\tisHidden\n"
        "\t\tsummarizeBy: none\n"
        "\t\tsourceColumn: [Value3]\n",
        encoding="utf-8",
    )

    result = bp_11.check(AnalysisContext.from_semantic_model_path(semantic_model))

    assert result.rule_status == "NA"
    assert result.summary["na_columns"] == 1


def test_parse_type_transform_list_handles_real_world_forms():
    pairs = parse_type_transform_list(
        '{{"CAMPAIGN_ID", type text}, {"SAMPLE_SIZE", Int64.Type}}'
    )
    assert pairs == [("CAMPAIGN_ID", "type text"), ("SAMPLE_SIZE", "Int64.Type")]

    # Nom de colonne contenant une virgule et des guillemets échappés : ne
    # doit pas être coupé au mauvais endroit.
    tricky = parse_type_transform_list('{{"A, B", type text}, {"C""D", Int64.Type}}')
    assert tricky == [("A, B", "type text"), ('C"D', "Int64.Type")]

    # Forme non reconnue : aucune paire, jamais d'exception.
    assert parse_type_transform_list("MyTypeList") == []
