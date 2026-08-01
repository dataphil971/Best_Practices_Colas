"""Schémas Pydantic de la validation tierce (Lot 4)."""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import ChecklistType, ReviewStatus


# --- Partage ---------------------------------------------------------------
class ShareCreate(BaseModel):
    reviewer_ids: list[uuid.UUID] = Field(min_length=1)
    ttl_days: int = Field(default=14, ge=1, le=90)


class ShareTargetOut(BaseModel):
    reviewer_id: uuid.UUID
    reviewer_name: str | None = None


class ShareLinkOut(BaseModel):
    id: uuid.UUID
    review_id: uuid.UUID
    token: str
    created_by: uuid.UUID
    expires_at: datetime
    revoked: bool
    created_at: datetime
    targets: list[ShareTargetOut] = Field(default_factory=list)

    model_config = {"from_attributes": True}


# --- Métadonnées publiques d'une revue partagée (lecture limitée) ----------
class SharedReviewMeta(BaseModel):
    review_id: uuid.UUID
    report_name: str
    checklist_type: ChecklistType
    status: ReviewStatus
    compliance_score: int | None = None
    author_name: str | None = None
    item_count: int = 0
    expires_at: datetime
    # Vrai si le porteur du lien (authentifié) est bien une cible → peut valider.
    can_validate: bool = False


# --- Validation ------------------------------------------------------------
class ItemComment(BaseModel):
    review_item_id: uuid.UUID
    comment: str = Field(min_length=1, max_length=4000)


class ValidationCreate(BaseModel):
    decision: str = Field(pattern="^(approved|rejected)$")
    global_comment: str | None = Field(default=None, max_length=8000)
    item_comments: list[ItemComment] = Field(default_factory=list)


class ValidationOut(BaseModel):
    id: uuid.UUID
    review_id: uuid.UUID
    reviewer_id: uuid.UUID
    reviewer_name: str | None = None
    decision: str
    global_comment: str | None = None
    created_at: datetime
    resulting_status: ReviewStatus

    model_config = {"from_attributes": True}
