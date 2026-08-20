"""Tests de non-régression pour BP-32.

Scénarios alignés sur Agent_BI/01_ALGORITHMES/32_ExplicitMeasures.md :
si un de ces tests doit changer, l'algorithme doit changer en premier.
"""

from pathlib import Path

from engine.context import AnalysisContext
from rules import bp_32

FIXTURES = Path(__file__).parent / "fixtures" / "bp_32"


def _context_for(scenario: str) -> AnalysisContext:
    return AnalysisContext.load(FIXTURES / scenario)


def test_ko_when_an_aggregation_is_applied_to_a_column():
    # §3 : signature déterministe d'une mesure implicite.
    result = bp_32.check(_context_for("ko"))

    assert result.rule_status == "KO"
    assert result.summary["implicit_aggregation_count"] == 1
    ko = result.summary["ko_details"][0]
    assert ko["evidence"]["table"] == "F_V"
    assert ko["evidence"]["column"] == "MONTANT"


def test_ok_when_only_measures_and_bare_columns_are_projected():
    # §5 : une colonne SANS nœud Aggregation est neutre (axe, slicer,
    # ligne de tableau) — elle ne doit jamais produire de KO, même dans une
    # zone nommée `Y` ou `Values`.
    result = bp_32.check(_context_for("ok"))

    assert result.rule_status == "OK"
    assert result.summary["implicit_aggregation_count"] == 0


def test_na_when_no_report_is_available():
    # §9 : OK n'est permis que si la couverture de parsing est complète.
    context = AnalysisContext.from_semantic_model_path(
        FIXTURES / "ok" / "M.SemanticModel"
    )
    result = bp_32.check(context)

    assert result.rule_status == "NA"
    assert result.execution_status == "PARTIAL"


def test_na_when_an_aggregation_targets_something_other_than_a_column(tmp_path):
    # §6 : `UNKNOWN_AGGREGATION` — ne prouve rien, mais empêche de conclure OK.
    (tmp_path / "M.SemanticModel" / "definition" / "tables").mkdir(parents=True)
    visual = tmp_path / "R.Report" / "definition" / "pages" / "p1" / "visuals" / "v1"
    visual.mkdir(parents=True)
    (visual / "visual.json").write_text(
        '{"name":"v1","visual":{"visualType":"card","query":{"queryState":{"Y":'
        '{"projections":[{"field":{"Aggregation":{"Expression":'
        '{"SomethingElse":{"Foo":1}},"Function":0}}}]}}}}}',
        encoding="utf-8",
    )

    result = bp_32.check(AnalysisContext.load(tmp_path))

    assert result.rule_status == "NA"
    assert result.summary["unresolved_aggregation_count"] == 1
    assert result.summary["implicit_aggregation_count"] == 0


def test_each_aggregation_node_is_counted_once(tmp_path):
    # §6 : « Le parser doit éviter de compter deux fois le même nœud. »
    (tmp_path / "M.SemanticModel" / "definition" / "tables").mkdir(parents=True)
    visual = tmp_path / "R.Report" / "definition" / "pages" / "p1" / "visuals" / "v1"
    visual.mkdir(parents=True)
    (visual / "visual.json").write_text(
        '{"name":"v1","visual":{"visualType":"barChart","query":{"queryState":{"Y":'
        '{"projections":[{"field":{"Aggregation":{"Expression":{"Column":'
        '{"Expression":{"SourceRef":{"Entity":"F_V"}},"Property":"MONTANT"}},'
        '"Function":0}}}]}}}}}',
        encoding="utf-8",
    )

    result = bp_32.check(AnalysisContext.load(tmp_path))

    assert result.summary["implicit_aggregation_count"] == 1
