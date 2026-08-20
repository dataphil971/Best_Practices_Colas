"""Schémas Pydantic du contrat JSON Agent BI (Lot 8).

Reflète l'enveloppe versionnée produite par
Agent_BI/03_PYTHON/engine/envelope.py (section « Contrat JSON » de
Agent_BI/README_Agent_BI.md). Les champs communs (rule_id, execution_status,
rule_status, findings) sont garantis par ce contrat et donc strictement
typés ; le reste de chaque résultat (ko_details, total_columns, etc.) varie
par règle — on l'accepte tel quel plutôt que de le remodéliser ici.
"""
from typing import Any

from pydantic import BaseModel, Field


class AgentSourceLocationIn(BaseModel):
    """Où se trouve le constat dans le projet analysé, à la ligne près.

    `line` est 1-indexée (comme un éditeur). `excerpt` porte le code réel :
    le frontend l'affiche sans jamais avoir accès au projet, qui reste sur le
    poste de l'utilisateur.
    """

    source_file: str
    line: int | None = None
    end_line: int | None = None
    excerpt: str | None = None


class AgentFindingIn(BaseModel):
    rule_id: str
    object_type: str
    object: str
    expected: str
    # `actual` est typé `Any` dans le contrat (engine/models.py, Finding.actual) :
    # selon la règle c'est un scalaire, mais rien n'interdit une liste ou un
    # objet. Le restreindre aux scalaires ferait rejeter en 422 l'enveloppe
    # ENTIÈRE pour un seul finding non scalaire — on l'accepte tel quel.
    actual: Any = None
    status: str  # OK | KO | NA
    evidence: dict = Field(default_factory=dict)
    reason: str = ""
    # Champs d'EXPLICABILITÉ. Doivent être déclarés ici : sans eux, Pydantic
    # les écarte silencieusement et `agent_evidence` perdrait exactement
    # l'information que l'utilisateur doit voir (ligne fautive, remédiation).
    location: AgentSourceLocationIn | None = None
    remediation: str = ""
    explanation: str = ""


class AgentResultIn(BaseModel):
    rule_id: str
    alias: str | None = None
    rule_name: str
    execution_status: str
    rule_status: str  # OK | KO | NA
    findings: list[AgentFindingIn] = Field(default_factory=list)

    # Champs spécifiques à chaque règle (ko_details, total_columns, ...) :
    # conservés tels quels dans model_extra plutôt que remodélisés.
    model_config = {"extra": "allow"}


class AgentProjectIn(BaseModel):
    name: str | None = None
    format: str | None = None
    project_path: str | None = None
    semantic_model_path: str | None = None
    fingerprint: str | None = None


class AgentEnvelopeIn(BaseModel):
    schema_version: str
    engine_version: str
    project: AgentProjectIn
    results: list[AgentResultIn]


class AgentImportDetail(BaseModel):
    rule_id: str
    reason: str | None = None
    previous_status: str | None = None
    proposed_status: str | None = None


class AgentImportResultOut(BaseModel):
    applied: int
    conflicts: int
    unmatched: int
    already_applied: int
    total: int
    details: dict[str, list[AgentImportDetail]]
