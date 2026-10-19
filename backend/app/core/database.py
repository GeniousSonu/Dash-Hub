from contextlib import contextmanager
from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3
import tempfile
from typing import Iterator
import uuid

from backend.app.core.config import settings


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def new_uuid() -> str:
    return str(uuid.uuid4())


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS organizations (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    settings_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    org_id TEXT NOT NULL REFERENCES organizations(id),
    email TEXT NOT NULL UNIQUE,
    full_name TEXT NOT NULL,
    role TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    working_status TEXT NOT NULL DEFAULT 'available',
    notification_prefs_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_role_scopes (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_name TEXT NOT NULL,
    project_id TEXT,
    website_id TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    org_id TEXT NOT NULL REFERENCES organizations(id),
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    client_name TEXT NOT NULL DEFAULT '',
    lead_user_id TEXT REFERENCES users(id),
    status TEXT NOT NULL DEFAULT 'active',
    priority TEXT NOT NULL DEFAULT 'normal',
    start_date TEXT,
    target_date TEXT,
    repo_links_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS milestones (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    target_date TEXT,
    status TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS websites (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id),
    name TEXT NOT NULL,
    domain TEXT NOT NULL,
    url TEXT NOT NULL,
    staging_url TEXT NOT NULL DEFAULT '',
    dev_url TEXT NOT NULL DEFAULT '',
    environment TEXT NOT NULL DEFAULT 'live',
    hosting_type TEXT NOT NULL DEFAULT 'managed_wp',
    health_status TEXT NOT NULL DEFAULT 'unknown',
    workflow_status TEXT NOT NULL DEFAULT 'due',
    maintainer_id TEXT REFERENCES users(id),
    developer_id TEXT REFERENCES users(id),
    reviewer_id TEXT REFERENCES users(id),
    frequency TEXT NOT NULL DEFAULT 'monthly',
    due_anchor_policy TEXT NOT NULL DEFAULT 'planned_date',
    last_completed_at TEXT,
    next_due_at TEXT,
    wp_version TEXT NOT NULL DEFAULT 'not_verified',
    php_version TEXT NOT NULL DEFAULT 'not_verified',
    active_theme TEXT NOT NULL DEFAULT '',
    is_child_theme_active INTEGER NOT NULL DEFAULT 0,
    builder TEXT NOT NULL DEFAULT 'gutenberg',
    has_wordfence INTEGER NOT NULL DEFAULT 1,
    backup_policy TEXT NOT NULL DEFAULT 'full_files_and_db_before_update',
    approved_backup_storage TEXT NOT NULL DEFAULT 's3://opshub-verified-backups',
    security_plugins_json TEXT NOT NULL DEFAULT '[]',
    persistent_notes TEXT NOT NULL DEFAULT '',
    developer_instructions TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(domain, environment)
);

CREATE TABLE IF NOT EXISTS workflow_templates (
    id TEXT PRIMARY KEY,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    version INTEGER NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    tasks_schema_json TEXT NOT NULL,
    rules_reference_json TEXT NOT NULL,
    created_by TEXT REFERENCES users(id),
    created_at TEXT NOT NULL,
    UNIQUE(code, version)
);

CREATE TABLE IF NOT EXISTS maintenance_schedules (
    id TEXT PRIMARY KEY,
    website_id TEXT NOT NULL UNIQUE REFERENCES websites(id) ON DELETE CASCADE,
    template_code TEXT NOT NULL DEFAULT 'WP_MAINT_SOP',
    frequency TEXT NOT NULL DEFAULT 'monthly',
    interval_days INTEGER NOT NULL DEFAULT 30,
    anchor_policy TEXT NOT NULL DEFAULT 'planned_date',
    planned_due_at TEXT NOT NULL,
    last_completed_at TEXT,
    next_due_at TEXT NOT NULL,
    owner_id TEXT REFERENCES users(id),
    is_active INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS maintenance_sessions (
    id TEXT PRIMARY KEY,
    website_id TEXT NOT NULL REFERENCES websites(id),
    template_id TEXT NOT NULL REFERENCES workflow_templates(id),
    template_version INTEGER NOT NULL,
    template_snapshot_json TEXT NOT NULL,
    maintainer_id TEXT NOT NULL REFERENCES users(id),
    reviewer_id TEXT REFERENCES users(id),
    status TEXT NOT NULL DEFAULT 'in_progress',
    environment_snapshot TEXT NOT NULL,
    builder_snapshot TEXT NOT NULL,
    planned_due_at TEXT,
    started_at TEXT NOT NULL,
    closed_at TEXT,
    closure_summary TEXT NOT NULL DEFAULT '',
    report_sent_at TEXT
);

CREATE TABLE IF NOT EXISTS session_checklist_items (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES maintenance_sessions(id) ON DELETE CASCADE,
    step_number INTEGER NOT NULL,
    code TEXT NOT NULL,
    title TEXT NOT NULL,
    required_process TEXT NOT NULL,
    automation_mode TEXT NOT NULL,
    is_conditional INTEGER NOT NULL DEFAULT 0,
    is_applicable INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'pending',
    owner_id TEXT REFERENCES users(id),
    observation TEXT NOT NULL DEFAULT '',
    action_taken TEXT NOT NULL DEFAULT '',
    na_reason TEXT NOT NULL DEFAULT '',
    blocked_reason TEXT NOT NULL DEFAULT '',
    rule_ref_key TEXT NOT NULL DEFAULT '',
    linked_issue_id TEXT,
    linked_approval_id TEXT,
    verified_by TEXT REFERENCES users(id),
    verified_at TEXT,
    updated_at TEXT NOT NULL,
    UNIQUE(session_id, step_number)
);

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id),
    milestone_id TEXT REFERENCES milestones(id),
    website_id TEXT REFERENCES websites(id),
    session_id TEXT REFERENCES maintenance_sessions(id),
    issue_id TEXT,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    owner_id TEXT NOT NULL REFERENCES users(id),
    reviewer_id TEXT REFERENCES users(id),
    priority TEXT NOT NULL DEFAULT 'normal',
    status TEXT NOT NULL DEFAULT 'ready',
    start_date TEXT,
    due_at TEXT,
    completed_at TEXT,
    estimated_hours REAL NOT NULL DEFAULT 0.0,
    actual_hours REAL NOT NULL DEFAULT 0.0,
    acceptance_criteria TEXT NOT NULL DEFAULT '',
    cancellation_reason TEXT NOT NULL DEFAULT '',
    depends_on_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS task_work_logs (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    author_id TEXT NOT NULL REFERENCES users(id),
    what_was_done TEXT NOT NULL,
    what_remains TEXT NOT NULL DEFAULT '',
    blockers TEXT NOT NULL DEFAULT '',
    next_action TEXT NOT NULL DEFAULT '',
    hours_logged REAL NOT NULL DEFAULT 0.0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS issues (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id),
    website_id TEXT REFERENCES websites(id),
    session_id TEXT REFERENCES maintenance_sessions(id),
    checklist_item_id TEXT REFERENCES session_checklist_items(id),
    source_task_id TEXT REFERENCES tasks(id),
    category TEXT NOT NULL,
    severity TEXT NOT NULL,
    priority TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    affected_component TEXT NOT NULL DEFAULT '',
    reproduction_steps TEXT NOT NULL DEFAULT '',
    owner_id TEXT REFERENCES users(id),
    reviewer_id TEXT REFERENCES users(id),
    status TEXT NOT NULL DEFAULT 'new',
    due_at TEXT,
    remediation_notes TEXT NOT NULL DEFAULT '',
    verification_outcome TEXT NOT NULL DEFAULT '',
    verified_by TEXT REFERENCES users(id),
    verified_at TEXT,
    closure_reason TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS approvals (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id),
    website_id TEXT REFERENCES websites(id),
    session_id TEXT REFERENCES maintenance_sessions(id),
    checklist_item_id TEXT REFERENCES session_checklist_items(id),
    issue_id TEXT REFERENCES issues(id),
    action_type TEXT NOT NULL,
    summary TEXT NOT NULL,
    risk_notes TEXT NOT NULL DEFAULT '',
    evidence_ref TEXT NOT NULL DEFAULT '',
    requester_id TEXT NOT NULL REFERENCES users(id),
    approver_id TEXT REFERENCES users(id),
    status TEXT NOT NULL DEFAULT 'pending',
    decision_rationale TEXT NOT NULL DEFAULT '',
    requested_at TEXT NOT NULL,
    decided_at TEXT,
    executed_by TEXT REFERENCES users(id),
    executed_at TEXT,
    verified_by TEXT REFERENCES users(id),
    verified_at TEXT
);

CREATE TABLE IF NOT EXISTS backup_records (
    id TEXT PRIMARY KEY,
    website_id TEXT NOT NULL REFERENCES websites(id),
    session_id TEXT REFERENCES maintenance_sessions(id),
    backup_type TEXT NOT NULL DEFAULT 'full_files_and_db',
    storage_location TEXT NOT NULL,
    size_mb REAL NOT NULL DEFAULT 0.0,
    status TEXT NOT NULL DEFAULT 'completed',
    is_verified INTEGER NOT NULL DEFAULT 0,
    verified_by TEXT REFERENCES users(id),
    verified_at TEXT,
    restore_test_status TEXT NOT NULL DEFAULT 'not_tested',
    retention_days INTEGER NOT NULL DEFAULT 30,
    exception_approval_id TEXT REFERENCES approvals(id),
    notes TEXT NOT NULL DEFAULT '',
    created_by TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evidences (
    id TEXT PRIMARY KEY,
    session_id TEXT REFERENCES maintenance_sessions(id),
    checklist_item_id TEXT REFERENCES session_checklist_items(id),
    task_id TEXT REFERENCES tasks(id),
    issue_id TEXT REFERENCES issues(id),
    evidence_type TEXT NOT NULL,
    title TEXT NOT NULL,
    storage_path TEXT NOT NULL DEFAULT '',
    content_json TEXT NOT NULL DEFAULT '{}',
    access_used TEXT NOT NULL DEFAULT 'manual',
    limitations TEXT NOT NULL DEFAULT '',
    captured_by TEXT REFERENCES users(id),
    captured_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reminders_and_reports (
    id TEXT PRIMARY KEY,
    record_type TEXT NOT NULL,
    subtype TEXT NOT NULL,
    target_entity_type TEXT NOT NULL,
    target_entity_id TEXT NOT NULL,
    title TEXT NOT NULL,
    recipients_json TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'sent',
    is_revised_report INTEGER NOT NULL DEFAULT 0,
    retry_count INTEGER NOT NULL DEFAULT 0,
    artifact_path TEXT NOT NULL DEFAULT '',
    error_message TEXT NOT NULL DEFAULT '',
    payload_summary_json TEXT NOT NULL DEFAULT '{}',
    generated_at TEXT NOT NULL,
    sent_at TEXT
);

CREATE TABLE IF NOT EXISTS activity_events (
    id TEXT PRIMARY KEY,
    actor_user_id TEXT,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    action TEXT NOT NULL,
    summary TEXT NOT NULL,
    before_json TEXT NOT NULL DEFAULT '{}',
    after_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TRIGGER IF NOT EXISTS prevent_activity_events_update
BEFORE UPDATE ON activity_events
BEGIN
    SELECT RAISE(ABORT, 'activity_events is append-only and cannot be updated');
END;

CREATE TRIGGER IF NOT EXISTS prevent_activity_events_delete
BEFORE DELETE ON activity_events
BEGIN
    SELECT RAISE(ABORT, 'activity_events is append-only and cannot be deleted');
END;

CREATE TABLE IF NOT EXISTS integration_configurations (
    id TEXT PRIMARY KEY,
    website_id TEXT REFERENCES websites(id),
    integration_type TEXT NOT NULL,
    endpoint_url TEXT NOT NULL DEFAULT '',
    credential_ref TEXT NOT NULL DEFAULT '',
    is_enabled INTEGER NOT NULL DEFAULT 1,
    settings_json TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT NOT NULL
);
"""


class DatabaseManager:
    def __init__(self, db_path: Path | None = None):
        self.db_path = Path(db_path) if db_path else settings.db_path

    def connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    @contextmanager
    def session(self) -> Iterator[sqlite3.Connection]:
        conn = self.connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_schema(self) -> None:
        try:
            with self.session() as conn:
                conn.executescript(SCHEMA_SQL)
        except sqlite3.OperationalError:
            self.db_path = Path(tempfile.gettempdir()) / "opshub_runtime" / "opshub.db"
            with self.session() as conn:
                conn.executescript(SCHEMA_SQL)


db_manager = DatabaseManager()
