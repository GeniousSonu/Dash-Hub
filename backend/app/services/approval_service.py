import sqlite3
from typing import Any

from backend.app.core.database import new_uuid, utc_now_iso
from backend.app.core.security import ROLE_PERMISSIONS
from backend.app.models.enums import ApprovalStatus
from backend.app.services.audit_service import AuditService


class ApprovalPolicyError(ValueError):
    """Raised when an approval decision violates separation of duties or role permissions."""


class ApprovalService:
    @classmethod
    def request_approval(
        cls,
        conn: sqlite3.Connection,
        *,
        project_id: str,
        action_type: str,
        summary: str,
        requester_id: str,
        website_id: str | None = None,
        session_id: str | None = None,
        checklist_item_id: str | None = None,
        risk_notes: str = "",
        approver_id: str | None = None,
    ) -> dict[str, Any]:
        app_id = new_uuid()
        now = utc_now_iso()
        conn.execute(
            """
            INSERT INTO approvals (
                id, project_id, website_id, session_id, checklist_item_id,
                action_type, summary, risk_notes, requester_id, approver_id,
                status, requested_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
            """,
            (
                app_id,
                project_id,
                website_id,
                session_id,
                checklist_item_id,
                action_type,
                summary,
                risk_notes,
                requester_id,
                approver_id,
                now,
            ),
        )
        AuditService.log_event(
            conn,
            actor_user_id=requester_id,
            entity_type="approval",
            entity_id=app_id,
            action="approval_requested",
            summary=f"Requested approval for '{action_type}': {summary}",
            after_state={"action_type": action_type, "status": "pending"},
        )
        return cls.get_approval(conn, app_id)

    @classmethod
    def decide_approval(
        cls,
        conn: sqlite3.Connection,
        *,
        approval_id: str,
        approver_user_id: str,
        decision: str,
        rationale: str,
    ) -> dict[str, Any]:
        app_row = cls.get_approval(conn, approval_id)
        if not app_row:
            raise ApprovalPolicyError(f"Approval '{approval_id}' not found.")

        if approver_user_id == app_row["requester_id"]:
            raise ApprovalPolicyError("Separation of Duties Violation: Requester cannot self-approve their own request.")

        user_row = conn.execute("SELECT * FROM users WHERE id = ?", (approver_user_id,)).fetchone()
        if not user_row or not user_row["is_active"]:
            raise ApprovalPolicyError("Approver user account is inactive or unrecognized.")

        role = user_row["role"]
        action_type = app_row["action_type"]

        if action_type in ("backup_exception", "manager_exception"):
            if "approve_manager_exceptions" not in ROLE_PERMISSIONS.get(role, set()):
                raise ApprovalPolicyError(f"Role '{role}' is not authorized to approve manager exceptions or backup overrides.")
        elif action_type in ("wp_core_upgrade", "plugin_theme_deletion", "divi_code_migration"):
            if "approve_developer_changes" not in ROLE_PERMISSIONS.get(role, set()):
                raise ApprovalPolicyError(f"Role '{role}' is not authorized to approve developer-level architectural changes.")

        now = utc_now_iso()
        conn.execute(
            """
            UPDATE approvals
            SET status = ?, approver_id = ?, decision_rationale = ?, decided_at = ?
            WHERE id = ?
            """,
            (decision, approver_user_id, rationale, now, approval_id),
        )
        AuditService.log_event(
            conn,
            actor_user_id=approver_user_id,
            entity_type="approval",
            entity_id=approval_id,
            action="approval_decided",
            summary=f"Approval '{app_row['summary']}' -> {decision}",
            before_state={"status": app_row["status"]},
            after_state={"status": decision, "rationale": rationale},
        )
        return cls.get_approval(conn, approval_id)

    @classmethod
    def get_approval(cls, conn: sqlite3.Connection, approval_id: str) -> dict[str, Any]:
        row = conn.execute("SELECT * FROM approvals WHERE id = ?", (approval_id,)).fetchone()
        return dict(row) if row else {}


class BackupService:
    @classmethod
    def record_backup(
        cls,
        conn: sqlite3.Connection,
        *,
        website_id: str,
        storage_location: str,
        created_by: str,
        session_id: str | None = None,
        backup_type: str = "full_files_and_db",
        size_mb: float = 250.0,
        is_verified: bool = False,
        restore_test_status: str = "not_tested",
        notes: str = "",
    ) -> dict[str, Any]:
        bid = new_uuid()
        now = utc_now_iso()
        verified_int = 1 if is_verified else 0
        verified_by = created_by if is_verified else None
        verified_at = now if is_verified else None

        conn.execute(
            """
            INSERT INTO backup_records (
                id, website_id, session_id, backup_type, storage_location, size_mb,
                status, is_verified, verified_by, verified_at, restore_test_status,
                notes, created_by, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'completed', ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                bid,
                website_id,
                session_id,
                backup_type,
                storage_location,
                size_mb,
                verified_int,
                verified_by,
                verified_at,
                restore_test_status,
                notes,
                created_by,
                now,
            ),
        )
        AuditService.log_event(
            conn,
            actor_user_id=created_by,
            entity_type="backup_record",
            entity_id=bid,
            action="backup_recorded",
            summary=f"Recorded backup at {storage_location} (verified={is_verified})",
            after_state={"storage_location": storage_location, "is_verified": is_verified},
        )
        return cls.get_backup(conn, bid)

    @classmethod
    def verify_backup(
        cls,
        conn: sqlite3.Connection,
        *,
        backup_id: str,
        verifier_user_id: str,
        restore_test_status: str = "verified_archive_integrity",
    ) -> dict[str, Any]:
        now = utc_now_iso()
        conn.execute(
            """
            UPDATE backup_records
            SET is_verified = 1, verified_by = ?, verified_at = ?, restore_test_status = ?, status = 'completed'
            WHERE id = ?
            """,
            (verifier_user_id, now, restore_test_status, backup_id),
        )
        AuditService.log_event(
            conn,
            actor_user_id=verifier_user_id,
            entity_type="backup_record",
            entity_id=backup_id,
            action="backup_verified",
            summary=f"Backup archive integrity verified ({backup_id})",
            after_state={"is_verified": 1, "restore_test_status": restore_test_status},
        )
        return cls.get_backup(conn, backup_id)

    @classmethod
    def get_backup(cls, conn: sqlite3.Connection, backup_id: str) -> dict[str, Any]:
        row = conn.execute("SELECT * FROM backup_records WHERE id = ?", (backup_id,)).fetchone()
        return dict(row) if row else {}
