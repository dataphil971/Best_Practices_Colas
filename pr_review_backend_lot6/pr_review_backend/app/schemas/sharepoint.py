"""Schémas Pydantic du connecteur SharePoint (Lot 6)."""
from pydantic import BaseModel, Field

from app.models.enums import ChecklistType


class SharePointSource(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    site: str = Field(min_length=1)          # https://contoso.sharepoint.com/sites/BI
    drive: str = "Documents"
    folder: str = "/"
    pattern: str = "*.xlsx"                   # ex. PR_*.xlsx
    target_checklist: ChecklistType


class SharePointConfigIn(BaseModel):
    tenant_id: str | None = None
    client_id: str | None = None
    secret_ref: str | None = None             # référence coffre du client secret
    sources: list[SharePointSource] = Field(default_factory=list)
    activate: bool = True


class SharePointConfigOut(BaseModel):
    tenant_id: str | None = None
    client_id: str | None = None
    sources: list[SharePointSource] = Field(default_factory=list)
    is_active: bool = False
    operational: bool = False
    # NB : le client secret n'est jamais exposé.


class SyncJobSummary(BaseModel):
    job_id: str
    review_id: str
    file: str
    status: str


class SyncResult(BaseModel):
    operational: bool
    sources: int
    listed: int
    imported: int
    skipped: int
    jobs: list[SyncJobSummary] = Field(default_factory=list)
