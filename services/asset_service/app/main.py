import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from prometheus_fastapi_instrumentator import Instrumentator
from psycopg.rows import dict_row

from .auth import authenticate_user, create_access_token, get_current_user, set_rls_user
from .database import get_connection
from .merge_worker import enqueue_many, enqueue_merge_job
from .opencue_integration import integration as opencue_integration
from .schemas import (
    AssetCreate,
    AssetResponse,
    AssetVersionCreate,
    AssetVersionResponse,
    BranchCreate,
    BranchMergeCreate,
    BranchMergeResponse,
    BranchMergeUpdate,
    BranchResponse,
    BranchUpdate,
    ChangelistCreate,
    ChangelistItemCreate,
    ChangelistItemResponse,
    ChangelistResponse,
    ChangelistSubmitRequest,
    LockRequest,
    MergeConflictCreate,
    MergeConflictResponse,
    MergeConflictUpdate,
    MergeJobCreate,
    MergeJobResponse,
    MergeJobUpdate,
    OpenCueDetailedResponse,
    OpenCueSummaryResponse,
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
Instrumentator().instrument(app).expose(app, include_in_schema=False)

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

MERGE_JOB_STATUSES = {"queued", "running", "staged", "completed", "failed"}
MERGE_JOB_TYPES = {"auto_integrate", "conflict_staging", "submit_gate"}


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
        changelist_id=row.get("changelist_id"),
        created_by=row["created_by"],
        created_at=row["created_at"],
        description=row.get("description"),
    )


def _changelist_item_row_to_response(row: Dict[str, Any]) -> ChangelistItemResponse:
    return ChangelistItemResponse(
        id=row["id"],
        asset_version_id=row["asset_version_id"],
        action=row["action"],
        target_branch_id=row.get("target_branch_id"),
        created_at=row["created_at"],
    )


def _changelist_row_to_response(conn, row: Dict[str, Any]) -> ChangelistResponse:
    items: List[ChangelistItemResponse] = []
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT id, asset_version_id, action, target_branch_id, created_at
            FROM changelist_items
            WHERE changelist_id = %s
            ORDER BY created_at
            """,
            (str(row["id"]),),
        )
        item_rows = cur.fetchall()
        items = [_changelist_item_row_to_response(item_row) for item_row in item_rows]

    shelf_id: Optional[UUID] = None
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT id FROM shelves WHERE changelist_id = %s ORDER BY created_at DESC LIMIT 1",
            (str(row["id"]),),
        )
        shelf_row = cur.fetchone()
        if shelf_row:
            shelf_id = shelf_row["id"]

    return ChangelistResponse(
        id=row["id"],
        project_id=row["project_id"],
        workspace_id=row.get("workspace_id"),
        created_by=row["created_by"],
        target_branch_id=row.get("target_branch_id"),
        status=row["status"],
        description=row.get("description"),
        submitter_notes=row.get("submitter_notes"),
        submitted_at=row.get("submitted_at"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        shelf_id=shelf_id,
        items=items,
    )


def _branch_merge_row_to_response(row: Dict[str, Any]) -> BranchMergeResponse:
    conflict_summary = row.get("conflict_summary")
    if isinstance(conflict_summary, str):
        try:
            conflict_summary = json.loads(conflict_summary)
        except json.JSONDecodeError:
            conflict_summary = {"raw": conflict_summary}
    return BranchMergeResponse(
        id=row["id"],
        project_id=row["project_id"],
        source_branch_id=row["source_branch_id"],
        target_branch_id=row["target_branch_id"],
        initiated_by=row["initiated_by"],
        status=row["status"],
        conflict_summary=conflict_summary,
        notes=row.get("notes"),
        created_at=row["created_at"],
        completed_at=row.get("completed_at"),
        updated_at=row["updated_at"],
    )


def _merge_conflict_row_to_response(row: Dict[str, Any]) -> MergeConflictResponse:
    return MergeConflictResponse(
        id=row["id"],
        branch_merge_id=row["branch_merge_id"],
        asset_id=row.get("asset_id"),
        asset_version_id=row.get("asset_version_id"),
        description=row.get("description"),
        resolution=row.get("resolution"),
        resolved_at=row.get("resolved_at"),
    )


def _merge_job_row_to_response(row: Dict[str, Any]) -> MergeJobResponse:
    conflict_snapshot = row.get("conflict_snapshot")
    if isinstance(conflict_snapshot, str):
        try:
            conflict_snapshot = json.loads(conflict_snapshot)
        except json.JSONDecodeError:
            conflict_snapshot = {"raw": conflict_snapshot}
    return MergeJobResponse(
        id=row["id"],
        branch_merge_id=row["branch_merge_id"],
        job_type=row["job_type"],
        status=row["status"],
        conflict_snapshot=conflict_snapshot,
        submit_gate_passed=row.get("submit_gate_passed", False),
        logs=row.get("logs"),
        started_at=row.get("started_at"),
        completed_at=row.get("completed_at"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _enforce_submit_gate(conn, merge_id: UUID) -> None:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT COUNT(*) AS gate_jobs FROM merge_jobs WHERE branch_merge_id = %s AND job_type = 'submit_gate'",
            (str(merge_id),),
        )
        gate_jobs_row = cur.fetchone()
        if not gate_jobs_row or gate_jobs_row["gate_jobs"] == 0:
            return

        cur.execute(
            """
            SELECT COUNT(*) AS gate_passes
            FROM merge_jobs
            WHERE branch_merge_id = %s
              AND submit_gate_passed IS TRUE
              AND status = 'completed'
            """,
            (str(merge_id),),
        )
        gate_row = cur.fetchone()
        if not gate_row or gate_row["gate_passes"] == 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Merge submit gate has not passed; ensure submit job completes successfully.",
            )

        cur.execute(
            """
            SELECT COUNT(*) AS outstanding
            FROM merge_jobs
            WHERE branch_merge_id = %s
              AND status IN ('queued', 'running', 'staged')
            """,
            (str(merge_id),),
        )
        outstanding_row = cur.fetchone()
        if outstanding_row and outstanding_row["outstanding"] > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Merge jobs are still running; wait for orchestration to finish before completing the merge.",
            )

        cur.execute(
            """
            SELECT COUNT(*) AS unresolved
            FROM merge_conflicts
            WHERE branch_merge_id = %s
              AND resolved_at IS NULL
            """,
            (str(merge_id),),
        )
        conflict_row = cur.fetchone()
        if conflict_row and conflict_row["unresolved"] > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Unresolved merge conflicts remain; resolve or stage them before completing the merge.",
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
                    SELECT s.id, s.workspace_id, s.asset_version_id, s.changelist_id, s.created_by, s.created_at, s.description
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
                changelist_id: Optional[str] = None
                if payload.changelist_id:
                    cur.execute(
                        "SELECT id, workspace_id, status FROM changelists WHERE id = %s",
                        (str(payload.changelist_id),),
                    )
                    changelist = cur.fetchone()
                    if not changelist:
                        raise HTTPException(status_code=404, detail="Changelist not found")
                    if str(changelist.get("workspace_id")) != str(payload.workspace_id):
                        raise HTTPException(status_code=400, detail="Changelist workspace mismatch")
                    if changelist.get("status") not in ("open", "pending_review"):
                        raise HTTPException(status_code=400, detail="Changelist is not accepting shelves")
                    changelist_id = str(payload.changelist_id)
                cur.execute(
                    """
                    INSERT INTO shelves (workspace_id, asset_version_id, changelist_id, created_by, description)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id, workspace_id, asset_version_id, changelist_id, created_by, created_at, description
                    """,
                    (
                        str(payload.workspace_id),
                        str(payload.asset_version_id),
                        changelist_id,
                        current_user["id"],
                        payload.description,
                    ),
                )
                row = cur.fetchone()
                if changelist_id:
                    cur.execute(
                        "UPDATE changelists SET updated_at = NOW() WHERE id = %s",
                        (changelist_id,),
                    )
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


@app.get("/projects/{project_id}/changelists", response_model=List[ChangelistResponse], tags=["changelists"])
def list_changelists(project_id: UUID, current_user: dict = Depends(get_current_user)):
    with get_connection() as conn:
        try:
            set_rls_user(conn, current_user["id"])
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT id, project_id, workspace_id, created_by, target_branch_id, status,
                           description, submitter_notes, submitted_at, created_at, updated_at
                    FROM changelists
                    WHERE project_id = %s
                    ORDER BY created_at DESC
                    """,
                    (str(project_id),),
                )
                rows = cur.fetchall()
            return [_changelist_row_to_response(conn, row) for row in rows]
        except HTTPException:
            conn.rollback()
            raise
        except Exception as exc:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/changelists", response_model=ChangelistResponse, status_code=status.HTTP_201_CREATED, tags=["changelists"])
def create_changelist(payload: ChangelistCreate, current_user: dict = Depends(get_current_user)):
    with get_connection() as conn:
        try:
            set_rls_user(conn, current_user["id"])
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute("SELECT project_id FROM workspaces WHERE id = %s", (str(payload.workspace_id),))
                workspace = cur.fetchone()
                if not workspace:
                    raise HTTPException(status_code=404, detail="Workspace not found")
                if str(workspace["project_id"]) != str(payload.project_id):
                    raise HTTPException(status_code=400, detail="Workspace does not belong to project")
                if payload.target_branch_id:
                    cur.execute("SELECT project_id FROM branches WHERE id = %s", (str(payload.target_branch_id),))
                    branch = cur.fetchone()
                    if not branch:
                        raise HTTPException(status_code=404, detail="Target branch not found")
                    if str(branch["project_id"]) != str(payload.project_id):
                        raise HTTPException(status_code=400, detail="Target branch not in project")
                if payload.shelf_id:
                    cur.execute(
                        "SELECT workspace_id, changelist_id FROM shelves WHERE id = %s",
                        (str(payload.shelf_id),),
                    )
                    shelf = cur.fetchone()
                    if not shelf:
                        raise HTTPException(status_code=404, detail="Shelf not found")
                    if str(shelf["workspace_id"]) != str(payload.workspace_id):
                        raise HTTPException(status_code=400, detail="Shelf workspace mismatch")
                    if shelf.get("changelist_id") is not None:
                        raise HTTPException(status_code=400, detail="Shelf is already linked to a changelist")
                cur.execute(
                    """
                    INSERT INTO changelists (project_id, workspace_id, created_by, target_branch_id, description)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id, project_id, workspace_id, created_by, target_branch_id, status,
                              description, submitter_notes, submitted_at, created_at, updated_at
                    """,
                    (
                        str(payload.project_id),
                        str(payload.workspace_id),
                        current_user["id"],
                        str(payload.target_branch_id) if payload.target_branch_id else None,
                        payload.description,
                    ),
                )
                changelist = cur.fetchone()
                if payload.shelf_id:
                    cur.execute(
                        "UPDATE shelves SET changelist_id = %s WHERE id = %s",
                        (str(changelist["id"]), str(payload.shelf_id)),
                    )
                conn.commit()
                return _changelist_row_to_response(conn, changelist)
        except HTTPException:
            conn.rollback()
            raise
        except Exception as exc:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/changelists/{changelist_id}", response_model=ChangelistResponse, tags=["changelists"])
def get_changelist(changelist_id: UUID, current_user: dict = Depends(get_current_user)):
    with get_connection() as conn:
        try:
            set_rls_user(conn, current_user["id"])
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT id, project_id, workspace_id, created_by, target_branch_id, status,
                           description, submitter_notes, submitted_at, created_at, updated_at
                    FROM changelists
                    WHERE id = %s
                    """,
                    (str(changelist_id),),
                )
                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="Changelist not found")
                return _changelist_row_to_response(conn, row)
        except HTTPException:
            conn.rollback()
            raise
        except Exception as exc:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post(
    "/changelists/{changelist_id}/items",
    response_model=ChangelistResponse,
    status_code=status.HTTP_200_OK,
    tags=["changelists"],
)
def add_changelist_item(
    changelist_id: UUID,
    payload: ChangelistItemCreate,
    current_user: dict = Depends(get_current_user),
):
    with get_connection() as conn:
        try:
            set_rls_user(conn, current_user["id"])
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "SELECT project_id, status FROM changelists WHERE id = %s",
                    (str(changelist_id),),
                )
                changelist = cur.fetchone()
                if not changelist:
                    raise HTTPException(status_code=404, detail="Changelist not found")
                if changelist["status"] not in ("open", "pending_review"):
                    raise HTTPException(status_code=400, detail="Changelist is not editable")
                if payload.action not in ("add", "edit", "delete", "integrate"):
                    raise HTTPException(status_code=400, detail="Unsupported changelist action")
                cur.execute(
                    """
                    SELECT a.project_id
                    FROM asset_versions av
                    JOIN assets a ON a.id = av.asset_id
                    WHERE av.id = %s
                    """,
                    (str(payload.asset_version_id),),
                )
                asset_project = cur.fetchone()
                if not asset_project:
                    raise HTTPException(status_code=404, detail="Asset version not found")
                if str(asset_project["project_id"]) != str(changelist["project_id"]):
                    raise HTTPException(status_code=400, detail="Asset version from different project")
                target_branch_id = None
                if payload.target_branch_id:
                    cur.execute("SELECT project_id FROM branches WHERE id = %s", (str(payload.target_branch_id),))
                    branch = cur.fetchone()
                    if not branch:
                        raise HTTPException(status_code=404, detail="Target branch not found")
                    if str(branch["project_id"]) != str(changelist["project_id"]):
                        raise HTTPException(status_code=400, detail="Target branch not in project")
                    target_branch_id = str(payload.target_branch_id)
                cur.execute(
                    """
                    INSERT INTO changelist_items (changelist_id, asset_version_id, action, target_branch_id)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (changelist_id, asset_version_id) DO UPDATE SET
                        action = EXCLUDED.action,
                        target_branch_id = EXCLUDED.target_branch_id,
                        created_at = NOW()
                    RETURNING id, asset_version_id, action, target_branch_id, created_at
                    """,
                    (
                        str(changelist_id),
                        str(payload.asset_version_id),
                        payload.action,
                        target_branch_id,
                    ),
                )
                cur.fetchone()
                cur.execute("UPDATE changelists SET updated_at = NOW() WHERE id = %s", (str(changelist_id),))
                cur.execute(
                    """
                    SELECT id, project_id, workspace_id, created_by, target_branch_id, status,
                           description, submitter_notes, submitted_at, created_at, updated_at
                    FROM changelists
                    WHERE id = %s
                    """,
                    (str(changelist_id),),
                )
                row = cur.fetchone()
                conn.commit()
                return _changelist_row_to_response(conn, row)
        except HTTPException:
            conn.rollback()
            raise
        except Exception as exc:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.delete(
    "/changelists/{changelist_id}/items/{item_id}",
    response_model=ChangelistResponse,
    tags=["changelists"],
)
def remove_changelist_item(
    changelist_id: UUID,
    item_id: UUID,
    current_user: dict = Depends(get_current_user),
):
    with get_connection() as conn:
        try:
            set_rls_user(conn, current_user["id"])
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "DELETE FROM changelist_items WHERE id = %s AND changelist_id = %s",
                    (str(item_id), str(changelist_id)),
                )
                if cur.rowcount == 0:
                    raise HTTPException(status_code=404, detail="Changelist item not found")
                cur.execute("UPDATE changelists SET updated_at = NOW() WHERE id = %s", (str(changelist_id),))
                cur.execute(
                    """
                    SELECT id, project_id, workspace_id, created_by, target_branch_id, status,
                           description, submitter_notes, submitted_at, created_at, updated_at
                    FROM changelists
                    WHERE id = %s
                    """,
                    (str(changelist_id),),
                )
                row = cur.fetchone()
                conn.commit()
                if not row:
                    raise HTTPException(status_code=404, detail="Changelist not found")
                return _changelist_row_to_response(conn, row)
        except HTTPException:
            conn.rollback()
            raise
        except Exception as exc:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post(
    "/changelists/{changelist_id}/submit",
    response_model=ChangelistResponse,
    tags=["changelists"],
)
def submit_changelist(
    changelist_id: UUID,
    payload: ChangelistSubmitRequest,
    current_user: dict = Depends(get_current_user),
):
    desired_status = payload.status or "submitted"
    if desired_status not in ("submitted", "pending_review"):
        raise HTTPException(status_code=400, detail="Unsupported changelist status")
    with get_connection() as conn:
        try:
            set_rls_user(conn, current_user["id"])
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "SELECT id, project_id, target_branch_id, status FROM changelists WHERE id = %s",
                    (str(changelist_id),),
                )
                changelist = cur.fetchone()
                if not changelist:
                    raise HTTPException(status_code=404, detail="Changelist not found")
                if changelist["status"] not in ("open", "pending_review") and changelist["status"] != desired_status:
                    raise HTTPException(status_code=400, detail="Changelist already finalized")
                if not changelist.get("target_branch_id"):
                    raise HTTPException(status_code=400, detail="Target branch is required before submit")
                cur.execute(
                    "SELECT COUNT(*) AS item_count FROM changelist_items WHERE changelist_id = %s",
                    (str(changelist_id),),
                )
                count_row = cur.fetchone()
                if not count_row or count_row["item_count"] == 0:
                    raise HTTPException(status_code=400, detail="Changelist must include at least one asset version")
                cur.execute(
                    """
                    UPDATE changelists
                    SET status = %s,
                        submitter_notes = %s,
                        submitted_at = NOW(),
                        updated_at = NOW()
                    WHERE id = %s
                    RETURNING id, project_id, workspace_id, created_by, target_branch_id, status,
                              description, submitter_notes, submitted_at, created_at, updated_at
                    """,
                    (
                        desired_status,
                        payload.submitter_notes,
                        str(changelist_id),
                    ),
                )
                row = cur.fetchone()
                conn.commit()
                if not row:
                    raise HTTPException(status_code=404, detail="Changelist not found")
                return _changelist_row_to_response(conn, row)
        except HTTPException:
            conn.rollback()
            raise
        except Exception as exc:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get(
    "/projects/{project_id}/branch-merges",
    response_model=List[BranchMergeResponse],
    tags=["branch-merges"],
)
def list_branch_merges(project_id: UUID, current_user: dict = Depends(get_current_user)):
    with get_connection() as conn:
        try:
            set_rls_user(conn, current_user["id"])
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT id, project_id, source_branch_id, target_branch_id, initiated_by, status,
                           conflict_summary, notes, created_at, completed_at, updated_at
                    FROM branch_merges
                    WHERE project_id = %s
                    ORDER BY created_at DESC
                    """,
                    (str(project_id),),
                )
                rows = cur.fetchall()
                return [_branch_merge_row_to_response(row) for row in rows]
        except HTTPException:
            conn.rollback()
            raise
        except Exception as exc:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post(
    "/branch-merges",
    response_model=BranchMergeResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["branch-merges"],
)
def create_branch_merge(payload: BranchMergeCreate, current_user: dict = Depends(get_current_user)):
    if payload.source_branch_id == payload.target_branch_id:
        raise HTTPException(status_code=400, detail="Source and target branches must differ")
    queued_job_ids: List[str] = []
    response: Optional[BranchMergeResponse] = None
    with get_connection() as conn:
        try:
            set_rls_user(conn, current_user["id"])
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute("SELECT project_id FROM branches WHERE id = %s", (str(payload.source_branch_id),))
                source_branch = cur.fetchone()
                if not source_branch:
                    raise HTTPException(status_code=404, detail="Source branch not found")
                cur.execute("SELECT project_id FROM branches WHERE id = %s", (str(payload.target_branch_id),))
                target_branch = cur.fetchone()
                if not target_branch:
                    raise HTTPException(status_code=404, detail="Target branch not found")
                if str(source_branch["project_id"]) != str(payload.project_id) or str(target_branch["project_id"]) != str(payload.project_id):
                    raise HTTPException(status_code=400, detail="Branches do not belong to project")
                cur.execute(
                    """
                    INSERT INTO branch_merges (project_id, source_branch_id, target_branch_id, initiated_by, notes)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id, project_id, source_branch_id, target_branch_id, initiated_by, status,
                              conflict_summary, notes, created_at, completed_at, updated_at
                    """,
                    (
                        str(payload.project_id),
                        str(payload.source_branch_id),
                        str(payload.target_branch_id),
                        current_user["id"],
                        payload.notes,
                    ),
                )
                merge = cur.fetchone()
                if not merge:
                    raise HTTPException(status_code=500, detail="Failed to create branch merge")

                merge_id = merge["id"]
                if payload.auto_integrate:
                    cur.execute(
                        """
                        INSERT INTO merge_jobs (branch_merge_id, job_type)
                        VALUES (%s, %s)
                        RETURNING id
                        """,
                        (str(merge_id), "auto_integrate"),
                    )
                    job_row = cur.fetchone()
                    if job_row:
                        queued_job_ids.append(str(job_row["id"]))
                if payload.stage_conflicts:
                    cur.execute(
                        """
                        INSERT INTO merge_jobs (branch_merge_id, job_type, status)
                        VALUES (%s, %s, %s)
                        """,
                        (str(merge_id), "conflict_staging", "staged"),
                    )
                if payload.requires_submit_gate:
                    cur.execute(
                        """
                        INSERT INTO merge_jobs (branch_merge_id, job_type)
                        VALUES (%s, %s)
                        RETURNING id
                        """,
                        (str(merge_id), "submit_gate"),
                    )
                    job_row = cur.fetchone()
                    if job_row:
                        queued_job_ids.append(str(job_row["id"]))

                cur.execute(
                    """
                    SELECT id, project_id, source_branch_id, target_branch_id, initiated_by, status,
                           conflict_summary, notes, created_at, completed_at, updated_at
                    FROM branch_merges
                    WHERE id = %s
                    """,
                    (str(merge_id),),
                )
                merge_row = cur.fetchone()
                response = _branch_merge_row_to_response(merge_row)
                conn.commit()
        except HTTPException:
            conn.rollback()
            raise
        except Exception as exc:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(exc)) from exc
    enqueue_many(queued_job_ids)
    if response is None:
        raise HTTPException(status_code=500, detail="Failed to create branch merge")
    return response


@app.patch("/branch-merges/{merge_id}", response_model=BranchMergeResponse, tags=["branch-merges"])
def update_branch_merge(merge_id: UUID, payload: BranchMergeUpdate, current_user: dict = Depends(get_current_user)):
    set_clauses: List[str] = []
    params: List[Any] = []
    needs_submit_gate = False
    mark_complete_on_merge = False
    if payload.status is not None:
        if payload.status not in ("pending", "merged", "conflicted", "cancelled"):
            raise HTTPException(status_code=400, detail="Invalid merge status")
        set_clauses.append("status = %s")
        params.append(payload.status)
        if payload.status == "merged":
            needs_submit_gate = True
            mark_complete_on_merge = True
    if payload.conflict_summary is not None:
        set_clauses.append("conflict_summary = %s")
        if isinstance(payload.conflict_summary, (dict, list)):
            params.append(json.dumps(payload.conflict_summary))
        else:
            params.append(payload.conflict_summary)
    if payload.notes is not None:
        set_clauses.append("notes = %s")
        params.append(payload.notes)
    if payload.completed is not None:
        if payload.completed:
            set_clauses.append("completed_at = NOW()")
            needs_submit_gate = True
        else:
            set_clauses.append("completed_at = NULL")
    if not set_clauses:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided")

    with get_connection() as conn:
        try:
            set_rls_user(conn, current_user["id"])
            if needs_submit_gate:
                _enforce_submit_gate(conn, merge_id)
            with conn.cursor(row_factory=dict_row) as cur:
                if mark_complete_on_merge and not any("completed_at" in clause for clause in set_clauses):
                    set_clauses.append("completed_at = NOW()")
                set_clauses.append("updated_at = NOW()")
                query = (
                    "UPDATE branch_merges SET "
                    + ", ".join(set_clauses)
                    + " WHERE id = %s RETURNING id, project_id, source_branch_id, target_branch_id, initiated_by, status, conflict_summary, notes, created_at, completed_at, updated_at"
                )
                params.append(str(merge_id))
                cur.execute(query, params)
                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="Branch merge not found")
                conn.commit()
                return _branch_merge_row_to_response(row)
        except HTTPException:
            conn.rollback()
            raise
        except Exception as exc:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get(
    "/branch-merges/{merge_id}/conflicts",
    response_model=List[MergeConflictResponse],
    tags=["branch-merges"],
)
def list_merge_conflicts(merge_id: UUID, current_user: dict = Depends(get_current_user)):
    with get_connection() as conn:
        try:
            set_rls_user(conn, current_user["id"])
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT id, branch_merge_id, asset_id, asset_version_id, description, resolution, resolved_at
                    FROM merge_conflicts
                    WHERE branch_merge_id = %s
                    ORDER BY created_at DESC NULLS LAST
                    """,
                    (str(merge_id),),
                )
                rows = cur.fetchall()
                return [_merge_conflict_row_to_response(row) for row in rows]
        except HTTPException:
            conn.rollback()
            raise
        except Exception as exc:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post(
    "/branch-merges/{merge_id}/conflicts",
    response_model=MergeConflictResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["branch-merges"],
)
def create_merge_conflict(
    merge_id: UUID,
    payload: MergeConflictCreate,
    current_user: dict = Depends(get_current_user),
):
    with get_connection() as conn:
        try:
            set_rls_user(conn, current_user["id"])
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute("SELECT id FROM branch_merges WHERE id = %s", (str(merge_id),))
                merge = cur.fetchone()
                if not merge:
                    raise HTTPException(status_code=404, detail="Branch merge not found")
                cur.execute(
                    """
                    INSERT INTO merge_conflicts (branch_merge_id, asset_id, asset_version_id, description)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id, branch_merge_id, asset_id, asset_version_id, description, resolution, resolved_at
                    """,
                    (
                        str(merge_id),
                        str(payload.asset_id) if payload.asset_id else None,
                        str(payload.asset_version_id) if payload.asset_version_id else None,
                        payload.description,
                    ),
                )
                row = cur.fetchone()
                conn.commit()
                return _merge_conflict_row_to_response(row)
        except HTTPException:
            conn.rollback()
            raise
        except Exception as exc:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.patch("/merge-conflicts/{conflict_id}", response_model=MergeConflictResponse, tags=["branch-merges"])
def update_merge_conflict(
    conflict_id: UUID,
    payload: MergeConflictUpdate,
    current_user: dict = Depends(get_current_user),
):
    set_clauses: List[str] = []
    params: List[Any] = []
    if payload.resolution is not None:
        set_clauses.append("resolution = %s")
        params.append(payload.resolution)
    if payload.resolved is not None:
        if payload.resolved:
            set_clauses.append("resolved_at = NOW()")
        else:
            set_clauses.append("resolved_at = NULL")
    if not set_clauses:
        raise HTTPException(status_code=400, detail="No fields provided")

    with get_connection() as conn:
        try:
            set_rls_user(conn, current_user["id"])
            with conn.cursor(row_factory=dict_row) as cur:
                query = (
                    "UPDATE merge_conflicts SET "
                    + ", ".join(set_clauses)
                    + " WHERE id = %s RETURNING id, branch_merge_id, asset_id, asset_version_id, description, resolution, resolved_at"
                )
                params.append(str(conflict_id))
                cur.execute(query, params)
                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="Merge conflict not found")
                conn.commit()
                return _merge_conflict_row_to_response(row)
        except HTTPException:
            conn.rollback()
            raise
        except Exception as exc:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get(
    "/branch-merges/{merge_id}/jobs",
    response_model=List[MergeJobResponse],
    tags=["branch-merges"],
)
def list_merge_jobs(merge_id: UUID, current_user: dict = Depends(get_current_user)):
    with get_connection() as conn:
        try:
            set_rls_user(conn, current_user["id"])
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT id, branch_merge_id, job_type, status, conflict_snapshot, submit_gate_passed,
                           logs, started_at, completed_at, created_at, updated_at
                    FROM merge_jobs
                    WHERE branch_merge_id = %s
                    ORDER BY created_at
                    """,
                    (str(merge_id),),
                )
                rows = cur.fetchall()
                return [_merge_job_row_to_response(row) for row in rows]
        except HTTPException:
            conn.rollback()
            raise
        except Exception as exc:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post(
    "/branch-merges/{merge_id}/jobs",
    response_model=MergeJobResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["branch-merges"],
)
def create_merge_job(merge_id: UUID, payload: MergeJobCreate, current_user: dict = Depends(get_current_user)):
    if payload.job_type not in MERGE_JOB_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported merge job type")
    job_status = payload.status or "queued"
    if job_status not in MERGE_JOB_STATUSES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported merge job status")

    conflict_snapshot_value = None
    if payload.conflict_snapshot is not None:
        conflict_snapshot_value = json.dumps(payload.conflict_snapshot)

    started_at = None
    completed_at = None
    if job_status in {"running", "staged", "completed", "failed"}:
        started_at = datetime.utcnow()
    if job_status in {"completed", "failed"}:
        completed_at = datetime.utcnow()

    submit_gate_passed = payload.submit_gate_passed if payload.job_type == "submit_gate" else False

    queued_job_id: Optional[str] = None
    response: Optional[MergeJobResponse] = None
    with get_connection() as conn:
        try:
            set_rls_user(conn, current_user["id"])
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute("SELECT id FROM branch_merges WHERE id = %s", (str(merge_id),))
                branch_merge = cur.fetchone()
                if not branch_merge:
                    raise HTTPException(status_code=404, detail="Branch merge not found")

                cur.execute(
                    """
                    INSERT INTO merge_jobs (branch_merge_id, job_type, status, conflict_snapshot, submit_gate_passed, logs, started_at, completed_at)
                    VALUES (%s, %s, %s, %s::jsonb, %s, %s, %s, %s)
                    RETURNING id, branch_merge_id, job_type, status, conflict_snapshot, submit_gate_passed,
                              logs, started_at, completed_at, created_at, updated_at
                    """,
                    (
                        str(merge_id),
                        payload.job_type,
                        job_status,
                        conflict_snapshot_value,
                        submit_gate_passed,
                        payload.logs,
                        started_at,
                        completed_at,
                    ),
                )
                row = cur.fetchone()
                conn.commit()
                response = _merge_job_row_to_response(row)
                queued_job_id = str(row["id"]) if job_status == "queued" else None
        except HTTPException:
            conn.rollback()
            raise
        except Exception as exc:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(exc)) from exc
    if queued_job_id:
        enqueue_merge_job(queued_job_id)
    if response is None:
        raise HTTPException(status_code=500, detail="Failed to create merge job")
    return response


@app.patch("/merge-jobs/{job_id}", response_model=MergeJobResponse, tags=["branch-merges"])
def update_merge_job(job_id: UUID, payload: MergeJobUpdate, current_user: dict = Depends(get_current_user)):
    updates: List[str] = []
    params: List[Any] = []
    new_status: Optional[str] = None
    queue_after_update = False
    response: Optional[MergeJobResponse] = None
    if payload.status is not None:
        if payload.status not in MERGE_JOB_STATUSES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported merge job status")
        updates.append("status = %s")
        params.append(payload.status)
        new_status = payload.status
        if payload.status == "queued":
            queue_after_update = True
    if payload.conflict_snapshot is not None:
        updates.append("conflict_snapshot = %s::jsonb")
        params.append(json.dumps(payload.conflict_snapshot))
    if payload.submit_gate_passed is not None:
        updates.append("submit_gate_passed = %s")
        params.append(payload.submit_gate_passed)
    if payload.logs is not None:
        updates.append("logs = %s")
        params.append(payload.logs)
    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided")

    with get_connection() as conn:
        try:
            set_rls_user(conn, current_user["id"])
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "SELECT id, branch_merge_id, job_type FROM merge_jobs WHERE id = %s",
                    (str(job_id),),
                )
                job_row = cur.fetchone()
                if not job_row:
                    raise HTTPException(status_code=404, detail="Merge job not found")
                if payload.submit_gate_passed and job_row["job_type"] != "submit_gate":
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Only submit gate jobs can be marked as passing the submit gate.",
                    )

                if new_status in {"running", "staged"}:
                    updates.append("started_at = COALESCE(started_at, NOW())")
                if new_status in {"completed", "failed"}:
                    updates.append("started_at = COALESCE(started_at, NOW())")
                    updates.append("completed_at = NOW()")

                updates.append("updated_at = NOW()")
                query = "UPDATE merge_jobs SET " + ", ".join(updates) + " WHERE id = %s RETURNING id, branch_merge_id, job_type, status, conflict_snapshot, submit_gate_passed, logs, started_at, completed_at, created_at, updated_at"
                params.append(str(job_id))
                cur.execute(query, params)
                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="Merge job not found")
                conn.commit()
                response = _merge_job_row_to_response(row)
        except HTTPException:
            conn.rollback()
            raise
        except Exception as exc:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(exc)) from exc
    if queue_after_update:
        enqueue_merge_job(str(job_id))
    if response is None:
        raise HTTPException(status_code=500, detail="Failed to update merge job")
    return response


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


@app.get(
    "/render/opencue/summary",
    response_model=OpenCueSummaryResponse,
    tags=["render"],
)
def get_opencue_summary(current_user: dict = Depends(get_current_user)):
    payload = opencue_integration.get_summary()
    return OpenCueSummaryResponse(
        enabled=payload["enabled"],
        available=payload["available"],
        summary=payload["summary"],
        last_updated=payload["last_updated"],
        source=payload.get("source"),
        message=payload.get("message"),
    )


@app.get(
    "/render/opencue/details",
    response_model=OpenCueDetailedResponse,
    tags=["render"],
)
def get_opencue_details(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    payload = opencue_integration.get_details()
    return OpenCueDetailedResponse(**payload)


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
