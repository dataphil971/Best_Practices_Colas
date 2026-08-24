"""Schémas Pydantic de l'import intelligent et des intégrations (Lot 5)."""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field


# --- Jobs d'import ---------------------------------------------------------
class ImportJobOut(BaseModel):
    id: uuid.UUID
    review_id: uuid.UUID | None = None
    source: str
    status: str
    result: dict | None = None
    error: str | None = None
    created_at: datetime
    finished_at: datetime | None = None

    model_config = {"from_attributes": True}


# --- Intégrations (admin) --------------------------------------------------
class IntegrationOut(BaseModel):
    id: uuid.UUID
    kind: str
    provider: str
    settings: dict = Field(default_factory=dict)
    is_active: bool
    updated_at: datetime
    # NB : secret_ref n'est jamais exposé au front.

    model_config = {"from_attributes": True}


class IntegrationsState(BaseModel):
    matching: list[IntegrationOut] = Field(default_factory=list)
    storage: list[IntegrationOut] = Field(default_factory=list)
    sharepoint: list[IntegrationOut] = Field(default_factory=list)
    active_matching: str = "local"
    active_storage: str = "internal"


class MatchingConfigIn(BaseModel):
    provider: str = Field(pattern="^(local|mistral|enterprise|openai|azure)$")
    settings: dict = Field(default_factory=dict)
    secret_ref: str | None = None
    activate: bool = True


class StorageConfigIn(BaseModel):
    provider: str = Field(pattern="^(internal|azure_blob|s3)$")
    settings: dict = Field(default_factory=dict)
    secret_ref: str | None = None
    activate: bool = True


class ConnectionTestResult(BaseModel):
    ok: bool
    provider: str
    detail: str | None = None
