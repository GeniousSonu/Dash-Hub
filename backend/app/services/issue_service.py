import sqlite3
from typing import Any

from backend.app.core.database import new_uuid, utc_now_iso
from backend.app.models.enums import IssueStatus
from backend.app.services.audit_service import AuditService


class IssueVerificationError(ValueError):
    """Raised when an issue transition violates verification requirements (INV-01)."""


class IssueService:
    @classmethod
    def create_issue(
        cls,
        conn: sqlite3.Connection,
        *,
        project_id: str,
        category: str,
        severity: str,
        priority: str,
        title: str,
        description: str,
        actor_user_id: str,
        owner_id: str | None = None,
        reviewer_id: str | None = None,
        website_id: str | None = None,
        session_id: str | None = None,
        checklist_item_id: str | None = None,
        due_at: str | None = None,
    ) -> dict[str, Any]:
        issue_id = new_uuid()
        now = utc_now_iso()
        conn.execute(
            """
            INSERT INTO issues (
                id, project_id, website_id, session_id, checklist_item_id, category,
                severity, priority, title, description, owner_id, reviewer_id,
                status, due_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new', ?, ?, ?)
            """,
            (
                issue_id,
                project_id,
                website_id,
                session_id,
                checklist_item_id,
                category,
                severity,
                priority,
                title,
                description,
                owner_id,
                reviewer_id,
                due_at,
                now,
                now,
            ),
        )
        AuditService.log_event(
            conn,
            actor_user_id=actor_user_id,
            entity_type="issue",
            entity_id=issue_id,
            action="issue_created",
            summary=f"Created issue '{title}' ({severity})",
            after_state={"title": title, "severity": severity, "status": "new"},
        )
        return cls.get_issue(conn, issue_id)

    @classmethod
    def record_remediation(
        cls,
        conn: sqlite3.Connection,
        *,
        issue_id: str,
        actor_user_id: str,
        remediation_notes: str,
        request_verification: bool = True,
    ) -> dict[str, Any]:
        issue = cls.get_issue(conn, issue_id)
        if not issue:
            raise IssueVerificationError(f"Issue '{issue_id}' not found.")

        now = utc_now_iso()
        target_status = IssueStatus.VERIFICATION.value if request_verification else IssueStatus.FIXED_MITIGATED.value
        conn.execute(
            """
            UPDATE issues
            SET status = ?, remediation_notes = ?, updated_at = ?
            WHERE id = ?
            """,
            (target_status, remediation_notes, now, issue_id),
        )
        AuditService.log_event(
            conn,
            actor_user_id=actor_user_id,
            entity_type="issue",
            entity_id=issue_id,
            action="remediation_recorded",
            summary=f"Recorded remediation for issue '{issue['title']}' -> {target_status}",
            before_state={"status": issue["status"]},
            after_state={"status": target_status, "remediation_notes": remediation_notes},
        )
        return cls.get_issue(conn, issue_id)

    @classmethod
    def verify_issue(
        cls,
        conn: sqlite3.Connection,
        *,
        issue_id: str,
        verifier_user_id: str,
        passed: bool,
        verification_notes: str,
        close_on_pass: bool = True,
    ) -> dict[str, Any]:
        issue = cls.get_issue(conn, issue_id)
        if not issue:
            raise IssueVerificationError(f"Issue '{issue_id}' not found.")

        now = utc_now_iso()
        if passed:
            outcome = "passed"
            new_status = IssueStatus.CLOSED.value if close_on_pass else IssueStatus.RESOLVED.value
        else:
            outcome = "failed"
            new_status = IssueStatus.REOPENED.value

        conn.execute(
            """
            UPDATE issues
            SET status = ?, verification_outcome = ?, verified_by = ?, verified_at = ?,
                remediation_notes = remediation_notes || char(10) || 'QA Verification: ' || ?,
                updated_at = ?
            WHERE id = ?
            """,
            (new_status, outcome, verifier_user_id, now, verification_notes, now, issue_id),
        )
        AuditService.log_event(
            conn,
            actor_user_id=verifier_user_id,
            entity_type="issue",
            entity_id=issue_id,
            action="verification_recorded",
            summary=f"QA Verification on '{issue['title']}': outcome={outcome} -> new_status={new_status}",
            before_state={"status": issue["status"]},
            after_state={"status": new_status, "verification_outcome": outcome},
        )
        return cls.get_issue(conn, issue_id)

    @classmethod
    def close_issue_directly(
        cls,
        conn: sqlite3.Connection,
        *,
        issue_id: str,
        actor_user_id: str,
        target_status: str,
        closure_reason: str,
    ) -> dict[str, Any]:
        issue = cls.get_issue(conn, issue_id)
        if not issue:
            raise IssueVerificationError(f"Issue '{issue_id}' not found.")

        if target_status == IssueStatus.CLOSED.value:
            if issue.get("verification_outcome") != "passed":
                raise IssueVerificationError(
                    "INV-01: Direct closure blocked without passed QA verification. "
                    "Issue must go through QA verification or be marked accepted_risk."
                )

        now = utc_now_iso()
        conn.execute(
            """
            UPDATE issues
            SET status = ?, closure_reason = ?, updated_at = ?
            WHERE id = ?
            """,
            (target_status, closure_reason, now, issue_id),
        )
        AuditService.log_event(
            conn,
            actor_user_id=actor_user_id,
            entity_type="issue",
            entity_id=issue_id,
            action="issue_closed",
            summary=f"Issue '{issue['title']}' transitioned to '{target_status}'",
            before_state={"status": issue["status"]},
            after_state={"status": target_status, "closure_reason": closure_reason},
        )
        return cls.get_issue(conn, issue_id)

    @classmethod
    def get_issue(cls, conn: sqlite3.Connection, issue_id: str) -> dict[str, Any]:
        row = conn.execute("SELECT * FROM issues WHERE id = ?", (issue_id,)).fetchone()
        return dict(row) if row else {}
