"""Tests de non-régression pour BP-21.

Scénarios alignés sur Agent_BI/01_ALGORITHMES/21_ConciseNames.md, y compris
les deux anomalies réelles documentées au §3.2 (espace final, espace
interne) : si un de ces tests doit changer, l'algorithme doit changer en
premier.
"""

from pathlib import Path

from engine.context import AnalysisContext
from rules import bp_21

FIXTURES = Path(__file__).parent / "fixtures" / "bp_21"


def _context_for(scenario: str) -> AnalysisContext:
    return AnalysisContext.from_semantic_model_path(FIXTURES / scenario)


def test_ok_when_all_names_respect_the_convention():
    result = bp_21.check(_context_for("ok"))

    assert result.rule_status == "OK"
    assert result.summary["ko_objects"] == 0
    assert result.summary["total_tables"] == 1
    assert result.summary["total_columns"] == 1
    assert result.summary["total_measures"] == 1


def test_ko_reproduces_the_two_real_naming_anomalies_from_the_algorithm_doc():
    result = bp_21.check(_context_for("ko"))

    assert result.rule_status == "KO"
    reasons_by_object = {d["object_name"]: d["reason"] for d in result.summary["ko_details"]}

    assert reasons_by_object["D_CHOICE.'ID '"] == "Espace en début ou fin de nom de colonne"
    assert (
        reasons_by_object["P_EVOLUTION_LEGEND_TOP.'P_LEGEND Order'"]
        == "Espace interne dans le nom de colonne (attendu UPPER_SNAKE_CASE)"
    )


def test_ko_when_a_table_has_no_recognized_prefix():
    result = bp_21.check(_context_for("ko"))

    table_kos = [d for d in result.summary["ko_details"] if d["object_type"] == "table"]
    assert table_kos == [{
        "object_type": "table",
        "object_name": "CAMPAIGNS",
        "reason": "Préfixe de table non reconnu (attendu D_/F_/T_/P_)",
    }]


def test_ko_when_display_folder_casing_is_inconsistent_within_a_table():
    result = bp_21.check(_context_for("ko"))

    folder_kos = [d for d in result.summary["ko_details"] if d["object_type"] == "displayFolder"]
    assert len(folder_kos) == 2
    assert all("incohérente" in d["reason"] for d in folder_kos)


def test_na_when_no_tmdl_file_is_found():
    result = bp_21.check(_context_for("na"))

    assert result.rule_status == "NA"
    assert result.execution_status == "ERROR"


def test_measure_table_exemption_does_not_require_a_prefix(tmp_path):
    semantic_model = tmp_path / "T.SemanticModel"
    tables_dir = semantic_model / "definition" / "tables"
    tables_dir.mkdir(parents=True)
    (tables_dir / "MEASURE.tmdl").write_text(
        "table MEASURE\n"
        "\tlineageTag: aaaaaaaa-0000-0000-0000-000000000000\n\n"
        "\tmeasure Nb_Responses = COUNT(F_RESPONSES[ID])\n"
        "\t\tformatString: 0\n",
        encoding="utf-8",
    )

    result = bp_21.check(AnalysisContext.from_semantic_model_path(semantic_model))

    assert result.rule_status == "OK"


def test_measure_name_is_not_polluted_by_a_trailing_equals_sign(tmp_path):
    # Bug réel (AI_BAROMETER_BI-CDS.SemanticModel, 2026-08-19) : la forme
    # réelle d'une mesure DAX est `measure Nom =` avec le `=` en fin de
    # ligne et l'expression sur les lignes suivantes (jamais inline) — le
    # nom se retrouvait avec un "=" collé à la fin (`pct_Total =`), signalé
    # à tort comme non conforme.
    semantic_model = tmp_path / "T.SemanticModel"
    tables_dir = semantic_model / "definition" / "tables"
    tables_dir.mkdir(parents=True)
    (tables_dir / "MEASURE.tmdl").write_text(
        "table MEASURE\n"
        "\tlineageTag: bbbbbbbb-0000-0000-0000-000000000000\n\n"
        "\tmeasure pct_Total =\n"
        "\t\t\t\n"
        "\t\t\tVAR _x = 1\n"
        "\t\t\tRETURN _x\n"
        "\t\tformatString: 0\n",
        encoding="utf-8",
    )

    result = bp_21.check(AnalysisContext.from_semantic_model_path(semantic_model))

    assert result.rule_status == "OK"
    measure_finding = next(f for f in result.findings if f.object_type == "measure")
    assert measure_finding.object == "MEASURE.pct_Total"


def test_names_are_never_stripped_before_control(tmp_path):
    # §6 : ne jamais .strip() avant de contrôler un espace en tête/fin —
    # sinon l'anomalie elle-même disparaîtrait avant d'être détectée.
    semantic_model = tmp_path / "T.SemanticModel"
    tables_dir = semantic_model / "definition" / "tables"
    tables_dir.mkdir(parents=True)
    (tables_dir / "D_X.tmdl").write_text(
        "table 'D_X '\n"
        "\tlineageTag: bbbbbbbb-0000-0000-0000-000000000000\n\n"
        "\tcolumn CODE\n"
        "\t\tdataType: string\n"
        "\t\tsummarizeBy: none\n",
        encoding="utf-8",
    )

    result = bp_21.check(AnalysisContext.from_semantic_model_path(semantic_model))

    assert result.rule_status == "KO"
    assert result.summary["ko_details"][0]["reason"] == "Espace en début ou fin de nom de table"
