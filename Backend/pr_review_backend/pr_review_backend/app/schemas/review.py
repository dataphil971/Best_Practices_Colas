"""Schémas Pydantic des revues (Lot 3)."""
import uuid
from datetime import datetime, date

from pydantic import BaseModel, Field

from app.models.enums import ChecklistType, ReviewStatus, ItemStatus, ProgressState, Criticality


# --- Création / mise à jour d'une revue ------------------------------------
class ReviewCreate(BaseModel):
    report_name: str = Field(min_length=1, max_length=300)
    checklist_type: ChecklistType


class ReviewUpdate(BaseModel):
    report_name: str | None = Field(default=None, min_length=1, max_length=300)
    status: ReviewStatus | None = None


# --- Mise à jour d'un item -------------------------------------------------
class ReviewItemUpdate(BaseModel):
    status: ItemStatus | None = None
    progress: ProgressState | None = None
    comment: str | None = None
    risk: str | None = None
    risk_comment: str | None = None
    proposed_solution: str | None = None
    estimated_days: str | None = None
    target_date: date | None = None
    definition_of_done: str | None = None
    priority: str | None = None
    responsible: str | None = None


# --- Sorties : synthèse d'une revue (listing) ------------------------------
class ReviewSummary(BaseModel):
    id: uuid.UUID
    report_name: str
    checklist_type: ChecklistType
    author_id: uuid.UUID
    author_name: str | None = None
    status: ReviewStatus
    compliance_score: int | None = None
    item_count: int = 0
    created_at: datetime
    submitted_at: datetime | None = None
    validated_at: datetime | None = None

    model_config = {"from_attributes": True}


# --- Sorties : item détaillé (avec le snapshot de règle) -------------------
class ReviewItemOut(BaseModel):
    id: uuid.UUID
    rule_version_id: uuid.UUID
    # Contenu figé de la règle (recopié depuis la version snapshot, lisibilité).
    rule_text: str
    subs: list[str] = Field(default_factory=list)
    criticality: Criticality
    version_number: int
    # Évaluation
    status: ItemStatus
    progress: ProgressState
    comment: str = ""
    risk: str = ""
    risk_comment: str = ""
    proposed_solution: str = ""
    estimated_days: str = ""
    target_date: date | None = None
    definition_of_done: str = ""
    priority: str = ""
    responsible: str = ""
    last_update: datetime
    # Provenance Agent BI (Lot 8) : 'unset' | 'human' | 'agent'.
    last_update_source: str = "unset"
    agent_evidence: dict | None = None


class CategoryGroup(BaseModel):
    category_id: uuid.UUID | None = None
    category_name: str
    order_index: int = 0
    items: list[ReviewItemOut] = Field(default_factory=list)


class ScoreBreakdown(BaseModel):
    score: int
    ok: int
    ko: int
    partial: int
    na: int
    unset: int
    evaluated: int
    total: int


class ReviewDetail(BaseModel):
    id: uuid.UUID
    report_name: str
    checklist_type: ChecklistType
    author_id: uuid.UUID
    author_name: str | None = None
    status: ReviewStatus
    compliance_score: int | None = None
    breakdown: ScoreBreakdown
    unset_count: int
    groups: list[CategoryGroup] = Field(default_factory=list)
    created_at: datetime
    submitted_at: datetime | None = None
    validated_at: datetime | None = None
