"""Moteur d'exécution d'Agent BI : contexte d'analyse partagé, orchestrateur, modèles.

Ordre d'import volontaire (des feuilles vers la racine) : `api` dépend du
registre de règles, qui dépend lui-même du moteur. L'importer en dernier évite
un cycle d'import au chargement du paquet.
"""

from engine.models import ColumnDef, Finding, RuleResult, TableDef
from engine.context import AnalysisContext
from engine.runner import Rule, run_rules
from engine.envelope import SCHEMA_VERSION, build_envelope
from engine.api import analyze_project

__all__ = [
    "SCHEMA_VERSION",
    "AnalysisContext",
    "ColumnDef",
    "Finding",
    "Rule",
    "RuleResult",
    "TableDef",
    "analyze_project",
    "build_envelope",
    "run_rules",
]
