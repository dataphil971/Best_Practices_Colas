"""Tests de non-régression pour BP-17.

Scénarios alignés sur Agent_BI/01_ALGORITHMES/17_DatabricksEndpoint.md.

Le format des blocs `partition`/`source =` a été confirmé contre un export
PBIP réel (AI_BAROMETER_BI-CDS.SemanticModel, 2026-08-19). Reste non vérifié
sur du réel : le motif regex `COMPUTE_CLUSTER_PATH` (aucun exemple de
compute cluster interactif observé sur ce projet, qui n'utilise Databricks
qu'en mode import via `Value.NativeQuery` — jamais en DirectQuery).
"""

from pathlib import Path

from engine.context import AnalysisContext
from rules import bp_17

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "bp_17"


def _context_for(scenario: str) -> AnalysisContext:
    return AnalysisContext.from_semantic_model_path(FIXTURES / scenario)


def test_ok_for_a_sql_warehouse_endpoint():
    result = bp_17.check(_context_for("ok"))

    assert result.rule_status == "OK"
    assert result.findings[0].actual == "SQL_WAREHOUSE"


def test_ko_for_a_compute_cluster_endpoint():
    result = bp_17.check(_context_for("ko"))

    assert result.rule_status == "KO"
    assert result.summary["ko_details"][0]["actual"] == "COMPUTE_CLUSTER"


def test_na_for_an_import_partition_out_of_scope():
    result = bp_17.check(_context_for("na_import"))

    assert result.rule_status == "NA"
    assert result.summary["evaluated_partitions"] == 0


def test_na_when_http_path_is_a_parameter_not_a_literal():
    # Le checker ne doit jamais deviner la valeur d'un paramètre — cf. §5 de
    # l'algorithme, résolution non garantie sans `m_constant_resolver`.
    result = bp_17.check(_context_for("na_unresolved"))

    assert result.rule_status == "NA"
    assert "non résolvable" in result.findings[0].reason


def test_na_when_partition_is_directquery_but_not_databricks(tmp_path):
    semantic_model = tmp_path / "T.SemanticModel"
    tables_dir = semantic_model / "definition" / "tables"
    tables_dir.mkdir(parents=True)
    (tables_dir / "F_X.tmdl").write_text(
        "table F_X\n"
        "\tlineageTag: aaaaaaaa-0000-0000-0000-000000000000\n\n"
        "\tpartition F_X = m\n"
        "\t\tmode: directQuery\n"
        "\t\tsource =\n"
        "\t\t\t\tlet\n"
        '\t\t\t\t\tSource = Sql.Database("server", "db")\n'
        "\t\t\t\tin\n"
        "\t\t\t\t\tSource\n",
        encoding="utf-8",
    )

    result = bp_17.check(AnalysisContext.from_semantic_model_path(semantic_model))

    assert result.rule_status == "NA"
    assert result.summary["evaluated_partitions"] == 0


def test_na_when_no_partition_exists_at_all(tmp_path):
    semantic_model = tmp_path / "T.SemanticModel"
    tables_dir = semantic_model / "definition" / "tables"
    tables_dir.mkdir(parents=True)
    (tables_dir / "D_CALCULEE.tmdl").write_text(
        "table D_CALCULEE\n"
        "\tlineageTag: cccccccc-0000-0000-0000-000000000000\n\n"
        "\tcolumn ID\n"
        "\t\tdataType: string\n"
        "\t\tsummarizeBy: none\n",
        encoding="utf-8",
    )

    result = bp_17.check(AnalysisContext.from_semantic_model_path(semantic_model))

    assert result.rule_status == "NA"
    assert result.summary["total_partitions"] == 0


def test_unquotes_the_http_path_before_classification(tmp_path):
    semantic_model = tmp_path / "T.SemanticModel"
    tables_dir = semantic_model / "definition" / "tables"
    tables_dir.mkdir(parents=True)
    (tables_dir / "F_X.tmdl").write_text(
        "table F_X\n"
        "\tlineageTag: bbbbbbbb-0000-0000-0000-000000000000\n\n"
        "\tpartition F_X = m\n"
        "\t\tmode: directQuery\n"
        "\t\tsource =\n"
        "\t\t\t\tlet\n"
        '\t\t\t\t\tSource = Databricks.Catalogs("host", "/sql/1.0/warehouses/XYZ", [])\n'
        "\t\t\t\tin\n"
        "\t\t\t\t\tSource\n",
        encoding="utf-8",
    )

    result = bp_17.check(AnalysisContext.from_semantic_model_path(semantic_model))

    assert result.rule_status == "OK"
    assert result.findings[0].evidence["http_path"] == "/sql/1.0/warehouses/XYZ"
