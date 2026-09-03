"""API programmatique du moteur Agent BI.

Unique fonction qu'un appelant externe doit connaître pour lancer une analyse.
Elle encapsule l'enchaînement lecture du projet -> exécution des règles ->
enveloppe JSON, afin que la CLI, un pipeline et tout futur appelant partagent
exactement le même chemin de code.
"""

from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from engine.context import AnalysisContext
from engine.envelope import build_envelope
from engine.runner import run_rules
from errors import ProjectNotFoundError
from rules.registry import resolve_rules


def analyze_project(
    project_path: str | Path,
    rule_ids: Sequence[str] | None = None,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Analyse un projet PBIP et retourne l'enveloppe JSON versionnée.

    Args:
        project_path: racine du projet PBIP (dossier contenant
            `<Nom>.SemanticModel/`).
        rule_ids: identifiants `BP-NN` à exécuter. `None` exécute toutes les
            règles implémentées du registre.
        generated_at: horodatage d'analyse, pour des sorties reproductibles.

    Returns:
        L'enveloppe JSON versionnée décrite dans `engine/envelope.py`.

    Raises:
        ProjectNotFoundError: si `project_path` n'existe pas ou n'est pas un
            dossier. Un projet existant mais dépourvu de modèle sémantique
            n'est **pas** une erreur : c'est une analyse dont les règles
            concluent `NA`, ce que l'enveloppe exprime explicitement.
        UnknownRuleError: si un identifiant de `rule_ids` n'existe pas.

    """
    path = Path(project_path)
    if not path.exists():
        raise ProjectNotFoundError(f"Le chemin de projet n'existe pas : {path}")
    if not path.is_dir():
        raise ProjectNotFoundError(f"Le chemin de projet n'est pas un dossier : {path}")

    context = AnalysisContext.load(path)
    results = run_rules(context, resolve_rules(rule_ids))
    return build_envelope(context, results, generated_at=generated_at)
