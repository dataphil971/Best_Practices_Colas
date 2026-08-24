"""Orchestrateur d'exécution des règles Agent BI.

Volontairement minimal : chaque règle est une fonction pure
`(AnalysisContext) -> RuleResult`, exécutée séquentiellement contre le même
contexte partagé. Rien n'empêche une parallélisation future, les règles
n'ayant pas d'effet de bord ni de dépendance entre elles.
"""

from typing import Callable, List

from engine.context import AnalysisContext
from engine.models import RuleResult

Rule = Callable[[AnalysisContext], RuleResult]


def run_rules(context: AnalysisContext, rules: List[Rule]) -> List[RuleResult]:
    return [rule(context) for rule in rules]
