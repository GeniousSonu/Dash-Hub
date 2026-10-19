import json
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any

from backend.app.core.database import new_uuid, utc_now_iso
from backend.app.models.enums import (
    ApprovalStatus,
    BuilderType,
    ChecklistItemStatus,
    DueAnchorPolicy,
    IssueStatus,
    SessionStatus,
    WebsiteEnvironment,
    WorkflowStatus,
)
from backend.app.services.audit_service import AuditService
from backend.app.services.sop_seed import CANONICAL_RULE_REFERENCES, WORDPRESS_SOP_23_STEPS


class SOPGateViolationError(ValueError):
    """Raised when a maintenance checklist transition or session closure violates SOP gating rules."""


class SOPGateService:
    """Manages versioned SOP templates, conditional step generation, pre-update backup gates, and session closure."""

    TEMPLATE_CODE = "WP_MAINT_SOP"

    @classmethod
    def ensure_default_template(cls, conn: sqlite3.Connection, created_by: str | None = None) -> dict[str, Any]:
        row = conn.execute(
            "SELECT * FROM workflow_templates WHERE code = ? AND is_active = 1 ORDER BY version DESC LIMIT 1",
            (cls.TEMPLATE_CODE,),
        ).fetchone()
        if row:
            return dict(row)

        template_id = new_uuid()
        now = utc_now_iso()
        conn.execute(
            """
            INSERT INTO workflow_templates (
                id, code, name, version, is_active, tasks_schema_json, rules_reference_json, created_by, created_at
            ) VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?)
            """,
            (
                template_id,
                cls.TEMPLATE_CODE,
                "WordPress Site Maintenance SOP (23-Step Guided Checklist)",
                1,
                json.dumps(WORDPRESS_SOP_23_STEPS),
                json.dumps(CANONICAL_RULE_REFERENCES),
                created_by,
                now,
            ),
        )
        AuditService.log_event(
            conn,
            actor_user_id=created_by,
            entity_type="workflow_template",
            entity_id=template_id,
            action="template_seeded",
            summary="Seeded WordPress Site Maintenance SOP v1 (23 steps + 8 rule references)",
            after_state={"code": cls.TEMPLATE_CODE, "version": 1},
        )
        return dict(conn.execute("SELECT * FROM workflow_templates WHERE id = ?", (template_id,)).fetchone())

    @classmethod
    def publish_new_template_version(
        cls,
        conn: sqlite3.Connection,
        *,
        actor_user_id: str,
        name: str | None = None,
        tasks_schema: list[dict[str, Any]] | None = None,
        rules_reference: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        current = cls.ensure_default_template(conn, created_by=actor_user_id)
        next_version = int(current["version"]) + 1
        new_id = new_uuid()
        now = utc_now_iso()

        new_tasks = tasks_schema if tasks_schema is not None else json.loads(current["tasks_schema_json"])
        new_rules = rules_reference if rules_reference is not None else json.loads(current["rules_reference_json"])
        new_name = name or current["name"]

        conn.execute("UPDATE workflow_templates SET is_active = 0 WHERE code = ?", (cls.TEMPLATE_CODE,))
        conn.execute(
            """
            INSERT INTO workflow_templates (
                id, code, name, version, is_active, tasks_schema_json, rules_reference_json, created_by, created_at
            ) VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?)
            """,
            (
                new_id,
                cls.TEMPLATE_CODE,
                new_name,
                next_version,
                json.dumps(new_tasks),
                json.dumps(new_rules),
                actor_user_id,
                now,
            ),
        )
        AuditService.log_event(
            conn,
            actor_user_id=actor_user_id,
            entity_type="workflow_template",
            entity_id=new_id,
            action="template_version_published",
            summary=f"Published {cls.TEMPLATE_CODE} version {next_version}",
            before_state={"version": current["version"]},
            after_state={"version": next_version},
        )
        return dict(conn.execute("SELECT * FROM workflow_templates WHERE id = ?", (new_id,)).fetchone())

    @classmethod
    def start_session(
        cls,
        conn: sqlite3.Connection,
        *,
        website_id: str,
        maintainer_id: str,
        reviewer_id: str | None = None,
        planned_due_at: str | None = None,
    ) -> dict[str, Any]:
        website = conn.execute("SELECT * FROM websites WHERE id = ?", (website_id,)).fetchone()
        if not website:
            raise ValueError(f"Website '{website_id}' not found.")

        template = cls.ensure_default_template(conn, created_by=maintainer_id)
        session_id = new_uuid()
        now = utc_now_iso()
        env = website["environment"]
        builder = website["builder"]

        snapshot_payload = {
            "template_id": template["id"],
            "code": template["code"],
            "version": template["version"],
            "tasks": json.loads(template["tasks_schema_json"]),
            "rules_reference": json.loads(template["rules_reference_json"]),
        }

        conn.execute(
            """
            INSERT INTO maintenance_sessions (
                id, website_id, template_id, template_version, template_snapshot_json,
                maintainer_id, reviewer_id, status, environment_snapshot, builder_snapshot,
                planned_due_at, started_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                website_id,
                template["id"],
                template["version"],
                json.dumps(snapshot_payload),
                maintainer_id,
                reviewer_id or website["reviewer_id"],
                SessionStatus.IN_PROGRESS.value,
                env,
                builder,
                planned_due_at or website["next_due_at"],
                now,
            ),
        )

        for step in snapshot_payload["tasks"]:
            step_num = int(step["step_number"])
            cond_type = step.get("condition_type", "always")
            is_conditional = 1 if step.get("is_conditional") else 0
            is_applicable = 1
            initial_status = ChecklistItemStatus.PENDING.value
            na_reason = ""

            if cond_type == "staging_only" and env != WebsiteEnvironment.STAGING.value:
                is_applicable = 0
                initial_status = ChecklistItemStatus.NOT_APPLICABLE.value
                na_reason = f"Rule applies to staging environments only (site environment is '{env}')."
            elif cond_type == "divi_only" and builder != BuilderType.DIVI.value:
                is_applicable = 0
                initial_status = ChecklistItemStatus.NOT_APPLICABLE.value
                na_reason = f"Rule applies to Divi Builder sites only (site builder is '{builder}')."

            conn.execute(
                """
                INSERT INTO session_checklist_items (
                    id, session_id, step_number, code, title, required_process,
                    automation_mode, is_conditional, is_applicable, status,
                    owner_id, na_reason, rule_ref_key, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_uuid(),
                    session_id,
                    step_num,
                    step["code"],
                    step["title"],
                    step["required_process"],
                    step["automation_mode"],
                    is_conditional,
                    is_applicable,
                    initial_status,
                    maintainer_id,
                    na_reason,
                    step.get("rule_ref_key", ""),
                    now,
                ),
            )

        conn.execute(
            "UPDATE websites SET workflow_status = ?, updated_at = ? WHERE id = ?",
            (WorkflowStatus.IN_PROGRESS.value, now, website_id),
        )

        AuditService.log_event(
            conn,
            actor_user_id=maintainer_id,
            entity_type="maintenance_session",
            entity_id=session_id,
            action="session_started",
            summary=f"Started maintenance session for {website['name']} ({env}) using template v{template['version']}",
            after_state={"session_id": session_id, "template_version": template["version"], "environment": env},
        )
        return cls.get_session_detail(conn, session_id)

    @classmethod
    def check_live_backup_gate(cls, conn: sqlite3.Connection, session_id: str) -> tuple[bool, str]:
        session = conn.execute("SELECT * FROM maintenance_sessions WHERE id = ?", (session_id,)).fetchone()
        if not session:
            return False, "Maintenance session not found."

        if session["environment_snapshot"] != WebsiteEnvironment.LIVE.value:
            return True, f"Environment '{session['environment_snapshot']}' does not enforce live pre-update backup lock."

        verified_backup = conn.execute(
            """
            SELECT id, storage_location, verified_at FROM backup_records
            WHERE session_id = ? AND is_verified = 1 AND status = 'completed'
            LIMIT 1
            """,
            (session_id,),
        ).fetchone()
        if verified_backup:
            return True, f"Verified backup on record ({verified_backup['storage_location']})."

        approved_exception = conn.execute(
            """
            SELECT id, approver_id, decided_at FROM approvals
            WHERE session_id = ? AND action_type = 'backup_exception' AND status IN ('approved', 'executed', 'verified')
            LIMIT 1
            """,
            (session_id,),
        ).fetchone()
        if approved_exception:
            return True, f"Authorized backup exception approved ({approved_exception['id']})."

        return (
            False,
            "LIVE SITE PRE-UPDATE GATE: A verified backup record (Step 9) or an approved 'backup_exception' "
            "is required before executing Core (#10), Theme (#11), or Plugin (#12) updates.",
        )

    @classmethod
    def update_checklist_item(
        cls,
        conn: sqlite3.Connection,
        *,
        session_id: str,
        step_number: int,
        actor_user_id: str,
        status: str,
        observation: str | None = None,
        action_taken: str | None = None,
        na_reason: str | None = None,
        blocked_reason: str | None = None,
        is_applicable_override: bool | None = None,
        linked_issue_id: str | None = None,
        linked_approval_id: str | None = None,
    ) -> dict[str, Any]:
        item = conn.execute(
            "SELECT * FROM session_checklist_items WHERE session_id = ? AND step_number = ?",
            (session_id, step_number),
        ).fetchone()
        if not item:
            raise ValueError(f"Step {step_number} not found in session {session_id}.")

        before_state = dict(item)
        session = conn.execute("SELECT * FROM maintenance_sessions WHERE id = ?", (session_id,)).fetchone()

        if status == ChecklistItemStatus.NOT_APPLICABLE.value:
            effective_na_reason = (na_reason if na_reason is not None else item["na_reason"]).strip()
            if not effective_na_reason:
                raise SOPGateViolationError(
                    f"Step {step_number} ({item['title']}) cannot be marked Not Applicable without recording a valid reason."
                )
            if step_number in (9, 22, 23) and session["environment_snapshot"] == WebsiteEnvironment.LIVE.value:
                raise SOPGateViolationError(
                    f"Step {step_number} ({item['title']}) is a mandatory completion gate on live sites and cannot be marked Not Applicable."
                )

        if step_number in (10, 11, 12) and status in (
            ChecklistItemStatus.IN_PROGRESS.value,
            ChecklistItemStatus.PASSED.value,
        ):
            gate_ok, gate_msg = cls.check_live_backup_gate(conn, session_id)
            if not gate_ok:
                raise SOPGateViolationError(gate_msg)

        if step_number == 10 and status == ChecklistItemStatus.PASSED.value:
            act_text = (action_taken if action_taken is not None else item["action_taken"]).lower()
            if "upgraded" in act_text or "updated core" in act_text:
                app_id = linked_approval_id or item["linked_approval_id"]
                if not app_id:
                    raise SOPGateViolationError(
                        "SOP GATE (Step 10): Upgrading WordPress core requires a linked Developer Approval record."
                    )
                app_row = conn.execute("SELECT status FROM approvals WHERE id = ?", (app_id,)).fetchone()
                if not app_row or app_row["status"] not in (
                    ApprovalStatus.APPROVED.value,
                    ApprovalStatus.EXECUTED.value,
                    ApprovalStatus.VERIFIED.value,
                ):
                    raise SOPGateViolationError(
                        "SOP GATE (Step 10): Linked WordPress core upgrade approval has not been approved yet."
                    )

        if step_number == 16 and status == ChecklistItemStatus.PASSED.value:
            act_text = (action_taken if action_taken is not None else item["action_taken"]).lower()
            if "deleted" in act_text or "removed" in act_text:
                app_id = linked_approval_id or item["linked_approval_id"]
                if not app_id:
                    raise SOPGateViolationError(
                        "SOP GATE (Step 16): Deleting plugins or themes from the cleanup list requires developer confirmation & a linked Approval record."
                    )
                app_row = conn.execute("SELECT status FROM approvals WHERE id = ?", (app_id,)).fetchone()
                if not app_row or app_row["status"] not in (
                    ApprovalStatus.APPROVED.value,
                    ApprovalStatus.EXECUTED.value,
                    ApprovalStatus.VERIFIED.value,
                ):
                    raise SOPGateViolationError(
                        "SOP GATE (Step 16): Linked plugin/theme deletion approval has not been approved yet."
                    )

        now = utc_now_iso()
        new_is_applicable = (
            (1 if is_applicable_override else 0)
            if is_applicable_override is not None
            else item["is_applicable"]
        )
        if status != ChecklistItemStatus.NOT_APPLICABLE.value and is_applicable_override is None:
            new_is_applicable = 1

        conn.execute(
            """
            UPDATE session_checklist_items
            SET status = ?,
                is_applicable = ?,
                observation = ?,
                action_taken = ?,
                na_reason = ?,
                blocked_reason = ?,
                linked_issue_id = ?,
                linked_approval_id = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                status,
                new_is_applicable,
                observation if observation is not None else item["observation"],
                action_taken if action_taken is not None else item["action_taken"],
                na_reason if na_reason is not None else item["na_reason"],
                blocked_reason if blocked_reason is not None else item["blocked_reason"],
                linked_issue_id if linked_issue_id is not None else item["linked_issue_id"],
                linked_approval_id if linked_approval_id is not None else item["linked_approval_id"],
                now,
                item["id"],
            ),
        )

        if step_number == 9 and status == ChecklistItemStatus.PASSED.value:
            gate_ok, _ = cls.check_live_backup_gate(conn, session_id)
            if not gate_ok:
                raise SOPGateViolationError(
                    "Step 9 (Backup) cannot be marked Passed on a live site until a verified Backup Record or approved exception is saved."
                )

        updated = dict(
            conn.execute("SELECT * FROM session_checklist_items WHERE id = ?", (item["id"],)).fetchone()
        )
        AuditService.log_event(
            conn,
            actor_user_id=actor_user_id,
            entity_type="session_checklist_item",
            entity_id=item["id"],
            action="step_updated",
            summary=f"Step {step_number} ({item['title']}) -> {status}",
            before_state={"status": before_state["status"], "observation": before_state["observation"]},
            after_state={"status": updated["status"], "observation": updated["observation"]},
        )
        return updated

    @classmethod
    def close_session(
        cls,
        conn: sqlite3.Connection,
        *,
        session_id: str,
        actor_user_id: str,
        target_status: str,
        closure_summary: str = "",
    ) -> dict[str, Any]:
        session = conn.execute("SELECT * FROM maintenance_sessions WHERE id = ?", (session_id,)).fetchone()
        if not session:
            raise ValueError(f"Maintenance session '{session_id}' not found.")

        items = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM session_checklist_items WHERE session_id = ? ORDER BY step_number ASC",
                (session_id,),
            ).fetchall()
        ]
        by_step = {i["step_number"]: i for i in items}

        if target_status in (SessionStatus.COMPLETED.value, SessionStatus.COMPLETED_WITH_FINDINGS.value):
            unfinished = [
                f"Step {i['step_number']} ({i['title']})"
                for i in items
                if i["status"] in (ChecklistItemStatus.PENDING.value, ChecklistItemStatus.IN_PROGRESS.value)
            ]
            if unfinished:
                raise SOPGateViolationError(
                    f"Cannot close session as '{target_status}': {len(unfinished)} step(s) are still pending/in-progress: {', '.join(unfinished[:5])}"
                )

            blocked = [f"Step {i['step_number']} ({i['title']})" for i in items if i["status"] == ChecklistItemStatus.BLOCKED.value]
            if blocked:
                raise SOPGateViolationError(
                    f"Cannot close session as '{target_status}' while steps remain Blocked: {', '.join(blocked)}"
                )

            gate_ok, gate_msg = cls.check_live_backup_gate(conn, session_id)
            if not gate_ok:
                raise SOPGateViolationError(gate_msg)

            step13 = by_step.get(13)
            if step13 and step13["status"] == ChecklistItemStatus.FAILED.value:
                issue_id = step13.get("linked_issue_id")
                if not issue_id:
                    raise SOPGateViolationError(
                        "CLOSURE GATE (Step 13): Critical post-update re-check failed without a linked high-priority Issue."
                    )
                issue = conn.execute("SELECT status, severity FROM issues WHERE id = ?", (issue_id,)).fetchone()
                exception_app = conn.execute(
                    """
                    SELECT id FROM approvals
                    WHERE session_id = ? AND action_type = 'post_update_exception' AND status IN ('approved', 'executed', 'verified')
                    """,
                    (session_id,),
                ).fetchone()
                if (not issue or issue["status"] not in (IssueStatus.RESOLVED.value, IssueStatus.CLOSED.value)) and not exception_app:
                    raise SOPGateViolationError(
                        "CLOSURE GATE (Step 13): Post-update re-check failure blocks normal session closure until the linked issue is resolved or a 'post_update_exception' approval is granted."
                    )

            for mandatory_step in (22, 23):
                st = by_step[mandatory_step]
                if st["status"] != ChecklistItemStatus.PASSED.value:
                    raise SOPGateViolationError(
                        f"CLOSURE GATE: Step {mandatory_step} ({st['title']}) must be marked PASSED before closing a session."
                    )

            has_findings = any(
                i["status"] in (ChecklistItemStatus.FAILED.value, ChecklistItemStatus.NOT_VERIFIED.value)
                for i in items
            )
            session_issues = conn.execute(
                "SELECT COUNT(*) AS cnt FROM issues WHERE session_id = ? AND status NOT IN ('resolved', 'closed', 'rejected', 'duplicate')",
                (session_id,),
            ).fetchone()["cnt"]
            if (has_findings or session_issues > 0) and target_status == SessionStatus.COMPLETED.value:
                target_status = SessionStatus.COMPLETED_WITH_FINDINGS.value

        now = utc_now_iso()
        conn.execute(
            """
            UPDATE maintenance_sessions
            SET status = ?, closed_at = ?, closure_summary = ?
            WHERE id = ?
            """,
            (target_status, now, closure_summary, session_id),
        )

        website = conn.execute("SELECT * FROM websites WHERE id = ?", (session["website_id"],)).fetchone()
        if target_status in (SessionStatus.COMPLETED.value, SessionStatus.COMPLETED_WITH_FINDINGS.value):
            next_due = cls.calculate_next_due_date(
                frequency=website["frequency"],
                anchor_policy=website["due_anchor_policy"],
                planned_due_iso=session["planned_due_at"] or website["next_due_at"],
                completed_iso=now,
            )
            conn.execute(
                """
                UPDATE websites
                SET workflow_status = ?, last_completed_at = ?, next_due_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (WorkflowStatus.UP_TO_DATE.value, now, next_due, now, website["id"]),
            )
            conn.execute(
                """
                UPDATE maintenance_schedules
                SET last_completed_at = ?, next_due_at = ?, planned_due_at = ?, updated_at = ?
                WHERE website_id = ?
                """,
                (now, next_due, next_due, now, website["id"]),
            )
        elif target_status == SessionStatus.BLOCKED.value:
            conn.execute(
                "UPDATE websites SET workflow_status = ?, updated_at = ? WHERE id = ?",
                (WorkflowStatus.BLOCKED.value, now, website["id"]),
            )

        AuditService.log_event(
            conn,
            actor_user_id=actor_user_id,
            entity_type="maintenance_session",
            entity_id=session_id,
            action="session_closed",
            summary=f"Closed maintenance session as '{target_status}'",
            before_state={"status": session["status"]},
            after_state={"status": target_status, "closed_at": now},
        )
        return cls.get_session_detail(conn, session_id)

    @staticmethod
    def calculate_next_due_date(
        *,
        frequency: str,
        anchor_policy: str,
        planned_due_iso: str | None,
        completed_iso: str,
        custom_days: int = 30,
    ) -> str:
        days_map = {
            "weekly": 7,
            "monthly": 30,
            "quarterly": 90,
            "custom": custom_days,
            "manual": 30,
        }
        delta = timedelta(days=days_map.get(frequency, 30))
        completed_dt = datetime.fromisoformat(completed_iso)
        if anchor_policy == DueAnchorPolicy.PLANNED_DATE.value and planned_due_iso:
            try:
                base_dt = datetime.fromisoformat(planned_due_iso)
                if base_dt.tzinfo is None:
                    base_dt = base_dt.replace(tzinfo=timezone.utc)
                next_dt = base_dt + delta
                while next_dt <= completed_dt:
                    next_dt += delta
                return next_dt.replace(microsecond=0).isoformat()
            except ValueError:
                pass
        return (completed_dt + delta).replace(microsecond=0).isoformat()

    @classmethod
    def get_session_detail(cls, conn: sqlite3.Connection, session_id: str) -> dict[str, Any]:
        session = conn.execute(
            """
            SELECT s.*, w.name AS website_name, w.domain AS website_domain,
                   u.full_name AS maintainer_name
            FROM maintenance_sessions s
            JOIN websites w ON s.website_id = w.id
            JOIN users u ON s.maintainer_id = u.id
            WHERE s.id = ?
            """,
            (session_id,),
        ).fetchone()
        if not session:
            raise ValueError(f"Session '{session_id}' not found.")

        result = dict(session)
        items = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM session_checklist_items WHERE session_id = ? ORDER BY step_number ASC",
                (session_id,),
            ).fetchall()
        ]
        snapshot = json.loads(result.pop("template_snapshot_json", "{}") or "{}")
        rules_ref = snapshot.get("rules_reference", CANONICAL_RULE_REFERENCES)
        for item in items:
            ref_key = item.get("rule_ref_key", "")
            item["rule_reference"] = rules_ref.get(ref_key) if ref_key else None

        gate_ok, gate_msg = cls.check_live_backup_gate(conn, session_id)
        result["backup_gate"] = {"is_satisfied": gate_ok, "message": gate_msg}
        result["items"] = items
        result["counts"] = {
            "total": len(items),
            "passed": sum(1 for i in items if i["status"] == ChecklistItemStatus.PASSED.value),
            "failed": sum(1 for i in items if i["status"] == ChecklistItemStatus.FAILED.value),
            "blocked": sum(1 for i in items if i["status"] == ChecklistItemStatus.BLOCKED.value),
            "not_applicable": sum(1 for i in items if i["status"] == ChecklistItemStatus.NOT_APPLICABLE.value),
            "not_verified": sum(1 for i in items if i["status"] == ChecklistItemStatus.NOT_VERIFIED.value),
            "pending": sum(
                1
                for i in items
                if i["status"] in (ChecklistItemStatus.PENDING.value, ChecklistItemStatus.IN_PROGRESS.value)
            ),
        }
        return result