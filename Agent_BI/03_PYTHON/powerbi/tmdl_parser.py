"""Parseur TMDL minimal pour les fichiers de table (`definition/tables/*.tmdl`).

Portée actuelle : nom de table et blocs `column` (nom brut + propriétés brutes,
sans interprétation). Les blocs `measure` et `partition` sont ignorés — ils ne
sont pas nécessaires aux règles actuellement implémentées et seront couverts
séparément quand une règle en aura besoin (ne pas les parser "au cas où").

Le format TMDL indente avec des tabulations (confirmé sur un projet PBIP réel,
`AI_BAROMETER_BI-CDS.SemanticModel`) : la profondeur d'un bloc est déterminée
en comptant les tabulations de tête, jamais un nombre fixe d'espaces.
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple

from engine.models import ColumnDef, TableDef


def _indent_depth(line: str) -> int:
    return len(line) - len(line.lstrip("\t"))


def _strip_quotes(raw_name: str) -> str:
    """Retire les guillemets simples d'un nom TMDL en préservant les espaces
    internes (ex: `'ID '` -> `ID `). Ne jamais appliquer .strip() au résultat :
    l'espace fait partie du nom réel, pas un artefact de formatage."""
    if len(raw_name) >= 2 and raw_name[0] == "'" and raw_name[-1] == "'":
        return raw_name[1:-1]
    return raw_name


def _parse_property_line(line: str) -> Optional[Tuple[str, object]]:
    stripped = line.strip()
    if not stripped:
        return None

    if stripped.startswith("annotation "):
        rest = stripped[len("annotation "):]
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


def parse_table_file(path: Path) -> Optional[TableDef]:
    """Parse un fichier `<Table>.tmdl` et retourne son `TableDef`.

    Retourne None si aucune déclaration `table <Nom>` n'a pu être trouvée
    (fichier vide ou non conforme) — la règle appelante doit alors traiter
    ce fichier comme non exploitable, pas comme une table vide valide.
    """
    lines = path.read_text(encoding="utf-8-sig").splitlines()

    table_name: Optional[str] = None
    columns: List[ColumnDef] = []

    i = 0
    while i < len(lines):
        line = lines[i]

        if not line.strip():
            i += 1
            continue

        depth = _indent_depth(line)
        content = line.strip()

        if depth == 0 and content.startswith("table "):
            table_name = content[len("table "):].strip()
            i += 1
            continue

        if depth == 1 and content.startswith("column "):
            raw_name = content[len("column "):].strip()
            name = _strip_quotes(raw_name)

            properties: Dict[str, object] = {}
            i += 1
            while i < len(lines):
                body_line = lines[i]
                if not body_line.strip():
                    i += 1
                    continue
                if _indent_depth(body_line) < 2:
                    break
                parsed = _parse_property_line(body_line)
                if parsed is not None:
                    key, value = parsed
                    properties[key] = value
                i += 1

            columns.append(ColumnDef(
                name=name,
                raw_name=raw_name,
                properties=properties,
                source_file=str(path),
            ))
            continue

        # Bloc `measure`/`partition`, propriété de table, ou toute autre ligne
        # hors périmètre : ignorée, avancée ligne à ligne (pas de saut de bloc
        # dédié, puisque son contenu n'a pas besoin d'être interprété ici).
        i += 1

    if table_name is None:
        return None

    return TableDef(name=table_name, source_file=str(path), columns=columns)


def parse_tables_directory(tables_dir: Path) -> List[TableDef]:
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
