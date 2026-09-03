"""BP-25 — Masquer les champs techniques démontrés.

Implémente l'algorithme documenté dans
Agent_BI/01_ALGORITHMES/25_HideTechnicalFields.md. Toute évolution de la
logique OK/KO/NA doit d'abord être répercutée dans ce document — ce fichier
ne doit jamais diverger silencieusement de sa spécification fonctionnelle.

PORTÉE PARTIELLE ASSUMÉE. Le §8 énumère quatre voies vers
`TECHNICAL_CONFIRMED` ; une seule est disponible ici :

  1. `company_policy.is_explicit_technical_field` — pas de policy dans ce
     dépôt. Non implémenté.
  2. annotation technique de gouvernance — n'existe pas. Non implémenté.
  3. **clé de tri exclusive (§4.1)** — calculable via l'index d'usage
     partagé. IMPLÉMENTÉ : une colonne qui sert de cible `sortByColumn` et
     n'a AUCUN autre usage (ni DAX, ni relation, ni rapport) est démontrée
     purement technique.
  4. colonne de support d'une table de mesures — exige la classification de
     BP-24, non implémentée. Non implémenté.

Conséquence : la règle ne conclut que sur les clés de tri exclusives. Toute
autre colonne reste `UNKNOWN` -> NA, jamais présumée technique.

§5 est respecté : un nom en `_ID`/`_KEY`, le seul fait d'être clé de
relation, ou l'absence d'usage dans le rapport courant ne suffisent JAMAIS —
aucun de ces signaux faibles n'est exploité comme preuve.

COUVERTURE : sans dossier `.Report/`, on ne peut pas démontrer l'absence
d'usage utilisateur (§6) — la règle rend alors NA sans aucun KO.
"""

from engine.context import AnalysisContext
from engine.models import Finding, RuleResult
from engine.usage_index import build_usage_index

RULE_ID = "BP-25"
RULE_NAME = "Masquer les champs techniques démontrés"

# Surfaces qui, seules, ne disqualifient pas une clé de tri exclusive.
_SORT_SURFACES = {"sort_by"}


def check(context: AnalysisContext) -> RuleResult:
    if not context.tables:
        return RuleResult(
            rule_id=RULE_ID,
            rule_name=RULE_NAME,
            execution_status="ERROR",
            rule_status="NA",
            summary={"reason": "Aucun fichier de table TMDL trouvé"},
        )

    if context.report_path is None:
        return RuleResult(
            rule_id=RULE_ID,
            rule_name=RULE_NAME,
            execution_status="PARTIAL",
            rule_status="NA",
            summary={
                "reason": "Rapport absent : absence d'usage utilisateur non démontrable",
                "technical_columns": 0,
                "visible_technical_columns": 0,
            },
        )

    usage, _dax_unqualified = build_usage_index(context)

    findings = []
    ko_details = []
    technical_count = 0

    for table in context.tables:
        for column in table.columns:
            object_name = f"{table.name}.{column.raw_name}"
            surfaces = set(usage.get((table.name, column.name), []))

            is_exclusive_sort_key = bool(surfaces) and surfaces <= _SORT_SURFACES
            if not is_exclusive_sort_key:
                # §9 : `BUSINESS_OR_USER_FACING` comme `UNKNOWN` -> NA. On ne
                # distingue pas les deux : aucune n'est évaluable ici.
                findings.append(
                    Finding(
                        rule_id=RULE_ID,
                        object_type="column",
                        object=object_name,
                        expected="isHidden si techniquement démontré",
                        actual=None,
                        status="NA",
                        reason="La colonne n'est pas démontrée comme purement technique",
                        evidence={
                            "table": table.name,
                            "column": column.raw_name,
                            "usages": sorted(surfaces),
                        },
                    )
                )
                continue

            technical_count += 1
            hidden = bool(column.get_property("isHidden"))
            evidence = {
                "table": table.name,
                "column": column.raw_name,
                "role": "TECHNICAL_CONFIRMED",
                "role_evidence": "clé de tri exclusive (aucun autre usage détecté)",
                "usages": sorted(surfaces),
                "source_file": column.source_file,
            }

            if hidden:
                findings.append(
                    Finding(
                        rule_id=RULE_ID,
                        object_type="column",
                        object=object_name,
                        expected="isHidden",
                        actual="isHidden",
                        status="OK",
                        evidence=evidence,
                    )
                )
            else:
                findings.append(
                    Finding(
                        rule_id=RULE_ID,
                        object_type="column",
                        object=object_name,
                        expected="isHidden",
                        actual="visible",
                        status="KO",
                        reason="Colonne purement technique (clé de tri exclusive) laissée visible",
                        evidence=evidence,
                        location=column.locate(context_lines=1),
                        explanation=(
                            "Cette colonne ne sert QUE à ordonner une autre colonne (sortByColumn) : "
                            "elle n'a aucune signification métier. Laissée visible, elle encombre le "
                            "volet des champs et un utilisateur peut la glisser dans un visuel par "
                            "erreur, obtenant un axe numérique sans valeur analytique."
                        ),
                        remediation=(
                            f"Ajouter `isHidden` au bloc `column {column.raw_name}` "
                            f"(ligne {column.line} de {column.source_file}). Le tri qu'elle pilote "
                            "continue de fonctionner : une colonne masquée reste utilisable comme "
                            "sortByColumn."
                        ),
                    )
                )
                ko_details.append({"table": table.name, "column": column.raw_name})

    # §11 : seules les colonnes TECHNICAL_CONFIRMED sont évaluables.
    if ko_details:
        rule_status = "KO"
    elif technical_count:
        rule_status = "OK"
    else:
        rule_status = "NA"

    return RuleResult(
        rule_id=RULE_ID,
        rule_name=RULE_NAME,
        execution_status="SUCCESS",
        rule_status=rule_status,
        findings=findings,
        summary={
            "technical_columns": technical_count,
            "visible_technical_columns": len(ko_details),
            "ko_details": ko_details,
        },
    )
