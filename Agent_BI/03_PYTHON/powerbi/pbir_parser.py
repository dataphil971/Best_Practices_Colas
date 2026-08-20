"""Parseur PBIR minimal pour le dossier `<Nom>.Report/`.

Portée actuelle : uniquement les FILTRES déclarés (`filterConfig`) aux trois
niveaux du rapport, avec la référence de champ qu'ils portent — c'est tout ce
dont BP-39 a besoin. Les visuels, signets, thèmes et propriétés de mise en
forme ne sont PAS extraits : aucune règle actuelle ne les exploite (même
principe que `powerbi/tmdl_parser.py`, ne pas parser "au cas où").

Format confirmé sur un export PBIP réel (AI_BAROMETER_BI-CDS.Report,
2026-08-19) :

    definition/report.json                              -> filtres rapport
    definition/pages/<pageId>/page.json                 -> filtres page
    definition/pages/<pageId>/visuals/<visualId>/visual.json -> filtres visuel

Une référence de champ y prend la forme :

    {"Column":  {"Expression": {"SourceRef": {"Entity": "<table>"}},
                 "Property": "<colonne>"}}
    {"Measure": {"Expression": {"SourceRef": {"Entity": "<table>"}},
                 "Property": "<mesure>"}}
"""

import json
from pathlib import Path
from typing import Any, List, Optional

from engine.models import ReportFilterDef

# §4 de BP-41 : visuels décoratifs ou de navigation, sans contenu analytique.
# Ils sont hors périmètre de la recherche de doublons — jamais classés KO.
NON_ANALYTICAL_VISUAL_TYPES = {
    "textbox", "image", "shape", "basicShape", "actionButton",
    "visualGroup", "pageNavigator", "bookmarkNavigator",
}


def _iter_field_references(node: Any) -> "list[tuple[str, Optional[str], Optional[str]]]":
    """Collecte récursivement les couples (kind, entity, property) d'un
    fragment JSON de champ. Récursif car un champ peut être imbriqué dans une
    agrégation, une hiérarchie ou une transformation dont la forme exacte
    varie selon la version PBIR — on ne suppose pas une profondeur fixe."""
    found: "list[tuple[str, Optional[str], Optional[str]]]" = []

    if isinstance(node, dict):
        for kind in ("Column", "Measure"):
            inner = node.get(kind)
            if isinstance(inner, dict):
                source_ref = inner.get("Expression", {})
                if isinstance(source_ref, dict):
                    source_ref = source_ref.get("SourceRef", {})
                entity = source_ref.get("Entity") if isinstance(source_ref, dict) else None
                found.append((kind, entity, inner.get("Property")))
        for value in node.values():
            found.extend(_iter_field_references(value))
    elif isinstance(node, list):
        for value in node:
            found.extend(_iter_field_references(value))

    return found


def _find_line_of_name(raw_text: str, name: str) -> Optional[int]:
    """Numéro de ligne (1-indexé) de la déclaration `"name": "<name>"`.

    Le module `json` ne conserve aucune position : sans cette recherche
    textuelle, un constat sur un filtre ne pourrait citer que le fichier, pas
    l'endroit. Les `name` PBIR sont des empreintes uniques, la recherche est
    donc sans ambiguïté. Retourne None si introuvable — jamais une ligne 1
    par défaut, qui pointerait au hasard.
    """
    if not name:
        return None
    needle = f'"{name}"'
    for index, line in enumerate(raw_text.splitlines(), start=1):
        if needle in line:
            return index
    return None


def _parse_one_file(path: Path, level: str, page_id: Optional[str],
                    visual_id: Optional[str]) -> List[ReportFilterDef]:
    try:
        raw_text = path.read_text(encoding="utf-8-sig")
        document = json.loads(raw_text)
    except (OSError, json.JSONDecodeError):
        # Fichier illisible : aucun filtre remonté. C'est à la règle
        # appelante de traiter l'absence comme "rien à tester" (NA), jamais
        # comme "aucun filtre cassé" (OK).
        return []

    filter_config = document.get("filterConfig")
    if not isinstance(filter_config, dict):
        return []

    filters: List[ReportFilterDef] = []
    for raw_filter in filter_config.get("filters", []):
        if not isinstance(raw_filter, dict):
            continue
        references = _iter_field_references(raw_filter.get("field", {}))
        name = str(raw_filter.get("name", ""))
        filters.append(ReportFilterDef(
            name=name,
            level=level,
            page_id=page_id,
            visual_id=visual_id,
            filter_type=raw_filter.get("type"),
            field_references=references,
            source_file=str(path),
            line=_find_line_of_name(raw_text, name),
        ))
    return filters


def _iter_definition_files(report_path: Optional[Path]) -> List[Path]:
    """Tous les fichiers JSON de définition du rapport, quel que soit leur
    niveau. Volontairement basé sur un parcours récursif plutôt que sur une
    liste de chemins figés : le §8 de BP-07 impose de « ne pas dépendre d'un
    chemin JSON unique », les emplacements variant selon la version PBIR."""
    if report_path is None or not report_path.exists():
        return []
    definition = report_path / "definition"
    if not definition.is_dir():
        return []
    return sorted(definition.rglob("*.json"))


def parse_report_field_references(
    report_path: Optional[Path],
) -> "set[tuple[str, str, str]]":
    """Toutes les références de champ (kind, entity, property) trouvées dans
    le rapport, tous fichiers et toutes surfaces confondus : projections de
    visuels, filtres, tris, info-bulles, signets...

    Aucune distinction de surface n'est faite : BP-07 a seulement besoin de
    savoir si un champ est référencé QUELQUE PART dans le rapport. Distinguer
    les surfaces (axe / légende / filtre...) serait du parsing "au cas où".
    """
    references: "set[tuple[str, str, str]]" = set()
    for path in _iter_definition_files(report_path):
        try:
            document = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            continue
        for kind, entity, prop in _iter_field_references(document):
            if entity and prop:
                references.add((kind, entity, prop))
    return references


def _iter_aggregation_nodes(node: Any) -> "list[tuple[Optional[str], Optional[str], Any]]":
    """Collecte les nœuds `Aggregation` appliqués à une `Column`.

    Retourne (entity, property, fonction brute). `entity`/`property` à None
    signalent une agrégation dont la cible n'est PAS une colonne résolue —
    à traiter en NA (`UNKNOWN_AGGREGATION`, §6 de BP-32), jamais en KO.
    """
    found: "list[tuple[Optional[str], Optional[str], Any]]" = []

    if isinstance(node, dict):
        aggregation = node.get("Aggregation")
        if isinstance(aggregation, dict):
            columns = [
                (entity, prop)
                for kind, entity, prop in _iter_field_references(
                    aggregation.get("Expression", {})
                )
                if kind == "Column"
            ]
            function = aggregation.get("Function")
            if columns:
                for entity, prop in columns:
                    found.append((entity, prop, function))
            else:
                found.append((None, None, function))

        for key, value in node.items():
            # Ne pas redescendre dans l'agrégation déjà traitée : le §6
            # impose de ne pas compter deux fois le même nœud.
            if key != "Aggregation":
                found.extend(_iter_aggregation_nodes(value))
    elif isinstance(node, list):
        for value in node:
            found.extend(_iter_aggregation_nodes(value))

    return found


def parse_report_implicit_aggregations(
    report_path: Optional[Path],
) -> "list[dict]":
    """Recense les agrégations implicites sérialisées dans les visuels.

    Une agrégation appliquée à une COLONNE est la signature déterministe
    d'une mesure implicite (§3 de BP-32). Une colonne SANS nœud
    `Aggregation` n'en est pas une (§5) : elle peut être un axe, un slicer,
    une ligne de tableau — elle n'est donc jamais remontée ici.
    """
    aggregations: "list[dict]" = []
    for path in _iter_definition_files(report_path):
        if path.name != "visual.json":
            continue
        try:
            document = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            continue
        visual = document.get("visual") or {}
        for entity, prop, function in _iter_aggregation_nodes(document):
            aggregations.append({
                "visual_id": document.get("name"),
                "visual_type": visual.get("visualType"),
                "page_id": path.parent.parent.parent.name,
                "table": entity,
                "column": prop,
                "aggregation_function_raw": function,
                "source_file": str(path),
            })
    return aggregations


def parse_report_visuals(report_path: Optional[Path]) -> "list[dict]":
    """Inventaire des visuels avec leur SIGNATURE ANALYTIQUE canonique.

    La signature suit le §5/§6 de BP-41 : type de visuel + références de
    champs projetées, triées. Elle NE dépend PAS de l'identifiant du visuel,
    de la page, de l'ordre JSON, de la position, de la taille, de la couleur
    ni du titre — ces éléments sont conservés à part, comme contexte de revue
    (§6 : « peuvent toutefois être conservés pour le contexte »).

    `signature` vaut None pour un visuel hors périmètre analytique
    (§4 : textbox, image, shape, actionButton, conteneur de groupe) ou sans
    aucun champ projeté : il ne participe alors pas à la recherche de
    doublons plutôt que de créer un faux groupe de visuels « vides ».
    """
    visuals: "list[dict]" = []
    for path in _iter_definition_files(report_path):
        if path.name != "visual.json":
            continue
        try:
            document = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            continue

        visual = document.get("visual") or {}
        visual_type = visual.get("visualType")
        is_group = "visualGroup" in document

        references = sorted({
            f"{kind}:{entity}[{prop}]"
            for kind, entity, prop in _iter_field_references(visual.get("query", {}))
            if entity and prop
        })

        signature = None
        if not is_group and visual_type not in NON_ANALYTICAL_VISUAL_TYPES and references:
            signature = (visual_type, tuple(references))

        visuals.append({
            "visual_id": document.get("name") or path.parent.name,
            "page_id": path.parent.parent.parent.name,
            "visual_type": visual_type,
            "is_group": is_group,
            "is_hidden": bool(document.get("isHidden")),
            "parent_group": document.get("parentGroupName"),
            "position": document.get("position"),
            "field_references": references,
            "signature": signature,
            "source_file": str(path),
        })
    return visuals


def parse_report_structure(report_path: Optional[Path]) -> "dict":
    """Structure du rapport nécessaire aux contrôles d'intégrité (BP-37/BP-38).

    Retourne un dict :
      * `visuals`        : {page_id: {visual_name}} — tout objet du dossier
                           `visuals/`, groupe compris (un groupe EST un
                           visual.json, porteur d'une clé `visualGroup`) ;
      * `groups`         : {page_id: {group_name}} ;
      * `parent_links`   : [(page_id, visual_name, parent_group_name)] ;
      * `interactions`   : [(page_id, source, target, type)] ;
      * `bookmark_files` : {bookmark_name} déclarés par un `*.bookmark.json` ;
      * `bookmark_items` : [(name, [children])] déclarés par `bookmarks.json` ;
      * `bookmarks_metadata_present` : bool.

    Aucune interprétation ici : les règles décident seules de ce qui
    constitue une incohérence.
    """
    structure = {
        "visuals": {}, "groups": {}, "parent_links": [], "interactions": [],
        "bookmark_files": set(), "bookmark_items": [],
        "bookmarks_metadata_present": False,
    }
    if report_path is None or not (report_path / "definition").is_dir():
        return structure

    definition = report_path / "definition"

    pages_dir = definition / "pages"
    if pages_dir.is_dir():
        for page_dir in sorted(p for p in pages_dir.iterdir() if p.is_dir()):
            page_id = page_dir.name
            structure["visuals"].setdefault(page_id, set())
            structure["groups"].setdefault(page_id, set())

            page_json = page_dir / "page.json"
            if page_json.exists():
                try:
                    page = json.loads(page_json.read_text(encoding="utf-8-sig"))
                except (OSError, json.JSONDecodeError):
                    page = {}
                for entry in page.get("visualInteractions", []) or []:
                    if isinstance(entry, dict):
                        structure["interactions"].append((
                            page_id, entry.get("source"), entry.get("target"),
                            entry.get("type"),
                        ))

            visuals_dir = page_dir / "visuals"
            if visuals_dir.is_dir():
                for visual_dir in sorted(v for v in visuals_dir.iterdir() if v.is_dir()):
                    visual_json = visual_dir / "visual.json"
                    if not visual_json.exists():
                        continue
                    try:
                        visual = json.loads(visual_json.read_text(encoding="utf-8-sig"))
                    except (OSError, json.JSONDecodeError):
                        continue
                    name = visual.get("name") or visual_dir.name
                    structure["visuals"][page_id].add(name)
                    if "visualGroup" in visual:
                        structure["groups"][page_id].add(name)
                    parent = visual.get("parentGroupName")
                    if parent:
                        structure["parent_links"].append((page_id, name, parent))

    bookmarks_dir = definition / "bookmarks"
    if bookmarks_dir.is_dir():
        for path in sorted(bookmarks_dir.glob("*.bookmark.json")):
            try:
                bookmark = json.loads(path.read_text(encoding="utf-8-sig"))
            except (OSError, json.JSONDecodeError):
                continue
            structure["bookmark_files"].add(bookmark.get("name") or path.stem)

        metadata = bookmarks_dir / "bookmarks.json"
        if metadata.exists():
            structure["bookmarks_metadata_present"] = True
            try:
                document = json.loads(metadata.read_text(encoding="utf-8-sig"))
            except (OSError, json.JSONDecodeError):
                document = {}
            for item in document.get("items", []) or []:
                if isinstance(item, dict):
                    children = [c for c in (item.get("children") or []) if isinstance(c, str)]
                    structure["bookmark_items"].append((item.get("name"), children))

    return structure


def parse_report_filters(report_path: Optional[Path]) -> List[ReportFilterDef]:
    """Collecte tous les filtres déclarés du rapport, tous niveaux confondus.

    Retourne `[]` si le dossier rapport est absent — un projet PBIP peut être
    livré sans son `.Report/`, ce qui n'est pas une erreur de lecture.
    """
    if report_path is None or not report_path.exists():
        return []

    definition = report_path / "definition"
    if not definition.is_dir():
        return []

    filters: List[ReportFilterDef] = []

    report_json = definition / "report.json"
    if report_json.exists():
        filters.extend(_parse_one_file(report_json, "report", None, None))

    pages_dir = definition / "pages"
    if pages_dir.is_dir():
        for page_dir in sorted(p for p in pages_dir.iterdir() if p.is_dir()):
            page_id = page_dir.name
            page_json = page_dir / "page.json"
            if page_json.exists():
                filters.extend(_parse_one_file(page_json, "page", page_id, None))

            visuals_dir = page_dir / "visuals"
            if visuals_dir.is_dir():
                for visual_dir in sorted(v for v in visuals_dir.iterdir() if v.is_dir()):
                    visual_json = visual_dir / "visual.json"
                    if visual_json.exists():
                        filters.extend(
                            _parse_one_file(visual_json, "visual", page_id, visual_dir.name)
                        )

    return filters
