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
    versions: List[AssetVersionResponse] = []


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
