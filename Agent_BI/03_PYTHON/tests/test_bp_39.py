"""Tests de non-régression pour BP-39.

Scénarios alignés sur Agent_BI/01_ALGORITHMES/39_ConfigAndTestFilters.md,
sous-contrôle « validation des références » uniquement (cf. l'avertissement
de portée en tête de rules/bp_39.py — la détection de contradictions exige
un solveur non implémenté).

Ces fixtures sont des projets PBIP COMPLETS (`.SemanticModel` + `.Report`)
et se chargent donc via `AnalysisContext.load`, pas via
`from_semantic_model_path` : le rapport vit à côté du modèle, jamais dedans.
"""

from pathlib import Path

from engine.context import AnalysisContext
from rules import bp_39

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "bp_39"


def _context_for(scenario: str) -> AnalysisContext:
    return AnalysisContext.load(FIXTURES / scenario)


def test_ok_when_every_filter_references_an_existing_object():
    result = bp_39.check(_context_for("ok"))

    assert result.rule_status == "OK"
    assert result.summary["total_filters"] == 1
    assert result.summary["broken_filters"] == 0


def test_ko_when_a_filter_references_a_column_absent_from_the_model():
    # Défaut réel trouvé sur AI_BAROMETER_BI-CDS : deux filtres de page
    # pointent vers F_RESPONSES[CAMPAIGN_SHORT_LABEL], colonne qui n'existe
    # que dans D_CAMPAIGNS.
    result = bp_39.check(_context_for("ko"))

    assert result.rule_status == "KO"
    assert result.summary["broken_filters"] == 1
    ko = result.summary["ko_details"][0]
    assert ko["evidence"]["missing_references"][0]["entity"] == "F_RESPONSES"
    assert ko["evidence"]["model_coverage_complete"] is True


def test_na_when_the_project_has_no_report_folder():
    # Contexte construit depuis le seul `.SemanticModel` : aucun rapport
    # atteignable — NA (« rien à analyser »), jamais OK.
    context = AnalysisContext.from_semantic_model_path(FIXTURES / "ok" / "Modele.SemanticModel")
    result = bp_39.check(context)

    assert result.rule_status == "NA"
    assert result.summary["total_filters"] == 0


def test_na_when_the_model_has_no_table(tmp_path):
    # §3 : sans couverture modèle, l'absence d'un objet ne prouve rien.
    (tmp_path / "M.SemanticModel" / "definition" / "tables").mkdir(parents=True)
    result = bp_39.check(AnalysisContext.load(tmp_path))

    assert result.rule_status == "NA"
    assert result.execution_status == "ERROR"


def test_na_when_a_filter_field_cannot_be_resolved(tmp_path):
    # §4 : une construction PBIR non supportée ne doit jamais être traitée
    # comme un filtre cassé.
    tables = tmp_path / "M.SemanticModel" / "definition" / "tables"
    tables.mkdir(parents=True)
    (tables / "D_X.tmdl").write_text(
        "table D_X\n\tlineageTag: x\n\n\tcolumn A\n\t\tdataType: string\n",
        encoding="utf-8",
    )
    page = tmp_path / "R.Report" / "definition" / "pages" / "p1"
    page.mkdir(parents=True)
    (page / "page.json").write_text(
        '{"name":"p1","filterConfig":{"filters":['
        '{"name":"f1","type":"Advanced","field":{"UnsupportedConstruct":{"Foo":1}}}'
        "]}}",
        encoding="utf-8",
    )

    result = bp_39.check(AnalysisContext.load(tmp_path))

    assert result.rule_status == "NA"
    assert result.summary["broken_filters"] == 0


def test_measure_references_are_resolved_against_measures_not_columns(tmp_path):
    tables = tmp_path / "M.SemanticModel" / "definition" / "tables"
    tables.mkdir(parents=True)
    (tables / "MEASURE.tmdl").write_text(
        "table MEASURE\n\tlineageTag: m\n\n\tmeasure Nb_Total =\n\t\t\tCOUNTROWS(D_X)\n",
        encoding="utf-8",
    )
    page = tmp_path / "R.Report" / "definition" / "pages" / "p1"
    page.mkdir(parents=True)
    (page / "page.json").write_text(
        '{"name":"p1","filterConfig":{"filters":['
        '{"name":"f1","type":"Advanced","field":{"Measure":{"Expression":'
        '{"SourceRef":{"Entity":"MEASURE"}},"Property":"Nb_Total"}}}'
        "]}}",
        encoding="utf-8",
    )

    result = bp_39.check(AnalysisContext.load(tmp_path))

    assert result.rule_status == "OK"
