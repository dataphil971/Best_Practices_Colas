"""BP-32 — Utiliser des mesures explicites plutôt que des agrégations implicites.

Implémente l'algorithme documenté dans
Agent_BI/01_ALGORITHMES/32_ExplicitMeasures.md. Toute évolution de la logique
OK/KO/NA doit d'abord être répercutée dans ce document — ce fichier ne doit
jamais diverger silencieusement de sa spécification fonctionnelle.

Signal déterministe recherché (§3) : un nœud `Aggregation` appliqué à une
`Column` dans le PBIR. C'est la sérialisation d'une mesure implicite.

INTERDIT et non implémenté (§1, §5, §7) : déduire une agrégation du nom d'une
zone (`Values`, `Y`...), du type de visuel, ou de la seule présence d'une
colonne dans une projection. Une colonne SANS nœud `Aggregation` est neutre —
axe, slicer, ligne de tableau ou filtre — jamais un KO.
"""

from engine.context import AnalysisContext
from engine.models import Finding, RuleResult

RULE_ID = "BP-32"
RULE_NAME = "Utiliser des mesures explicites plutôt que des agrégations implicites"


def check(context: AnalysisContext) -> RuleResult:
    if context.report_path is None:
        # §9 : l'absence d'agrégation implicite ne peut être déclarée OK que
        # si la couverture de parsing est complète. Sans rapport, rien n'a
        # été parcouru — NA, jamais OK.
        return RuleResult(
            rule_id=RULE_ID,
            rule_name=RULE_NAME,
            execution_status="PARTIAL",
            rule_status="NA",
            summary={
                "reason": "Aucun dossier <Nom>.Report/ trouvé : couverture PBIR nulle",
                "implicit_aggregation_count": 0,
            },
        )

    aggregations = context.report_implicit_aggregations
    findings = []
    resolved = []
    unresolved = []

    for item in aggregations:
        object_name = f"{item['page_id']}/{item['visual_id']}"
        if item["table"] and item["column"]:
            object_name += f"::{item['table']}[{item['column']}]"
            resolved.append(item)
            findings.append(
                Finding(
                    rule_id=RULE_ID,
                    object_type="visual_field",
                    object=object_name,
                    expected="mesure explicite",
                    actual=f"agrégation implicite (Function={item['aggregation_function_raw']})",
                    status="KO",
                    reason="Agrégation appliquée à une colonne dans le rapport",
                    evidence=item,
                )
            )
        else:
            # §6 : `UNKNOWN_AGGREGATION` — agrégation dont la cible n'est pas
            # une colonne résolue. Ne prouve rien, empêche de conclure OK.
            unresolved.append(item)
            findings.append(
                Finding(
                    rule_id=RULE_ID,
                    object_type="visual_field",
                    object=object_name,
                    expected="mesure explicite",
                    actual=None,
                    status="NA",
                    reason="Agrégation dont la cible n'est pas une colonne résolue",
                    evidence=item,
                )
            )

    if resolved:
        rule_status = "KO"
    elif unresolved:
        rule_status = "NA"
    else:
        rule_status = "OK"

    return RuleResult(
        rule_id=RULE_ID,
        rule_name=RULE_NAME,
        execution_status="SUCCESS",
        rule_status=rule_status,
        findings=findings,
        summary={
            "implicit_aggregation_count": len(resolved),
            "unresolved_aggregation_count": len(unresolved),
            "ko_details": [f.to_dict() for f in findings if f.status == "KO"],
        },
    )
