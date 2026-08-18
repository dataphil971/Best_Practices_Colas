"""Construction de l'enveloppe JSON versionnée retournée par Agent BI.

Ce contrat est ce qu'un futur appelant externe (serveur Node local, route
FastAPI d'import) doit pouvoir consommer sans connaître les détails internes
du moteur. Toute évolution incompatible de cette forme doit incrémenter
SCHEMA_VERSION — un consommateur externe doit pouvoir se fier à ce numéro
plutôt qu'à la présence/absence de champs.
"""

from typing import Any, Dict, List, Optional

from engine.context import AnalysisContext
from engine.models import RuleResult

SCHEMA_VERSION = "1.0"
ENGINE_VERSION = "0.1.0"


def _derive_project_name(context: AnalysisContext) -> Optional[str]:
    if context.semantic_model_path is not None:
        name = context.semantic_model_path.name
        suffix = ".SemanticModel"
        return name[: -len(suffix)] if name.endswith(suffix) else name
    if context.project_path is not None:
        return context.project_path.name
    return None


def build_envelope(context: AnalysisContext, results: List[RuleResult]) -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "engine_version": ENGINE_VERSION,
        "project": {
            "name": _derive_project_name(context),
            "format": "PBIP",
            "project_path": str(context.project_path) if context.project_path else None,
            "semantic_model_path": str(context.semantic_model_path) if context.semantic_model_path else None,
            "fingerprint": context.fingerprint,
        },
        "results": [result.to_dict() for result in results],
    }
