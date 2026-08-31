"""Tests du parseur TMDL.

Le parseur ne prend aucune décision OK/KO/NA : on vérifie ici uniquement qu'il
restitue fidèlement ce qui est écrit dans le fichier, y compris les formes
« sales » rencontrées sur de vrais projets.
"""

from powerbi.tmdl_parser import parse_table_file, parse_tables_directory


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

    assert table is not None
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

    assert table is not None
    assert table.name == "MEASURE"
    assert table.columns == []


def test_parser_reads_consecutive_columns(tmp_path):
    # Un bloc `column` doit s'arrêter au suivant : sans cela, les propriétés
    # de la deuxième colonne seraient attribuées à la première.
    tmdl_file = tmp_path / "TWO.tmdl"
    tmdl_file.write_text(
        "table TWO\n\tcolumn A\n\t\tsummarizeBy: none\n\tcolumn B\n\t\tsummarizeBy: sum\n",
        encoding="utf-8",
    )

    table = parse_table_file(tmdl_file)

    assert table is not None
    assert [column.name for column in table.columns] == ["A", "B"]
    assert table.columns[0].get_property("summarizeBy") == "none"
    assert table.columns[1].get_property("summarizeBy") == "sum"


def test_parser_reads_isolated_boolean_properties(tmp_path):
    tmdl_file = tmp_path / "HIDDEN.tmdl"
    tmdl_file.write_text(
        "table HIDDEN\n\tcolumn TECH_KEY\n\t\tisHidden\n\t\tsummarizeBy: none\n",
        encoding="utf-8",
    )

    table = parse_table_file(tmdl_file)

    assert table is not None
    assert table.columns[0].get_property("isHidden") is True


def test_parser_returns_none_for_a_file_without_a_table_declaration(tmp_path):
    tmdl_file = tmp_path / "empty.tmdl"
    tmdl_file.write_text("", encoding="utf-8")

    assert parse_table_file(tmdl_file) is None


def test_parse_tables_directory_returns_empty_list_when_directory_is_missing(tmp_path):
    # C'est au contexte d'analyse d'interpréter cette absence en NA, pas au
    # parseur : il ne doit ni lever, ni inventer une table.
    assert parse_tables_directory(tmp_path / "inexistant") == []
