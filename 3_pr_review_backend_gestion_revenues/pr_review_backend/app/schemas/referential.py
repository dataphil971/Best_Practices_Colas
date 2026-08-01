"""Schémas Pydantic du référentiel versionné (Lot 2)."""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import ChecklistType, Criticality, LifecycleState


# --- Catégories ------------------------------------------------------------
class CategoryOut(BaseModel):
    id: uuid.UUID
    checklist_type: ChecklistType
    name: str
    order_index: int

    model_config = {"from_attributes": True}


class CategoryCreate(BaseModel):
    checklist_type: ChecklistType
    name: str = Field(min_length=1, max_length=200)
    order_index: int = 0


# --- Versions de règles ----------------------------------------------------
class RuleVersionOut(BaseModel):
    id: uuid.UUID
    rule_id: uuid.UUID
    version_number: int
    text: str
    subs: list[str] = Field(default_factory=list)
    criticality: Criticality
    is_current: bool
    lifecycle: LifecycleState
    proposed_by: uuid.UUID | None = None
    reviewed_by: uuid.UUID | None = None
    review_comment: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Règles (identité + version courante) ----------------------------------
class RuleOut(BaseModel):
    id: uuid.UUID
    checklist_type: ChecklistType
    category_id: uuid.UUID
    category_name: str
    status: str
    current_version: RuleVersionOut | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Entrées : proposer / reformuler une règle -----------------------------
class RuleCreate(BaseModel):
    """Proposer une nouvelle règle. Admin → approuvée d'office ; sinon pending."""
    checklist_type: ChecklistType
    category_id: uuid.UUID
    text: str = Field(min_length=3, max_length=2000)
    subs: list[str] = Field(default_factory=list)
    criticality: Criticality = Criticality.recommended


class RuleRevise(BaseModel):
    """Reformuler une règle : crée une nouvelle version (jamais d'écrasement)."""
    text: str = Field(min_length=3, max_length=2000)
    subs: list[str] = Field(default_factory=list)
    criticality: Criticality = Criticality.recommended
    category_id: uuid.UUID | None = None


class RejectPayload(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)


# --- Journal d'activité ----------------------------------------------------
class RuleActivityOut(BaseModel):
    id: uuid.UUID
    action: str
    rule_id: uuid.UUID | None = None
    rule_version_id: uuid.UUID | None = None
    actor_id: uuid.UUID
    actor_name: str | None = None
    rule_text: str
    checklist_type: ChecklistType
    detail: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
