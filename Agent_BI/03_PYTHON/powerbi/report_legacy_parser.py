"""Parseur du format de rapport « legacy » : `<Nom>.Report/report.json`.

Deux sérialisations de rapport coexistent dans PBIP :

* le format **PBIR étendu**, arborescent — `definition/pages/<pageId>/visuals/
  <visualId>/visual.json` — lu par `powerbi/pbir_parser.py` ;
* le format **legacy**, un unique `report.json` à la racine du dossier
  `.Report/`, dans lequel les configurations sont des CHAÎNES JSON imbriquées.

Ce module lit le second et expose exactement les mêmes fonctions que le
premier, avec les mêmes structures de retour. Les règles rapport (BP-32,
BP-37, BP-38, BP-39, BP-41) ne connaissent donc pas le format qu'elles
analysent : c'est `engine/context.py` qui choisit le parseur.

Différences de forme traitées ici — ce sont elles qui rendaient les règles
rapport aveugles sur ce format :

1. **Configurations sérialisées en chaîne.** `report["config"]`,
   `section["config"]`, `visualContainer["config"]` et les `filters` sont des
   `str` contenant du JSON, pas des objets. Ils sont décodés à la volée.

2. **Références de champ par ALIAS.** Dans un `prototypeQuery`, un champ
   s'écrit `{"SourceRef": {"Source": "m"}}` où `m` est un alias déclaré dans
   la clause `From` du même query : `{"Name": "m", "Entity": "Mesures"}`.
   Le format PBIR, lui, porte directement `{"SourceRef": {"Entity": ...}}`.
   Sans résolution de l'alias, toute référence sortirait avec `entity=None`
   et serait donc ignorée. `_resolve_field_references` fait cette résolution.

3. **Groupes de visuels.** Un groupe porte `singleVisualGroup` au lieu de
   `singleVisual` ; l'appartenance passe par `parentGroupName`.

4. **Interactions.** Elles vivent dans `section["config"]["relationships"]`
   sous la forme `{"source", "target", "type"}`, et non dans un
   `visualInteractions` de page.

5. **Signets.** Ils vivent dans `report["config"]["bookmarks"]`, en arbre
   (`children`), et non dans des fichiers `*.bookmark.json`.

Aucune décision OK/KO/NA n'est prise ici : ce module lit, il n'interprète pas.
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from engine.models import ReportFilterDef
from powerbi.pbir_parser import (
    NON_ANALYTICAL_VISUAL_TYPES,
    _iter_field_references,
)

REPORT_FILE_NAME = "report.json"


def _find_line_of_name(lines: list[str], name: str) -> int | None:
    """Numéro de ligne (1-indexé) où apparaît le nom d'un filtre.

    Ne peut pas réutiliser la fonction homonyme du parseur PBIR : celle-ci
    cherche `"<name>"`, or dans un `report.json` legacy les filtres vivent à
    l'intérieur d'une CHAÎNE JSON, où les guillemets sont échappés
    (`\\"filtre\\"`). La recherche avec guillemets n'y trouve donc jamais rien
    et tout constat perdrait sa localisation dans un fichier de plusieurs
    mégaoctets.

    On cherche le nom nu, ce qui est sans ambiguïté : les `name` de filtre
    sont des empreintes générées. Retourne None si introuvable — jamais une
    ligne 1 par défaut, qui pointerait au hasard.

    Prend les lignes DÉJÀ découpées, jamais le texte brut : un rapport réel
    porte plus d'un millier de filtres, et redécouper le fichier à chaque
    appel coûtait 42 s sur un `report.json` de 4 Mo — l'essentiel du temps
    d'analyse du projet.
    """
    if not name:
        return None
    for index, line in enumerate(lines, start=1):
        if name in line:
            return index
    return None


def is_legacy_report(report_path: Path | None) -> bool:
    """Vrai si le dossier rapport est au format legacy.

    Le critère est l'existence de `report.json` à la RACINE du dossier
    `.Report/`. Il ne suffit pas de constater l'absence de `definition/` :
    un rapport PBIR étendu possède lui aussi un `definition/report.json`, à
    un autre emplacement.
    """
    if report_path is None or not report_path.is_dir():
        return False
    return (report_path / REPORT_FILE_NAME).is_file()


@lru_cache(maxsize=4)
def _load_report_cached(path: Path, _mtime: float, _size: int) -> dict[str, Any]:
    """Lecture et décodage effectifs, mémorisés.

    `_mtime` et `_size` ne sont pas utilisés dans le corps : ils font partie de
    la CLÉ de cache, pour qu'un fichier modifié entre deux appels soit relu au
    lieu d'être servi depuis la mémoire.
    """
    try:
        document = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    return document if isinstance(document, dict) else {}


def _load_report(report_path: Path | None) -> dict[str, Any]:
    """Contenu de `report.json`, ou `{}` s'il est absent ou illisible.

    Un dictionnaire vide fait que toutes les fonctions ci-dessous rendent des
    structures vides. C'est à la règle appelante de traduire « rien lu » en
    `NA`, jamais en `OK` — l'absence de preuve n'est pas une conformité.

    Le résultat est mémorisé : les cinq fonctions publiques de ce module
    appellent chacune `_load_report`, et un `report.json` réel pèse plusieurs
    mégaoctets. Sans mémorisation, le contexte le relisait et le re-décodait
    cinq fois, contrairement au principe de lecture unique du projet.

    Ce n'est PAS le poste de coût dominant d'une analyse : sur un rapport de
    4 Mo, la mémorisation n'a pas changé le temps total de façon mesurable.
    Elle reste justifiée par le principe, pas par le gain.
    """
    if not is_legacy_report(report_path):
        return {}
    assert report_path is not None
    path = report_path / REPORT_FILE_NAME
    try:
        stat = path.stat()
    except OSError:
        return {}
    return _load_report_cached(path, stat.st_mtime, stat.st_size)


def _decode_embedded(raw: Any) -> Any:
    """Décode une valeur qui peut être soit du JSON déjà désérialisé, soit une
    CHAÎNE contenant du JSON — les deux se rencontrent selon la version de
    Power BI Desktop ayant produit le fichier. Retourne `None` si la chaîne
    n'est pas du JSON valide, jamais une exception : un fragment corrompu ne
    doit pas empêcher de lire le reste du rapport.
    """
    if isinstance(raw, str):
        if not raw.strip():
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None
    return raw


def _alias_map(query: Any) -> dict[str, str]:
    """Table alias -> entité déclarée par la clause `From` d'un query.

    `[{"Name": "m", "Entity": "Mesures"}]` donne `{"m": "Mesures"}`.
    """
    aliases: dict[str, str] = {}
    if not isinstance(query, dict):
        return aliases
    for source in query.get("From") or []:
        if isinstance(source, dict):
            name = source.get("Name")
            entity = source.get("Entity")
            if isinstance(name, str) and isinstance(entity, str):
                aliases[name] = entity
    return aliases


def _iter_source_aliases(node: Any) -> list[tuple[str, str | None, str | None]]:
    """Comme `_iter_field_references`, mais rend l'ALIAS `SourceRef.Source`
    au lieu de l'entité. Nécessaire parce que le format legacy référence les
    tables indirectement.
    """
    found: list[tuple[str, str | None, str | None]] = []

    if isinstance(node, dict):
        for kind in ("Column", "Measure"):
            inner = node.get(kind)
            if isinstance(inner, dict):
                source_ref = inner.get("Expression", {})
                if isinstance(source_ref, dict):
                    source_ref = source_ref.get("SourceRef", {})
                alias = source_ref.get("Source") if isinstance(source_ref, dict) else None
                found.append((kind, alias, inner.get("Property")))
        for value in node.values():
            found.extend(_iter_source_aliases(value))
    elif isinstance(node, list):
        for value in node:
            found.extend(_iter_source_aliases(value))

    return found


def _resolve_field_references(node: Any, query: Any = None) -> list[tuple[str, str | None, str | None]]:
    """Références (kind, entity, property) d'un fragment legacy, alias résolus.

    Deux formes cohabitent dans un même fichier : `SourceRef.Entity` (direct,
    utilisé par les expressions de filtre) et `SourceRef.Source` (alias,
    utilisé par les `prototypeQuery`). Les deux sont collectées, puis
    dédoublonnées en conservant l'ordre — une même colonne peut apparaître
    dans `Select` et dans `OrderBy` sans devoir être comptée deux fois.

    Un même nœud est vu par les DEUX collecteurs : celui qui lit `Entity` en
    sort avec `entity=None` (il n'y a pas d'`Entity` sur une référence par
    alias), celui qui lit `Source` en sort avec l'entité résolue. Garder les
    deux ferait passer un champ parfaitement résolu pour une référence
    inconnue — et, pour BP-32, transformerait chaque agrégation en un
    `UNKNOWN_AGGREGATION` fantôme. Une référence `(kind, None, prop)` est donc
    supprimée dès qu'une référence résolue existe pour le même `(kind, prop)`.
    """
    aliases = _alias_map(query if query is not None else node)

    references: list[tuple[str, str | None, str | None]] = list(_iter_field_references(node))
    for kind, alias, prop in _iter_source_aliases(node):
        entity = aliases.get(alias) if alias else None
        references.append((kind, entity, prop))

    resolved = {(kind, prop) for kind, entity, prop in references if entity is not None}

    seen: set[tuple[str, str | None, str | None]] = set()
    unique: list[tuple[str, str | None, str | None]] = []
    for reference in references:
        kind, entity, prop = reference
        if entity is None and (kind, prop) in resolved:
            continue
        # Une référence qui reste non résolue est conservée : elle signale à la
        # règle qu'un champ existe sans pouvoir être rattaché à sa table.
        if reference not in seen:
            seen.add(reference)
            unique.append(reference)
    return unique


def _iter_visual_containers(document: dict[str, Any]) -> list[tuple[str, dict[str, Any], dict[str, Any]]]:
    """Aplatit le rapport en (page_id, conteneur brut, configuration décodée).

    `page_id` est le `name` technique de la section, jamais son `displayName` :
    c'est lui que portent les interactions et les signets.
    """
    containers: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    for section in document.get("sections") or []:
        if not isinstance(section, dict):
            continue
        page_id = str(section.get("name") or "")
        for container in section.get("visualContainers") or []:
            if not isinstance(container, dict):
                continue
            config = _decode_embedded(container.get("config"))
            containers.append((page_id, container, config if isinstance(config, dict) else {}))
    return containers


def _visual_identity(config: dict[str, Any]) -> tuple[str, dict[str, Any], bool]:
    """(identifiant, bloc visuel, est_un_groupe) d'un conteneur.

    Un groupe porte `singleVisualGroup` ; un visuel ordinaire `singleVisual`.
    """
    single_group = config.get("singleVisualGroup")
    if isinstance(single_group, dict):
        return str(config.get("name") or ""), single_group, True
    single = config.get("singleVisual")
    return str(config.get("name") or ""), single if isinstance(single, dict) else {}, False


def parse_report_field_references(report_path: Path | None) -> "set[tuple[str, str, str]]":
    """Toutes les références de champ du rapport, toutes surfaces confondues.

    Même contrat que la fonction homonyme du parseur PBIR : BP-07 a seulement
    besoin de savoir si un champ est référencé QUELQUE PART.
    """
    document = _load_report(report_path)
    if not document:
        return set()

    references: set[tuple[str, str, str]] = set()

    def collect(node: Any, query: Any = None) -> None:
        for kind, entity, prop in _resolve_field_references(node, query):
            if entity and prop:
                references.add((kind, entity, prop))

    # Filtres de rapport, puis tout ce que portent les pages et les visuels.
    collect(_decode_embedded(document.get("filters")) or [])
    collect(_decode_embedded(document.get("config")) or {})

    for section in document.get("sections") or []:
        if not isinstance(section, dict):
            continue
        collect(_decode_embedded(section.get("filters")) or [])
        for container in section.get("visualContainers") or []:
            if not isinstance(container, dict):
                continue
            collect(_decode_embedded(container.get("filters")) or [])
            config = _decode_embedded(container.get("config"))
            if not isinstance(config, dict):
                continue
            _, visual, _ = _visual_identity(config)
            collect(config, visual.get("prototypeQuery"))

    return references


def parse_report_implicit_aggregations(report_path: Path | None) -> "list[dict]":
    """Agrégations implicites sérialisées dans les visuels (signature de BP-32).

    Dans le format legacy, une mesure implicite se lit dans le `Select` du
    `prototypeQuery` : un nœud `Aggregation` appliqué à une `Column`. Une
    colonne SANS `Aggregation` reste neutre — axe, slicer, ligne de tableau —
    et n'est jamais remontée.
    """
    document = _load_report(report_path)
    if not document:
        return []

    source_file = str(report_path / REPORT_FILE_NAME) if report_path else ""
    aggregations: list[dict] = []

    for page_id, _container, config in _iter_visual_containers(document):
        visual_id, visual, is_group = _visual_identity(config)
        if is_group:
            continue
        query = visual.get("prototypeQuery")
        if not isinstance(query, dict):
            continue
        for item in query.get("Select") or []:
            if not isinstance(item, dict):
                continue
            aggregation = item.get("Aggregation")
            if not isinstance(aggregation, dict):
                continue

            expression = aggregation.get("Expression") or {}
            columns = [
                (entity, prop)
                for kind, entity, prop in _resolve_field_references(expression, query)
                if kind == "Column" and prop
            ]
            function = aggregation.get("Function")

            if columns:
                for entity, prop in columns:
                    aggregations.append(
                        {
                            "visual_id": visual_id,
                            "visual_type": visual.get("visualType"),
                            "page_id": page_id,
                            "table": entity,
                            "column": prop,
                            "aggregation_function_raw": function,
                            "source_file": source_file,
                        }
                    )
            else:
                # Agrégation dont la cible n'est pas une colonne résolue :
                # `UNKNOWN_AGGREGATION` (§6 de BP-32). Ne prouve rien, mais
                # empêche de conclure OK — d'où sa remontée avec table/colonne
                # à None plutôt que son omission silencieuse.
                aggregations.append(
                    {
                        "visual_id": visual_id,
                        "visual_type": visual.get("visualType"),
                        "page_id": page_id,
                        "table": None,
                        "column": None,
                        "aggregation_function_raw": function,
                        "source_file": source_file,
                    }
                )
    return aggregations


def parse_report_visuals(report_path: Path | None) -> "list[dict]":
    """Inventaire des visuels avec leur signature analytique canonique (BP-41).

    La signature est (type, références projetées triées) — indépendante de
    l'identifiant, de la page, de la position et de la taille, exactement
    comme dans le parseur PBIR, pour que les deux formats produisent des
    signatures comparables.
    """
    document = _load_report(report_path)
    if not document:
        return []

    source_file = str(report_path / REPORT_FILE_NAME) if report_path else ""
    visuals: list[dict] = []

    for page_id, container, config in _iter_visual_containers(document):
        visual_id, visual, is_group = _visual_identity(config)
        visual_type = "visualGroup" if is_group else visual.get("visualType")
        query = visual.get("prototypeQuery")

        references = sorted(
            {
                f"{kind}:{entity}[{prop}]"
                for kind, entity, prop in _resolve_field_references(query or {}, query)
                if entity and prop
            }
        )

        signature = None
        if not is_group and visual_type not in NON_ANALYTICAL_VISUAL_TYPES and references:
            signature = (visual_type, tuple(references))

        visuals.append(
            {
                "visual_id": visual_id,
                "page_id": page_id,
                "visual_type": visual_type,
                "is_group": is_group,
                # Le format legacy ne sérialise pas d'indicateur de visuel
                # masqué au niveau du conteneur : la visibilité est portée par
                # les signets. False signifie donc « non démontré masqué ».
                "is_hidden": False,
                "parent_group": config.get("parentGroupName"),
                "position": {
                    "x": container.get("x"),
                    "y": container.get("y"),
                    "z": container.get("z"),
                    "width": container.get("width"),
                    "height": container.get("height"),
                },
                "field_references": references,
                "signature": signature,
                "source_file": source_file,
            }
        )

    return visuals


def _collect_bookmarks(
    items: Any, accumulator: list[tuple[str | None, list[str]]], names: set[str]
) -> None:
    """Aplatit l'arbre des signets en (nom, [noms des enfants]).

    Les signets legacy sont hiérarchiques : un groupe porte `children`. La
    même forme est produite que par `bookmarks.json` en PBIR, pour que BP-37
    n'ait pas à distinguer les deux.
    """
    if not isinstance(items, list):
        return
    for item in items:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        children_raw = item.get("children") or []
        children = [
            str(child.get("name"))
            for child in children_raw
            if isinstance(child, dict) and child.get("name")
        ]
        if isinstance(name, str):
            names.add(name)
        accumulator.append((name, children))
        _collect_bookmarks(children_raw, accumulator, names)


def parse_report_structure(report_path: Path | None) -> "dict":
    """Structure du rapport nécessaire aux contrôles d'intégrité (BP-37/BP-38).

    Retourne les mêmes clés que le parseur PBIR : `visuals`, `groups`,
    `parent_links`, `interactions`, `bookmark_files`, `bookmark_items`,
    `bookmarks_metadata_present`.
    """
    structure: dict[str, Any] = {
        "visuals": {},
        "groups": {},
        "parent_links": [],
        "interactions": [],
        "bookmark_files": set(),
        "bookmark_items": [],
        "bookmarks_metadata_present": False,
    }

    document = _load_report(report_path)
    if not document:
        return structure

    for section in document.get("sections") or []:
        if not isinstance(section, dict):
            continue
        page_id = str(section.get("name") or "")
        structure["visuals"].setdefault(page_id, set())
        structure["groups"].setdefault(page_id, set())

        for container in section.get("visualContainers") or []:
            if not isinstance(container, dict):
                continue
            config = _decode_embedded(container.get("config"))
            if not isinstance(config, dict):
                continue
            visual_id, _visual, is_group = _visual_identity(config)
            if not visual_id:
                continue
            structure["visuals"][page_id].add(visual_id)
            if is_group:
                structure["groups"][page_id].add(visual_id)
            parent = config.get("parentGroupName")
            if parent:
                structure["parent_links"].append((page_id, visual_id, parent))

        section_config = _decode_embedded(section.get("config"))
        if isinstance(section_config, dict):
            for relationship in section_config.get("relationships") or []:
                if isinstance(relationship, dict):
                    structure["interactions"].append(
                        (
                            page_id,
                            relationship.get("source"),
                            relationship.get("target"),
                            relationship.get("type"),
                        )
                    )

    report_config = _decode_embedded(document.get("config"))
    if isinstance(report_config, dict):
        bookmarks = report_config.get("bookmarks")
        if isinstance(bookmarks, list):
            # `bookmarks_metadata_present` marque « la déclaration des signets
            # existe », pas « il y a des signets » : une liste vide déclarée
            # reste une déclaration, ce que BP-37 distingue d'une absence.
            structure["bookmarks_metadata_present"] = True
            names: set[str] = set()
            _collect_bookmarks(bookmarks, structure["bookmark_items"], names)
            structure["bookmark_files"] = names

    return structure


def parse_report_filters(report_path: Path | None) -> list[ReportFilterDef]:
    """Filtres déclarés aux trois niveaux : rapport, page, visuel (BP-39).

    Dans le format legacy, chaque niveau porte une clé `filters` contenant une
    CHAÎNE JSON. Le champ filtré est dans `expression`, et son type dans
    `type` — mêmes rôles que `field` et `type` du `filterConfig` PBIR.
    """
    document = _load_report(report_path)
    if not document:
        return []

    assert report_path is not None
    path = report_path / REPORT_FILE_NAME
    try:
        # Découpé UNE fois pour tous les filtres du rapport : `_find_line_of_name`
        # est appelée une fois par filtre, et il y en a plus d'un millier.
        raw_lines = path.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        raw_lines = []
    source_file = str(path)

    filters: list[ReportFilterDef] = []

    def collect(raw: Any, level: str, page_id: str | None, visual_id: str | None) -> None:
        entries = _decode_embedded(raw)
        if not isinstance(entries, list):
            return
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            name = str(entry.get("name", ""))
            references = _resolve_field_references(entry.get("expression", {}), entry.get("filter"))
            filters.append(
                ReportFilterDef(
                    name=name,
                    level=level,
                    page_id=page_id,
                    visual_id=visual_id,
                    filter_type=entry.get("type"),
                    field_references=references,
                    source_file=source_file,
                    line=_find_line_of_name(raw_lines, name),
                )
            )

    collect(document.get("filters"), "report", None, None)

    for section in document.get("sections") or []:
        if not isinstance(section, dict):
            continue
        page_id = str(section.get("name") or "")
        collect(section.get("filters"), "page", page_id, None)
        for container in section.get("visualContainers") or []:
            if not isinstance(container, dict):
                continue
            config = _decode_embedded(container.get("config"))
            visual_id = str(config.get("name") or "") if isinstance(config, dict) else None
            collect(container.get("filters"), "visual", page_id, visual_id)

    return filters
