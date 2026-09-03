"""Construction de l'enveloppe JSON versionnée retournée par Agent BI.

Ce contrat est ce qu'un appelant externe (pipeline Azure DevOps, route
d'API, outil tiers) doit pouvoir consommer sans connaître les
détails internes du moteur.

Versionnement de `schema_version` (`MAJEUR.MINEUR`) :

- **MAJEUR** est incrémenté en cas d'évolution *incompatible* (champ retiré,
  renommé, ou dont le sens change). Un consommateur doit refuser une version
  majeure qu'il ne connaît pas.
- **MINEUR** est incrémenté en cas d'évolution *additive* (nouveau champ). Un
  consommateur écrit pour une version mineure antérieure continue de
  fonctionner sans modification.

Un consommateur externe doit se fier à ce numéro plutôt qu'à la présence ou à
l'absence d'un champ.
"""

from collections import Counter
from datetime import UTC, datetime
from typing import Any

from core import RULE_STATUSES, SEMANTIC_MODEL_SUFFIX, RuleStatus
from engine.context import AnalysisContext
from engine.models import RuleResult
from version import ENGINE_VERSION

SCHEMA_VERSION = "1.1"


def _derive_project_name(context: AnalysisContext) -> str | None:
    if context.semantic_model_path is not None:
        name = context.semantic_model_path.name
        return name[: -len(SEMANTIC_MODEL_SUFFIX)] if name.endswith(SEMANTIC_MODEL_SUFFIX) else name
    if context.project_path is not None:
        return context.project_path.name
    return None


def derive_overall_status(results: list[RuleResult]) -> RuleStatus:
    """Statut consolidé d'une analyse, selon la même asymétrie que les règles.

    Un seul `KO` suffit à rendre l'ensemble `KO`. En l'absence de `KO`, un seul
    `NA` suffit à rendre l'ensemble `NA` : on ne déclare `OK` un projet que si
    **toutes** les règles ont pu conclure à la conformité. Une analyse sans
    aucune règle exécutée est `NA`, jamais `OK` — l'absence de contrôle ne
    démontre aucune conformité.
    """
    statuses = {result.rule_status for result in results}
    if "KO" in statuses:
        return "KO"
    if "OK" in statuses and "NA" not in statuses:
        return "OK"
    return "NA"


def _build_summary(results: list[RuleResult]) -> dict[str, Any]:
    rules_by_status = Counter(result.rule_status for result in results)
    findings_by_status: Counter[str] = Counter()
    for result in results:
        findings_by_status.update(finding.status for finding in result.findings)

    return {
        "overall_status": derive_overall_status(results),
        "rules_evaluated": len(results),
        "rules_by_status": {status: rules_by_status.get(status, 0) for status in RULE_STATUSES},
        "findings_by_status": {status: findings_by_status.get(status, 0) for status in RULE_STATUSES},
    }


def build_envelope(
    context: AnalysisContext,
    results: list[RuleResult],
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Assemble l'enveloppe JSON versionnée d'une analyse.

    Args:
        context: le contexte d'analyse, déjà chargé.
        results: les résultats de règles, dans l'ordre d'exécution.
        generated_at: horodatage d'analyse. Laisser à None en usage normal ;
            une valeur explicite permet aux tests de produire une enveloppe
            reproductible octet pour octet.

    Returns:
        L'enveloppe, directement sérialisable en JSON.

    """
    moment = generated_at or datetime.now(UTC)

    return {
        "schema_version": SCHEMA_VERSION,
        "engine_version": ENGINE_VERSION,
        # Métadonnée contextuelle, volontairement hors du périmètre de
        # déterminisme : deux analyses du même projet produisent les mêmes
        # `results`, mais pas le même `generated_at`.
        "generated_at": moment.isoformat(),
        "project": {
            "name": _derive_project_name(context),
            "format": "PBIP",
            "project_path": str(context.project_path) if context.project_path else None,
            "semantic_model_path": (
                str(context.semantic_model_path) if context.semantic_model_path else None
            ),
            "fingerprint": context.fingerprint,
        },
        "summary": _build_summary(results),
        "results": [result.to_dict() for result in results],
    }
