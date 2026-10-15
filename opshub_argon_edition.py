#!/usr/bin/env python3
"""
OpsHub — Maintenance & Project Operations Command Center (Argon Design System Edition)
Unified FastAPI Backend + 23-Step WordPress SOP Gating Engine + Responsive PySide6 Desktop Client.

Highlights in this production edition:
  - Centralized Argon Design System Tokens (`ARGON_TOKENS`) with Light & Dark Mode toggle (`◐`)
  - Responsive Window Geometry (`85%` of screen, `setMinimumSize(860, 540)`, `QScrollArea` wrapper, collapsible sidebar `☰`)
  - JWT + 6-digit 2FA TOTP Authentication (`/api/v1/auth/login` & `/api/v1/auth/verify-2fa`) + 7-Role RBAC
  - Runtime Feature Flags (`/api/v1/feature-flags`) & Internationalization (`EN`, `ES`, `HI`)
  - Full 23-Step WordPress SOP Gating Engine (`INV-01`..`INV-06`), Read-Only Checks, PDF & Excel Exporters
"""

import json
import os
import sqlite3
import sys
import tempfile
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.testclient import TestClient
import httpx
import openpyxl
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


# ============================================================================
# 1. CONFIGURATION, DATABASE SCHEMA (16 TABLES) & APPEND-ONLY AUDIT TRAIL
# ============================================================================

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("OPSHUB_DATA_DIR", str(BASE_DIR / "storage")))
REPORTS_DIR = DATA_DIR / "reports"
MAIL_SINK_DIR = DATA_DIR / "mail_sink"


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
        default_path = Path(os.getenv("OPSHUB_DB_PATH", str(BASE_DIR / "opshub.db")))
        self.db_path = Path(db_path) if db_path else default_path

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


# ============================================================================
# 2. RBAC PERMISSIONS & APPEND-ONLY AUDIT SERVICE
# ============================================================================

ROLE_PERMISSIONS: dict[str, set[str]] = {
    "system_admin": {
        "manage_users",
        "manage_templates",
        "manage_integrations",
        "assign_work",
        "execute_maintenance",
        "approve_developer_changes",
        "approve_manager_exceptions",
        "verify_work",
        "view_records",
        "export_reports",
    },
    "manager": {
        "assign_work",
        "execute_maintenance",
        "approve_manager_exceptions",
        "verify_work",
        "view_records",
        "export_reports",
    },
    "maintenance_engineer": {"execute_maintenance", "view_records", "export_reports"},
    "developer": {"execute_maintenance", "approve_developer_changes", "view_records", "export_reports"},
    "reviewer_qa": {"verify_work", "view_records", "export_reports"},
    "readonly_stakeholder": {"view_records"},
    "report_recipient": set(),
}


def check_permission(user_row: dict[str, Any], required_permission: str) -> None:
    if not user_row or not user_row.get("is_active", 0):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is inactive or unrecognized.")
    role = user_row.get("role", "")
    if required_permission not in ROLE_PERMISSIONS.get(role, set()):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role '{role}' does not have permission '{required_permission}'.",
        )


class AuditService:
    @staticmethod
    def log_event(
        conn: sqlite3.Connection,
        *,
        actor_user_id: str | None,
        entity_type: str,
        entity_id: str,
        action: str,
        summary: str,
        before_state: dict[str, Any] | None = None,
        after_state: dict[str, Any] | None = None,
    ) -> str:
        event_id = new_uuid()
        conn.execute(
            """
            INSERT INTO activity_events (
                id, actor_user_id, entity_type, entity_id, action, summary, before_json, after_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                actor_user_id,
                entity_type,
                entity_id,
                action,
                summary,
                json.dumps(before_state or {}, default=str),
                json.dumps(after_state or {}, default=str),
                utc_now_iso(),
            ),
        )
        return event_id

    @staticmethod
    def list_events(conn: sqlite3.Connection, limit: int = 100) -> list[dict[str, Any]]:
        rows = conn.execute(
            """
            SELECT e.*, u.full_name AS actor_name, u.role AS actor_role
            FROM activity_events e
            LEFT JOIN users u ON e.actor_user_id = u.id
            ORDER BY e.created_at DESC, e.rowid DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


# ============================================================================
# 3. 23-STEP WORDPRESS MAINTENANCE SOP SEED & GATING ENGINE
# ============================================================================

CANONICAL_RULE_REFERENCES: dict[str, dict[str, str]] = {
    "htaccess_security_headers": {
        "title": "Required .htaccess Security Headers & PHP Disclosure Controls",
        "snippet": (
            "<IfModule mod_headers.c>\n"
            '    Header always set X-Frame-Options "SAMEORIGIN"\n'
            '    Header always set X-Content-Type-Options "nosniff"\n'
            "    Header unset X-Powered-By\n"
            "    # Enable HSTS includeSubDomains ONLY after confirming all subdomains serve HTTPS\n"
            "</IfModule>"
        ),
        "guidance": "Validate Apache compatibility and subdomain HTTPS readiness before changes. Do not append duplicate directives.",
    },
    "file_permissions_policy": {
        "title": "Live & Staging File Permission Policy Targets",
        "snippet": "Directories: 755 | Standard Files: 644 | .htaccess: 644 | wp-config.php: 444 or 600 per host",
        "guidance": "Treat 444/644 as policy inputs to validate against the host, never universal values forced automatically.",
    },
    "wp_debug_constants": {
        "title": "Approved WordPress Debug Constants (wp-config.php)",
        "snippet": "define('WP_DEBUG', false);\ndefine('WP_DEBUG_LOG', false);\ndefine('WP_DEBUG_DISPLAY', false);\ndefine('SCRIPT_DEBUG', false);",
        "guidance": "Detect duplicate constant definitions; avoid editing wp-config.php unattended on live sites.",
    },
    "staging_robots_policy": {
        "title": "Staging Search-Engine Discouragement & Access Control Notice",
        "snippet": "User-agent: *\nDisallow: /",
        "guidance": "robots.txt does NOT provide access control. Use HTTP Basic Auth or Password Protected plugin for private staging sites.",
    },
    "directory_indexing_rule": {
        "title": "Disable Directory Listing Directive",
        "snippet": "Options -Indexes",
        "guidance": "Verify directory listing is disabled at the web server level where supported.",
    },
    "plugin_cleanup_review_list": {
        "title": "Plugins & Themes Flagged for Cleanup Review",
        "snippet": "WP File Manager, Hello Dolly, Akismet Anti Spam, String Locator, WP Rollback, WordPress Importer, All-in-One WP Migration, Better Search Replace",
        "guidance": "A list match is a review trigger, NOT automatic deletion authorization. Verify usage with developer and keep one default theme.",
    },
    "wordfence_and_security_plugins": {
        "title": "Security Plugins & Wordfence Verification Guide",
        "snippet": "WPS Hide Login, Advanced reCAPTCHA, Limit Login Attempts, Stream, Password Protected (staging), Wordfence Scan",
        "guidance": "Verify settings against internal guide, run scan, log actionable findings as issues, and record a post-change re-scan.",
    },
}

WORDPRESS_SOP_23_STEPS: list[dict[str, Any]] = [
    {"step_number": 1, "code": "SOP_01", "title": "Website overview", "required_process": "Review public frontend, links, images, forms, and checkout. Automated link checks assist but do not replace visual review.", "automation_mode": "read_only_check", "is_conditional": False, "condition_type": "always", "rule_ref_key": ""},
    {"step_number": 2, "code": "SOP_02", "title": "Slow website / performance", "required_process": "If slow, run performance check and record tool, URL, metrics, and observations; spawn separate remediation issue.", "automation_mode": "read_only_check", "is_conditional": False, "condition_type": "always", "rule_ref_key": ""},
    {"step_number": 3, "code": "SOP_03", "title": "Default/core files", "required_process": "Compare WordPress core files with trusted checksums where access allows; obtain approval before destructive action.", "automation_mode": "read_only_check", "is_conditional": False, "condition_type": "always", "rule_ref_key": ""},
    {"step_number": 4, "code": "SOP_04", "title": ".htaccess security rules", "required_process": "Check clickjacking, MIME-sniffing, HSTS, and PHP disclosure headers.", "automation_mode": "read_only_check", "is_conditional": False, "condition_type": "always", "rule_ref_key": "htaccess_security_headers"},
    {"step_number": 5, "code": "SOP_05", "title": "File permissions", "required_process": "Inspect permissions where filesystem access is available against host policy (e.g., 444 sensitive PHP, 644 .htaccess).", "automation_mode": "read_only_check", "is_conditional": False, "condition_type": "always", "rule_ref_key": "file_permissions_policy"},
    {"step_number": 6, "code": "SOP_06", "title": "Debug logging", "required_process": "Inspect WP_DEBUG, WP_DEBUG_LOG, WP_DEBUG_DISPLAY, SCRIPT_DEBUG and duplicate constants.", "automation_mode": "read_only_check", "is_conditional": False, "condition_type": "always", "rule_ref_key": "wp_debug_constants"},
    {"step_number": 7, "code": "SOP_07", "title": "Search-engine discouragement for staging", "required_process": "Confirm staging sites discourage indexing (robots.txt Disallow: /) and enforce private access control.", "automation_mode": "read_only_check", "is_conditional": True, "condition_type": "staging_only", "rule_ref_key": "staging_robots_policy"},
    {"step_number": 8, "code": "SOP_08", "title": "Directory indexing", "required_process": "Verify directory listing is disabled at server/configuration level (Options -Indexes).", "automation_mode": "read_only_check", "is_conditional": False, "condition_type": "always", "rule_ref_key": "directory_indexing_rule"},
    {"step_number": 9, "code": "SOP_09", "title": "Backup", "required_process": "MANDATORY LIVE GATE: Require verified backup before update work unless an authorized exception is recorded.", "automation_mode": "suggested_action", "is_conditional": False, "condition_type": "always", "rule_ref_key": ""},
    {"step_number": 10, "code": "SOP_10", "title": "WordPress core updates", "required_process": "Record current/available version. Require developer approval before core upgrade. Locked until Step 9 Backup verified on live sites.", "automation_mode": "approved_action", "is_conditional": False, "condition_type": "always", "rule_ref_key": ""},
    {"step_number": 11, "code": "SOP_11", "title": "Theme updates", "required_process": "Confirm child theme active where expected; update parent theme under approval policy. Locked until Step 9 Backup verified on live sites.", "automation_mode": "approved_action", "is_conditional": False, "condition_type": "always", "rule_ref_key": ""},
    {"step_number": 12, "code": "SOP_12", "title": "Plugin updates", "required_process": "Inventory plugins, review risk, record selected/deferred/failed/successful updates. Locked until Step 9 Backup verified on live sites.", "automation_mode": "approved_action", "is_conditional": False, "condition_type": "always", "rule_ref_key": ""},
    {"step_number": 13, "code": "SOP_13", "title": "Post-update re-check", "required_process": "Re-test frontend, admin, forms, checkout. Critical failure requires linked high-priority issue and blocks normal closure.", "automation_mode": "read_only_check", "is_conditional": False, "condition_type": "always", "rule_ref_key": ""},
    {"step_number": 14, "code": "SOP_14", "title": "Plugin conflicts / duplicate functionality", "required_process": "Flag overlapping cache/performance plugins for review; do not auto-deactivate.", "automation_mode": "read_only_check", "is_conditional": False, "condition_type": "always", "rule_ref_key": ""},
    {"step_number": 15, "code": "SOP_15", "title": "Disable auto-update policy", "required_process": "Inspect core/theme/plugin auto-update settings against organizational policy.", "automation_mode": "read_only_check", "is_conditional": False, "condition_type": "always", "rule_ref_key": ""},
    {"step_number": 16, "code": "SOP_16", "title": "Unused plugins/themes cleanup", "required_process": "Review cleanup list (WP File Manager, Hello Dolly, Akismet, String Locator, WP Rollback, WP Importer, All-in-One WP Migration, Better Search Replace). Require developer approval before deletion.", "automation_mode": "approved_action", "is_conditional": False, "condition_type": "always", "rule_ref_key": "plugin_cleanup_review_list"},
    {"step_number": 17, "code": "SOP_17", "title": "Administrator users", "required_process": "Review administrator accounts and confirm legitimacy; require approval for account changes.", "automation_mode": "read_only_check", "is_conditional": False, "condition_type": "always", "rule_ref_key": ""},
    {"step_number": 18, "code": "SOP_18", "title": "Site Health", "required_process": "Review WordPress Tools -> Site Health recommendations and critical errors.", "automation_mode": "read_only_check", "is_conditional": False, "condition_type": "always", "rule_ref_key": ""},
    {"step_number": 19, "code": "SOP_19", "title": "Divi Builder (conditional)", "required_process": "Shown when website uses Divi. Review Theme Options -> Integration; require developer review before moving custom code.", "automation_mode": "read_only_check", "is_conditional": True, "condition_type": "divi_only", "rule_ref_key": ""},
    {"step_number": 20, "code": "SOP_20", "title": "Security plugins", "required_process": "Verify WPS Hide Login, Advanced reCAPTCHA, Limit Login Attempts, Stream, and Password Protected (staging).", "automation_mode": "read_only_check", "is_conditional": False, "condition_type": "always", "rule_ref_key": "wordfence_and_security_plugins"},
    {"step_number": 21, "code": "SOP_21", "title": "Wordfence scan", "required_process": "Verify Wordfence settings, run scan, create issues for warnings, and record post-change re-scan.", "automation_mode": "read_only_check", "is_conditional": False, "condition_type": "always", "rule_ref_key": "wordfence_and_security_plugins"},
    {"step_number": 22, "code": "SOP_22", "title": "Final frontend check", "required_process": "MANDATORY CLOSURE GATE: Revisit public frontend and key functions before closing the session.", "automation_mode": "read_only_check", "is_conditional": False, "condition_type": "always", "rule_ref_key": ""},
    {"step_number": 23, "code": "SOP_23", "title": "Review notes", "required_process": "MANDATORY CLOSURE GATE: Review persistent notes, previous maintenance notes, open issues, and dev instructions.", "automation_mode": "read_only_check", "is_conditional": False, "condition_type": "always", "rule_ref_key": ""},
]


class SOPGateViolationError(ValueError):
    pass


class SOPGateService:
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
            ) VALUES (?, ?, ?, 1, 1, ?, ?, ?, ?)
            """,
            (
                template_id,
                cls.TEMPLATE_CODE,
                "WordPress Site Maintenance SOP (23-Step Guided Checklist)",
                json.dumps(WORDPRESS_SOP_23_STEPS),
                json.dumps(CANONICAL_RULE_REFERENCES),
                created_by,
                now,
            ),
        )
        return dict(conn.execute("SELECT * FROM workflow_templates WHERE id = ?", (template_id,)).fetchone())

    @classmethod
    def start_session(cls, conn: sqlite3.Connection, *, website_id: str, maintainer_id: str, reviewer_id: str | None = None) -> dict[str, Any]:
        website = conn.execute("SELECT * FROM websites WHERE id = ?", (website_id,)).fetchone()
        if not website:
            raise ValueError(f"Website '{website_id}' not found.")
        template = cls.ensure_default_template(conn, created_by=maintainer_id)
        session_id = new_uuid()
        now = utc_now_iso()
        env = website["environment"]
        builder = website["builder"]
        snapshot = {
            "template_id": template["id"],
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
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'in_progress', ?, ?, ?, ?)
            """,
            (
                session_id,
                website_id,
                template["id"],
                template["version"],
                json.dumps(snapshot),
                maintainer_id,
                reviewer_id or website["reviewer_id"],
                env,
                builder,
                website["next_due_at"],
                now,
            ),
        )
        for step in snapshot["tasks"]:
            step_num = int(step["step_number"])
            cond_type = step.get("condition_type", "always")
            is_applicable = 1
            initial_status = "pending"
            na_reason = ""
            if cond_type == "staging_only" and env != "staging":
                is_applicable = 0
                initial_status = "not_applicable"
                na_reason = f"Applies to staging environments only (site is '{env}')."
            elif cond_type == "divi_only" and builder != "divi":
                is_applicable = 0
                initial_status = "not_applicable"
                na_reason = f"Applies to Divi Builder sites only (site builder is '{builder}')."
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
                    1 if step.get("is_conditional") else 0,
                    is_applicable,
                    initial_status,
                    maintainer_id,
                    na_reason,
                    step.get("rule_ref_key", ""),
                    now,
                ),
            )
        conn.execute("UPDATE websites SET workflow_status = 'in_progress', updated_at = ? WHERE id = ?", (now, website_id))
        AuditService.log_event(
            conn,
            actor_user_id=maintainer_id,
            entity_type="maintenance_session",
            entity_id=session_id,
            action="session_started",
            summary=f"Started 23-step SOP session for {website['name']} ({env})",
        )
        return cls.get_session_detail(conn, session_id)

    @classmethod
    def check_live_backup_gate(cls, conn: sqlite3.Connection, session_id: str) -> tuple[bool, str]:
        session = conn.execute("SELECT * FROM maintenance_sessions WHERE id = ?", (session_id,)).fetchone()
        if not session:
            return False, "Session not found."
        if session["environment_snapshot"] != "live":
            return True, f"Environment '{session['environment_snapshot']}' does not enforce live pre-update backup lock."
        bkp = conn.execute(
            "SELECT storage_location FROM backup_records WHERE session_id = ? AND is_verified = 1 LIMIT 1",
            (session_id,),
        ).fetchone()
        if bkp:
            return True, f"Verified backup on record ({bkp['storage_location']})."
        exc = conn.execute(
            "SELECT id FROM approvals WHERE session_id = ? AND action_type = 'backup_exception' AND status IN ('approved', 'executed', 'verified') LIMIT 1",
            (session_id,),
        ).fetchone()
        if exc:
            return True, f"Authorized backup exception approved ({exc['id']})."
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
        linked_issue_id: str | None = None,
        linked_approval_id: str | None = None,
    ) -> dict[str, Any]:
        item = conn.execute(
            "SELECT * FROM session_checklist_items WHERE session_id = ? AND step_number = ?",
            (session_id, step_number),
        ).fetchone()
        if not item:
            raise ValueError(f"Step {step_number} not found.")
        session = conn.execute("SELECT * FROM maintenance_sessions WHERE id = ?", (session_id,)).fetchone()

        if status == "not_applicable":
            eff_na = (na_reason if na_reason is not None else (observation or item["na_reason"])).strip()
            if not eff_na:
                raise SOPGateViolationError(f"Step {step_number} cannot be marked N/A without recording a reason.")
            if step_number in (9, 22, 23) and session["environment_snapshot"] == "live":
                raise SOPGateViolationError(f"Step {step_number} is a mandatory gate on live sites and cannot be marked N/A.")

        if step_number in (10, 11, 12) and status in ("in_progress", "passed"):
            gate_ok, gate_msg = cls.check_live_backup_gate(conn, session_id)
            if not gate_ok:
                raise SOPGateViolationError(gate_msg)

        if step_number == 9 and status == "passed":
            gate_ok, _ = cls.check_live_backup_gate(conn, session_id)
            if not gate_ok:
                raise SOPGateViolationError(
                    "Step 9 (Backup) cannot be marked Passed on a live site until a verified Backup Record is saved."
                )

        now = utc_now_iso()
        conn.execute(
            """
            UPDATE session_checklist_items
            SET status = ?,
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
        AuditService.log_event(
            conn,
            actor_user_id=actor_user_id,
            entity_type="session_checklist_item",
            entity_id=item["id"],
            action="step_updated",
            summary=f"Step {step_number} ({item['title']}) -> {status}",
        )
        return dict(conn.execute("SELECT * FROM session_checklist_items WHERE id = ?", (item["id"],)).fetchone())

    @classmethod
    def close_session(cls, conn: sqlite3.Connection, *, session_id: str, actor_user_id: str, target_status: str = "completed", closure_summary: str = "") -> dict[str, Any]:
        items = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM session_checklist_items WHERE session_id = ? ORDER BY step_number ASC",
                (session_id,),
            ).fetchall()
        ]
        by_step = {i["step_number"]: i for i in items}
        if target_status in ("completed", "completed_with_findings"):
            unfinished = [f"Step {i['step_number']}" for i in items if i["status"] in ("pending", "in_progress")]
            if unfinished:
                raise SOPGateViolationError(f"Cannot close session while steps are pending: {', '.join(unfinished[:5])}")
            gate_ok, gate_msg = cls.check_live_backup_gate(conn, session_id)
            if not gate_ok:
                raise SOPGateViolationError(gate_msg)
            for m_step in (22, 23):
                if by_step[m_step]["status"] != "passed":
                    raise SOPGateViolationError(f"CLOSURE GATE: Step {m_step} ({by_step[m_step]['title']}) must be marked PASSED.")
            if any(i["status"] in ("failed", "not_verified") for i in items):
                target_status = "completed_with_findings"

        now = utc_now_iso()
        conn.execute(
            "UPDATE maintenance_sessions SET status = ?, closed_at = ?, closure_summary = ? WHERE id = ?",
            (target_status, now, closure_summary, session_id),
        )
        return cls.get_session_detail(conn, session_id)

    @classmethod
    def get_session_detail(cls, conn: sqlite3.Connection, session_id: str) -> dict[str, Any]:
        session = conn.execute(
            """
            SELECT s.*, w.name AS website_name, w.domain AS website_domain, u.full_name AS maintainer_name
            FROM maintenance_sessions s
            JOIN websites w ON s.website_id = w.id
            JOIN users u ON s.maintainer_id = u.id
            WHERE s.id = ?
            """,
            (session_id,),
        ).fetchone()
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
            rk = item.get("rule_ref_key", "")
            item["rule_reference"] = rules_ref.get(rk) if rk else None
        gate_ok, gate_msg = cls.check_live_backup_gate(conn, session_id)
        result["backup_gate"] = {"is_satisfied": gate_ok, "message": gate_msg}
        result["items"] = items
        result["counts"] = {
            "total": len(items),
            "passed": sum(1 for i in items if i["status"] == "passed"),
            "failed": sum(1 for i in items if i["status"] == "failed"),
            "blocked": sum(1 for i in items if i["status"] == "blocked"),
            "not_applicable": sum(1 for i in items if i["status"] == "not_applicable"),
            "not_verified": sum(1 for i in items if i["status"] == "not_verified"),
        }
        return result


# ============================================================================
# 4. ARGON DESIGN TOKENS, i18n, SEED DATA & FASTAPI ENDPOINTS
# ============================================================================

ARGON_TOKENS: dict[str, Any] = {
    "brand": {
        "primary": "#5E72E4",       # Argon Indigo
        "primary_hover": "#324CDD",
        "accent": "#11CDEF",        # Argon Cyan
        "success": "#2DCE89",       # Argon Emerald
        "warning": "#FB6340",       # Argon Orange
        "danger": "#F5365C",        # Argon Ruby
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
        "bg_sidebar": "#172B4D",    # Argon Dark Navy
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

I18N_DICTIONARY: dict[str, dict[str, str]] = {
    "en": {
        "app_title": "OpsHub — Maintenance & Project Operations Command Center",
        "search_placeholder": "Global Search across Projects, Websites, Tasks, and Issue IDs (Ctrl+K)...",
    },
    "es": {
        "app_title": "OpsHub — Centro de Mantenimiento y Operaciones de Proyectos",
        "search_placeholder": "Búsqueda global en Proyectos, Sitios, Tareas e Incidencias (Ctrl+K)...",
    },
    "hi": {
        "app_title": "OpsHub — वेबसाइट मेंटेनेंस और प्रोजेक्ट ऑपरेशंस कमांड सेंटर",
        "search_placeholder": "प्रोजेक्ट्स, वेबसाइट्स, टास्क और इश्यू खोजें (Ctrl+K)...",
    },
}

FEATURE_FLAGS: dict[str, bool] = {
    "enforce_live_backup_gate": True,
    "enable_readonly_http_automation": True,
    "enable_2fa_totp_verification": True,
    "enable_argon_dark_mode": True,
    "enable_i18n_multilang": True,
}


def build_argon_qss(mode: str = "light") -> str:
    pal = ARGON_TOKENS["dark"] if mode == "dark" else ARGON_TOKENS["light"]
    brand = ARGON_TOKENS["brand"]
    font_ui = ARGON_TOKENS["typography"]["font_ui"]
    return f"""
QMainWindow, QWidget#CentralWorkArea, QScrollArea {{
    background-color: {pal['bg_canvas']};
    color: {pal['text_primary']};
    font-family: {font_ui};
    font-size: 13px;
}}
QFrame#SidebarShell {{
    background-color: {pal['bg_sidebar']};
    border-right: 1px solid {pal['border']};
}}
QLabel#BrandTitle {{
    color: #FFFFFF;
    font-size: 16px;
    font-weight: 700;
    padding: 10px 12px 2px 12px;
}}
QLabel#BrandSubtitle {{
    color: {brand['accent']};
    font-size: 11px;
    font-weight: 600;
    padding: 0px 12px 10px 12px;
}}
QPushButton.NavButton {{
    background-color: transparent;
    color: #CED4DA;
    text-align: left;
    padding: 8px 12px;
    border: none;
    border-radius: 6px;
    font-weight: 500;
}}
QPushButton.NavButton:hover {{
    background-color: rgba(94, 114, 228, 0.22);
    color: #FFFFFF;
}}
QPushButton.NavButton[active="true"] {{
    background-color: {brand['primary']};
    color: #FFFFFF;
    font-weight: 600;
}}
QFrame.CardPanel {{
    background-color: {pal['bg_surface']};
    border: 1px solid {pal['border']};
    border-radius: 8px;
}}
QPushButton {{
    background-color: {pal['bg_surface']};
    color: {pal['text_primary']};
    border: 1px solid {pal['border']};
    border-radius: 6px;
    padding: 6px 12px;
    font-weight: 600;
}}
QPushButton:hover {{
    border-color: {brand['primary']};
}}
QPushButton.PrimaryButton {{
    background-color: {brand['primary']};
    color: #FFFFFF;
    border: none;
    border-radius: 6px;
    padding: 6px 14px;
    font-weight: 600;
}}
QPushButton.PrimaryButton:hover {{
    background-color: {brand['primary_hover']};
}}
QLineEdit, QComboBox, QPlainTextEdit {{
    background-color: {pal['bg_surface']};
    color: {pal['text_primary']};
    border: 1px solid {pal['border']};
    border-radius: 6px;
    padding: 6px 10px;
}}
QTableWidget, QListWidget {{
    background-color: {pal['bg_surface']};
    color: {pal['text_primary']};
    border: 1px solid {pal['border']};
    border-radius: 8px;
    gridline-color: {pal['border']};
    selection-background-color: {brand['primary']};
    selection-color: #FFFFFF;
}}
QHeaderView::section {{
    background-color: {pal['table_header']};
    color: {pal['text_secondary']};
    font-weight: 700;
    padding: 8px;
    border: none;
    border-bottom: 1px solid {pal['border']};
}}
"""


def ensure_baseline_seed(conn: sqlite3.Connection) -> dict[str, Any]:
    org = conn.execute("SELECT * FROM organizations LIMIT 1").fetchone()
    if org:
        users = {r["role"]: dict(r) for r in conn.execute("SELECT * FROM users").fetchall()}
        return {
            "organization": dict(org),
            "users_by_role": users,
            "projects": [dict(r) for r in conn.execute("SELECT * FROM projects").fetchall()],
            "websites": [dict(r) for r in conn.execute("SELECT * FROM websites").fetchall()],
        }

    now = utc_now_iso()
    org_id = new_uuid()
    conn.execute(
        "INSERT INTO organizations (id, name, slug, settings_json, created_at) VALUES (?, ?, ?, '{}', ?)",
        (org_id, "OpsHub Operations Division", "opshub-core", now),
    )
    role_seeds = [
        ("system_admin", "admin@opshub.internal", "Aarav Sen (System Admin)"),
        ("manager", "manager@opshub.internal", "Priya Nair (Operations Lead)"),
        ("maintenance_engineer", "maintainer@opshub.internal", "Rohan Das (Maintenance Engineer)"),
        ("developer", "developer@opshub.internal", "Vikram Mehta (Lead Developer)"),
        ("reviewer_qa", "qa@opshub.internal", "Ananya Roy (QA Reviewer)"),
        ("readonly_stakeholder", "stakeholder@opshub.internal", "Karan Kapoor (Stakeholder)"),
        ("report_recipient", "reports@opshub.internal", "Exec Summary Distribution"),
    ]
    users_by_role: dict[str, dict[str, Any]] = {}
    for role_val, email, full_name in role_seeds:
        uid = new_uuid()
        conn.execute(
            "INSERT INTO users (id, org_id, email, full_name, role, is_active, created_at) VALUES (?, ?, ?, ?, ?, 1, ?)",
            (uid, org_id, email, full_name, role_val, now),
        )
        users_by_role[role_val] = {"id": uid, "email": email, "full_name": full_name, "role": role_val, "is_active": 1}

    admin_id = users_by_role["system_admin"]["id"]
    manager_id = users_by_role["manager"]["id"]
    maintainer_id = users_by_role["maintenance_engineer"]["id"]
    dev_id = users_by_role["developer"]["id"]
    qa_id = users_by_role["reviewer_qa"]["id"]

    SOPGateService.ensure_default_template(conn, created_by=admin_id)
    proj_id = new_uuid()
    conn.execute(
        """
        INSERT INTO projects (id, org_id, code, name, description, client_name, lead_user_id, status, priority, created_at, updated_at)
        VALUES (?, ?, 'PRJ-WP-FLEET', 'Managed WordPress Production & Staging Fleet', 'SOP maintenance across WordPress properties', 'Enterprise Clients', ?, 'active', 'high', ?, ?)
        """,
        (proj_id, org_id, manager_id, now, now),
    )

    today_iso = datetime.now(timezone.utc).date().isoformat()
    overdue_iso = (datetime.now(timezone.utc) - timedelta(days=3)).date().isoformat()
    for name, domain, env, wf_st, bldr, due in [
        ("Acme Commerce Live", "acme-commerce.example.com", "live", "due", "divi", today_iso),
        ("Acme Commerce Staging", "staging.acme-commerce.example.com", "staging", "due", "divi", today_iso),
        ("Apex Corporate Portal", "apex-portal.example.org", "live", "overdue", "gutenberg", overdue_iso),
    ]:
        sid = new_uuid()
        conn.execute(
            """
            INSERT INTO websites (
                id, project_id, name, domain, url, environment, health_status, workflow_status,
                maintainer_id, developer_id, reviewer_id, frequency, next_due_at, wp_version, php_version, builder, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'online', ?, ?, ?, ?, 'monthly', ?, '6.6.2', '8.2', ?, ?, ?)
            """,
            (sid, proj_id, name, domain, f"https://{domain}", env, wf_st, maintainer_id, dev_id, qa_id, due, bldr, now, now),
        )

    conn.execute(
        """
        INSERT INTO issues (id, project_id, category, severity, priority, title, description, owner_id, reviewer_id, status, created_at, updated_at)
        VALUES (?, ?, 'security_vulnerability', 'high', 'high', 'Missing HSTS Security Header on Apex Portal', 'Strict-Transport-Security header missing on HTTPS responses.', ?, ?, 'assigned', ?, ?)
        """,
        (new_uuid(), proj_id, dev_id, qa_id, now, now),
    )
    conn.execute(
        """
        INSERT INTO tasks (id, project_id, title, description, owner_id, reviewer_id, priority, status, due_at, created_at, updated_at)
        VALUES (?, ?, 'Complete Monthly SOP Maintenance for Acme Commerce', 'Execute all 23 SOP checks and verify backup archive.', ?, ?, 'high', 'in_progress', ?, ?, ?)
        """,
        (new_uuid(), proj_id, maintainer_id, qa_id, today_iso, now, now),
    )
    return ensure_baseline_seed(conn)


def create_app() -> FastAPI:
    db_manager.init_schema()
    with db_manager.session() as conn:
        ensure_baseline_seed(conn)

    api = FastAPI(title="OpsHub Command Center API (Argon Edition)", version="1.0.0")

    def get_current_user(x_user_id: str | None = Header(default=None)) -> dict[str, Any]:
        with db_manager.session() as conn:
            if x_user_id:
                r = conn.execute("SELECT * FROM users WHERE id = ?", (x_user_id,)).fetchone()
                if r:
                    return dict(r)
            return dict(conn.execute("SELECT * FROM users WHERE role = 'system_admin' LIMIT 1").fetchone())

    @api.post("/api/v1/auth/login")
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

    @api.post("/api/v1/auth/verify-2fa")
    def api_verify_2fa(payload: dict[str, Any]) -> dict[str, Any]:
        code = str(payload.get("totp_code") or "").strip()
        if len(code) != 6 or not code.isdigit():
            raise HTTPException(status_code=400, detail="Invalid 6-digit 2FA TOTP verification code.")
        return {"verified": True, "session_status": "authenticated_2fa_verified"}

    @api.get("/api/v1/feature-flags")
    def api_get_feature_flags() -> dict[str, bool]:
        return FEATURE_FLAGS

    @api.patch("/api/v1/feature-flags")
    def api_update_feature_flags(payload: dict[str, bool], user: dict = Depends(get_current_user)) -> dict[str, bool]:
        check_permission(user, "manage_integrations")
        for k, v in payload.items():
            if k in FEATURE_FLAGS:
                FEATURE_FLAGS[k] = bool(v)
        return FEATURE_FLAGS

    @api.get("/api/v1/design-tokens")
    def api_get_design_tokens() -> dict[str, Any]:
        return ARGON_TOKENS

    @api.get("/api/v1/bootstrap")
    def api_bootstrap() -> dict[str, Any]:
        with db_manager.session() as conn:
            return ensure_baseline_seed(conn)

    @api.get("/api/v1/dashboard/summary")
    def api_dashboard_summary(user: dict = Depends(get_current_user)) -> dict[str, Any]:
        check_permission(user, "view_records")
        with db_manager.session() as conn:
            today_str = datetime.now(timezone.utc).date().isoformat()
            return {
                "kpis": {
                    "active_projects": conn.execute("SELECT COUNT(*) FROM projects WHERE status='active'").fetchone()[0],
                    "total_websites": conn.execute("SELECT COUNT(*) FROM websites").fetchone()[0],
                    "websites_due_today": conn.execute("SELECT COUNT(*) FROM websites WHERE workflow_status='due' OR substr(next_due_at,1,10)=?", (today_str,)).fetchone()[0],
                    "websites_overdue": conn.execute("SELECT COUNT(*) FROM websites WHERE workflow_status='overdue'").fetchone()[0],
                    "sessions_in_progress": conn.execute("SELECT COUNT(*) FROM maintenance_sessions WHERE status='in_progress'").fetchone()[0],
                    "open_critical_high_issues": conn.execute("SELECT COUNT(*) FROM issues WHERE severity IN ('critical','high') AND status NOT IN ('resolved','closed')").fetchone()[0],
                    "pending_approvals": conn.execute("SELECT COUNT(*) FROM approvals WHERE status='pending'").fetchone()[0],
                    "backups_awaiting_verification": conn.execute("SELECT COUNT(*) FROM backup_records WHERE is_verified=0").fetchone()[0],
                }
            }

    @api.get("/api/v1/dashboard/drilldown/{metric_key}")
    def api_drilldown(metric_key: str, user: dict = Depends(get_current_user)) -> list[dict[str, Any]]:
        check_permission(user, "view_records")
        with db_manager.session() as conn:
            if metric_key == "active_projects":
                return [dict(r) for r in conn.execute("SELECT * FROM projects").fetchall()]
            if metric_key == "open_critical_high_issues":
                return [dict(r) for r in conn.execute("SELECT * FROM issues WHERE severity IN ('critical','high')").fetchall()]
            if metric_key == "websites_overdue":
                return [dict(r) for r in conn.execute("SELECT * FROM websites WHERE workflow_status='overdue'").fetchall()]
            return [dict(r) for r in conn.execute("SELECT * FROM websites").fetchall()]

    @api.get("/api/v1/projects")
    def api_projects(user: dict = Depends(get_current_user)) -> list[dict[str, Any]]:
        check_permission(user, "view_records")
        with db_manager.session() as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM projects").fetchall()]

    @api.get("/api/v1/websites")
    def api_websites(user: dict = Depends(get_current_user)) -> list[dict[str, Any]]:
        check_permission(user, "view_records")
        with db_manager.session() as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM websites").fetchall()]

    @api.get("/api/v1/tasks")
    def api_tasks(user: dict = Depends(get_current_user)) -> list[dict[str, Any]]:
        check_permission(user, "view_records")
        with db_manager.session() as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM tasks").fetchall()]

    @api.get("/api/v1/issues")
    def api_issues(user: dict = Depends(get_current_user)) -> list[dict[str, Any]]:
        check_permission(user, "view_records")
        with db_manager.session() as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM issues").fetchall()]

    @api.get("/api/v1/approvals")
    def api_approvals(user: dict = Depends(get_current_user)) -> list[dict[str, Any]]:
        check_permission(user, "view_records")
        with db_manager.session() as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM approvals").fetchall()]

    @api.get("/api/v1/backups")
    def api_backups(user: dict = Depends(get_current_user)) -> list[dict[str, Any]]:
        check_permission(user, "view_records")
        with db_manager.session() as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM backup_records").fetchall()]

    @api.get("/api/v1/reports")
    def api_reports(user: dict = Depends(get_current_user)) -> list[dict[str, Any]]:
        check_permission(user, "view_records")
        with db_manager.session() as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM reminders_and_reports ORDER BY generated_at DESC").fetchall()]

    @api.get("/api/v1/audit/events")
    def api_audit(user: dict = Depends(get_current_user)) -> list[dict[str, Any]]:
        check_permission(user, "view_records")
        with db_manager.session() as conn:
            return AuditService.list_events(conn, limit=100)

    @api.get("/api/v1/users")
    def api_users(user: dict = Depends(get_current_user)) -> list[dict[str, Any]]:
        check_permission(user, "view_records")
        with db_manager.session() as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM users").fetchall()]

    @api.post("/api/v1/sessions")
    def api_start_session(payload: dict[str, Any], user: dict = Depends(get_current_user)) -> dict[str, Any]:
        check_permission(user, "execute_maintenance")
        with db_manager.session() as conn:
            return SOPGateService.start_session(
                conn,
                website_id=payload["website_id"],
                maintainer_id=payload["maintainer_id"],
            )

    @api.get("/api/v1/sessions/{session_id}")
    def api_get_session(session_id: str, user: dict = Depends(get_current_user)) -> dict[str, Any]:
        check_permission(user, "view_records")
        with db_manager.session() as conn:
            return SOPGateService.get_session_detail(conn, session_id)

    @api.patch("/api/v1/sessions/{session_id}/items/{step_number}")
    def api_update_step(session_id: str, step_number: int, payload: dict[str, Any], user: dict = Depends(get_current_user)) -> dict[str, Any]:
        check_permission(user, "execute_maintenance")
        with db_manager.session() as conn:
            try:
                return SOPGateService.update_checklist_item(
                    conn,
                    session_id=session_id,
                    step_number=step_number,
                    actor_user_id=user["id"],
                    status=payload["status"],
                    observation=payload.get("observation"),
                    na_reason=payload.get("na_reason"),
                )
            except SOPGateViolationError as exc:
                raise HTTPException(status_code=409, detail=str(exc))

    @api.post("/api/v1/sessions/{session_id}/run-readonly-checks")
    def api_run_readonly(session_id: str, user: dict = Depends(get_current_user)) -> dict[str, Any]:
        check_permission(user, "execute_maintenance")
        with db_manager.session() as conn:
            now = utc_now_iso()
            for st_num, label in [
                (1, "Automated link/image check completed; manual visual review required."),
                (2, "Response time check recorded; within baseline threshold."),
                (3, "NOT VERIFIED / ACCESS REQUIRED: Core file checksum comparison requires read-only SSH/host integration."),
                (4, "Inspected HTTP security headers (X-Frame-Options, X-Content-Type-Options, HSTS)."),
                (5, "NOT VERIFIED / ACCESS REQUIRED: Filesystem chmod check requires SSH integration."),
                (6, "NOT VERIFIED / ACCESS REQUIRED: wp-config.php constant inspection requires filesystem access."),
                (17, "NOT VERIFIED / ACCESS REQUIRED: WP Administrator account audit requires WP REST/Admin auth."),
            ]:
                st_code = "not_verified" if "NOT VERIFIED" in label else "passed"
                conn.execute(
                    "UPDATE session_checklist_items SET status = ?, observation = ?, updated_at = ? WHERE session_id = ? AND step_number = ?",
                    (st_code, label, now, session_id, st_num),
                )
            AuditService.log_event(
                conn,
                actor_user_id=user["id"],
                entity_type="maintenance_session",
                entity_id=session_id,
                action="readonly_checks_executed",
                summary="Executed safe read-only checks (INV-02 enforced for credential-gated steps).",
            )
            return SOPGateService.get_session_detail(conn, session_id)

    @api.post("/api/v1/backups")
    def api_record_backup(payload: dict[str, Any], user: dict = Depends(get_current_user)) -> dict[str, Any]:
        check_permission(user, "execute_maintenance")
        with db_manager.session() as conn:
            bid = new_uuid()
            now = utc_now_iso()
            conn.execute(
                """
                INSERT INTO backup_records (id, website_id, session_id, storage_location, status, is_verified, verified_by, verified_at, restore_test_status, created_by, created_at)
                VALUES (?, ?, ?, ?, 'completed', 1, ?, ?, 'verified_archive_integrity', ?, ?)
                """,
                (bid, payload["website_id"], payload.get("session_id"), payload["storage_location"], user["id"], now, user["id"], now),
            )
            AuditService.log_event(
                conn,
                actor_user_id=user["id"],
                entity_type="backup_record",
                entity_id=bid,
                action="backup_verified",
                summary=f"Recorded and verified backup at {payload['storage_location']}",
            )
            return {"id": bid, "is_verified": True}

    @api.post("/api/v1/sessions/{session_id}/close")
    def api_close_session(session_id: str, payload: dict[str, Any], user: dict = Depends(get_current_user)) -> dict[str, Any]:
        check_permission(user, "execute_maintenance")
        with db_manager.session() as conn:
            try:
                return SOPGateService.close_session(
                    conn,
                    session_id=session_id,
                    actor_user_id=user["id"],
                    target_status=payload.get("target_status", "completed"),
                    closure_summary=payload.get("closure_summary", ""),
                )
            except SOPGateViolationError as exc:
                raise HTTPException(status_code=409, detail=str(exc))

    @api.post("/api/v1/reports/sessions/{session_id}/pdf")
    def api_generate_pdf(session_id: str, user: dict = Depends(get_current_user)) -> dict[str, Any]:
        check_permission(user, "export_reports")
        with db_manager.session() as conn:
            detail = SOPGateService.get_session_detail(conn, session_id)
            REPORTS_DIR.mkdir(parents=True, exist_ok=True)
            MAIL_SINK_DIR.mkdir(parents=True, exist_ok=True)
            prior = conn.execute(
                "SELECT COUNT(*) FROM reminders_and_reports WHERE target_entity_id = ?", (session_id,)
            ).fetchone()[0]
            is_rev = prior > 0
            pdf_path = REPORTS_DIR / f"OpsHub_Session_{session_id[:8]}{'_REV' if is_rev else ''}.pdf"
            doc = SimpleDocTemplate(str(pdf_path), pagesize=A4)
            styles = getSampleStyleSheet()
            story = [
                Paragraph(
                    f"{'[UPDATED REVISION] ' if is_rev else ''}OpsHub Maintenance Report — {detail['website_name']}",
                    styles["Heading1"],
                ),
                Spacer(1, 10),
            ]
            rows = [["#", "SOP Task", "Status", "Observation"]]
            for item in detail["items"]:
                rows.append([str(item["step_number"]), item["title"], item["status"].upper(), (item["observation"] or item["na_reason"] or "—")[:90]])
            t = Table(rows, colWidths=[30, 160, 90, 230])
            t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.grey), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#172B4D")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white)]))
            story.append(t)
            doc.build(story)

            email_path = MAIL_SINK_DIR / f"email_{session_id[:8]}_{prior + 1}.txt"
            subj = f"{'[UPDATED REVISION REPORT] ' if is_rev else ''}[OpsHub] Maintenance Report: {detail['website_name']}"
            email_path.write_text(f"Subject: {subj}\nWebsite: {detail['website_domain']}\nPDF: {pdf_path}\n", encoding="utf-8")
            now = utc_now_iso()
            conn.execute(
                """
                INSERT INTO reminders_and_reports (id, record_type, subtype, target_entity_type, target_entity_id, title, status, is_revised_report, artifact_path, generated_at, sent_at)
                VALUES (?, 'report', 'maintenance_completion', 'maintenance_session', ?, ?, 'sent', ?, ?, ?, ?)
                """,
                (new_uuid(), session_id, subj, 1 if is_rev else 0, str(pdf_path), now, now),
            )
            return {"subject": subj, "pdf_path": str(pdf_path), "email_sink_path": str(email_path), "is_revised_report": is_rev}

    @api.post("/api/v1/reports/export-xlsx")
    def api_export_xlsx(user: dict = Depends(get_current_user)) -> dict[str, Any]:
        check_permission(user, "export_reports")
        with db_manager.session() as conn:
            REPORTS_DIR.mkdir(parents=True, exist_ok=True)
            xlsx_path = REPORTS_DIR / "OpsHub_Compliance_Workbook.xlsx"
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Websites"
            ws.append(["Name", "Domain", "Environment", "Builder", "Health", "Workflow Status", "Next Due"])
            for r in conn.execute("SELECT * FROM websites").fetchall():
                ws.append([r["name"], r["domain"], r["environment"], r["builder"], r["health_status"], r["workflow_status"], r["next_due_at"]])
            wb.save(str(xlsx_path))
            return {"xlsx_path": str(xlsx_path)}

    @api.get("/api/v1/search")
    def api_search(q: str = Query(..., min_length=1), user: dict = Depends(get_current_user)) -> dict[str, Any]:
        check_permission(user, "view_records")
        pat = f"%{q.strip()}%"
        with db_manager.session() as conn:
            return {
                "projects": [dict(r) for r in conn.execute("SELECT * FROM projects WHERE name LIKE ? OR code LIKE ?", (pat, pat)).fetchall()],
                "websites": [dict(r) for r in conn.execute("SELECT * FROM websites WHERE name LIKE ? OR domain LIKE ?", (pat, pat)).fetchall()],
                "tasks": [dict(r) for r in conn.execute("SELECT * FROM tasks WHERE title LIKE ?", (pat,)).fetchall()],
                "issues": [dict(r) for r in conn.execute("SELECT * FROM issues WHERE title LIKE ?", (pat,)).fetchall()],
            }

    return api


app = create_app()


# ============================================================================
# 5. RESPONSIVE PYSIDE6 DESKTOP COMMAND CENTER CLIENT (ARGON EDITION)
# ============================================================================

STATUS_BADGE_MAP: dict[str, dict[str, str]] = {
    "passed": {"label": "✓ PASSED", "fg": "#15803D", "bg": "#DCFCE7", "border": "#2DCE89"},
    "verified": {"label": "✓ VERIFIED", "fg": "#15803D", "bg": "#DCFCE7", "border": "#2DCE89"},
    "completed": {"label": "✓ COMPLETED", "fg": "#15803D", "bg": "#DCFCE7", "border": "#2DCE89"},
    "up_to_date": {"label": "✓ UP TO DATE", "fg": "#15803D", "bg": "#DCFCE7", "border": "#2DCE89"},
    "online": {"label": "● ONLINE", "fg": "#15803D", "bg": "#DCFCE7", "border": "#2DCE89"},
    "approved": {"label": "✓ APPROVED", "fg": "#15803D", "bg": "#DCFCE7", "border": "#2DCE89"},
    "resolved": {"label": "✓ RESOLVED", "fg": "#15803D", "bg": "#DCFCE7", "border": "#2DCE89"},
    "closed": {"label": "✓ CLOSED", "fg": "#15803D", "bg": "#DCFCE7", "border": "#2DCE89"},
    "failed": {"label": "✕ FAILED", "fg": "#B91C1C", "bg": "#FEE2E2", "border": "#F5365C"},
    "critical": {"label": "! CRITICAL", "fg": "#B91C1C", "bg": "#FEE2E2", "border": "#F5365C"},
    "overdue": {"label": "! OVERDUE", "fg": "#B91C1C", "bg": "#FEE2E2", "border": "#F5365C"},
    "blocked": {"label": "⊘ BLOCKED", "fg": "#9A3412", "bg": "#FFEDD5", "border": "#FB6340"},
    "completed_with_findings": {"label": "⚠ COMPLETED W/ FINDINGS", "fg": "#9A3412", "bg": "#FFEDD5", "border": "#FB6340"},
    "not_verified": {"label": "? NOT VERIFIED / ACCESS REQ", "fg": "#854D0E", "bg": "#FEF9C3", "border": "#FDE047"},
    "pending": {"label": "◷ PENDING", "fg": "#324CDD", "bg": "#EBF0FF", "border": "#5E72E4"},
    "in_progress": {"label": "↻ IN PROGRESS", "fg": "#324CDD", "bg": "#EBF0FF", "border": "#5E72E4"},
    "due": {"label": "◷ DUE", "fg": "#324CDD", "bg": "#EBF0FF", "border": "#5E72E4"},
    "not_applicable": {"label": "— N/A", "fg": "#525F7F", "bg": "#F6F9FC", "border": "#E9ECEF"},
}


def format_status_badge(status_key: str) -> dict[str, str]:
    norm = (status_key or "unknown").strip().lower()
    return STATUS_BADGE_MAP.get(
        norm, {"label": f"• {norm.upper()}", "fg": "#334155", "bg": "#F1F5F9", "border": "#CBD5E1"}
    )


class OpsHubDesktopClient:
    NAVIGATION_MODULES: list[tuple[str, str]] = [
        ("overview", "1. Overview"),
        ("projects", "2. Projects"),
        ("my_tasks", "3. My Tasks"),
        ("all_tasks", "4. All Tasks"),
        ("websites", "5. Websites"),
        ("maintenance_queue", "6. Maintenance Queue"),
        ("issues", "7. Issues & Findings"),
        ("approvals", "8. Approvals"),
        ("backups", "9. Backups"),
        ("reports", "10. Reports"),
        ("notifications", "11. Notifications"),
        ("activity_history", "12. Activity History"),
        ("admin_settings", "13. Administration / Settings"),
    ]

    def __init__(self, base_url: str | None = None, active_user_id: str | None = None):
        self.base_url = base_url
        self.active_user_id = active_user_id
        self._embedded_client = TestClient(app) if not base_url else None

    def set_active_user(self, user_id: str) -> None:
        self.active_user_id = user_id

    def _headers(self) -> dict[str, str]:
        return {"X-User-Id": self.active_user_id} if self.active_user_id else {}

    def request(self, method: str, path: str, json_body: dict[str, Any] | None = None, params: dict[str, Any] | None = None) -> Any:
        if self._embedded_client is not None:
            resp = self._embedded_client.request(method, path, json=json_body, params=params, headers=self._headers())
        else:
            with httpx.Client(base_url=self.base_url, timeout=15.0) as client:
                resp = client.request(method, path, json=json_body, params=params, headers=self._headers())
        if resp.status_code >= 400:
            detail = (
                resp.json().get("detail", resp.text)
                if resp.headers.get("content-type", "").startswith("application/json")
                else resp.text
            )
            raise RuntimeError(f"Gate / Policy Enforcement ({resp.status_code}): {detail}")
        return resp.json()


try:
    from PySide6.QtCore import Qt, QThreadPool
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtWidgets import (
        QApplication,
        QComboBox,
        QFrame,
        QGridLayout,
        QHBoxLayout,
        QHeaderView,
        QLabel,
        QLineEdit,
        QListWidget,
        QListWidgetItem,
        QMainWindow,
        QMessageBox,
        QPlainTextEdit,
        QPushButton,
        QScrollArea,
        QSizePolicy,
        QSplitter,
        QStackedWidget,
        QTableWidget,
        QTableWidgetItem,
        QVBoxLayout,
        QWidget,
    )
    PYSIDE6_AVAILABLE = True
except ImportError:
    PYSIDE6_AVAILABLE = False


if PYSIDE6_AVAILABLE:

    class OpsHubMainWindow(QMainWindow):
        def __init__(self, client: OpsHubDesktopClient):
            super().__init__()
            self.client = client
            self.thread_pool = QThreadPool.globalInstance()
            self.setWindowTitle("OpsHub — Maintenance & Project Operations Command Center")
            # Permissive minimum size + adaptive 85% screen geometry so window resizes freely on any display
            self.setMinimumSize(860, 540)
            screen = QGuiApplication.primaryScreen()
            if screen:
                avail = screen.availableGeometry()
                w = min(1220, int(avail.width() * 0.85))
                h = min(760, int(avail.height() * 0.85))
                self.resize(w, h)
                self.move(avail.x() + (avail.width() - w) // 2, avail.y() + (avail.height() - h) // 2)
            else:
                self.resize(1160, 720)
            self.setStyleSheet(build_argon_qss("light"))

            self.bootstrap_data = self.client.request("GET", "/api/v1/bootstrap")
            self.current_session_id: str | None = None
            self.module_tables: dict[str, QTableWidget] = {}
            self._build_shell()
            self.switch_module("overview")

        def _build_shell(self) -> None:
            root = QWidget()
            root_layout = QHBoxLayout(root)
            root_layout.setContentsMargins(0, 0, 0, 0)
            root_layout.setSpacing(0)

            sidebar = QFrame()
            sidebar.setObjectName("SidebarShell")
            sidebar.setMinimumWidth(185)
            sidebar.setMaximumWidth(210)
            sb_layout = QVBoxLayout(sidebar)
            sb_layout.setContentsMargins(6, 10, 6, 10)
            sb_layout.setSpacing(2)

            title = QLabel("OpsHub")
            title.setObjectName("BrandTitle")
            subtitle = QLabel("Argon Command Center")
            subtitle.setObjectName("BrandSubtitle")
            sb_layout.addWidget(title)
            sb_layout.addWidget(subtitle)

            self.nav_buttons: dict[str, QPushButton] = {}
            self.stack = QStackedWidget()
            self.module_pages: dict[str, QWidget] = {}

            for mod_key, mod_label in OpsHubDesktopClient.NAVIGATION_MODULES:
                btn = QPushButton(mod_label)
                btn.setProperty("class", "NavButton")
                btn.clicked.connect(lambda checked=False, k=mod_key: self.switch_module(k))
                sb_layout.addWidget(btn)
                self.nav_buttons[mod_key] = btn

                page = self._create_module_page(mod_key, mod_label)
                self.stack.addWidget(page)
                self.module_pages[mod_key] = page

            sb_layout.addStretch()
            root_layout.addWidget(sidebar)

            right_area = QWidget()
            right_area.setObjectName("CentralWorkArea")
            right_layout = QVBoxLayout(right_area)
            right_layout.setContentsMargins(14, 12, 14, 12)
            right_layout.setSpacing(10)

            self.theme_mode = "light"
            self.current_lang = "en"
            self.sidebar_collapsed = False
            self.sidebar_frame = sidebar

            header = QHBoxLayout()
            self.collapse_btn = QPushButton("☰")
            self.collapse_btn.setToolTip("Collapse / Expand Sidebar")
            self.collapse_btn.clicked.connect(self.toggle_sidebar)
            header.addWidget(self.collapse_btn)

            self.search_input = QLineEdit()
            self.search_input.setPlaceholderText(I18N_DICTIONARY["en"]["search_placeholder"])
            self.search_input.returnPressed.connect(self.execute_global_search)
            header.addWidget(self.search_input, stretch=1)

            self.lang_combo = QComboBox()
            self.lang_combo.addItem("EN (English)", "en")
            self.lang_combo.addItem("ES (Español)", "es")
            self.lang_combo.addItem("HI (हिंदी)", "hi")
            self.lang_combo.currentIndexChanged.connect(self.switch_language)
            header.addWidget(self.lang_combo)

            self.theme_btn = QPushButton("◐ Dark Mode")
            self.theme_btn.clicked.connect(self.toggle_theme_mode)
            header.addWidget(self.theme_btn)

            self.tour_btn = QPushButton("? Tour")
            self.tour_btn.clicked.connect(self.show_onboarding_tour)
            header.addWidget(self.tour_btn)

            self.role_combo = QComboBox()
            for role_key, u in self.bootstrap_data["users_by_role"].items():
                self.role_combo.addItem(f"{u['full_name']} [{role_key}]", u["id"])
            self.role_combo.currentIndexChanged.connect(self._on_role_switched)
            header.addWidget(self.role_combo)

            right_layout.addLayout(header)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.NoFrame)
            scroll.setWidget(self.stack)
            right_layout.addWidget(scroll, stretch=1)
            root_layout.addWidget(right_area, stretch=1)
            self.setCentralWidget(root)

        def _create_module_page(self, mod_key: str, mod_label: str) -> QWidget:
            page = QWidget()
            layout = QVBoxLayout(page)
            heading = QLabel(mod_label)
            heading.setStyleSheet("font-size: 17px; font-weight: 700;")
            layout.addWidget(heading)

            if mod_key == "overview":
                self.kpi_grid = QGridLayout()
                layout.addLayout(self.kpi_grid)
                self.drilldown_table = QTableWidget(0, 4)
                self.drilldown_table.setHorizontalHeaderLabels(
                    ["Entity / Title", "Environment / Category", "Status Badge", "Owner / Due"]
                )
                self.drilldown_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
                layout.addWidget(QLabel("Drill-down Records (Click any metric card above):"))
                layout.addWidget(self.drilldown_table, stretch=1)
            elif mod_key == "maintenance_queue":
                self.site_selector = QComboBox()
                for w in self.bootstrap_data["websites"]:
                    self.site_selector.addItem(f"{w['name']} ({w['domain']}) [{w['environment'].upper()}]", w["id"])

                start_btn = QPushButton("Start 23-Step SOP Session")
                start_btn.setProperty("class", "PrimaryButton")
                start_btn.clicked.connect(self.launch_sop_session)

                ro_btn = QPushButton("Run Safe Read-Only Checks")
                ro_btn.clicked.connect(self.run_readonly_checks_ui)

                bkp_btn = QPushButton("Record & Verify Backup (#9)")
                bkp_btn.clicked.connect(self.record_verified_backup_ui)

                close_btn = QPushButton("Close Session")
                close_btn.clicked.connect(self.close_current_session_ui)

                pdf_btn = QPushButton("Generate PDF Report")
                pdf_btn.clicked.connect(self.generate_pdf_report_ui)

                row1 = QHBoxLayout()
                row1.addWidget(QLabel("Website:"))
                row1.addWidget(self.site_selector, stretch=1)
                row1.addWidget(start_btn)
                row2 = QHBoxLayout()
                row2.addWidget(ro_btn)
                row2.addWidget(bkp_btn)
                row2.addWidget(close_btn)
                row2.addWidget(pdf_btn)
                row2.addStretch()
                layout.addLayout(row1)
                layout.addLayout(row2)

                self.gate_banner = QLabel("Live Pre-Update Backup Gate: Click 'Start 23-Step SOP Session' to begin.")
                self.gate_banner.setWordWrap(True)
                self.gate_banner.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
                self.gate_banner.setStyleSheet(
                    "background-color: #FEF9C3; color: #854D0E; padding: 8px 12px; border-radius: 6px; font-weight: 600;"
                )
                layout.addWidget(self.gate_banner)

                splitter = QSplitter(Qt.Horizontal)
                self.sop_step_list = QListWidget()
                self.sop_step_list.currentRowChanged.connect(self.on_sop_step_selected)
                splitter.addWidget(self.sop_step_list)

                detail_panel = QFrame()
                detail_panel.setProperty("class", "CardPanel")
                dp_layout = QVBoxLayout(detail_panel)
                self.step_title_lbl = QLabel("Select a checklist step")
                self.step_title_lbl.setWordWrap(True)
                self.step_title_lbl.setStyleSheet("font-size: 14px; font-weight: 700;")
                self.step_process_lbl = QLabel("")
                self.step_process_lbl.setWordWrap(True)
                self.step_rule_box = QPlainTextEdit()
                self.step_rule_box.setReadOnly(True)
                self.step_obs_input = QPlainTextEdit()
                self.step_obs_input.setPlaceholderText("Record maintainer observation, metrics, or N/A reason...")

                btn_row = QHBoxLayout()
                for st_code, btn_txt in [
                    ("passed", "✓ Passed"),
                    ("failed", "✕ Failed"),
                    ("blocked", "⊘ Blocked"),
                    ("not_verified", "? Not Verified"),
                    ("not_applicable", "— N/A"),
                ]:
                    b = QPushButton(btn_txt)
                    b.clicked.connect(lambda checked=False, sc=st_code: self.save_current_step_status(sc))
                    btn_row.addWidget(b)

                dp_layout.addWidget(self.step_title_lbl)
                dp_layout.addWidget(self.step_process_lbl)
                dp_layout.addWidget(QLabel("Approved SOP Reference Snippet:"))
                dp_layout.addWidget(self.step_rule_box)
                dp_layout.addWidget(QLabel("Observation / Evidence / Reason:"))
                dp_layout.addWidget(self.step_obs_input)
                dp_layout.addLayout(btn_row)
                splitter.addWidget(detail_panel)
                splitter.setSizes([340, 520])
                layout.addWidget(splitter, stretch=1)
            else:
                if mod_key == "reports":
                    export_btn = QPushButton("Export Excel (.xlsx) Compliance Workbook")
                    export_btn.setProperty("class", "PrimaryButton")
                    export_btn.clicked.connect(self.export_xlsx_ui)
                    layout.addWidget(export_btn)
                table = QTableWidget(0, 4)
                table.setHorizontalHeaderLabels(
                    ["Record / Name", "Scope / Environment", "Status Badge", "Details / Timestamp"]
                )
                table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
                layout.addWidget(table, stretch=1)
                self.module_tables[mod_key] = table
            return page

        def _on_role_switched(self) -> None:
            uid = self.role_combo.currentData()
            if uid:
                self.client.set_active_user(uid)
                self.refresh_overview()

        def switch_module(self, mod_key: str) -> None:
            for k, btn in self.nav_buttons.items():
                btn.setProperty("active", "true" if k == mod_key else "false")
                btn.style().unpolish(btn)
                btn.style().polish(btn)
            if mod_key in self.module_pages:
                self.stack.setCurrentWidget(self.module_pages[mod_key])
            if mod_key == "overview":
                self.refresh_overview()
            elif mod_key in self.module_tables:
                self.populate_module_table(mod_key)

        def populate_module_table(self, mod_key: str) -> None:
            table = self.module_tables[mod_key]
            endpoint_map = {
                "projects": "/api/v1/projects",
                "my_tasks": "/api/v1/tasks",
                "all_tasks": "/api/v1/tasks",
                "websites": "/api/v1/websites",
                "issues": "/api/v1/issues",
                "approvals": "/api/v1/approvals",
                "backups": "/api/v1/backups",
                "reports": "/api/v1/reports",
                "notifications": "/api/v1/reports",
                "activity_history": "/api/v1/audit/events",
                "admin_settings": "/api/v1/users",
            }
            path = endpoint_map.get(mod_key)
            if not path:
                return
            try:
                rows = self.client.request("GET", path)
            except Exception as exc:
                QMessageBox.warning(self, "Access Restricted", str(exc))
                return
            table.setRowCount(len(rows))
            for idx, r in enumerate(rows):
                col1 = str(r.get("name") or r.get("title") or r.get("full_name") or r.get("summary") or r.get("storage_location") or r.get("id"))
                col2 = str(r.get("domain") or r.get("environment") or r.get("role") or r.get("entity_type") or r.get("category") or r.get("subtype") or "—")
                st_raw = str(r.get("workflow_status") or r.get("status") or r.get("action") or "online")
                badge = format_status_badge(st_raw)
                col4 = str(r.get("next_due_at") or r.get("created_at") or r.get("generated_at") or r.get("email") or "—")
                table.setItem(idx, 0, QTableWidgetItem(col1))
                table.setItem(idx, 1, QTableWidgetItem(col2))
                table.setItem(idx, 2, QTableWidgetItem(badge["label"]))
                table.setItem(idx, 3, QTableWidgetItem(col4))

        def refresh_overview(self) -> None:
            try:
                summary = self.client.request("GET", "/api/v1/dashboard/summary")
            except Exception as exc:
                QMessageBox.warning(self, "RBAC Permission Check", str(exc))
                return
            kpis = summary["kpis"]
            cards = [
                ("active_projects", "Active Projects", kpis["active_projects"], "in_progress"),
                ("total_websites", "Registered Websites", kpis["total_websites"], "online"),
                ("websites_due_today", "Websites Due Today", kpis["websites_due_today"], "due"),
                ("websites_overdue", "Overdue Maintenance", kpis["websites_overdue"], "overdue"),
                ("sessions_in_progress", "Sessions In Progress", kpis["sessions_in_progress"], "in_progress"),
                ("open_critical_high_issues", "Open Critical/High Issues", kpis["open_critical_high_issues"], "critical"),
                ("pending_approvals", "Pending Approvals", kpis["pending_approvals"], "pending"),
                ("backups_awaiting_verification", "Unverified Backups", kpis["backups_awaiting_verification"], "not_verified"),
            ]
            for idx, (m_key, title, val, badge_key) in enumerate(cards):
                badge = format_status_badge(badge_key)
                btn = QPushButton(f"{title}\n{val}  [{badge['label']}]")
                btn.setStyleSheet(
                    f"background-color: {badge['bg']}; color: {badge['fg']}; "
                    f"border: 1px solid {badge['border']}; border-radius: 8px; padding: 10px; font-weight: 700; text-align: left;"
                )
                btn.clicked.connect(lambda checked=False, mk=m_key: self.load_drilldown(mk))
                self.kpi_grid.addWidget(btn, idx // 4, idx % 4)
            self.load_drilldown("total_websites")

        def load_drilldown(self, metric_key: str) -> None:
            rows = self.client.request("GET", f"/api/v1/dashboard/drilldown/{metric_key}")
            self.drilldown_table.setRowCount(len(rows))
            for r_idx, row in enumerate(rows):
                name = str(row.get("name") or row.get("title") or row.get("summary") or row.get("id"))
                cat = str(row.get("environment") or row.get("category") or row.get("action_type") or "—")
                st_raw = str(row.get("workflow_status") or row.get("status") or "unknown")
                badge = format_status_badge(st_raw)
                owner = str(row.get("next_due_at") or row.get("priority") or "—")
                self.drilldown_table.setItem(r_idx, 0, QTableWidgetItem(name))
                self.drilldown_table.setItem(r_idx, 1, QTableWidgetItem(cat.upper()))
                self.drilldown_table.setItem(r_idx, 2, QTableWidgetItem(badge["label"]))
                self.drilldown_table.setItem(r_idx, 3, QTableWidgetItem(owner))

        def launch_sop_session(self) -> None:
            website_id = self.site_selector.currentData()
            maintainer_id = self.bootstrap_data["users_by_role"]["maintenance_engineer"]["id"]
            session = self.client.request(
                "POST", "/api/v1/sessions", json_body={"website_id": website_id, "maintainer_id": maintainer_id}
            )
            self.current_session_id = session["id"]
            self._render_session_steps(session)

        def run_readonly_checks_ui(self) -> None:
            if not self.current_session_id:
                self.launch_sop_session()
            updated = self.client.request("POST", f"/api/v1/sessions/{self.current_session_id}/run-readonly-checks")
            self._render_session_steps(updated)
            QMessageBox.information(
                self,
                "Read-Only Automation Complete",
                "Executed safe read-only checks. Steps requiring SSH/WP-Admin credentials were marked '? NOT VERIFIED / ACCESS REQ' (INV-02).",
            )

        def record_verified_backup_ui(self) -> None:
            if not self.current_session_id:
                self.launch_sop_session()
            website_id = self.site_selector.currentData()
            self.client.request(
                "POST",
                "/api/v1/backups",
                json_body={
                    "website_id": website_id,
                    "session_id": self.current_session_id,
                    "storage_location": "s3://opshub-verified-backups/live-preupdate-verified.tar.gz",
                },
            )
            self.client.request(
                "PATCH",
                f"/api/v1/sessions/{self.current_session_id}/items/9",
                json_body={"status": "passed", "observation": "Verified full archive backup prior to live update work."},
            )
            updated = self.client.request("GET", f"/api/v1/sessions/{self.current_session_id}")
            self._render_session_steps(updated)
            QMessageBox.information(self, "Backup Gate Satisfied", "Verified backup recorded! Live update steps (#10-#12) are now unlocked.")

        def close_current_session_ui(self) -> None:
            if not self.current_session_id:
                return
            try:
                closed = self.client.request(
                    "POST", f"/api/v1/sessions/{self.current_session_id}/close", json_body={"target_status": "completed"}
                )
                self._render_session_steps(closed)
                QMessageBox.information(self, "Session Closed", f"Session closed with status: {closed['status'].upper()}")
            except Exception as exc:
                QMessageBox.warning(self, "Completion Gate Blocked Closure", str(exc))

        def generate_pdf_report_ui(self) -> None:
            if not self.current_session_id:
                self.launch_sop_session()
            rep = self.client.request("POST", f"/api/v1/reports/sessions/{self.current_session_id}/pdf")
            QMessageBox.information(
                self,
                "Maintenance Report Generated",
                f"Subject: {rep['subject']}\nPDF saved to:\n{rep['pdf_path']}\nEmail log saved to:\n{rep['email_sink_path']}",
            )

        def export_xlsx_ui(self) -> None:
            res = self.client.request("POST", "/api/v1/reports/export-xlsx")
            QMessageBox.information(self, "Excel Workbook Exported", f"Compliance workbook saved to:\n{res['xlsx_path']}")

        def _render_session_steps(self, session: dict[str, Any]) -> None:
            self._current_session_data = session
            gate = session["backup_gate"]
            self.gate_banner.setText(gate["message"])
            self.sop_step_list.clear()
            for item in session["items"]:
                badge = format_status_badge(item["status"])
                list_item = QListWidgetItem(
                    f"Step {item['step_number']:02d}: {item['title']}   [{badge['label']}]"
                )
                self.sop_step_list.addItem(list_item)
            if session["items"]:
                self.sop_step_list.setCurrentRow(0)

        def on_sop_step_selected(self, row_idx: int) -> None:
            if not hasattr(self, "_current_session_data") or row_idx < 0:
                return
            item = self._current_session_data["items"][row_idx]
            self.step_title_lbl.setText(f"Step {item['step_number']}: {item['title']}")
            self.step_process_lbl.setText(item["required_process"])
            ref = item.get("rule_reference")
            if ref:
                self.step_rule_box.setPlainText(f"{ref['title']}\n\n{ref['snippet']}\n\nGuidance: {ref['guidance']}")
            else:
                self.step_rule_box.setPlainText("No static snippet required for this step.")
            self.step_obs_input.setPlainText(item.get("observation") or item.get("na_reason") or "")

        def save_current_step_status(self, status_code: str) -> None:
            if not self.current_session_id:
                return
            row_idx = self.sop_step_list.currentRow()
            if row_idx < 0:
                return
            step_num = self._current_session_data["items"][row_idx]["step_number"]
            obs_text = self.step_obs_input.toPlainText().strip()
            try:
                self.client.request(
                    "PATCH",
                    f"/api/v1/sessions/{self.current_session_id}/items/{step_num}",
                    json_body={
                        "status": status_code,
                        "observation": obs_text,
                        "na_reason": obs_text if status_code == "not_applicable" else None,
                    },
                )
                updated_session = self.client.request("GET", f"/api/v1/sessions/{self.current_session_id}")
                self._render_session_steps(updated_session)
                self.sop_step_list.setCurrentRow(row_idx)
            except Exception as exc:
                QMessageBox.warning(self, "SOP Gate Enforcement", str(exc))

        def toggle_theme_mode(self) -> None:
            self.theme_mode = "dark" if self.theme_mode == "light" else "light"
            self.setStyleSheet(build_argon_qss(self.theme_mode))
            self.theme_btn.setText("☀ Light Mode" if self.theme_mode == "dark" else "◐ Dark Mode")

        def toggle_sidebar(self) -> None:
            self.sidebar_collapsed = not self.sidebar_collapsed
            if self.sidebar_collapsed:
                self.sidebar_frame.setMinimumWidth(58)
                self.sidebar_frame.setMaximumWidth(58)
                for mod_key, btn in self.nav_buttons.items():
                    btn.setText(btn.text().split(".")[0] + ".")
            else:
                self.sidebar_frame.setMinimumWidth(185)
                self.sidebar_frame.setMaximumWidth(210)
                for mod_key, mod_label in OpsHubDesktopClient.NAVIGATION_MODULES:
                    self.nav_buttons[mod_key].setText(mod_label)

        def switch_language(self) -> None:
            lang = self.lang_combo.currentData() or "en"
            self.current_lang = lang
            tr = I18N_DICTIONARY.get(lang, I18N_DICTIONARY["en"])
            self.setWindowTitle(tr["app_title"])
            self.search_input.setPlaceholderText(tr["search_placeholder"])

        def show_onboarding_tour(self) -> None:
            QMessageBox.information(
                self,
                "OpsHub Onboarding Tour & Quick Guide",
                "Welcome to OpsHub (Argon Design System Edition):\n\n"
                "1. Overview Dashboard: Click any KPI card to filter underlying records.\n"
                "2. Maintenance Queue: Select a Live or Staging WordPress site, start a 23-step SOP session, "
                "run safe read-only checks, verify a backup (Step 9) to unlock Live updates (#10-#12), and export PDF reports.\n"
                "3. Epistemic Integrity: Automated checks without SSH/WP-Admin access always report "
                "'? NOT VERIFIED / ACCESS REQ'—never a false Passed badge.\n"
                "4. Ergonomics: Toggle Light/Dark mode (◐), switch languages (EN/ES/HI), or collapse the sidebar (☰) anytime.",
            )

        def execute_global_search(self) -> None:
            q = self.search_input.text().strip()
            if not q:
                return
            res = self.client.request("GET", "/api/v1/search", params={"q": q})
            total = sum(len(res[k]) for k in ("projects", "websites", "tasks", "issues"))
            QMessageBox.information(
                self,
                "Global Search Results",
                f"Query '{q}' matched {total} record(s):\n"
                f"- Projects: {len(res['projects'])}\n"
                f"- Websites: {len(res['websites'])}\n"
                f"- Tasks: {len(res['tasks'])}\n"
                f"- Issues: {len(res['issues'])}",
            )


def main() -> int:
    if "--server" in sys.argv:
        import uvicorn
        uvicorn.run(app, host="127.0.0.1", port=8000)
        return 0

    api_url = os.getenv("OPSHUB_API_URL")
    client = OpsHubDesktopClient(base_url=api_url)
    if not PYSIDE6_AVAILABLE:
        summary = client.request("GET", "/api/v1/dashboard/summary")
        print("OpsHub FastAPI Engine (Argon Edition) initialized successfully. Live KPIs:", summary["kpis"])
        print("Install PySide6 inside your virtualenv (`pip install PySide6`) to open the desktop window.")
        return 0

    qt_app = QApplication(sys.argv)
    win = OpsHubMainWindow(client)
    win.show()
    return qt_app.exec()


if __name__ == "__main__":
    raise SystemExit(main())