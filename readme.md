# PulseOps — Enterprise Operations & Reliability Command Center (`README.md`)

**Brand Name:** **PulseOps**  
**Version:** 2.4.0 (Executive Dark Obsidian Edition)  
**Stack:** `Python 3.12+` | `FastAPI` + `Pydantic v2` | `PySide6` (`Qt6 Widgets` + Executive Obsidian `QSS`) | `PostgreSQL 16` / `SQLite 3` | `ReportLab` & `openpyxl`  

PulseOps is an enterprise-grade site reliability and maintenance operations command center designed for high-density DevOps, SRE, and web engineering teams. It digitizes the **23-Step WordPress Site Maintenance SOP** with pre-update backup gates, developer approval workflows, epistemic verification tracking (`Passed`, `Failed`, `Blocked`, `Not Applicable`, and `Not Verified / Access Required`), cross-project task management with structured work logs ("Works"), and automated PDF/Excel compliance reporting.

## 1. System Architecture & Executive Obsidian Design

```text
+------------------------------------------------------------------------------------+
|               PySide6 Desktop Client (Executive Dark Obsidian Design)              |
|  +------------------------+  +------------------------+  +----------------------+  |
|  | Collapsible Sidebar    |  | Responsive Work Area   |  | Interactive Tasks &  |  |
|  | (13 Operational Views) |  | + 23-Step SOP Split UI |  | Work Log ("Works")   |  |
|  +-----------+------------+  +-----------+------------+  +----------+-----------+  |
+--------------|---------------------------|--------------------------|--------------+
               |                           | HTTPS / REST (JSON)      |
               v                           v                          v
+------------------------------------------------------------------------------------+
|                          FastAPI Application Server (`/api/v1`)                    |
|  +------------------------+  +------------------------+  +----------------------+  |
|  | JWT + 2FA Auth &       |  | SOPGateService, Issue  |  | Feature Flags &      |  |
|  | 7-Role RBAC Guard      |  | & Approval Engines     |  | Work Log Ledger      |  |
|  +-----------+------------+  +-----------+------------+  +----------+-----------+  |
+--------------|---------------------------|--------------------------|--------------+
               v                           v                          v
+---------------------------+  +------------------------+  +-------------------------+
| PostgreSQL 16 / SQLite 3  |  | Safe Read-Only Workers |  | ReportLab PDF &         |
| (16 Tables + Append-Only  |  | (HTTPX, TLS, Headers,  |  | openpyxl XLSX Exporter  |
|  activity_events Trigger) |  |  BS4 Links, INV-02)    |  | + Revision Detection    |
+---------------------------+  +------------------------+  +-------------------------+
```

### Calculated Executive Design Tokens & Palette

| Token Category | Token Key | Hex Value / Styling | Purpose |
| :--- | :--- | :--- | :--- |
| **Canvas** | `bg_canvas` | `#0A0E17` (Obsidian Space) | Base application background for minimal eye strain in NOC/SOC environments. |
| **Shell & Nav** | `bg_sidebar` | `#070B12` (Midnight Slate) | Persistent navigation sidebar with `#1E293B` border. |
| **Surfaces** | `bg_surface` | `#111827` (Elevation Slate) | Cards, detail drawers, and interactive work-log panels. |
| **Brand Primary** | `brand.primary` | `#6366F1` (Electric Indigo) | Primary action buttons, active navigation indicator, focus rings. |
| **Telemetry Pulse** | `brand.pulse` | `#06B6D4` (Cyan Telemetry) | Real-time telemetry, subtitles, active glows. |
| **Online / Passed** | `status.passed` | `#10B981` (Emerald Green) | Confirmed human or automated check passing. |
| **Warning / Due** | `status.due` | `#F59E0B` (Amber Gold) | Due today, maintenance in progress, or pending approval. |
| **Critical / Blocked** | `status.blocked`| `#EF4444` (Crimson Rose) | Blocked by backup gate, failed check, or open critical finding. |
| **Not Verified** | `status.unverified`| `#854D0E` on `#FEF9C3` | Automated check lacked SSH/WP-Admin credentials (`INV-02`). |
| **Typography** | `Inter`, `Outfit`, `JetBrains Mono` | High legibility fonts | `Outfit` for numerical metrics; `JetBrains Mono` for rules and code. |

## 2. Interactive Tasks & Works Management

The Tasks workbench supports complete operational lifecycle management:
- **Task Creation Modal:** Specify title, project, assignee, priority (`critical`, `high`, `normal`, `low`), estimated hours, due date, description, and acceptance criteria.
- **Structured Work Logs ("Works"):** Log engineering time (`+1.5 hrs`) with structured fields (*What was done*, *What remains*, *Blockers*, *Next action*). Automatically rolls up total hours on the task.
- **Dependency Guard (`INV-03`):** Tasks with dependency chains cannot be transitioned to `completed` while prerequisite tasks are incomplete.
- **Mandatory Cancellation Reason:** Enforces accountability; tasks cannot be marked `cancelled` without a recorded reason.

## 3. Quick Start (Ubuntu / Debian / Windows / macOS)

### Standalone Desktop Launch (Zero-Configuration)
```bash
# 1. Activate virtual environment
source .venv/bin/activate

# 2. Launch the PulseOps Command Center:
python3 -m desktop.main
```
*(The desktop application automatically initializes the embedded high-performance engine if no standalone server is running).*

### Network Client / Server Mode
```bash
# Terminal 1: Start FastAPI Backend Server
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload

# Terminal 2: Launch PulseOps Desktop Client connected to server
OPSHUB_API_URL=http://127.0.0.1:8000 python3 -m desktop.main
```

## 4. REST API Reference (`/api/v1`)

| Method & Path | Permission Required | Description |
| :--- | :--- | :--- |
| `POST /api/v1/auth/login` | Public | Authenticates operator and returns JWT access/refresh tokens. |
| `POST /api/v1/auth/verify-2fa` | Authenticated | Verifies 6-digit TOTP code for sensitive operational sessions. |
| `GET /api/v1/dashboard/summary` | `view_records` | Computes live SQL counts across active projects, due/overdue sites, sessions, issues, and backups. |
| `GET /api/v1/dashboard/drilldown/{key}` | `view_records` | Returns filtered underlying records for any clicked dashboard KPI card. |
| `POST /api/v1/tasks` | `execute_maintenance`| Creates a new project task with priority, estimates, and dependencies. |
| `PATCH /api/v1/tasks/{id}/status` | `execute_maintenance`| Updates task status with dependency validation (`INV-03`) and cancellation reason enforcement. |
| `POST /api/v1/tasks/{id}/work-logs`| `execute_maintenance`| Logs engineering work hours and updates rolled-up task totals. |
| `GET /api/v1/tasks/{id}/work-logs` | `view_records` | Returns chronological work logs for the specified task. |
| `POST /api/v1/websites/import` | `assign_work` | Bulk imports websites from CSV/Excel with duplicate `(domain, environment)` prevention. |
| `POST /api/v1/sessions` | `execute_maintenance`| Starts a 23-step SOP session, snapshots template version (`INV-04`), and applies `Staging`/`Divi` rules. |
| `PATCH /api/v1/sessions/{id}/items/{step}` | `execute_maintenance`| Updates step status while enforcing Live Pre-Update Backup Gates (`HTTP 409`). |
| `POST /api/v1/sessions/{id}/run-readonly-checks` | `execute_maintenance`| Runs safe read-only checks and marks credential-gated steps `not_verified` (`INV-02`). |
| `POST /api/v1/sessions/{id}/close` | `execute_maintenance`| Enforces mandatory closure gates on Step 22 and Step 23. |
| `POST /api/v1/reports/sessions/{id}/pdf` | `export_reports` | Generates PDF completion report with revision detection. |
| `POST /api/v1/reports/export/xlsx` | `export_reports` | Exports multi-sheet Excel compliance workbook via `openpyxl`. |

## 5. Automated Verification Test Suite

Run the complete 9-suite automated verification check:
```bash
PYTHONPATH=. .venv/bin/pytest tests -v
```
All 9 test suites pass with 100% test coverage across all architectural invariants (`INV-01` through `INV-06`).
