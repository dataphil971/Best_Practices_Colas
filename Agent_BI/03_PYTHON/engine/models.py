"""Structures de données partagées par le moteur Agent BI.

Ces structures reflètent directement les conventions décrites dans
Agent_BI/README_Agent_BI.md (statuts OK/KO/NA, principe de preuve) : toute
évolution de ces conventions doit être répercutée ici.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ColumnDef:
    """Une colonne telle qu'extraite d'un bloc `column` TMDL.

    `name` est la valeur utile (guillemets retirés) ; `raw_name` conserve la
    forme brute telle qu'écrite dans le TMDL (guillemets compris) pour les
    preuves et les messages utilisateur.
    """

    name: str
    raw_name: str
    properties: Dict[str, Any]
    source_file: str

    def get_property(self, key: str) -> Optional[Any]:
        return self.properties.get(key)


@dataclass
class TableDef:
    name: str
    source_file: str
    columns: List[ColumnDef] = field(default_factory=list)


@dataclass
class Finding:
    """Un constat unitaire, conforme au « Principe de preuve » du README :
    Rule ID / Object / Expected / Actual / Evidence / Status."""

    rule_id: str
    object_type: str
    object: str
    expected: str
    actual: Any
    status: str  # OK | KO | NA
    evidence: Dict[str, Any] = field(default_factory=dict)
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "object_type": self.object_type,
            "object": self.object,
            "expected": self.expected,
            "actual": self.actual,
            "status": self.status,
            "evidence": self.evidence,
            "reason": self.reason,
        }


@dataclass
class RuleResult:
    """Résultat global d'une règle, tel que sérialisé dans le résultat d'audit."""

    rule_id: str
    rule_name: str
    execution_status: str  # SUCCESS | ERROR | PARTIAL
    rule_status: str       # OK | KO | NA — jamais un autre statut
    alias: Optional[str] = None
    findings: List[Finding] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {"rule_id": self.rule_id}
        if self.alias:
            result["alias"] = self.alias
        result["rule_name"] = self.rule_name
        result["execution_status"] = self.execution_status
        result["rule_status"] = self.rule_status
        result.update(self.summary)
        # `summary` ne contient que ce que chaque règle choisit d'y mettre
        # (ex: ko_details/na_details pour BP-22). `findings` porte la preuve
        # complète (object/expected/actual/evidence) pour CHAQUE objet,
        # y compris les OK — nécessaire pour un consommateur externe
        # (API, frontend) qui ne doit jamais avoir à redériver une preuve.
        result["findings"] = [finding.to_dict() for finding in self.findings]
        return result
