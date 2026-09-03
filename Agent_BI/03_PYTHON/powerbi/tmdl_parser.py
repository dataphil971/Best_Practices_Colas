"""Parseur TMDL minimal pour les fichiers de table, relations, modèle et
expressions.

Portée actuelle : nom de table, blocs `column` et `measure` (nom brut +
propriétés brutes, sans interprétation), blocs `partition` (mode + code M
source brut, cf. `powerbi/m_lang.py` pour son inspection), blocs
`relationship` de `definition/relationships.tmdl`, et annotations du bloc
`model` de `definition/model.tmdl`. `definition/expressions.tmdl` (requêtes
partagées et paramètres M) n'est pas encore lu — aucune règle actuelle n'en a
besoin (ne pas le parser "au cas où").

Le format TMDL indente normalement avec des tabulations (confirmé sur un
projet PBIP réel, `AI_BAROMETER_BI-CDS.SemanticModel`), mais un fichier
réécrit à la main ou recopié depuis un éditeur/un rendu Markdown peut avoir
ses tabulations converties en espaces. La profondeur d'un bloc est donc
déterminée par comparaison RELATIVE des longueurs d'indentation (une ligne de
propriété est "plus indentée que" sa colonne, quel que soit le caractère
utilisé) plutôt qu'en comptant des tabulations : un fichier indenté en
espaces n'est ainsi pas silencieusement lu comme une table à zéro colonne.

AVERTISSEMENT — contrairement aux blocs `table`/`column`/`relationship`, le
bloc `partition` (et son code M multi-lignes après `source =`) n'a JAMAIS été
vérifié contre un export PBIP réel dans ce dépôt (aucun extrait `partition`
n'apparaît dans Agent_BI/01_ALGORITHMES/). Le format supposé ici suit la même
convention TMDL que les autres blocs (`clé: valeur` avant `source =`, code M
brut sur les lignes plus indentées ensuite), par cohérence avec le reste du
format déjà confirmé — mais reste à valider sur un vrai projet.
"""

from pathlib import Path

from engine.models import ColumnDef, ExpressionDef, PartitionDef, RelationshipDef, TableDef


def _indent_len(line: str) -> int:
    return len(line) - len(line.lstrip())


def _strip_quotes(raw_name: str) -> str:
    """Retire les guillemets simples d'un nom TMDL en préservant les espaces
    internes (ex: `'ID '` -> `ID `). Ne jamais appliquer .strip() au résultat :
    l'espace fait partie du nom réel, pas un artefact de formatage."""
    if len(raw_name) >= 2 and raw_name[0] == "'" and raw_name[-1] == "'":
        return raw_name[1:-1]
    return raw_name


def _parse_property_line(line: str) -> tuple[str, object] | None:
    stripped = line.strip()
    if not stripped:
        return None

    if stripped.startswith("annotation "):
        rest = stripped[len("annotation ") :]
        if " = " in rest:
            key, _, value = rest.partition(" = ")
            return (f"annotation:{key.strip()}", value.strip())
        return (f"annotation:{rest.strip()}", "")

    if ": " in stripped:
        key, _, value = stripped.partition(": ")
        return (key.strip(), value.strip())

    if stripped.endswith(":"):
        return (stripped[:-1].strip(), "")

    if " = " in stripped:
        key, _, value = stripped.partition(" = ")
        return (key.strip(), value.strip())

    # Propriété booléenne isolée (ex: `isHidden`).
    return (stripped, True)


def _split_name_and_inline_expression(raw: str) -> tuple[str, str | None]:
    """Sépare le nom brut d'une éventuelle expression DAX inline
    (`column X = SUM(...)`), ou du signe `=` isolé en fin de ligne quand
    l'expression commence sur les lignes suivantes plus indentées — forme la
    plus courante en pratique pour une mesure (`measure Nom =` puis un DAX
    multi-lignes, même convention que `partition ... source =`) : confirmée
    sur un export PBIP réel (AI_BAROMETER_BI-CDS.SemanticModel, 2026-08-19)
    où TOUTES les mesures suivent cette forme, jamais l'expression inline.

    Le nom peut être entre guillemets simples et contenir un espace : on ne
    peut donc pas se fier au premier espace pour le délimiter, seulement à la
    paire de guillemets ou, à défaut, au séparateur ` = ` / au `=` final.
    """
    raw = raw.rstrip()
    if raw.startswith("'"):
        end = raw.find("'", 1)
        if end != -1:
            name_part = raw[: end + 1]
            rest = raw[end + 1 :].strip()
            if rest.startswith("="):
                return name_part, rest[1:].strip() or None
            return name_part, None
    if raw.endswith("="):
        return raw[:-1].rstrip(), None
    if " = " in raw:
        name_part, _, expr = raw.partition(" = ")
        return name_part.strip(), expr.strip()
    return raw, None


def _parse_named_block(
    lines: list[str], start: int, block_indent: int, keyword_len: int, source_file: str
) -> tuple[ColumnDef, int]:
    """Parse un bloc `column`/`measure` : nom brut + propriétés du corps.

    `keyword_len` est la longueur du mot-clé + l'espace qui le suit
    (`len("column ")` ou `len("measure ")`), pour isoler le nom.

    Une mesure (ou une colonne calculée) porte son expression DAX inline sur
    la même ligne que sa déclaration (`measure Nom = <expression>`) : elle
    est isolée du nom pour ne jamais polluer les contrôles qui portent
    seulement sur le nom (ex. BP-21). Le corps du bloc peut ensuite contenir
    une suite d'expression multi-lignes avant les propriétés reconnues
    (`formatString`, `displayFolder`, ...) ; ces lignes ne correspondent à
    aucune propriété connue et sont ignorées sans effet sur les clés utiles,
    puisqu'aucune règle actuelle ne lit l'expression elle-même.
    """
    content = lines[start].strip()
    raw_name, _inline_expression = _split_name_and_inline_expression(content[keyword_len:])
    name = _strip_quotes(raw_name)

    properties: dict[str, object] = {}
    property_lines: dict[str, int] = {}
    i = start + 1
    last_body_line = start
    while i < len(lines):
        body_line = lines[i]
        if not body_line.strip():
            i += 1
            continue
        if _indent_len(body_line) <= block_indent:
            break
        parsed = _parse_property_line(body_line)
        if parsed is not None:
            key, value = parsed
            properties[key] = value
            # Lignes 1-indexées : `i` est un index de liste, l'utilisateur
            # attend le numéro affiché par son éditeur.
            property_lines[key] = i + 1
        last_body_line = i
        i += 1

    return (
        ColumnDef(
            name=name,
            raw_name=raw_name,
            properties=properties,
            source_file=source_file,
            line=start + 1,
            end_line=last_body_line + 1,
            property_lines=property_lines,
        ),
        i,
    )


def _parse_partition_block(
    lines: list[str], start: int, block_indent: int, source_file: str
) -> tuple[PartitionDef, int]:
    """Parse un bloc `partition <Nom> = m` : mode + code M source brut.

    Les propriétés précédant `source =` (`mode:`, `queryGroup:`, ...) sont
    lues normalement ligne par ligne. À partir de `source =`, en revanche, le
    corps n'est PAS relu comme une suite de propriétés `clé: valeur` — ce
    serait interpréter du code M (qui contient ses propres `:`/`=`) comme du
    TMDL structurel. Tout ce qui suit `source =` est conservé tel quel comme
    texte M brut, jusqu'au dédent de fin de bloc.
    """
    content = lines[start].strip()
    header = content[len("partition ") :]
    name_part, _, kind = header.partition(" = ")
    name = _strip_quotes(name_part.strip())
    source_kind = kind.strip() or None

    mode: str | None = None
    source_lines: list[str] = []
    in_source = False
    m_source_line: int | None = None

    i = start + 1
    while i < len(lines):
        body_line = lines[i]

        if not body_line.strip():
            if in_source:
                source_lines.append("")
            i += 1
            continue

        if _indent_len(body_line) <= block_indent:
            break

        stripped = body_line.strip()

        if not in_source:
            if stripped.startswith("mode:"):
                mode = stripped[len("mode:") :].strip()
            elif stripped == "source =" or stripped.startswith("source = "):
                in_source = True
                inline = stripped[len("source =") :].strip()
                if inline:
                    source_lines.append(inline)
                    m_source_line = i + 1
                else:
                    # Le code M commence à la ligne SUIVANTE.
                    m_source_line = i + 2
            # Autre propriété de partition (queryGroup, annotation...) :
            # ignorée, aucune règle actuelle n'en a besoin.
            i += 1
            continue

        source_lines.append(body_line)
        i += 1

    joined = "\n".join(source_lines)
    m_source = joined.strip() or None

    if m_source and m_source_line is not None:
        # `.strip()` a pu retirer des lignes vides en tête : sans ce
        # rattrapage, toutes les étapes M seraient décalées vers le haut.
        leading = joined[: len(joined) - len(joined.lstrip())]
        m_source_line += leading.count("\n")

    return PartitionDef(
        name=name,
        mode=mode,
        source_kind=source_kind,
        m_source=m_source,
        source_file=source_file,
        line=start + 1,
        m_source_line=m_source_line if m_source else None,
    ), i


def parse_table_file(path: Path) -> TableDef | None:
    """Parse un fichier `<Table>.tmdl` et retourne son `TableDef`.

    Retourne None si aucune déclaration `table <Nom>` n'a pu être trouvée
    (fichier vide ou non conforme) — la règle appelante doit alors traiter
    ce fichier comme non exploitable, pas comme une table vide valide.
    """
    lines = path.read_text(encoding="utf-8-sig").splitlines()

    table_name: str | None = None
    table_line: int | None = None
    columns: list[ColumnDef] = []
    measures: list[ColumnDef] = []
    partitions: list[PartitionDef] = []

    i = 0
    while i < len(lines):
        line = lines[i]

        if not line.strip():
            i += 1
            continue

        indent = _indent_len(line)
        content = line.strip()

        if indent == 0 and content.startswith("table "):
            # `_strip_quotes`, jamais `.strip()` seul : un nom de table
            # contenant un espace (rare mais réel, ex. BP-21) est encadré de
            # guillemets simples par TMDL — les retirer sans toucher à
            # l'espace interne/final qu'ils protègent, exactement comme pour
            # les colonnes et mesures.
            table_name = _strip_quotes(content[len("table ") :].strip())
            table_line = i + 1
            i += 1
            continue

        # Toute ligne indentée atteinte ICI (pas déjà consommée par le corps
        # d'une colonne/mesure précédente) est un membre direct de la table :
        # exactement le niveau "column"/"measure" du bloc, quelle que soit la
        # largeur d'indentation réelle du fichier.
        if indent > 0 and content.startswith("column "):
            col, i = _parse_named_block(lines, i, indent, len("column "), str(path))
            columns.append(col)
            continue

        if indent > 0 and content.startswith("measure "):
            mes, i = _parse_named_block(lines, i, indent, len("measure "), str(path))
            measures.append(mes)
            continue

        if indent > 0 and content.startswith("partition "):
            part, i = _parse_partition_block(lines, i, indent, str(path))
            partitions.append(part)
            continue

        # Propriété de table ou toute autre ligne hors périmètre : ignorée,
        # avancée ligne à ligne (pas de saut de bloc dédié, puisque son
        # contenu n'a pas besoin d'être interprété ici).
        i += 1

    if table_name is None:
        return None

    return TableDef(
        name=table_name,
        source_file=str(path),
        line=table_line,
        columns=columns,
        measures=measures,
        partitions=partitions,
    )


def _table_and_column(ref: object) -> tuple[str, str]:
    # Forme attendue : "Table.Colonne" ou "Table.'Colonne avec espace'".
    text = str(ref)
    table, _, column = text.partition(".")
    return table.strip(), _strip_quotes(column.strip())


def parse_relationships_file(path: Path) -> list[RelationshipDef]:
    """Parse `definition/relationships.tmdl` : un `RelationshipDef` par bloc
    `relationship <id>`.

    Retourne une liste vide si le fichier est absent — un modèle sans aucune
    relation est un état valide (table unique), pas une erreur de lecture ;
    c'est à la règle appelante de distinguer ce cas de la vraie absence de
    fichier, via `AnalysisContext.relationships_tmdl_path`.
    """
    if not path.exists():
        return []

    lines = path.read_text(encoding="utf-8-sig").splitlines()
    relationships: list[RelationshipDef] = []

    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue

        indent = _indent_len(line)
        content = line.strip()

        if indent == 0 and content.startswith("relationship "):
            rel_id = content[len("relationship ") :].strip()
            rel_indent = indent
            rel_line = i + 1
            properties: dict[str, object] = {}
            rel_property_lines: dict[str, int] = {}
            i += 1
            while i < len(lines):
                body_line = lines[i]
                if not body_line.strip():
                    i += 1
                    continue
                if _indent_len(body_line) <= rel_indent:
                    break
                parsed = _parse_property_line(body_line)
                if parsed is not None:
                    key, value = parsed
                    properties[key] = value
                    rel_property_lines[key] = i + 1
                i += 1

            from_table, from_column = _table_and_column(properties.get("fromColumn", ""))
            to_table, to_column = _table_and_column(properties.get("toColumn", ""))
            is_active_raw = properties.get("isActive")
            is_active = True if is_active_raw is None else str(is_active_raw).strip().lower() != "false"

            relationships.append(
                RelationshipDef(
                    id=rel_id,
                    from_table=from_table,
                    from_column=from_column,
                    to_table=to_table,
                    to_column=to_column,
                    from_cardinality=(
                        str(properties["fromCardinality"]).strip()
                        if "fromCardinality" in properties
                        else None
                    ),
                    to_cardinality=(
                        str(properties["toCardinality"]).strip() if "toCardinality" in properties else None
                    ),
                    cross_filtering_behavior=(
                        str(properties["crossFilteringBehavior"]).strip()
                        if "crossFilteringBehavior" in properties
                        else None
                    ),
                    is_active=is_active,
                    source_file=str(path),
                    line=rel_line,
                    property_lines=rel_property_lines,
                )
            )
            continue

        i += 1

    return relationships


def parse_model_file(path: Path) -> dict[str, str]:
    """Parse les annotations du modèle portées par `definition/model.tmdl`.

    Contrairement à l'hypothèse initiale (annotations imbriquées sous le
    bloc `model <Nom>`), un export réel place les annotations du modèle
    (`__PBI_TimeIntelligenceEnabled`, `PBI_QueryOrder`, ...) directement à la
    RACINE du fichier (profondeur 0), au même niveau que `model <Nom>`,
    les blocs `queryGroup <Nom>` et les lignes `ref table <Nom>` — jamais
    imbriquées sous `model`. Confirmé sur un export PBIP réel
    (`AI_BAROMETER_BI-CDS.SemanticModel`, 2026-08-19).

    Les annotations propres à un `queryGroup` (ex. `PBI_QueryGroupOrder`)
    sont, elles, indentées sous leur bloc `queryGroup` (profondeur > 0) : ne
    retenir que la profondeur 0 les exclut naturellement, sans confusion de
    nom avec les annotations du modèle.
    """
    if not path.exists():
        return {}

    lines = path.read_text(encoding="utf-8-sig").splitlines()
    annotations: dict[str, str] = {}

    for line in lines:
        if not line.strip():
            continue
        if _indent_len(line) != 0:
            continue
        content = line.strip()
        if not content.startswith("annotation "):
            continue
        parsed = _parse_property_line(content)
        if parsed is not None:
            key, value = parsed
            if key.startswith("annotation:"):
                annotations[key[len("annotation:") :]] = str(value)

    return annotations


def parse_expressions_file(path: Path) -> list[ExpressionDef]:
    """Parse `definition/expressions.tmdl` : un `ExpressionDef` par bloc
    `expression <Nom> = ...` de profondeur 0.

    Trois formes confirmées sur un export PBIP réel
    (AI_BAROMETER_BI-CDS.SemanticModel, 2026-08-19) :

    1. `expression Nom = <valeur> [meta [...]]` — sur une seule ligne
       (typiquement un paramètre, ex. `IsParameterQuery=true` dans `meta`).
    2. `expression Nom =` puis code M sur les lignes suivantes, plus
       indentées (même convention que `partition ... source =`).
    3. `expression Nom = \\`\\`\\`` puis code M jusqu'à une ligne composée
       du seul délimiteur `\\`\\`\\``  — utilisé par le sérialiseur TMDL pour
       certaines expressions (observé pour une requête contenant une chaîne
       SQL multi-lignes).

    Retourne une liste vide si le fichier est absent — un projet sans aucune
    requête partagée est un état valide, pas une erreur de lecture.
    """
    if not path.exists():
        return []

    lines = path.read_text(encoding="utf-8-sig").splitlines()
    n = len(lines)
    expressions: list[ExpressionDef] = []
    i = 0

    while i < n:
        line = lines[i]
        if not line.strip() or _indent_len(line) != 0:
            i += 1
            continue

        content = line.strip()
        if not content.startswith("expression "):
            i += 1
            continue

        header = content[len("expression ") :]
        raw_name, tail = _split_name_and_inline_expression(header)
        name = _strip_quotes(raw_name)
        expression_line = i + 1
        m_source_line = i + 2  # le corps commence à la ligne suivante
        i += 1

        if tail is not None and tail.strip() == "```":
            body_lines: list[str] = []
            while i < n and lines[i].strip() != "```":
                body_lines.append(lines[i])
                i += 1
            if i < n:
                i += 1  # consomme la ligne de fermeture ```
            m_source = "\n".join(body_lines).strip() or None
        elif tail is None:
            body_lines = []
            while i < n:
                body_line = lines[i]
                if not body_line.strip():
                    body_lines.append("")
                    i += 1
                    continue
                if _indent_len(body_line) <= 0:
                    break
                body_lines.append(body_line)
                i += 1
            m_source = "\n".join(body_lines).strip() or None
        else:
            # Forme sur une seule ligne (paramètre) : la valeur elle-même
            # n'est en général pas un bloc `let...in` — laissée telle quelle,
            # `parse_let_steps` y trouvera simplement 0 étape.
            m_source = tail.strip() or None
            m_source_line = expression_line  # valeur inline : même ligne

        expressions.append(
            ExpressionDef(
                name=name,
                m_source=m_source,
                source_file=str(path),
                line=expression_line,
                m_source_line=m_source_line if m_source else None,
            )
        )

    return expressions


def parse_tables_directory(tables_dir: Path) -> list[TableDef]:
    """Parse tous les fichiers `*.tmdl` d'un dossier `definition/tables/`.

    Retourne une liste vide si le dossier n'existe pas — c'est au contexte
    d'analyse (`engine/context.py`) d'interpréter cette absence en `NA`,
    pas au parseur.
    """
    if not tables_dir.exists() or not tables_dir.is_dir():
        return []

    tables = []
    for tmdl_file in sorted(tables_dir.glob("*.tmdl")):
        table = parse_table_file(tmdl_file)
        if table is not None:
            tables.append(table)
    return tables
