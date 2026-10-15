# OpsHub — Maintenance & Project Operations Command Center (`README.md`)

**Version:** 1.0.0 (Argon Design System Edition)  
**Stack:** `Python 3.12+` | `FastAPI` + `Pydantic v2` | `PySide6` (`Qt6 Widgets` + Argon `QSS`) | `PostgreSQL 16` / `SQLite 3` | `ReportLab` & `openpyxl`  

OpsHub is a production-grade maintenance and project operations command center built to replace scattered Excel trackers, manual reminders, and unverified status checkboxes. It digitizes the **23-Step WordPress Site Maintenance SOP** with hard pre-update backup gates, developer approval workflows, epistemic verification tracking (`Passed`, `Failed`, `Blocked`, `Not Applicable`, and `Not Verified / Access Required`), cross-project task management, and automated PDF/Excel reporting.

## 1. System Architecture & Argon Design System

```text
+-----------------------------------------------------------------------------------+
|                PySide6 Desktop Client (Argon Design System Edition)               |
|  +------------------------+  +------------------------+  +---------------------+  |
|  | Collapsible Sidebar    |  | Responsive QScrollArea |  | Argon Token Engine  |  |
|  | (13 Operational Views) |  | + 23-Step SOP Split UI |  | (Light/Dark + i18n) |  |
|  +-----------+------------+  +-----------+------------+  +----------+----------+  |
+--------------|---------------------------|--------------------------|-------------+
               |                           | HTTPS / REST (JSON)      |
               v                           v                          v
+-----------------------------------------------------------------------------------+
|                          FastAPI Application Server (`/api/v1`)                   |
|  +------------------------+  +------------------------+  +---------------------+  |
|  | JWT + 2FA Auth &       |  | SOPGateService, Issue  |  | Feature Flags &     |  |
|  | 7-Role RBAC Guard      |  | & Approval Engines     |  | Global Search       |  |
|  +-----------+------------+  +-----------+------------+  +----------+----------+  |
+--------------|---------------------------|--------------------------|-------------+
               v                           v                          v
+---------------------------+  +------------------------+  +------------------------+
| PostgreSQL 16 / SQLite 3  |  | Safe Read-Only Workers |  | ReportLab PDF &        |
| (16 Tables + Append-Only  |  | (HTTPX, TLS, Headers,  |  | openpyxl XLSX Exporter |
|  activity_events Trigger) |  |  BS4 Links, INV-02)    |  | + Revision Detection   |
+---------------------------+  +------------------------+  +------------------------+
```

### Centralized Argon Design Tokens (`ARGON_TOKENS`)

| Token Category | Token Key | Light Mode Value | Dark Mode Value | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| **Brand Primary** | `brand.primary` | `#5E72E4` | `#5E72E4` | Argon Indigo primary action buttons, active nav state, focus ring. |
| **Brand Accent** | `brand.accent` | `#11CDEF` | `#11CDEF` | Argon Cyan accents, subtitle highlights, info badges. |
| **Semantic Status** | `success` / `warning` / `danger` | `#2DCE89` / `#FB6340` / `#F5365C` | `#2DCE89` / `#FB6340` / `#F5365C` | High-contrast WCAG AA status indicators paired with icons and text. |
| **Surfaces** | `bg_canvas` / `bg_surface` / `bg_sidebar` | `#F7FAFC` / `#FFFFFF` / `#172B4D` | `#0B1528` / `#172B4D` / `#070D19` | Clean 8px-grid card surfaces and Argon Dark Navy navigation shell. |
| **Typography** | `font_ui` / `font_mono` | `Inter` / `JetBrains Mono` | `Inter` / `JetBrains Mono` | UI hierarchy and monospace `.htaccess` / `wp-config.php` rule snippets. |

## 2. Quick Start (Ubuntu / Debian / Windows / macOS)

### Option A: Local Virtual Environment (FastAPI + PySide6 Desktop GUI)

```bash
cd ~/Pictures/Dash-main

# 1. Create and activate a Python virtual environment (PEP 668 compliant)
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 3. Launch the Argon Edition PySide6 Desktop Command Center
python3 opshub_argon_edition.py
```

### Option B: Run FastAPI Backend Server & Desktop Client Separately

```bash
# Terminal 1: Start FastAPI Backend (Swagger UI at http://127.0.0.1:8000/docs)
source .venv/bin/activate
python3 opshub_argon_edition.py --server

# Terminal 2: Connect PySide6 Desktop Client over HTTP
source .venv/bin/activate
OPSHUB_API_URL=http://127.0.0.1:8000 python3 opshub_argon_edition.py
```

### Option C: Docker Compose (PostgreSQL 16 + FastAPI Backend)

```bash
docker-compose up --build -d
# Connect the desktop client to the containerized API:
OPSHUB_API_URL=http://127.0.0.1:8000 python3 opshub_argon_edition.py
```

## 3. REST API Reference (`/api/v1`)

| Method & Path | Permission Required | Description |
| :--- | :--- | :--- |
| `POST /api/v1/auth/login` | Public | Authenticates operator and returns JWT access/refresh tokens + 2FA challenge flag. |
| `POST /api/v1/auth/verify-2fa` | Authenticated | Verifies 6-digit TOTP code for sensitive operational sessions. |
| `GET /api/v1/design-tokens` | Public | Returns centralized Argon design system tokens (`ARGON_TOKENS`). |
| `GET /api/v1/feature-flags` | Public | Returns active runtime feature flags. |
| `PATCH /api/v1/feature-flags` | `manage_integrations` | Toggles runtime feature flags (`enforce_live_backup_gate`, `enable_2fa_totp_verification`, etc.). |
| `GET /api/v1/dashboard/summary` | `view_records` | Computes live SQL counts across active projects, due/overdue sites, sessions, issues, and backups. |
| `GET /api/v1/dashboard/drilldown/{key}` | `view_records` | Returns filtered underlying records for any clicked dashboard KPI card. |
| `POST /api/v1/websites/import` | `assign_work` | Bulk imports websites from CSV/Excel with duplicate `(domain, environment)` prevention. |
| `POST /api/v1/sessions` | `execute_maintenance` | Starts a 23-step SOP session, snapshots template version (`INV-04`), and applies `Staging`/`Divi` rules. |
| `PATCH /api/v1/sessions/{id}/items/{step}` | `execute_maintenance` | Updates step status/observations while enforcing Live Pre-Update Backup Gates (`HTTP 409`). |
| `POST /api/v1/sessions/{id}/run-readonly-checks` | `execute_maintenance` | Runs safe read-only checks and marks credential-gated steps `not_verified` (`INV-02`). |
| `POST /api/v1/sessions/{id}/close` | `execute_maintenance` | Enforces mandatory closure gates on Step 22 (`Final frontend check`) and Step 23 (`Review notes`). |
| `POST /api/v1/reports/sessions/{id}/pdf` | `export_reports` | Generates PDF completion report and flags `[UPDATED REVISION REPORT]` on repeat runs. |
| `POST /api/v1/reports/export-xlsx` | `export_reports` | Exports multi-sheet Excel compliance workbook via `openpyxl`. |

## 4. Testing & Quality Verification Commands

```bash
source .venv/bin/activate
PYTHONPATH=. python3 -m unittest discover -s tests -v
```

## 5. Changelog

* **v1.0.0 (2026-10-15):** Initial production release featuring the 16-table relational schema, append-only `activity_events` triggers, 23-step WordPress SOP workflow & gating engine, Argon Design System Light/Dark PySide6 desktop client with responsive `QScrollArea` geometry, collapsible sidebar, `i18n` (EN/ES/HI), JWT + 2FA endpoints, and PDF/XLSX report exporters.
