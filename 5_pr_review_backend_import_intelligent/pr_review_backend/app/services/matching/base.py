"""
Interface commune des fournisseurs de correspondance (Lot 5, §6.1).

Tous les fournisseurs (local par défaut, IA optionnels) implémentent le même
protocole, ce qui permet de les interchanger sans toucher au reste du code.
"""
from dataclasses import dataclass, field
from typing import Protocol

from app.models.enums import ItemStatus


@dataclass(frozen=True)
class RuleRef:
    """Une règle du référentiel, identifiée par sa version + son texte."""
    rule_version_id: str
    text: str


@dataclass
class MatchResult:
    imported_index: int
    rule_version_id: str | None
    confidence: float
    verdict: str  # 'identical' | 'probable' | 'new'
    detected_status: ItemStatus | None = None


# Seuils par défaut (§6.2), ajustables.
THRESHOLD_IDENTICAL = 0.95
THRESHOLD_PROBABLE = 0.70


def verdict_for(confidence: float) -> str:
    if confidence >= THRESHOLD_IDENTICAL:
        return "identical"
    if confidence >= THRESHOLD_PROBABLE:
        return "probable"
    return "new"


class MatchProvider(Protocol):
    """Contrat commun à tous les fournisseurs de matching."""

    name: str

    def match_rules(
        self,
        imported_texts: list[str],
        referential: list[RuleRef],
    ) -> list[MatchResult]:
        """Associe chaque texte importé à la règle la plus proche + un score [0,1]."""
        ...

    def detect_status(self, raw: str) -> ItemStatus | None:
        """Déduit OK/KO/Partiel/N/A d'une valeur cellule, même formulée librement."""
        ...
