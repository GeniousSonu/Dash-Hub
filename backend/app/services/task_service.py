import json
import sqlite3
from typing import Any

from backend.app.core.database import new_uuid, utc_now_iso
from backend.app.models.enums import TaskPriority, TaskStatus
from backend.app.services.audit_service import AuditService


class TaskValidationError(ValueError):
    """Raised when task lifecycle transitions or dependencies are violated."""


class TaskService:
    @classmethod
    def create_task(
        cls,
        conn: sqlite3.Connection,
        *,
        project_id: str,
        title: str,
        owner_id: str,
        actor_user_id: str,
        description: str = "",
        website_id: str | None = None,
        session_id: str | None = None,
        issue_id: str | None = None,
        priority: str = "normal",
        status: str = "ready",
        due_at: str | None = None,
        estimated_hours: float = 0.0,
        acceptance_criteria: str = "",
        depends_on: list[str] | None = None,
    ) -> dict[str, Any]:
        task_id = new_uuid()
        now = utc_now_iso()
        dep_list = depends_on or []

        conn.execute(
            """
            INSERT INTO tasks (
                id, project_id, title, description, owner_id, website_id, session_id,
                issue_id, priority, status, due_at, estimated_hours, actual_hours,
                acceptance_criteria, depends_on_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0.0, ?, ?, ?, ?)
            """,
            (
                task_id,
                project_id,
                title,
                description,
                owner_id,
                website_id,
                session_id,
                issue_id,
                priority,
                status,
                due_at,
                estimated_hours,
                acceptance_criteria,
                json.dumps(dep_list),
                now,
                now,
            ),
        )
        AuditService.log_event(
            conn,
            actor_user_id=actor_user_id,
            entity_type="task",
            entity_id=task_id,
            action="task_created",
            summary=f"Created task '{title}'",
            after_state={"title": title, "status": status, "owner_id": owner_id},
        )
        return cls.get_task(conn, task_id)

    @classmethod
    def update_task_status(
        cls,
        conn: sqlite3.Connection,
        *,
        task_id: str,
        new_status: str,
        actor_user_id: str,
        cancellation_reason: str = "",
        new_owner_id: str | None = None,
    ) -> dict[str, Any]:
        task = cls.get_task(conn, task_id)
        if not task:
            raise TaskValidationError(f"Task '{task_id}' not found.")

        if new_status == TaskStatus.COMPLETED.value:
            depends_on = json.loads(task.get("depends_on_json") or "[]")
            for dep_id in depends_on:
                dep_row = conn.execute("SELECT id, title, status FROM tasks WHERE id = ?", (dep_id,)).fetchone()
                if dep_row and dep_row["status"] != TaskStatus.COMPLETED.value:
                    raise TaskValidationError(
                        f"Cannot complete task while dependency '{dep_row['title']}' is incomplete (status: {dep_row['status']})."
                    )

        if new_status == TaskStatus.CANCELLED.value:
            reason = cancellation_reason.strip()
            if not reason:
                raise TaskValidationError("A cancellation reason is mandatory when cancelling a task.")

        now = utc_now_iso()
        completed_at = now if new_status == TaskStatus.COMPLETED.value else task.get("completed_at")
        owner_id = new_owner_id if new_owner_id else task["owner_id"]

        conn.execute(
            """
            UPDATE tasks
            SET status = ?, cancellation_reason = ?, completed_at = ?, owner_id = ?, updated_at = ?
            WHERE id = ?
            """,
            (new_status, cancellation_reason if new_status == TaskStatus.CANCELLED.value else "", completed_at, owner_id, now, task_id),
        )
        AuditService.log_event(
            conn,
            actor_user_id=actor_user_id,
            entity_type="task",
            entity_id=task_id,
            action="task_status_updated",
            summary=f"Task '{task['title']}' status updated from {task['status']} to {new_status}",
            before_state={"status": task["status"]},
            after_state={"status": new_status, "cancellation_reason": cancellation_reason},
        )
        return cls.get_task(conn, task_id)

    @classmethod
    def add_work_log(
        cls,
        conn: sqlite3.Connection,
        *,
        task_id: str,
        author_id: str,
        what_was_done: str,
        what_remains: str = "",
        blockers: str = "",
        next_action: str = "",
        hours_logged: float = 0.0,
    ) -> dict[str, Any]:
        task = cls.get_task(conn, task_id)
        if not task:
            raise TaskValidationError(f"Task '{task_id}' not found.")

        log_id = new_uuid()
        now = utc_now_iso()
        conn.execute(
            """
            INSERT INTO task_work_logs (
                id, task_id, author_id, what_was_done, what_remains, blockers, next_action, hours_logged, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                log_id,
                task_id,
                author_id,
                what_was_done,
                what_remains,
                blockers,
                next_action,
                hours_logged,
                now,
            ),
        )
        new_total_hours = float(task.get("actual_hours") or 0.0) + hours_logged
        conn.execute(
            "UPDATE tasks SET actual_hours = ?, updated_at = ? WHERE id = ?",
            (new_total_hours, now, task_id),
        )
        AuditService.log_event(
            conn,
            actor_user_id=author_id,
            entity_type="task_work_log",
            entity_id=log_id,
            action="work_log_added",
            summary=f"Logged {hours_logged}h on task '{task['title']}'",
            after_state={"hours_logged": hours_logged, "new_total_hours": new_total_hours},
        )
        return {
            "id": log_id,
            "task_id": task_id,
            "hours_logged": hours_logged,
            "total_task_hours": new_total_hours,
        }

    @classmethod
    def list_work_logs(cls, conn: sqlite3.Connection, task_id: str) -> list[dict[str, Any]]:
        rows = conn.execute(
            """
            SELECT l.*, u.full_name AS author_name, u.email AS author_email
            FROM task_work_logs l
            LEFT JOIN users u ON l.author_id = u.id
            WHERE l.task_id = ?
            ORDER BY l.created_at DESC
            """,
            (task_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    @classmethod
    def get_task(cls, conn: sqlite3.Connection, task_id: str) -> dict[str, Any]:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return dict(row) if row else {}

