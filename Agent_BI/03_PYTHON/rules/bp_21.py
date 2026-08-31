"""BP-21 — Noms d'objets concis, cohérents et conformes à la convention du modèle.

Implémente l'algorithme documenté dans
Agent_BI/01_ALGORITHMES/21_ConciseNames.md (§3.3 regex, §7 pseudo-code).
Toute évolution de la logique OK/KO/NA doit d'abord être répercutée dans ce
document — ce fichier ne doit jamais diverger silencieusement de sa
spécification fonctionnelle.

Les noms ne sont JAMAIS `.strip()`és avant contrôle (§6 de l'algorithme) :
c'est précisément la présence d'un espace superflu dans le nom réel qui
constitue l'anomalie à signaler.

Une colonne masquée est HORS PÉRIMÈTRE (§4.1) : son nom n'est vu de personne,
et la convention ne lui est pas appliquée dans les modèles réels. Le motif est
celui de `bp_07.py`, mot pour mot — deux règles qui répondraient différemment à
« une colonne masquée est-elle jugée ? » seraient deux dialectes dans un même
dépôt.
"""

import re

from engine.context import AnalysisContext
from engine.models import Finding, RuleResult, SourceLocation
from rules import bp_07

RULE_ID = "BP-21"
RULE_NAME = "Noms d'objets concis, cohérents et conformes à la convention du modèle"

#: Motif d'exclusion d'une colonne masquée. Partagé mot pour mot avec
#: `bp_07.py` : le jour où l'un des deux change, l'autre doit changer aussi.
HIDDEN_COLUMN_REASON = bp_07.HIDDEN_COLUMN_REASON

TABLE_NAME_PATTERN = re.compile(r"^(D_|F_|T_|P_)[A-Z0-9]+(_[A-Z0-9]+)*$")
TABLE_NAME_EXEMPTIONS = {"MEASURE"}
COLUMN_NAME_PATTERN = re.compile(r"^[A-Z0-9]+(_[A-Z0-9]+)*$")
MEASURE_NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
LEADING_OR_TRAILING_WHITESPACE = re.compile(r"^\s|\s$")
INTERNAL_WHITESPACE = re.compile(r"\s")
SPECIAL_CHAR_PATTERN = re.compile(r"[^\w\s]", re.UNICODE)


def _check_table_name(name: str) -> "tuple[str, str] | None":
    """Retourne (status, reason) si KO, None si OK."""
    if name in TABLE_NAME_EXEMPTIONS:
        return None
    if LEADING_OR_TRAILING_WHITESPACE.search(name):
        return ("KO", "Espace en début ou fin de nom de table")
    if not TABLE_NAME_PATTERN.match(name):
        return ("KO", "Préfixe de table non reconnu (attendu D_/F_/T_/P_)")
    return None


def _check_column_name(name: str) -> "tuple[str, str] | None":
    if LEADING_OR_TRAILING_WHITESPACE.search(name):
        return ("KO", "Espace en début ou fin de nom de colonne")
    if SPECIAL_CHAR_PATTERN.search(name.replace("_", "")):
        return ("KO", "Caractère spécial ambigu dans le nom de colonne")
    if INTERNAL_WHITESPACE.search(name):
        return ("KO", "Espace interne dans le nom de colonne (attendu UPPER_SNAKE_CASE)")
    if not COLUMN_NAME_PATTERN.match(name):
        return ("KO", "Casse ou format non conforme à la convention UPPER_SNAKE_CASE")
    return None


def _check_measure_name(name: str) -> "tuple[str, str] | None":
    if LEADING_OR_TRAILING_WHITESPACE.search(name):
        return ("KO", "Espace en début ou fin de nom de mesure")
    if INTERNAL_WHITESPACE.search(name):
        return ("KO", "Espace interne toléré en DAX mais incohérent avec la convention du modèle")
    if not MEASURE_NAME_PATTERN.match(name):
        return ("KO", "Caractère spécial ambigu dans le nom de mesure")
    return None


def _check_display_folder_whitespace(value: str) -> "tuple[str, str] | None":
    if LEADING_OR_TRAILING_WHITESPACE.search(value):
        return ("KO", "Espace en début ou fin de displayFolder")
    return None


def check(context: AnalysisContext) -> RuleResult:
    if not context.tables:
        return RuleResult(
            rule_id=RULE_ID,
            rule_name=RULE_NAME,
            execution_status="ERROR",
            rule_status="NA",
            summary={"reason": "Aucun fichier de table TMDL trouvé"},
        )

    findings = []
    ko_details = []
    total_tables = total_columns = total_measures = 0
    hidden_columns = 0

    # displayFolder : regroupés par (table, valeur normalisée en casse) pour
    # détecter une casse incohérente entre dossiers du même niveau (§4 étape 4).
    folders_by_table: dict[str, dict[str, list[tuple[str, str]]]] = {}

    def _record(status_reason, object_type, object_name, evidence, location=None, remediation=""):
        if status_reason is None:
            findings.append(
                Finding(
                    rule_id=RULE_ID,
                    object_type=object_type,
                    object=object_name,
                    expected="convention de nommage respectée",
                    actual=None,
                    status="OK",
                    evidence=evidence,
                    location=location,
                )
            )
        else:
            status, reason = status_reason
            # `actual` reste `None` : le nom fautif est déjà `object`, le
            # répéter n'apporterait rien — c'est `reason` qui porte
            # l'information utile (nature précise de l'anomalie détectée).
            findings.append(
                Finding(
                    rule_id=RULE_ID,
                    object_type=object_type,
                    object=object_name,
                    expected="convention de nommage respectée",
                    actual=None,
                    status=status,
                    reason=reason,
                    evidence=evidence,
                    location=location,
                    explanation=(
                        "Un nom hors convention se voit dans le volet des champs de tous les "
                        "utilisateurs et dans chaque formule qui le référence. Un espace de tête "
                        "ou de fin est le cas le plus coûteux : deux noms visuellement identiques "
                        "deviennent techniquement différents, ce qui provoque des erreurs "
                        "silencieuses de correspondance."
                    ),
                    remediation=remediation,
                )
            )
            ko_details.append(
                {
                    "object_type": object_type,
                    "object_name": object_name,
                    "reason": reason,
                }
            )

    for table in context.tables:
        total_tables += 1
        evidence = {"table": table.name, "source_file": table.source_file}
        _record(
            _check_table_name(table.name),
            "table",
            table.name,
            evidence,
            location=SourceLocation.from_file(table.source_file, table.line),
            remediation=(
                f"Renommer la table `{table.name}` avec un préfixe du référentiel "
                "(D_ dimension, F_ fait, T_ technique, P_ paramétrage), puis reporter le "
                "nouveau nom dans relationships.tmdl et dans les mesures DAX qui la citent."
            ),
        )

        for column in table.columns:
            total_columns += 1
            object_name = f"{table.name}.{column.raw_name}"
            evidence = {
                "table": table.name,
                "column": column.raw_name,
                "source_file": column.source_file,
            }

            # §4.1 : hors périmètre. Le constat est émis quand même — un objet
            # écarté en silence serait indiscernable d'un objet oublié — mais
            # en `NA`, et il ne compte pas dans le statut global.
            if column.get_property("isHidden"):
                hidden_columns += 1
                findings.append(
                    Finding(
                        rule_id=RULE_ID,
                        object_type="column",
                        object=object_name,
                        expected="convention de nommage respectée",
                        actual="masquée",
                        status="NA",
                        reason=HIDDEN_COLUMN_REASON,
                        evidence=evidence,
                    )
                )
                continue

            _record(
                _check_column_name(column.name),
                "column",
                object_name,
                evidence,
                location=column.locate(context_lines=1),
                remediation=(
                    f"Renommer la colonne `{column.raw_name}` en UPPER_SNAKE_CASE sans espace "
                    f"(ligne {column.line} de {column.source_file}), puis reporter le nouveau "
                    "nom partout où elle est référencée : relationships.tmdl, mesures DAX, "
                    "sortByColumn et champs du rapport."
                ),
            )

            folder = column.get_property("displayFolder")
            if folder is not None and str(folder) != "":
                folders_by_table.setdefault(table.name, {}).setdefault(str(folder).lower(), []).append(
                    (str(folder), object_name)
                )

        for measure in table.measures:
            total_measures += 1
            object_name = f"{table.name}.{measure.raw_name}"
            evidence = {
                "table": table.name,
                "measure": measure.raw_name,
                "source_file": measure.source_file,
            }
            _record(
                _check_measure_name(measure.name),
                "measure",
                object_name,
                evidence,
                location=measure.locate(context_lines=1),
                remediation=(
                    f"Renommer la mesure `{measure.raw_name}` sans espace ni caractère "
                    f"spécial (ligne {measure.line} de {measure.source_file}), puis reporter "
                    "le nouveau nom dans les mesures DAX qui l'appellent et dans les visuels "
                    "du rapport qui l'affichent."
                ),
            )

            folder = measure.get_property("displayFolder")
            if folder is not None and str(folder) != "":
                folders_by_table.setdefault(table.name, {}).setdefault(str(folder).lower(), []).append(
                    (str(folder), object_name)
                )

    for table_name, groups in folders_by_table.items():
        for entries in groups.values():
            distinct_raw = {raw for raw, _obj in entries}
            for raw, object_name in entries:
                whitespace_issue = _check_display_folder_whitespace(raw)
                if whitespace_issue is not None:
                    ko_details.append(
                        {
                            "object_type": "displayFolder",
                            "object_name": f"{table_name}::{object_name}",
                            "reason": whitespace_issue[1],
                        }
                    )
                    findings.append(
                        Finding(
                            rule_id=RULE_ID,
                            object_type="displayFolder",
                            object=f"{table_name}::{object_name}",
                            expected="displayFolder sans espace superflu, casse cohérente",
                            actual=raw,
                            status="KO",
                            reason=whitespace_issue[1],
                            evidence={"table": table_name, "display_folder": raw},
                        )
                    )
                elif len(distinct_raw) > 1:
                    reason = (
                        f"Casse de displayFolder incohérente dans la table {table_name} : "
                        f"{sorted(distinct_raw)} désignent le même dossier"
                    )
                    ko_details.append(
                        {
                            "object_type": "displayFolder",
                            "object_name": f"{table_name}::{object_name}",
                            "reason": reason,
                        }
                    )
                    findings.append(
                        Finding(
                            rule_id=RULE_ID,
                            object_type="displayFolder",
                            object=f"{table_name}::{object_name}",
                            expected="casse cohérente entre dossiers de même niveau",
                            actual=raw,
                            status="KO",
                            reason=reason,
                            evidence={
                                "table": table_name,
                                "display_folder": raw,
                                "variants": sorted(distinct_raw),
                            },
                        )
                    )

    ok_count = sum(1 for f in findings if f.status == "OK")
    rule_status = "KO" if ko_details else "OK"

    return RuleResult(
        rule_id=RULE_ID,
        rule_name=RULE_NAME,
        execution_status="SUCCESS",
        rule_status=rule_status,
        findings=findings,
        summary={
            "total_tables": total_tables,
            "total_columns": total_columns,
            "total_measures": total_measures,
            # Rendu explicite : sans ce compte, un modèle dont presque tout est
            # masqué donnerait un `OK` sans qu'on voie sur quoi il porte.
            "hidden_columns_out_of_scope": hidden_columns,
            "ok_objects": ok_count,
            "ko_objects": len(ko_details),
            "ko_details": ko_details,
        },
    )
