"""Schémas Pydantic du contrat JSON Agent BI (Lot 8).

Reflète l'enveloppe versionnée produite par
Agent_BI/03_PYTHON/engine/envelope.py (section « Contrat JSON » de
Agent_BI/README_Agent_BI.md). Les champs communs (rule_id, execution_status,
rule_status, findings) sont garantis par ce contrat et donc strictement
typés ; le reste de chaque résultat (ko_details, total_columns, etc.) varie
par règle — on l'accepte tel quel plutôt que de le remodéliser ici.
"""
from pydantic import BaseModel, Field


class AgentFindingIn(BaseModel):
    rule_id: str
    object_type: str
    object: str
    expected: str
    actual: str | int | float | bool | None = None
    status: str  # OK | KO | NA
    evidence: dict = Field(default_factory=dict)
    reason: str = ""


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
