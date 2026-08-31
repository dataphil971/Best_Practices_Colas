"""Tests de non-régression pour BP-25.

Scénarios alignés sur Agent_BI/01_ALGORITHMES/25_HideTechnicalFields.md,
voie « clé de tri exclusive » (§4.1) uniquement — cf. l'avertissement de
portée en tête de rules/bp_25.py : les trois autres voies vers
`TECHNICAL_CONFIRMED` exigent une policy ou BP-24, absentes de ce dépôt.
"""

from pathlib import Path

from engine.context import AnalysisContext
from rules import bp_25

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "bp_25"


def _context_for(scenario: str) -> AnalysisContext:
    return AnalysisContext.load(FIXTURES / scenario)


def test_ok_when_an_exclusive_sort_key_is_hidden():
    result = bp_25.check(_context_for("ok"))

    assert result.rule_status == "OK"
    assert result.summary["technical_columns"] == 1
    assert result.summary["visible_technical_columns"] == 0


def test_ko_when_an_exclusive_sort_key_is_left_visible():
    result = bp_25.check(_context_for("ko"))

    assert result.rule_status == "KO"
    assert result.summary["visible_technical_columns"] == 1
    ko = result.findings and next(f for f in result.findings if f.status == "KO")
    assert ko.evidence["role"] == "TECHNICAL_CONFIRMED"
    assert "tri exclusive" in ko.evidence["role_evidence"]


def test_a_sort_key_also_used_elsewhere_is_not_declared_technical(tmp_path):
    # §4.3/§5 : un autre usage (ici une relation) empêche de démontrer que la
    # colonne est PUREMENT technique — UNKNOWN, donc NA, jamais KO.
    tables = tmp_path / "M.SemanticModel" / "definition" / "tables"
    tables.mkdir(parents=True)
    (tables / "D_L.tmdl").write_text(
        "table D_L\n\tlineageTag: l\n\n"
        "\tcolumn LIBELLE\n\t\tdataType: string\n\t\tsortByColumn: ORDRE\n\n"
        "\tcolumn ORDRE\n\t\tdataType: int64\n",
        encoding="utf-8",
    )
    (tmp_path / "M.SemanticModel" / "definition" / "relationships.tmdl").write_text(
        "relationship r1\n\tfromColumn: F_A.ORDRE\n\ttoColumn: D_L.ORDRE\n",
        encoding="utf-8",
    )
    page = tmp_path / "R.Report" / "definition" / "pages" / "p1"
    page.mkdir(parents=True)
    (page / "page.json").write_text('{"name":"p1"}', encoding="utf-8")

    result = bp_25.check(AnalysisContext.load(tmp_path))

    assert result.summary["technical_columns"] == 0
    assert result.rule_status == "NA"


def test_a_column_used_in_the_report_is_never_declared_technical(tmp_path):
    # §6 : usage utilisateur direct -> BUSINESS_OR_USER_FACING -> NA.
    tables = tmp_path / "M.SemanticModel" / "definition" / "tables"
    tables.mkdir(parents=True)
    (tables / "D_L.tmdl").write_text(
        "table D_L\n\tlineageTag: l\n\n"
        "\tcolumn LIBELLE\n\t\tdataType: string\n\t\tsortByColumn: ORDRE\n\n"
        "\tcolumn ORDRE\n\t\tdataType: int64\n",
        encoding="utf-8",
    )
    page = tmp_path / "R.Report" / "definition" / "pages" / "p1"
    page.mkdir(parents=True)
    (page / "page.json").write_text(
        '{"name":"p1","filterConfig":{"filters":[{"name":"f","type":"Categorical",'
        '"field":{"Column":{"Expression":{"SourceRef":{"Entity":"D_L"}},'
        '"Property":"ORDRE"}}}]}}',
        encoding="utf-8",
    )

    result = bp_25.check(AnalysisContext.load(tmp_path))

    assert result.summary["technical_columns"] == 0
    assert result.rule_status == "NA"


def test_na_when_the_report_is_absent_from_the_scope():
    # Sans rapport, l'absence d'usage utilisateur n'est pas démontrable.
    context = AnalysisContext.from_semantic_model_path(FIXTURES / "ko" / "M.SemanticModel")
    result = bp_25.check(context)

    assert result.rule_status == "NA"
    assert result.execution_status == "PARTIAL"
    assert result.summary["visible_technical_columns"] == 0
