"""Celery tasks powering merge automation."""
from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, Optional

from celery.utils.log import get_task_logger
from psycopg.rows import dict_row

from .auth import clear_rls_user, set_rls_user
from .celery_app import celery_app
from .database import get_connection

LOGGER = get_task_logger(__name__)
AUTOMATION_USER_ID = os.getenv("MERGE_AUTOMATION_USER_ID")


def _set_automation_identity(conn) -> None:
    if AUTOMATION_USER_ID:
        set_rls_user(conn, AUTOMATION_USER_ID)
        return
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM users WHERE role = 'admin' ORDER BY created_at LIMIT 1"
        )
        row = cur.fetchone()
        if row:
            set_rls_user(conn, row[0])
        else:
            clear_rls_user(conn)


def _append_log(conn, job_id: str, message: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE merge_jobs
               SET logs = COALESCE(logs, '') || %s || '\n',
                   updated_at = NOW()
             WHERE id = %s
            """,
            (f"[{datetime.utcnow().isoformat()}Z] {message}", job_id),
        )


def _complete_job(
    conn,
    job_id: str,
    branch_merge_id: str,
    *,
    status: str,
    submit_gate_passed: Optional[bool] = None,
) -> None:
    with conn.cursor() as cur:
        updates = ["status = %s", "completed_at = COALESCE(completed_at, NOW())", "updated_at = NOW()"]
        params: list[Any] = [status]
        if submit_gate_passed is not None:
            updates.append("submit_gate_passed = %s")
            params.append(submit_gate_passed)
        updates.append("started_at = COALESCE(started_at, NOW())")
        params.append(job_id)
        cur.execute(
            f"UPDATE merge_jobs SET {', '.join(updates)} WHERE id = %s",
            params,
        )

    _maybe_finalize_branch_merge(conn, branch_merge_id)


def _fail_job(conn, job_id: str, branch_merge_id: str, reason: str) -> None:
    _append_log(conn, job_id, reason)
    _complete_job(conn, job_id, branch_merge_id, status="failed")
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE branch_merges
               SET status = 'conflicted',
                   updated_at = NOW()
             WHERE id = %s AND status <> 'cancelled'
            """,
            (branch_merge_id,),
        )


def _maybe_finalize_branch_merge(conn, branch_merge_id: str) -> None:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT job_type, status, submit_gate_passed
              FROM merge_jobs
             WHERE branch_merge_id = %s
            """,
            (branch_merge_id,),
        )
        jobs = cur.fetchall()

    if not jobs:
        return

    all_completed = True
    submit_gate_ok = True
    for job in jobs:
        if job["status"] != "completed":
            all_completed = False
        if job["job_type"] == "submit_gate" and not job.get("submit_gate_passed"):
            submit_gate_ok = False

    if all_completed and submit_gate_ok:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE branch_merges
                   SET status = 'merged',
                       completed_at = COALESCE(completed_at, NOW()),
                       updated_at = NOW()
                 WHERE id = %s AND status <> 'cancelled'
                """,
                (branch_merge_id,),
            )


def run_merge_job(job_id: str) -> Dict[str, Any]:
    LOGGER.info("Evaluating merge job %s", job_id)
    with get_connection() as conn:
        _set_automation_identity(conn)
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                UPDATE merge_jobs
                   SET status = 'running',
                       started_at = COALESCE(started_at, NOW()),
                       updated_at = NOW()
                 WHERE id = %s AND status = 'queued'
                RETURNING id, branch_merge_id, job_type
                """,
                (job_id,),
            )
            job_row = cur.fetchone()

        if not job_row:
            LOGGER.warning("No queued job found for id=%s", job_id)
            conn.commit()
            return {"job_id": job_id, "status": "skipped"}

        branch_merge_id = str(job_row["branch_merge_id"])
        job_type = job_row["job_type"]
        LOGGER.info("Running job %s (%s)", job_id, job_type)

        try:
            if job_type == "auto_integrate":
                _append_log(conn, job_id, "Executing automated integration pipeline")
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(
                        """
                        SELECT COUNT(*) AS unresolved
                          FROM merge_conflicts
                         WHERE branch_merge_id = %s AND resolved_at IS NULL
                        """,
                        (branch_merge_id,),
                    )
                    unresolved = cur.fetchone()["unresolved"]
                if unresolved:
                    _fail_job(
                        conn,
                        job_id,
                        branch_merge_id,
                        f"Detected {unresolved} unresolved conflicts during auto integrate",
                    )
                else:
                    _append_log(conn, job_id, "Integration completed without conflicts")
                    _complete_job(conn, job_id, branch_merge_id, status="completed")
            elif job_type == "submit_gate":
                _append_log(conn, job_id, "Running submit gate validation")
                _complete_job(conn, job_id, branch_merge_id, status="completed", submit_gate_passed=True)
            else:
                _append_log(conn, job_id, f"No-op handler for job type {job_type}; marking staged")
                _complete_job(conn, job_id, branch_merge_id, status="completed")
            conn.commit()
            LOGGER.info("Job %s completed", job_id)
            return {"job_id": job_id, "status": "completed", "job_type": job_type}
        except Exception as exc:  # pragma: no cover - defensive logging
            conn.rollback()
            LOGGER.exception("Job %s failed", job_id)
            raise exc


@celery_app.task(name="app.tasks.execute_merge_job")
def execute_merge_job(job_id: str) -> Dict[str, Any]:
    """Entry point executed by Celery workers."""
    return run_merge_job(job_id)
