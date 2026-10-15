# OpsHub Step-by-Step Engineering Implementation Plan

**Document Version:** 1.0  
**Date:** 15 October 2026  
**Execution Strategy:** Trustworthy Data -> Dependable SOP Workflow -> Visible Ownership -> Automatic Reporting -> Safe Read-Only Automation  

## 1. Repository & Directory Structure

```text
opshub/
├── prd.md                          # Product Requirements & 23-step SOP spec
├── architecture.md                 # System topology, 16-table schema & API spec
├── design.md                       # UI/UX wireframe, QSS tokens & badge spec
├── memory.md                       # Core invariants, SOP reference rules & ADRs
├── status.md                       # Phase tracker & open decisions register
├── implementation_plan.md          # Step-by-step build & verification guide
├── pyproject.toml                  # Pinned dependencies & pytest config
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI app factory & lifespan scheduler hook
│   │   ├── core/
│   │   │   ├── config.py           # Env configuration & secret store resolver
│   │   │   ├── database.py         # SQLAlchemy 2.x engine & session management
│   │   │   └── security.py         # RBAC permissions & JWT auth dependencies
│   │   ├── models/                 # 16 SQLAlchemy ORM models
│   │   │   ├── org_user.py         # Organization, User, Role, UserRole
│   │   │   ├── project_site.py     # Project, Milestone, Website
│   │   │   ├── sop_workflow.py     # WorkflowTemplate, MaintenanceSchedule, Session, ChecklistItem
│   │   │   ├── operations.py       # Task, WorkLog, Issue, Approval, BackupRecord, Evidence
│   │   │   └── audit_report.py     # ActivityEvent, ReminderAndReport, IntegrationConfig
│   │   ├── schemas/                # Pydantic v2 request/response schemas
│   │   ├── services/               # Pure domain logic & gating services
│   │   │   ├── audit_service.py    # Append-only activity event recorder
│   │   │   ├── import_service.py   # CSV/Excel website importer with deduplication
│   │   │   ├── sop_gate_service.py # 23-step template seeding, conditional rules & completion gates
│   │   │   ├── issue_service.py    # Issue lifecycle & verification state machine
│   │   │   ├── approval_service.py # Approval request, decision & execution tracker
│   │   │   └── dashboard_service.py# Real-time KPI aggregation & drill-down queries
│   │   └── api/                    # FastAPI routers (/dashboard, /websites, /sessions, etc.)
│   └── alembic/                    # Database schema migrations
├── workers/
│   ├── scheduler.py                # APScheduler job runner (due dates, reminders, reports)
│   ├── checks/
│   │   ├── http_tls_check.py       # Read-only HTTP status, response time, TLS expiry & headers
│   │   └── link_image_check.py     # BeautifulSoup4 broken-link & missing-image inspector
│   └── reports/
│       ├── pdf_exporter.py         # ReportLab PDF completion & summary report generator
│       ├── excel_csv_exporter.py   # openpyxl & CSV export generator with redaction
│       └── email_dispatcher.py     # SMTP / sink email sender with retry & delivery logs
├── desktop/
│   ├── main.py                     # PySide6 QApplication entry point
│   ├── services/
│   │   └── api_client.py           # QThreadPool async client for FastAPI / service layer
│   └── ui/
│       ├── main_window.py          # 13-module sidebar shell, global search & header bar
│       ├── styles/
│       │   └── theme.qss           # Semantic QSS stylesheet & accessible badge styles
│       ├── widgets/
│       │   ├── status_badge.py     # Icon + text + color badge widget (Passed/Failed/Not Verified/etc.)
│       │   └── kpi_card.py         # Clickable dashboard metric card
│       └── views/                  # 13 primary navigation module screens
└── tests/
    ├── conftest.py                 # Isolated in-memory SQLite fixtures
    ├── unit/
    │   ├── test_sop_gates.py       # Pre-update backup gate, conditional Divi/Staging & closure tests
    │   ├── test_issue_lifecycle.py # Verification pass/fail state transition tests
    │   └── test_import_dedup.py    # Excel/CSV website import & duplicate prevention tests
    └── integration/
        ├── test_api_workflow.py    # End-to-end maintenance session & approval flow
        └── test_readonly_checks.py # Honest Not Verified / Passed check evidence tests
```

## 2. Step-by-Step Build Sequence (Phases 1 to 6)

### Step 1: Database Layer, Audit Trail & Seeded SOP Template (Phase 1A)
1. **Implement SQLAlchemy 2.x Models (`backend/app/models/`):**
   - Define all 16 core entities with strict enums for `WebsiteEnvironment`, `HealthStatus`, `WorkflowStatus`, `ChecklistItemStatus`, `TaskStatus`, `IssueSeverity`, `IssueStatus`, and `ApprovalStatus`.
   - Enforce foreign keys and composite uniqueness constraints (e.g., unique `(project_id, domain, environment)` on `websites`; unique `(code, version)` on `workflow_templates`).
2. **Build Append-Only Audit Service (`backend/app/services/audit_service.py`):**
   - Create `record_event(session, actor_id, entity_type, entity_id, action, before, after)` that writes to `activity_events` within the active database transaction.
3. **Seed Version 1 of the 23-Step WordPress Maintenance SOP (`backend/app/services/sop_gate_service.py`):**
   - Populate all 23 tasks from Section 8.1 of the blueprint along with their conditional applicability rules (`staging_only` for Step 7, `divi_only` for Step 19, `live_backup_gate` on Step 9 unlocking Steps 10–12, and mandatory closure gates on Steps 22 and 23) and the 8 canonical rule reference snippets from Section 8.2.
4. **Verification Gate 1:**
   - Run `pytest tests/unit/test_models_and_seed.py` to confirm all 16 tables create cleanly, the 23-step SOP template seeds with version `1`, and `activity_events` logs initial creation.

### Step 2: Inventory Importer, Project Register & Live Dashboard Queries (Phase 1B)
1. **Build CSV/Excel Website Importer (`backend/app/services/import_service.py`):**
   - Parse `.xlsx` (via `openpyxl`) and `.csv` files, validate required fields (`name`, `domain`, `environment`), detect duplicate domains before commit, and log an import summary.
2. **Implement Live Dashboard Aggregation (`backend/app/services/dashboard_service.py`):**
   - Write SQLAlchemy aggregation queries for all 11 dashboard widgets (active projects, websites by environment, due today/7d/overdue, sessions by status, open critical/high issues, pending approvals, unverified backups, completed tasks, SSL alerts, and recent activity).
   - Provide a `get_drilldown_records(metric_key)` method so clicking any metric card returns the exact underlying rows.
3. **Verification Gate 2:**
   - Run `pytest tests/unit/test_import_dedup.py` to verify zero duplicate imports and accurate dashboard KPI counts against seeded records.

### Step 3: SOP Workflow Engine, Conditional Rules & Completion Gates (Phase 2)
1. **Build Session Instantiation with Template Snapshot:**
   - When `start_maintenance_session(website_id, maintainer_id)` is called, copy the active `WorkflowTemplate` JSON into `session.template_version_snapshot_json` and generate the 23 `SessionChecklistItem` rows.
   - Automatically mark Step 7 (`Search-engine discouragement`) as `Not Applicable` on `live` sites (with reason `"Live environment"`) and `Pending` on `staging` sites.
   - Automatically mark Step 19 (`Divi Builder`) as `Pending` if `website.builder == 'divi'` and `Not Applicable` otherwise (while allowing manual override).
2. **Enforce Pre-Update & Closure Gates (`SOPGateService`):**
   - Block updates to Steps 10, 11, and 12 on `live` sites unless `BackupRecord` is verified for the session or an approved backup exception exists.
   - Block session closure as `Completed` unless all required steps are addressed, Steps 22 and 23 are `Passed`, and any Step 13 (`Post-update re-check`) failure has a linked issue and resolution/exception.
3. **Verification Gate 3:**
   - Run `pytest tests/unit/test_sop_gates.py` covering live vs. staging sessions, Divi conditional logic, backup gate blocking/unblocking, and session closure rules.

### Step 4: Cross-Project Tasks, Issue Lifecycle & Approval Workflows (Phase 3)
1. **General Task Service (`backend/app/services/task_service.py`):**
   - Support full task lifecycle (`Backlog` -> `Completed` / `Cancelled` with mandatory cancellation reason), task dependencies, owner reassignment history, and explicit work log entries (`what_was_done`, `what_remains`, `blockers`, `next_action`).
2. **Issue & Verification Service (`backend/app/services/issue_service.py`):**
   - Allow spawning an `Issue` directly from any failed SOP checklist item or project task.
   - Enforce the verification gate: transitioning an issue from `Verification` with `outcome='failed'` automatically returns the issue to `In Progress` / `Reopened`; `Closed` is only reachable after `Verification` passes or `Accepted Risk` is approved.
3. **Approval Workflow Service (`backend/app/services/approval_service.py`):**
   - Implement `request_approval`, `decide_approval` (`Approved` / `Rejected` / `More Information Required`), `mark_executed`, and `mark_verified`, ensuring self-approval by a `Maintenance Engineer` is rejected by RBAC.
4. **Verification Gate 4:**
   - Run `pytest tests/unit/test_issue_lifecycle.py` and `test_approvals.py` to verify RBAC separation of duties and verification state machines.

### Step 5: Scheduler, Reminders, PDF/Excel Exports & Email Reports (Phase 4)
1. **Recurrence & Reminder Scheduler (`workers/scheduler.py`):**
   - Compute `next_due_at` using the website's `anchor_policy` (`planned_date` vs. `completion_date`).
   - Generate due reminders, overdue alerts, idle session nudges, and critical issue escalations with deduplication keys so alerts are never spammed repeatedly.
2. **Report & Export Generators (`workers/reports/`):**
   - Build `pdf_exporter.py` (using `ReportLab`) and `excel_csv_exporter.py` (using `openpyxl` and `csv`) to export Maintenance Completion Reports, Daily/Weekly Summaries, Issue Registers, and Overdue Lists with automatic secret/path redaction.
   - Record every generation and SMTP delivery attempt in `reminders_and_reports` and support marked `[UPDATED REVISION]` sends if a session changes after initial report delivery.
3. **Verification Gate 5:**
   - Run integration tests confirming PDF/XLSX/CSV file generation, post-report revision detection, and scheduler retry handling on simulated SMTP failure.

### Step 6: Safe Read-Only Website Automation Workers (Phase 5)
1. **HTTP, TLS & Security Header Inspector (`workers/checks/http_tls_check.py`):**
   - Inspect HTTP reachability, response time, TLS certificate expiration days, `robots.txt` rules, and security headers (`X-Frame-Options`, `X-Content-Type-Options`, `Strict-Transport-Security`, `X-Powered-By`).
2. **Broken Link & Image Inspector (`workers/checks/link_image_check.py`):**
   - Parse public homepage/key URLs with `BeautifulSoup4` to flag broken links (`4xx`/`5xx`) and missing image assets.
3. **Epistemic Limitation Recording:**
   - If a site blocks requests, requires auth, or lacks SSH/WP REST credentials for core/permission checks (Steps 3, 5, 6, 17), record status `not_verified` with explicit `limitations` text and attach the `Evidence` JSON to the session step.
4. **Verification Gate 6:**
   - Run `pytest tests/integration/test_readonly_checks.py` against local mock HTTP responses to verify both `Passed`/`Failed` header detection and `Not Verified` behavior when access is restricted.

### Step 7: PySide6 Desktop Client & FastAPI Integration (Phase 1–6 UI Shell)
1. **Build Main Navigation Shell (`desktop/ui/main_window.py`):**
   - Implement the 13 primary navigation views, `Ctrl+K` global search bar, and role switcher/indicator.
2. **Build Interactive Views:**
   - **Global Dashboard View:** 11 clickable KPI cards wired to drill-down tables.
   - **Websites & Import Wizard View:** Multi-tab site profile and Excel/CSV import preview dialog.
   - **SOP Maintenance Session View:** 23-step interactive checklist with conditional step badges, inline Rule Reference drawer, Pre-Update Backup Gate banner, and one-click Issue/Approval creation modals.
   - **Tasks, Issues, Approvals, Backups, Reports & Audit Views:** Filterable tables, detail drawers, and export buttons running via `QThreadPool` workers.
