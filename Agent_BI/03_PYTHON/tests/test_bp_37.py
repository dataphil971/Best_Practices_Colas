"""Tests de non-régression pour BP-37.

Scénarios alignés sur Agent_BI/01_ALGORITHMES/37_OrganizeVisualsBookmarks.md,
sous-contrôle STRUCTUREL uniquement (cf. l'avertissement de portée en tête de
rules/bp_37.py : le nommage exige une policy absente de ce dépôt).
"""

from pathlib import Path

from engine.context import AnalysisContext
from rules import bp_37

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "bp_37"


def _context_for(scenario: str) -> AnalysisContext:
    return AnalysisContext.load(FIXTURES / scenario)


def test_ok_when_group_and_bookmark_references_all_resolve():
    result = bp_37.check(_context_for("ok"))

    assert result.rule_status == "OK"
    assert result.summary["broken_group_references"] == 0
    assert result.summary["broken_bookmark_references"] == 0


def test_ko_when_parent_group_name_points_to_a_missing_group():
    result = bp_37.check(_context_for("ko_group"))

    assert result.rule_status == "KO"
    assert result.summary["broken_group_references"] == 1
    ko = result.summary["ko_details"][0]
    assert ko["actual"] == "GROUPE_INEXISTANT"


def test_ko_when_bookmarks_metadata_references_a_missing_bookmark():
    result = bp_37.check(_context_for("ko_bookmark"))

    assert result.rule_status == "KO"
    assert result.summary["broken_bookmark_references"] == 1


def test_na_when_no_report_is_available():
    context = AnalysisContext.from_semantic_model_path(FIXTURES / "ok" / "M.SemanticModel")
    result = bp_37.check(context)

    assert result.rule_status == "NA"
    assert result.execution_status == "PARTIAL"


def test_ko_when_the_bookmark_hierarchy_contains_a_cycle(tmp_path):
    # §6.3 : les cycles de hiérarchie sont une incohérence structurelle.
    (tmp_path / "M.SemanticModel" / "definition" / "tables").mkdir(parents=True)
    bookmarks = tmp_path / "R.Report" / "definition" / "bookmarks"
    bookmarks.mkdir(parents=True)
    (bookmarks / "bookmarks.json").write_text(
        '{"items":[{"name":"a","children":["b"]},{"name":"b","children":["a"]}]}',
        encoding="utf-8",
    )

    result = bp_37.check(AnalysisContext.load(tmp_path))

    assert result.rule_status == "KO"
    assert any("Cycle" in f.reason for f in result.findings if f.status == "KO")


def test_na_when_bookmark_files_exist_without_metadata(tmp_path):
    # §7 : ne jamais supposer la hiérarchie quand bookmarks.json manque.
    (tmp_path / "M.SemanticModel" / "definition" / "tables").mkdir(parents=True)
    bookmarks = tmp_path / "R.Report" / "definition" / "bookmarks"
    bookmarks.mkdir(parents=True)
    (bookmarks / "bk1.bookmark.json").write_text('{"name":"bk1","displayName":"S1"}', encoding="utf-8")

    result = bp_37.check(AnalysisContext.load(tmp_path))

    assert result.rule_status == "NA"


def test_ungrouped_visuals_never_produce_a_ko(tmp_path):
    # §5 : le nombre de visuels non groupés est un diagnostic, jamais un KO.
    (tmp_path / "M.SemanticModel" / "definition" / "tables").mkdir(parents=True)
    visuals = tmp_path / "R.Report" / "definition" / "pages" / "p1" / "visuals"
    for i in range(8):
        d = visuals / f"v{i}"
        d.mkdir(parents=True)
        (d / "visual.json").write_text(
            f'{{"name":"v{i}","visual":{{"visualType":"card"}}}}', encoding="utf-8"
        )

    result = bp_37.check(AnalysisContext.load(tmp_path))

    assert result.rule_status != "KO"
