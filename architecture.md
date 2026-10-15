# OpsHub System Architecture & Data Model Specification

**Document Version:** 1.0  
**Date:** 15 October 2026  
**Architecture Pattern:** Centralized FastAPI Service + Shared PostgreSQL Database + Asynchronous Scheduler/Worker + PySide6 Desktop Client  

## 1. Client-Server Topology Separates the Desktop UI from the System of Record

OpsHub uses a centralized multi-user architecture where the FastAPI backend and PostgreSQL database act as the single source of truth, and the PySide6 desktop application operates as an authenticated client. For local single-user prototyping or offline evaluation, the backend layer supports a configurable SQLite fallback through SQLAlchemy 2.x without changing service or UI code.

```text
+-------------------------------------------------------------------------+
|                     PySide6 Desktop Client (Qt Widgets)                 |
|  +-------------------+  +--------------------+  +--------------------+  |
|  | Views & Dialogs   |  | Background QThread |  | OS Keyring Token   |  |
|  | (13 Nav Modules)  |  | API Worker Pool    |  | & Session Store    |  |
|  +---------+---------+  +---------+----------+  +---------+----------+  |
+------------|----------------------|-----------------------|-------------+
             |                      | HTTPS / REST (JSON)   |
             v                      v                       v
+-------------------------------------------------------------------------+
|                        FastAPI Application Server                       |
|  +-------------------+  +--------------------+  +--------------------+  |
|  | Auth & RBAC       |  | Domain Services    |  | Report & Export    |  |
|  | Middleware        |  | (SOP, Gate, Issue) |  | Generators         |  |
|  +---------+---------+  +---------+----------+  +---------+----------+  |
+------------|----------------------|-----------------------|-------------+
             |                      |                       |
             v                      v                       v
+------------------------+  +------------------+  +-----------------------+
|  PostgreSQL Database   |  | APScheduler /    |  | Controlled Evidence   |
|  (SQLAlchemy 2.x +     |  | Background       |  | Storage & Secret      |
|   Alembic Migrations)  |  | Check Workers    |  | Manager               |
+------------------------+  +--------+---------+  +-----------------------+
                                     |
       +-----------------------------+-----------------------------+
       |                             |                             |
       v                             v                             v
+--------------+           +-------------------+         +------------------+
| SMTP / Email |           | Read-Only HTTPX / |         | Optional WP REST |
| Delivery     |           | TLS / BS4 Checks  |         | & Paramiko SSH   |
+--------------+           +-------------------+         +------------------+
```

## 2. Technology Stack Pins Proven Libraries by Architectural Layer

| Architectural Layer | Technology Choice | Responsibility & Architectural Rationale |
| :--- | :--- | :--- |
| **Desktop Client GUI** | `PySide6` (Qt6 Widgets) + `QSS` | Native cross-platform desktop ergonomics (Linux/Ubuntu & Windows), fast table rendering, non-blocking `QThreadPool` workers. |
| **Desktop Charts** | `PyQtGraph` | High-performance native Qt charts for operational metrics, issue aging, and compliance trends. |
| **Application Language** | `Python 3.12+` | Unified language across desktop client, FastAPI backend, automation workers, and test suites. |
| **Backend API Framework** | `FastAPI` + `Pydantic v2` + `Uvicorn` | Strict request/response validation, OpenAPI schema generation, dependency-injected RBAC permissions. |
| **Database & ORM** | `PostgreSQL 16+` (Prod) / `SQLite 3` (Dev) + `SQLAlchemy 2.x` + `Alembic` | Relational integrity, transactional audit logging, JSONB support for versioned SOP snapshots, repeatable schema migrations. |
| **Scheduler & Workers** | `APScheduler` + Async Worker Pool | Runs independently of desktop sessions to trigger maintenance queues, overdue escalations, email reports, and read-only scans. |
| **Read-Only Web Checks** | `HTTPX` + `BeautifulSoup4` + `ssl` | Asynchronous HTTP status, response timing, security header inspection, TLS certificate expiry, and broken link/image discovery. |
| **Browser Smoke Tests** | `Playwright` (Optional Phase 5 worker) | Headless browser verification of critical frontend flows (forms, checkout, login) without modifying production state. |
| **Remote Diagnostics** | `Paramiko` (Optional Phase 5 worker) | Strictly read-only SSH checks for file permissions and core checksums where explicitly authorized. |
| **Document Exports** | `ReportLab` (PDF), `openpyxl` (XLSX), `csv` | Generates tamper-evident PDF completion reports, Excel workbooks, and CSV audit exports. |
| **Secret Management** | `keyring` (Desktop) + Server Env/Vault | Keeps API tokens, SMTP credentials, and integration secrets out of databases, config files, and logs. |
| **Testing & Packaging** | `pytest`, `pytest-asyncio`, `PyInstaller` | Automated unit/integration coverage for workflow gates and single-folder/binary desktop packaging. |

## 3. Relational Data Model Enforces Versioned SOP Templates and Audit History

### Core Database Entities (16 Tables)

| Table Name | Primary Key | Key Columns & Foreign Keys | Domain Invariant / Constraint |
| :--- | :--- | :--- | :--- |
| `organizations` | `id (UUID)` | `name`, `slug`, `settings_json`, `created_at` | Root tenant boundary for teams, projects, and policies. |
| `users` | `id (UUID)` | `org_id`, `email`, `full_name`, `password_hash`, `is_active`, `notification_prefs_json` | Unique email; stores identity and notification preferences only. |
| `roles` & `user_roles` | `id (UUID)` | `user_id`, `role_name`, `project_id (nullable)`, `website_id (nullable)` | Supports global roles or project/website-scoped least privilege. |
| `projects` | `id (UUID)` | `org_id`, `code`, `name`, `client_name`, `lead_user_id`, `status`, `priority`, `start_date`, `target_date` | Groups both general tasks and linked WordPress websites. |
| `websites` | `id (UUID)` | `project_id`, `name`, `domain`, `environment` (`live`/`staging`/`dev`), `health_status`, `workflow_status`, `builder` (`divi`/`gutenberg`/`elementor`/`other`), `maintainer_id`, `developer_id`, `reviewer_id`, `wp_version`, `php_version`, `persistent_notes` | `health_status` (`online`/`degraded`/`down`/`unknown`) is strictly separate from `workflow_status` (`up_to_date`/`due`/`in_progress`/`overdue`/`blocked`). |
| `workflow_templates` | `id (UUID)` | `code`, `name`, `version (int)`, `is_active`, `tasks_schema_json`, `rules_reference_json`, `created_by` | Immutable once published; edits create a new `version` row. |
| `maintenance_schedules` | `id (UUID)` | `website_id`, `template_id`, `frequency` (`weekly`/`monthly`/`quarterly`/`custom`), `interval_days`, `anchor_policy` (`planned_date`/`completion_date`), `last_completed_at`, `next_due_at`, `assigned_owner_id` | Calculates `next_due_at` deterministically based on `anchor_policy`. |
| `maintenance_sessions` | `id (UUID)` | `website_id`, `schedule_id`, `template_id`, `template_version_snapshot_json`, `maintainer_id`, `reviewer_id`, `status`, `started_at`, `closed_at`, `closure_summary` | Stores a full JSON snapshot of the template version at session start so future SOP edits never alter historical records. |
| `session_checklist_items` | `id (UUID)` | `session_id`, `step_number (1..23)`, `code`, `title`, `is_conditional`, `is_applicable`, `status`, `owner_id`, `observation`, `action_taken`, `na_reason`, `verified_by`, `verified_at` | `status` enum: `pending`, `in_progress`, `passed`, `failed`, `blocked`, `not_applicable`, `not_verified`. |
| `tasks` | `id (UUID)` | `project_id`, `website_id (opt)`, `session_id (opt)`, `issue_id (opt)`, `title`, `description`, `owner_id`, `reviewer_id`, `priority`, `status`, `due_at`, `estimated_hours`, `actual_hours`, `acceptance_criteria` | General task engine supporting dependencies (`task_dependencies` join table) and work logs (`task_work_logs`). |
| `issues` | `id (UUID)` | `project_id`, `website_id (opt)`, `session_id (opt)`, `checklist_item_id (opt)`, `category`, `severity`, `priority`, `title`, `description`, `owner_id`, `reviewer_id`, `status`, `due_at`, `remediation_notes`, `verification_outcome`, `closure_reason` | Separates `severity` (`critical`..`informational`) from `priority` (`urgent`..`low`). Cannot close without verification or accepted risk. |
| `approvals` | `id (UUID)` | `project_id`, `website_id`, `session_id (opt)`, `checklist_item_id (opt)`, `action_type`, `summary`, `risk_notes`, `requester_id`, `approver_id`, `status`, `decision_rationale`, `decided_at`, `executed_at`, `verified_at` | Tracks `requested -> pending -> approved/rejected -> executed -> verified`. |
| `backup_records` | `id (UUID)` | `website_id`, `session_id (opt)`, `backup_type`, `storage_location`, `size_bytes`, `status`, `is_verified`, `restore_test_status`, `exception_approval_id (opt)`, `created_by`, `created_at` | Satisfies the Live Site Pre-Update Gate when `is_verified == True` or `exception_approval_id` is approved. |
| `evidences` | `id (UUID)` | `session_id (opt)`, `checklist_item_id (opt)`, `task_id (opt)`, `issue_id (opt)`, `evidence_type` (`file`/`check_json`/`url`/`note`), `storage_path`, `sha256_hash`, `captured_by`, `access_used`, `limitations`, `captured_at` | Stores automated scan outputs and uploaded screenshots outside public web roots. |
| `reminders_and_reports` | `id (UUID)` | `record_type` (`reminder`/`report`), `report_type`, `target_entity_id`, `recipients_json`, `status` (`queued`/`sent`/`failed`), `retry_count`, `error_message`, `generated_at`, `sent_at` | Tracks every scheduled notification and email report delivery attempt. |
| `activity_events` | `id (UUID)` | `actor_user_id`, `entity_type`, `entity_id`, `action`, `before_json`, `after_json`, `ip_address`, `created_at` | Append-only audit log; no `UPDATE` or `DELETE` permissions granted to application runtime. |

## 4. Service Layer Enforces SOP Gating and Safe Automation Boundaries

### Gating Engine (`backend/app/services/sop_gate_service.py`)

1. **Pre-Update Gate (Steps 10, 11, 12):**
   - When `website.environment == 'live'`, transitioning Step 10 (Core Updates), Step 11 (Theme Updates), or Step 12 (Plugin Updates) to `in_progress` or `passed` queries `backup_records` for the active `session_id`.
   - If no backup exists with `is_verified == True` AND no linked `Approval` record has `action_type == 'backup_exception'` and `status == 'approved'`, the service raises `PreUpdateGateError` (`HTTP 409 Conflict`).
2. **Approval Gate (Steps 3, 10, 11, 12, 16, 17, 19):**
   - Destructive or production-sensitive actions require a linked `Approval` record in `approved` state before the step can record execution.
3. **Session Closure Gate (`close_session`):**
   - Verifies all applicable required steps (1..23) are in a terminal state (`passed`, `failed`, `blocked`, `not_applicable`, or `not_verified`).
   - Enforces that Step 22 (`Final frontend check`) and Step 23 (`Review notes`) are `passed`.
   - Checks if Step 13 (`Post-update re-check`) failed; if so, requires a linked high-priority `Issue` and blocks normal `Completed` closure unless resolved or an exception is approved.

### Read-Only Automation Runner (`workers/checks/`)

Every automated check returns a standardized `CheckResultPayload`:
- `check_name`: Identifier of the check (`http_reachability`, `tls_expiry`, `security_headers`, `broken_links`, `robots_txt`).
- `outcome`: `passed`, `failed`, or `not_verified` (never defaults to `passed` on timeout, 401/403, or missing credentials).
- `access_used`: `public_http`, `wp_rest_readonly`, or `ssh_readonly`.
- `limitations`: Explicit human-readable note explaining what could not be checked (e.g., `"Inspected public HTTP response headers only; .htaccess directive structure requires filesystem read access"`).
- `raw_evidence`: Structured dictionary saved as an `Evidence` record and attached to the corresponding `SessionChecklistItem`.

## 5. REST API Contract Organizes Endpoints by Operational Domain

| API Prefix | Key Endpoints | Purpose |
| :--- | :--- | :--- |
| `/api/v1/auth` | `POST /login`, `POST /refresh`, `GET /me` | JWT authentication and current role/permission profile. |
| `/api/v1/dashboard` | `GET /summary`, `GET /drilldown/{metric_key}` | Live database counts and filtered record drill-downs for all 11 dashboard widgets. |
| `/api/v1/projects` | `GET /`, `POST /`, `GET /{id}`, `PATCH /{id}`, `GET /{id}/milestones` | Project register, team membership, and milestone tracking. |
| `/api/v1/websites` | `GET /`, `POST /`, `POST /import`, `GET /{id}`, `PATCH /{id}` | WordPress inventory CRUD and validated CSV/XLSX bulk import. |
| `/api/v1/templates` | `GET /`, `POST /`, `POST /{id}/publish-version`, `GET /rules-reference` | Versioned SOP templates and editable internal reference snippets. |
| `/api/v1/sessions` | `POST /`, `GET /queue`, `GET /{id}`, `PATCH /{id}/items/{step}`, `POST /{id}/close` | SOP session execution, step updates, gate validation, and closure. |
| `/api/v1/tasks` | `GET /`, `POST /`, `PATCH /{id}`, `POST /{id}/work-logs` | Cross-project task management, dependencies, and work logs. |
| `/api/v1/issues` | `GET /`, `POST /`, `PATCH /{id}/status`, `POST /{id}/verify` | Issue lifecycle, triage, assignment, and QA verification. |
| `/api/v1/approvals` | `GET /`, `POST /`, `POST /{id}/decide`, `POST /{id}/mark-executed` | Developer/Manager approval workflow and execution tracking. |
| `/api/v1/backups` | `GET /`, `POST /`, `POST /{id}/verify` | Backup registry and pre-update gate verification. |
| `/api/v1/reports` | `GET /`, `POST /generate`, `POST /test-email`, `GET /deliveries` | On-demand PDF/CSV/XLSX export and scheduled email delivery logs. |
| `/api/v1/checks` | `POST /sessions/{id}/run-readonly` | Triggers asynchronous safe read-only checks and attaches evidence. |
| `/api/v1/audit` | `GET /events` | Filterable, append-only timeline of all system state changes. |
