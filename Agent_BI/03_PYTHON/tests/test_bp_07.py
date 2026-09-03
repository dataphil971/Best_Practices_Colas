"""Tests de non-régression pour BP-07.

Scénarios alignés sur Agent_BI/01_ALGORITHMES/07_RemoveUnusedFields.md :
si un de ces tests doit changer, l'algorithme doit changer en premier.

Les fixtures sont des projets PBIP COMPLETS (`.SemanticModel` + `.Report`) :
sans rapport, la règle ne peut produire aucun KO (§9), c'est précisément ce
que vérifie `test_na_when_the_report_is_absent_from_the_analysed_scope`.
"""

from pathlib import Path

from engine.context import AnalysisContext
from powerbi.dax_lang import extract_column_references
from rules import bp_07

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "bp_07"


def test_ko_only_for_a_visible_column_with_no_usage_anywhere():
    result = bp_07.check(AnalysisContext.load(FIXTURES / "ko"))

    assert result.rule_status == "KO"
    unused = {(d["table"], d["column"]) for d in result.summary["ko_details"]}
    assert ("D_X", "INUTILISEE") in unused
    # Une colonne utilisée dans le rapport ou en DAX qualifié n'est jamais KO.
    assert ("D_X", "UTILISEE_RAPPORT") not in unused
    assert ("D_X", "UTILISEE_DAX") not in unused


def test_hidden_columns_are_out_of_scope_and_never_ko():
    # §10 : la bonne pratique cible les colonnes VISIBLES.
    result = bp_07.check(AnalysisContext.load(FIXTURES / "ko"))

    unused = {(d["table"], d["column"]) for d in result.summary["ko_details"]}
    assert ("D_X", "MASQUEE_INUTILISEE") not in unused
    assert result.summary["hidden_columns"] == 1


def test_a_column_named_only_inside_a_dax_comment_is_not_considered_used():
    # Sans neutralisation des commentaires, `CITEE_EN_COMMENTAIRE` passerait
    # pour utilisée et la règle raterait une vraie colonne morte.
    result = bp_07.check(AnalysisContext.load(FIXTURES / "ko"))

    unused = {(d["table"], d["column"]) for d in result.summary["ko_details"]}
    assert ("D_X", "CITEE_EN_COMMENTAIRE") in unused


def test_na_when_the_report_is_absent_from_the_analysed_scope():
    # §9 : sans rapport lisible, l'absence d'usage n'est pas démontrable —
    # garde principale contre les faux positifs.
    context = AnalysisContext.from_semantic_model_path(FIXTURES / "ko" / "M.SemanticModel")
    result = bp_07.check(context)

    assert result.rule_status == "NA"
    assert result.execution_status == "PARTIAL"
    assert result.summary["unused_columns"] == 0
    assert result.summary["coverage"]["report"] is False


def test_usage_scope_is_reported_as_current_pbip_only():
    # §2 : ne jamais affirmer « inutilisée partout ».
    result = bp_07.check(AnalysisContext.load(FIXTURES / "ko"))

    assert result.summary["usage_scope"] == "CURRENT_PBIP"


def test_an_unqualified_dax_reference_blocks_the_ko_for_a_same_named_column(tmp_path):
    # §7 : `[X]` ne doit jamais être attribué arbitrairement — mais il doit
    # empêcher de conclure « inutilisée » pour toute colonne nommée X.
    tables = tmp_path / "M.SemanticModel" / "definition" / "tables"
    tables.mkdir(parents=True)
    (tables / "D_Y.tmdl").write_text(
        "table D_Y\n\tlineageTag: y\n\n"
        "\tcolumn AMBIGUE\n\t\tdataType: string\n\t\tsummarizeBy: none\n\n"
        "\tmeasure M1 =\n\t\t\tSUMX(D_Y, [AMBIGUE])\n",
        encoding="utf-8",
    )
    report = tmp_path / "R.Report" / "definition" / "pages" / "p1"
    report.mkdir(parents=True)
    (report / "page.json").write_text('{"name":"p1"}', encoding="utf-8")

    result = bp_07.check(AnalysisContext.load(tmp_path))

    assert result.summary["unused_columns"] == 0
    blocked = next(f for f in result.findings if f.object == "D_Y.AMBIGUE")
    assert blocked.status == "NA"
    assert "non qualifiée" in blocked.reason


def test_relationship_and_sort_by_columns_count_as_usage(tmp_path):
    tables = tmp_path / "M.SemanticModel" / "definition" / "tables"
    tables.mkdir(parents=True)
    (tables / "D_Z.tmdl").write_text(
        "table D_Z\n\tlineageTag: z\n\n"
        "\tcolumn CLE\n\t\tdataType: int64\n\t\tsummarizeBy: none\n\n"
        "\tcolumn LIBELLE\n\t\tdataType: string\n\t\tsummarizeBy: none\n"
        "\t\tsortByColumn: ORDRE\n\n"
        "\tcolumn ORDRE\n\t\tdataType: int64\n\t\tsummarizeBy: none\n",
        encoding="utf-8",
    )
    (tmp_path / "M.SemanticModel" / "definition" / "relationships.tmdl").write_text(
        "relationship r1\n\tfromColumn: F_A.CLE\n\ttoColumn: D_Z.CLE\n",
        encoding="utf-8",
    )
    report = tmp_path / "R.Report" / "definition" / "pages" / "p1"
    report.mkdir(parents=True)
    (report / "page.json").write_text(
        '{"name":"p1","filterConfig":{"filters":[{"name":"f","type":"Categorical",'
        '"field":{"Column":{"Expression":{"SourceRef":{"Entity":"D_Z"}},'
        '"Property":"LIBELLE"}}}]}}',
        encoding="utf-8",
    )

    result = bp_07.check(AnalysisContext.load(tmp_path))

    assert result.rule_status == "OK"
    assert result.summary["unused_columns"] == 0


def test_dax_extractor_separates_qualified_from_unqualified_references():
    qualified, unqualified = extract_column_references(
        "SUM(F_VENTES[MONTANT]) + SUMX('Ma Table'[Qte], [Mesure])"
    )

    assert ("F_VENTES", "MONTANT") in qualified
    assert ("Ma Table", "Qte") in qualified
    assert unqualified == {"Mesure"}


def test_dax_extractor_ignores_comments_and_string_literals():
    qualified, unqualified = extract_column_references(
        '// D_X[COMMENTAIRE]\n/* D_X[BLOC] */\nVAR t = "D_X[CHAINE]"\nRETURN SUM(D_X[REEL])'
    )

    assert qualified == {("D_X", "REEL")}
    assert unqualified == set()
