"""BP-38 — Éliminer les interactions croisées inutiles.

Implémente l'algorithme documenté dans
Agent_BI/01_ALGORITHMES/38_EliminateVisualInteractions.md. Toute évolution de
la logique OK/KO/NA doit d'abord être répercutée dans ce document — ce
fichier ne doit jamais diverger silencieusement de sa spécification
fonctionnelle.

PORTÉE PARTIELLE ASSUMÉE. Le §1 énonce lui-même les deux dimensions de la
règle :

  1. COHÉRENCE TECHNIQUE des références d'interaction — « La première est
     déterministe. » Implémentée ici (§4).
  2. PERTINENCE FONCTIONNELLE d'une interaction — « nécessite une politique
     ou une revue contextuelle ». NON implémentée : sans matrice de policy
     ni reviewer, le document impose NA.

Conséquence : cette règle ne dit jamais qu'une interaction est INUTILE, elle
dit seulement si les interactions déclarées pointent vers des visuels qui
existent. Ne pas la « compléter » par une heuristique de pertinence.

§3 est respecté : l'ABSENCE d'une entrée `visualInteractions` n'est jamais
interprétée — ni comme une interaction active et inutile, ni comme une
interaction non revue.
"""

from engine.context import AnalysisContext
from engine.models import Finding, RuleResult

RULE_ID = "BP-38"
RULE_NAME = "Éliminer les interactions croisées inutiles"


def check(context: AnalysisContext) -> RuleResult:
    if context.report_path is None:
        return RuleResult(
            rule_id=RULE_ID,
            rule_name=RULE_NAME,
            execution_status="PARTIAL",
            rule_status="NA",
            summary={
                "reason": "Aucun dossier <Nom>.Report/ trouvé : interactions non analysables",
                "total_interactions": 0,
            },
        )

    structure = context.report_structure
    interactions = structure.get("interactions", [])

    if not interactions:
        # §3 : ne rien conclure de l'absence d'entrées sérialisées.
        return RuleResult(
            rule_id=RULE_ID,
            rule_name=RULE_NAME,
            execution_status="SUCCESS",
            rule_status="NA",
            summary={
                "reason": "Aucune interaction sérialisée : rien à contrôler",
                "total_interactions": 0,
                "broken_interactions": 0,
            },
        )

    findings = []
    for page_id, source, target, interaction_type in interactions:
        object_name = f"{page_id}/{source}->{target}"
        page_visuals = structure.get("visuals", {}).get(page_id, set())
        evidence = {"page": page_id, "source": source, "target": target, "type": interaction_type}

        missing = [
            label
            for label, value in (("source", source), ("target", target))
            if not value or value not in page_visuals
        ]

        if missing:
            findings.append(
                Finding(
                    rule_id=RULE_ID,
                    object_type="interaction",
                    object=object_name,
                    expected="source et target existants sur la page",
                    actual=", ".join(f"{m} introuvable" for m in missing),
                    status="KO",
                    reason="Interaction référençant un visuel inexistant",
                    evidence={**evidence, "missing": missing},
                )
            )
        else:
            findings.append(
                Finding(
                    rule_id=RULE_ID,
                    object_type="interaction",
                    object=object_name,
                    expected="source et target existants sur la page",
                    actual=interaction_type,
                    status="OK",
                    evidence=evidence,
                )
            )

    ko = [f for f in findings if f.status == "KO"]
    rule_status = "KO" if ko else "OK"

    return RuleResult(
        rule_id=RULE_ID,
        rule_name=RULE_NAME,
        execution_status="SUCCESS",
        rule_status=rule_status,
        findings=findings,
        summary={
            "total_interactions": len(findings),
            "broken_interactions": len(ko),
            "ko_details": [f.to_dict() for f in ko],
        },
    )
