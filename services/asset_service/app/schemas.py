from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class TokenRequest(BaseModel):
    username: str = Field(..., example="admin_user")
    password: str = Field(..., example="admin123")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 3600


class AssetCreate(BaseModel):
    name: str
    type: str
    project_id: UUID
    metadata: dict = Field(default_factory=dict)


class AssetVersionCreate(BaseModel):
    version_number: int
    branch_id: Optional[UUID]
    notes: Optional[str] = None


class AssetVersionResponse(BaseModel):
    id: UUID
    version_number: int
    file_path: Optional[str]
    branch_id: Optional[UUID]
    created_at: datetime
    notes: Optional[str]


class AssetResponse(BaseModel):
    id: UUID
    name: str
    type: str
    project_id: UUID
    metadata: dict
    created_by: Optional[UUID]
    versions: List[AssetVersionResponse] = Field(default_factory=list)


class ProjectCreate(BaseModel):
    name: str
    code: str
    description: Optional[str]
    status: Optional[str]
    storage_quota_tb: Optional[float]
    storage_provider: Optional[str]
    storage_location: Optional[str]


class ProjectUpdate(BaseModel):
    name: Optional[str]
    description: Optional[str]
    status: Optional[str]
    storage_quota_tb: Optional[float]
    storage_provider: Optional[str]
    storage_location: Optional[str]
    archived: Optional[bool]


class ProjectResponse(BaseModel):
    id: UUID
    name: str
    code: str
    description: Optional[str]
    status: str
    storage_quota_tb: float
    storage_provider: Optional[str]
    storage_location: Optional[str]
    archived_at: Optional[datetime]
    archived_by: Optional[UUID]
    created_at: datetime
    updated_at: datetime


class BranchCreate(BaseModel):
    name: str
    description: Optional[str]
    parent_branch_id: Optional[UUID]


class BranchUpdate(BaseModel):
    name: Optional[str]
    description: Optional[str]


class BranchResponse(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    description: Optional[str]
    parent_branch_id: Optional[UUID]
    created_by: Optional[UUID]
    created_at: datetime


class ShelfCreate(BaseModel):
    workspace_id: UUID
    asset_version_id: UUID
    changelist_id: Optional[UUID]
    description: Optional[str]


class ShelfResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    asset_version_id: UUID
    changelist_id: Optional[UUID]
    created_by: UUID
    created_at: datetime
    description: Optional[str]


class ChangelistItemResponse(BaseModel):
    id: UUID
    asset_version_id: UUID
    action: str
    target_branch_id: Optional[UUID]
    created_at: datetime


class ChangelistResponse(BaseModel):
    id: UUID
    project_id: UUID
    workspace_id: Optional[UUID]
    created_by: UUID
    target_branch_id: Optional[UUID]
    status: str
    description: Optional[str]
    submitter_notes: Optional[str]
    submitted_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    shelf_id: Optional[UUID]
    items: List[ChangelistItemResponse] = Field(default_factory=list)


class ChangelistCreate(BaseModel):
    project_id: UUID
    workspace_id: UUID
    target_branch_id: Optional[UUID]
    description: Optional[str]
    shelf_id: Optional[UUID]


class ChangelistItemCreate(BaseModel):
    asset_version_id: UUID
    action: str = "edit"
    target_branch_id: Optional[UUID]


class ChangelistSubmitRequest(BaseModel):
    submitter_notes: Optional[str]
    status: Optional[str] = "submitted"


class BranchMergeCreate(BaseModel):
    project_id: UUID
    source_branch_id: UUID
    target_branch_id: UUID
    notes: Optional[str]


class BranchMergeResponse(BaseModel):
    id: UUID
    project_id: UUID
    source_branch_id: UUID
    target_branch_id: UUID
    initiated_by: UUID
    status: str
    conflict_summary: Optional[dict]
    notes: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]


class BranchMergeUpdate(BaseModel):
    status: Optional[str]
    conflict_summary: Optional[dict]
    notes: Optional[str]
    completed: Optional[bool]


class MergeConflictCreate(BaseModel):
    asset_id: Optional[UUID]
    asset_version_id: Optional[UUID]
    description: str


class MergeConflictUpdate(BaseModel):
    resolution: Optional[str]
    resolved: Optional[bool]


class MergeConflictResponse(BaseModel):
    id: UUID
    branch_merge_id: UUID
    asset_id: Optional[UUID]
    asset_version_id: Optional[UUID]
    description: Optional[str]
    resolution: Optional[str]
    resolved_at: Optional[datetime]


class PermissionBase(BaseModel):
    user_id: UUID
    asset_id: Optional[UUID]
    read: bool = True
    write: bool = False
    delete: bool = False


class PermissionCreate(PermissionBase):
    project_id: UUID


class PermissionUpdate(BaseModel):
    read: Optional[bool]
    write: Optional[bool]
    delete: Optional[bool]


class PermissionResponse(BaseModel):
    id: UUID
    project_id: UUID
    asset_id: Optional[UUID]
    user_id: UUID
    read: bool
    write: bool
    delete: bool


class ReviewResponse(BaseModel):
    id: UUID
    asset_name: str
    version_number: int
    reviewer: str
    status: str
    comments: Optional[str]
    reviewed_at: datetime


class ReviewUpdateRequest(BaseModel):
    status: str
    comments: Optional[str]


class LockRequest(BaseModel):
    asset_id: UUID
    workspace_id: Optional[UUID]
    expires_at: Optional[datetime]
    notes: Optional[str]


class WorkspaceCreate(BaseModel):
    project_id: UUID
    branch_id: Optional[UUID]
    name: str
    description: Optional[str]
