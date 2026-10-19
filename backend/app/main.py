from contextlib import asynccontextmanager
import json
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from pydantic import BaseModel, Field

from backend.app.core.config import settings
from backend.app.core.database import db_manager
from backend.app.core.security import check_permission
from backend.app.services.approval_service import ApprovalPolicyError, ApprovalService, BackupService
from backend.app.services.audit_service import AuditService
from backend.app.services.dashboard_service import DashboardService
from backend.app.services.import_service import InventoryImportService
from backend.app.services.issue_service import IssueService, IssueVerificationError
from backend.app.services.seed_demo import BootstrapSeedService
from backend.app.services.sop_gate_service import SOPGateService, SOPGateViolationError
from backend.app.services.task_service import TaskService, TaskValidationError
from workers.checks.http_tls_check import SafeReadOnlyCheckRunner
from workers.reports.pdf_exporter import ReportAndExportService
from workers.scheduler import MaintenanceSchedulerWorker


class StartSessionPayload(BaseModel):
    website_id: str
    maintainer_id: str
    reviewer_id: str | None = None


class UpdateStepPayload(BaseModel):
    status: str
    observation: str | None = None
    action_taken: str | None = None
    na_reason: str | None = None
    blocked_reason: str | None = None
    is_applicable_override: bool | None = None
    linked_issue_id: str | None = None
    linked_approval_id: str | None = None


class CloseSessionPayload(BaseModel):
    target_status: str = "completed"
    closure_summary: str = ""


class CreateBackupPayload(BaseModel):
    website_id: str
    session_id: str | None = None
    storage_location: str
    backup_type: str = "full_files_and_db"
    size_mb: float = 250.0
    is_verified: bool = False
    restore_test_status: str = "not_tested"
    notes: str = ""


class VerifyBackupPayload(BaseModel):
    restore_test_status: str = "verified_archive_integrity"


class RequestApprovalPayload(BaseModel):
    project_id: str
    website_id: str | None = None
    session_id: str | None = None
    checklist_item_id: str | None = None
    action_type: str
    summary: str
    risk_notes: str = ""
    approver_id: str | None = None


class DecideApprovalPayload(BaseModel):
    decision: str
    rationale: str


class CreateIssuePayload(BaseModel):
    project_id: str
    website_id: str | None = None
    session_id: str | None = None
    checklist_item_id: str | None = None
    category: str
    severity: str
    priority: str
    title: str
    description: str
    owner_id: str | None = None
    reviewer_id: str | None = None
    due_at: str | None = None


class RemediateIssuePayload(BaseModel):
    remediation_notes: str
    request_verification: bool = True


class VerifyIssuePayload(BaseModel):
    passed: bool
    verification_notes: str
    close_on_pass: bool = True


class DirectCloseIssuePayload(BaseModel):
    target_status: str
    closure_reason: str


class CreateTaskPayload(BaseModel):
    project_id: str
    title: str
    owner_id: str
    description: str = ""
    website_id: str | None = None
    session_id: str | None = None
    issue_id: str | None = None
    priority: str = "normal"
    status: str = "ready"
    due_at: str | None = None
    estimated_hours: float = 0.0
    acceptance_criteria: str = ""
    depends_on: list[str] = Field(default_factory=list)


class UpdateTaskStatusPayload(BaseModel):
    new_status: str
    cancellation_reason: str = ""
    new_owner_id: str | None = None


class WorkLogPayload(BaseModel):
    what_was_done: str
    what_remains: str = ""
    blockers: str = ""
    next_action: str = ""
    hours_logged: float = 0.0


class ImportWebsitesPayload(BaseModel):
    rows: list[dict[str, Any]]
    default_project_id: str
    default_maintainer_id: str
    dry_run: bool = False


ARGON_TOKENS: dict[str, Any] = {
    "brand": {
        "primary": "#5E72E4",
        "primary_hover": "#324CDD",
        "accent": "#11CDEF",
        "success": "#2DCE89",
        "warning": "#FB6340",
        "danger": "#F5365C",
        "info": "#11CDEF",
    },
    "typography": {
        "font_ui": '"Inter", "Segoe UI", "Ubuntu", sans-serif',
        "font_mono": '"JetBrains Mono", "Fira Code", "Ubuntu Mono", monospace',
    },
    "spacing_grid_px": [4, 8, 12, 16, 24, 32],
    "radii_px": {"sm": 6, "md": 8, "lg": 12},
    "light": {
        "bg_canvas": "#F7FAFC",
        "bg_surface": "#FFFFFF",
        "bg_sidebar": "#172B4D",
        "text_primary": "#172B4D",
        "text_secondary": "#525F7F",
        "border": "#E9ECEF",
        "table_header": "#F6F9FC",
    },
    "dark": {
        "bg_canvas": "#0B1528",
        "bg_surface": "#172B4D",
        "bg_sidebar": "#070D19",
        "text_primary": "#F7FAFC",
        "text_secondary": "#8898AA",
        "border": "#2B3553",
        "table_header": "#111C33",
    },
}

FEATURE_FLAGS: dict[str, bool] = {
    "enforce_live_backup_gate": True,
    "enable_2fa_totp_verification": False,
    "allow_developer_self_service_overrides": False,
    "send_slack_webhook_alerts": False,
    "enable_experimental_dark_mode": True,
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    db_manager.init_schema()
    with db_manager.session() as conn:
        BootstrapSeedService.ensure_baseline_seed(conn)
    yield


def create_app() -> FastAPI:
    db_manager.init_schema()
    app = FastAPI(title=settings.app_name, version=settings.version, lifespan=lifespan)

    def get_current_user(x_user_id: str | None = Header(default=None)) -> dict[str, Any]:
        with db_manager.session() as conn:
            if x_user_id:
                row = conn.execute("SELECT * FROM users WHERE id = ?", (x_user_id,)).fetchone()
                if row:
                    return dict(row)
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user header.")
            row = conn.execute("SELECT * FROM users WHERE role = 'system_admin' LIMIT 1").fetchone()
            if not row:
                seed = BootstrapSeedService.ensure_baseline_seed(conn)
                return seed["users_by_role"]["system_admin"]
            return dict(row)

    @app.get("/api/v1/health")
    def health_check() -> dict[str, Any]:
        return {"status": "ok", "app": settings.app_name, "version": settings.version}

    @app.post("/api/v1/auth/login")
    def api_auth_login(payload: dict[str, Any]) -> dict[str, Any]:
        email = (payload.get("email") or "admin@opshub.internal").strip()
        with db_manager.session() as conn:
            u = conn.execute("SELECT * FROM users WHERE email = ? AND is_active = 1", (email,)).fetchone()
            if not u:
                raise HTTPException(status_code=401, detail="Invalid credentials or inactive account.")
            user_dict = dict(u)
            return {
                "access_token": f"opshub_jwt_{user_dict['id']}",
                "refresh_token": f"opshub_refresh_{user_dict['id']}",
                "token_type": "bearer",
                "requires_2fa": FEATURE_FLAGS["enable_2fa_totp_verification"],
                "user": user_dict,
            }

    @app.post("/api/v1/auth/verify-2fa")
    def api_verify_2fa(payload: dict[str, Any]) -> dict[str, Any]:
        code = str(payload.get("totp_code") or "").strip()
        if len(code) != 6 or not code.isdigit():
            raise HTTPException(status_code=400, detail="Invalid 6-digit 2FA TOTP verification code.")
        return {"verified": True, "session_status": "authenticated_2fa_verified"}

    @app.get("/api/v1/feature-flags")
    def api_get_feature_flags() -> dict[str, bool]:
        return FEATURE_FLAGS

    @app.patch("/api/v1/feature-flags")
    def api_update_feature_flags(payload: dict[str, bool], user: dict = Depends(get_current_user)) -> dict[str, bool]:
        check_permission(user, "manage_integrations")
        for k, v in payload.items():
            if k in FEATURE_FLAGS:
                FEATURE_FLAGS[k] = bool(v)
        return FEATURE_FLAGS

    @app.get("/api/v1/design-tokens")
    def api_get_design_tokens() -> dict[str, Any]:
        return ARGON_TOKENS

    @app.get("/api/v1/bootstrap")
    def get_bootstrap_data() -> dict[str, Any]:
        with db_manager.session() as conn:
            return BootstrapSeedService.ensure_baseline_seed(conn)

    @app.get("/api/v1/users")
    def list_users(user: dict = Depends(get_current_user)) -> list[dict[str, Any]]:
        check_permission(user, "view_records")
        with db_manager.session() as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM users ORDER BY full_name").fetchall()]

    @app.get("/api/v1/dashboard/summary")
    def dashboard_summary(user: dict = Depends(get_current_user)) -> dict[str, Any]:
        check_permission(user, "view_records")
        with db_manager.session() as conn:
            return DashboardService.get_summary(conn)

    @app.get("/api/v1/dashboard/drilldown/{metric_key}")
    def dashboard_drilldown(metric_key: str, user: dict = Depends(get_current_user)) -> list[dict[str, Any]]:
        check_permission(user, "view_records")
        with db_manager.session() as conn:
            return DashboardService.get_drilldown(conn, metric_key)

    @app.get("/api/v1/projects")
    def list_projects(user: dict = Depends(get_current_user)) -> list[dict[str, Any]]:
        check_permission(user, "view_records")
        with db_manager.session() as conn:
            return [
                dict(r)
                for r in conn.execute(
                    """
                    SELECT p.*, u.full_name AS lead_name,
                           (SELECT COUNT(*) FROM tasks t WHERE t.project_id = p.id) AS total_tasks,
                           (SELECT COUNT(*) FROM tasks t WHERE t.project_id = p.id AND t.status = 'completed') AS completed_tasks
                    FROM projects p
                    LEFT JOIN users u ON p.lead_user_id = u.id
                    ORDER BY p.created_at DESC
                    """
                ).fetchall()
            ]

    @app.get("/api/v1/websites")
    def list_websites(
        environment: str | None = None,
        workflow_status: str | None = None,
        user: dict = Depends(get_current_user),
    ) -> list[dict[str, Any]]:
        check_permission(user, "view_records")
        with db_manager.session() as conn:
            q = """
                SELECT w.*, p.name AS project_name, u.full_name AS maintainer_name
                FROM websites w
                JOIN projects p ON w.project_id = p.id
                LEFT JOIN users u ON w.maintainer_id = u.id
                WHERE 1=1
            """
            params: list[Any] = []
            if environment:
                q += " AND w.environment = ?"
                params.append(environment)
            if workflow_status:
                q += " AND w.workflow_status = ?"
                params.append(workflow_status)
            q += " ORDER BY w.name ASC"
            return [dict(r) for r in conn.execute(q, params).fetchall()]

    @app.post("/api/v1/websites/import")
    def import_websites_endpoint(
        payload: ImportWebsitesPayload, user: dict = Depends(get_current_user)
    ) -> dict[str, Any]:
        check_permission(user, "assign_work")
        with db_manager.session() as conn:
            return InventoryImportService.import_websites(
                conn,
                rows=payload.rows,
                default_project_id=payload.default_project_id,
                default_maintainer_id=payload.default_maintainer_id,
                actor_user_id=user["id"],
                dry_run=payload.dry_run,
            )

    @app.get("/api/v1/templates/current")
    def get_current_template(user: dict = Depends(get_current_user)) -> dict[str, Any]:
        check_permission(user, "view_records")
        with db_manager.session() as conn:
            tpl = SOPGateService.ensure_default_template(conn, created_by=user["id"])
            tpl["tasks_schema"] = json.loads(tpl.pop("tasks_schema_json"))
            tpl["rules_reference"] = json.loads(tpl.pop("rules_reference_json"))
            return tpl

    @app.post("/api/v1/sessions")
    def start_maintenance_session(
        payload: StartSessionPayload, user: dict = Depends(get_current_user)
    ) -> dict[str, Any]:
        check_permission(user, "execute_maintenance")
        with db_manager.session() as conn:
            return SOPGateService.start_session(
                conn,
                website_id=payload.website_id,
                maintainer_id=payload.maintainer_id,
                reviewer_id=payload.reviewer_id,
            )

    @app.get("/api/v1/sessions")
    def list_sessions(user: dict = Depends(get_current_user)) -> list[dict[str, Any]]:
        check_permission(user, "view_records")
        with db_manager.session() as conn:
            return [
                dict(r)
                for r in conn.execute(
                    """
                    SELECT s.id, s.website_id, s.template_version, s.maintainer_id, s.status,
                           s.environment_snapshot, s.builder_snapshot, s.started_at, s.closed_at,
                           w.name AS website_name, w.domain AS website_domain, u.full_name AS maintainer_name
                    FROM maintenance_sessions s
                    JOIN websites w ON s.website_id = w.id
                    JOIN users u ON s.maintainer_id = u.id
                    ORDER BY s.started_at DESC
                    """
                ).fetchall()
            ]

    @app.get("/api/v1/sessions/{session_id}")
    def get_session(session_id: str, user: dict = Depends(get_current_user)) -> dict[str, Any]:
        check_permission(user, "view_records")
        with db_manager.session() as conn:
            return SOPGateService.get_session_detail(conn, session_id)

    @app.patch("/api/v1/sessions/{session_id}/items/{step_number}")
    def update_session_step(
        session_id: str,
        step_number: int,
        payload: UpdateStepPayload,
        user: dict = Depends(get_current_user),
    ) -> dict[str, Any]:
        check_permission(user, "execute_maintenance")
        with db_manager.session() as conn:
            try:
                return SOPGateService.update_checklist_item(
                    conn,
                    session_id=session_id,
                    step_number=step_number,
                    actor_user_id=user["id"],
                    status=payload.status,
                    observation=payload.observation,
                    action_taken=payload.action_taken,
                    na_reason=payload.na_reason,
                    blocked_reason=payload.blocked_reason,
                    is_applicable_override=payload.is_applicable_override,
                    linked_issue_id=payload.linked_issue_id,
                    linked_approval_id=payload.linked_approval_id,
                )
            except SOPGateViolationError as exc:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    @app.post("/api/v1/sessions/{session_id}/close")
    def close_session_endpoint(
        session_id: str,
        payload: CloseSessionPayload,
        user: dict = Depends(get_current_user),
    ) -> dict[str, Any]:
        check_permission(user, "execute_maintenance")
        with db_manager.session() as conn:
            try:
                return SOPGateService.close_session(
                    conn,
                    session_id=session_id,
                    actor_user_id=user["id"],
                    target_status=payload.target_status,
                    closure_summary=payload.closure_summary,
                )
            except SOPGateViolationError as exc:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    @app.post("/api/v1/sessions/{session_id}/run-readonly-checks")
    def run_readonly_checks_endpoint(
        session_id: str, user: dict = Depends(get_current_user)
    ) -> dict[str, Any]:
        check_permission(user, "execute_maintenance")
        with db_manager.session() as conn:
            return SafeReadOnlyCheckRunner.run_session_readonly_checks(
                conn, session_id=session_id, actor_user_id=user["id"]
            )

    @app.post("/api/v1/backups")
    def create_backup_endpoint(
        payload: CreateBackupPayload, user: dict = Depends(get_current_user)
    ) -> dict[str, Any]:
        check_permission(user, "execute_maintenance")
        with db_manager.session() as conn:
            return BackupService.record_backup(
                conn,
                website_id=payload.website_id,
                session_id=payload.session_id,
                storage_location=payload.storage_location,
                created_by=user["id"],
                backup_type=payload.backup_type,
                size_mb=payload.size_mb,
                is_verified=payload.is_verified,
                restore_test_status=payload.restore_test_status,
                notes=payload.notes,
            )

    @app.post("/api/v1/backups/{backup_id}/verify")
    def verify_backup_endpoint(
        backup_id: str, payload: VerifyBackupPayload, user: dict = Depends(get_current_user)
    ) -> dict[str, Any]:
        check_permission(user, "execute_maintenance")
        with db_manager.session() as conn:
            return BackupService.verify_backup(
                conn,
                backup_id=backup_id,
                verifier_user_id=user["id"],
                restore_test_status=payload.restore_test_status,
            )

    @app.get("/api/v1/backups")
    def list_backups(user: dict = Depends(get_current_user)) -> list[dict[str, Any]]:
        check_permission(user, "view_records")
        with db_manager.session() as conn:
            return [
                dict(r)
                for r in conn.execute(
                    """
                    SELECT b.*, w.name AS website_name, w.domain AS website_domain, u.full_name AS creator_name
                    FROM backup_records b
                    JOIN websites w ON b.website_id = w.id
                    JOIN users u ON b.created_by = u.id
                    ORDER BY b.created_at DESC
                    """
                ).fetchall()
            ]

    @app.post("/api/v1/approvals")
    def request_approval_endpoint(
        payload: RequestApprovalPayload, user: dict = Depends(get_current_user)
    ) -> dict[str, Any]:
        check_permission(user, "execute_maintenance")
        with db_manager.session() as conn:
            return ApprovalService.request_approval(
                conn,
                project_id=payload.project_id,
                website_id=payload.website_id,
                session_id=payload.session_id,
                checklist_item_id=payload.checklist_item_id,
                action_type=payload.action_type,
                summary=payload.summary,
                risk_notes=payload.risk_notes,
                requester_id=user["id"],
                approver_id=payload.approver_id,
            )

    @app.post("/api/v1/approvals/{approval_id}/decide")
    def decide_approval_endpoint(
        approval_id: str, payload: DecideApprovalPayload, user: dict = Depends(get_current_user)
    ) -> dict[str, Any]:
        with db_manager.session() as conn:
            try:
                return ApprovalService.decide_approval(
                    conn,
                    approval_id=approval_id,
                    approver_user_id=user["id"],
                    decision=payload.decision,
                    rationale=payload.rationale,
                )
            except ApprovalPolicyError as exc:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))

    @app.get("/api/v1/approvals")
    def list_approvals(user: dict = Depends(get_current_user)) -> list[dict[str, Any]]:
        check_permission(user, "view_records")
        with db_manager.session() as conn:
            return [
                dict(r)
                for r in conn.execute(
                    """
                    SELECT a.*, req.full_name AS requester_name, app.full_name AS approver_name,
                           w.name AS website_name, w.domain AS website_domain
                    FROM approvals a
                    JOIN users req ON a.requester_id = req.id
                    LEFT JOIN users app ON a.approver_id = app.id
                    LEFT JOIN websites w ON a.website_id = w.id
                    ORDER BY a.requested_at DESC
                    """
                ).fetchall()
            ]

    @app.post("/api/v1/issues")
    def create_issue_endpoint(
        payload: CreateIssuePayload, user: dict = Depends(get_current_user)
    ) -> dict[str, Any]:
        check_permission(user, "execute_maintenance")
        with db_manager.session() as conn:
            return IssueService.create_issue(
                conn,
                project_id=payload.project_id,
                website_id=payload.website_id,
                session_id=payload.session_id,
                checklist_item_id=payload.checklist_item_id,
                category=payload.category,
                severity=payload.severity,
                priority=payload.priority,
                title=payload.title,
                description=payload.description,
                owner_id=payload.owner_id,
                reviewer_id=payload.reviewer_id,
                due_at=payload.due_at,
                actor_user_id=user["id"],
            )

    @app.post("/api/v1/issues/{issue_id}/remediate")
    def remediate_issue_endpoint(
        issue_id: str, payload: RemediateIssuePayload, user: dict = Depends(get_current_user)
    ) -> dict[str, Any]:
        check_permission(user, "execute_maintenance")
        with db_manager.session() as conn:
            try:
                return IssueService.record_remediation(
                    conn,
                    issue_id=issue_id,
                    actor_user_id=user["id"],
                    remediation_notes=payload.remediation_notes,
                    request_verification=payload.request_verification,
                )
            except IssueVerificationError as exc:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    @app.post("/api/v1/issues/{issue_id}/verify")
    def verify_issue_endpoint(
        issue_id: str, payload: VerifyIssuePayload, user: dict = Depends(get_current_user)
    ) -> dict[str, Any]:
        check_permission(user, "verify_work")
        with db_manager.session() as conn:
            return IssueService.verify_issue(
                conn,
                issue_id=issue_id,
                verifier_user_id=user["id"],
                passed=payload.passed,
                verification_notes=payload.verification_notes,
                close_on_pass=payload.close_on_pass,
            )

    @app.post("/api/v1/issues/{issue_id}/close")
    def close_issue_endpoint(
        issue_id: str, payload: DirectCloseIssuePayload, user: dict = Depends(get_current_user)
    ) -> dict[str, Any]:
        check_permission(user, "execute_maintenance")
        with db_manager.session() as conn:
            try:
                return IssueService.close_issue_directly(
                    conn,
                    issue_id=issue_id,
                    actor_user_id=user["id"],
                    target_status=payload.target_status,
                    closure_reason=payload.closure_reason,
                )
            except IssueVerificationError as exc:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    @app.get("/api/v1/issues")
    def list_issues(user: dict = Depends(get_current_user)) -> list[dict[str, Any]]:
        check_permission(user, "view_records")
        with db_manager.session() as conn:
            return [
                dict(r)
                for r in conn.execute(
                    """
                    SELECT i.*, p.name AS project_name, w.name AS website_name, w.domain AS website_domain,
                           u.full_name AS owner_name
                    FROM issues i
                    JOIN projects p ON i.project_id = p.id
                    LEFT JOIN websites w ON i.website_id = w.id
                    LEFT JOIN users u ON i.owner_id = u.id
                    ORDER BY i.created_at DESC
                    """
                ).fetchall()
            ]

    @app.post("/api/v1/tasks")
    def create_task_endpoint(
        payload: CreateTaskPayload, user: dict = Depends(get_current_user)
    ) -> dict[str, Any]:
        check_permission(user, "execute_maintenance")
        with db_manager.session() as conn:
            return TaskService.create_task(
                conn,
                project_id=payload.project_id,
                title=payload.title,
                owner_id=payload.owner_id,
                actor_user_id=user["id"],
                description=payload.description,
                website_id=payload.website_id,
                session_id=payload.session_id,
                issue_id=payload.issue_id,
                priority=payload.priority,
                status=payload.status,
                due_at=payload.due_at,
                estimated_hours=payload.estimated_hours,
                acceptance_criteria=payload.acceptance_criteria,
                depends_on=payload.depends_on,
            )

    @app.patch("/api/v1/tasks/{task_id}/status")
    def update_task_status_endpoint(
        task_id: str, payload: UpdateTaskStatusPayload, user: dict = Depends(get_current_user)
    ) -> dict[str, Any]:
        check_permission(user, "execute_maintenance")
        with db_manager.session() as conn:
            try:
                return TaskService.update_task_status(
                    conn,
                    task_id=task_id,
                    new_status=payload.new_status,
                    actor_user_id=user["id"],
                    cancellation_reason=payload.cancellation_reason,
                    new_owner_id=payload.new_owner_id,
                )
            except TaskValidationError as exc:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    @app.post("/api/v1/tasks/{task_id}/work-logs")
    def add_work_log_endpoint(
        task_id: str, payload: WorkLogPayload, user: dict = Depends(get_current_user)
    ) -> dict[str, Any]:
        check_permission(user, "execute_maintenance")
        with db_manager.session() as conn:
            return TaskService.add_work_log(
                conn,
                task_id=task_id,
                author_id=user["id"],
                what_was_done=payload.what_was_done,
                what_remains=payload.what_remains,
                blockers=payload.blockers,
                next_action=payload.next_action,
                hours_logged=payload.hours_logged,
            )

    @app.get("/api/v1/tasks/{task_id}/work-logs")
    def list_task_work_logs_endpoint(
        task_id: str, user: dict = Depends(get_current_user)
    ) -> list[dict[str, Any]]:
        check_permission(user, "view_records")
        with db_manager.session() as conn:
            return TaskService.list_work_logs(conn, task_id)

    @app.get("/api/v1/tasks")
    def list_tasks(owner_id: str | None = None, user: dict = Depends(get_current_user)) -> list[dict[str, Any]]:
        check_permission(user, "view_records")
        with db_manager.session() as conn:
            q = """
                SELECT t.*, p.name AS project_name, u.full_name AS owner_name
                FROM tasks t
                JOIN projects p ON t.project_id = p.id
                JOIN users u ON t.owner_id = u.id
                WHERE 1=1
            """
            params: list[Any] = []
            if owner_id:
                q += " AND t.owner_id = ?"
                params.append(owner_id)
            q += " ORDER BY t.created_at DESC"
            return [dict(r) for r in conn.execute(q, params).fetchall()]

    @app.post("/api/v1/reports/sessions/{session_id}/pdf")
    def generate_session_report_endpoint(
        session_id: str, user: dict = Depends(get_current_user)
    ) -> dict[str, Any]:
        check_permission(user, "export_reports")
        with db_manager.session() as conn:
            return ReportAndExportService.generate_session_pdf_report(
                conn, session_id=session_id, actor_user_id=user["id"]
            )

    @app.post("/api/v1/reports/export-xlsx")
    def export_xlsx_endpoint(user: dict = Depends(get_current_user)) -> dict[str, Any]:
        check_permission(user, "export_reports")
        with db_manager.session() as conn:
            path = ReportAndExportService.export_inventory_and_issues_xlsx(conn, actor_user_id=user["id"])
            return {"xlsx_path": str(path)}

    @app.get("/api/v1/reports")
    def list_reports_and_reminders(user: dict = Depends(get_current_user)) -> list[dict[str, Any]]:
        check_permission(user, "view_records")
        with db_manager.session() as conn:
            return [
                dict(r)
                for r in conn.execute(
                    "SELECT * FROM reminders_and_reports ORDER BY generated_at DESC"
                ).fetchall()
            ]

    @app.post("/api/v1/scheduler/run-cycle")
    def trigger_scheduler_cycle(user: dict = Depends(get_current_user)) -> dict[str, Any]:
        check_permission(user, "assign_work")
        with db_manager.session() as conn:
            return MaintenanceSchedulerWorker.run_cycle(conn)

    @app.get("/api/v1/audit/events")
    def list_audit_events(
        entity_type: str | None = None,
        entity_id: str | None = None,
        limit: int = Query(default=100, le=500),
        user: dict = Depends(get_current_user),
    ) -> list[dict[str, Any]]:
        check_permission(user, "view_records")
        with db_manager.session() as conn:
            return AuditService.list_events(conn, entity_type=entity_type, entity_id=entity_id, limit=limit)

    @app.get("/api/v1/search")
    def global_search(q: str = Query(..., min_length=1), user: dict = Depends(get_current_user)) -> dict[str, Any]:
        check_permission(user, "view_records")
        pattern = f"%{q.strip()}%"
        with db_manager.session() as conn:
            projects = [
                dict(r)
                for r in conn.execute(
                    "SELECT id, code, name, status FROM projects WHERE name LIKE ? OR code LIKE ?",
                    (pattern, pattern),
                ).fetchall()
            ]
            websites = [
                dict(r)
                for r in conn.execute(
                    "SELECT id, name, domain, environment, workflow_status FROM websites WHERE name LIKE ? OR domain LIKE ?",
                    (pattern, pattern),
                ).fetchall()
            ]
            tasks = [
                dict(r)
                for r in conn.execute(
                    "SELECT id, title, status, priority FROM tasks WHERE title LIKE ? OR id LIKE ?",
                    (pattern, pattern),
                ).fetchall()
            ]
            issues = [
                dict(r)
                for r in conn.execute(
                    "SELECT id, title, severity, status FROM issues WHERE title LIKE ? OR id LIKE ?",
                    (pattern, pattern),
                ).fetchall()
            ]
            return {
                "query": q,
                "projects": projects,
                "websites": websites,
                "tasks": tasks,
                "issues": issues,
            }

    return app


app = create_app()