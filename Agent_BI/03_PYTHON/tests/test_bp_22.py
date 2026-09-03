"""Tests de non-régression pour BP-22.

Scénarios alignés sur Agent_BI/01_ALGORITHMES/22_DisableSummarization.md :
si un de ces tests doit changer, l'algorithme doit changer en premier
(cf. `agent-bi-test-generator` et `agent-bi-rule-review` dans .claude/skills/).
"""

from pathlib import Path

from engine.context import AnalysisContext
from powerbi.tmdl_parser import parse_table_file
from rules import bp_22

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "bp_22"


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


def test_to_dict_serializes_full_findings_with_evidence():
    # Un consommateur externe (API, frontend) doit pouvoir retrouver la
    # preuve complète de chaque objet sans redériver quoi que ce soit à
    # partir de ko_details/na_details.
    result = bp_22.check(_context_for("ko")).to_dict()

    assert "findings" in result
    amount_finding = next(f for f in result["findings"] if f["object"] == "F_TEST.AMOUNT")
    assert amount_finding["status"] == "KO"
    assert amount_finding["expected"] == "summarizeBy = none"
    assert amount_finding["actual"] == "sum"
    assert amount_finding["evidence"]["table"] == "F_TEST"
    assert amount_finding["evidence"]["source_file"].endswith("F_TEST.tmdl")


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
        '\t\tsourceColumn: "ID "\n',
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


def test_parser_reads_columns_when_the_file_is_indented_with_spaces(tmp_path):
    # Un fichier TMDL réel est indenté en tabulations, mais un fichier
    # réécrit à la main ou recopié depuis un éditeur/un rendu Markdown peut
    # avoir ses tabulations converties en espaces. Sans tolérance à cela, la
    # colonne n'est jamais vue : le résultat glisse silencieusement vers
    # "0 colonne évaluée" plutôt que vers une erreur visible.
    tmdl_file = tmp_path / "D_CAMPAIGNS.tmdl"
    tmdl_file.write_text(
        "table D_CAMPAIGNS\n"
        "    lineageTag: 6bfd2601-0ebf-442a-8353-f9e5f53901ab\n\n"
        "    column CAMPAIGN_ID\n"
        "        dataType: string\n"
        "        isHidden\n"
        "        lineageTag: b30938a6-aa65-4080-bd83-dd84d12c599d\n"
        "        summarizeBy: none\n"
        "        sourceColumn: CAMPAIGN_ID\n\n"
        "        changedProperty = IsHidden\n\n"
        "        annotation SummarizationSetBy = Automatic\n",
        encoding="utf-8",
    )

    table = parse_table_file(tmdl_file)

    assert table.name == "D_CAMPAIGNS"
    assert len(table.columns) == 1
    assert table.columns[0].name == "CAMPAIGN_ID"
    assert table.columns[0].get_property("summarizeBy") == "none"


def test_ok_and_ko_are_both_detected_on_a_space_indented_file(tmp_path):
    semantic_model = tmp_path / "Fixture.SemanticModel"
    tables_dir = semantic_model / "definition" / "tables"
    tables_dir.mkdir(parents=True)
    (tables_dir / "D_CONFORME.tmdl").write_text(
        "table D_CONFORME\n"
        "    lineageTag: aaaaaaaa-0000-0000-0000-000000000000\n\n"
        "    column ID\n"
        "        dataType: string\n"
        "        summarizeBy: none\n"
        "        sourceColumn: ID\n",
        encoding="utf-8",
    )
    (tables_dir / "F_NON_CONFORME.tmdl").write_text(
        "table F_NON_CONFORME\n"
        "    lineageTag: bbbbbbbb-0000-0000-0000-000000000000\n\n"
        "    column AMOUNT\n"
        "        dataType: double\n"
        "        summarizeBy: sum\n"
        "        sourceColumn: AMOUNT\n",
        encoding="utf-8",
    )

    result = bp_22.check(AnalysisContext.from_semantic_model_path(semantic_model))

    assert result.rule_status == "KO"
    assert result.summary["total_columns"] == 2
    assert result.summary["conforming_columns"] == 1
    assert result.summary["nonconforming_columns"] == 1
    assert result.summary["ko_details"] == [
        {"table": "F_NON_CONFORME", "column": "AMOUNT", "summarizeBy": "sum"},
    ]


def test_parser_returns_none_for_a_file_without_a_table_declaration(tmp_path):
    tmdl_file = tmp_path / "empty.tmdl"
    tmdl_file.write_text("", encoding="utf-8")

    assert parse_table_file(tmdl_file) is None
