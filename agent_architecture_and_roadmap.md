# OpsHub — Master Architecture & Agent Execution Playbook
**Role Topology:** Chief Architect & Lead Reviewer (`Gemini`) ⇄ Product & Engineering Coordinator (`You`) ⇄ Implementation Agent (`Antigravity / Codex`)  
**Target Stack:** `Python 3.12+` | `FastAPI` + `Pydantic v2` | `SQLite` (Dev/Local) & `PostgreSQL 16` (Prod) | `APScheduler` | `PySide6` (`Qt6 Widgets` + `QSS`)  
**Document Purpose:** Drop this file (`AGENT_ARCHITECTURE_AND_ROADMAP.md`) into the root of your repository (`~/Pictures/Dash-main/`) and instruct **Antigravity** or **Codex** to execute it sprint by sprint.

## 1. Tri-Party Engineering Workflow (How We Build Together)

| Role | Actor | Core Responsibility in Every Sprint |
| :--- | :--- | :--- |
| **Chief Architect & Reviewer** | **Gemini (Me)** | Defines system architecture, database schemas, SOP state machines, UI ergonomics, and sprint prompts; reviews diffs/logs/screenshots after each agent run and writes corrective patches if needed. |
| **Engineering Coordinator** | **You** | Feeds the Sprint Prompt from Section 6 to Antigravity/Codex, runs the verification command in terminal, tests the PySide6 window, and pastes terminal output or feedback back here. |
| **Builder Agent** | **Antigravity / Codex** | Reads this blueprint, writes modular production code and `pytest` / `unittest` suites, runs verification commands inside `.venv`, and never skips acceptance gates. |

## 2. Critical UI/UX Ergonomics & Window Sizing Rules (Mandatory for Antigravity)

> **CRITICAL FIX FOR DESKTOP WINDOW SIZING & RESIZING:**  
> Never hard-code `self.resize(1440, 900)` or pack 7 wide buttons into a single unscrollable `QHBoxLayout`. In Qt/PySide6, wide horizontal layouts force the window's `minimumSizeHint()` to exceed laptop screens (1366×768 or 1920×1080 at 125%–150% Ubuntu fractional scaling), locking the window from being resized smaller.

Every PySide6 view built by Antigravity/Codex **MUST** obey these 6 layout laws:

1. **Dynamic Screen-Relative Startup Geometry:**
   - Query `screen_geom = QGuiApplication.primaryScreen().availableGeometry()`.
   - Set initial width to `min(1240, int(screen_geom.width() * 0.85))` and initial height to `min(780, int(screen_geom.height() * 0.85))`.
   - Center the window inside `screen_geom` on launch.
2. **Permissive Minimum Window Size:**
   - Call `self.setMinimumSize(860, 540)` on `QMainWindow` and ensure `self.setWindowFlags(Qt.Window)` includes standard minimize, maximize, and resize handles.
3. **Mandatory `QScrollArea` Wrapper on the Central Workspace:**
   - Wrap the right-hand module stack (`QStackedWidget`) inside a `QScrollArea` with `scroll_area.setWidgetResizable(True)` and `scroll_area.setFrameShape(QFrame.NoFrame)`. This decouples internal widget minimum widths from the outer `QMainWindow` frame so the user can freely shrink, half-tile (`Super + Left/Right`), or maximize the window on any screen.
4. **Collapsible / Compact Sidebar (`190px` Default):**
   - Keep the left navigation sidebar at `190px` width (with a `[☰]` collapse toggle down to `56px` icon-only mode) so it never eats horizontal real estate.
5. **Multi-Row Action Toolbars & Elided Text:**
   - Wrap action buttons into a 2-row `QGridLayout` or compact toolbar rather than a single wide `QHBoxLayout`.
   - Set `QSizePolicy.Ignored` or `QSizePolicy.Expanding` with `wordWrap=True` on long labels (such as the Pre-Update Backup Gate banner) so long text never forces the window wider.
6. **Non-Blocking Background Workers (`QThreadPool`):**
   - Run all HTTP checks, file imports, and PDF/XLSX report generations inside `QRunnable` workers so the GUI never freezes.

## 3. Target Repository Structure (`~/Pictures/Dash-main/`)

Instruct Antigravity/Codex to organize the repository into this modular structure while keeping `opshub_app.py` (or `main.py`) at the root as a one-command launcher:

```text
Dash-main/
├── AGENT_ARCHITECTURE_AND_ROADMAP.md   # Master blueprint for Antigravity / Codex
├── prd.md                              # Product Requirements & 23-step SOP matrix
├── architecture.md                     # System topology & 16-table schema
├── design.md                           # UI/UX tokens, QSS palette & badge rules
├── memory.md                           # Non-negotiable invariants (INV-01..INV-06)
├── status.md                           # Sprint progress tracker
├── requirements.txt                    # Python dependencies for .venv
├── opshub_responsive_app.py            # Turnkey single-command responsive launcher
├── backend/
│   ├── __init__.py
│   └── app/
│       ├── __init__.py
│       ├── main.py                     # FastAPI application factory & routers
│       ├── core/
│       │   ├── config.py               # Paths, env vars & OS keyring secret resolver
│       │   ├── database.py             # 16-table SQLite/PostgreSQL schema & session mgr
│       │   └── security.py             # 7-role RBAC permission matrix
│       ├── models/
│       │   └── enums.py                # Strict domain enums for all state machines
│       └── services/
│           ├── audit_service.py        # Append-only activity_events logger
│           ├── sop_seed.py             # 23-step WordPress SOP + 8 rule snippets
│           ├── sop_gate_service.py     # Versioning, conditional rules & completion gates
│           ├── import_service.py       # CSV/XLSX website importer with deduplication
│           ├── task_service.py         # Cross-project tasks, dependencies & work logs
│           ├── issue_service.py        # Issue lifecycle & QA verification state machine
│           ├── approval_service.py     # Developer/Manager approval & backup services
│           ├── dashboard_service.py    # 11 live KPI aggregations & drill-down queries
│           └── seed_demo.py            # Baseline organization, 7 role users & sample sites
├── workers/
│   ├── scheduler.py                    # Idempotent due/overdue reminders & escalations
│   ├── checks/
│   │   └── http_tls_check.py           # Read-only HTTP/TLS/header/link checks (INV-02)
│   └── reports/
│       └── pdf_exporter.py             # ReportLab PDF, openpyxl XLSX & mail sink exporter
├── desktop/
│   ├── main.py                         # PySide6 responsive entry point
│   ├── services/
│   │   └── api_client.py               # Dual-mode HTTP / embedded FastAPI client + QThreadPool
│   └── ui/
│       ├── main_window.py              # Responsive QScrollArea shell + 13 module views
│       ├── styles/
│       │   └── theme.qss               # Slate/Blue high-contrast QSS theme
│       └── widgets/
│           └── status_badge.py         # Accessible icon + text + color badges
└── tests/
    ├── unit/
    │   ├── test_sop_gates.py
    │   ├── test_issue_and_approvals.py
    │   └── test_desktop_client_and_tasks.py
    └── integration/
        └── test_api_and_reports.py
```

## 4. Six Non-Negotiable Domain Invariants (Antigravity Must Enforce)

| ID | Invariant Name | Engineering Enforcement Rule |
| :--- | :--- | :--- |
| **`INV-01`** | **Completion ≠ Verification** | Marking a task/issue Fixed or an approval Approved never implies Verification. Issues in `fixed_mitigated` / `verification` cannot transition to `closed` without a passed QA verification outcome (or Manager-approved `accepted_risk`). If QA verification fails, the issue automatically transitions to `reopened`. |
| **`INV-02`** | **Epistemic Honesty in Automation** | Automated checks that lack SSH, filesystem, or WP-Admin access (such as Step 3 Core Checksums, Step 5 File Permissions, Step 6 `wp-config.php` Debug Constants, Step 17 Admin Users) MUST record `not_verified` with an explicit `limitations` string—never `passed`. |
| **`INV-03`** | **Decoupled Health vs. Workflow Status** | Every `websites` row stores `health_status` (`online`, `degraded`, `down`, `unknown`) separately from `workflow_status` (`up_to_date`, `due`, `in_progress`, `blocked`, `overdue`). |
| **`INV-04`** | **Immutable SOP Template Snapshots** | Starting a `maintenance_sessions` row copies the active `workflow_templates` JSON into `template_snapshot_json` so future SOP edits never rewrite historical session records. |
| **`INV-05`** | **Hard Pre-Update & Closure Gates** | On `live` websites, Steps 10 (Core), 11 (Themes), and 12 (Plugins) are locked (`HTTP 409`) until Step 9 (`Backup`) has a verified `backup_records` row (`is_verified=1`) or an approved `backup_exception` approval. Closing a session as `completed` is blocked until Steps 22 (`Final frontend check`) and 23 (`Review notes`) are `passed`. |
| **`INV-06`** | **Append-Only Audit Trail** | Database triggers (`prevent_activity_events_update` and `prevent_activity_events_delete`) block any `UPDATE` or `DELETE` on `activity_events`. |

## 5. Complete 23-Step WordPress SOP Specification & Gating Matrix

| Step | Code | Title | Condition | Pre-Update Backup Gate | Approval Gate | Closure Gate | Rule Reference Key |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **01** | `SOP_01` | Website overview | Always | No | None | No | — |
| **02** | `SOP_02` | Slow website / performance | Always | No | None | No | — |
| **03** | `SOP_03` | Default/core files | Always | No | `core_file_remediation` | No | — |
| **04** | `SOP_04` | `.htaccess` security rules | Always | No | None | No | `htaccess_security_headers` |
| **05** | `SOP_05` | File permissions | Always | No | None | No | `file_permissions_policy` |
| **06** | `SOP_06` | Debug logging | Always | No | None | No | `wp_debug_constants` |
| **07** | `SOP_07` | Search-engine discouragement | `staging_only` | No | None | No | `staging_robots_policy` |
| **08** | `SOP_08` | Directory indexing | Always | No | None | No | `directory_indexing_rule` |
| **09** | `SOP_09` | Backup | Always | **Unlocks 10–12** | `backup_exception` (if skipped) | **Yes (Live)** | — |
| **10** | `SOP_10` | WordPress core updates | Always | **Locked on Live** | `wp_core_upgrade` | No | — |
| **11** | `SOP_11` | Theme updates | Always | **Locked on Live** | Parent theme policy | No | — |
| **12** | `SOP_12` | Plugin updates | Always | **Locked on Live** | Risky plugin policy | No | — |
| **13** | `SOP_13` | Post-update re-check | Always | No | `post_update_exception` | **Blocks if Failed** | — |
| **14** | `SOP_14` | Plugin conflicts / duplicates | Always | No | None | No | — |
| **15** | `SOP_15` | Disable auto-update policy | Always | No | Policy deviation | No | — |
| **16** | `SOP_16` | Unused plugins/themes cleanup | Always | No | `plugin_theme_deletion` | No | `plugin_cleanup_review_list` |
| **17** | `SOP_17` | Administrator users | Always | No | `admin_account_change` | No | — |
| **18** | `SOP_18` | Site Health | Always | No | None | No | — |
| **19** | `SOP_19` | Divi Builder (conditional) | `divi_only` | No | `divi_code_migration` | No | — |
| **20** | `SOP_20` | Security plugins | Always | No | None | No | `wordfence_and_security_plugins` |
| **21** | `SOP_21` | Wordfence scan | Always | No | None | No | `wordfence_and_security_plugins` |
| **22** | `SOP_22` | Final frontend check | Always | No | None | **Mandatory PASS** | — |
| **23** | `SOP_23` | Review notes | Always | No | None | **Mandatory PASS** | — |

## 6. Copy-Paste Sprint Prompts for Antigravity / Codex

Copy and paste these prompts one at a time into **Antigravity** or **Codex**. After each sprint, run the verification command and share the output with me for review.

### Sprint 1 Prompt: Core Database Schema, RBAC Security & Append-Only Audit Engine
> **Prompt for Antigravity / Codex:**  
> "Read `AGENT_ARCHITECTURE_AND_ROADMAP.md`, `architecture.md`, and `memory.md`. Implement Sprint 1:
> 1. Create `backend/app/core/config.py`, `backend/app/models/enums.py`, `backend/app/core/database.py`, `backend/app/core/security.py`, and `backend/app/services/audit_service.py`.
> 2. Ensure `database.py` defines all 16 tables (`organizations`, `users`, `user_role_scopes`, `projects`, `milestones`, `websites`, `workflow_templates`, `maintenance_schedules`, `maintenance_sessions`, `session_checklist_items`, `tasks`, `task_work_logs`, `issues`, `approvals`, `backup_records`, `evidences`, `reminders_and_reports`, `activity_events`, `integration_configurations`) plus the SQLite triggers preventing `UPDATE` and `DELETE` on `activity_events` (`INV-06`).
> 3. Implement the 7-role RBAC permission matrix in `security.py`, ensuring `report_recipient` has zero application access and `readonly_stakeholder` is read-only.
> 4. Write and run unit tests verifying schema initialization, RBAC checks, and append-only audit trigger enforcement."

### Sprint 2 Prompt: 23-Step WordPress SOP Engine, Conditional Rules & Completion Gates
> **Prompt for Antigravity / Codex:**  
> "Read Section 5 of `AGENT_ARCHITECTURE_AND_ROADMAP.md` and `prd.md`. Implement Sprint 2:
> 1. Create `backend/app/services/sop_seed.py` and `backend/app/services/sop_gate_service.py`.
> 2. Seed all 23 WordPress Maintenance SOP tasks and the 8 canonical rule reference snippets (`.htaccess` headers, `444`/`644` permission policy inputs, `WP_DEBUG` constants, staging `robots.txt` access-control warning, directory indexing, 8-item plugin cleanup review list, and Wordfence guide).
> 3. In `SOPGateService.start_session()`, snapshot the active template version into `template_snapshot_json` (`INV-04`), automatically mark Step 7 (`Search-engine discouragement`) as `not_applicable` on `live` sites and `pending` on `staging` sites, and mark Step 19 (`Divi Builder`) as `pending` when `website.builder == 'divi'` and `not_applicable` otherwise.
> 4. Enforce the Live Site Pre-Update Backup Gate (`INV-05`): block transitioning Steps 10, 11, or 12 to `in_progress` or `passed` on live sites unless a verified `backup_records` row (`is_verified=1`) or an approved `backup_exception` approval exists for the session.
> 5. Enforce Developer Approval gates on Step 10 (Core upgrade) and Step 16 (Plugin/theme deletion), and enforce the Session Closure Gate requiring Steps 22 and 23 to be `passed` and blocking normal completion if Step 13 (`Post-update re-check`) failed without a resolved issue or exception.
> 6. Run `PYTHONPATH=. python3 -m unittest tests/unit/test_sop_gates.py -v` and confirm 100% pass."

### Sprint 3 Prompt: CSV/Excel Inventory Importer, Tasks, Issue Verification & Approvals
> **Prompt for Antigravity / Codex:**  
> "Implement Sprint 3 across `backend/app/services/`:
> 1. Build `import_service.py` supporting `.csv` and `.xlsx` (`openpyxl`) website imports with column normalization, dry-run preview, duplicate `(domain, environment)` detection, and automatic `maintenance_schedules` creation.
> 2. Build `task_service.py` with dependency blocking (`cannot complete task while dependency is incomplete`), mandatory `cancellation_reason`, and work-log hour rollups.
> 3. Build `issue_service.py` enforcing `INV-01`: block direct transition to `closed` without a passed QA verification outcome; if `verify_issue(passed=False)` is called, automatically transition the issue to `reopened`.
> 4. Build `approval_service.py` and `BackupService` enforcing separation of duties (Maintenance Engineers cannot approve restricted actions or self-approve their own requests).
> 5. Build `dashboard_service.py` computing live SQL counts and drill-down records for all 11 dashboard KPIs.
> 6. Run `PYTHONPATH=. python3 -m unittest tests/unit/test_issue_and_approvals.py -v`."

### Sprint 4 Prompt: Safe Read-Only Checks, Scheduler, PDF/XLSX Exporters & FastAPI Router
> **Prompt for Antigravity / Codex:**  
> "Implement Sprint 4 in `workers/` and `backend/app/main.py`:
> 1. Build `workers/checks/http_tls_check.py` using `httpx` and `BeautifulSoup4` for HTTP status, response time, security headers, and link/image discovery. Enforce `INV-02`: steps requiring SSH or WP-Admin credentials (#3, #5, #6, #17) must record `not_verified` with explicit `limitations` metadata when credentials are not configured.
> 2. Build `workers/reports/pdf_exporter.py` using `ReportLab` and `openpyxl` with automatic secret redaction and `[UPDATED REVISION REPORT]` detection when a session report is regenerated.
> 3. Build `workers/scheduler.py` with daily deduplication for overdue website reminders and high-severity issue escalations.
> 4. Wire all `/api/v1/*` endpoints in `backend/app/main.py` and verify with `tests/integration/test_api_and_reports.py`."

### Sprint 5 Prompt: Responsive PySide6 Desktop Command Center (Fixing Screen Sizing & All 13 Modules)
> **Prompt for Antigravity / Codex:**  
> "Read Section 2 of `AGENT_ARCHITECTURE_AND_ROADMAP.md` and `design.md`. Build and polish the PySide6 desktop application (`desktop/` and `opshub_responsive_app.py`):
> 1. Fix window geometry and resizing: query `QGuiApplication.primaryScreen().availableGeometry()`, size the window to 85% of available screen width/height (capped at `1240x780`), set `self.setMinimumSize(860, 540)`, and wrap the right workspace inside a `QScrollArea` (`setWidgetResizable(True)`) so the user can freely resize, shrink, tile, or maximize the window on any monitor.
> 2. Implement the collapsible `190px` sidebar with all 13 navigation modules (`Overview`, `Projects`, `My Tasks`, `All Tasks`, `Websites`, `Maintenance Queue`, `Issues & Findings`, `Approvals`, `Backups`, `Reports`, `Notifications`, `Activity History`, `Administration / Settings`).
> 3. Implement interactive dialogs/actions for CSV/Excel Website Import, New Task + Work Log entry, Issue Creation + QA Verification sign-off, Approval Decision (`Approve` / `Reject`), Backup Verification, and 23-Step SOP Session execution with the inline Rule Reference drawer."
