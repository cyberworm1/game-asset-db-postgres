import json
from pathlib import Path
from typing import List
from uuid import UUID

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile, status
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
    LockRequest,
    ReviewResponse,
    ReviewUpdateRequest,
    TokenRequest,
    TokenResponse,
    WorkspaceCreate,
)
from .storage import save_asset_file

app = FastAPI(title="Asset Depot Service", version="1.0.0")

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


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
                if asset["metadata"] is None:
                    asset["metadata"] = {}
                elif isinstance(asset["metadata"], str):
                    asset["metadata"] = json.loads(asset["metadata"])
                return AssetResponse(**asset)
        except Exception as exc:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/projects/{project_id}/assets", response_model=List[AssetResponse], tags=["assets"])
def list_project_assets(project_id: UUID, current_user: dict = Depends(get_current_user)):
    with get_connection() as conn:
        try:
            set_rls_user(conn, current_user["id"])
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "SELECT id, name, type, project_id, metadata, created_by FROM assets WHERE project_id = %s",
                    (str(project_id),),
                )
                assets = cur.fetchall()
                asset_map = {}
                for asset in assets:
                    if asset["metadata"] is None:
                        asset["metadata"] = {}
                    elif isinstance(asset["metadata"], str):
                        asset["metadata"] = json.loads(asset["metadata"])
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
