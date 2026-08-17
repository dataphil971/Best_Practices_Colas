"""Tests de non-régression pour BP-22.

Scénarios alignés sur Agent_BI/01_ALGORITHMES/22_DisableSummarization.md :
si un de ces tests doit changer, l'algorithme doit changer en premier
(cf. `agent-bi-test-generator` et `agent-bi-rule-review` dans .github/skills/).
"""

from pathlib import Path

from engine.context import AnalysisContext
from powerbi.tmdl_parser import parse_table_file
from rules import bp_22

FIXTURES = Path(__file__).parent / "fixtures" / "bp_22"


def _context_for(scenario: str) -> AnalysisContext:
    return AnalysisContext.from_semantic_model_path(FIXTURES / scenario)


def test_ok_when_all_columns_summarize_by_none():
    result = bp_22.check(_context_for("ok"))

    assert result.rule_status == "OK"
    assert result.execution_status == "SUCCESS"
    assert result.summary["total_columns"] == 2
    assert result.summary["conforming_columns"] == 2
    assert result.summary["nonconforming_columns"] == 0
    assert result.summary["na_columns"] == 0


def test_ok_is_case_insensitive_and_trims_whitespace():
    # TEST_LABEL porte `summarizeBy: None` (majuscule) dans la fixture "ok" :
    # doit être traité comme conforme, cf. §7 Normalisation de l'algorithme.
    result = bp_22.check(_context_for("ok"))

    label_finding = next(f for f in result.findings if f.object.endswith("TEST_LABEL"))
    assert label_finding.status == "OK"


def test_ko_when_a_column_has_a_non_none_aggregation():
    result = bp_22.check(_context_for("ko"))

    assert result.rule_status == "KO"
    assert result.execution_status == "SUCCESS"
    assert result.summary["nonconforming_columns"] == 1
    assert result.summary["ko_details"] == [
        {"table": "F_TEST", "column": "AMOUNT", "summarizeBy": "sum"},
    ]


def test_na_when_summarize_by_is_missing_or_unreadable():
    result = bp_22.check(_context_for("na"))

    assert result.rule_status == "NA"
    assert result.execution_status == "PARTIAL"
    assert result.summary["nonconforming_columns"] == 0
    assert result.summary["na_columns"] == 2


def test_na_when_no_tmdl_file_is_found(tmp_path):
    empty_semantic_model = tmp_path / "Empty.SemanticModel"
    (empty_semantic_model / "definition" / "tables").mkdir(parents=True)

    result = bp_22.check(AnalysisContext.from_semantic_model_path(empty_semantic_model))

    assert result.rule_status == "NA"
    assert result.execution_status == "ERROR"
    assert result.findings == []


def test_parser_preserves_leading_and_trailing_whitespace_in_column_names(tmp_path):
    # Reproduit l'anomalie réelle documentée dans BP-21 : D_CHOICE.'ID '
    # (espace final dans le nom technique de la colonne).
    tmdl_file = tmp_path / "D_CHOICE.tmdl"
    tmdl_file.write_text(
        "table D_CHOICE\n"
        "\tlineageTag: aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa\n\n"
        "\tcolumn 'ID '\n"
        "\t\tdataType: int64\n"
        "\t\tsummarizeBy: none\n"
        "\t\tsourceColumn: \"ID \"\n",
        encoding="utf-8",
    )

    table = parse_table_file(tmdl_file)

    assert table.name == "D_CHOICE"
    assert table.columns[0].name == "ID "
    assert table.columns[0].raw_name == "'ID '"
    assert table.columns[0].get_property("summarizeBy") == "none"


def test_parser_ignores_measure_blocks(tmp_path):
    tmdl_file = tmp_path / "MEASURE.tmdl"
    tmdl_file.write_text(
        "table MEASURE\n"
        "\tlineageTag: bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb\n\n"
        "\tmeasure Nb_Responses = COUNT(F_RESPONSES[ID])\n"
        "\t\tformatString: 0\n"
        "\t\tdisplayFolder: STATS\n"
        "\t\tlineageTag: cccccccc-cccc-cccc-cccc-cccccccccccc\n",
        encoding="utf-8",
    )

    table = parse_table_file(tmdl_file)

    assert table.name == "MEASURE"
    assert table.columns == []


def test_parser_returns_none_for_a_file_without_a_table_declaration(tmp_path):
    tmdl_file = tmp_path / "empty.tmdl"
    tmdl_file.write_text("", encoding="utf-8")

    assert parse_table_file(tmdl_file) is None
