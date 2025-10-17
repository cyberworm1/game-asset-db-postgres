import json
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from psycopg.rows import dict_row

from .auth import authenticate_user, create_access_token, get_current_user, set_rls_user
from .database import get_connection
from .schemas import (
    AssetCreate,
    AssetResponse,
    AssetVersionCreate,
    AssetVersionResponse,
    BranchCreate,
    BranchResponse,
    BranchUpdate,
    LockRequest,
    PermissionCreate,
    PermissionResponse,
    PermissionUpdate,
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
    ReviewResponse,
    ReviewUpdateRequest,
    ShelfCreate,
    ShelfResponse,
    TokenRequest,
    TokenResponse,
    WorkspaceCreate,
)
from .storage import save_asset_file

app = FastAPI(title="Asset Depot Service", version="1.0.0")

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def _normalize_metadata(raw: Any) -> dict:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"raw": raw}
    return dict(raw)


def _project_row_to_response(row: Dict[str, Any]) -> ProjectResponse:
    storage_quota = row.get("storage_quota_tb")
    if isinstance(storage_quota, Decimal):
        storage_quota = float(storage_quota)
    return ProjectResponse(
        id=row["id"],
        name=row["name"],
        code=row["code"],
        description=row.get("description"),
        status=row.get("status", "planning"),
        storage_quota_tb=storage_quota if storage_quota is not None else 0.0,
        storage_provider=row.get("storage_provider"),
        storage_location=row.get("storage_location"),
        archived_at=row.get("archived_at"),
        archived_by=row.get("archived_by"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _branch_row_to_response(row: Dict[str, Any]) -> BranchResponse:
    return BranchResponse(
        id=row["id"],
        project_id=row["project_id"],
        name=row["name"],
        description=row.get("description"),
        parent_branch_id=row.get("parent_branch_id"),
        created_by=row.get("created_by"),
        created_at=row["created_at"],
    )


def _shelf_row_to_response(row: Dict[str, Any]) -> ShelfResponse:
    return ShelfResponse(
        id=row["id"],
        workspace_id=row["workspace_id"],
        asset_version_id=row["asset_version_id"],
        created_by=row["created_by"],
        created_at=row["created_at"],
        description=row.get("description"),
    )


def _permission_row_to_response(row: Dict[str, Any]) -> PermissionResponse:
    return PermissionResponse(
        id=row["id"],
        project_id=row["project_id"],
        asset_id=row.get("asset_id"),
        user_id=row["user_id"],
        read=row["read"],
        write=row["write"],
        delete=row["delete"],
    )


@app.get("/health", tags=["system"])
def health_check():
    return {"status": "ok"}


@app.post("/auth/token", response_model=TokenResponse, tags=["auth"])
def login(payload: TokenRequest):
    user = authenticate_user(payload.username, payload.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token(user_id=user["id"], username=user["username"], role=user["role"])
    return TokenResponse(access_token=token)


@app.get("/projects", response_model=List[ProjectResponse], tags=["projects"])
def list_projects(
    include_archived: bool = Query(default=False, description="Include archived projects in the result set"),
    current_user: dict = Depends(get_current_user),
):
    with get_connection() as conn:
        try:
            set_rls_user(conn, current_user["id"])
            with conn.cursor(row_factory=dict_row) as cur:
                query = """
                    SELECT id, name, code, description, status, storage_quota_tb, storage_provider,
                           storage_location, archived_at, archived_by, created_at, updated_at
                    FROM projects
                """
                if not include_archived:
                    query += " WHERE archived_at IS NULL"
                query += " ORDER BY created_at DESC"
                cur.execute(query)
                rows = cur.fetchall()
                return [_project_row_to_response(row) for row in rows]
        except HTTPException:
            conn.rollback()
            raise
        except Exception as exc:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED, tags=["projects"])
def create_project(payload: ProjectCreate, current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    storage_quota = payload.storage_quota_tb if payload.storage_quota_tb is not None else 10.0
    with get_connection() as conn:
        try:
            set_rls_user(conn, current_user["id"])
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    INSERT INTO projects (name, code, description, status, storage_quota_tb, storage_provider, storage_location, archived_at, archived_by)
                    VALUES (%s, %s, %s, COALESCE(%s, 'planning'), %s, %s, %s, NULL, NULL)
                    RETURNING id, name, code, description, status, storage_quota_tb, storage_provider, storage_location,
                              archived_at, archived_by, created_at, updated_at
                    """,
                    (
                        payload.name,
                        payload.code,
                        payload.description,
                        payload.status,
                        storage_quota,
                        payload.storage_provider,
                        payload.storage_location,
                    ),
                )
                project = cur.fetchone()
                conn.commit()
                return _project_row_to_response(project)
        except Exception as exc:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.patch("/projects/{project_id}", response_model=ProjectResponse, tags=["projects"])
def update_project(project_id: UUID, payload: ProjectUpdate, current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    updates: List[str] = []
    params: List[Any] = []
    if payload.name is not None:
        updates.append("name = %s")
        params.append(payload.name)
    if payload.description is not None:
        updates.append("description = %s")
        params.append(payload.description)
    if payload.status is not None:
        updates.append("status = %s")
        params.append(payload.status)
    if payload.storage_quota_tb is not None:
        updates.append("storage_quota_tb = %s")
        params.append(payload.storage_quota_tb)
    if payload.storage_provider is not None:
        updates.append("storage_provider = %s")
        params.append(payload.storage_provider)
    if payload.storage_location is not None:
        updates.append("storage_location = %s")
        params.append(payload.storage_location)
    if payload.archived is not None:
        if payload.archived:
            updates.append("archived_at = COALESCE(archived_at, NOW())")
            updates.append("archived_by = %s")
            params.append(current_user["id"])
        else:
            updates.append("archived_at = NULL")
            updates.append("archived_by = NULL")
    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided")
    updates.append("updated_at = NOW()")

    with get_connection() as conn:
        try:
            set_rls_user(conn, current_user["id"])
            with conn.cursor(row_factory=dict_row) as cur:
                query = "UPDATE projects SET " + ", ".join(updates) + " WHERE id = %s RETURNING id, name, code, description, status, storage_quota_tb, storage_provider, storage_location, archived_at, archived_by, created_at, updated_at"
                params.append(str(project_id))
                cur.execute(query, params)
                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="Project not found")
                conn.commit()
                return _project_row_to_response(row)
        except HTTPException:
            conn.rollback()
            raise
        except Exception as exc:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/projects/{project_id}/branches", response_model=List[BranchResponse], tags=["branches"])
def list_branches(project_id: UUID, current_user: dict = Depends(get_current_user)):
    with get_connection() as conn:
        try:
            set_rls_user(conn, current_user["id"])
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT id, project_id, name, description, parent_branch_id, created_by, created_at
                    FROM branches
                    WHERE project_id = %s
                    ORDER BY created_at DESC
                    """,
                    (str(project_id),),
                )
                rows = cur.fetchall()
                return [_branch_row_to_response(row) for row in rows]
        except HTTPException:
            conn.rollback()
            raise
        except Exception as exc:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/projects/{project_id}/branches", response_model=BranchResponse, status_code=status.HTTP_201_CREATED, tags=["branches"])
def create_branch(project_id: UUID, payload: BranchCreate, current_user: dict = Depends(get_current_user)):
    with get_connection() as conn:
        try:
            set_rls_user(conn, current_user["id"])
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    INSERT INTO branches (project_id, name, description, parent_branch_id, created_by)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id, project_id, name, description, parent_branch_id, created_by, created_at
                    """,
                    (
                        str(project_id),
                        payload.name,
                        payload.description,
                        str(payload.parent_branch_id) if payload.parent_branch_id else None,
                        current_user["id"],
                    ),
                )
                row = cur.fetchone()
                conn.commit()
                return _branch_row_to_response(row)
        except Exception as exc:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.patch("/branches/{branch_id}", response_model=BranchResponse, tags=["branches"])
def update_branch(branch_id: UUID, payload: BranchUpdate, current_user: dict = Depends(get_current_user)):
    updates: List[str] = []
    params: List[Any] = []
    if payload.name is not None:
        updates.append("name = %s")
        params.append(payload.name)
    if payload.description is not None:
        updates.append("description = %s")
        params.append(payload.description)
    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided")

    with get_connection() as conn:
        try:
            set_rls_user(conn, current_user["id"])
            with conn.cursor(row_factory=dict_row) as cur:
                query = "UPDATE branches SET " + ", ".join(updates) + " WHERE id = %s RETURNING id, project_id, name, description, parent_branch_id, created_by, created_at"
                params.append(str(branch_id))
                cur.execute(query, params)
                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="Branch not found")
                conn.commit()
                return _branch_row_to_response(row)
        except HTTPException:
            conn.rollback()
            raise
        except Exception as exc:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/projects/{project_id}/shelves", response_model=List[ShelfResponse], tags=["shelves"])
def list_shelves(project_id: UUID, current_user: dict = Depends(get_current_user)):
    with get_connection() as conn:
        try:
            set_rls_user(conn, current_user["id"])
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT s.id, s.workspace_id, s.asset_version_id, s.created_by, s.created_at, s.description
                    FROM shelves s
                    JOIN workspaces w ON w.id = s.workspace_id
                    WHERE w.project_id = %s
                    ORDER BY s.created_at DESC
                    """,
                    (str(project_id),),
                )
                rows = cur.fetchall()
                return [_shelf_row_to_response(row) for row in rows]
        except HTTPException:
            conn.rollback()
            raise
        except Exception as exc:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/shelves", response_model=ShelfResponse, status_code=status.HTTP_201_CREATED, tags=["shelves"])
def create_shelf(payload: ShelfCreate, current_user: dict = Depends(get_current_user)):
    with get_connection() as conn:
        try:
            set_rls_user(conn, current_user["id"])
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    INSERT INTO shelves (workspace_id, asset_version_id, created_by, description)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id, workspace_id, asset_version_id, created_by, created_at, description
                    """,
                    (
                        str(payload.workspace_id),
                        str(payload.asset_version_id),
                        current_user["id"],
                        payload.description,
                    ),
                )
                row = cur.fetchone()
                conn.commit()
                return _shelf_row_to_response(row)
        except Exception as exc:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.delete("/shelves/{shelf_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["shelves"])
def delete_shelf(shelf_id: UUID, current_user: dict = Depends(get_current_user)):
    with get_connection() as conn:
        try:
            set_rls_user(conn, current_user["id"])
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM shelves WHERE id = %s AND created_by = %s",
                    (str(shelf_id), current_user["id"]),
                )
                if cur.rowcount == 0:
                    if current_user.get("role") != "admin":
                        raise HTTPException(status_code=403, detail="Cannot delete shelf you do not own")
                    cur.execute("DELETE FROM shelves WHERE id = %s", (str(shelf_id),))
            conn.commit()
            return None
        except HTTPException:
            conn.rollback()
            raise
        except Exception as exc:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/projects/{project_id}/permissions", response_model=List[PermissionResponse], tags=["permissions"])
def list_permissions(project_id: UUID, current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    with get_connection() as conn:
        try:
            set_rls_user(conn, current_user["id"])
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT id, project_id, asset_id, user_id, read, write, delete
                    FROM permissions
                    WHERE project_id = %s
                    ORDER BY user_id
                    """,
                    (str(project_id),),
                )
                rows = cur.fetchall()
                return [_permission_row_to_response(row) for row in rows]
        except HTTPException:
            conn.rollback()
            raise
        except Exception as exc:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/projects/{project_id}/permissions", response_model=PermissionResponse, status_code=status.HTTP_201_CREATED, tags=["permissions"])
def create_permission(project_id: UUID, payload: PermissionCreate, current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    if payload.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Project mismatch")
    with get_connection() as conn:
        try:
            set_rls_user(conn, current_user["id"])
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    INSERT INTO permissions (project_id, asset_id, user_id, read, write, delete)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id, project_id, asset_id, user_id, read, write, delete
                    """,
                    (
                        str(payload.project_id),
                        str(payload.asset_id) if payload.asset_id else None,
                        str(payload.user_id),
                        payload.read,
                        payload.write,
                        payload.delete,
                    ),
                )
                row = cur.fetchone()
                conn.commit()
                return _permission_row_to_response(row)
        except Exception as exc:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.put("/permissions/{permission_id}", response_model=PermissionResponse, tags=["permissions"])
def update_permission(permission_id: UUID, payload: PermissionUpdate, current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    updates: List[str] = []
    params: List[Any] = []
    if payload.read is not None:
        updates.append("read = %s")
        params.append(payload.read)
    if payload.write is not None:
        updates.append("write = %s")
        params.append(payload.write)
    if payload.delete is not None:
        updates.append("delete = %s")
        params.append(payload.delete)
    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided")

    with get_connection() as conn:
        try:
            set_rls_user(conn, current_user["id"])
            with conn.cursor(row_factory=dict_row) as cur:
                query = "UPDATE permissions SET " + ", ".join(updates) + " WHERE id = %s RETURNING id, project_id, asset_id, user_id, read, write, delete"
                params.append(str(permission_id))
                cur.execute(query, params)
                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="Permission not found")
                conn.commit()
                return _permission_row_to_response(row)
        except HTTPException:
            conn.rollback()
            raise
        except Exception as exc:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.delete("/permissions/{permission_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["permissions"])
def delete_permission(permission_id: UUID, current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    with get_connection() as conn:
        try:
            set_rls_user(conn, current_user["id"])
            with conn.cursor() as cur:
                cur.execute("DELETE FROM permissions WHERE id = %s", (str(permission_id),))
                if cur.rowcount == 0:
                    raise HTTPException(status_code=404, detail="Permission not found")
            conn.commit()
            return None
        except HTTPException:
            conn.rollback()
            raise
        except Exception as exc:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/assets", response_model=AssetResponse, tags=["assets"], status_code=status.HTTP_201_CREATED)
def create_asset(payload: AssetCreate, current_user: dict = Depends(get_current_user)):
    with get_connection() as conn:
        try:
            set_rls_user(conn, current_user["id"])
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    INSERT INTO assets (name, type, metadata, project_id, created_by)
                    VALUES (%s, %s, %s::jsonb, %s, %s)
                    RETURNING id, name, type, project_id, metadata, created_by
                    """,
                    (
                        payload.name,
                        payload.type,
                        json.dumps(payload.metadata),
                        str(payload.project_id),
                        current_user["id"],
                    ),
                )
                asset = cur.fetchone()
                conn.commit()
                asset["versions"] = []
                asset["metadata"] = _normalize_metadata(asset.get("metadata"))
                return AssetResponse(**asset)
        except Exception as exc:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/projects/{project_id}/assets", response_model=List[AssetResponse], tags=["assets"])
def list_project_assets(
    project_id: UUID,
    search: Optional[str] = Query(default=None, description="Filter assets by case-insensitive name fragment"),
    tags: Optional[List[str]] = Query(default=None, description="Filter assets by tag names (matches any)"),
    current_user: dict = Depends(get_current_user),
):
    with get_connection() as conn:
        try:
            set_rls_user(conn, current_user["id"])
            with conn.cursor(row_factory=dict_row) as cur:
                params: List[Any] = [str(project_id)]
                query = "SELECT id, name, type, project_id, metadata, created_by FROM assets WHERE project_id = %s"
                if search:
                    query += " AND name ILIKE %s"
                    params.append(f"%{search}%")
                if tags:
                    query += " AND id IN (SELECT asset_id FROM asset_tags at JOIN tags t ON t.id = at.tag_id WHERE t.name = ANY(%s))"
                    params.append(tuple(tags))
                cur.execute(query, params)
                assets = cur.fetchall()
                asset_map = {}
                for asset in assets:
                    asset["metadata"] = _normalize_metadata(asset.get("metadata"))
                    asset["versions"] = []
                    asset_map[asset["id"]] = asset
                if not assets:
                    return []
                cur.execute(
                    """
                    SELECT id, asset_id, version_number, branch_id, file_path, notes, created_at
                    FROM asset_versions
                    WHERE asset_id = ANY(%s)
                    ORDER BY asset_id, version_number
                    """,
                    ([str(asset_id) for asset_id in asset_map.keys()],),
                )
                for version in cur.fetchall():
                    asset = asset_map.get(version["asset_id"])
                    if asset is not None:
                        asset["versions"].append(
                            AssetVersionResponse(
                                id=version["id"],
                                version_number=version["version_number"],
                                branch_id=version["branch_id"],
                                file_path=version["file_path"],
                                notes=version["notes"],
                                created_at=version["created_at"],
                            )
                        )
                return [AssetResponse(**asset) for asset in asset_map.values()]
        except HTTPException:
            conn.rollback()
            raise
        except Exception as exc:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/assets/{asset_id}", response_model=AssetResponse, tags=["assets"])
def get_asset(asset_id: UUID, current_user: dict = Depends(get_current_user)):
    with get_connection() as conn:
        try:
            set_rls_user(conn, current_user["id"])
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "SELECT id, name, type, project_id, metadata, created_by FROM assets WHERE id = %s",
                    (str(asset_id),),
                )
                asset = cur.fetchone()
                if not asset:
                    raise HTTPException(status_code=404, detail="Asset not found")
                asset["metadata"] = _normalize_metadata(asset.get("metadata"))
                cur.execute(
                    """
                    SELECT id, asset_id, version_number, branch_id, file_path, notes, created_at
                    FROM asset_versions
                    WHERE asset_id = %s
                    ORDER BY version_number DESC
                    """,
                    (str(asset_id),),
                )
                asset["versions"] = [AssetVersionResponse(**row) for row in cur.fetchall()]
                return AssetResponse(**asset)
        except HTTPException:
            conn.rollback()
            raise
        except Exception as exc:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/assets/{asset_id}/versions", response_model=AssetVersionResponse, tags=["assets"], status_code=status.HTTP_201_CREATED)
def create_asset_version(asset_id: UUID, payload: AssetVersionCreate, current_user: dict = Depends(get_current_user)):
    with get_connection() as conn:
        try:
            set_rls_user(conn, current_user["id"])
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    INSERT INTO asset_versions (asset_id, version_number, branch_id, notes)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id, version_number, file_path, branch_id, created_at, notes
                    """,
                    (
                        str(asset_id),
                        payload.version_number,
                        str(payload.branch_id) if payload.branch_id else None,
                        payload.notes,
                    ),
                )
                version = cur.fetchone()
                conn.commit()
                return AssetVersionResponse(**version)
        except Exception as exc:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/assets/{asset_id}/versions/upload", response_model=AssetVersionResponse, tags=["assets"])
async def upload_asset_version(
    asset_id: UUID,
    version_number: int,
    branch_id: UUID | None = None,
    notes: str | None = None,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    with get_connection() as conn:
        try:
            set_rls_user(conn, current_user["id"])
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute("SELECT project_id FROM assets WHERE id = %s", (str(asset_id),))
                asset = cur.fetchone()
                if not asset:
                    raise HTTPException(status_code=404, detail="Asset not found")
                storage_path = save_asset_file(
                    project_id=str(asset["project_id"]), asset_id=str(asset_id), filename=file.filename, file_obj=file.file
                )
                cur.execute(
                    """
                    INSERT INTO asset_versions (asset_id, version_number, branch_id, file_path, notes)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (asset_id, version_number) DO UPDATE SET
                        branch_id = EXCLUDED.branch_id,
                        file_path = EXCLUDED.file_path,
                        notes = EXCLUDED.notes,
                        created_at = NOW()
                    RETURNING id, version_number, file_path, branch_id, created_at, notes
                    """,
                    (
                        str(asset_id),
                        version_number,
                        str(branch_id) if branch_id else None,
                        storage_path,
                        notes,
                    ),
                )
                version = cur.fetchone()
                conn.commit()
                return AssetVersionResponse(**version)
        except HTTPException:
            conn.rollback()
            raise
        except Exception as exc:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/reviews/pending", response_model=List[ReviewResponse], tags=["reviews"])
def list_pending_reviews(current_user: dict = Depends(get_current_user)):
    with get_connection() as conn:
        try:
            set_rls_user(conn, current_user["id"])
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT ar.id, a.name AS asset_name, av.version_number, u.username AS reviewer,
                           ar.status, ar.comments, ar.reviewed_at
                    FROM asset_reviews ar
                    JOIN asset_versions av ON av.id = ar.asset_version_id
                    JOIN assets a ON a.id = av.asset_id
                    LEFT JOIN users u ON u.id = ar.reviewer_id
                    WHERE ar.status = 'pending'
                    ORDER BY ar.reviewed_at DESC NULLS LAST
                    """
                )
                rows = cur.fetchall()
                return [ReviewResponse(**row) for row in rows]
        except HTTPException:
            conn.rollback()
            raise
        except Exception as exc:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.patch("/reviews/{review_id}", response_model=ReviewResponse, tags=["reviews"])
def update_review(review_id: UUID, payload: ReviewUpdateRequest, current_user: dict = Depends(get_current_user)):
    with get_connection() as conn:
        try:
            set_rls_user(conn, current_user["id"])
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    UPDATE asset_reviews
                    SET status = %s, comments = %s, reviewed_at = NOW()
                    WHERE id = %s
                    RETURNING id, status, comments, reviewed_at,
                              (SELECT name FROM assets WHERE id = (SELECT asset_id FROM asset_versions WHERE id = asset_reviews.asset_version_id)) AS asset_name,
                              (SELECT version_number FROM asset_versions WHERE id = asset_reviews.asset_version_id) AS version_number,
                              (SELECT username FROM users WHERE id = asset_reviews.reviewer_id) AS reviewer
                    """,
                    (payload.status, payload.comments, str(review_id)),
                )
                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="Review not found")
                conn.commit()
                return ReviewResponse(**row)
        except HTTPException:
            conn.rollback()
            raise
        except Exception as exc:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/locks", tags=["locks"], status_code=status.HTTP_201_CREATED)
def create_lock(payload: LockRequest, current_user: dict = Depends(get_current_user)):
    with get_connection() as conn:
        try:
            set_rls_user(conn, current_user["id"])
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    INSERT INTO asset_locks (asset_id, locked_by, workspace_id, expires_at, notes)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (asset_id) DO UPDATE SET
                        locked_by = EXCLUDED.locked_by,
                        workspace_id = EXCLUDED.workspace_id,
                        expires_at = EXCLUDED.expires_at,
                        notes = EXCLUDED.notes,
                        locked_at = NOW()
                    RETURNING id, asset_id, locked_by, workspace_id, locked_at, expires_at, notes
                    """,
                    (
                        str(payload.asset_id),
                        current_user["id"],
                        str(payload.workspace_id) if payload.workspace_id else None,
                        payload.expires_at,
                        payload.notes,
                    ),
                )
                row = cur.fetchone()
                conn.commit()
                return dict(row)
        except HTTPException:
            conn.rollback()
            raise
        except Exception as exc:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.delete("/locks/{asset_id}", tags=["locks"], status_code=status.HTTP_204_NO_CONTENT)
def release_lock(asset_id: UUID, current_user: dict = Depends(get_current_user)):
    with get_connection() as conn:
        try:
            set_rls_user(conn, current_user["id"])
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM asset_locks WHERE asset_id = %s AND locked_by = %s",
                    (str(asset_id), current_user["id"]),
                )
                if cur.rowcount == 0 and current_user["role"] != "admin":
                    raise HTTPException(status_code=403, detail="Cannot release lock you do not own")
                if cur.rowcount == 0 and current_user["role"] == "admin":
                    cur.execute("DELETE FROM asset_locks WHERE asset_id = %s", (str(asset_id),))
            conn.commit()
            return None
        except HTTPException:
            conn.rollback()
            raise
        except Exception as exc:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/workspaces", tags=["workspaces"], status_code=status.HTTP_201_CREATED)
def create_workspace(payload: WorkspaceCreate, current_user: dict = Depends(get_current_user)):
    with get_connection() as conn:
        try:
            set_rls_user(conn, current_user["id"])
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    INSERT INTO workspaces (project_id, user_id, branch_id, name, description)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id, project_id, user_id, branch_id, name, description, created_at, last_synced_at
                    """,
                    (
                        str(payload.project_id),
                        current_user["id"],
                        str(payload.branch_id) if payload.branch_id else None,
                        payload.name,
                        payload.description,
                    ),
                )
                row = cur.fetchone()
                conn.commit()
                return dict(row)
        except HTTPException:
            conn.rollback()
            raise
        except Exception as exc:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/reviews", response_class=HTMLResponse, tags=["reviews"])
def reviews_web(request: Request, current_user: dict = Depends(get_current_user)):
    with get_connection() as conn:
        try:
            set_rls_user(conn, current_user["id"])
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT ar.id, a.name AS asset_name, av.version_number, ar.status, ar.comments,
                           ar.reviewed_at, u.username AS reviewer
                    FROM asset_reviews ar
                    JOIN asset_versions av ON av.id = ar.asset_version_id
                    JOIN assets a ON a.id = av.asset_id
                    LEFT JOIN users u ON u.id = ar.reviewer_id
                    ORDER BY ar.reviewed_at DESC NULLS LAST
                    """
                )
                rows = cur.fetchall()
        except Exception as exc:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(exc)) from exc
    return templates.TemplateResponse("reviews.html", {"request": request, "reviews": rows, "username": current_user["username"]})
