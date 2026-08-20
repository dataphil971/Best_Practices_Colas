"""BP-09 — Désactiver l'option Auto Date/Time.

Implémente l'algorithme documenté dans
Agent_BI/01_ALGORITHMES/09_DisableAutoDateTime.md. Toute évolution de la
logique OK/KO/NA doit d'abord être répercutée dans ce document — ce fichier
ne doit jamais diverger silencieusement de sa spécification fonctionnelle.

Le contrôle porte sur une unique annotation du modèle
(`__PBI_TimeIntelligenceEnabled`) : le nombre de colonnes date/dateTime
n'est PAS un signal de verdict (§3 de l'algorithme — un diagnostic possible,
qui ne doit jamais faire basculer le statut).
"""

from engine.context import AnalysisContext
from engine.models import Finding, RuleResult

RULE_ID = "BP-09"
RULE_NAME = "Désactiver l'option Auto Date/Time"

ANNOTATION_KEY = "__PBI_TimeIntelligenceEnabled"


def _normalize(raw: object) -> "bool | None":
    """Cf. §6 de l'algorithme : seules les valeurs textuelles "0"/"1" sont
    résolues. Toute autre graphie (true/false/disabled/enabled...) reste NA
    tant que le contrat TMDL analysé ne l'a pas explicitement démontrée."""
    value = str(raw).strip().strip('"').strip("'")
    if value == "0":
        return False
    if value == "1":
        return True
    return None


def check(context: AnalysisContext) -> RuleResult:
    model_path = context.model_tmdl_path
    if model_path is None or not model_path.exists():
        return RuleResult(
            rule_id=RULE_ID,
            rule_name=RULE_NAME,
            execution_status="ERROR",
            rule_status="NA",
            summary={"reason": "model.tmdl absent ou illisible"},
        )

    raw = context.model_annotations.get(ANNOTATION_KEY)
    evidence = {"source_file": str(model_path)}

    if raw is None:
        return RuleResult(
            rule_id=RULE_ID,
            rule_name=RULE_NAME,
            execution_status="SUCCESS",
            rule_status="NA",
            findings=[Finding(
                rule_id=RULE_ID, object_type="model", object="model",
                expected=f"{ANNOTATION_KEY} = 0", actual=None, status="NA",
                reason=(
                    f"Annotation {ANNOTATION_KEY} absente : état du réglage "
                    "non démontrable à partir de cette preuve"
                ),
                evidence={**evidence, "annotation_found": False},
            )],
            summary={
                "annotation_found": False,
                "reason": f"Annotation {ANNOTATION_KEY} absente",
            },
        )

    normalized = _normalize(raw)
    evidence = {**evidence, "annotation_found": True, "raw_value": raw}

    if normalized is False:
        return RuleResult(
            rule_id=RULE_ID,
            rule_name=RULE_NAME,
            execution_status="SUCCESS",
            rule_status="OK",
            findings=[Finding(
                rule_id=RULE_ID, object_type="model", object="model",
                expected=f"{ANNOTATION_KEY} = 0", actual=raw, status="OK",
                evidence=evidence,
            )],
            summary={"annotation_found": True, "raw_value": raw},
        )

    if normalized is True:
        return RuleResult(
            rule_id=RULE_ID,
            rule_name=RULE_NAME,
            execution_status="SUCCESS",
            rule_status="KO",
            findings=[Finding(
                rule_id=RULE_ID, object_type="model", object="model",
                expected=f"{ANNOTATION_KEY} = 0", actual=raw, status="KO",
                reason="Auto Date/Time explicitement activé",
                evidence=evidence,
            )],
            summary={"annotation_found": True, "raw_value": raw},
        )

    return RuleResult(
        rule_id=RULE_ID,
        rule_name=RULE_NAME,
        execution_status="SUCCESS",
        rule_status="NA",
        findings=[Finding(
            rule_id=RULE_ID, object_type="model", object="model",
            expected=f"{ANNOTATION_KEY} = 0", actual=raw, status="NA",
            reason="Valeur de l'annotation non reconnue",
            evidence=evidence,
        )],
        summary={"annotation_found": True, "raw_value": raw, "reason": "Valeur non reconnue"},
    )
