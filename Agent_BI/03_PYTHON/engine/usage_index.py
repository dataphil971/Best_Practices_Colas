"""Index d'usage des colonnes du modèle, partagé entre règles.

Réponse au §4 de Agent_BI/01_ALGORITHMES/07_RemoveUnusedFields.md : « Il est
construit une seule fois pour le PBIP et peut être réutilisé par les autres
règles. » Extrait de `rules/bp_07.py` le jour où un second consommateur est
apparu (`rules/bp_25.py`) — pas avant, conformément au principe du moteur de
ne rien factoriser "au cas où".

Surfaces couvertes (§5 de BP-07) :
  * `dax`           — références QUALIFIÉES `Table[Colonne]` du TMDL ;
  * `relationships` — `fromColumn` / `toColumn` ;
  * `sort_by`       — cible d'un `sortByColumn` ;
  * `group_by`      — cible d'un `groupByColumn` ;
  * `report`        — toute référence de champ du rapport PBIR.

Les références DAX NON qualifiées (`[Nom]`) ne sont jamais converties en
usage : elles sont retournées à part, comme bloqueurs (§7 de BP-07).
"""

from pathlib import Path
from typing import Dict, List, Set, Tuple

from powerbi.dax_lang import extract_column_references

ColumnKey = Tuple[str, str]


def _scan_model_dax(context) -> Tuple[Set[ColumnKey], Set[str]]:
    """Balaie le TEXTE BRUT de chaque fichier de table.

    Volontairement plus large que « les seules expressions de mesures » : le
    fichier contient aussi les colonnes calculées, les tables calculées et
    diverses propriétés référençant des colonnes. Cette sur-approximation ne
    peut que faire détecter PLUS d'usages (ou plus de bloqueurs), donc
    supprimer des KO — jamais en fabriquer un faux.
    """
    qualified: Set[ColumnKey] = set()
    unqualified: Set[str] = set()
    for table in context.tables:
        try:
            raw = Path(table.source_file).read_text(encoding="utf-8-sig")
        except OSError:
            continue
        found_qualified, found_unqualified = extract_column_references(raw)
        qualified |= found_qualified
        unqualified |= found_unqualified
    return qualified, unqualified


def build_usage_index(context) -> Tuple[Dict[ColumnKey, List[str]], Set[str]]:
    """Retourne ((table, colonne) -> surfaces d'usage, noms DAX ambigus)."""
    usage: Dict[ColumnKey, List[str]] = {}

    def record(table_name, column_name, surface):
        if table_name and column_name:
            usage.setdefault((table_name, column_name), []).append(surface)

    dax_qualified, dax_unqualified = _scan_model_dax(context)
    for table_name, column_name in dax_qualified:
        record(table_name, column_name, "dax")

    for relationship in context.relationships:
        record(relationship.from_table, relationship.from_column, "relationships")
        record(relationship.to_table, relationship.to_column, "relationships")

    for table in context.tables:
        for column in table.columns:
            for prop, surface in (("sortByColumn", "sort_by"),
                                  ("groupByColumn", "group_by")):
                target = column.get_property(prop)
                if target:
                    record(table.name, str(target).strip().strip("'"), surface)

    for _kind, entity, prop in context.report_field_references:
        record(entity, prop, "report")

    return usage, dax_unqualified
