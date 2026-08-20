"""Tests de l'EXPLICABILITÉ des constats : localisation, extrait, remédiation.

Ce que ces tests protègent : un utilisateur (ou un assistant IA) doit pouvoir
comprendre et corriger un KO sans rouvrir le projet. Une régression sur les
numéros de ligne est silencieuse — le moteur continue de trouver les bons
défauts, mais pointe le mauvais endroit — d'où la vérification systématique
du numéro CONTRE le contenu réel du fichier.
"""

from pathlib import Path

from engine.context import AnalysisContext
from engine.models import SourceLocation
from powerbi.m_lang import parse_let_steps
from powerbi.tmdl_parser import parse_table_file
from rules import bp_15, bp_21, bp_22

FIXTURES = Path(__file__).parent / "fixtures"


def _line_of(path: Path, line_number: int) -> str:
    return path.read_text(encoding="utf-8-sig").splitlines()[line_number - 1]


def test_column_property_lines_point_at_the_real_property(tmp_path):
    tmdl = tmp_path / "D_X.tmdl"
    tmdl.write_text(
        "table D_X\n"           # 1
        "\tlineageTag: x\n"     # 2
        "\n"                    # 3
        "\tcolumn MONTANT\n"    # 4
        "\t\tdataType: double\n"      # 5
        "\t\tsummarizeBy: sum\n",     # 6
        encoding="utf-8",
    )

    table = parse_table_file(tmdl)
    column = table.columns[0]

    assert table.line == 1
    assert column.line == 4
    assert column.property_lines["dataType"] == 5
    assert column.property_lines["summarizeBy"] == 6
    # Le numéro doit correspondre au contenu réel, pas seulement être plausible.
    assert "summarizeBy: sum" in _line_of(tmdl, column.property_lines["summarizeBy"])


def test_bp22_points_at_the_summarize_by_line_not_the_column_line():
    context = AnalysisContext.from_semantic_model_path(FIXTURES / "bp_22" / "ko")
    result = bp_22.check(context)

    ko = next(f for f in result.findings if f.status == "KO")
    assert ko.location is not None
    assert ko.location.line is not None
    # La ligne pointée doit bien contenir la propriété reprochée.
    assert "summarizeBy" in _line_of(Path(ko.location.source_file), ko.location.line)
    assert ko.remediation
    assert ko.explanation


def test_a_finding_carries_a_readable_excerpt_of_the_faulty_code():
    context = AnalysisContext.from_semantic_model_path(FIXTURES / "bp_22" / "ko")
    ko = next(f for f in bp_22.check(context).findings if f.status == "KO")

    assert ko.location.excerpt
    assert "summarizeBy" in ko.location.excerpt


def test_m_step_offsets_resolve_to_the_right_absolute_line(tmp_path):
    tmdl = tmp_path / "F_A.tmdl"
    tmdl.write_text(
        "table F_A\n"                                   # 1
        "\tlineageTag: a\n"                             # 2
        "\n"                                            # 3
        "\tpartition F_A = m\n"                         # 4
        "\t\tmode: import\n"                            # 5
        "\t\tsource =\n"                                # 6
        "\t\t\t\tlet\n"                                 # 7
        "\t\t\t\t    Source = Sql.Database(\"s\",\"d\"),\n"   # 8
        "\t\t\t\t    Buffered = Table.Buffer(Source),\n"      # 9
        "\t\t\t\t    Final = Table.SelectRows(Buffered, each [X] > 0)\n"  # 10
        "\t\t\t\tin\n"                                  # 11
        "\t\t\t\t    Final\n",                          # 12
        encoding="utf-8",
    )

    table = parse_table_file(tmdl)
    partition = table.partitions[0]
    assert partition.line == 4
    assert partition.m_source_line == 7  # la ligne du `let`

    steps = parse_let_steps(partition.m_source)
    by_name = {s.name: partition.m_source_line + s.line_offset for s in steps}

    assert by_name["Source"] == 8
    assert by_name["Buffered"] == 9
    assert by_name["Final"] == 10
    for name, line in by_name.items():
        assert name in _line_of(tmdl, line)


def test_bp15_points_at_the_fold_breaking_step():
    context = AnalysisContext.from_semantic_model_path(FIXTURES / "bp_15" / "ko_buffer")
    ko = next(f for f in bp_15.check(context).findings if f.status == "KO")

    assert ko.location is not None and ko.location.line is not None
    assert "Table.Buffer" in _line_of(Path(ko.location.source_file), ko.location.line)
    # La remédiation doit nommer les étapes en aval, pas rester générique.
    assert "Filtered" in ko.remediation


def test_bp21_locates_the_offending_object():
    context = AnalysisContext.from_semantic_model_path(FIXTURES / "bp_21" / "ko")
    ko = next(f for f in bp_21.check(context).findings if f.status == "KO")

    assert ko.location is not None
    assert ko.location.line is not None
    assert ko.remediation


def test_location_survives_serialisation_to_the_json_contract():
    # Un consommateur externe (backend, frontend, LLM) ne voit QUE to_dict().
    context = AnalysisContext.from_semantic_model_path(FIXTURES / "bp_22" / "ko")
    ko = next(f for f in bp_22.check(context).findings if f.status == "KO").to_dict()

    assert ko["location"]["line"] is not None
    assert ko["location"]["excerpt"]
    assert ko["remediation"]
    assert ko["explanation"]


def test_a_missing_line_never_fabricates_a_location():
    # Une règle qui ne sait pas situer son constat doit laisser `line` à None
    # plutôt que d'inventer une ligne 1 par défaut.
    location = SourceLocation.from_file("fichier/inexistant.tmdl", None)

    assert location.line is None
    assert location.excerpt is None


def test_an_unreadable_file_degrades_without_raising():
    # L'extrait est un confort d'affichage : son échec ne doit jamais faire
    # échouer une règle.
    location = SourceLocation.from_file("fichier/inexistant.tmdl", 12)

    assert location.line == 12
    assert location.excerpt is None
