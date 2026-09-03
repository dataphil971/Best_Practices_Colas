"""Exceptions du moteur Agent BI.

Toutes héritent de `AgentBIError` : un appelant peut ainsi distinguer une
erreur prévisible du moteur (chemin invalide, règle inconnue) d'un bug Python
non géré, qui doit rester une exception nue.
"""


class AgentBIError(Exception):
    """Classe de base de toutes les erreurs prévisibles d'Agent BI."""


class ProjectNotFoundError(AgentBIError):
    """Le chemin de projet fourni n'existe pas ou n'est pas un dossier."""


class UnknownRuleError(AgentBIError):
    """Un identifiant de règle demandé n'existe pas dans le catalogue."""
