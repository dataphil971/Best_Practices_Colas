"""Tests de non-régression pour BP-15.

Scénarios alignés sur Agent_BI/01_ALGORITHMES/15_QueryFolding.md (branches
statiques uniquement — aucune preuve runtime disponible dans ce dépôt).

Le format des blocs `partition`/`source =` et des `expression` de
`expressions.tmdl` a été confirmé contre un export PBIP réel
(AI_BAROMETER_BI-CDS.SemanticModel, 2026-08-19) — cf. `test_bp_17.py` pour
l'avertissement équivalent côté `partition` seule.
"""

from pathlib import Path

from engine.context import AnalysisContext
from rules import bp_15

FIXTURES = Path(__file__).parent / "fixtures" / "bp_15"


def _context_for(scenario: str) -> AnalysisContext:
    return AnalysisContext.from_semantic_model_path(FIXTURES / scenario)


def test_ok_when_no_transformation_after_source_navigation():
    result = bp_15.check(_context_for("ok_no_transform"))

    assert result.rule_status == "OK"
    assert result.findings[0].actual == "aucune transformation"


def test_ok_for_native_query_with_no_downstream_steps():
    result = bp_15.check(_context_for("ok_native_no_downstream"))

    assert result.rule_status == "OK"
    assert "Value.NativeQuery" in result.findings[0].actual


def test_ko_when_table_buffer_precedes_later_steps():
    result = bp_15.check(_context_for("ko_buffer"))

    assert result.rule_status == "KO"
    assert result.summary["ko_details"][0]["actual"] == "Table.Buffer"


def test_ko_when_native_query_has_downstream_steps_without_enable_folding():
    result = bp_15.check(_context_for("ko_native_no_enable_folding"))

    assert result.rule_status == "KO"
    reason = result.summary["ko_details"][0]["reason"]
    assert "EnableFolding" in reason


def test_na_out_of_scope_for_a_non_foldable_source():
    # Un connecteur fichier ne doit jamais faire basculer le statut global
    # (§4 et §11 : NOT_APPLICABLE est hors périmètre, pas une preuve KO/NA).
    result = bp_15.check(_context_for("na_not_applicable"))

    assert result.rule_status == "NA"
    assert result.summary["evaluated_partitions"] == 0


def test_na_when_no_runtime_proof_is_available_for_a_heavy_transform():
    # Transformation présente sur une source foldable, mais sans preuve
    # runtime ni rupture explicite : le document interdit de fabriquer un
    # OK ou un KO sur cette seule base statique.
    result = bp_15.check(_context_for("na_no_runtime_proof"))

    assert result.rule_status == "NA"


def test_ko_status_prevails_even_with_other_out_of_scope_partitions(tmp_path):
    # Une partition NON_FOLDABLE à côté d'une rupture explicite ne doit pas
    # diluer le KO (§11 : seuls les constats évaluables comptent).
    semantic_model = tmp_path / "T.SemanticModel"
    tables_dir = semantic_model / "definition" / "tables"
    tables_dir.mkdir(parents=True)
    (tables_dir / "D_CSV.tmdl").write_text(
        "table D_CSV\n"
        "\tlineageTag: aaaaaaaa-0000-0000-0000-000000000000\n\n"
        "\tpartition D_CSV = m\n"
        "\t\tmode: import\n"
        "\t\tsource =\n"
        "\t\t\t\tlet\n"
        "\t\t\t\t\tSource = Csv.Document(File.Contents(\"x.csv\"), [])\n"
        "\t\t\t\tin\n"
        "\t\t\t\t\tSource\n",
        encoding="utf-8",
    )
    (tables_dir / "F_A.tmdl").write_text(
        "table F_A\n"
        "\tlineageTag: bbbbbbbb-0000-0000-0000-000000000000\n\n"
        "\tpartition F_A = m\n"
        "\t\tmode: import\n"
        "\t\tsource =\n"
        "\t\t\t\tlet\n"
        "\t\t\t\t\tSource = Sql.Database(\"s\", \"d\"),\n"
        "\t\t\t\t\tStopped = Table.StopFolding(Source),\n"
        "\t\t\t\t\tFiltered = Table.SelectRows(Stopped, each [X] > 0)\n"
        "\t\t\t\tin\n"
        "\t\t\t\t\tFiltered\n",
        encoding="utf-8",
    )

    result = bp_15.check(AnalysisContext.from_semantic_model_path(semantic_model))

    assert result.rule_status == "KO"
    assert result.summary["evaluated_partitions"] == 1


def test_na_when_partition_has_no_m_code(tmp_path):
    semantic_model = tmp_path / "T.SemanticModel"
    tables_dir = semantic_model / "definition" / "tables"
    tables_dir.mkdir(parents=True)
    (tables_dir / "F_CALC.tmdl").write_text(
        "table F_CALC\n"
        "\tlineageTag: cccccccc-0000-0000-0000-000000000000\n\n"
        "\tpartition F_CALC = calculated\n"
        "\t\tmode: import\n"
        "\t\tsource = F_A\n",
        encoding="utf-8",
    )

    result = bp_15.check(AnalysisContext.from_semantic_model_path(semantic_model))

    assert result.rule_status == "NA"


def test_ok_for_a_shared_expression_reachable_only_through_expressions_tmdl():
    # Bug réel (AI_BAROMETER_BI-CDS.SemanticModel, 2026-08-19) : une requête
    # partagée (definition/expressions.tmdl) référencée par une autre requête
    # mais jamais chargée directement dans une table était invisible pour
    # cette règle. La fixture reproduit le format confirmé (délimiteur
    # ``` pour une expression contenant une chaîne SQL multi-lignes).
    result = bp_15.check(_context_for("ok_shared_expression"))

    assert result.rule_status == "OK"
    assert result.findings[0].object_type == "expression"
    assert result.findings[0].object == "D_STRUCTURES"


def test_comments_before_each_step_do_not_hide_them(tmp_path):
    # Bug réel : un `//` en tête d'étape (convention BP-35 : commenter
    # chaque étape complexe) faisait échouer `parse_let_steps` sur TOUTES
    # les étapes du fichier, pas seulement la commentée.
    semantic_model = tmp_path / "T.SemanticModel"
    tables_dir = semantic_model / "definition" / "tables"
    tables_dir.mkdir(parents=True)
    (tables_dir / "F_X.tmdl").write_text(
        "table F_X\n"
        "\tlineageTag: dddddddd-0000-0000-0000-000000000000\n\n"
        "\tpartition F_X = m\n"
        "\t\tmode: import\n"
        "\t\tsource =\n"
        "\t\t\t\tlet\n"
        "\t\t\t\t    // Charge la source\n"
        "\t\t\t\t    Source = Sql.Database(\"s\", \"d\"),\n"
        "\t\t\t\t    /* filtre les lignes invalides */\n"
        "\t\t\t\t    Filtered = Table.SelectRows(Source, each [X] <> null),\n"
        "\t\t\t\t    Buffered = Table.Buffer(Filtered),\n"
        "\t\t\t\t    // rupture volontaire pour ce test\n"
        "\t\t\t\t    Final = Table.SelectRows(Buffered, each [Y] > 0)\n"
        "\t\t\t\tin\n"
        "\t\t\t\t    Final\n",
        encoding="utf-8",
    )

    result = bp_15.check(AnalysisContext.from_semantic_model_path(semantic_model))

    # Sans le retrait des commentaires, aucune étape n'était reconnue ->
    # "Code M non interprétable" (NA), jamais ce KO.
    assert result.rule_status == "KO"
    assert result.summary["ko_details"][0]["actual"] == "Table.Buffer"
